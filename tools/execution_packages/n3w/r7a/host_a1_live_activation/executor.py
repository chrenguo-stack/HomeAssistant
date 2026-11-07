#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SSH_TRANSPORT_PATH = REPO_ROOT / "tools/n3w_t1_ssh_transport.py"

SCHEMA = "gh.n3w-t1-r7a-host-a1-live-activation-result/1"
AUTHORIZATION = "N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261107_01"
CONFIRMATION = "EXECUTE R7A HOST DAEMON COMPOSE A1 LIVE ACTIVATION: YES"

EXPECTED_MANAGER = "local/greenhouse-manager:fresh-bf38e388497b"
EXPECTED_HOMEASSISTANT = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_BROKER = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_PEER_RUNTIME_IDS = {
    "homeassistant": "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306",
    "broker": "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
}
MANAGER_USER = "999:999"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
HOST_UNIT = "n3w-t1-ha-ota.service"

STATE_ROOT = "/var/lib/n3w-t1-core-updater"
V2_TRANSACTION = f"{STATE_ROOT}/upgrade.json"
LEGACY_TRANSACTION = f"{STATE_ROOT}/manager-upgrade.json"
HA_USB_TRANSACTION = f"{STATE_ROOT}/homeassistant-usb-upgrade.json"
HA_PREPARE_STATE = f"{STATE_ROOT}/homeassistant-usb-prepare.json"

RUNTIME_ROOT = "/run/n3w-t1-ota"
SOCKET_PATH = f"{RUNTIME_ROOT}/ha-ota.sock"
RUNTIME_MANIFEST = f"{RUNTIME_ROOT}/approved-homeassistant.json"
ACTIVATION_ENV = "/etc/n3wfc4/ha-ota-activation.env"
APPROVED_MANIFEST = "/etc/n3w-t1-ota/approved-homeassistant.json"
HOST_UNIT_PATH = "/etc/systemd/system/n3w-t1-ha-ota.service"
SERVICES_DROPIN = (
    "/etc/systemd/system/n3wfc4-services-activation.service.d/"
    "95-n3w-ha-ota.conf"
)

SOURCE_DESTINATIONS = {
    "tools/n3w_t1_core_updater_ha_daemon.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_daemon.py",
    "tools/n3w_t1_core_updater_ha_ipc.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py",
    "tools/n3w_t1_core_updater_ha_prepare.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare.py",
    "tools/n3w_t1_core_updater_ha_prepare_host.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py",
    "tools/n3w_t1_core_updater_ha_usb.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb.py",
    "tools/n3w_t1_core_updater_ha_usb_state.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb_state.py",
    "tools/n3w_t1_core_updater_ha_usb_media.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb_media.py",
    "tools/n3w_t1_core_updater_ha_backup.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_backup.py",
    "tools/n3w_t1_core_updater_ha_recovery.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_recovery.py",
    "tools/n3w_t1_core_updater_v2_common.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_v2_common.py",
    "tools/n3w_t1_core_updater_v2_state.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_v2_state.py",
    "tools/n3w_t1_core_updater_common.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_common.py",
    "tools/n3w_t1_portable_image_identity.py":
        "/opt/HomeAssistant/tools/n3w_t1_portable_image_identity.py",
    "infra/n3w-t1/production/docker-compose.ha-ota.yml":
        "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml",
    "infra/n3w-t1/systemd/n3w-t1-ha-ota.service":
        HOST_UNIT_PATH,
    "infra/n3w-t1/systemd/n3wfc4-services-activation.ha-ota.conf":
        SERVICES_DROPIN,
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json":
        APPROVED_MANIFEST,
}

LIVE_TARGETS = tuple(SOURCE_DESTINATIONS.values()) + (ACTIVATION_ENV,)
HA_IMAGE_RE = re.compile(
    r"^local/n3w-homeassistant:(?P<version>[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,3})-[0-9a-f]{8,64}$"
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EXECUTION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,160}$")


class StopExecution(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution(f"json_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise StopExecution(f"json_shape_invalid:{path.name}")
    return value


def run_local(
    argv: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution(f"local_command_timeout:{Path(argv[0]).name}") from error
    except OSError as error:
        raise StopExecution(
            f"local_command_transport_error:{Path(argv[0]).name}"
        ) from error
    if check and result.returncode != 0:
        raise StopExecution(
            f"local_command_failed:{Path(argv[0]).name}:{result.returncode}"
        )
    return result


def git_text(*args: str) -> str:
    return run_local(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.strip()


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise StopExecution("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    metadata = root.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise StopExecution("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, value: Any) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_local_source(
    expected_commit: str,
    *,
    require_live: bool,
) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
        raise StopExecution("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")

    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "gh.n3w-t1-r7a-host-a1-live-activation-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("proposed_authorization_id") != AUTHORIZATION:
        raise StopExecution("manifest_authorization_mismatch")
    if manifest.get("confirmation") != CONFIRMATION:
        raise StopExecution("manifest_confirmation_mismatch")

    authority = manifest.get("source_authority")
    expected_paths = set(SOURCE_DESTINATIONS) | {"tools/n3w_t1_ssh_transport.py"}
    if not isinstance(authority, dict) or set(authority) != expected_paths:
        raise StopExecution("source_authority_shape_invalid")
    for path, expected_blob in authority.items():
        observed = git_text("rev-parse", f"HEAD:{path}")
        if observed != expected_blob:
            raise StopExecution(f"source_authority_drift:{path}")

    if require_live and manifest.get("live_execution_authorized") is not True:
        raise StopExecution("live_execution_not_authorized")
    return manifest


def load_ssh_transport(manifest: dict[str, Any]) -> type:
    authority = manifest["source_authority"]
    if (
        SSH_TRANSPORT_PATH.is_symlink()
        or not SSH_TRANSPORT_PATH.is_file()
        or git_text("hash-object", str(SSH_TRANSPORT_PATH))
        != authority["tools/n3w_t1_ssh_transport.py"]
    ):
        raise StopExecution("ssh_transport_binding_invalid")
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_ssh_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise StopExecution("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def start_ssh_epoch(
    transport_type: type,
    *,
    target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
) -> Any:
    transport = None
    try:
        transport = transport_type(
            target=target,
            known_hosts=known_hosts.expanduser(),
            expected_host_key_sha256=expected_host_key_sha256,
        )
        transport.start_epoch()
        return transport
    except Exception as error:
        if transport is not None:
            try:
                transport.close_epoch()
            except Exception:
                pass
        raise StopExecution(
            f"ssh_epoch_start_failed:{type(error).__name__}"
        ) from error


def remote(
    transport: Any,
    argv: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return transport.run_remote(argv, timeout=timeout, check=check)
    except Exception as error:
        raise StopExecution(f"remote_command_failed:{Path(argv[0]).name}") from error


def copy_to(
    transport: Any,
    local: Path,
    remote_path: str,
    *,
    timeout: int = 300,
) -> None:
    try:
        transport.scp_to(local, remote_path, timeout=timeout)
    except Exception as error:
        raise StopExecution("remote_copy_failed") from error


def parse_systemd_show(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in payload.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def remote_exists(transport: Any, path: str, kind: str = "-e") -> bool:
    return remote(
        transport,
        ["test", kind, path],
        check=False,
        timeout=30,
    ).returncode == 0


def remote_private_json(
    transport: Any,
    path: str,
    *,
    schema: str,
) -> dict[str, Any]:
    if remote_exists(transport, path, "-L"):
        raise StopExecution("state_file_symlink")
    if not remote_exists(transport, path, "-f"):
        raise StopExecution("state_file_missing")
    metadata = remote(
        transport,
        ["stat", "-c", "%u:%g:%a:%F", path],
        timeout=30,
    ).stdout.strip()
    if metadata != "0:0:600:regular file":
        raise StopExecution("state_file_metadata_invalid")
    try:
        document = json.loads(remote(transport, ["cat", path], timeout=30).stdout)
    except json.JSONDecodeError as error:
        raise StopExecution("state_file_json_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != schema:
        raise StopExecution("state_file_schema_invalid")
    return document


def docker_container(transport: Any, image: str) -> dict[str, Any]:
    ids = [
        line.strip()
        for line in remote(
            transport,
            [
                "docker",
                "ps",
                "--filter",
                f"ancestor={image}",
                "--format",
                "{{.ID}}",
            ],
            timeout=60,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise StopExecution("container_cardinality_invalid")
    try:
        document = json.loads(
            remote(transport, ["docker", "inspect", ids[0]], timeout=60).stdout
        )
    except json.JSONDecodeError as error:
        raise StopExecution("container_inspect_json_invalid") from error
    if not isinstance(document, list) or len(document) != 1:
        raise StopExecution("container_inspect_shape_invalid")
    item = document[0]
    if not isinstance(item, dict):
        raise StopExecution("container_inspect_shape_invalid")
    return item


def env_map(document: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in document.get("Config", {}).get("Env") or []:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def usb_like_disk_count(transport: Any) -> int:
    raw = remote(
        transport,
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--output",
            "TYPE,RM,RO,SIZE,MODEL,TRAN,MOUNTPOINTS,MAJ:MIN",
        ],
        timeout=60,
    )
    try:
        document = json.loads(raw.stdout)
    except json.JSONDecodeError as error:
        raise StopExecution("lsblk_json_invalid") from error
    devices = document.get("blockdevices")
    if not isinstance(devices, list):
        raise StopExecution("lsblk_shape_invalid")
    return sum(
        1
        for item in devices
        if isinstance(item, dict)
        and item.get("type") == "disk"
        and (
            str(item.get("tran") or "").lower() == "usb"
            or bool(item.get("rm"))
        )
    )


def installed_version_from_ha_image(image: str) -> str:
    match = HA_IMAGE_RE.fullmatch(image)
    if match is None:
        raise StopExecution("homeassistant_image_version_invalid")
    return match.group("version")


def require_manager_transaction(transport: Any) -> dict[str, Any]:
    transaction = remote_private_json(
        transport,
        V2_TRANSACTION,
        schema="gh.n3w-t1-core-updater-transaction/2",
    )
    if (
        transaction.get("component") != "manager"
        or transaction.get("status") != "COMMITTED"
        or transaction.get("phase") != "COMMITTED"
        or transaction.get("authorization_consumed") is not True
        or transaction.get("target", {}).get("target_image_ref") != EXPECTED_MANAGER
        or not isinstance(transaction.get("target_runtime_image_id"), str)
        or SHA256_RE.fullmatch(transaction["target_runtime_image_id"]) is None
    ):
        raise StopExecution("manager_transaction_invalid")
    return transaction


def require_recovery_clear(transport: Any) -> dict[str, Any]:
    legacy_status = None
    if remote_exists(transport, LEGACY_TRANSACTION):
        legacy = remote_private_json(
            transport,
            LEGACY_TRANSACTION,
            schema="gh.n3w-t1-core-updater-transaction/1",
        )
        legacy_status = legacy.get("status")
        if legacy_status not in {"COMMITTED", "ROLLED_BACK"}:
            raise StopExecution("legacy_manager_recovery_required")
    return {
        "v2_manager_status": "COMMITTED",
        "legacy_manager_status": legacy_status,
        "recovery_required": False,
    }


def require_activation_residue_absent(transport: Any) -> None:
    for path in (
        HOST_UNIT_PATH,
        SERVICES_DROPIN,
        ACTIVATION_ENV,
        APPROVED_MANIFEST,
        RUNTIME_ROOT,
        HA_USB_TRANSACTION,
        HA_PREPARE_STATE,
    ):
        if remote_exists(transport, path, "-L") or remote_exists(
            transport,
            path,
        ):
            raise StopExecution("a1_activation_residue_present")


def collect_preflight(transport: Any) -> dict[str, Any]:
    if remote(transport, ["uname", "-m"], timeout=30).stdout.strip() != "aarch64":
        raise StopExecution("host_architecture_invalid")
    if (
        remote(
            transport,
            ["systemctl", "is-system-running"],
            check=False,
            timeout=30,
        ).stdout.strip()
        != "running"
    ):
        raise StopExecution("host_system_state_invalid")
    if remote(
        transport,
        ["systemctl", "is-active", SERVICES_UNIT],
        check=False,
        timeout=30,
    ).stdout.strip() != "active":
        raise StopExecution("services_owner_not_active")
    if remote(
        transport,
        ["systemctl", "is-active", BROKER_UNIT],
        check=False,
        timeout=30,
    ).stdout.strip() != "active":
        raise StopExecution("broker_owner_not_active")

    host_unit = parse_systemd_show(
        remote(
            transport,
            [
                "systemctl",
                "show",
                HOST_UNIT,
                "--property=LoadState",
                "--property=ActiveState",
                "--no-pager",
            ],
            check=False,
            timeout=30,
        ).stdout
    )
    if host_unit.get("LoadState") != "not-found":
        raise StopExecution("a1_host_service_already_present")

    require_activation_residue_absent(transport)
    if usb_like_disk_count(transport) != 0:
        raise StopExecution("usb_like_disk_present")

    transaction = require_manager_transaction(transport)
    recovery = require_recovery_clear(transport)
    manager = docker_container(transport, EXPECTED_MANAGER)
    homeassistant = docker_container(transport, EXPECTED_HOMEASSISTANT)
    broker = docker_container(transport, EXPECTED_BROKER)

    if (
        manager.get("Config", {}).get("Image") != EXPECTED_MANAGER
        or manager.get("Image") != transaction["target_runtime_image_id"]
        or manager.get("Config", {}).get("User") != MANAGER_USER
        or manager.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("manager_runtime_invalid")
    manager_env = env_map(manager)
    if any(key.startswith("GH_N3W_T1_OTA_") for key in manager_env):
        raise StopExecution("manager_ota_env_already_present")
    mounts = manager.get("Mounts") or []
    if any(
        item.get("Destination") == "/run/n3w/t1-ota"
        or item.get("Source") in {"/var/run/docker.sock", "/run/docker.sock"}
        or item.get("Destination") in {"/var/run/docker.sock", "/run/docker.sock"}
        for item in mounts
        if isinstance(item, dict)
    ):
        raise StopExecution("manager_privilege_or_ota_mount_drift")

    if (
        homeassistant.get("Config", {}).get("Image") != EXPECTED_HOMEASSISTANT
        or homeassistant.get("Image") != EXPECTED_PEER_RUNTIME_IDS["homeassistant"]
        or homeassistant.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("homeassistant_runtime_invalid")
    if (
        broker.get("Config", {}).get("Image") != EXPECTED_BROKER
        or broker.get("Image") != EXPECTED_PEER_RUNTIME_IDS["broker"]
        or broker.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("broker_runtime_invalid")

    version = installed_version_from_ha_image(EXPECTED_HOMEASSISTANT)
    return {
        "architecture": "aarch64",
        "manager_image": EXPECTED_MANAGER,
        "manager_runtime_image_id": transaction["target_runtime_image_id"],
        "homeassistant_image": EXPECTED_HOMEASSISTANT,
        "homeassistant_runtime_image_id": EXPECTED_PEER_RUNTIME_IDS["homeassistant"],
        "broker_image": EXPECTED_BROKER,
        "broker_runtime_image_id": EXPECTED_PEER_RUNTIME_IDS["broker"],
        "broker_container_id": broker.get("Id"),
        "installed_homeassistant_version": version,
        "manager_transaction_sha256": hashlib.sha256(canonical(transaction)).hexdigest(),
        "legacy_manager_transaction_status": recovery["legacy_manager_status"],
        "recovery_required": recovery["recovery_required"],
        "usb_like_disk_count": 0,
        "a1_residue_absent": True,
    }


def remote_staging_root(execution_id: str) -> str:
    if EXECUTION_ID_RE.fullmatch(execution_id) is None:
        raise StopExecution("execution_id_invalid")
    suffix = hashlib.sha256(execution_id.encode("utf-8")).hexdigest()[:16]
    return f"/var/tmp/n3w-r7a-a1-{suffix}"


def stage_bundle(
    transport: Any,
    execution_id: str,
    installed_version: str,
) -> tuple[str, dict[str, str]]:
    root = remote_staging_root(execution_id)
    if remote_exists(transport, root, "-L") or remote_exists(transport, root):
        raise StopExecution("remote_staging_already_exists")
    remote(
        transport,
        ["install", "-d", "-m", "0700", "-o", "root", "-g", "root", root],
        timeout=60,
    )
    hashes: dict[str, str] = {}
    for relative in sorted(SOURCE_DESTINATIONS):
        local = REPO_ROOT / relative
        if local.is_symlink() or not local.is_file():
            raise StopExecution(f"local_source_invalid:{relative}")
        remote_path = f"{root}/source/{relative}"
        remote(
            transport,
            [
                "install",
                "-d",
                "-m",
                "0700",
                "-o",
                "root",
                "-g",
                "root",
                str(Path(remote_path).parent),
            ],
            timeout=60,
        )
        copy_to(transport, local, remote_path, timeout=300)
        hashes[relative] = sha256_file(local)
        observed = remote(
            transport,
            ["sha256sum", remote_path],
            timeout=60,
        ).stdout.strip().split()
        if len(observed) != 2 or observed[0] != hashes[relative]:
            raise StopExecution("remote_source_hash_mismatch")

    env_local = Path(tempfile.mkdtemp(prefix="n3w-r7a-a1-env.")) / "ha-ota-activation.env"
    env_local.write_text(
        "GH_N3W_T1_OTA_ENABLED=true\n"
        f"GH_N3W_T1_OTA_INSTALLED_VERSION={installed_version}\n",
        encoding="utf-8",
    )
    os.chmod(env_local, 0o600)
    env_remote = f"{root}/generated/ha-ota-activation.env"
    remote(
        transport,
        [
            "install",
            "-d",
            "-m",
            "0700",
            "-o",
            "root",
            "-g",
            "root",
            str(Path(env_remote).parent),
        ],
        timeout=60,
    )
    copy_to(transport, env_local, env_remote, timeout=120)
    hashes["__activation_env__"] = sha256_file(env_local)
    observed = remote(
        transport,
        ["sha256sum", env_remote],
        timeout=60,
    ).stdout.strip().split()
    if len(observed) != 2 or observed[0] != hashes["__activation_env__"]:
        raise StopExecution("remote_activation_env_hash_mismatch")
    return root, hashes


def snapshot_rollback(
    transport: Any,
    staging_root: str,
) -> dict[str, Any]:
    backup_root = f"{staging_root}/rollback"
    remote(
        transport,
        ["install", "-d", "-m", "0700", "-o", "root", "-g", "root", backup_root],
        timeout=60,
    )
    inventory: dict[str, Any] = {}
    for index, target in enumerate(LIVE_TARGETS):
        if remote_exists(transport, target, "-L"):
            raise StopExecution("activation_target_symlink")
        exists = remote_exists(transport, target)
        present = remote_exists(transport, target, "-f")
        if exists and not present:
            raise StopExecution("activation_target_not_regular")
        item: dict[str, Any] = {"present": present}
        if present:
            metadata = remote(
                transport,
                ["stat", "-c", "%u:%g:%a:%F", target],
                timeout=30,
            ).stdout.strip()
            if not metadata.endswith(":regular file"):
                raise StopExecution("activation_target_not_regular")
            digest = remote(
                transport,
                ["sha256sum", target],
                timeout=60,
            ).stdout.strip().split()
            if len(digest) != 2:
                raise StopExecution("activation_target_hash_invalid")
            backup = f"{backup_root}/{index:02d}"
            remote(transport, ["cp", "-a", "--", target, backup], timeout=120)
            backup_digest = remote(
                transport,
                ["sha256sum", backup],
                timeout=60,
            ).stdout.strip().split()
            if len(backup_digest) != 2 or backup_digest[0] != digest[0]:
                raise StopExecution("rollback_backup_hash_mismatch")
            item.update(
                {
                    "metadata": metadata,
                    "sha256": digest[0],
                    "backup": backup,
                }
            )
        inventory[target] = item
    return inventory


def install_file(
    transport: Any,
    source: str,
    destination: str,
    *,
    mode: str,
) -> None:
    remote(
        transport,
        [
            "install",
            "-D",
            "-m",
            mode,
            "-o",
            "root",
            "-g",
            "root",
            source,
            destination,
        ],
        timeout=120,
    )


def activate(
    transport: Any,
    staging_root: str,
) -> None:
    for relative, destination in SOURCE_DESTINATIONS.items():
        install_file(
            transport,
            f"{staging_root}/source/{relative}",
            destination,
            mode="0644",
        )
    install_file(
        transport,
        f"{staging_root}/generated/ha-ota-activation.env",
        ACTIVATION_ENV,
        mode="0600",
    )
    remote(transport, ["systemctl", "daemon-reload"], timeout=60)
    remote(
        transport,
        ["systemctl", "enable", "--now", HOST_UNIT],
        timeout=120,
    )
    remote(
        transport,
        ["systemctl", "restart", SERVICES_UNIT],
        timeout=180,
    )


def require_file_metadata(
    transport: Any,
    path: str,
    expected: str,
) -> None:
    observed = remote(
        transport,
        ["stat", "-c", "%u:%g:%a:%F", path],
        timeout=30,
    ).stdout.strip()
    if observed != expected:
        raise StopExecution(f"metadata_invalid:{Path(path).name}")


def require_source_hashes(
    transport: Any,
    expected_hashes: dict[str, str],
) -> None:
    for relative, destination in SOURCE_DESTINATIONS.items():
        observed = remote(
            transport,
            ["sha256sum", destination],
            timeout=60,
        ).stdout.strip().split()
        if len(observed) != 2 or observed[0] != expected_hashes[relative]:
            raise StopExecution("installed_source_hash_mismatch")


def manager_ipc_status_probe(
    transport: Any,
    manager_id: str,
) -> dict[str, Any]:
    if (
        not isinstance(manager_id, str)
        or re.fullmatch(r"[0-9a-f]{12,64}", manager_id) is None
    ):
        raise StopExecution("manager_container_id_invalid")
    probe = (
        "import json;"
        "from greenhouse_manager.runtime.t1_ota_ipc import UnixSocketOtaBridge;"
        "s=UnixSocketOtaBridge('/run/n3w/t1-ota/ha-ota.sock')"
        ".get_homeassistant_ota_runtime_state();"
        "print(json.dumps({"
        "'phase':s.phase,"
        "'progress_percent':s.progress_percent,"
        "'error_code':s.error_code,"
        "'usb_confirmation_required':s.usb_confirmation_required"
        "},sort_keys=True))"
    )
    result = remote(
        transport,
        [
            "docker",
            "exec",
            "--user",
            MANAGER_USER,
            manager_id,
            "python",
            "-c",
            probe,
        ],
        timeout=30,
    )
    try:
        document = json.loads(result.stdout.strip())
    except json.JSONDecodeError as error:
        raise StopExecution("manager_ipc_status_json_invalid") from error
    if document != {
        "phase": "DISCOVERED",
        "progress_percent": None,
        "error_code": None,
        "usb_confirmation_required": False,
    }:
        raise StopExecution("manager_ipc_status_invalid")
    return document


def validate_post_activation(
    transport: Any,
    preflight: dict[str, Any],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    if remote(
        transport,
        ["systemctl", "is-active", HOST_UNIT],
        check=False,
        timeout=30,
    ).stdout.strip() != "active":
        raise StopExecution("host_daemon_not_active")
    if remote(
        transport,
        ["systemctl", "is-enabled", HOST_UNIT],
        check=False,
        timeout=30,
    ).stdout.strip() != "enabled":
        raise StopExecution("host_daemon_not_enabled")
    if remote(
        transport,
        ["systemctl", "is-active", SERVICES_UNIT],
        check=False,
        timeout=30,
    ).stdout.strip() != "active":
        raise StopExecution("services_owner_not_active_post")

    require_file_metadata(transport, RUNTIME_ROOT, "0:999:750:directory")
    require_file_metadata(transport, SOCKET_PATH, "0:999:660:socket")
    require_file_metadata(transport, RUNTIME_MANIFEST, "0:999:640:regular file")
    require_file_metadata(transport, ACTIVATION_ENV, "0:0:600:regular file")
    require_file_metadata(transport, APPROVED_MANIFEST, "0:0:644:regular file")
    require_file_metadata(transport, HOST_UNIT_PATH, "0:0:644:regular file")
    require_file_metadata(transport, SERVICES_DROPIN, "0:0:644:regular file")
    require_source_hashes(transport, source_hashes)

    main_pid = remote(
        transport,
        ["systemctl", "show", HOST_UNIT, "--property=MainPID", "--value"],
        timeout=30,
    ).stdout.strip()
    if not main_pid.isdigit() or int(main_pid) <= 1:
        raise StopExecution("host_daemon_pid_invalid")
    credentials = remote(
        transport,
        ["ps", "-o", "euid=", "-o", "egid=", "-p", main_pid],
        timeout=30,
    ).stdout.split()
    if credentials != ["0", "999"]:
        raise StopExecution("host_daemon_credentials_invalid")

    transaction = require_manager_transaction(transport)
    if (
        hashlib.sha256(canonical(transaction)).hexdigest()
        != preflight["manager_transaction_sha256"]
    ):
        raise StopExecution("manager_transaction_drift")

    manager = docker_container(transport, EXPECTED_MANAGER)
    homeassistant = docker_container(transport, EXPECTED_HOMEASSISTANT)
    broker = docker_container(transport, EXPECTED_BROKER)

    if (
        manager.get("Config", {}).get("Image") != EXPECTED_MANAGER
        or manager.get("Image") != preflight["manager_runtime_image_id"]
        or manager.get("Config", {}).get("User") != MANAGER_USER
        or manager.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("manager_runtime_invalid_post")
    values = env_map(manager)
    expected_env = {
        "GH_N3W_T1_OTA_ENABLED": "true",
        "GH_N3W_T1_OTA_INSTALLED_VERSION": preflight["installed_homeassistant_version"],
        "GH_N3W_T1_OTA_MANIFEST_PATH":
            "/run/n3w/t1-ota/approved-homeassistant.json",
        "GH_N3W_T1_OTA_SOCKET_PATH": "/run/n3w/t1-ota/ha-ota.sock",
    }
    if any(values.get(key) != value for key, value in expected_env.items()):
        raise StopExecution("manager_ota_env_invalid")

    mounts = manager.get("Mounts") or []
    runtime_mounts = [
        item
        for item in mounts
        if isinstance(item, dict)
        and item.get("Destination") == "/run/n3w/t1-ota"
    ]
    if (
        len(runtime_mounts) != 1
        or runtime_mounts[0].get("Source") != RUNTIME_ROOT
        or runtime_mounts[0].get("RW") is not False
    ):
        raise StopExecution("manager_runtime_mount_invalid")
    if any(
        item.get("Source") in {"/var/run/docker.sock", "/run/docker.sock"}
        or item.get("Destination") in {"/var/run/docker.sock", "/run/docker.sock"}
        for item in mounts
        if isinstance(item, dict)
    ):
        raise StopExecution("manager_docker_socket_present")
    devices = manager.get("HostConfig", {}).get("Devices")
    if devices not in (None, []):
        raise StopExecution("manager_block_device_access_present")

    manager_ipc_status = manager_ipc_status_probe(
        transport,
        manager.get("Id"),
    )

    if (
        homeassistant.get("Config", {}).get("Image") != EXPECTED_HOMEASSISTANT
        or homeassistant.get("Image") != EXPECTED_PEER_RUNTIME_IDS["homeassistant"]
        or homeassistant.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("homeassistant_drift_post")
    if (
        broker.get("Config", {}).get("Image") != EXPECTED_BROKER
        or broker.get("Image") != EXPECTED_PEER_RUNTIME_IDS["broker"]
        or broker.get("State", {}).get("Status") != "running"
        or broker.get("Id") != preflight["broker_container_id"]
    ):
        raise StopExecution("broker_continuity_invalid")

    if usb_like_disk_count(transport) != 0:
        raise StopExecution("usb_like_disk_present_post")
    if remote_exists(transport, HA_USB_TRANSACTION) or remote_exists(
        transport, HA_PREPARE_STATE
    ):
        raise StopExecution("prepare_transaction_created_during_a1")

    activation_env = remote(
        transport,
        ["cat", ACTIVATION_ENV],
        timeout=30,
    ).stdout
    expected_activation_env = (
        "GH_N3W_T1_OTA_ENABLED=true\n"
        f"GH_N3W_T1_OTA_INSTALLED_VERSION={preflight['installed_homeassistant_version']}\n"
    )
    if activation_env != expected_activation_env:
        raise StopExecution("activation_env_drift")

    return {
        "host_daemon": "active",
        "host_socket": SOCKET_PATH,
        "manager_ota_enabled": True,
        "manager_runtime_bind_read_only": True,
        "manager_ipc_status": manager_ipc_status,
        "broker_continuity": True,
        "homeassistant_unchanged": True,
        "usb_like_disk_count": 0,
        "prepare_transaction_absent": True,
    }


def restore_targets(
    transport: Any,
    inventory: dict[str, Any],
) -> None:
    for target, item in inventory.items():
        if item.get("present") is True:
            backup = item.get("backup")
            if not isinstance(backup, str):
                raise StopExecution("rollback_backup_invalid")
            metadata = str(item["metadata"]).split(":")
            remote(
                transport,
                [
                    "install",
                    "-D",
                    "-m",
                    metadata[2],
                    "-o",
                    metadata[0],
                    "-g",
                    metadata[1],
                    backup,
                    target,
                ],
                timeout=120,
            )
        else:
            remote(transport, ["rm", "-f", "--", target], timeout=60)


def rollback_activation(
    transport: Any,
    inventory: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    remote(
        transport,
        ["systemctl", "stop", HOST_UNIT],
        check=False,
        timeout=60,
    )
    remote(
        transport,
        ["systemctl", "disable", HOST_UNIT],
        check=False,
        timeout=60,
    )
    restore_targets(transport, inventory)
    remote(transport, ["systemctl", "daemon-reload"], timeout=60)
    remote(
        transport,
        ["systemctl", "restart", SERVICES_UNIT],
        timeout=180,
    )

    manager = docker_container(transport, EXPECTED_MANAGER)
    homeassistant = docker_container(transport, EXPECTED_HOMEASSISTANT)
    broker = docker_container(transport, EXPECTED_BROKER)
    manager_env = env_map(manager)
    mounts = manager.get("Mounts") or []
    if (
        manager.get("Config", {}).get("Image") != EXPECTED_MANAGER
        or manager.get("Image") != preflight["manager_runtime_image_id"]
        or manager.get("State", {}).get("Status") != "running"
        or any(key.startswith("GH_N3W_T1_OTA_") for key in manager_env)
        or any(
            isinstance(item, dict)
            and item.get("Destination") == "/run/n3w/t1-ota"
            for item in mounts
        )
    ):
        raise StopExecution("rollback_manager_invalid")
    if (
        homeassistant.get("Config", {}).get("Image") != EXPECTED_HOMEASSISTANT
        or homeassistant.get("Image") != EXPECTED_PEER_RUNTIME_IDS["homeassistant"]
        or homeassistant.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("rollback_homeassistant_invalid")
    if (
        broker.get("Config", {}).get("Image") != EXPECTED_BROKER
        or broker.get("Image") != EXPECTED_PEER_RUNTIME_IDS["broker"]
        or broker.get("State", {}).get("Status") != "running"
        or broker.get("Id") != preflight["broker_container_id"]
    ):
        raise StopExecution("rollback_broker_invalid")
    if usb_like_disk_count(transport) != 0:
        raise StopExecution("rollback_usb_inventory_invalid")
    if remote_exists(transport, HA_USB_TRANSACTION) or remote_exists(
        transport, HA_PREPARE_STATE
    ):
        raise StopExecution("rollback_prepare_state_invalid")
    return {
        "manager_successor_healthy_ota_disabled": True,
        "homeassistant_unchanged": True,
        "broker_continuity": True,
        "usb_like_disk_count": 0,
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION:
        raise StopExecution("authorization_id_mismatch")
    if args.confirm != CONFIRMATION:
        raise StopExecution("execution_confirmation_mismatch")

    manifest = validate_local_source(
        args.expected_commit,
        require_live=True,
    )
    root = prepare_evidence_root(args.evidence_root)
    closure: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "STOP",
        "execution_id": args.execution_id,
        "authorization_id": AUTHORIZATION,
        "live_execution_authorized": manifest["live_execution_authorized"],
        "t1_access": False,
        "t1_file_write": False,
        "authorization_claimed": False,
        "activation_invoked": False,
        "second_activation_invoked": False,
        "services_owner_restart_invoked": False,
        "automatic_a1_rollback_invoked": False,
        "automatic_a1_rollback_pass": None,
        "usb_mutation": False,
        "prepare_intent_invoked": False,
        "confirm_usb_erase_invoked": False,
        "board_access": False,
        "first_failed_operation": None,
    }

    transport = None
    claimed = False
    inventory: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    try:
        transport_type = load_ssh_transport(manifest)
        transport = start_ssh_epoch(
            transport_type,
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        closure["t1_access"] = True

        preflight = collect_preflight(transport)
        write_private(root / "preflight.json", preflight)

        staging_root, source_hashes = stage_bundle(
            transport,
            args.execution_id,
            preflight["installed_homeassistant_version"],
        )
        closure["t1_file_write"] = True
        write_private(
            root / "staging.json",
            {"root": staging_root, "hashes": source_hashes},
        )

        inventory = snapshot_rollback(transport, staging_root)
        write_private(root / "rollback_inventory.json", inventory)

        write_private(
            root / "authorization_claim.json",
            {
                "authorization_id": AUTHORIZATION,
                "claimed": True,
                "replay_permitted": False,
                "activation_limit": 1,
            },
        )
        claimed = True
        closure["authorization_claimed"] = True
        closure["activation_invoked"] = True

        activate(transport, staging_root)
        closure["services_owner_restart_invoked"] = True

        post = validate_post_activation(
            transport,
            preflight,
            source_hashes,
        )
        write_private(root / "post_activation.json", post)
        closure.update(
            status="PASS",
            host_daemon_active=True,
            manager_ota_enabled=True,
            recovery_required=False,
        )
        return closure
    except StopExecution as error:
        closure["first_failed_operation"] = str(error)
        if (
            claimed
            and transport is not None
            and inventory is not None
            and preflight is not None
        ):
            closure["automatic_a1_rollback_invoked"] = True
            try:
                rollback = rollback_activation(
                    transport,
                    inventory,
                    preflight,
                )
                write_private(root / "rollback_result.json", rollback)
                closure["automatic_a1_rollback_pass"] = True
                closure["recovery_required"] = False
            except Exception as rollback_error:
                closure["automatic_a1_rollback_pass"] = False
                closure["recovery_required"] = True
                closure["rollback_error_type"] = type(rollback_error).__name__
        return closure
    finally:
        if transport is not None:
            try:
                closed = transport.close_epoch()
                closure["ssh_master_cleanup"] = closed.get("session_closed") is True
            except Exception as error:
                closure["ssh_master_cleanup"] = False
                closure["ssh_cleanup_error_type"] = type(error).__name__
                if closure.get("status") == "PASS":
                    closure["status"] = "STOP"
                    closure["first_failed_operation"] = "ssh_master_cleanup_failed"
        write_private(root / "closure.json", closure)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--execute", action="store_true")
    value.add_argument("--expected-commit")
    value.add_argument("--authorization-id")
    value.add_argument("--execution-id")
    value.add_argument("--evidence-root", type=Path)
    value.add_argument("--t1-ssh-target")
    value.add_argument("--known-hosts", type=Path)
    value.add_argument("--expected-host-key-sha256")
    value.add_argument("--confirm", default="")
    return value


def main() -> int:
    args = parser().parse_args()
    required = (
        args.expected_commit,
        args.authorization_id,
        args.execution_id,
        args.evidence_root,
        args.t1_ssh_target,
        args.known_hosts,
        args.expected_host_key_sha256,
    )
    if not args.execute or any(value is None for value in required):
        print(json.dumps({"status": "STOP", "reason": "execution_arguments_missing"}))
        return 2
    try:
        result = execute(args)
    except StopExecution as error:
        result = {
            "schema": SCHEMA,
            "status": "STOP",
            "first_failed_operation": str(error),
            "t1_access": False,
            "activation_invoked": False,
            "replay_permitted": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
