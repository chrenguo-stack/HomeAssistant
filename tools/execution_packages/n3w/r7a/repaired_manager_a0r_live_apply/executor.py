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

REPOSITORY = "chrenguo-stack/HomeAssistant"
RUN_ID = 42480154921
ARTIFACT_ID = 13616844356
ARTIFACT_NAME = "n3w-t1-core-updater-manager-v2-7807271e4c48"
ARTIFACT_DIGEST = (
    "sha256:3c07406cd51258c8ef95f02e1e6cc80d09eb7235c218e7ead74a02a5521442fd"
)
PACKAGE_CONTROL_HEAD = "4c883c02fbf3a64d944548a1dda8c7431d59ae61"
UPDATER_PYZ_SHA256 = (
    "c0461a5097d8af0f8a6e7f3a175b7dadc82b55a436c6c229092262cd35521b44"
)
MANAGER_TAR_SHA256 = (
    "9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67"
)
MANAGER_BUILD_IMAGE_ID = (
    "sha256:b1875c6ed969df108d2df768d61369a0c93956d146f284276b392c686c13a4f9"
)

TARGET_RELATIVE = "infra/n3w-t1/upgrades/manager-7807271e4c48.json"
BASELINE_RELATIVE = (
    "infra/n3w-t1/clean-reference/r7a-repaired-manager-predecessor-bf38-baseline-20261108.json"
)
EXPECTED_PREDECESSOR = "local/greenhouse-manager:fresh-bf38e388497b"
TARGET_MANAGER = "local/greenhouse-manager:fresh-7807271e4c48"
EXPECTED_HOMEASSISTANT = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_BROKER = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_RUNTIME_IDS = {
    "manager": (
        "sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff"
    ),
    "homeassistant": (
        "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
    ),
    "broker": (
        "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"
    ),
}
EXPECTED_IMAGES = {
    "manager": EXPECTED_PREDECESSOR,
    "homeassistant": EXPECTED_HOMEASSISTANT,
    "broker": EXPECTED_BROKER,
}

AUTHORIZATION = "N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01"
CONFIRMATION = "EXECUTE R7A REPAIRED MANAGER A0R LIVE APPLY: YES"
APPLY_CONFIRMATION = "T1_CORE_UPDATER_APPLY"
REMOTE_DIR = "/var/tmp/n3w-r7a-repaired-manager-a0r-20261108-01"

EXPECTED_PACKAGE_FILES = {
    "greenhouse-manager-arm64.tar",
    "manager-target-v2.json",
    "package-binding.json",
    "t1-core-updater.pyz",
    "upgrade-baseline-a.json",
}

UPDATER_STATE_ROOT = "/var/lib/n3w-t1-core-updater"
UPDATER_STATE_FILES = {
    "current": (
        "upgrade.json",
        "gh.n3w-t1-core-updater-transaction/2",
    ),
    "legacy": (
        "manager-upgrade.json",
        "gh.n3w-t1-core-updater-transaction/1",
    ),
    "ha_usb": (
        "homeassistant-usb-upgrade.json",
        "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1",
    ),
}
TERMINAL_TRANSACTION_STATUS = {"COMMITTED", "ROLLED_BACK"}


class StopExecution(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def load_ssh_transport() -> type:
    if (
        SSH_TRANSPORT_PATH.is_symlink()
        or not SSH_TRANSPORT_PATH.is_file()
        or git_text("hash-object", str(SSH_TRANSPORT_PATH))
        != "dec4c9159195e2008094d94fef3fc76c4b977e46"
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


def validate_local_source(expected_commit: str, *, require_live: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
        raise StopExecution("expected_package_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")

    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "gh.n3w-t1-r7a-repaired-manager-a0r-live-execution-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("authorization_id") != AUTHORIZATION:
        raise StopExecution("manifest_authorization_mismatch")
    authority = manifest.get("package_authority")
    if (
        not isinstance(authority, dict)
        or authority.get("artifact_id") != ARTIFACT_ID
        or authority.get("artifact_digest") != ARTIFACT_DIGEST
        or authority.get("package_control_head") != PACKAGE_CONTROL_HEAD
    ):
        raise StopExecution("manifest_package_authority_mismatch")
    if require_live and manifest.get("live_execution_authorized") is not True:
        raise StopExecution("live_execution_not_authorized")
    return manifest


def verify_github_artifact(download_root: Path) -> tuple[Path, dict[str, Any]]:
    metadata_result = run_local(
        [
            "gh",
            "api",
            f"repos/{REPOSITORY}/actions/artifacts/{ARTIFACT_ID}",
        ],
        timeout=60,
    )
    try:
        metadata = json.loads(metadata_result.stdout)
    except json.JSONDecodeError as error:
        raise StopExecution("artifact_metadata_invalid") from error
    if (
        metadata.get("id") != ARTIFACT_ID
        or metadata.get("name") != ARTIFACT_NAME
        or metadata.get("digest") != ARTIFACT_DIGEST
        or metadata.get("expired") is not False
        or metadata.get("workflow_run", {}).get("id") != RUN_ID
        or metadata.get("workflow_run", {}).get("head_sha") != PACKAGE_CONTROL_HEAD
    ):
        raise StopExecution("artifact_metadata_mismatch")

    package = download_root / "package"
    package.mkdir()
    run_local(
        [
            "gh",
            "run",
            "download",
            str(RUN_ID),
            "-R",
            REPOSITORY,
            "-n",
            ARTIFACT_NAME,
            "-D",
            str(package),
        ],
        timeout=900,
    )
    if {item.name for item in package.iterdir()} != EXPECTED_PACKAGE_FILES:
        raise StopExecution("package_file_set_mismatch")

    tar = package / "greenhouse-manager-arm64.tar"
    pyz = package / "t1-core-updater.pyz"
    if sha256_file(tar) != MANAGER_TAR_SHA256:
        raise StopExecution("manager_tar_sha256_mismatch")
    if sha256_file(pyz) != UPDATER_PYZ_SHA256:
        raise StopExecution("updater_pyz_sha256_mismatch")

    target = read_json(package / "manager-target-v2.json")
    baseline = read_json(package / "upgrade-baseline-a.json")
    binding = read_json(package / "package-binding.json")
    if canonical(target) != canonical(read_json(REPO_ROOT / TARGET_RELATIVE)):
        raise StopExecution("package_target_repo_mismatch")
    if canonical(baseline) != canonical(read_json(REPO_ROOT / BASELINE_RELATIVE)):
        raise StopExecution("package_baseline_repo_mismatch")
    if (
        target.get("expected_predecessor_image_ref") != EXPECTED_PREDECESSOR
        or target.get("target_image_ref") != TARGET_MANAGER
        or target.get("target_archive_sha256") != MANAGER_TAR_SHA256
        or target.get("rollback_compatible") is not True
    ):
        raise StopExecution("target_contract_mismatch")
    if (
        binding.get("control_plane_head") != PACKAGE_CONTROL_HEAD
        or binding.get("upstream_artifact_id") != 13615963302
        or binding.get("manager_image") != TARGET_MANAGER
        or binding.get("manager_build_image_id") != MANAGER_BUILD_IMAGE_ID
        or binding.get("manager_tar_sha256") != MANAGER_TAR_SHA256
        or binding.get("updater_pyz_sha256") != UPDATER_PYZ_SHA256
        or binding.get("manager_rebuilt") is not False
        or binding.get("homeassistant_included") is not False
        or binding.get("broker_included") is not False
        or binding.get("t1_mutation") is not False
    ):
        raise StopExecution("package_binding_mismatch")
    return package, {
        "metadata": metadata,
        "target": target,
        "baseline": baseline,
        "binding": binding,
    }


def parse_systemd_show(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in payload.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def remote_exists(transport: Any, path: str, kind: str = "-e") -> bool:
    result = transport.run_remote(["test", kind, path], check=False, timeout=30)
    return result.returncode == 0


def docker_container(transport: Any, image: str) -> dict[str, Any]:
    ids = [
        line.strip()
        for line in transport.run_remote(
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
            transport.run_remote(
                ["docker", "inspect", ids[0]],
                timeout=60,
            ).stdout
        )
    except json.JSONDecodeError as error:
        raise StopExecution("container_inspect_json_invalid") from error
    if not isinstance(document, list) or len(document) != 1:
        raise StopExecution("container_inspect_shape_invalid")
    item = document[0]
    if not isinstance(item, dict):
        raise StopExecution("container_inspect_shape_invalid")
    return item


def usb_like_disk_count(transport: Any) -> int:
    raw = transport.run_remote(
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


def collect_readonly_preflight(transport: Any) -> dict[str, Any]:
    if transport.run_remote(["uname", "-m"], timeout=30).stdout.strip() != "aarch64":
        raise StopExecution("host_architecture_invalid")
    system_state = transport.run_remote(
        ["systemctl", "is-system-running"],
        check=False,
        timeout=30,
    ).stdout.strip()
    if system_state != "running":
        raise StopExecution("host_system_state_invalid")

    containers = {
        name: docker_container(transport, image)
        for name, image in EXPECTED_IMAGES.items()
    }
    for name, document in containers.items():
        if (
            document.get("Config", {}).get("Image") != EXPECTED_IMAGES[name]
            or document.get("Image") != EXPECTED_RUNTIME_IDS[name]
            or document.get("RestartCount") != 0
            or document.get("State", {}).get("Status") != "running"
        ):
            raise StopExecution(f"{name}_runtime_identity_invalid")

    manager = containers["manager"]
    mounts = manager.get("Mounts") or []
    env = manager.get("Config", {}).get("Env") or []
    if manager.get("Config", {}).get("User") != "999:999":
        raise StopExecution("manager_uid_gid_invalid")
    if any(
        item.get("Source") in {"/var/run/docker.sock", "/run/docker.sock"}
        or item.get("Destination") in {"/var/run/docker.sock", "/run/docker.sock"}
        for item in mounts
    ):
        raise StopExecution("manager_docker_socket_present")
    if any(item.get("Destination") == "/run/n3w/t1-ota" for item in mounts):
        raise StopExecution("manager_ota_mount_already_present")
    if any(
        isinstance(item, str) and item.startswith("GH_N3W_T1_OTA_")
        for item in env
    ):
        raise StopExecution("manager_ota_env_already_present")

    ota_unit = parse_systemd_show(
        transport.run_remote(
            [
                "systemctl",
                "show",
                "n3w-t1-ha-ota.service",
                "--property=LoadState",
                "--property=ActiveState",
                "--no-pager",
            ],
            check=False,
            timeout=30,
        ).stdout
    )
    if ota_unit.get("LoadState") != "not-found":
        raise StopExecution("r7a_host_service_already_deployed")

    if (
        remote_exists(transport, "/run/n3w-t1-ota", "-d")
        or remote_exists(transport, "/run/n3w-t1-ota/ha-ota.sock", "-S")
        or remote_exists(transport, "/etc/n3wfc4/ha-ota-activation.env", "-f")
        or remote_exists(
            transport,
            "/etc/n3w-t1-ota/approved-homeassistant.json",
            "-f",
        )
    ):
        raise StopExecution("r7a_activation_residue_present")

    usb_count = usb_like_disk_count(transport)
    if usb_count != 0:
        raise StopExecution("usb_like_disk_present")

    return {
        "architecture": "aarch64",
        "system_state": system_state,
        "manager_image": EXPECTED_PREDECESSOR,
        "homeassistant_image": EXPECTED_HOMEASSISTANT,
        "broker_image": EXPECTED_BROKER,
        "manager_uid_gid": "999:999",
        "manager_ota_enabled": False,
        "r7a_host_service_load_state": "not-found",
        "usb_like_disk_count": usb_count,
    }


def read_remote_private_json(
    transport: Any,
    path: str,
    *,
    schema: str,
) -> dict[str, Any] | None:
    if transport.run_remote(
        ["test", "-L", path],
        check=False,
        timeout=30,
    ).returncode == 0:
        raise StopExecution("updater_state_symlink")
    if transport.run_remote(
        ["test", "-e", path],
        check=False,
        timeout=30,
    ).returncode != 0:
        return None
    metadata = transport.run_remote(
        ["stat", "-c", "%U:%G:%a:%F", path],
        timeout=30,
    ).stdout.strip()
    if metadata != "root:root:600:regular file":
        raise StopExecution("updater_state_metadata_invalid")
    try:
        document = json.loads(
            transport.run_remote(
                ["cat", path],
                timeout=30,
            ).stdout
        )
    except json.JSONDecodeError as error:
        raise StopExecution("updater_state_json_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != schema:
        raise StopExecution("updater_state_schema_invalid")
    return document


def collect_updater_state_readonly(transport: Any) -> dict[str, Any]:
    if transport.run_remote(
        ["test", "-L", UPDATER_STATE_ROOT],
        check=False,
        timeout=30,
    ).returncode == 0:
        raise StopExecution("updater_state_root_symlink")
    metadata = transport.run_remote(
        ["stat", "-c", "%U:%G:%a:%F", UPDATER_STATE_ROOT],
        timeout=30,
    ).stdout.strip()
    if metadata != "root:root:700:directory":
        raise StopExecution("updater_state_root_invalid")

    observed: dict[str, Any] = {}
    for label, (name, schema) in UPDATER_STATE_FILES.items():
        document = read_remote_private_json(
            transport,
            f"{UPDATER_STATE_ROOT}/{name}",
            schema=schema,
        )
        observed[label] = document

    current = observed["current"]
    legacy = observed["legacy"]
    ha_usb = observed["ha_usb"]
    if (
        isinstance(current, dict)
        and current.get("status") not in TERMINAL_TRANSACTION_STATUS
    ):
        raise StopExecution("updater_recovery_required")
    if (
        isinstance(legacy, dict)
        and legacy.get("status") not in TERMINAL_TRANSACTION_STATUS
    ):
        raise StopExecution("legacy_updater_recovery_required")
    if ha_usb is not None:
        raise StopExecution("ha_usb_successor_state_present")

    return {
        "recovery_required": False,
        "current_transaction": (
            {
                "component": current.get("component"),
                "status": current.get("status"),
                "phase": current.get("phase"),
            }
            if isinstance(current, dict)
            else None
        ),
        "legacy_transaction": (
            {
                "status": legacy.get("status"),
                "phase": legacy.get("phase"),
            }
            if isinstance(legacy, dict)
            else None
        ),
        "ha_usb_transaction_present": False,
    }


def stage_package(transport: Any, package: Path) -> dict[str, str]:
    local_hashes = {
        name: sha256_file(package / name)
        for name in sorted(EXPECTED_PACKAGE_FILES)
    }
    present = transport.run_remote(
        ["test", "-e", REMOTE_DIR],
        check=False,
        timeout=30,
    ).returncode == 0
    if not present:
        transport.run_remote(
            ["install", "-d", "-m", "0700", "-o", "root", "-g", "root", REMOTE_DIR],
            timeout=60,
        )
        for name in sorted(EXPECTED_PACKAGE_FILES):
            transport.scp_to(package / name, f"{REMOTE_DIR}/{name}", timeout=900)
    metadata = transport.run_remote(
        ["stat", "-c", "%U:%G:%a:%F", REMOTE_DIR],
        timeout=30,
    ).stdout.strip()
    if metadata != "root:root:700:directory":
        raise StopExecution("remote_staging_metadata_invalid")

    entries = {
        line.strip()
        for line in transport.run_remote(
            [
                "find",
                REMOTE_DIR,
                "-mindepth",
                "1",
                "-maxdepth",
                "1",
                "-printf",
                "%f\\n",
            ],
            timeout=30,
        ).stdout.splitlines()
        if line.strip()
    }
    if entries != EXPECTED_PACKAGE_FILES:
        raise StopExecution("remote_staging_file_set_mismatch")

    remote_hashes: dict[str, str] = {}
    for name in sorted(EXPECTED_PACKAGE_FILES):
        remote_path = f"{REMOTE_DIR}/{name}"
        if transport.run_remote(
            ["test", "-L", remote_path],
            check=False,
            timeout=30,
        ).returncode == 0:
            raise StopExecution("remote_staging_symlink")
        if transport.run_remote(
            ["test", "-f", remote_path],
            check=False,
            timeout=30,
        ).returncode != 0:
            raise StopExecution("remote_staging_file_invalid")
        result = transport.run_remote(
            ["sha256sum", remote_path],
            timeout=120,
        )
        parts = result.stdout.strip().split()
        if len(parts) != 2:
            raise StopExecution("remote_sha256_output_invalid")
        remote_hashes[name] = parts[0]
    if remote_hashes != local_hashes:
        raise StopExecution("remote_package_sha256_mismatch")
    return local_hashes


def updater_command(
    transport: Any,
    args: list[str],
    *,
    timeout: int,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return transport.run_remote(
        [
            "python3",
            "-B",
            f"{REMOTE_DIR}/t1-core-updater.pyz",
            *args,
        ],
        timeout=timeout,
        check=check,
    )


def parse_updater(result: subprocess.CompletedProcess[str], operation: str) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise StopExecution(f"{operation}_json_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution(f"{operation}_json_shape_invalid")
    return value


def validate_plan(document: dict[str, Any]) -> None:
    current = document.get("current")
    target = document.get("target")
    if (
        document.get("status") != "PASS"
        or document.get("operation") != "plan"
        or document.get("component") != "manager"
        or document.get("mutation") is not False
        or document.get("rollback_available") is not True
        or document.get("target_archive_verified") is not True
        or not isinstance(current, dict)
        or current.get("image") != EXPECTED_PREDECESSOR
        or not isinstance(target, dict)
        or target.get("target_image_ref") != TARGET_MANAGER
    ):
        raise StopExecution("pre_apply_plan_invalid")


def validate_post_apply(
    transport: Any,
    status: dict[str, Any],
    inspect: dict[str, Any],
) -> None:
    transaction = status.get("transaction")
    snapshot = inspect.get("snapshot")
    if (
        status.get("status") != "PASS"
        or status.get("recovery_required") is not False
        or not isinstance(transaction, dict)
        or transaction.get("status") != "COMMITTED"
        or transaction.get("phase") != "COMMITTED"
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256")
        != hashlib.sha256(AUTHORIZATION.encode("utf-8")).hexdigest()
        or transaction.get("target", {}).get("target_image_ref") != TARGET_MANAGER
        or inspect.get("status") != "PASS"
        or inspect.get("component") != "manager"
        or not isinstance(snapshot, dict)
        or snapshot.get("image_bindings", {}).get("manager") != TARGET_MANAGER
        or snapshot.get("image_bindings", {}).get("homeassistant")
        != EXPECTED_HOMEASSISTANT
        or snapshot.get("image_bindings", {}).get("broker") != EXPECTED_BROKER
    ):
        raise StopExecution("post_apply_updater_state_invalid")

    target_runtime_id = transaction.get("target_runtime_image_id")
    runtime = snapshot.get("runtime")
    manager_runtime = runtime.get("manager") if isinstance(runtime, dict) else None
    if (
        not isinstance(target_runtime_id, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", target_runtime_id) is None
        or not isinstance(manager_runtime, dict)
        or manager_runtime.get("image_ref") != TARGET_MANAGER
        or manager_runtime.get("image_id") != target_runtime_id
    ):
        raise StopExecution("post_apply_manager_runtime_authority_invalid")

    target_doc = docker_container(transport, TARGET_MANAGER)
    if (
        target_doc.get("Image") != target_runtime_id
        or target_doc.get("Config", {}).get("User") != "999:999"
        or target_doc.get("RestartCount") != 0
        or target_doc.get("State", {}).get("Status") != "running"
    ):
        raise StopExecution("post_apply_manager_runtime_invalid")
    env = target_doc.get("Config", {}).get("Env") or []
    mounts = target_doc.get("Mounts") or []
    if any(
        isinstance(item, str) and item.startswith("GH_N3W_T1_OTA_")
        for item in env
    ):
        raise StopExecution("post_apply_ota_unexpectedly_enabled")
    if any(item.get("Destination") == "/run/n3w/t1-ota" for item in mounts):
        raise StopExecution("post_apply_ota_mount_unexpected")

    if docker_container(transport, EXPECTED_HOMEASSISTANT).get("Image") != (
        EXPECTED_RUNTIME_IDS["homeassistant"]
    ):
        raise StopExecution("post_apply_homeassistant_drift")
    if docker_container(transport, EXPECTED_BROKER).get("Image") != (
        EXPECTED_RUNTIME_IDS["broker"]
    ):
        raise StopExecution("post_apply_broker_drift")
    if usb_like_disk_count(transport) != 0:
        raise StopExecution("post_apply_usb_like_disk_present")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION:
        raise StopExecution("authorization_id_mismatch")
    if args.confirm != CONFIRMATION:
        raise StopExecution("execution_confirmation_mismatch")

    manifest = validate_local_source(
        args.expected_package_commit,
        require_live=True,
    )
    root = prepare_evidence_root(args.evidence_root)
    closure: dict[str, Any] = {
        "schema": "gh.n3w-t1-r7a-repaired-manager-a0r-live-execution-result/1",
        "status": "STOP",
        "execution_id": args.execution_id,
        "authorization_id": AUTHORIZATION,
        "live_execution_authorized": manifest["live_execution_authorized"],
        "package_artifact_id": ARTIFACT_ID,
        "t1_access": False,
        "t1_file_write": False,
        "apply_invoked": False,
        "second_apply_invoked": False,
        "executor_explicit_rollback_invoked": False,
        "updater_internal_failure_rollback_possible": True,
        "usb_mutation": False,
        "host_daemon_activation": False,
        "board_access": False,
        "first_failed_operation": None,
    }

    work = Path(tempfile.mkdtemp(prefix="n3w-r7a-a0-package."))
    transport = None
    try:
        package, package_info = verify_github_artifact(work)
        write_private(root / "package_authority.json", package_info)

        transport_type = load_ssh_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        closure["t1_access"] = True

        preflight = collect_readonly_preflight(transport)
        write_private(root / "preflight.json", preflight)

        updater_state = collect_updater_state_readonly(transport)
        write_private(root / "pre_updater_state.json", updater_state)

        hashes = stage_package(transport, package)
        closure["t1_file_write"] = True
        write_private(root / "remote_package_hashes.json", hashes)

        status = parse_updater(
            updater_command(transport, ["status"], timeout=120),
            "status",
        )
        if status.get("status") != "PASS" or status.get("recovery_required") is not False:
            raise StopExecution("pre_apply_status_invalid")
        write_private(root / "pre_status.json", status)

        inspect = parse_updater(
            updater_command(
                transport,
                ["inspect", "--component", "manager"],
                timeout=180,
            ),
            "inspect",
        )
        write_private(root / "pre_inspect.json", inspect)
        if inspect.get("snapshot", {}).get("image_bindings", {}) != EXPECTED_IMAGES:
            raise StopExecution("pre_apply_binding_drift")

        plan_args = [
            "plan",
            "--target-manifest",
            f"{REMOTE_DIR}/manager-target-v2.json",
            "--baseline-manifest",
            f"{REMOTE_DIR}/upgrade-baseline-a.json",
            "--manager-tar",
            f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
        ]
        plan = parse_updater(
            updater_command(transport, plan_args, timeout=300),
            "plan",
        )
        validate_plan(plan)
        write_private(root / "pre_plan.json", plan)

        closure["apply_invoked"] = True
        write_private(
            root / "authorization_claim.json",
            {
                "authorization_id": AUTHORIZATION,
                "claimed": True,
                "replay_permitted": False,
                "apply_limit": 1,
            },
        )
        apply_args = [
            "apply",
            "--target-manifest",
            f"{REMOTE_DIR}/manager-target-v2.json",
            "--baseline-manifest",
            f"{REMOTE_DIR}/upgrade-baseline-a.json",
            "--manager-tar",
            f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
            "--authorization-id",
            AUTHORIZATION,
            "--confirmation",
            APPLY_CONFIRMATION,
        ]
        apply_result = updater_command(
            transport,
            apply_args,
            timeout=900,
            check=False,
        )
        apply_doc: dict[str, Any] | None = None
        try:
            apply_doc = parse_updater(apply_result, "apply")
            write_private(root / "apply.json", apply_doc)
        except StopExecution:
            write_private(
                root / "apply_transport.json",
                {
                    "returncode": apply_result.returncode,
                    "stdout_sha256": hashlib.sha256(
                        apply_result.stdout.encode("utf-8")
                    ).hexdigest(),
                    "stderr_sha256": hashlib.sha256(
                        apply_result.stderr.encode("utf-8")
                    ).hexdigest(),
                },
            )

        post_status_result = updater_command(
            transport,
            ["status"],
            timeout=120,
            check=False,
        )
        post_inspect_result = updater_command(
            transport,
            ["inspect", "--component", "manager"],
            timeout=180,
            check=False,
        )
        post_status = parse_updater(post_status_result, "post_status")
        post_inspect = parse_updater(post_inspect_result, "post_inspect")
        write_private(root / "post_status.json", post_status)
        write_private(root / "post_inspect.json", post_inspect)

        if (
            apply_result.returncode != 0
            or not isinstance(apply_doc, dict)
            or apply_doc.get("status") != "PASS"
            or apply_doc.get("operation") != "apply"
            or apply_doc.get("transaction_status") != "COMMITTED"
            or apply_doc.get("authorization_consumed") is not True
        ):
            raise StopExecution("apply_not_committed")

        validate_post_apply(transport, post_status, post_inspect)

        closure["status"] = "PASS"
        closure["transaction_status"] = "COMMITTED"
        closure["manager_after"] = TARGET_MANAGER
        closure["recovery_required"] = False
        return closure
    except StopExecution as error:
        closure["first_failed_operation"] = str(error)
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
    value.add_argument("--expected-package-commit")
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
        args.expected_package_commit,
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
            "schema": "gh.n3w-t1-r7a-repaired-manager-a0r-live-execution-result/1",
            "status": "STOP",
            "first_failed_operation": str(error),
            "t1_access": False,
            "apply_invoked": False,
            "replay_permitted": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
