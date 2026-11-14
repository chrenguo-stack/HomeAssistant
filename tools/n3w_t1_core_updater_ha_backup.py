from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from n3w_t1_core_updater_v2_common import (
    SHA256,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)


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
        destination_root: Path,
    ) -> HaDataBackupRecord:
        ...

    def verify_backup(
        self,
        record: HaDataBackupRecord,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ) -> HaDataBackupRecord:
        ...

    def restore_preupgrade_backup(
        self,
        record: HaDataBackupRecord,
    ) -> None:
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
    expected_fields = {
        "archive_sha256",
        "archive_size_bytes",
        "manifest_sha256",
        "verified",
        "fsynced",
        "consistent_preupgrade_point",
        "complete_production_config",
        "storage_integrity_verified",
        "ownership_metadata_present",
        "confidentiality_protected",
        "authenticity_protected",
        "unsupported_external_state",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise UpdaterV2Error("ha_data_backup_document_invalid")
    try:
        record = HaDataBackupRecord(**value)
    except TypeError as error:
        raise UpdaterV2Error("ha_data_backup_document_invalid") from error
    return validate_backup_record(record)


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
PROGRESS_QUANTUM_BYTES = 64 * 1024 * 1024
BackupProgress = Callable[[str, int], None]


@dataclass(frozen=True)
class HaQuiesceEvidence:
    owner_inactive: bool
    homeassistant_stopped: bool
    manager_stopped: bool
    broker_preserved: bool

    def validate(self) -> "HaQuiesceEvidence":
        if any(
            value is not True
            for value in (
                self.owner_inactive,
                self.homeassistant_stopped,
                self.manager_stopped,
                self.broker_preserved,
            )
        ):
            raise UpdaterV2Error("ha_backup_quiesce_evidence_invalid")
        return self


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_file(
    path: Path,
    progress: BackupProgress | None = None,
) -> str:
    digest = hashlib.sha256()
    processed = 0
    next_report = PROGRESS_QUANTUM_BYTES
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            processed += len(chunk)
            if progress is not None and processed >= next_report:
                progress("hash", processed)
                next_report += PROGRESS_QUANTUM_BYTES
    return digest.hexdigest()


def _hmac_file(
    path: Path,
    *,
    key: bytes,
    prefix: bytes,
    progress: BackupProgress | None = None,
) -> str:
    digest = hmac.new(key, digestmod=hashlib.sha256)
    digest.update(prefix)
    processed = 0
    next_report = PROGRESS_QUANTUM_BYTES
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            processed += len(chunk)
            if progress is not None and processed >= next_report:
                progress("authenticate", processed)
                next_report += PROGRESS_QUANTUM_BYTES
    return digest.hexdigest()


class ProtectedHaDataBackupProvider:
    """Quiesced HA backup protected by SYSTEM_ROOT_KEY-derived subkeys."""

    def __init__(
        self,
        *,
        ha_data_root: Path = DEFAULT_HA_DATA_ROOT,
        system_root_key: Path = DEFAULT_SYSTEM_ROOT_KEY,
        product_config: Path = DEFAULT_PRODUCT_HA_CONFIG,
        openssl_binary: str = "openssl",
        tar_binary: str = "tar",
        progress: BackupProgress | None = None,
    ) -> None:
        self.ha_data_root = ha_data_root
        self.system_root_key = system_root_key
        self.product_config = product_config
        self.openssl_binary = openssl_binary
        self.tar_binary = tar_binary
        self.progress = progress

    def _report(self, phase: str, value: int = 0) -> None:
        if self.progress is not None:
            self.progress(phase, value)

    def _root_key(self) -> bytes:
        path = self.system_root_key
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("ha_data_backup_root_key_invalid")
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise UpdaterV2Error("ha_data_backup_root_key_mode_invalid")
        payload = path.read_bytes()
        if len(payload) != 32:
            raise UpdaterV2Error("ha_data_backup_root_key_invalid")
        return payload

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

    def _verify_sqlite(self) -> None:
        database = self.ha_data_root / "home-assistant_v2.db"
        if not database.exists():
            return
        if database.is_symlink() or not database.is_file():
            raise UpdaterV2Error("ha_data_backup_sqlite_invalid")
        try:
            connection = sqlite3.connect(
                f"file:{database}?mode=ro",
                uri=True,
                timeout=10.0,
            )
            try:
                rows = tuple(connection.execute("PRAGMA quick_check"))
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise UpdaterV2Error(
                "ha_data_backup_sqlite_check_failed"
            ) from error
        if rows != (("ok",),):
            raise UpdaterV2Error("ha_data_backup_sqlite_integrity_failed")

    @staticmethod
    def _passphrase_fd(passphrase: bytes) -> int:
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, passphrase + b"\n")
        finally:
            os.close(write_fd)
        return read_fd

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

    @staticmethod
    def _wait(
        process: subprocess.Popen[bytes],
        error_code: str,
    ) -> None:
        stderr = process.stderr.read() if process.stderr is not None else b""
        returncode = process.wait()
        if returncode != 0:
            raise UpdaterV2Error(
                error_code
                + ":"
                + stderr.decode("utf-8", errors="replace")[:120]
            )

    def _archive_to_encrypted(
        self,
        *,
        destination: Path,
        passphrase: bytes,
    ) -> None:
        read_fd = self._passphrase_fd(passphrase)
        try:
            with destination.open("w+b") as output:
                crypto = subprocess.Popen(
                    self._openssl_argv(
                        pass_fd=read_fd,
                        decrypt=False,
                    ),
                    stdin=subprocess.PIPE,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    pass_fds=(read_fd,),
                )
                os.close(read_fd)
                read_fd = -1
                if crypto.stdin is None:
                    raise UpdaterV2Error(
                        "ha_data_backup_crypto_pipe_invalid"
                    )
                archive = subprocess.Popen(
                    [
                        self.tar_binary,
                        "--create",
                        "--gzip",
                        "--file=-",
                        "--numeric-owner",
                        "--one-file-system",
                        "--directory",
                        str(self.ha_data_root),
                        ".",
                    ],
                    stdout=crypto.stdin,
                    stderr=subprocess.PIPE,
                )
                crypto.stdin.close()
                self._wait(
                    archive,
                    "ha_data_backup_archive_create_failed",
                )
                self._wait(crypto, "ha_data_backup_crypto_failed")
                output.flush()
                os.fsync(output.fileno())
        except (FileNotFoundError, OSError) as error:
            raise UpdaterV2Error(
                "ha_data_backup_host_tool_unavailable"
            ) from error
        finally:
            if read_fd >= 0:
                os.close(read_fd)

    def _decrypt_to_tar(
        self,
        *,
        archive_path: Path,
        passphrase: bytes,
        tar_args: list[str],
        capture_stdout: bool,
    ) -> bytes:
        read_fd = self._passphrase_fd(passphrase)
        try:
            with archive_path.open("rb") as source:
                crypto = subprocess.Popen(
                    self._openssl_argv(
                        pass_fd=read_fd,
                        decrypt=True,
                    ),
                    stdin=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    pass_fds=(read_fd,),
                )
                os.close(read_fd)
                read_fd = -1
                if crypto.stdout is None:
                    raise UpdaterV2Error(
                        "ha_data_backup_crypto_pipe_invalid"
                    )
                tar_process = subprocess.Popen(
                    [self.tar_binary, *tar_args],
                    stdin=crypto.stdout,
                    stdout=(
                        subprocess.PIPE
                        if capture_stdout
                        else subprocess.DEVNULL
                    ),
                    stderr=subprocess.PIPE,
                )
                crypto.stdout.close()
                stdout, stderr = tar_process.communicate()
                if tar_process.returncode != 0:
                    raise UpdaterV2Error(
                        "ha_data_backup_archive_verify_failed:"
                        + stderr.decode(
                            "utf-8",
                            errors="replace",
                        )[:120]
                    )
                self._wait(crypto, "ha_data_backup_crypto_failed")
                return stdout or b""
        except (FileNotFoundError, OSError) as error:
            raise UpdaterV2Error(
                "ha_data_backup_host_tool_unavailable"
            ) from error
        finally:
            if read_fd >= 0:
                os.close(read_fd)

    def _manifest_sha256(
        self,
        *,
        archive_path: Path,
        passphrase: bytes,
    ) -> str:
        listing = self._decrypt_to_tar(
            archive_path=archive_path,
            passphrase=passphrase,
            tar_args=[
                "--list",
                "--verbose",
                "--full-time",
                "--utc",
                "--quoting-style=escape",
                "--numeric-owner",
                "--gzip",
                "--file=-",
            ],
            capture_stdout=True,
        )
        return sha256_bytes(listing)

    def _compare_with_quiesced_source(
        self,
        *,
        archive_path: Path,
        passphrase: bytes,
    ) -> None:
        self._decrypt_to_tar(
            archive_path=archive_path,
            passphrase=passphrase,
            tar_args=[
                "--compare",
                "--numeric-owner",
                "--gzip",
                "--file=-",
                "--directory",
                str(self.ha_data_root),
            ],
            capture_stdout=False,
        )

    @staticmethod
    def _auth_prefix(
        transaction_id_sha256: str,
        manifest_sha256: str,
    ) -> bytes:
        return (
            b"gh.n3w.ha-backup.auth.v1\x00"
            + transaction_id_sha256.encode("ascii")
            + b"\x00"
            + manifest_sha256.encode("ascii")
            + b"\x00"
        )

    @staticmethod
    def _private_destination(path: Path) -> None:
        if path.is_symlink():
            raise UpdaterV2Error("ha_data_backup_directory_invalid")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.is_dir():
            raise UpdaterV2Error("ha_data_backup_directory_invalid")
        metadata = path.stat()
        if (
            metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise UpdaterV2Error(
                "ha_data_backup_directory_metadata_invalid"
            )

    @staticmethod
    def _write_metadata(
        path: Path,
        document: dict[str, object],
    ) -> None:
        descriptor, raw = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(raw)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(canonical(document))
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _metadata(
        self,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ) -> dict[str, object]:
        path = destination_root / BACKUP_METADATA_NAME
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("ha_data_backup_metadata_missing")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error(
                "ha_data_backup_metadata_invalid"
            ) from error
        expected = {
            "schema",
            "transaction_id_sha256",
            "archive_name",
            "archive_sha256",
            "archive_size_bytes",
            "manifest_sha256",
            "encryption",
            "authentication",
            "key_derivation",
            "auth_tag_sha256",
        }
        if not isinstance(document, dict) or set(document) != expected:
            raise UpdaterV2Error("ha_data_backup_metadata_invalid")
        if (
            document.get("schema") != BACKUP_SCHEMA
            or document.get("transaction_id_sha256")
            != transaction_id_sha256
            or document.get("archive_name") != BACKUP_ARCHIVE_NAME
            or document.get("encryption") != BACKUP_ENCRYPTION
            or document.get("authentication")
            != BACKUP_AUTHENTICATION
            or document.get("key_derivation")
            != BACKUP_KEY_DERIVATION
        ):
            raise UpdaterV2Error("ha_data_backup_metadata_invalid")
        return document

    def create_consistent_backup(
        self,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ) -> HaDataBackupRecord:
        if SHA256.fullmatch(transaction_id_sha256) is None:
            raise UpdaterV2Error(
                "ha_data_backup_transaction_id_invalid"
            )
        self._report("source_validation")
        self._validate_source_tree()
        self._verify_sqlite()
        passphrase, mac_key = self._keys(transaction_id_sha256)
        self._private_destination(destination_root)
        archive_path = destination_root / BACKUP_ARCHIVE_NAME
        metadata_path = destination_root / BACKUP_METADATA_NAME
        if archive_path.is_symlink() or metadata_path.is_symlink():
            raise UpdaterV2Error(
                "ha_data_backup_destination_invalid"
            )
        archive_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

        descriptor, raw = tempfile.mkstemp(
            prefix=f".{BACKUP_ARCHIVE_NAME}.",
            dir=destination_root,
        )
        os.close(descriptor)
        temporary = Path(raw)
        try:
            self._report("archive_encrypt")
            self._archive_to_encrypted(
                destination=temporary,
                passphrase=passphrase,
            )
            os.chmod(temporary, 0o600)
            manifest_sha256 = self._manifest_sha256(
                archive_path=temporary,
                passphrase=passphrase,
            )
            self._report("source_compare")
            self._compare_with_quiesced_source(
                archive_path=temporary,
                passphrase=passphrase,
            )
            archive_sha256 = _sha256_file(
                temporary,
                self.progress,
            )
            archive_size = temporary.stat().st_size
            auth_tag = _hmac_file(
                temporary,
                key=mac_key,
                prefix=self._auth_prefix(
                    transaction_id_sha256,
                    manifest_sha256,
                ),
                progress=self.progress,
            )
            os.replace(temporary, archive_path)
            _fsync_directory(destination_root)
            self._write_metadata(
                metadata_path,
                {
                    "schema": BACKUP_SCHEMA,
                    "transaction_id_sha256": transaction_id_sha256,
                    "archive_name": BACKUP_ARCHIVE_NAME,
                    "archive_sha256": archive_sha256,
                    "archive_size_bytes": archive_size,
                    "manifest_sha256": manifest_sha256,
                    "encryption": BACKUP_ENCRYPTION,
                    "authentication": BACKUP_AUTHENTICATION,
                    "key_derivation": BACKUP_KEY_DERIVATION,
                    "auth_tag_sha256": auth_tag,
                },
            )
        finally:
            temporary.unlink(missing_ok=True)

        record = HaDataBackupRecord(
            archive_sha256=archive_sha256,
            archive_size_bytes=archive_size,
            manifest_sha256=manifest_sha256,
            verified=True,
            fsynced=True,
            consistent_preupgrade_point=True,
            complete_production_config=True,
            storage_integrity_verified=True,
            ownership_metadata_present=True,
            confidentiality_protected=True,
            authenticity_protected=True,
            unsupported_external_state=False,
        )
        return self.verify_backup(
            record,
            transaction_id_sha256=transaction_id_sha256,
            destination_root=destination_root,
        )

    def verify_backup(
        self,
        record: HaDataBackupRecord,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ) -> HaDataBackupRecord:
        validated = validate_backup_record(record)
        self._private_destination(destination_root)
        metadata = self._metadata(
            transaction_id_sha256=transaction_id_sha256,
            destination_root=destination_root,
        )
        archive_path = destination_root / BACKUP_ARCHIVE_NAME
        if archive_path.is_symlink() or not archive_path.is_file():
            raise UpdaterV2Error("ha_data_backup_archive_missing")
        if (
            metadata.get("archive_sha256")
            != validated.archive_sha256
            or metadata.get("archive_size_bytes")
            != validated.archive_size_bytes
            or metadata.get("manifest_sha256")
            != validated.manifest_sha256
            or archive_path.stat().st_size
            != validated.archive_size_bytes
        ):
            raise UpdaterV2Error("ha_data_backup_identity_drift")
        self._report("verify_ciphertext")
        if (
            _sha256_file(archive_path, self.progress)
            != validated.archive_sha256
        ):
            raise UpdaterV2Error(
                "ha_data_backup_archive_hash_mismatch"
            )

        passphrase, mac_key = self._keys(transaction_id_sha256)
        observed_tag = _hmac_file(
            archive_path,
            key=mac_key,
            prefix=self._auth_prefix(
                transaction_id_sha256,
                validated.manifest_sha256,
            ),
            progress=self.progress,
        )
        stored_tag = metadata.get("auth_tag_sha256")
        if (
            not isinstance(stored_tag, str)
            or SHA256.fullmatch(stored_tag) is None
            or not hmac.compare_digest(observed_tag, stored_tag)
        ):
            raise UpdaterV2Error(
                "ha_data_backup_authentication_failed"
            )
        self._report("verify_plaintext")
        if (
            self._manifest_sha256(
                archive_path=archive_path,
                passphrase=passphrase,
            )
            != validated.manifest_sha256
        ):
            raise UpdaterV2Error(
                "ha_data_backup_manifest_hash_mismatch"
            )
        self._report("verified", validated.archive_size_bytes)
        return validated

    def restore_preupgrade_backup(
        self,
        record: HaDataBackupRecord,
    ) -> None:
        validate_backup_record(record)
        raise UpdaterV2Error(
            "ha_data_backup_restore_requires_separate_gate"
        )
