#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SCHEMA = "gh.n3w.r10-t1-candidate-upgrade-execution/1"
PACKAGE_SCHEMA = "gh.n3w.r10-t1-candidate-upgrade-package/1"
UPGRADE_SCHEMA = "gh.n3w.r10-t1-candidate-upgrade-transaction/1"

PREDECESSOR_SOURCE = "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6"
TARGET_SOURCE = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
PREDECESSOR_MANAGER_IMAGE = "local/greenhouse-manager:fresh-03dab2bd04e7"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"

CONFIRMATION = "APPLY R10 T1 CANDIDATE UPGRADE: YES"
AUTH_PREFIX = "N3W_R10_T1_CANDIDATE_UPGRADE_"

PROVISION_ROOT = Path("/var/lib/n3w-t1-provisioning")
F4_TRANSACTION = PROVISION_ROOT / "F4_ACTIVATION_TRANSACTION.json"
UPGRADE_TRANSACTION = PROVISION_ROOT / "R10_CANDIDATE_UPGRADE_TRANSACTION.json"
UPGRADE_WORK_PARENT = Path("/var/lib/n3w-r10-candidate-upgrade")
MANAGER_ROOT = Path("/var/lib/greenhouse-manager")

SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
REGISTRATION_UNIT = "n3wfc4-registration-ingress-guard.service"

COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
REGISTRATION_TLS_ROOT = Path("/etc/n3wfc4/registration-tls")
TRUSTED_LAN_RUNTIME = Path("/run/n3wfc4-trusted-lan")

REGISTRATION_CHAIN = "N3WFC4-REGISTRATION-INGRESS"
REGISTRATION_COMMENT = "n3wfc4-registration-ingress-v1"
REGISTRATION_PORTS = (("tcp", 47110), ("udp", 47111), ("tcp", 47112))

F4_CHANGED_TARGETS = {
    "/etc/n3wfc4/docker-compose.yml",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    (
        "/etc/NetworkManager/dispatcher.d/"
        "90-n3wfc4-broker-ingress-guard"
    ),
}

F4_HISTORICAL_PROTECTED_FIELDS = (
    "schema",
    "authorization_id",
    "release_id",
    "host_instance_id",
    "system_id",
    "system_id_sha256",
    "package_source_head",
    "package_manifest_sha256",
    "runtime_acceptance_report_sha256",
    "certificate_status_sha256",
)


class UpgradeError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def run(
    argv: Iterable[str],
    *,
    input_text: str | None = None,
    timeout: int = 180,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    command = tuple(str(item) for item in argv)
    try:
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeError(
            f"command_execution_failed:{Path(command[0]).name}"
        ) from error
    if result.returncode not in allowed:
        raise UpgradeError(
            f"command_failed:{Path(command[0]).name}:{result.returncode}:"
            + (result.stderr.strip() or result.stdout.strip())[:240]
        )
    return result.stdout


def require_root() -> None:
    if os.geteuid() != 0:
        raise UpgradeError("root_required")


def file_binding(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UpgradeError(f"file_invalid:{path}")
    metadata = path.stat()
    return {
        "sha256": sha256_file(path),
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int,
    uid: int,
    gid: int,
    exclusive: bool = False,
) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise UpgradeError(f"parent_invalid:{parent}")
    if exclusive:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(path, flags, mode)
        temporary = None
    else:
        temporary = parent / (
            f".{path.name}.r10-upgrade-{os.getpid()}"
        )
        if temporary.exists() or temporary.is_symlink():
            raise UpgradeError("temporary_path_collision")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, mode)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        target = path if exclusive else temporary
        assert target is not None
        os.chmod(target, mode)
        os.chown(target, uid, gid)
        if not exclusive:
            os.replace(target, path)
            replaced = True
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if (
            not exclusive
            and temporary is not None
            and not replaced
            and temporary.exists()
        ):
            temporary.unlink(missing_ok=True)


def atomic_write_json(
    path: Path,
    document: dict[str, Any],
    *,
    exclusive: bool = False,
) -> None:
    atomic_write_bytes(
        path,
        (
            json.dumps(document, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8"),
        mode=0o600,
        uid=0,
        gid=0,
        exclusive=exclusive,
    )


def read_private_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UpgradeError(f"private_record_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise UpgradeError(f"private_record_metadata_invalid:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpgradeError(
            f"private_record_json_invalid:{path.name}"
        ) from error
    if not isinstance(value, dict):
        raise UpgradeError(f"private_record_shape_invalid:{path.name}")
    return value


def safe_package_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != relative
    ):
        raise UpgradeError("package_path_invalid")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise UpgradeError(f"package_symlink:{relative}")
    if not current.is_file():
        raise UpgradeError(f"package_file_missing:{relative}")
    return current


def validate_package(
    package_root: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    root = package_root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise UpgradeError("package_root_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256):
        raise UpgradeError("manifest_sha256_invalid")
    manifest_path = root / "manifest.json"
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or sha256_file(manifest_path) != expected_manifest_sha256
    ):
        raise UpgradeError("manifest_binding_invalid")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpgradeError("manifest_json_invalid") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != PACKAGE_SCHEMA
        or manifest.get("predecessor_source") != PREDECESSOR_SOURCE
        or manifest.get("target_source") != TARGET_SOURCE
        or manifest.get("predecessor_manager_image")
        != PREDECESSOR_MANAGER_IMAGE
        or manifest.get("target_manager_image") != TARGET_MANAGER_IMAGE
    ):
        raise UpgradeError("manifest_contract_invalid")
    policy = manifest.get("policy")
    if (
        not isinstance(policy, dict)
        or policy.get("secret_values_included") is not False
        or policy.get("homeassistant_image_included") is not False
        or policy.get("broker_image_included") is not False
        or policy.get("compose_override_allowed") is not False
        or policy.get("force_recreate_allowed") is not False
        or policy.get("t1_access") is not False
        or policy.get("t1_mutation") is not False
        or policy.get("board_access") is not False
    ):
        raise UpgradeError("manifest_policy_invalid")

    manager = manifest.get("manager")
    if not isinstance(manager, dict):
        raise UpgradeError("manager_manifest_invalid")
    manager_path = safe_package_file(
        root,
        str(manager.get("artifact_path", "")),
    )
    if (
        sha256_file(manager_path) != manager.get("tar_sha256")
        or manager_path.stat().st_size
        != manager.get("tar_size_bytes")
        or manager.get("image_id") is None
        or manager.get("platform") != "linux/arm64"
        or manager.get("historical_byte_continuity_claimed") is not False
    ):
        raise UpgradeError("manager_artifact_binding_invalid")

    executor = manifest.get("executor")
    if not isinstance(executor, dict):
        raise UpgradeError("executor_manifest_invalid")
    executor_path = safe_package_file(
        root,
        str(executor.get("artifact_path", "")),
    )
    if (
        sha256_file(executor_path) != executor.get("sha256")
        or executor_path.stat().st_size != executor.get("size")
    ):
        raise UpgradeError("executor_binding_invalid")

    for group_name in ("live_files", "source_overlay"):
        group = manifest.get(group_name)
        if not isinstance(group, dict):
            raise UpgradeError(f"{group_name}_invalid")
        for record in group.values():
            if not isinstance(record, dict):
                raise UpgradeError(f"{group_name}_record_invalid")
            path = safe_package_file(
                root,
                str(record.get("artifact_path", "")),
            )
            if (
                sha256_file(path) != record.get("sha256")
                or path.stat().st_size != record.get("size")
            ):
                raise UpgradeError(
                    f"package_member_binding_invalid:"
                    f"{record.get('artifact_path')}"
                )
    return manifest


def parse_env(path: Path) -> tuple[list[str], dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise UpgradeError("compose_env_invalid")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise UpgradeError("compose_env_read_failed") from error
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise UpgradeError("compose_env_line_invalid")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise UpgradeError("compose_env_key_invalid")
        values[key] = value
    return lines, values


def rewrite_manager_image(
    path: Path,
    *,
    expected: str,
    target: str,
) -> None:
    lines, values = parse_env(path)
    if values.get("GH_MANAGER_IMAGE") != expected:
        raise UpgradeError("compose_env_manager_image_drift")
    count = sum(
        1 for line in lines if line.startswith("GH_MANAGER_IMAGE=")
    )
    if count != 1:
        raise UpgradeError("compose_env_manager_image_count_invalid")
    replaced = [
        (
            f"GH_MANAGER_IMAGE={target}"
            if line.startswith("GH_MANAGER_IMAGE=")
            else line
        )
        for line in lines
    ]
    metadata = path.stat()
    atomic_write_bytes(
        path,
        ("\n".join(replaced) + "\n").encode("utf-8"),
        mode=stat.S_IMODE(metadata.st_mode),
        uid=metadata.st_uid,
        gid=metadata.st_gid,
    )


def container(service: str, *, running_only: bool = True) -> dict[str, Any]:
    command = [
        "docker",
        "ps" if running_only else "ps",
    ]
    if not running_only:
        command.append("-a")
    command.extend(
        [
            "--filter",
            "label=com.docker.compose.project=n3wfc4",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "-q",
        ]
    )
    identifiers = [
        line.strip()
        for line in run(command, timeout=30).splitlines()
        if line.strip()
    ]
    if len(identifiers) != 1:
        raise UpgradeError(f"container_not_unique:{service}")
    try:
        docs = json.loads(
            run(("docker", "inspect", identifiers[0]), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise UpgradeError(f"container_inspect_invalid:{service}") from error
    if (
        not isinstance(docs, list)
        or len(docs) != 1
        or not isinstance(docs[0], dict)
    ):
        raise UpgradeError(f"container_inspect_invalid:{service}")
    return docs[0]


def container_public_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    config = document.get("Config")
    state = document.get("State")
    if not isinstance(config, dict) or not isinstance(state, dict):
        raise UpgradeError("container_snapshot_invalid")
    return {
        "id": str(document.get("Id") or ""),
        "image_id": str(document.get("Image") or ""),
        "image": str(config.get("Image") or ""),
        "started_at": str(state.get("StartedAt") or ""),
        "restart_count": int(document.get("RestartCount") or 0),
        "running": state.get("Running") is True,
    }


def service_state(unit: str) -> dict[str, str]:
    active = run(
        ("systemctl", "is-active", unit),
        timeout=20,
        allowed=frozenset({0, 3, 4}),
    ).strip()
    enabled = run(
        ("systemctl", "is-enabled", unit),
        timeout=20,
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()
    load = run(
        ("systemctl", "show", unit, "-p", "LoadState", "--value"),
        timeout=20,
        allowed=frozenset({0, 1}),
    ).strip()
    return {
        "active": active or "inactive",
        "enabled": enabled or "unknown",
        "load": load or "unknown",
    }


def listener_count(protocol: str, port: int) -> int:
    flag = "-lnt" if protocol == "tcp" else "-lnu"
    output = run(("ss", "-H", flag), timeout=20)
    suffix = f":{port}"
    count = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[3].endswith(suffix):
            count += 1
    return count


def database_state() -> dict[str, Any]:
    path = MANAGER_ROOT / "manager/manager-state.sqlite3"
    if path.is_symlink() or not path.is_file():
        raise UpgradeError("manager_database_invalid")
    try:
        con = sqlite3.connect(
            "file:" + str(path) + "?mode=ro",
            uri=True,
            timeout=5,
        )
        con.execute("PRAGMA query_only=ON")
        integrity_row = con.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "invalid"
        tables = {
            str(row[0])
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        current = int(
            con.execute(
                "SELECT COUNT(*) FROM registrations "
                "WHERE retired_at IS NULL"
            ).fetchone()[0]
        )
        first_present = "first_registration_attempts" in tables
        unresolved: int | None = None
        if first_present:
            unresolved = int(
                con.execute(
                    "SELECT COUNT(*) FROM first_registration_attempts "
                    "WHERE state='ACTIVE' OR "
                    "(state IN ('EXPIRED','RESTART_INVALIDATED') "
                    "AND cleanup_state!='COMPLETE')"
                ).fetchone()[0]
            )
        con.close()
    except sqlite3.Error as error:
        raise UpgradeError("manager_database_read_failed") from error
    return {
        "integrity": integrity,
        "current_registration_count": current,
        "first_registration_table_present": first_present,
        "unresolved_first_registration": unresolved,
    }


def pairing_window_closed(manager_id: str) -> bool:
    output = run(
        (
            "docker",
            "exec",
            manager_id,
            "greenhouse-manager-pairing",
            "window-status",
        ),
        timeout=30,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(value, dict)
        and value.get("accepted") is True
        and value.get("pairing_window_state") == "CLOSED"
        and value.get("raw_locator_in_output") is False
    )


def f4_services_eligibility() -> None:
    output = run(
        (
            "/usr/local/sbin/n3w-t1-f4-activation",
            "eligibility",
            "--phase",
            "services",
        ),
        timeout=120,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise UpgradeError("f4_eligibility_json_invalid") from error
    if (
        not isinstance(value, dict)
        or value.get("status") != "PASS"
        or value.get("activation_eligible") is not True
        or value.get("eligibility_phase") != "services"
    ):
        raise UpgradeError("f4_services_eligibility_failed")


def tree_size(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        raise UpgradeError(f"state_root_invalid:{path}")
    total = 0
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        for name in dirs:
            item = root_path / name
            if item.is_symlink():
                raise UpgradeError("state_symlink_forbidden")
        for name in files:
            item = root_path / name
            if item.is_symlink() or not item.is_file():
                raise UpgradeError("state_special_file_forbidden")
            total += item.stat().st_size
    return total


def registration_firewall_absent() -> bool:
    output = run(("iptables-save", "-t", "filter"), timeout=20)
    return (
        REGISTRATION_CHAIN not in output
        and REGISTRATION_COMMENT not in output
    )


def expected_predecessor_binding(record: dict[str, Any]) -> dict[str, Any]:
    predecessor = record.get("predecessor")
    if not isinstance(predecessor, dict):
        raise UpgradeError("predecessor_binding_missing")
    return predecessor


def verify_predecessor_file(record: dict[str, Any]) -> None:
    target = Path(str(record["target"]))
    predecessor = expected_predecessor_binding(record)
    if target.is_symlink() or not target.is_file():
        raise UpgradeError(f"predecessor_file_missing:{target}")
    binding = file_binding(target)
    if (
        binding["sha256"] != predecessor.get("sha256")
        or binding["size"] != predecessor.get("size")
        or binding["mode"] != int(record["mode"])
        or binding["uid"] != 0
        or binding["gid"] != 0
    ):
        raise UpgradeError(f"predecessor_file_drift:{target}")


def verify_prestate(
    package_root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if (
        UPGRADE_TRANSACTION.exists()
        or UPGRADE_TRANSACTION.is_symlink()
        or UPGRADE_WORK_PARENT.exists()
        or UPGRADE_WORK_PARENT.is_symlink()
    ):
        raise UpgradeError("upgrade_predecessor_residue")
    if (
        REGISTRATION_TLS_ROOT.exists()
        or REGISTRATION_TLS_ROOT.is_symlink()
        or TRUSTED_LAN_RUNTIME.exists()
        or TRUSTED_LAN_RUNTIME.is_symlink()
    ):
        raise UpgradeError("registration_predecessor_residue")
    registration = service_state(REGISTRATION_UNIT)
    if (
        registration["load"] != "not-found"
        or registration["active"] == "active"
    ):
        raise UpgradeError("registration_unit_predecessor_drift")
    if not registration_firewall_absent():
        raise UpgradeError("registration_firewall_predecessor_drift")

    services = service_state(SERVICES_UNIT)
    broker_service = service_state(BROKER_UNIT)
    if services["active"] != "active" or broker_service["active"] != "active":
        raise UpgradeError("production_service_prestate_invalid")

    broker_doc = container("broker")
    manager_doc = container("manager")
    ha_doc = container("homeassistant")
    snapshots = {
        "broker": container_public_snapshot(broker_doc),
        "manager": container_public_snapshot(manager_doc),
        "homeassistant": container_public_snapshot(ha_doc),
    }
    if snapshots["manager"]["image"] != PREDECESSOR_MANAGER_IMAGE:
        raise UpgradeError("manager_image_predecessor_drift")
    if not all(value["running"] for value in snapshots.values()):
        raise UpgradeError("container_prestate_not_running")

    target_image = run(
        ("docker", "image", "inspect", TARGET_MANAGER_IMAGE),
        timeout=30,
        allowed=frozenset({0, 1}),
    )
    if target_image.strip():
        raise UpgradeError("target_manager_image_preexisting")

    _lines, env = parse_env(COMPOSE_ENV)
    if env.get("GH_MANAGER_IMAGE") != PREDECESSOR_MANAGER_IMAGE:
        raise UpgradeError("compose_env_predecessor_drift")
    system_id = env.get("GH_SYSTEM_ID")
    if not system_id:
        raise UpgradeError("system_id_missing")

    live = manifest["live_files"]
    for record in live.values():
        if record.get("predecessor_present") is True:
            verify_predecessor_file(record)
        else:
            target = Path(str(record["target"]))
            if target.exists() or target.is_symlink():
                raise UpgradeError(f"new_live_file_preexists:{target}")

    for record in manifest["source_overlay"].values():
        target = Path(str(record["target"]))
        predecessor = record.get("predecessor")
        if predecessor is None:
            if target.exists() or target.is_symlink():
                raise UpgradeError(
                    f"new_source_overlay_preexists:{target}"
                )
        else:
            verify_predecessor_file(
                {
                    **record,
                    "predecessor_present": True,
                }
            )

    f4_services_eligibility()
    f4_transaction = read_private_json(F4_TRANSACTION)
    installed = f4_transaction.get("installed_files")
    if not isinstance(installed, dict):
        raise UpgradeError("f4_installed_files_missing")
    for target in F4_CHANGED_TARGETS:
        record = next(
            (
                item
                for item in live.values()
                if item.get("target") == target
            ),
            None,
        )
        if not isinstance(record, dict):
            raise UpgradeError("f4_changed_target_manifest_missing")
        expected = expected_predecessor_binding(record)
        current = installed.get(target)
        if (
            not isinstance(current, dict)
            or current.get("sha256") != expected.get("sha256")
            or current.get("size") != expected.get("size")
        ):
            raise UpgradeError(
                f"f4_predecessor_binding_drift:{target}"
            )

    db = database_state()
    if (
        db["integrity"] != "ok"
        or db["current_registration_count"] != 1
        or db["first_registration_table_present"] is not False
    ):
        raise UpgradeError("database_predecessor_invalid")
    if not pairing_window_closed(str(manager_doc["Id"])):
        raise UpgradeError("pairing_window_not_closed")

    state_bytes = tree_size(MANAGER_ROOT)
    static_bytes = (
        F4_TRANSACTION.stat().st_size
        + COMPOSE_ENV.stat().st_size
        + sum(
            (
                Path(str(record["target"])).stat().st_size
                if Path(str(record["target"])).is_file()
                else 0
            )
            for record in [
                *manifest["live_files"].values(),
                *manifest["source_overlay"].values(),
            ]
        )
    )
    rollback_estimate = state_bytes + static_bytes + 16 * 1024 * 1024
    manager_size = int(manifest["manager"]["image_size_bytes"])
    reserve = int(
        manifest["capacity"]["upgrade_emergency_reserve_bytes"]
    )
    free = shutil.disk_usage("/").free
    required = rollback_estimate + manager_size + reserve
    if free < required:
        raise UpgradeError("upgrade_capacity_insufficient")

    return {
        "broker": snapshots["broker"],
        "manager": snapshots["manager"],
        "homeassistant": snapshots["homeassistant"],
        "system_id": system_id,
        "f4_transaction_sha256": sha256_file(F4_TRANSACTION),
        "f4_installed_files_sha256": canonical_sha256(installed),
        "database": db,
        "manager_root_size_bytes": state_bytes,
        "rollback_estimate_bytes": rollback_estimate,
        "free_bytes": free,
        "required_free_bytes": required,
    }


def valid_authorization_id(value: str) -> bool:
    return (
        value.startswith(AUTH_PREFIX)
        and len(value) <= 200
        and value.replace("_", "").replace("-", "").isalnum()
    )


def claim_upgrade(
    *,
    authorization_id: str,
    manifest_sha256: str,
    package_head: str,
    prestate: dict[str, Any],
) -> dict[str, Any]:
    if not valid_authorization_id(authorization_id):
        raise UpgradeError("authorization_id_invalid")
    if UPGRADE_TRANSACTION.exists() or UPGRADE_TRANSACTION.is_symlink():
        raise UpgradeError("upgrade_authorization_replay_forbidden")
    document = {
        "schema": UPGRADE_SCHEMA,
        "status": "CLAIMED",
        "phase": "CLAIMED",
        "authorization_id": authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "package_manifest_sha256": manifest_sha256,
        "package_head": package_head,
        "predecessor_source": PREDECESSOR_SOURCE,
        "target_source": TARGET_SOURCE,
        "predecessor_f4_transaction_sha256": (
            prestate["f4_transaction_sha256"]
        ),
        "predecessor_f4_installed_files_sha256": (
            prestate["f4_installed_files_sha256"]
        ),
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "current_registration_count": 1,
        "board_access": False,
        "committed": False,
        "rollback_completed": False,
    }
    atomic_write_json(UPGRADE_TRANSACTION, document, exclusive=True)
    return document


def advance_upgrade(phase: str, **fields: Any) -> dict[str, Any]:
    document = read_private_json(UPGRADE_TRANSACTION)
    document.update(fields)
    document["phase"] = phase
    document["status"] = (
        "PASS" if phase == "COMMITTED" else
        "ROLLED_BACK" if phase == "ROLLED_BACK" else
        "FAIL" if phase == "ROLLBACK_FAILED" else
        "CLAIMED"
    )
    atomic_write_json(UPGRADE_TRANSACTION, document)
    return document


def workspace_for(authorization_id: str) -> Path:
    suffix = sha256_bytes(authorization_id.encode("utf-8"))[:16]
    return UPGRADE_WORK_PARENT / suffix


def create_workspace(authorization_id: str) -> Path:
    if UPGRADE_WORK_PARENT.exists() or UPGRADE_WORK_PARENT.is_symlink():
        raise UpgradeError("upgrade_workspace_preexisting")
    UPGRADE_WORK_PARENT.mkdir(mode=0o700)
    workspace = workspace_for(authorization_id)
    workspace.mkdir(mode=0o700)
    return workspace


def backup_file(path: Path, backup_root: Path, key: str) -> dict[str, Any]:
    target = backup_root / key
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise UpgradeError(f"backup_source_invalid:{path}")
        metadata = path.stat()
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)
        return {
            "present": True,
            "path": str(path),
            "backup": target.name,
            "binding": file_binding(path),
            "uid": metadata.st_uid,
            "gid": metadata.st_gid,
            "mode": stat.S_IMODE(metadata.st_mode),
        }
    return {
        "present": False,
        "path": str(path),
        "backup": None,
    }


def static_backup(
    workspace: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    root = workspace / "static"
    root.mkdir(mode=0o700)
    records: dict[str, Any] = {}
    records["f4_transaction"] = backup_file(
        F4_TRANSACTION, root, "f4-transaction.bin"
    )
    records["compose_env"] = backup_file(
        COMPOSE_ENV, root, "docker-compose.env.bin"
    )
    index = 0
    for group_name in ("live_files", "source_overlay"):
        for name, record in manifest[group_name].items():
            records[f"{group_name}:{name}"] = backup_file(
                Path(str(record["target"])),
                root,
                f"file-{index:03d}.bin",
            )
            index += 1
    firewall = run(("iptables-save", "-t", "filter"), timeout=20)
    firewall_path = root / "iptables-filter-prestate.txt"
    firewall_path.write_text(firewall, encoding="utf-8")
    os.chmod(firewall_path, 0o600)
    records["firewall_sha256"] = sha256_file(firewall_path)
    record_path = root / "index.json"
    record_path.write_text(
        json.dumps(records, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(record_path, 0o600)
    return records


def load_target_manager(
    package_root: Path,
    manifest: dict[str, Any],
) -> None:
    manager = manifest["manager"]
    tar_path = safe_package_file(
        package_root,
        str(manager["artifact_path"]),
    )
    run(("docker", "load", "-i", str(tar_path)), timeout=600)
    try:
        value = json.loads(
            run(
                ("docker", "image", "inspect", TARGET_MANAGER_IMAGE),
                timeout=30,
            )
        )
    except json.JSONDecodeError as error:
        raise UpgradeError("target_image_inspect_invalid") from error
    if (
        not isinstance(value, list)
        or len(value) != 1
        or value[0].get("Id") != manager["image_id"]
        or value[0].get("Architecture") != "arm64"
        or value[0].get("Os") != "linux"
    ):
        raise UpgradeError("target_image_binding_invalid")


def generate_registration_tls(
    workspace: Path,
    system_id: str,
) -> Path:
    tls_root = workspace / "registration-tls"
    tls_root.mkdir(mode=0o700)
    system_path = tls_root / "system-id"
    system_path.write_text(system_id + "\n", encoding="utf-8")
    os.chmod(system_path, 0o600)
    script = r"""
from datetime import UTC, datetime
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from greenhouse_manager.bootstrap.fresh_broker import _generate_registration_tls

root=Path("/work")
system_id=(root/"system-id").read_text(encoding="utf-8").strip()
key_bytes, cert_bytes=_generate_registration_tls(
    system_id=system_id,
    now=datetime.now(UTC),
)
(root/"bootstrap.key").write_bytes(key_bytes)
(root/"bootstrap.pem").write_bytes(cert_bytes)
key=serialization.load_pem_private_key(key_bytes,password=None)
cert=x509.load_pem_x509_certificate(cert_bytes)
if (
    key.public_key().public_numbers()
    != cert.public_key().public_numbers()
    or cert.subject != cert.issuer
):
    raise SystemExit(3)
print("REGISTRATION_TLS_GENERATION=PASS")
"""
    run(
        (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            "0:0",
            "--mount",
            f"type=bind,src={tls_root},dst=/work",
            "--entrypoint",
            "python",
            TARGET_MANAGER_IMAGE,
            "-c",
            script,
        ),
        timeout=120,
    )
    key = tls_root / "bootstrap.key"
    cert = tls_root / "bootstrap.pem"
    if (
        key.is_symlink()
        or cert.is_symlink()
        or not key.is_file()
        or not cert.is_file()
        or key.stat().st_size == 0
        or cert.stat().st_size == 0
    ):
        raise UpgradeError("registration_tls_generation_invalid")
    system_path.unlink()
    os.chmod(key, 0o600)
    os.chmod(cert, 0o600)
    return tls_root


def copy_bound_file(
    source: Path,
    target: Path,
    *,
    mode: int,
    uid: int = 0,
    gid: int = 0,
) -> None:
    if source.is_symlink() or not source.is_file():
        raise UpgradeError(f"install_source_invalid:{source}")
    if not target.parent.exists():
        target.parent.mkdir(parents=True, mode=0o755)
    atomic_write_bytes(
        target,
        source.read_bytes(),
        mode=mode,
        uid=uid,
        gid=gid,
    )


def install_runtime_files(
    package_root: Path,
    manifest: dict[str, Any],
) -> None:
    # New guard tools/unit first, so the target dispatcher is never exposed
    # without its target service implementation.
    preferred = (
        "registration_guard",
        "trusted_lan_authority",
        "registration_unit",
        "compose",
        "services_unit",
        "dispatcher",
    )
    live = manifest["live_files"]
    for name in preferred:
        record = live[name]
        source = safe_package_file(
            package_root,
            str(record["artifact_path"]),
        )
        copy_bound_file(
            source,
            Path(str(record["target"])),
            mode=int(record["mode"]),
        )
        if file_binding(Path(str(record["target"])))["sha256"] != record["sha256"]:
            raise UpgradeError(f"live_install_verify_failed:{name}")

    for name, record in manifest["source_overlay"].items():
        source = safe_package_file(
            package_root,
            str(record["artifact_path"]),
        )
        copy_bound_file(
            source,
            Path(str(record["target"])),
            mode=int(record["mode"]),
        )
        if file_binding(Path(str(record["target"])))["sha256"] != record["sha256"]:
            raise UpgradeError(f"source_overlay_verify_failed:{name}")


def install_registration_tls(tls_root: Path) -> None:
    if REGISTRATION_TLS_ROOT.exists() or REGISTRATION_TLS_ROOT.is_symlink():
        raise UpgradeError("registration_tls_target_preexisting")
    REGISTRATION_TLS_ROOT.mkdir(mode=0o755)
    copy_bound_file(
        tls_root / "bootstrap.pem",
        REGISTRATION_TLS_ROOT / "bootstrap.pem",
        mode=0o644,
        uid=0,
        gid=0,
    )
    copy_bound_file(
        tls_root / "bootstrap.key",
        REGISTRATION_TLS_ROOT / "bootstrap.key",
        mode=0o600,
        uid=999,
        gid=999,
    )


def manager_state_backup(workspace: Path) -> Path:
    if MANAGER_ROOT.is_symlink() or not MANAGER_ROOT.is_dir():
        raise UpgradeError("manager_root_invalid")
    target = workspace / "greenhouse-manager-preupgrade.tar"
    run(
        (
            "tar",
            "--numeric-owner",
            "-cpf",
            str(target),
            "-C",
            str(MANAGER_ROOT.parent),
            MANAGER_ROOT.name,
        ),
        timeout=300,
    )
    os.chmod(target, 0o600)
    if not target.is_file() or target.stat().st_size == 0:
        raise UpgradeError("manager_state_backup_invalid")
    return target


def restore_manager_state(archive: Path) -> None:
    if archive.is_symlink() or not archive.is_file():
        raise UpgradeError("manager_state_archive_invalid")
    if MANAGER_ROOT.exists():
        shutil.rmtree(MANAGER_ROOT)
    run(
        (
            "tar",
            "--numeric-owner",
            "-xpf",
            str(archive),
            "-C",
            str(MANAGER_ROOT.parent),
        ),
        timeout=300,
    )
    if MANAGER_ROOT.is_symlink() or not MANAGER_ROOT.is_dir():
        raise UpgradeError("manager_state_restore_invalid")


def successor_f4_document(
    predecessor: dict[str, Any],
    *,
    manifest: dict[str, Any],
    authorization_id: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    current_installed = predecessor.get("installed_files")
    if not isinstance(current_installed, dict):
        raise UpgradeError("f4_installed_files_invalid")
    before_hash = canonical_sha256(current_installed)
    successor = copy.deepcopy(predecessor)
    updated = copy.deepcopy(current_installed)

    by_target = {
        str(record["target"]): record
        for record in manifest["live_files"].values()
        if record.get("f4_bound") is True
    }
    if set(by_target) != F4_CHANGED_TARGETS:
        raise UpgradeError("f4_changed_target_set_invalid")
    for target, record in by_target.items():
        updated[target] = file_binding(Path(target))

    successor["installed_files"] = updated
    successor.update(
        {
            "r10_candidate_upgrade_authorization_id": authorization_id,
            "r10_candidate_upgrade_authorization_claimed": True,
            "r10_candidate_upgrade_authorization_consumed": True,
            "r10_candidate_upgrade_replay_allowed": False,
            "r10_candidate_upgrade_predecessor_source": PREDECESSOR_SOURCE,
            "r10_candidate_upgrade_target_source": TARGET_SOURCE,
            "r10_candidate_upgrade_manifest_sha256": manifest_sha256,
            "r10_candidate_upgrade_predecessor_installed_files_sha256": (
                before_hash
            ),
            "r10_candidate_upgrade_successor_installed_files_sha256": (
                canonical_sha256(updated)
            ),
            "r10_candidate_upgrade_committed": False,
        }
    )

    for field in F4_HISTORICAL_PROTECTED_FIELDS:
        if successor.get(field) != predecessor.get(field):
            raise UpgradeError(f"f4_historical_field_changed:{field}")
    changed = {
        key
        for key in set(predecessor) | set(successor)
        if predecessor.get(key) != successor.get(key)
    }
    allowed = {"installed_files"} | {
        key for key in successor if key.startswith("r10_candidate_upgrade_")
    }
    if not changed.issubset(allowed):
        raise UpgradeError("f4_successor_unexpected_field_change")
    return successor


def write_f4_successor(
    *,
    manifest: dict[str, Any],
    authorization_id: str,
    manifest_sha256: str,
) -> None:
    predecessor = read_private_json(F4_TRANSACTION)
    if predecessor.get("r10_candidate_upgrade_authorization_claimed") is True:
        raise UpgradeError("f4_successor_replay_forbidden")
    successor = successor_f4_document(
        predecessor,
        manifest=manifest,
        authorization_id=authorization_id,
        manifest_sha256=manifest_sha256,
    )
    atomic_write_json(F4_TRANSACTION, successor)
    reread = read_private_json(F4_TRANSACTION)
    if canonical_sha256(reread) != canonical_sha256(successor):
        raise UpgradeError("f4_successor_readback_mismatch")


def commit_f4_successor() -> None:
    document = read_private_json(F4_TRANSACTION)
    if (
        document.get("r10_candidate_upgrade_authorization_claimed") is not True
        or document.get("r10_candidate_upgrade_committed") is not False
    ):
        raise UpgradeError("f4_successor_commit_prestate_invalid")
    document["r10_candidate_upgrade_committed"] = True
    atomic_write_json(F4_TRANSACTION, document)


def trusted_lan_ready() -> bool:
    path = TRUSTED_LAN_RUNTIME / "state.json"
    if path.is_symlink() or not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, dict)
        and value.get("schema") == "gh.trusted-product-lan/1"
        and value.get("interface") == "eth0"
        and value.get("available") is True
        and isinstance(value.get("generation"), str)
        and bool(value.get("generation"))
    )


def manager_capabilities(manager_id: str) -> bool:
    code = r"""
import json
from greenhouse_manager.runtime.n3w_first_registration_transaction import FIRST_REGISTRATION_TTL_SECONDS, FirstRegistrationTransactionService
from greenhouse_manager.runtime.n3w_registration_runtime import RegistrationNetworkRuntime
from greenhouse_manager.runtime.n3w_dynamic_pairing_window import DynamicPairingWindowController
print(json.dumps({
 "ttl": FIRST_REGISTRATION_TTL_SECONDS == 1800,
 "transaction": FirstRegistrationTransactionService is not None,
 "runtime": RegistrationNetworkRuntime is not None,
 "window": hasattr(DynamicPairingWindowController, "open_first_registration"),
}, sort_keys=True))
"""
    output = run(
        (
            "docker",
            "exec",
            manager_id,
            "python",
            "-c",
            code,
        ),
        timeout=30,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict) and all(value.values())


def strict_postcheck(
    prestate: dict[str, Any],
) -> dict[str, Any]:
    if service_state(SERVICES_UNIT)["active"] != "active":
        raise UpgradeError("services_not_active_postupgrade")
    registration = service_state(REGISTRATION_UNIT)
    if (
        registration["active"] != "active"
        or registration["enabled"] != "enabled"
        or registration["load"] != "loaded"
    ):
        raise UpgradeError("registration_guard_not_ready")

    broker = container_public_snapshot(container("broker"))
    manager_doc = container("manager")
    manager = container_public_snapshot(manager_doc)
    homeassistant = container_public_snapshot(container("homeassistant"))

    if (
        broker["id"] != prestate["broker"]["id"]
        or broker["image_id"] != prestate["broker"]["image_id"]
        or broker["image"] != prestate["broker"]["image"]
        or broker["started_at"] != prestate["broker"]["started_at"]
        or broker["restart_count"] != prestate["broker"]["restart_count"]
    ):
        raise UpgradeError("broker_continuity_failed")
    if manager["image"] != TARGET_MANAGER_IMAGE or not manager["running"]:
        raise UpgradeError("target_manager_not_running")
    if (
        homeassistant["image"] != prestate["homeassistant"]["image"]
        or homeassistant["image_id"] != prestate["homeassistant"]["image_id"]
        or not homeassistant["running"]
    ):
        raise UpgradeError("homeassistant_image_changed")
    if not trusted_lan_ready():
        raise UpgradeError("trusted_lan_not_ready")
    if (
        listener_count("tcp", 47110) != 1
        or listener_count("udp", 47111) != 1
        or listener_count("tcp", 47112) != 0
    ):
        raise UpgradeError("registration_listener_postcheck_failed")
    if not pairing_window_closed(str(manager_doc["Id"])):
        raise UpgradeError("pairing_window_postcheck_failed")
    if not manager_capabilities(str(manager_doc["Id"])):
        raise UpgradeError("manager_capability_postcheck_failed")

    db = database_state()
    if (
        db["integrity"] != "ok"
        or db["current_registration_count"] != 1
        or db["first_registration_table_present"] is not True
        or db["unresolved_first_registration"] != 0
    ):
        raise UpgradeError("database_postcheck_failed")
    f4_services_eligibility()
    return {
        "broker": broker,
        "manager": manager,
        "homeassistant": homeassistant,
        "database": db,
        "registration_guard": registration,
    }


def cleanup_registration_firewall() -> None:
    for protocol, port in REGISTRATION_PORTS:
        run(
            (
                "iptables",
                "-D",
                "INPUT",
                "-p",
                protocol,
                "-m",
                protocol,
                "--dport",
                str(port),
                "-m",
                "comment",
                "--comment",
                REGISTRATION_COMMENT,
                "-j",
                REGISTRATION_CHAIN,
            ),
            timeout=20,
            allowed=frozenset({0, 1}),
        )
    run(
        ("iptables", "-F", REGISTRATION_CHAIN),
        timeout=20,
        allowed=frozenset({0, 1}),
    )
    run(
        ("iptables", "-X", REGISTRATION_CHAIN),
        timeout=20,
        allowed=frozenset({0, 1}),
    )
    if not registration_firewall_absent():
        raise UpgradeError("registration_firewall_cleanup_failed")


def restore_static(
    workspace: Path,
    records: dict[str, Any],
) -> None:
    root = workspace / "static"
    for key, record in records.items():
        if key == "firewall_sha256":
            continue
        if not isinstance(record, dict):
            continue
        path = Path(str(record["path"]))
        if record.get("present") is True:
            backup = root / str(record["backup"])
            atomic_write_bytes(
                path,
                backup.read_bytes(),
                mode=int(record["mode"]),
                uid=int(record["uid"]),
                gid=int(record["gid"]),
            )
        else:
            if path.is_symlink():
                raise UpgradeError(f"rollback_symlink_unexpected:{path}")
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()


def verify_predecessor_runtime(
    prestate: dict[str, Any],
) -> None:
    if service_state(SERVICES_UNIT)["active"] != "active":
        raise UpgradeError("rollback_services_not_active")
    broker = container_public_snapshot(container("broker"))
    manager = container_public_snapshot(container("manager"))
    homeassistant = container_public_snapshot(container("homeassistant"))
    if (
        broker["id"] != prestate["broker"]["id"]
        or broker["started_at"] != prestate["broker"]["started_at"]
        or broker["image_id"] != prestate["broker"]["image_id"]
        or manager["image"] != PREDECESSOR_MANAGER_IMAGE
        or homeassistant["image"] != prestate["homeassistant"]["image"]
    ):
        raise UpgradeError("rollback_runtime_not_predecessor")
    db = database_state()
    if (
        db["integrity"] != "ok"
        or db["current_registration_count"] != 1
        or db["first_registration_table_present"] is not False
    ):
        raise UpgradeError("rollback_database_not_predecessor")
    f4_services_eligibility()


def rollback(
    *,
    workspace: Path,
    records: dict[str, Any],
    prestate: dict[str, Any],
    manager_archive: Path | None,
) -> None:
    errors: list[str] = []
    try:
        run(
            ("systemctl", "stop", SERVICES_UNIT),
            timeout=180,
            allowed=frozenset({0, 5}),
        )
    except Exception as error:
        errors.append("stop_services:" + type(error).__name__)
    try:
        run(
            ("systemctl", "stop", REGISTRATION_UNIT),
            timeout=60,
            allowed=frozenset({0, 5}),
        )
        run(
            ("systemctl", "disable", REGISTRATION_UNIT),
            timeout=60,
            allowed=frozenset({0, 1, 5}),
        )
    except Exception as error:
        errors.append("stop_registration:" + type(error).__name__)
    try:
        cleanup_registration_firewall()
    except Exception as error:
        errors.append("firewall:" + type(error).__name__)
    try:
        if TRUSTED_LAN_RUNTIME.exists():
            shutil.rmtree(TRUSTED_LAN_RUNTIME)
    except Exception as error:
        errors.append("trusted_lan:" + type(error).__name__)
    try:
        if manager_archive is not None:
            restore_manager_state(manager_archive)
    except Exception as error:
        errors.append("manager_state:" + type(error).__name__)
    try:
        restore_static(workspace, records)
    except Exception as error:
        errors.append("static:" + type(error).__name__)
    try:
        if REGISTRATION_TLS_ROOT.exists():
            shutil.rmtree(REGISTRATION_TLS_ROOT)
    except Exception as error:
        errors.append("registration_tls:" + type(error).__name__)
    try:
        run(("systemctl", "daemon-reload"), timeout=60)
    except Exception as error:
        errors.append("daemon_reload:" + type(error).__name__)
    try:
        run(("systemctl", "start", SERVICES_UNIT), timeout=240)
        verify_predecessor_runtime(prestate)
    except Exception as error:
        errors.append("predecessor_runtime:" + type(error).__name__)
    try:
        run(
            ("docker", "image", "rm", TARGET_MANAGER_IMAGE),
            timeout=120,
            allowed=frozenset({0, 1}),
        )
    except Exception as error:
        errors.append("target_image_cleanup:" + type(error).__name__)
    if errors:
        advance_upgrade(
            "ROLLBACK_FAILED",
            rollback_completed=False,
            rollback_error_count=len(errors),
            rollback_error_classes=errors,
        )
        raise UpgradeError("rollback_unproven")
    advance_upgrade(
        "ROLLED_BACK",
        rollback_completed=True,
        rollback_error_count=0,
        committed=False,
    )


def execute_apply(
    *,
    package_root: Path,
    expected_manifest_sha256: str,
    authorization_id: str,
    confirmation: str,
) -> dict[str, Any]:
    require_root()
    if confirmation != CONFIRMATION:
        raise UpgradeError("confirmation_invalid")
    manifest = validate_package(
        package_root,
        expected_manifest_sha256,
    )
    prestate = verify_prestate(package_root, manifest)

    claim_upgrade(
        authorization_id=authorization_id,
        manifest_sha256=expected_manifest_sha256,
        package_head=str(manifest["package_head"]),
        prestate=prestate,
    )

    workspace: Path | None = None
    records: dict[str, Any] = {}
    manager_archive: Path | None = None
    rollback_required = True
    try:
        workspace = create_workspace(authorization_id)
        records = static_backup(workspace, manifest)
        advance_upgrade(
            "BACKUP_STATIC_COMPLETE",
            static_backup_complete=True,
            workspace_sha256=sha256_bytes(
                str(workspace).encode("utf-8")
            ),
        )

        load_target_manager(package_root, manifest)
        tls_stage = generate_registration_tls(
            workspace,
            str(prestate["system_id"]),
        )
        advance_upgrade(
            "CANDIDATE_STAGED",
            target_manager_image_loaded=True,
            registration_tls_staged=True,
        )

        broker_before = container_public_snapshot(container("broker"))
        run(("systemctl", "stop", SERVICES_UNIT), timeout=240)
        broker_after = container_public_snapshot(container("broker"))
        if broker_before != broker_after:
            raise UpgradeError("broker_changed_during_services_stop")

        manager_archive = manager_state_backup(workspace)
        if shutil.disk_usage("/").free < int(
            manifest["capacity"]["upgrade_emergency_reserve_bytes"]
        ) + int(manifest["manager"]["image_size_bytes"]):
            raise UpgradeError("capacity_after_backup_insufficient")
        advance_upgrade(
            "SERVICES_STOPPED_BACKUP_COMPLETE",
            services_stopped=True,
            manager_state_backup_sha256=sha256_file(manager_archive),
        )

        install_runtime_files(package_root, manifest)
        rewrite_manager_image(
            COMPOSE_ENV,
            expected=PREDECESSOR_MANAGER_IMAGE,
            target=TARGET_MANAGER_IMAGE,
        )
        install_registration_tls(tls_stage)
        run(("systemctl", "daemon-reload"), timeout=60)
        run(
            ("systemctl", "enable", REGISTRATION_UNIT),
            timeout=60,
        )
        run(
            ("systemctl", "start", REGISTRATION_UNIT),
            timeout=60,
        )
        registration = service_state(REGISTRATION_UNIT)
        if (
            registration["active"] != "active"
            or registration["enabled"] != "enabled"
            or not trusted_lan_ready()
        ):
            raise UpgradeError("registration_guard_activation_failed")

        write_f4_successor(
            manifest=manifest,
            authorization_id=authorization_id,
            manifest_sha256=expected_manifest_sha256,
        )
        f4_services_eligibility()
        advance_upgrade(
            "SUCCESSOR_BOUND",
            f4_successor_bound=True,
            f4_successor_installed_files_sha256=canonical_sha256(
                read_private_json(F4_TRANSACTION)["installed_files"]
            ),
        )

        run(("systemctl", "start", SERVICES_UNIT), timeout=300)
        post = strict_postcheck(prestate)

        commit_f4_successor()
        f4_services_eligibility()
        advance_upgrade(
            "COMMITTED",
            committed=True,
            rollback_completed=False,
            target_manager_image_id=post["manager"]["image_id"],
            database_integrity="PASS",
            current_registration_count=1,
            first_registration_table_present=True,
            unresolved_first_registration=0,
            broker_continuity=True,
            homeassistant_image_unchanged=True,
            registration_guard_ready=True,
            trusted_lan_ready=True,
            listener_47110=1,
            listener_47111=1,
            listener_47112=0,
            pairing_window="CLOSED",
            board_access=False,
        )
        rollback_required = False
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "phase": "COMMITTED",
            "predecessor_source": PREDECESSOR_SOURCE,
            "target_source": TARGET_SOURCE,
            "target_manager_image": TARGET_MANAGER_IMAGE,
            "current_registration_count": 1,
            "broker_continuity": True,
            "registration_runtime_ready": True,
            "board_access": False,
            "authorization_consumed": True,
        }
    except Exception:
        if (
            rollback_required
            and workspace is not None
            and records
        ):
            rollback(
                workspace=workspace,
                records=records,
                prestate=prestate,
                manager_archive=manager_archive,
            )
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--package-root", type=Path, required=True)
    value.add_argument("--expected-manifest-sha256", required=True)
    value.add_argument("--authorization-id", required=True)
    value.add_argument("--confirm", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute_apply(
            package_root=args.package_root,
            expected_manifest_sha256=args.expected_manifest_sha256,
            authorization_id=args.authorization_id,
            confirmation=args.confirm,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as error:
        claimed = UPGRADE_TRANSACTION.exists() and not UPGRADE_TRANSACTION.is_symlink()
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP_PARTIAL" if claimed else "STOP",
                    "reason": str(error)[:240] or type(error).__name__,
                    "authorization_consumed": claimed,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
