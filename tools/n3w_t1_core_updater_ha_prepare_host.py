from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import n3w_t1_portable_image_identity as portable
from n3w_t1_core_updater_ha_prepare import (
    HostUsbCandidate,
    PreparedUsbMedia,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb_media import (
    USB_LABEL,
    UsbCapacityInputs,
    validate_filesystem_uuid,
)
from n3w_t1_core_updater_v2_common import (
    SHA256,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)

HOST_RELEASE_POLICY_SCHEMA = "gh.n3w-t1-ha-ota-host-release-policy/1"
USB_TX_MANIFEST_SCHEMA = "gh.n3w-t1-ha-usb-transaction-manifest/1"
USB_TX_PHASE_SCHEMA = "gh.n3w-t1-ha-usb-transaction-phase/1"
USB_TX_CHECKSUM_SCHEMA = "gh.n3w-t1-ha-usb-checksums/1"
DEFAULT_HOST_RELEASE_POLICY = Path(
    "/etc/n3w-t1-ota/homeassistant-release-source.json"
)
DEFAULT_RUNTIME_ROOT = Path("/run/n3w-t1-ota")
MAX_POLICY_BYTES = 64 * 1024
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024
MAX_CAPACITY_INPUT_BYTES = 64 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class HostReleasePolicy:
    release_identity: str
    artifact_url: str
    target_archive_sha256: str
    target_archive_size_bytes: int
    predecessor_recovery_worst_case_bytes: int
    ha_data_backup_worst_case_bytes: int
    transaction_metadata_and_working_bytes: int
    removable_media_reserve_bytes: int

    def validate(self) -> "HostReleasePolicy":
        if (
            not isinstance(self.release_identity, str)
            or not 3 <= len(self.release_identity) <= 128
            or any(character.isspace() for character in self.release_identity)
        ):
            raise UpdaterV2Error("ha_prepare_policy_release_invalid")
        parsed = urllib.parse.urlsplit(self.artifact_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise UpdaterV2Error("ha_prepare_policy_artifact_url_invalid")
        if (
            not isinstance(self.target_archive_sha256, str)
            or SHA256.fullmatch(self.target_archive_sha256) is None
        ):
            raise UpdaterV2Error("ha_prepare_policy_archive_sha_invalid")
        if (
            type(self.target_archive_size_bytes) is not int
            or self.target_archive_size_bytes <= 0
            or self.target_archive_size_bytes > MAX_DOWNLOAD_BYTES
        ):
            raise UpdaterV2Error("ha_prepare_policy_capacity_invalid")
        capacity_values = (
            self.predecessor_recovery_worst_case_bytes,
            self.ha_data_backup_worst_case_bytes,
            self.transaction_metadata_and_working_bytes,
            self.removable_media_reserve_bytes,
        )
        if any(
            type(value) is not int
            or value <= 0
            or value > MAX_CAPACITY_INPUT_BYTES
            for value in capacity_values
        ):
            raise UpdaterV2Error("ha_prepare_policy_capacity_invalid")
        return self

    def capacity_inputs(self) -> UsbCapacityInputs:
        self.validate()
        return UsbCapacityInputs(
            target_artifact_bytes=self.target_archive_size_bytes,
            predecessor_recovery_worst_case_bytes=(
                self.predecessor_recovery_worst_case_bytes
            ),
            ha_data_backup_worst_case_bytes=self.ha_data_backup_worst_case_bytes,
            transaction_metadata_and_working_bytes=(
                self.transaction_metadata_and_working_bytes
            ),
            removable_media_reserve_bytes=self.removable_media_reserve_bytes,
        )


def _reject_duplicate_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UpdaterV2Error("ha_prepare_json_duplicate_field")
        result[key] = value
    return result


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _root_owned_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_file()
    ):
        raise UpdaterV2Error("ha_prepare_policy_path_invalid")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or metadata.st_size <= 0
        or metadata.st_size > max_bytes
    ):
        raise UpdaterV2Error("ha_prepare_policy_metadata_invalid")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdaterV2Error("ha_prepare_policy_json_invalid") from error
    if not isinstance(document, dict):
        raise UpdaterV2Error("ha_prepare_policy_json_invalid")
    return document


class FixedHostReleasePolicyProvider:
    def __init__(self, path: Path = DEFAULT_HOST_RELEASE_POLICY) -> None:
        self.path = path

    def load(self, transaction: dict[str, Any]) -> HostReleasePolicy:
        document = _root_owned_json(self.path, max_bytes=MAX_POLICY_BYTES)
        expected = {
            "schema",
            "release_identity",
            "artifact_url",
            "target_archive_sha256",
            "target_archive_size_bytes",
            "predecessor_recovery_worst_case_bytes",
            "ha_data_backup_worst_case_bytes",
            "transaction_metadata_and_working_bytes",
            "removable_media_reserve_bytes",
        }
        if set(document) != expected or document.get("schema") != HOST_RELEASE_POLICY_SCHEMA:
            raise UpdaterV2Error("ha_prepare_policy_schema_invalid")
        policy = HostReleasePolicy(
            release_identity=document["release_identity"],
            artifact_url=document["artifact_url"],
            target_archive_sha256=document["target_archive_sha256"],
            target_archive_size_bytes=document["target_archive_size_bytes"],
            predecessor_recovery_worst_case_bytes=document[
                "predecessor_recovery_worst_case_bytes"
            ],
            ha_data_backup_worst_case_bytes=document[
                "ha_data_backup_worst_case_bytes"
            ],
            transaction_metadata_and_working_bytes=document[
                "transaction_metadata_and_working_bytes"
            ],
            removable_media_reserve_bytes=document[
                "removable_media_reserve_bytes"
            ],
        ).validate()
        manifest = transaction.get("target_manifest_identity")
        if not isinstance(manifest, dict):
            raise UpdaterV2Error("ha_prepare_policy_manifest_invalid")
        if (
            policy.release_identity != manifest.get("release_identity")
            or policy.target_archive_sha256
            != transaction.get("target_archive_sha256")
            or policy.target_archive_size_bytes
            != transaction.get("target_archive_size")
        ):
            raise UpdaterV2Error("ha_prepare_policy_binding_drift")
        return policy


def _run(
    argv: tuple[str, ...],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 30,
) -> bytes:
    try:
        result = subprocess.run(
            argv,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise UpdaterV2Error("ha_prepare_host_tool_missing") from error
    except subprocess.TimeoutExpired as error:
        raise UpdaterV2Error("ha_prepare_host_command_timeout") from error
    if result.returncode:
        raise UpdaterV2Error("ha_prepare_host_command_failed")
    return result.stdout


def _run_optional(
    argv: tuple[str, ...],
    *,
    timeout: int = 30,
) -> bytes | None:
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise UpdaterV2Error("ha_prepare_host_tool_missing") from error
    except subprocess.TimeoutExpired as error:
        raise UpdaterV2Error("ha_prepare_host_command_timeout") from error
    if result.returncode:
        return None
    return result.stdout


def _strict_json_bytes(payload: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdaterV2Error(code) from error
    if not isinstance(value, dict):
        raise UpdaterV2Error(code)
    return value


def _flatten_blocks(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(node)
        children = node.get("children")
        if isinstance(children, list):
            result.extend(
                _flatten_blocks(
                    [child for child in children if isinstance(child, dict)]
                )
            )
    return result


def _mountpoints(node: dict[str, Any]) -> tuple[str, ...]:
    value = node.get("mountpoints")
    if value is None:
        legacy = node.get("mountpoint")
        value = [] if legacy is None else [legacy]
    if not isinstance(value, list):
        return ()
    return tuple(
        item
        for item in value
        if isinstance(item, str) and item.strip()
    )


def _boolish(value: Any) -> bool:
    return value is True or value == 1 or value == "1"


def _require_private_directory(
    path: Path,
    *,
    create: bool = False,
    allow_group_read_execute: bool = False,
) -> None:
    if path.is_symlink():
        raise UpdaterV2Error("usb_runtime_directory_invalid")
    if not path.exists():
        if not create:
            raise UpdaterV2Error("usb_runtime_directory_invalid")
        path.mkdir(parents=True, mode=0o700)
    if not path.is_dir():
        raise UpdaterV2Error("usb_runtime_directory_invalid")
    metadata = path.stat()
    mode = stat.S_IMODE(metadata.st_mode)
    forbidden = 0o027 if allow_group_read_execute else 0o077
    if metadata.st_uid != os.geteuid() or mode & forbidden:
        raise UpdaterV2Error("usb_runtime_directory_metadata_invalid")


def _stable_fingerprint(node: dict[str, Any]) -> str:
    serial = node.get("serial")
    wwn = node.get("wwn")
    stable = serial if isinstance(serial, str) and serial.strip() else wwn
    if not isinstance(stable, str) or not stable.strip():
        raise UpdaterV2Error("usb_stable_identity_unavailable")
    identity = {
        "stable_id": stable.strip(),
        "model": str(node.get("model") or "").strip(),
        "size": node.get("size"),
        "transport": str(node.get("tran") or "").strip().lower(),
    }
    return sha256_bytes(canonical(identity))


class SubprocessPrepareBackend:
    """Fixed-command host backend. MQTT never supplies device paths or URLs."""

    def __init__(
        self,
        *,
        policy_provider: FixedHostReleasePolicyProvider | None = None,
        runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    ) -> None:
        self.policy_provider = policy_provider or FixedHostReleasePolicyProvider()
        self.runtime_root = runtime_root

    def _lsblk(self) -> list[dict[str, Any]]:
        payload = _run(
            (
                "lsblk",
                "--json",
                "--bytes",
                "--paths",
                "--output",
                "PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN",
            )
        )
        document = _strict_json_bytes(payload, "usb_inventory_invalid")
        blocks = document.get("blockdevices")
        if not isinstance(blocks, list):
            raise UpdaterV2Error("usb_inventory_invalid")
        return [node for node in blocks if isinstance(node, dict)]

    def inventory(self) -> tuple[HostUsbCandidate, ...]:
        root_major_minor = _run(
            ("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
        ).decode("utf-8", errors="strict").strip()
        if not root_major_minor:
            raise UpdaterV2Error("usb_root_device_unresolved")
        candidates: list[HostUsbCandidate] = []
        for disk in self._lsblk():
            if disk.get("type") != "disk":
                continue
            descendants = _flatten_blocks([disk])
            major_minors = {
                str(item.get("maj:min") or "").strip()
                for item in descendants
            }
            mounted = any(_mountpoints(item) for item in descendants)
            path = disk.get("path")
            if not isinstance(path, str) or not path.startswith("/dev/"):
                continue
            transport = str(disk.get("tran") or "").strip().lower()
            removable = _boolish(disk.get("rm"))
            if transport != "usb" and not removable:
                continue
            try:
                size = int(disk.get("size"))
            except (TypeError, ValueError):
                size = 0
            candidate = HostUsbCandidate(
                locator=path,
                public_fingerprint=_stable_fingerprint(disk),
                display_model=(
                    str(disk.get("model") or "").strip()
                    or "USB Mass Storage"
                ),
                display_capacity_bytes=size,
                newly_inserted=True,
                removable=removable,
                mass_storage=transport == "usb",
                read_only=_boolish(disk.get("ro")),
                is_root_device=root_major_minor in major_minors,
                backs_production_mount=mounted,
            )
            candidates.append(candidate.validate())
        return tuple(candidates)

    def capacity_inputs(
        self,
        transaction: dict[str, Any],
    ) -> UsbCapacityInputs:
        return self.policy_provider.load(transaction).capacity_inputs()

    def _same_candidate(self, candidate: HostUsbCandidate) -> HostUsbCandidate:
        matches = tuple(
            observed
            for observed in self.inventory()
            if observed.public_fingerprint == candidate.public_fingerprint
        )
        if len(matches) != 1:
            raise UpdaterV2Error("usb_format_candidate_drift")
        observed = matches[0]
        if (
            observed.locator != candidate.locator
            or observed.display_model.strip() != candidate.display_model.strip()
            or observed.display_capacity_bytes
            != candidate.display_capacity_bytes
        ):
            raise UpdaterV2Error("usb_format_candidate_drift")
        if (
            observed.read_only
            or observed.is_root_device
            or observed.backs_production_mount
            or not observed.removable
            or not observed.mass_storage
        ):
            raise UpdaterV2Error("usb_format_target_not_eligible")
        return observed

    @staticmethod
    def _partition(locator: str) -> str:
        payload = _run(
            (
                "lsblk",
                "--json",
                "--paths",
                "--output",
                "PATH,TYPE,PKNAME",
                locator,
            )
        )
        document = _strict_json_bytes(payload, "usb_partition_inventory_invalid")
        blocks = document.get("blockdevices")
        if not isinstance(blocks, list):
            raise UpdaterV2Error("usb_partition_inventory_invalid")
        nodes = _flatten_blocks(
            [item for item in blocks if isinstance(item, dict)]
        )
        partitions = [
            item.get("path")
            for item in nodes
            if item.get("type") == "part"
            and isinstance(item.get("path"), str)
        ]
        if len(partitions) != 1:
            raise UpdaterV2Error("usb_partition_shape_invalid")
        return str(partitions[0])

    @staticmethod
    def _self_test(mount_path: Path) -> None:
        payload = os.urandom(64 * 1024)
        expected = hashlib.sha256(payload).digest()
        path = mount_path / ".n3w-usb-selftest"
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if hashlib.sha256(path.read_bytes()).digest() != expected:
                raise UpdaterV2Error("usb_selftest_hash_mismatch")
        finally:
            path.unlink(missing_ok=True)
        directory = os.open(
            mount_path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def format_and_mount(
        self,
        *,
        candidate: HostUsbCandidate,
        transaction_id_sha256: str,
    ) -> PreparedUsbMedia:
        if SHA256.fullmatch(transaction_id_sha256) is None:
            raise UpdaterV2Error("ha_usb_transaction_id_invalid")
        observed = self._same_candidate(candidate)
        _run(("wipefs", "--all", "--force", observed.locator))
        _run(
            (
                "sfdisk",
                "--wipe",
                "always",
                "--wipe-partitions",
                "always",
                observed.locator,
            ),
            input_bytes=b"label: gpt\n,;\n",
        )
        _run(("udevadm", "settle"))
        partition = self._partition(observed.locator)
        _run(("mkfs.ext4", "-F", "-L", USB_LABEL, partition), timeout=120)

        _require_private_directory(
            self.runtime_root,
            allow_group_read_execute=True,
        )
        mount_root = self.runtime_root / "media"
        _require_private_directory(mount_root, create=True)
        mount_path = mount_root / transaction_id_sha256[:16]
        _require_private_directory(mount_path, create=True)
        mounted = False
        try:
            _run(
                (
                    "mount",
                    "-o",
                    "nodev,nosuid,noexec",
                    partition,
                    str(mount_path),
                )
            )
            mounted = True
            filesystem_uuid = _run(
                ("blkid", "-s", "UUID", "-o", "value", partition)
            ).decode("utf-8", errors="strict").strip().lower()
            validate_filesystem_uuid(filesystem_uuid)
            self._self_test(mount_path)
            filesystem = os.statvfs(mount_path)
            measured = filesystem.f_bavail * filesystem.f_frsize
            return PreparedUsbMedia(
                locator=observed.locator,
                public_fingerprint=observed.public_fingerprint,
                filesystem_uuid=filesystem_uuid,
                measured_usable_bytes=measured,
                mount_path=str(mount_path),
            ).validate()
        except Exception:
            if mounted:
                try:
                    _run(("umount", str(mount_path)))
                except UpdaterV2Error:
                    pass
            try:
                mount_path.rmdir()
            except OSError:
                pass
            raise

    @staticmethod
    def _atomic_json(path: Path, document: dict[str, Any]) -> None:
        if path.is_symlink():
            raise UpdaterV2Error("usb_transaction_metadata_path_invalid")
        payload = (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )
        descriptor, raw = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(
                path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    def sync_transaction_metadata(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> None:
        media.validate()
        self._require_bound_media(media)
        transaction_id = transaction.get("transaction_id_sha256")
        phase = transaction.get("phase")
        release = transaction.get("target_manifest_identity")
        release_identity = (
            release.get("release_identity")
            if isinstance(release, dict)
            else None
        )
        target_image = transaction.get("target_image_ref")
        target_sha = transaction.get("target_archive_sha256")
        target_size = transaction.get("target_archive_size")
        if (
            not isinstance(transaction_id, str)
            or SHA256.fullmatch(transaction_id) is None
            or not isinstance(phase, str)
            or not isinstance(release_identity, str)
            or not isinstance(target_image, str)
            or not isinstance(target_sha, str)
            or SHA256.fullmatch(target_sha) is None
            or type(target_size) is not int
            or target_size <= 0
        ):
            raise UpdaterV2Error("usb_transaction_metadata_invalid")

        transaction_dir = (
            Path(media.mount_path) / "n3w-update" / "transaction"
        )
        _require_private_directory(transaction_dir, create=True)
        manifest = {
            "schema": USB_TX_MANIFEST_SCHEMA,
            "transaction_id_sha256": transaction_id,
            "release_identity": release_identity,
            "target_image_ref": target_image,
            "target_archive_sha256": target_sha,
            "target_archive_size_bytes": target_size,
            "usb_filesystem_uuid": media.filesystem_uuid,
            "usb_device_identity_public_fingerprint": (
                media.public_fingerprint
            ),
        }
        phase_document = {
            "schema": USB_TX_PHASE_SCHEMA,
            "transaction_id_sha256": transaction_id,
            "phase": phase,
            "target_artifact_verified": bool(
                transaction.get("target_artifact_verified", False)
            ),
            "usb_capacity_verified": bool(
                transaction.get("usb_capacity_verified", False)
            ),
        }
        checksums = {
            "schema": USB_TX_CHECKSUM_SCHEMA,
            "target_archive_sha256": target_sha,
            "target_archive_size_bytes": target_size,
        }
        self._atomic_json(transaction_dir / "manifest.json", manifest)
        self._atomic_json(transaction_dir / "phase.json", phase_document)
        self._atomic_json(transaction_dir / "checksums.json", checksums)
        self._fsync_directory(transaction_dir)

    def reopen_bound_media(
        self,
        transaction: dict[str, Any],
    ) -> PreparedUsbMedia | None:
        filesystem_uuid = transaction.get("usb_filesystem_uuid")
        fingerprint = transaction.get(
            "usb_device_identity_public_fingerprint"
        )
        transaction_id = transaction.get("transaction_id_sha256")
        measured = transaction.get("usb_measured_usable_bytes")
        if (
            not isinstance(filesystem_uuid, str)
            or not isinstance(fingerprint, str)
            or SHA256.fullmatch(fingerprint) is None
            or not isinstance(transaction_id, str)
            or SHA256.fullmatch(transaction_id) is None
            or type(measured) is not int
            or measured <= 0
        ):
            raise UpdaterV2Error("usb_bound_media_authority_invalid")
        validate_filesystem_uuid(filesystem_uuid)

        raw_partition = _run_optional(
            ("blkid", "-U", filesystem_uuid.lower())
        )
        if raw_partition is None:
            return None
        partition = raw_partition.decode(
            "utf-8",
            errors="strict",
        ).strip()
        if not partition.startswith("/dev/"):
            raise UpdaterV2Error("usb_bound_partition_invalid")
        raw_parent = _run_optional(
            (
                "lsblk",
                "--noheadings",
                "--paths",
                "--output",
                "PKNAME",
                partition,
            )
        )
        if raw_parent is None:
            return None
        parent = raw_parent.decode("utf-8", errors="strict").strip()
        if not parent.startswith("/dev/"):
            raise UpdaterV2Error("usb_bound_parent_invalid")

        disks = [
            item
            for item in self._lsblk()
            if item.get("type") == "disk" and item.get("path") == parent
        ]
        if len(disks) != 1:
            raise UpdaterV2Error("usb_bound_parent_ambiguous")
        disk = disks[0]
        transport = str(disk.get("tran") or "").strip().lower()
        if (
            transport != "usb"
            or not _boolish(disk.get("rm"))
            or _boolish(disk.get("ro"))
            or _stable_fingerprint(disk) != fingerprint
        ):
            raise UpdaterV2Error("usb_bound_device_identity_mismatch")

        root_major_minor = _run(
            ("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
        ).decode("utf-8", errors="strict").strip()
        major_minors = {
            str(item.get("maj:min") or "").strip()
            for item in _flatten_blocks([disk])
        }
        if root_major_minor in major_minors:
            raise UpdaterV2Error("usb_bound_device_is_root")

        _require_private_directory(
            self.runtime_root,
            allow_group_read_execute=True,
        )
        mount_root = self.runtime_root / "media"
        _require_private_directory(mount_root, create=True)
        mount_path = mount_root / transaction_id[:16]
        _require_private_directory(mount_path, create=True)

        raw_target = _run_optional(
            (
                "findmnt",
                "--noheadings",
                "--output",
                "TARGET",
                "--source",
                partition,
            )
        )
        if raw_target is None:
            _run(
                (
                    "mount",
                    "-o",
                    "nodev,nosuid,noexec",
                    partition,
                    str(mount_path),
                )
            )
        else:
            target = raw_target.decode(
                "utf-8",
                errors="strict",
            ).strip()
            if target != str(mount_path):
                raise UpdaterV2Error("usb_bound_partition_mounted_elsewhere")

        media = PreparedUsbMedia(
            locator=parent,
            public_fingerprint=fingerprint,
            filesystem_uuid=filesystem_uuid.lower(),
            measured_usable_bytes=measured,
            mount_path=str(mount_path),
        ).validate()
        self._require_bound_media(media)
        filesystem_type = _run(
            ("blkid", "-s", "TYPE", "-o", "value", partition)
        ).decode("utf-8", errors="strict").strip()
        label = _run(
            ("blkid", "-s", "LABEL", "-o", "value", partition)
        ).decode("utf-8", errors="strict").strip()
        if filesystem_type != "ext4" or label != USB_LABEL:
            raise UpdaterV2Error("usb_bound_filesystem_contract_invalid")
        return media

    def abort_prepared_media(self, media: PreparedUsbMedia) -> None:
        media.validate()
        mount_path = Path(media.mount_path)
        try:
            _run(("umount", str(mount_path)))
        finally:
            try:
                mount_path.rmdir()
            except OSError:
                pass

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _require_bound_media(self, media: PreparedUsbMedia) -> str:
        media.validate()
        mount_path = Path(media.mount_path)
        source = _run(
            (
                "findmnt",
                "--noheadings",
                "--output",
                "SOURCE",
                "--target",
                str(mount_path),
            )
        ).decode("utf-8", errors="strict").strip()
        if not source.startswith("/dev/"):
            raise UpdaterV2Error("usb_mount_source_invalid")
        observed_uuid = _run(
            ("blkid", "-s", "UUID", "-o", "value", source)
        ).decode("utf-8", errors="strict").strip().lower()
        validate_filesystem_uuid(observed_uuid)
        if observed_uuid != media.filesystem_uuid.lower():
            raise UpdaterV2Error("usb_filesystem_uuid_mismatch")

        parent = _run(
            (
                "lsblk",
                "--noheadings",
                "--paths",
                "--output",
                "PKNAME",
                source,
            )
        ).decode("utf-8", errors="strict").strip()
        if not parent.startswith("/dev/"):
            raise UpdaterV2Error("usb_bound_parent_invalid")
        disks = [
            item
            for item in self._lsblk()
            if item.get("type") == "disk" and item.get("path") == parent
        ]
        if len(disks) != 1:
            raise UpdaterV2Error("usb_bound_parent_ambiguous")
        disk = disks[0]
        if (
            str(disk.get("tran") or "").strip().lower() != "usb"
            or not _boolish(disk.get("rm"))
            or _boolish(disk.get("ro"))
            or _stable_fingerprint(disk) != media.public_fingerprint
        ):
            raise UpdaterV2Error("usb_bound_device_identity_mismatch")
        root_major_minor = _run(
            ("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
        ).decode("utf-8", errors="strict").strip()
        major_minors = {
            str(item.get("maj:min") or "").strip()
            for item in _flatten_blocks([disk])
        }
        if root_major_minor in major_minors:
            raise UpdaterV2Error("usb_bound_device_is_root")
        return source

    def prepare_target(
        self,
        *,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        media.validate()
        self._require_bound_media(media)
        policy = self.policy_provider.load(transaction)
        mount_path = Path(media.mount_path)
        if mount_path.is_symlink() or not mount_path.is_dir():
            raise UpdaterV2Error("usb_mount_path_invalid")
        update_dir = mount_path / "n3w-update"
        _require_private_directory(update_dir, create=True)
        target_dir = update_dir / "target"
        _require_private_directory(target_dir, create=True)
        destination = target_dir / "homeassistant-arm64.tar.gz"
        if destination.is_symlink():
            raise UpdaterV2Error("ha_target_destination_invalid")
        if destination.exists():
            identity = portable.parse_image_archive(
                destination,
                expected_archive_sha256=policy.target_archive_sha256,
                expected_archive_size_bytes=policy.target_archive_size_bytes,
                expected_tag=transaction["target_image_ref"],
                platform_os="linux",
                platform_architecture="arm64",
            )
            self._require_bound_media(media)
            return ImageRecoveryRecord(
                kind="target",
                image_ref=transaction["target_image_ref"],
                archive_sha256=policy.target_archive_sha256,
                archive_size_bytes=policy.target_archive_size_bytes,
                portable_identity_sha256=sha256_bytes(
                    canonical(identity.to_dict())
                ),
                platform="linux/arm64",
                verified=True,
                fsynced=True,
            )
        descriptor, raw = tempfile.mkstemp(
            prefix=".homeassistant-target.",
            dir=target_dir,
        )
        temporary = Path(raw)
        digest = hashlib.sha256()
        total = 0
        try:
            request = urllib.request.Request(
                policy.artifact_url,
                headers={"User-Agent": "n3w-t1-core-updater/1"},
                method="GET",
            )
            try:
                response_context = urllib.request.urlopen(request, timeout=30)
            except Exception as error:
                raise UpdaterV2Error("ha_target_download_failed") from error
            with response_context as response:
                final_url = urllib.parse.urlsplit(response.geturl())
                if (
                    final_url.scheme != "https"
                    or not final_url.hostname
                    or final_url.username is not None
                    or final_url.password is not None
                ):
                    raise UpdaterV2Error("ha_target_download_redirect_invalid")
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        declared = int(content_length)
                    except ValueError as error:
                        raise UpdaterV2Error(
                            "ha_target_content_length_invalid"
                        ) from error
                    if declared != policy.target_archive_size_bytes:
                        raise UpdaterV2Error(
                            "ha_target_content_length_mismatch"
                        )
                with os.fdopen(descriptor, "wb", closefd=True) as stream:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > policy.target_archive_size_bytes:
                            raise UpdaterV2Error("ha_target_download_oversize")
                        digest.update(block)
                        stream.write(block)
                    stream.flush()
                    os.fsync(stream.fileno())
            if (
                total != policy.target_archive_size_bytes
                or digest.hexdigest() != policy.target_archive_sha256
            ):
                raise UpdaterV2Error("ha_target_download_identity_mismatch")
            self._require_bound_media(media)
            identity = portable.parse_image_archive(
                temporary,
                expected_archive_sha256=policy.target_archive_sha256,
                expected_archive_size_bytes=policy.target_archive_size_bytes,
                expected_tag=transaction["target_image_ref"],
                platform_os="linux",
                platform_architecture="arm64",
            )
            os.replace(temporary, destination)
            self._fsync_directory(target_dir)
            self._require_bound_media(media)
            return ImageRecoveryRecord(
                kind="target",
                image_ref=transaction["target_image_ref"],
                archive_sha256=policy.target_archive_sha256,
                archive_size_bytes=policy.target_archive_size_bytes,
                portable_identity_sha256=sha256_bytes(
                    canonical(identity.to_dict())
                ),
                platform="linux/arm64",
                verified=True,
                fsynced=True,
            )
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
