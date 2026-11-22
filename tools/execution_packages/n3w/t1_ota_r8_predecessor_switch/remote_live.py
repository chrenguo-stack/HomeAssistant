#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import contract
import executor


STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")
STATE_PATH = STATE_ROOT / "r8-predecessor-switch.json"
HA_DATA_ROOT = Path("/var/lib/n3wfc4-homeassistant")
USB_MOUNT = Path("/mnt")
P3_PREDECESSOR_ARCHIVE = Path("n3w-update/predecessor/homeassistant-predecessor.tar.gz")
R8_USB_ROOT = Path("N3W-R8/predecessor-switch")
RENAME_EXCHANGE = 2
READINESS_TIMEOUT_SECONDS = 600


class LiveError(RuntimeError):
    pass


def run(
    argv: tuple[str, ...],
    *,
    timeout: int = 60,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        argv,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode:
        raise LiveError(
            "command_failed:"
            + Path(argv[0]).name
            + ":"
            + str(result.returncode)
        )
    return result


def require_private_directory(path: Path, *, create: bool = False) -> None:
    if create and not path.exists():
        path.mkdir(mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise LiveError("private_directory_invalid")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LiveError("private_directory_metadata_invalid")


def atomic_write_state(document: dict[str, Any]) -> None:
    require_private_directory(STATE_ROOT, create=True)
    current = None
    if STATE_PATH.exists() or STATE_PATH.is_symlink():
        if STATE_PATH.is_symlink() or not STATE_PATH.is_file():
            raise LiveError("switch_state_invalid")
        try:
            current = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise LiveError("switch_state_invalid") from error
        if (
            not isinstance(current, dict)
            or current.get("transaction_id") != document.get("transaction_id")
        ):
            raise LiveError("switch_state_transaction_collision")
    fd, raw = tempfile.mkstemp(prefix=".r8-predecessor-switch.", dir=STATE_ROOT)
    temporary = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(contract.canonical(document) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE_PATH)
        directory = os.open(STATE_ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def read_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists() and not STATE_PATH.is_symlink():
        return None
    if STATE_PATH.is_symlink() or not STATE_PATH.is_file():
        raise LiveError("switch_state_invalid")
    info = STATE_PATH.stat()
    if (
        info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size > 64 * 1024
    ):
        raise LiveError("switch_state_metadata_invalid")
    value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiveError("switch_state_invalid")
    return value


def source_mounts(device: str) -> list[str]:
    result = run(
        (
            "findmnt",
            "--list",
            "--source",
            device,
            "--output",
            "TARGET",
            "--noheadings",
        ),
        check=False,
        timeout=20,
    )
    if result.returncode not in {0, 1}:
        raise LiveError("usb_mount_probe_failed")
    return [
        line.strip()
        for line in result.stdout.decode().splitlines()
        if line.strip()
    ]


def mount_usb(*, read_only: bool) -> None:
    if source_mounts(contract.BOUND_USB_DEVICE):
        raise LiveError("usb_already_mounted")
    if USB_MOUNT.is_symlink() or not USB_MOUNT.is_dir():
        raise LiveError("usb_mountpoint_invalid")
    options = (
        "ro,noload,nodev,nosuid,noexec"
        if read_only
        else "rw,nodev,nosuid,noexec"
    )
    run(
        (
            "mount",
            "--internal-only",
            "-t",
            "ext4",
            "-o",
            options,
            "--",
            contract.BOUND_USB_DEVICE,
            str(USB_MOUNT),
        ),
        timeout=30,
    )


def unmount_usb() -> None:
    result = run(
        ("findmnt", "--mountpoint", str(USB_MOUNT)),
        check=False,
        timeout=10,
    )
    if result.returncode == 0:
        run(("umount", "--", str(USB_MOUNT)), timeout=30)
    elif result.returncode != 1:
        raise LiveError("usb_mountpoint_probe_failed")


def exchange_directories(first: Path, second: Path) -> None:
    if first.parent != second.parent:
        raise LiveError("data_exchange_parent_mismatch")
    parent = first.parent
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        exchange = getattr(libc, "renameat2", None)
        if exchange is None:
            raise LiveError("data_exchange_unavailable")
        exchange.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        exchange.restype = ctypes.c_int
        if exchange(
            descriptor,
            os.fsencode(first.name),
            descriptor,
            os.fsencode(second.name),
            RENAME_EXCHANGE,
        ):
            raise OSError(ctypes.get_errno(), "renameat2")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def directory_identity(path: Path) -> tuple[int, int]:
    if path.is_symlink() or not path.is_dir():
        raise LiveError("data_directory_invalid")
    info = path.stat()
    return os.statvfs(path).f_fsid, info.st_ino


def ensure_recovery_modules(recovery_pyz: Path) -> None:
    if (
        recovery_pyz.is_symlink()
        or not recovery_pyz.is_file()
        or recovery_pyz.stat().st_size <= 0
    ):
        raise LiveError("recovery_package_invalid")
    sys.path.insert(0, str(recovery_pyz))


def p3_transaction():
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_v2_common import canonical

    store = HaUsbStateStore()
    current = store.read()
    if (
        current is None
        or current.get("phase") != "U13B_ROLLED_BACK"
        or current.get("status") != "ROLLED_BACK"
        or contract.sha256_bytes(canonical(current))
        != contract.CURRENT_ROLLBACK_TX_SHA256
    ):
        raise LiveError("p3_rollback_transaction_drift")
    return current


def verify_usb_binding(current: dict[str, Any]) -> None:
    from n3w_t1_core_updater_ha_mounted_media import bound_usb_device

    expected_uuid = current.get("usb_filesystem_uuid")
    if not isinstance(expected_uuid, str) or not expected_uuid:
        raise LiveError("p3_usb_uuid_missing")
    row = bound_usb_device(expected_uuid.lower(), STATE_ROOT)
    if (
        not isinstance(row, dict)
        or row.get("name") != contract.BOUND_USB_DEVICE
        or row.get("maj:min") != contract.BOUND_USB_MAJOR_MINOR
        or row.get("fstype") != "ext4"
    ):
        raise LiveError("p3_usb_binding_drift")


def p3_rollback_archive() -> Path:
    path = USB_MOUNT / P3_PREDECESSOR_ARCHIVE
    if path.is_symlink() or not path.is_file():
        raise LiveError("p3_rollback_archive_missing")
    if path.stat().st_size != contract.CURRENT_ROLLBACK_ARCHIVE_SIZE:
        raise LiveError("p3_rollback_archive_size_drift")
    if contract.sha256_file(path) != contract.CURRENT_ROLLBACK_ARCHIVE_SHA256:
        raise LiveError("p3_rollback_archive_sha256_drift")
    return path


def verify_current_archive_identity():
    from n3w_t1_core_updater_v2_common import canonical
    from n3w_t1_portable_image_identity import parse_image_archive

    path = p3_rollback_archive()
    identity = parse_image_archive(
        path,
        expected_archive_sha256=contract.CURRENT_ROLLBACK_ARCHIVE_SHA256,
        expected_archive_size_bytes=contract.CURRENT_ROLLBACK_ARCHIVE_SIZE,
        expected_tag=contract.CURRENT_IMAGE,
        platform_os="linux",
        platform_architecture="arm64",
    )
    if (
        contract.sha256_bytes(canonical(identity.to_dict()))
        != contract.CURRENT_ROLLBACK_PORTABLE_SHA256
    ):
        raise LiveError("p3_rollback_portable_identity_drift")
    return identity


def verify_current_archive_against_runtime(host) -> None:
    from n3w_t1_portable_image_identity import verify_runtime_document

    identity = verify_current_archive_identity()
    document = host._image_document(contract.CURRENT_IMAGE)
    if document is None:
        raise LiveError("current_image_missing")
    verdict = verify_runtime_document(identity, document)
    if (
        verdict.status != "VERIFIED"
        or verdict.runtime_image_id != contract.CURRENT_IMAGE_ID
    ):
        raise LiveError("p3_rollback_runtime_identity_drift")


def image_document(host, reference: str) -> dict[str, Any] | None:
    return host._image_document(reference)


def stopped_ha_containers() -> list[dict[str, Any]]:
    result = run(
        (
            "docker",
            "ps",
            "--all",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=n3wfc4",
            "--filter",
            "label=com.docker.compose.service=homeassistant",
            "--format",
            "{{json .}}",
        ),
        timeout=30,
    )
    values = []
    for raw in result.stdout.decode().splitlines():
        if raw.strip():
            values.append(json.loads(raw))
    return values


def container_ids_by_ancestor(image_id: str) -> list[str]:
    result = run(
        (
            "docker",
            "ps",
            "--all",
            "--no-trunc",
            "--quiet",
            "--filter",
            "ancestor=" + image_id,
        ),
        timeout=30,
    )
    return [
        line.strip()
        for line in result.stdout.decode().splitlines()
        if line.strip()
    ]


def inspect_container(container_id: str) -> dict[str, Any]:
    value = json.loads(
        run(("docker", "inspect", container_id), timeout=30).stdout
    )
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise LiveError("container_inspect_invalid")
    return value[0]


def remove_exact_stopped_ha_container(image_ref: str, image_id: str) -> None:
    rows = stopped_ha_containers()
    matching = []
    for row in rows:
        container_id = row.get("ID")
        if not isinstance(container_id, str):
            raise LiveError("ha_container_inventory_invalid")
        document = inspect_container(container_id)
        config = document.get("Config")
        state = document.get("State")
        if (
            isinstance(config, dict)
            and config.get("Image") == image_ref
            and document.get("Image") == image_id
        ):
            if not isinstance(state, dict) or state.get("Running") is True:
                raise LiveError("ha_container_not_stopped")
            matching.append(container_id)
    users = container_ids_by_ancestor(image_id)
    if sorted(users) != sorted(matching):
        raise LiveError("ha_image_has_other_container_users")
    if len(matching) > 1:
        raise LiveError("ha_container_ambiguous")
    if matching:
        run(("docker", "container", "rm", matching[0]), timeout=120)
    if container_ids_by_ancestor(image_id):
        raise LiveError("ha_container_release_incomplete")


def exact_image_removable(host, reference: str, image_id: str) -> None:
    document = image_document(host, reference)
    if document is None or document.get("Id") != image_id:
        raise LiveError("exact_image_binding_drift")
    tags = document.get("RepoTags")
    digests = document.get("RepoDigests")
    expected_digest = reference.rsplit(":", 1)[0] + "@" + image_id
    if tags != [reference] or digests not in ([], None, [expected_digest]):
        raise LiveError("exact_image_has_additional_references")


def remove_exact_image(host, reference: str, image_id: str) -> None:
    exact_image_removable(host, reference, image_id)
    run(("docker", "image", "rm", "--no-prune", image_id), timeout=300)
    if image_document(host, reference) is not None or image_document(host, image_id) is not None:
        raise LiveError("exact_image_release_incomplete")


def stream_docker_load(expected_size: int, expected_sha256: str) -> None:
    process = subprocess.Popen(
        ("docker", "load"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None:
        raise LiveError("docker_load_stdin_unavailable")
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            block = sys.stdin.buffer.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            total += len(block)
            process.stdin.write(block)
        process.stdin.close()
        process.stdin = None
        stdout, stderr = process.communicate(timeout=1800)
    except BaseException:
        if process.poll() is None:
            process.kill()
        raise
    if process.returncode:
        raise LiveError("docker_load_failed")
    if total != expected_size:
        raise LiveError("predecessor_stream_size_mismatch")
    if digest.hexdigest() != expected_sha256:
        raise LiveError("predecessor_stream_sha256_mismatch")


def backup_evidence_from_state(state: dict[str, Any]) -> executor.BackupEvidence | None:
    value = state.get("backup")
    if value is None:
        return None
    return executor.BackupEvidence(
        archive_sha256=value["archive_sha256"],
        archive_size_bytes=value["archive_size_bytes"],
        manifest_sha256=value["manifest_sha256"],
        staged_manifest_sha256=value["staged_manifest_sha256"],
        filesystem_id=value["filesystem_id"],
        original_data_inode=value["original_data_inode"],
        staged_data_inode=value["staged_data_inode"],
        preserved_path=value["preserved_path"],
    )


def restore_original_data_from_evidence(
    backup: executor.BackupEvidence | None,
) -> None:
    if backup is None:
        return
    preserved = Path(backup.preserved_path)
    if not preserved.exists() or preserved.is_symlink():
        raise LiveError("preserved_original_data_missing")
    current_identity = directory_identity(HA_DATA_ROOT)
    preserved_identity = directory_identity(preserved)
    original = (backup.filesystem_id, backup.original_data_inode)
    staged = (backup.filesystem_id, backup.staged_data_inode)
    if current_identity == original and preserved_identity == staged:
        return
    if current_identity == staged and preserved_identity == original:
        exchange_directories(HA_DATA_ROOT, preserved)
    else:
        raise LiveError("data_exchange_recovery_ambiguous")
    if directory_identity(HA_DATA_ROOT) != original:
        raise LiveError("original_data_restore_failed")


def remove_predecessor_if_exact(host) -> None:
    document = image_document(host, contract.PREDECESSOR_IMAGE)
    if document is None:
        return
    if document.get("Id") != contract.PREDECESSOR_IMAGE_ID:
        raise LiveError("predecessor_cleanup_identity_drift")
    remove_exact_stopped_ha_container(
        contract.PREDECESSOR_IMAGE,
        contract.PREDECESSOR_IMAGE_ID,
    )
    remove_exact_image(
        host,
        contract.PREDECESSOR_IMAGE,
        contract.PREDECESSOR_IMAGE_ID,
    )


def restore_current_image_if_needed(host) -> None:
    document = image_document(host, contract.CURRENT_IMAGE)
    if document is not None:
        if document.get("Id") != contract.CURRENT_IMAGE_ID:
            raise LiveError("current_restore_preexisting_identity_drift")
        return
    verify_current_archive_identity()
    path = p3_rollback_archive()
    run(("docker", "load", "-i", str(path)), timeout=1800)
    document = image_document(host, contract.CURRENT_IMAGE)
    if document is None or document.get("Id") != contract.CURRENT_IMAGE_ID:
        raise LiveError("current_image_restore_failed")


def recover_to_current(source_head: str) -> dict[str, Any]:
    from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

    state = read_state()
    if state is None:
        raise LiveError("switch_recovery_state_missing")
    contract.validate_recovery_state(
        state,
        expected_source_head=source_head,
    )
    phase = state["phase"]
    if phase == contract.PHASE_PREDECESSOR_HEALTHY:
        return {
            "status": "PREDECESSOR_SWITCH_ALREADY_HEALTHY",
            "phase": phase,
            "transaction_id": state["transaction_id"],
        }
    if phase == contract.PHASE_ROLLED_BACK:
        return {
            "status": "PREDECESSOR_SWITCH_ALREADY_ROLLED_BACK",
            "phase": phase,
            "transaction_id": state["transaction_id"],
        }

    host = LocalHaPredecessorRuntime()
    current = p3_transaction()
    verify_usb_binding(current)
    mount_usb(read_only=False)
    failure = None
    try:
        verify_current_archive_identity()
        try:
            host.stop_services()
        except Exception:
            if host.rollback_writers_quiesced() is not True:
                raise

        remove_predecessor_if_exact(host)
        backup = backup_evidence_from_state(state)
        restore_original_data_from_evidence(backup)
        restore_current_image_if_needed(host)

        binding = host.component_binding_v2("homeassistant")
        if binding == contract.PREDECESSOR_IMAGE:
            host.rewrite_component_image(
                "homeassistant",
                contract.PREDECESSOR_IMAGE,
                contract.CURRENT_IMAGE,
            )
        elif binding != contract.CURRENT_IMAGE:
            raise LiveError("current_binding_recovery_ambiguous")

        host.start_services(readiness_timeout=READINESS_TIMEOUT_SECONDS)
        runtime = host._runtime("homeassistant")
        if (
            runtime["image_ref"] != contract.CURRENT_IMAGE
            or runtime["image_id"] != contract.CURRENT_IMAGE_ID
            or runtime["restart_count"] != 0
        ):
            raise LiveError("current_runtime_recovery_failed")
        snapshot = host.observe_v2()
        if host._converged_health_v2(snapshot) is not True:
            raise LiveError("current_health_recovery_failed")

        terminal = {
            **state,
            "phase": contract.PHASE_ROLLED_BACK,
            "failure": "recovered_from:" + phase,
        }
        atomic_write_state(terminal)
        return {
            "status": "PREDECESSOR_SWITCH_RECOVERED_TO_CURRENT",
            "phase": contract.PHASE_ROLLED_BACK,
            "transaction_id": state["transaction_id"],
            "recovered_from": phase,
        }
    except Exception as error:
        failure = str(error).partition(":")[0] or type(error).__name__
        terminal = {
            **state,
            "phase": contract.PHASE_RECOVERY_REQUIRED,
            "failure": "recovery_failed:" + failure,
        }
        atomic_write_state(terminal)
        return {
            "status": "PREDECESSOR_SWITCH_RECOVERY_REQUIRED",
            "phase": contract.PHASE_RECOVERY_REQUIRED,
            "transaction_id": state["transaction_id"],
            "failure": failure,
        }
    finally:
        unmount_usb()


class LocalSwitchBackend:
    def __init__(
        self,
        *,
        grant: contract.SwitchGrant,
        source_head: str,
        read_only_usb: bool,
    ) -> None:
        from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

        self.grant = grant
        self.source_head = source_head
        self.host = LocalHaPredecessorRuntime()
        self.read_only_usb = read_only_usb
        self.mounted = False
        self.baseline: dict[str, dict[str, Any]] | None = None
        self.backup_record = None

    def close(self) -> None:
        if self.mounted:
            unmount_usb()
            self.mounted = False

    def _mount(self) -> None:
        if not self.mounted:
            mount_usb(read_only=self.read_only_usb)
            self.mounted = True

    def _current_health(self) -> dict[str, dict[str, Any]]:
        if self.host.component_binding_v2("homeassistant") != contract.CURRENT_IMAGE:
            raise LiveError("current_binding_drift")
        if self.host.image_binding_modes_v2().get("homeassistant") != "dynamic":
            raise LiveError("current_binding_mode_not_dynamic")
        current = self.host._runtime("homeassistant")
        manager = self.host._runtime("manager")
        broker = self.host._runtime("broker")
        if (
            current["image_ref"] != contract.CURRENT_IMAGE
            or current["image_id"] != contract.CURRENT_IMAGE_ID
            or current["restart_count"] != 0
            or image_document(self.host, contract.PREDECESSOR_IMAGE) is not None
        ):
            raise LiveError("current_runtime_drift")
        snapshot = self.host.observe_v2()
        if self.host._converged_health_v2(snapshot) is not True:
            raise LiveError("current_health_not_converged")
        return {"homeassistant": current, "manager": manager, "broker": broker}

    def verify_preflight(self, grant: contract.SwitchGrant) -> None:
        if grant != self.grant or grant.source_head != self.source_head:
            raise LiveError("switch_source_binding_drift")
        if time.time() >= grant.expires_at_unix:
            raise LiveError("switch_grant_expired")
        existing = read_state()
        if existing is not None:
            raise LiveError("switch_transaction_state_already_exists")
        self.baseline = self._current_health()
        current = p3_transaction()
        verify_usb_binding(current)
        self._mount()
        verify_current_archive_against_runtime(self.host)

        original_fsid, _ = directory_identity(HA_DATA_ROOT)
        docker_root = Path(
            self.host._run(
                ("docker", "info", "--format", "{{.DockerRootDir}}")
            ).stdout.decode().strip()
        )
        if (
            not docker_root.is_absolute()
            or docker_root.stat().st_dev != HA_DATA_ROOT.stat().st_dev
            or os.statvfs(docker_root).f_fsid != original_fsid
        ):
            raise LiveError("switch_internal_filesystem_split")

    def write_state(self, document: dict[str, Any]) -> None:
        atomic_write_state(document)

    def quiesce_application(self, grant: contract.SwitchGrant) -> None:
        self.host.stop_services()
        if self.host.rollback_writers_quiesced() is not True:
            raise LiveError("application_writers_not_quiesced")
        verify_current_archive_against_runtime(self.host)

    def _fresh_backup_directory(self, txid: str) -> Path:
        # mkdir one level at a time and never replace existing content.
        current = USB_MOUNT
        for name in R8_USB_ROOT.parts:
            current = current / name
            if not current.exists():
                current.mkdir(mode=0o700)
            require_private_directory(current)
        tx_root = current / txid
        if tx_root.exists() or tx_root.is_symlink():
            raise LiveError("switch_usb_transaction_already_exists")
        tx_root.mkdir(mode=0o700)
        backup = tx_root / "ha-backup"
        backup.mkdir(mode=0o700)
        return backup

    def create_fresh_backup_and_stage(
        self,
        grant: contract.SwitchGrant,
        txid: str,
    ) -> executor.BackupEvidence:
        from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackup

        if self.host.rollback_writers_quiesced() is not True:
            raise LiveError("backup_writers_not_quiesced")
        backup_dir = self._fresh_backup_directory(txid)
        backup_fd = os.open(
            backup_dir,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            backup = ProtectedHaDataBackup(
                work_root=STATE_ROOT,
                ha_data_root=HA_DATA_ROOT,
            )
            record = backup.create(backup_fd, txid)
            if backup.verify(backup_fd, txid, record) != record:
                raise LiveError("fresh_backup_verification_drift")

            preserved = HA_DATA_ROOT.parent / (
                ".n3w-r8-preserved-10.4-" + txid[:16]
            )
            if preserved.exists() or preserved.is_symlink():
                raise LiveError("preserved_data_path_occupied")
            original_fsid, original_inode = directory_identity(HA_DATA_ROOT)
            backup.restore_to_stage(backup_fd, txid, record, preserved)
            staged_fsid, staged_inode = directory_identity(preserved)
            if staged_fsid != original_fsid or staged_inode == original_inode:
                raise LiveError("staged_data_filesystem_drift")
            self.backup_record = record
            return executor.BackupEvidence(
                archive_sha256=record.archive_sha256,
                archive_size_bytes=record.archive_size_bytes,
                manifest_sha256=record.manifest_sha256,
                staged_manifest_sha256=record.manifest_sha256,
                filesystem_id=original_fsid,
                original_data_inode=original_inode,
                staged_data_inode=staged_inode,
                preserved_path=str(preserved),
            )
        finally:
            os.close(backup_fd)

    def exchange_data_root(
        self,
        grant: contract.SwitchGrant,
        txid: str,
        backup: executor.BackupEvidence,
    ) -> None:
        if self.host.rollback_writers_quiesced() is not True:
            raise LiveError("data_exchange_writers_not_quiesced")
        preserved = Path(backup.preserved_path)
        if directory_identity(HA_DATA_ROOT) != (
            backup.filesystem_id,
            backup.original_data_inode,
        ):
            raise LiveError("original_data_identity_drift")
        if directory_identity(preserved) != (
            backup.filesystem_id,
            backup.staged_data_inode,
        ):
            raise LiveError("staged_data_identity_drift")
        exchange_directories(HA_DATA_ROOT, preserved)
        if directory_identity(HA_DATA_ROOT) != (
            backup.filesystem_id,
            backup.staged_data_inode,
        ):
            raise LiveError("published_staged_data_identity_drift")
        if directory_identity(preserved) != (
            backup.filesystem_id,
            backup.original_data_inode,
        ):
            raise LiveError("preserved_original_data_identity_drift")

    def release_current_image(
        self,
        grant: contract.SwitchGrant,
        txid: str,
    ) -> None:
        if self.host.rollback_writers_quiesced() is not True:
            raise LiveError("current_release_writers_not_quiesced")
        remove_exact_stopped_ha_container(
            contract.CURRENT_IMAGE,
            contract.CURRENT_IMAGE_ID,
        )
        remove_exact_image(
            self.host,
            contract.CURRENT_IMAGE,
            contract.CURRENT_IMAGE_ID,
        )

    def measure_post_release_available_bytes(
        self,
        grant: contract.SwitchGrant,
    ) -> int:
        if image_document(self.host, contract.CURRENT_IMAGE) is not None:
            raise LiveError("post_release_current_image_present")
        docker_root = Path(
            self.host._run(
                ("docker", "info", "--format", "{{.DockerRootDir}}")
            ).stdout.decode().strip()
        )
        info = os.statvfs(docker_root)
        return info.f_bavail * info.f_frsize

    def load_predecessor_from_stream(
        self,
        grant: contract.SwitchGrant,
        txid: str,
    ) -> None:
        if image_document(self.host, contract.CURRENT_IMAGE) is not None:
            raise LiveError("single_image_current_still_present")
        if image_document(self.host, contract.PREDECESSOR_IMAGE) is not None:
            raise LiveError("predecessor_image_preexisting")
        stream_docker_load(
            grant.predecessor_archive_size,
            grant.predecessor_archive_sha256,
        )
        document = image_document(self.host, contract.PREDECESSOR_IMAGE)
        if document is None or document.get("Id") != contract.PREDECESSOR_IMAGE_ID:
            raise LiveError("predecessor_loaded_identity_drift")
        if image_document(self.host, contract.CURRENT_IMAGE) is not None:
            raise LiveError("single_image_contract_violated")

    def switch_to_predecessor_binding(
        self,
        grant: contract.SwitchGrant,
        txid: str,
    ) -> None:
        self.host.rewrite_component_image(
            "homeassistant",
            contract.CURRENT_IMAGE,
            contract.PREDECESSOR_IMAGE,
        )
        if self.host.component_binding_v2("homeassistant") != contract.PREDECESSOR_IMAGE:
            raise LiveError("predecessor_binding_not_published")

    def start_and_verify_predecessor(
        self,
        grant: contract.SwitchGrant,
        txid: str,
    ) -> None:
        if self.baseline is None:
            raise LiveError("switch_baseline_missing")
        self.host.start_services(readiness_timeout=READINESS_TIMEOUT_SECONDS)
        runtime = self.host._runtime("homeassistant")
        if (
            runtime["image_ref"] != contract.PREDECESSOR_IMAGE
            or runtime["image_id"] != contract.PREDECESSOR_IMAGE_ID
            or runtime["restart_count"] != 0
            or image_document(self.host, contract.CURRENT_IMAGE) is not None
        ):
            raise LiveError("predecessor_runtime_not_exact")
        for component in ("manager", "broker"):
            observed = self.host._runtime(component)
            baseline = self.baseline[component]
            for key in ("image_ref", "image_id", "runtime_contract_sha256"):
                if observed[key] != baseline[key]:
                    raise LiveError(component + "_runtime_drift")
        snapshot = self.host.observe_v2()
        if self.host._converged_health_v2(snapshot) is not True:
            raise LiveError("predecessor_health_not_converged")
        state = read_state()
        backup = state.get("backup") if isinstance(state, dict) else None
        if not isinstance(backup, dict):
            raise LiveError("predecessor_backup_state_missing")
        preserved = Path(backup["preserved_path"])
        if directory_identity(preserved) != (
            backup["filesystem_id"],
            backup["original_data_inode"],
        ):
            raise LiveError("preserved_original_data_drift")

    def _restore_original_data(
        self,
        backup: executor.BackupEvidence | None,
    ) -> None:
        restore_original_data_from_evidence(backup)

    def _remove_predecessor_if_present(self) -> None:
        remove_predecessor_if_exact(self.host)

    def _restore_current_image(self) -> None:
        restore_current_image_if_needed(self.host)

    def rollback_to_current(
        self,
        grant: contract.SwitchGrant,
        txid: str,
        *,
        phase: str,
        backup: executor.BackupEvidence | None,
    ) -> None:
        try:
            self.host.stop_services()
        except Exception:
            if self.host.rollback_writers_quiesced() is not True:
                raise
        self._remove_predecessor_if_present()
        self._restore_original_data(backup)
        self._restore_current_image()
        binding = self.host.component_binding_v2("homeassistant")
        if binding == contract.PREDECESSOR_IMAGE:
            self.host.rewrite_component_image(
                "homeassistant",
                contract.PREDECESSOR_IMAGE,
                contract.CURRENT_IMAGE,
            )
        elif binding != contract.CURRENT_IMAGE:
            raise LiveError("current_binding_recovery_ambiguous")
        self.host.start_services(readiness_timeout=READINESS_TIMEOUT_SECONDS)
        current = self.host._runtime("homeassistant")
        if (
            current["image_ref"] != contract.CURRENT_IMAGE
            or current["image_id"] != contract.CURRENT_IMAGE_ID
            or current["restart_count"] != 0
        ):
            raise LiveError("current_runtime_recovery_failed")
        snapshot = self.host.observe_v2()
        if self.host._converged_health_v2(snapshot) is not True:
            raise LiveError("current_health_recovery_failed")


def preflight_report(source_head: str) -> dict[str, Any]:
    from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

    host = LocalHaPredecessorRuntime()
    if source_mounts(contract.BOUND_USB_DEVICE):
        raise LiveError("host_usb_already_mounted")
    baseline = {
        name: host._runtime(name)
        for name in ("broker", "manager", "homeassistant")
    }
    if (
        baseline["homeassistant"]["image_ref"] != contract.CURRENT_IMAGE
        or baseline["homeassistant"]["image_id"] != contract.CURRENT_IMAGE_ID
        or host.component_binding_v2("homeassistant") != contract.CURRENT_IMAGE
        or host.image_binding_modes_v2().get("homeassistant") != "dynamic"
        or image_document(host, contract.PREDECESSOR_IMAGE) is not None
    ):
        raise LiveError("preflight_runtime_drift")
    snapshot = host.observe_v2()
    if host._converged_health_v2(snapshot) is not True:
        raise LiveError("preflight_health_not_converged")
    current = p3_transaction()
    verify_usb_binding(current)
    mount_usb(read_only=True)
    try:
        verify_current_archive_against_runtime(host)
        root_info = os.statvfs("/")
        data_fsid, data_inode = directory_identity(HA_DATA_ROOT)
        return {
            "schema": contract.SCHEMA,
            "status": "R8_PREDECESSOR_SWITCH_READONLY_PREFLIGHT_PASS",
            "source_head": source_head,
            "current_image": contract.CURRENT_IMAGE,
            "current_image_id": contract.CURRENT_IMAGE_ID,
            "predecessor_present": False,
            "rollback_transaction_sha256": contract.CURRENT_ROLLBACK_TX_SHA256,
            "rollback_archive_sha256": contract.CURRENT_ROLLBACK_ARCHIVE_SHA256,
            "data_filesystem_id": data_fsid,
            "data_inode": data_inode,
            "pre_release_available_bytes": (
                root_info.f_bavail * root_info.f_frsize
            ),
            "capacity_decision": "DEFER_UNTIL_POST_RELEASE_MEASUREMENT",
            "host_usb_mount_before": False,
            "isolated_usb_read_only": True,
        }
    finally:
        unmount_usb()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "execute", "recover", "status"), required=True)
    parser.add_argument("--recovery-pyz", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--grant", type=Path)
    args = parser.parse_args()

    ensure_recovery_modules(args.recovery_pyz)

    if args.mode == "status":
        print(json.dumps({"status": "OBSERVED", "state": read_state()}, sort_keys=True))
        return 0

    if args.mode == "recover":
        try:
            report = recover_to_current(args.source_head)
        finally:
            if source_mounts(contract.BOUND_USB_DEVICE):
                raise LiveError("host_usb_mount_leaked")
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] in {
            "PREDECESSOR_SWITCH_RECOVERED_TO_CURRENT",
            "PREDECESSOR_SWITCH_ALREADY_ROLLED_BACK",
            "PREDECESSOR_SWITCH_ALREADY_HEALTHY",
        } else 3

    if args.mode == "preflight":
        try:
            report = preflight_report(args.source_head)
        finally:
            if source_mounts(contract.BOUND_USB_DEVICE):
                raise LiveError("host_usb_mount_leaked")
        report["host_usb_mount_after"] = False
        print(json.dumps(report, sort_keys=True))
        return 0

    if args.grant is None:
        raise LiveError("switch_grant_required")
    if args.grant.is_symlink() or not args.grant.is_file():
        raise LiveError("switch_grant_invalid")
    grant_info = args.grant.stat()
    if (
        grant_info.st_uid != os.geteuid()
        or stat.S_IMODE(grant_info.st_mode) != 0o600
        or grant_info.st_size <= 0
        or grant_info.st_size > 16 * 1024
    ):
        raise LiveError("switch_grant_metadata_invalid")
    raw = json.loads(args.grant.read_text(encoding="utf-8"))
    grant = contract.SwitchGrant.from_document(raw)
    backend = LocalSwitchBackend(
        grant=grant,
        source_head=args.source_head,
        read_only_usb=False,
    )
    try:
        result = executor.execute_switch(backend, grant)
    finally:
        backend.close()
        if source_mounts(contract.BOUND_USB_DEVICE):
            raise LiveError("host_usb_mount_leaked")

    print(json.dumps({
        "status": result.status,
        "transaction_id": result.transaction_id,
        "phase": result.phase,
        "post_release_capacity": result.post_release_capacity,
        "failure": result.failure,
    }, sort_keys=True))
    if result.status == "PREDECESSOR_SWITCH_PASS":
        return 0
    if result.status == "PREDECESSOR_SWITCH_ROLLED_BACK":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
