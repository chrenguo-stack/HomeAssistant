from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error, canonical


@dataclass(frozen=True)
class HaDataBackupRecord:
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    verified: bool
    fsynced: bool
    consistent_preupgrade_point: bool
    complete_production_config: bool
    storage_integrity_verified: bool
    ownership_metadata_present: bool
    confidentiality_protected: bool
    authenticity_protected: bool
    unsupported_external_state: bool

    def public(self) -> dict[str, str | int | bool]:
        return {
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "manifest_sha256": self.manifest_sha256,
            "verified": self.verified,
            "fsynced": self.fsynced,
            "consistent_preupgrade_point": self.consistent_preupgrade_point,
            "complete_production_config": self.complete_production_config,
            "storage_integrity_verified": self.storage_integrity_verified,
            "ownership_metadata_present": self.ownership_metadata_present,
            "confidentiality_protected": self.confidentiality_protected,
            "authenticity_protected": self.authenticity_protected,
            "unsupported_external_state": self.unsupported_external_state,
        }


class HaDataBackupProvider(Protocol):
    def create_consistent_backup(
        self,
        *,
        transaction_id_sha256: str,
    ) -> HaDataBackupRecord:
        ...

    def verify_backup(
        self,
        record: HaDataBackupRecord,
    ) -> HaDataBackupRecord:
        ...



def validate_backup_record(record: HaDataBackupRecord) -> HaDataBackupRecord:
    if (
        not isinstance(record.archive_sha256, str)
        or SHA256.fullmatch(record.archive_sha256) is None
        or not isinstance(record.manifest_sha256, str)
        or SHA256.fullmatch(record.manifest_sha256) is None
        or not isinstance(record.archive_size_bytes, int)
        or isinstance(record.archive_size_bytes, bool)
        or record.archive_size_bytes <= 0
    ):
        raise UpdaterV2Error("ha_data_backup_identity_invalid")
    if record.unsupported_external_state is True:
        raise UpdaterV2Error("ha_data_backup_external_state_unsupported")
    required_true = (
        record.verified,
        record.fsynced,
        record.consistent_preupgrade_point,
        record.complete_production_config,
        record.storage_integrity_verified,
        record.ownership_metadata_present,
        record.confidentiality_protected,
        record.authenticity_protected,
    )
    if any(value is not True for value in required_true):
        raise UpdaterV2Error("ha_data_backup_contract_incomplete")
    return record


def backup_record_from_document(value: object) -> HaDataBackupRecord:
    if not isinstance(value, dict):
        raise UpdaterV2Error("ha_data_backup_document_invalid")
    try:
        return validate_backup_record(HaDataBackupRecord(**value))
    except TypeError as error:
        raise UpdaterV2Error("ha_data_backup_document_invalid") from error


BACKUP_SCHEMA = "gh.n3w-t1-ha-data-backup-protected/1"
BACKUP_ARCHIVE_NAME = "homeassistant-preupgrade.tar.gz.enc"
BACKUP_METADATA_NAME = "homeassistant-preupgrade.metadata.json"
BACKUP_ENCRYPTION = "aes-256-ctr+pbkdf2-sha256"
BACKUP_AUTHENTICATION = "hmac-sha256-etm"
BACKUP_KEY_DERIVATION = "hmac-sha256-system-root-key-v1"
BACKUP_PBKDF2_ITERATIONS = 200_000
DEFAULT_HA_DATA_ROOT = Path("/var/lib/n3wfc4-homeassistant")
DEFAULT_SYSTEM_ROOT_KEY = Path(
    "/var/lib/greenhouse-manager/identity/system-root.key"
)
DEFAULT_PRODUCT_HA_CONFIG = Path(
    "/opt/HomeAssistant/infra/n3w-t1/production/"
    "homeassistant-configuration.yaml"
)
EXTERNAL_DB_RE = re.compile(rb"(?m)^[ \t]*db_url[ \t]*:")


class ProtectedHaDataBackup:
    """Create and verify a quiesced HA archive in a pinned private directory."""

    def __init__(
        self, *, work_root: Path, ha_data_root: Path = DEFAULT_HA_DATA_ROOT,
        system_root_key: Path = DEFAULT_SYSTEM_ROOT_KEY,
        product_config: Path = DEFAULT_PRODUCT_HA_CONFIG,
    ) -> None:
        self.work_root = work_root
        self.ha_data_root = ha_data_root
        self.system_root_key = system_root_key
        self.product_config = product_config
        self.openssl_binary = "/usr/bin/openssl"
        self.tar_binary = "/usr/bin/tar"

    def _root_key(self) -> bytes:
        directory = self.system_root_key.parent
        if directory.is_symlink() or stat.S_IMODE(directory.stat().st_mode) & 0o022:
            raise UpdaterV2Error("ha_data_backup_root_key_directory_invalid")
        fd = os.open(self.system_root_key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as key:
            entry = os.fstat(key.fileno())
            if (
                not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1
                or stat.S_IMODE(entry.st_mode) != 0o600 or entry.st_size != 32
            ):
                raise UpdaterV2Error("ha_data_backup_root_key_invalid")
            value = key.read(33)
            if len(value) != 32:
                raise UpdaterV2Error("ha_data_backup_root_key_invalid")
            return value

    @staticmethod
    def _derive(
        root_key: bytes,
        transaction_id_sha256: str,
        purpose: bytes,
    ) -> bytes:
        if SHA256.fullmatch(transaction_id_sha256) is None:
            raise UpdaterV2Error("ha_data_backup_transaction_id_invalid")
        return hmac.new(
            root_key,
            b"gh.n3w.ha-backup.v1\x00"
            + purpose
            + b"\x00"
            + transaction_id_sha256.encode("ascii"),
            hashlib.sha256,
        ).digest()

    def _keys(self, transaction_id_sha256: str) -> tuple[bytes, bytes]:
        root = self._root_key()
        passphrase = self._derive(root, transaction_id_sha256, b"enc")
        mac_key = self._derive(root, transaction_id_sha256, b"mac")
        return passphrase.hex().encode("ascii"), mac_key

    def _validate_source_tree(self) -> None:
        root = self.ha_data_root
        if root.is_symlink() or not root.is_dir():
            raise UpdaterV2Error("ha_data_backup_source_invalid")
        try:
            resolved_root = root.resolve(strict=True)
            root_device = root.stat().st_dev
        except OSError as error:
            raise UpdaterV2Error("ha_data_backup_source_invalid") from error

        yaml_paths: list[Path] = []
        if self.product_config.exists():
            yaml_paths.append(self.product_config)
        for directory, names, files in os.walk(root, followlinks=False):
            base = Path(directory)
            for name in names + files:
                path = base / name
                try:
                    metadata = path.lstat()
                except OSError as error:
                    raise UpdaterV2Error("ha_data_backup_scan_failed") from error
                if stat.S_ISLNK(metadata.st_mode):
                    try:
                        target = path.resolve(strict=True)
                        target.relative_to(resolved_root)
                        if target.stat().st_dev != root_device:
                            raise UpdaterV2Error(
                                "ha_data_backup_external_state_unsupported"
                            )
                    except UpdaterV2Error:
                        raise
                    except (OSError, ValueError) as error:
                        raise UpdaterV2Error(
                            "ha_data_backup_external_state_unsupported"
                        ) from error
                elif not (
                    stat.S_ISDIR(metadata.st_mode)
                    or stat.S_ISREG(metadata.st_mode)
                ):
                    raise UpdaterV2Error(
                        "ha_data_backup_special_file_unsupported"
                    )
                elif metadata.st_dev != root_device:
                    raise UpdaterV2Error(
                        "ha_data_backup_external_state_unsupported"
                    )
                if (
                    stat.S_ISREG(metadata.st_mode)
                    and path.suffix.lower() in {".yaml", ".yml"}
                ):
                    yaml_paths.append(path)

        for path in yaml_paths:
            try:
                payload = path.read_bytes()
            except OSError as error:
                raise UpdaterV2Error(
                    "ha_data_backup_external_state_probe_failed"
                ) from error
            if EXTERNAL_DB_RE.search(payload):
                raise UpdaterV2Error(
                    "ha_data_backup_external_state_unsupported"
                )

    def _openssl_argv(self, *, pass_fd: int, decrypt: bool) -> list[str]:
        argv = [
            self.openssl_binary,
            "enc",
            "-aes-256-ctr",
            "-pbkdf2",
            "-iter",
            str(BACKUP_PBKDF2_ITERATIONS),
            "-md",
            "sha256",
            "-salt",
            "-pass",
            f"fd:{pass_fd}",
        ]
        if decrypt:
            argv.append("-d")
        return argv

    def _verify_sqlite(self) -> None:
        database = self.ha_data_root / "home-assistant_v2.db"
        sidecars = [Path(str(database) + suffix) for suffix in ("-wal", "-journal", "-shm")]
        present = [path for path in sidecars if path.exists() or path.is_symlink()]
        if not database.exists() and not present:
            return
        if any(path.is_symlink() or not path.is_file() for path in [database, *present]):
            raise UpdaterV2Error("ha_data_backup_sqlite_invalid")
        try:
            if present:
                work = self.work_root.lstat()
                if (not stat.S_ISDIR(work.st_mode) or work.st_uid != os.geteuid()
                    or stat.S_IMODE(work.st_mode) & 0o077):
                    raise UpdaterV2Error("ha_data_backup_work_directory_invalid")
                with tempfile.TemporaryDirectory(prefix=".ha-sqlite-", dir=self.work_root) as directory:
                    scratch = Path(directory)
                    for path in [database, *present]:
                        if not path.name.endswith("-shm"):
                            shutil.copyfile(path, scratch / path.name)
                    self._quick_check((scratch / database.name).as_uri() + "?mode=rw")
            else:
                self._quick_check(database.as_uri() + "?mode=ro&immutable=1")
        except (OSError, sqlite3.Error) as error:
            raise UpdaterV2Error("ha_data_backup_sqlite_check_failed") from error

    @staticmethod
    def _quick_check(uri: str) -> None:
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        try:
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise UpdaterV2Error("ha_data_backup_sqlite_integrity_failed")
        finally:
            connection.close()

    def _tar_pipeline(
        self,
        stream: BinaryIO,
        passphrase: bytes,
        tar_args: list[str],
        *,
        decrypt: bool,
        hash_listing: bool = False,
    ) -> str:
        read_fd, write_fd = os.pipe()
        processes: list[subprocess.Popen[bytes]] = []
        try:
            with os.fdopen(write_fd, "wb") as writer:
                writer.write(passphrase + b"\n")
            crypto = self._openssl_argv(pass_fd=read_fd, decrypt=decrypt)
            tar = [self.tar_binary, *tar_args]
            producer = subprocess.Popen(
                crypto if decrypt else tar,
                stdin=stream if decrypt else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                pass_fds=(read_fd,) if decrypt else (),
            )
            processes.append(producer)
            assert producer.stdout is not None
            try:
                consumer = subprocess.Popen(
                    tar if decrypt else crypto,
                    stdin=producer.stdout,
                    stdout=subprocess.PIPE if hash_listing else (subprocess.DEVNULL if decrypt else stream),
                    stderr=subprocess.DEVNULL,
                    pass_fds=() if decrypt else (read_fd,),
                )
                processes.append(consumer)
            finally:
                producer.stdout.close()
            digest = hashlib.sha256()
            if consumer.stdout is not None:
                with consumer.stdout as listing:
                    while block := listing.read(1024 * 1024):
                        digest.update(block)
            if consumer.wait() != 0 or producer.wait() != 0:
                raise UpdaterV2Error("ha_data_backup_archive_pipeline_failed")
            return digest.hexdigest()
        except OSError as error:
            raise UpdaterV2Error("ha_data_backup_archive_io_failed") from error
        finally:
            os.close(read_fd)
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait()

    @staticmethod
    def _ciphertext_identity(
        stream: BinaryIO, mac_key: bytes, transaction_id: str, manifest_sha: str
    ) -> tuple[str, str]:
        digest = hashlib.sha256()
        tag = hmac.new(mac_key, digestmod=hashlib.sha256)
        tag.update(
            b"gh.n3w.ha-backup.auth.v1\x00"
            + transaction_id.encode("ascii") + b"\x00" + manifest_sha.encode("ascii") + b"\x00"
        )
        stream.seek(0)
        while block := stream.read(1024 * 1024):
            digest.update(block)
            tag.update(block)
        return digest.hexdigest(), tag.hexdigest()

    def _manifest(self, stream: BinaryIO, passphrase: bytes) -> str:
        stream.seek(0)
        return self._tar_pipeline(
            stream, passphrase,
            ["--list", "--verbose", "--full-time", "--utc", "--quoting-style=escape",
             "--numeric-owner", "--gzip", "--file=-"],
            decrypt=True, hash_listing=True,
        )

    @staticmethod
    def _metadata(
        transaction_id: str, record: HaDataBackupRecord, tag: str
    ) -> dict[str, object]:
        return {
            "schema": BACKUP_SCHEMA,
            "transaction_id_sha256": transaction_id,
            "archive_name": BACKUP_ARCHIVE_NAME,
            "archive_sha256": record.archive_sha256,
            "archive_size_bytes": record.archive_size_bytes,
            "manifest_sha256": record.manifest_sha256,
            "encryption": BACKUP_ENCRYPTION,
            "authentication": BACKUP_AUTHENTICATION,
            "key_derivation": BACKUP_KEY_DERIVATION,
            "auth_tag_sha256": tag,
        }

    @staticmethod
    def _file(directory: int, name: str, *, create: bool = False) -> BinaryIO:
        flags = os.O_NOFOLLOW | os.O_NONBLOCK
        flags |= os.O_RDWR | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY
        fd = os.open(name, flags, 0o600, dir_fd=directory)
        stream = os.fdopen(fd, "r+b" if create else "rb", buffering=0)
        entry = os.fstat(fd)
        if (
            not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1
            or entry.st_uid != os.geteuid() or stat.S_IMODE(entry.st_mode) != 0o600
            or entry.st_dev != os.fstat(directory).st_dev
        ):
            stream.close()
            raise UpdaterV2Error("ha_data_backup_file_identity_invalid")
        return stream

    def create(self, directory: int, transaction_id: str) -> HaDataBackupRecord:
        """Seal the snapshot. The install controller reopens it before admission."""
        self._validate_source_tree()
        self._verify_sqlite()
        passphrase, mac_key = self._keys(transaction_id)
        with self._file(directory, BACKUP_ARCHIVE_NAME, create=True) as archive:
            self._tar_pipeline(
                archive, passphrase,
                ["--create", "--gzip", "--file=-", "--numeric-owner", "--one-file-system",
                 "--directory", str(self.ha_data_root), "."],
                decrypt=False,
            )
            os.fsync(archive.fileno())
            manifest = self._manifest(archive, passphrase)
            archive.seek(0)
            self._tar_pipeline(
                archive, passphrase,
                ["--compare", "--numeric-owner", "--gzip", "--file=-",
                 "--directory", str(self.ha_data_root)],
                decrypt=True,
            )
            digest, tag = self._ciphertext_identity(archive, mac_key, transaction_id, manifest)
            record = HaDataBackupRecord(
                archive_sha256=digest, archive_size_bytes=os.fstat(archive.fileno()).st_size,
                manifest_sha256=manifest, verified=True, fsynced=True,
                consistent_preupgrade_point=True, complete_production_config=True,
                storage_integrity_verified=True, ownership_metadata_present=True,
                confidentiality_protected=True, authenticity_protected=True,
                unsupported_external_state=False,
            )
        with self._file(directory, BACKUP_METADATA_NAME, create=True) as metadata:
            metadata.write(canonical(self._metadata(transaction_id, record, tag)) + b"\n")
            metadata.flush()
            os.fsync(metadata.fileno())
        os.fsync(directory)
        return record

    def verify(self, directory: int, transaction_id: str, record: HaDataBackupRecord) -> HaDataBackupRecord:
        validate_backup_record(record)
        passphrase, mac_key = self._keys(transaction_id)
        with self._file(directory, BACKUP_METADATA_NAME) as metadata:
            raw = metadata.read(16_385)
        try:
            if len(raw) > 16_384:
                raise ValueError("oversized metadata")
            stored = json.loads(raw)
        except (UnicodeError, ValueError) as error:
            raise UpdaterV2Error("ha_data_backup_metadata_invalid") from error
        with self._file(directory, BACKUP_ARCHIVE_NAME) as archive:
            before = os.fstat(archive.fileno())
            if before.st_size != record.archive_size_bytes:
                raise UpdaterV2Error("ha_data_backup_identity_drift")
            digest, tag = self._ciphertext_identity(
                archive, mac_key, transaction_id, record.manifest_sha256
            )
            if digest != record.archive_sha256:
                raise UpdaterV2Error("ha_data_backup_archive_hash_mismatch")
            observed_tag = stored.get("auth_tag_sha256") if isinstance(stored, dict) else None
            if (
                not isinstance(observed_tag, str) or SHA256.fullmatch(observed_tag) is None
                or not hmac.compare_digest(tag, observed_tag)
                or stored != self._metadata(transaction_id, record, tag)
            ):
                raise UpdaterV2Error("ha_data_backup_authentication_failed")
            if self._manifest(archive, passphrase) != record.manifest_sha256:
                raise UpdaterV2Error("ha_data_backup_manifest_hash_mismatch")
            after = os.stat(BACKUP_ARCHIVE_NAME, dir_fd=directory, follow_symlinks=False)
            if (
                not os.path.samestat(before, after) or before.st_size != after.st_size
                or before.st_ctime_ns != after.st_ctime_ns
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise UpdaterV2Error("ha_data_backup_archive_changed")
        return record
