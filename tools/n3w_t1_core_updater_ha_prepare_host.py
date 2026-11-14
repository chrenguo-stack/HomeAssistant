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
import n3w_t1_core_updater_ha_capacity as capacity
from n3w_t1_core_updater_ha_backup import (
    BACKUP_ARCHIVE_NAME,
    HaDataBackupRecord,
    validate_backup_record,
)
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

HOST_RELEASE_POLICY_SCHEMA = "gh.n3w-t1-ha-ota-host-release-policy/2"
USB_TX_MANIFEST_SCHEMA = "gh.n3w-t1-ha-usb-transaction-manifest/1"
USB_TX_PHASE_SCHEMA = "gh.n3w-t1-ha-usb-transaction-phase/1"
USB_TX_CHECKSUM_SCHEMA = "gh.n3w-t1-ha-usb-checksums/1"
USB_TX_CONTENT_AUTHORITY_SCHEMA = "gh.n3w-t1-ha-usb-content-authority/1"
DEFAULT_HOST_RELEASE_POLICY = Path(
    "/etc/n3w-t1-ota/homeassistant-release-source.json"
)
DEFAULT_RUNTIME_ROOT = Path("/run/n3w-t1-ota")
DEFAULT_HA_DATA_ROOT = Path("/var/lib/n3wfc4-homeassistant")
HOMEASSISTANT_CONTAINER = "n3wfc4-homeassistant-1"
MAX_POLICY_BYTES = 64 * 1024
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024
MAX_CAPACITY_INPUT_BYTES = 64 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class HostReleasePolicy:
    release_identity: str
    artifact_url: str
    target_archive_sha256: str
    target_archive_size_bytes: int
    expected_predecessor_image_ref: str
    predecessor_recovery_budget_bytes: int
    capacity_policy: capacity.CapacityPolicy

    def validate(self) -> "HostReleasePolicy":
        if (
            not isinstance(self.release_identity, str)
            or not 3 <= len(self.release_identity) <= 128
            or any(character.isspace() for character in self.release_identity)
        ):
            raise UpdaterV2Error("ha_prepare_policy_release_invalid")
        parsed = urllib.parse.urlsplit(self.artifact_url)
        expected_path = (
            f"/n3w/homeassistant/releases/{self.release_identity}/"
            "homeassistant-arm64.tar.gz"
        )
        if (
            parsed.scheme != "https"
            or parsed.hostname != "ota.hahub.top"
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != expected_path
            or parsed.query
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
        if (
            not isinstance(self.expected_predecessor_image_ref, str)
            or not self.expected_predecessor_image_ref.startswith(
                "local/n3w-homeassistant:"
            )
            or self.expected_predecessor_image_ref.strip()
            != self.expected_predecessor_image_ref
        ):
            raise UpdaterV2Error("ha_prepare_policy_predecessor_invalid")
        if (
            type(self.predecessor_recovery_budget_bytes) is not int
            or self.predecessor_recovery_budget_bytes <= 0
            or self.predecessor_recovery_budget_bytes > MAX_CAPACITY_INPUT_BYTES
        ):
            raise UpdaterV2Error("ha_prepare_policy_capacity_invalid")
        if self.capacity_policy != capacity.CapacityPolicy.frozen():
            raise UpdaterV2Error("ha_prepare_capacity_policy_drift")
        return self

    def capacity_breakdown(
        self,
        ha_data_measured_bytes: int,
    ) -> capacity.CapacityBreakdown:
        self.validate()
        return capacity.compute_capacity(
            target_artifact_bytes=self.target_archive_size_bytes,
            predecessor_recovery_budget_bytes=self.predecessor_recovery_budget_bytes,
            ha_data_measured_bytes=ha_data_measured_bytes,
            policy=self.capacity_policy,
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
            "expected_predecessor_image_ref",
            "predecessor_recovery_budget_bytes",
            "capacity_policy",
        }
        if (
            set(document) != expected
            or document.get("schema") != HOST_RELEASE_POLICY_SCHEMA
        ):
            raise UpdaterV2Error("ha_prepare_policy_schema_invalid")
        policy = HostReleasePolicy(
            release_identity=document["release_identity"],
            artifact_url=document["artifact_url"],
            target_archive_sha256=document["target_archive_sha256"],
            target_archive_size_bytes=document["target_archive_size_bytes"],
            expected_predecessor_image_ref=document[
                "expected_predecessor_image_ref"
            ],
            predecessor_recovery_budget_bytes=document[
                "predecessor_recovery_budget_bytes"
            ],
            capacity_policy=capacity.CapacityPolicy.from_document(
                document["capacity_policy"]
            ),
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
            or policy.expected_predecessor_image_ref
            != transaction.get("current_image_ref")
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


def measure_ha_data_tree(root: Path) -> int:
    if (
        not root.is_absolute()
        or _path_contains_symlink(root)
        or not root.is_dir()
    ):
        raise UpdaterV2Error("ha_data_root_invalid")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise UpdaterV2Error("ha_data_root_invalid") from error

    total = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = tuple(os.scandir(directory))
        except OSError as error:
            raise UpdaterV2Error("ha_data_measurement_failed") from error
        for entry in entries:
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise UpdaterV2Error("ha_data_measurement_failed") from error

            if stat.S_ISLNK(metadata.st_mode):
                try:
                    target = path.resolve(strict=True)
                    target.relative_to(resolved_root)
                except (OSError, ValueError) as error:
                    raise UpdaterV2Error(
                        "ha_data_external_persistent_state_unsupported"
                    ) from error
            elif stat.S_ISDIR(metadata.st_mode):
                stack.append(path)
            elif not stat.S_ISREG(metadata.st_mode):
                raise UpdaterV2Error("ha_data_special_file_unsupported")

            if metadata.st_size < 0:
                raise UpdaterV2Error("ha_data_measurement_invalid")
            total += metadata.st_size
            if total > capacity.MAX_SAFE_BYTES:
                raise UpdaterV2Error("ha_data_measurement_overflow")
    return total


def _stable_fingerprint(node: dict[str, Any]) -> str:
    """Session observation fingerprint; never cross-session recovery authority."""
    serial = (
        node["serial"].strip()
        if isinstance(node.get("serial"), str) and node["serial"].strip()
        else None
    )
    wwn = (
        node["wwn"].strip()
        if isinstance(node.get("wwn"), str) and node["wwn"].strip()
        else None
    )
    identity = {
        "path": str(node.get("path") or "").strip(),
        "major_minor": str(node.get("maj:min") or "").strip(),
        "serial": serial,
        "wwn": wwn,
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
        ha_data_root: Path = DEFAULT_HA_DATA_ROOT,
    ) -> None:
        self.policy_provider = policy_provider or FixedHostReleasePolicyProvider()
        self.runtime_root = runtime_root
        self.ha_data_root = ha_data_root

    def _lsblk(self) -> list[dict[str, Any]]:
        payload = _run(
            (
                "lsblk",
                "--json",
                "--bytes",
                "--paths",
                "--tree",
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

    def capacity_breakdown(
        self,
        transaction: dict[str, Any],
    ) -> capacity.CapacityBreakdown:
        policy = self.policy_provider.load(transaction)
        measured = measure_ha_data_tree(self.ha_data_root)
        return policy.capacity_breakdown(measured)

    def capacity_snapshot(
        self,
        transaction: dict[str, Any],
        *,
        calculated_at_unix: int,
    ) -> dict[str, int | str]:
        return self.capacity_breakdown(transaction).snapshot(
            calculated_at_unix=calculated_at_unix
        )

    def capacity_inputs(
        self,
        transaction: dict[str, Any],
    ) -> UsbCapacityInputs:
        breakdown = self.capacity_breakdown(transaction)
        return UsbCapacityInputs(
            target_artifact_bytes=breakdown.target_artifact_bytes,
            predecessor_recovery_worst_case_bytes=(
                breakdown.predecessor_recovery_budget_bytes
            ),
            ha_data_backup_worst_case_bytes=breakdown.ha_data_backup_budget_bytes,
            transaction_metadata_and_working_bytes=(
                breakdown.transaction_working_budget_bytes
            ),
            removable_media_reserve_bytes=breakdown.removable_reserve_bytes,
        )

    @staticmethod
    def _filesystem_space(mount_path: Path) -> tuple[int, int]:
        if mount_path.is_symlink() or not mount_path.is_dir():
            raise UpdaterV2Error("usb_mount_path_invalid")
        try:
            values = os.statvfs(mount_path)
        except OSError as error:
            raise UpdaterV2Error("usb_free_space_unavailable") from error
        used = (values.f_blocks - values.f_bfree) * values.f_frsize
        free = values.f_bavail * values.f_frsize
        effective = used + free
        if (
            used < 0
            or free < 0
            or effective <= 0
            or effective > capacity.MAX_SAFE_BYTES
        ):
            raise UpdaterV2Error("usb_free_space_invalid")
        return effective, free

    @staticmethod
    def _observed_free_bytes(media: PreparedUsbMedia) -> int:
        media.validate()
        _effective, free = SubprocessPrepareBackend._filesystem_space(
            Path(media.mount_path)
        )
        return free

    def install_capacity_revalidation(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> capacity.InstallCapacityRevalidation:
        policy = self.policy_provider.load(transaction)
        measured = measure_ha_data_tree(self.ha_data_root)
        return capacity.compute_install_revalidation(
            target_artifact_bytes=policy.target_archive_size_bytes,
            predecessor_recovery_budget_bytes=(
                policy.predecessor_recovery_budget_bytes
            ),
            ha_data_measured_bytes=measured,
            observed_usb_free_bytes=self._observed_free_bytes(media),
            policy=policy.capacity_policy,
        )

    @staticmethod
    def _reclaimable_backup_bytes(
        media: PreparedUsbMedia,
        reclaimable_backup: HaDataBackupRecord | None,
    ) -> int:
        media.validate()
        archive = (
            Path(media.mount_path)
            / "n3w-update"
            / "ha-data"
            / BACKUP_ARCHIVE_NAME
        )
        if not archive.exists() and not archive.is_symlink():
            return 0
        if archive.is_symlink() or not archive.is_file():
            raise UpdaterV2Error("ha_backup_reclaimable_archive_invalid")
        metadata = archive.stat()
        if metadata.st_nlink != 1:
            raise UpdaterV2Error("ha_backup_reclaimable_archive_invalid")
        if reclaimable_backup is not None:
            validated = validate_backup_record(reclaimable_backup)
            if metadata.st_size != validated.archive_size_bytes:
                raise UpdaterV2Error(
                    "ha_backup_reclaimable_archive_invalid"
                )
        allocated = metadata.st_blocks * 512
        if (
            allocated < 0
            or allocated > capacity.MAX_SAFE_BYTES
            or metadata.st_size < 0
        ):
            raise UpdaterV2Error("ha_backup_reclaimable_archive_invalid")
        return min(metadata.st_size, allocated)

    def backup_capacity_revalidation(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
        *,
        predecessor: ImageRecoveryRecord,
        reclaimable_backup: HaDataBackupRecord | None = None,
    ) -> capacity.BackupCapacityRevalidation:
        policy = self.policy_provider.load(transaction)
        measured = measure_ha_data_tree(self.ha_data_root)
        reclaimable_bytes = self._reclaimable_backup_bytes(
            media,
            reclaimable_backup,
        )
        return capacity.compute_backup_revalidation(
            target_artifact_bytes=policy.target_archive_size_bytes,
            predecessor_archive_bytes=predecessor.archive_size_bytes,
            ha_data_measured_bytes=measured,
            observed_usb_free_bytes=self._observed_free_bytes(media),
            reclaimable_backup_bytes=reclaimable_bytes,
            policy=policy.capacity_policy,
        )

    def recovery_admission_capacity(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
        *,
        target: ImageRecoveryRecord,
        predecessor: ImageRecoveryRecord,
        backup: HaDataBackupRecord,
    ) -> capacity.RecoveryAdmissionCapacity:
        policy = self.policy_provider.load(transaction)
        current = self.capacity_breakdown(transaction)
        return capacity.compute_recovery_admission_capacity(
            target_archive_bytes=target.archive_size_bytes,
            predecessor_archive_bytes=predecessor.archive_size_bytes,
            ha_backup_archive_bytes=backup.archive_size_bytes,
            transaction_working_budget_bytes=(
                current.transaction_working_budget_bytes
            ),
            observed_usb_free_bytes=self._observed_free_bytes(media),
            policy=policy.capacity_policy,
        )

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
            measured, _free = self._filesystem_space(mount_path)
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

        update_dir = Path(media.mount_path) / "n3w-update"
        _require_private_directory(update_dir, create=True)
        transaction_dir = update_dir / "transaction"
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
        content_authority = {
            "schema": USB_TX_CONTENT_AUTHORITY_SCHEMA,
            "transaction_id_sha256": transaction_id,
            "release_identity": release_identity,
            "target_artifact_identity": transaction.get(
                "target_artifact_identity"
            ),
            "predecessor_recovery_identity": transaction.get(
                "predecessor_recovery_identity"
            ),
            "ha_data_backup_identity": transaction.get(
                "ha_data_backup_identity"
            ),
            "recovery_content_manifest_sha256": transaction.get(
                "recovery_content_manifest_sha256"
            ),
        }
        self._atomic_json(transaction_dir / "manifest.json", manifest)
        self._atomic_json(transaction_dir / "phase.json", phase_document)
        self._atomic_json(transaction_dir / "checksums.json", checksums)
        self._atomic_json(
            transaction_dir / "content-authority.json",
            content_authority,
        )
        self._fsync_directory(transaction_dir)

    def resolve_transaction_media(
        self,
        transaction: dict[str, Any],
        *,
        write_required: bool,
    ) -> PreparedUsbMedia | None:
        transaction_id = transaction.get("transaction_id_sha256")
        if (
            not isinstance(transaction_id, str)
            or SHA256.fullmatch(transaction_id) is None
        ):
            raise UpdaterV2Error("ha_usb_transaction_id_invalid")

        root_major_minor = _run(
            ("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
        ).decode("utf-8", errors="strict").strip()
        if not root_major_minor:
            raise UpdaterV2Error("usb_root_device_unresolved")

        _require_private_directory(
            self.runtime_root,
            allow_group_read_execute=True,
        )
        mount_root = self.runtime_root / "media"
        _require_private_directory(mount_root, create=True)
        mount_path = mount_root / transaction_id[:16]

        matches: list[tuple[dict[str, Any], str, str]] = []
        for disk in self._lsblk():
            if disk.get("type") != "disk":
                continue
            path = disk.get("path")
            if not isinstance(path, str) or not path.startswith("/dev/"):
                continue
            if (
                str(disk.get("tran") or "").strip().lower() != "usb"
                or not _boolish(disk.get("rm"))
                or (write_required and _boolish(disk.get("ro")))
            ):
                continue
            descendants = _flatten_blocks([disk])
            major_minors = {
                str(item.get("maj:min") or "").strip()
                for item in descendants
            }
            if root_major_minor in major_minors:
                continue
            partitions = [
                item
                for item in descendants
                if item.get("type") == "part"
                and isinstance(item.get("path"), str)
            ]
            if len(partitions) != 1:
                continue
            partition = str(partitions[0]["path"])
            mounted_points = tuple(
                point
                for item in descendants
                for point in _mountpoints(item)
            )
            if mounted_points and set(mounted_points) != {str(mount_path)}:
                continue
            fs_raw = _run_optional(
                ("blkid", "-s", "TYPE", "-o", "value", partition)
            )
            label_raw = _run_optional(
                ("blkid", "-s", "LABEL", "-o", "value", partition)
            )
            uuid_raw = _run_optional(
                ("blkid", "-s", "UUID", "-o", "value", partition)
            )
            if fs_raw is None or label_raw is None or uuid_raw is None:
                continue
            filesystem_type = fs_raw.decode("utf-8", errors="strict").strip()
            label = label_raw.decode("utf-8", errors="strict").strip()
            filesystem_uuid = uuid_raw.decode(
                "utf-8", errors="strict"
            ).strip().lower()
            if filesystem_type != "ext4" or label != USB_LABEL:
                continue
            validate_filesystem_uuid(filesystem_uuid)
            matches.append((disk, partition, filesystem_uuid))

        if not matches:
            return None
        if len(matches) != 1:
            raise UpdaterV2Error("usb_multiple_eligible_devices")

        disk, partition, filesystem_uuid = matches[0]
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
            _require_private_directory(mount_path, create=True)
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
            target = raw_target.decode("utf-8", errors="strict").strip()
            if target != str(mount_path):
                raise UpdaterV2Error("usb_bound_partition_mounted_elsewhere")
            if mount_path.is_symlink() or not mount_path.is_dir():
                raise UpdaterV2Error("usb_mount_path_invalid")

        measured, _free = self._filesystem_space(mount_path)
        current = PreparedUsbMedia(
            locator=str(disk["path"]),
            public_fingerprint=_stable_fingerprint(disk),
            filesystem_uuid=filesystem_uuid,
            measured_usable_bytes=measured,
            mount_path=str(mount_path),
        ).validate()
        self._require_bound_media(current)
        if measured < capacity.USB_MEASURED_USABLE_FLOOR_BYTES:
            raise UpdaterV2Error("usb_measured_capacity_below_floor")
        return current

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

    @staticmethod
    def _cleanup_stale_target_temporaries(target_dir: Path) -> None:
        removed = False
        for item in target_dir.iterdir():
            if not item.name.startswith(".homeassistant-target."):
                continue
            if item.is_symlink() or not item.is_file():
                raise UpdaterV2Error("ha_target_temporary_invalid")
            item.unlink()
            removed = True
        if removed:
            SubprocessPrepareBackend._fsync_directory(target_dir)

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
        self._cleanup_stale_target_temporaries(target_dir)
        destination = target_dir / "homeassistant-arm64.tar.gz"
        if destination.is_symlink():
            raise UpdaterV2Error("ha_target_destination_invalid")
        if destination.exists():
            try:
                identity = portable.parse_image_archive(
                    destination,
                    expected_archive_sha256=policy.target_archive_sha256,
                    expected_archive_size_bytes=policy.target_archive_size_bytes,
                    expected_tag=transaction["target_image_ref"],
                    platform_os="linux",
                    platform_architecture="arm64",
                )
            except portable.PortableImageIdentityError:
                destination.unlink()
                self._fsync_directory(target_dir)
            else:
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
                    or final_url.hostname != "ota.hahub.top"
                    or final_url.port not in (None, 443)
                    or final_url.username is not None
                    or final_url.password is not None
                    or final_url.query
                    or final_url.fragment
                    or response.geturl() != policy.artifact_url
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

    def verify_prepared_target(
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
        _require_private_directory(update_dir, create=False)
        target_dir = update_dir / "target"
        _require_private_directory(target_dir, create=False)
        destination = target_dir / "homeassistant-arm64.tar.gz"
        if destination.is_symlink() or not destination.is_file():
            raise UpdaterV2Error("ha_target_destination_invalid")
        try:
            identity = portable.parse_image_archive(
                destination,
                expected_archive_sha256=policy.target_archive_sha256,
                expected_archive_size_bytes=policy.target_archive_size_bytes,
                expected_tag=transaction["target_image_ref"],
                platform_os="linux",
                platform_architecture="arm64",
            )
        except portable.PortableImageIdentityError as error:
            raise UpdaterV2Error(
                "ha_target_existing_identity_invalid"
            ) from error
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


    @staticmethod
    def _expected_predecessor_runtime_id(
        transaction: dict[str, Any],
        image_ref: str,
    ) -> str:
        if transaction.get("current_image_ref") != image_ref:
            raise UpdaterV2Error("ha_predecessor_transaction_ref_drift")
        identity = transaction.get("current_image_identity")
        runtime_id = (
            identity.get("runtime_image_id")
            if isinstance(identity, dict)
            else None
        )
        platform = identity.get("platform") if isinstance(identity, dict) else None
        if (
            not isinstance(runtime_id, str)
            or not runtime_id.startswith("sha256:")
            or SHA256.fullmatch(runtime_id[7:]) is None
            or platform != "linux/arm64"
        ):
            raise UpdaterV2Error(
                "ha_predecessor_transaction_identity_invalid"
            )
        return runtime_id

    @staticmethod
    def _require_predecessor_container_authority(
        transaction: dict[str, Any],
        image_ref: str,
    ) -> str:
        expected_runtime_id = (
            SubprocessPrepareBackend._expected_predecessor_runtime_id(
                transaction,
                image_ref,
            )
        )
        payload = _run(
            (
                "docker",
                "inspect",
                "--type",
                "container",
                HOMEASSISTANT_CONTAINER,
            )
        )
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error(
                "ha_predecessor_container_identity_invalid"
            ) from error
        if (
            not isinstance(value, list)
            or len(value) != 1
            or not isinstance(value[0], dict)
        ):
            raise UpdaterV2Error("ha_predecessor_container_identity_invalid")
        container = value[0]
        config = container.get("Config")
        observed_ref = config.get("Image") if isinstance(config, dict) else None
        observed_runtime_id = container.get("Image")
        if (
            observed_ref != image_ref
            or observed_runtime_id != expected_runtime_id
        ):
            raise UpdaterV2Error("ha_predecessor_container_runtime_drift")
        return expected_runtime_id

    @staticmethod
    def _cleanup_stale_predecessor_temporaries(predecessor_dir: Path) -> None:
        removed = False
        for item in predecessor_dir.iterdir():
            if not item.name.startswith(".homeassistant-predecessor."):
                continue
            if item.is_symlink() or not item.is_file():
                raise UpdaterV2Error("ha_predecessor_temporary_invalid")
            item.unlink()
            removed = True
        if removed:
            SubprocessPrepareBackend._fsync_directory(predecessor_dir)

    @staticmethod
    def _stream_predecessor_archive(
        image_ref: str,
        destination: Path,
    ) -> None:
        docker_process: subprocess.Popen[bytes] | None = None
        gzip_process: subprocess.Popen[bytes] | None = None
        try:
            with destination.open("wb") as stream:
                try:
                    docker_process = subprocess.Popen(
                        ("docker", "image", "save", image_ref),
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    if docker_process.stdout is None:
                        raise UpdaterV2Error(
                            "ha_predecessor_export_pipe_unavailable"
                        )
                    gzip_process = subprocess.Popen(
                        ("gzip", "-n", "-c"),
                        stdin=docker_process.stdout,
                        stdout=stream,
                        stderr=subprocess.DEVNULL,
                    )
                    docker_process.stdout.close()
                    try:
                        gzip_returncode = gzip_process.wait(timeout=1800)
                        docker_returncode = docker_process.wait(timeout=60)
                    except subprocess.TimeoutExpired as error:
                        raise UpdaterV2Error(
                            "ha_predecessor_export_timeout"
                        ) from error
                except FileNotFoundError as error:
                    raise UpdaterV2Error(
                        "ha_predecessor_export_tool_unavailable"
                    ) from error
                if docker_returncode != 0 or gzip_returncode != 0:
                    raise UpdaterV2Error("ha_predecessor_export_failed")
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            for process in (gzip_process, docker_process):
                if process is not None and process.poll() is None:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass

    def prepare_predecessor_recovery(
        self,
        *,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        media.validate()
        self._require_bound_media(media)
        policy = self.policy_provider.load(transaction)
        image_ref = transaction.get("current_image_ref")
        if (
            not isinstance(image_ref, str)
            or image_ref != policy.expected_predecessor_image_ref
            or not image_ref.startswith("local/n3w-homeassistant:")
        ):
            raise UpdaterV2Error("ha_predecessor_image_ref_invalid")

        expected_runtime_id = self._require_predecessor_container_authority(
            transaction,
            image_ref,
        )

        mount_path = Path(media.mount_path)
        if mount_path.is_symlink() or not mount_path.is_dir():
            raise UpdaterV2Error("usb_mount_path_invalid")
        update_dir = mount_path / "n3w-update"
        _require_private_directory(update_dir, create=True)
        predecessor_dir = update_dir / "predecessor"
        _require_private_directory(predecessor_dir, create=True)
        self._cleanup_stale_predecessor_temporaries(predecessor_dir)
        destination = predecessor_dir / "homeassistant-predecessor.tar.gz"
        if destination.is_symlink():
            raise UpdaterV2Error("ha_predecessor_destination_invalid")

        if destination.exists():
            try:
                return self.verify_prepared_predecessor(
                    transaction=transaction,
                    media=media,
                )
            except UpdaterV2Error as error:
                if str(error) not in {
                    "ha_predecessor_archive_identity_invalid",
                    "ha_predecessor_archive_budget_exceeded",
                }:
                    raise
                if not destination.is_file():
                    raise UpdaterV2Error(
                        "ha_predecessor_destination_invalid"
                    )
                destination.unlink()
                self._fsync_directory(predecessor_dir)

        descriptor, raw = tempfile.mkstemp(
            prefix=".homeassistant-predecessor.",
            dir=predecessor_dir,
        )
        temporary = Path(raw)
        os.close(descriptor)
        try:
            self._stream_predecessor_archive(image_ref, temporary)
            self._require_bound_media(media)
            try:
                identity = portable.parse_image_archive(
                    temporary,
                    expected_tag=image_ref,
                    platform_os="linux",
                    platform_architecture="arm64",
                )
            except portable.PortableImageIdentityError as error:
                raise UpdaterV2Error(
                    "ha_predecessor_archive_identity_invalid"
                ) from error
            if identity.archive_size_bytes > policy.predecessor_recovery_budget_bytes:
                raise UpdaterV2Error("ha_predecessor_archive_budget_exceeded")
            if (
                self._require_predecessor_container_authority(
                    transaction,
                    image_ref,
                )
                != expected_runtime_id
            ):
                raise UpdaterV2Error(
                    "ha_predecessor_container_runtime_drift"
                )
            verdict = portable.verify_docker_image(identity, image_ref)
            if (
                verdict.status != "VERIFIED"
                or verdict.runtime_image_id != expected_runtime_id
            ):
                raise UpdaterV2Error(
                    "ha_predecessor_runtime_identity_mismatch"
                )
            os.replace(temporary, destination)
            self._fsync_directory(predecessor_dir)
            self._require_bound_media(media)
            return ImageRecoveryRecord(
                kind="predecessor",
                image_ref=image_ref,
                archive_sha256=identity.archive_sha256,
                archive_size_bytes=identity.archive_size_bytes,
                portable_identity_sha256=sha256_bytes(
                    canonical(identity.to_dict())
                ),
                platform="linux/arm64",
                verified=True,
                fsynced=True,
            )
        finally:
            temporary.unlink(missing_ok=True)

    def verify_prepared_predecessor(
        self,
        *,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        media.validate()
        self._require_bound_media(media)
        policy = self.policy_provider.load(transaction)
        image_ref = transaction.get("current_image_ref")
        if (
            not isinstance(image_ref, str)
            or image_ref != policy.expected_predecessor_image_ref
            or not image_ref.startswith("local/n3w-homeassistant:")
        ):
            raise UpdaterV2Error("ha_predecessor_image_ref_invalid")
        expected_runtime_id = self._require_predecessor_container_authority(
            transaction,
            image_ref,
        )
        destination = (
            Path(media.mount_path)
            / "n3w-update"
            / "predecessor"
            / "homeassistant-predecessor.tar.gz"
        )
        if destination.is_symlink() or not destination.is_file():
            raise UpdaterV2Error("ha_predecessor_destination_invalid")
        try:
            identity = portable.parse_image_archive(
                destination,
                expected_tag=image_ref,
                platform_os="linux",
                platform_architecture="arm64",
            )
        except portable.PortableImageIdentityError as error:
            raise UpdaterV2Error(
                "ha_predecessor_archive_identity_invalid"
            ) from error
        if identity.archive_size_bytes > policy.predecessor_recovery_budget_bytes:
            raise UpdaterV2Error("ha_predecessor_archive_budget_exceeded")
        if (
            self._require_predecessor_container_authority(
                transaction,
                image_ref,
            )
            != expected_runtime_id
        ):
            raise UpdaterV2Error("ha_predecessor_container_runtime_drift")
        verdict = portable.verify_docker_image(identity, image_ref)
        if (
            verdict.status != "VERIFIED"
            or verdict.runtime_image_id != expected_runtime_id
        ):
            raise UpdaterV2Error("ha_predecessor_runtime_identity_mismatch")
        self._require_bound_media(media)
        return ImageRecoveryRecord(
            kind="predecessor",
            image_ref=image_ref,
            archive_sha256=identity.archive_sha256,
            archive_size_bytes=identity.archive_size_bytes,
            portable_identity_sha256=sha256_bytes(
                canonical(identity.to_dict())
            ),
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        )
