from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
    verify_manager_production_driver_contract,
)
from .t1_manager_identity_migration_production_transaction_adapter_contract import (
    ManagerIdentityProductionTransactionAdapterContractError,
    build_manager_production_transaction_adapter_contract,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-live-runtime-gate/1"
RUNTIME_SCHEMA = "gh.m2.t1-manager-runtime-binding/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MANAGER_AUTH_KEYS = {
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD",
    "GH_MQTT_PASSWORD_FILE",
}


class ManagerIdentityLiveRuntimeGateError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))[:16]


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManagerIdentityLiveRuntimeGateError(f"{label} SHA-256 is invalid")
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityLiveRuntimeGateError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityLiveRuntimeGateError(f"{label} must be a JSON object")
    return document


def _run_inspect(runner: CommandRunner) -> dict[str, Any]:
    command = ("docker", "inspect", "greenhouse-manager")
    code, output = runner.run(command)
    if code != 0:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager cannot be inspected"
        )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager inspection returned invalid JSON"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "exactly one greenhouse-manager container is required"
        )
    return documents[0]


def _environment(config: Mapping[str, Any]) -> dict[str, str]:
    raw = config.get("Env")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager environment metadata is invalid"
        )
    values: dict[str, str] = {}
    for item in raw:
        key, separator, value = item.partition("=")
        if separator:
            values[key] = value
    if any(values.get(key, "") for key in _MANAGER_AUTH_KEYS):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager already has active MQTT authentication"
        )
    return values


def _normalized_runtime(document: Mapping[str, Any]) -> tuple[dict[str, object], dict[str, str]]:
    state = document.get("State")
    config = document.get("Config")
    if not isinstance(state, dict) or not isinstance(config, dict):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager runtime metadata is incomplete"
        )
    if state.get("Status") != "running" or int(document.get("RestartCount", -1)) != 0:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager must be running with restart count zero"
        )
    environment = _environment(config)
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose labels are missing"
        )
    compose_labels = {
        "project": str(labels.get("com.docker.compose.project", "")).strip(),
        "working_dir": str(
            labels.get("com.docker.compose.project.working_dir", "")
        ).strip(),
        "config_files": str(
            labels.get("com.docker.compose.project.config_files", "")
        ).strip(),
    }
    if not all(compose_labels.values()):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose labels are incomplete"
        )
    runtime = {
        "container_id": str(document.get("Id", "")),
        "image_id": str(document.get("Image", "")),
        "image_ref": str(config.get("Image", "")),
        "started_at": str(state.get("StartedAt", "")),
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": bool(environment.get("GH_MQTT_CLIENT_ID", "")),
        "legacy_client_id_fingerprint": (
            _fingerprint(environment["GH_MQTT_CLIENT_ID"])
            if environment.get("GH_MQTT_CLIENT_ID")
            else None
        ),
        "mqtt_username_present": False,
        "mqtt_password_present": False,
        "mqtt_password_file_present": False,
    }
    if not all(runtime[field] for field in ("container_id", "image_id", "image_ref")):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager runtime identity is incomplete"
        )
    return runtime, compose_labels


def _absolute_regular_file(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ManagerIdentityLiveRuntimeGateError(f"{label} is missing or unsafe")
    return path.resolve()


def _absolute_directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ManagerIdentityLiveRuntimeGateError(f"{label} is missing or unsafe")
    return path.resolve()


def _path_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
        "size": stat.st_size,
        "sha256": _sha_path(path),
    }


def _current_compose_binding(labels: Mapping[str, str]) -> dict[str, object]:
    working = _absolute_directory(
        Path(labels["working_dir"]).expanduser(),
        "greenhouse-manager Compose working directory",
    )
    files: list[Path] = []
    for raw in labels["config_files"].split(","):
        value = raw.strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = working / path
        path = _absolute_regular_file(
            path,
            "greenhouse-manager Compose configuration",
        )
        if not path.is_relative_to(working):
            raise ManagerIdentityLiveRuntimeGateError(
                "greenhouse-manager Compose configuration escaped the working directory"
            )
        files.append(path)
    if not files:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose configuration list is empty"
        )
    environment_path = working / ".env"
    environment: dict[str, object] | None = None
    if environment_path.exists() or environment_path.is_symlink():
        environment = _path_record(
            _absolute_regular_file(
                environment_path,
                "greenhouse-manager Compose environment",
            )
        )
    return {
        "project": labels["project"],
        "working_dir": str(working),
        "config_files": [_path_record(path) for path in files],
        "environment": environment,
    }


def _runtime_security(document: Mapping[str, Any]) -> dict[str, bool]:
    host = document.get("HostConfig")
    if not isinstance(host, dict):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager HostConfig metadata is missing"
        )
    cap_drop = host.get("CapDrop")
    security_opt = host.get("SecurityOpt")
    checks = {
        "read_only_rootfs": host.get("ReadonlyRootfs") is True,
        "not_privileged": host.get("Privileged") is False,
        "all_capabilities_dropped": isinstance(cap_drop, list)
        and any(str(item).upper() == "ALL" for item in cap_drop),
        "no_new_privileges": isinstance(security_opt, list)
        and any(str(item).startswith("no-new-privileges") for item in security_opt),
    }
    if not all(checks.values()):
        failed = next(name for name, passed in checks.items() if not passed)
        raise ManagerIdentityLiveRuntimeGateError(
            f"greenhouse-manager runtime security profile drifted: {failed}"
        )
    return checks


def _active_secret_checks(
    runtime_binding: Mapping[str, Any],
    document: Mapping[str, Any],
) -> dict[str, bool]:
    raw_root = runtime_binding.get("target_secret_root")
    raw_password = runtime_binding.get("target_password_file")
    if not isinstance(raw_root, str) or not isinstance(raw_password, str):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager active secret target binding is incomplete"
        )
    root = Path(raw_root).expanduser()
    password = Path(raw_password).expanduser()
    if not root.is_absolute() or not password.is_absolute():
        raise ManagerIdentityLiveRuntimeGateError(
            "manager active secret target binding is unsafe"
        )
    if root.is_symlink() or password.is_symlink():
        raise ManagerIdentityLiveRuntimeGateError(
            "manager active secret target uses a symbolic link"
        )
    root = root.resolve()
    password = password.resolve()
    if not password.is_relative_to(root):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager password target escaped the active secret root"
        )
    if root.exists() and (
        not root.is_dir() or root.stat().st_mode & 0o077
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager active secret root is not private"
        )
    parent = password.parent
    if parent.exists() and (
        parent.is_symlink()
        or not parent.is_dir()
        or parent.stat().st_mode & 0o077
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager password target parent is not private"
        )
    if password.exists() or password.is_symlink():
        raise ManagerIdentityLiveRuntimeGateError(
            "manager password target is already active"
        )
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager mount inventory is missing"
        )
    for mount in mounts:
        if not isinstance(mount, dict):
            raise ManagerIdentityLiveRuntimeGateError(
                "greenhouse-manager mount inventory is invalid"
            )
        destination = mount.get("Destination")
        source = mount.get("Source")
        if destination == "/run/secrets/gh_manager_mqtt_password":
            raise ManagerIdentityLiveRuntimeGateError(
                "manager password target is already mounted"
            )
        if isinstance(source, str) and source:
            candidate = Path(source).expanduser()
            if candidate.is_absolute():
                candidate = candidate.resolve()
                if candidate == root or candidate.is_relative_to(root):
                    raise ManagerIdentityLiveRuntimeGateError(
                        "manager active secret root is already mounted"
                    )
    return {
        "active_secret_root_private_or_absent": True,
        "manager_password_target_absent": True,
        "manager_password_mount_absent": True,
    }


def build_manager_identity_live_runtime_gate(
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    driver_path = Path(driver_contract_file).expanduser().resolve()
    preparation = Path(preparation_directory).expanduser().resolve()
    driver_contract = _read_private_json(
        driver_path,
        "manager production driver contract",
    )
    verified = verify_manager_production_driver_contract(driver_contract)
    driver_sha = _require_sha(
        verified.get("driver_contract_sha256"),
        "manager production driver contract",
    )
    if driver_contract.get("driver_contract_sha256") != driver_sha:
        raise ManagerIdentityLiveRuntimeGateError(
            "manager production driver contract binding does not match"
        )

    rebuilt_adapter = build_manager_production_transaction_adapter_contract(preparation)
    adapter_sha = _require_sha(
        rebuilt_adapter.get("adapter_contract_sha256"),
        "manager production adapter contract",
    )
    if driver_contract.get("adapter_contract_sha256") != adapter_sha:
        raise ManagerIdentityLiveRuntimeGateError(
            "manager production driver contract does not match the preparation package"
        )

    runtime_path = preparation / "manager-runtime-binding.json"
    runtime_binding = _read_private_json(runtime_path, "manager runtime binding")
    if (
        runtime_binding.get("schema") != RUNTIME_SCHEMA
        or runtime_binding.get("read_only_capture") is not True
        or runtime_binding.get("current_services_modified") is not False
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager runtime binding safety flags are invalid"
        )
    runtime_sha = _sha_path(runtime_path)
    if driver_contract.get("manager_runtime_binding_sha256") != runtime_sha:
        raise ManagerIdentityLiveRuntimeGateError(
            "manager runtime binding SHA-256 does not match the driver contract"
        )

    document = _run_inspect(runner or SubprocessRunner())
    current_runtime, labels = _normalized_runtime(document)
    saved_runtime = runtime_binding.get("container")
    saved_compose = runtime_binding.get("compose")
    if not isinstance(saved_runtime, dict) or not isinstance(saved_compose, dict):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager runtime binding is incomplete"
        )
    if current_runtime != saved_runtime:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager runtime identity drifted from preparation"
        )
    runtime_fingerprint = _fingerprint(_canonical_json(current_runtime))
    if driver_contract.get("manager_runtime_fingerprint") != runtime_fingerprint:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager runtime fingerprint does not match"
        )

    current_compose = _current_compose_binding(labels)
    if current_compose != saved_compose:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose binding drifted from preparation"
        )
    compose_fingerprint = _fingerprint(_canonical_json(current_compose))
    if driver_contract.get("compose_binding_fingerprint") != compose_fingerprint:
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose binding fingerprint does not match"
        )
    if driver_contract.get("compose_project_fingerprint") != _fingerprint(
        str(current_compose["project"])
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose project fingerprint does not match"
        )
    if driver_contract.get("compose_working_directory_fingerprint") != _fingerprint(
        str(current_compose["working_dir"])
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose working directory fingerprint does not match"
        )
    if driver_contract.get("compose_config_set_fingerprint") != _fingerprint(
        _canonical_json(current_compose["config_files"])
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "greenhouse-manager Compose configuration fingerprint does not match"
        )

    security_checks = _runtime_security(document)
    secret_checks = _active_secret_checks(runtime_binding, document)
    raw_root = str(runtime_binding["target_secret_root"])
    raw_password = str(runtime_binding["target_password_file"])
    if driver_contract.get("active_secret_root_fingerprint") != _fingerprint(raw_root):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager active secret root fingerprint does not match"
        )
    if driver_contract.get("active_password_target_fingerprint") != _fingerprint(
        raw_password
    ):
        raise ManagerIdentityLiveRuntimeGateError(
            "manager password target fingerprint does not match"
        )

    checks = {
        "driver_contract_verified": True,
        "adapter_contract_rebuilt_and_bound": True,
        "runtime_binding_hash_verified": True,
        "manager_running_zero_restart": True,
        "manager_runtime_identity_unchanged": True,
        "manager_authentication_not_active": True,
        "compose_project_unchanged": True,
        "compose_files_and_environment_unchanged": True,
        "runtime_security_profile_preserved": True,
        **security_checks,
        **secret_checks,
        "single_read_only_docker_inspect_model": True,
    }
    live_binding = {
        "driver_contract_sha256": driver_sha,
        "adapter_contract_sha256": adapter_sha,
        "runtime_binding_sha256": runtime_sha,
        "manager_runtime_fingerprint": runtime_fingerprint,
        "compose_binding_fingerprint": compose_fingerprint,
        "image_id_fingerprint": _fingerprint(str(current_runtime["image_id"])),
        "image_ref_fingerprint": _fingerprint(str(current_runtime["image_ref"])),
        "container_id_fingerprint": _fingerprint(str(current_runtime["container_id"])),
        "compose_project_fingerprint": _fingerprint(str(current_compose["project"])),
        "compose_working_directory_fingerprint": _fingerprint(
            str(current_compose["working_dir"])
        ),
        "active_secret_root_fingerprint": _fingerprint(raw_root),
        "active_password_target_fingerprint": _fingerprint(raw_password),
    }
    return {
        "schema": SCHEMA,
        "read_only": True,
        "driver_contract_sha256": driver_sha,
        "adapter_contract_sha256": adapter_sha,
        "runtime_binding_sha256": runtime_sha,
        "live_binding_sha256": _sha_bytes(
            _canonical_json(live_binding).encode("utf-8")
        ),
        "live_binding": live_binding,
        "checks": checks,
        "live_runtime_gate_ready": all(checks.values()),
        "ready_for_fresh_rollback_preparation": True,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only real-T1 greenhouse-manager runtime, mount, Compose, "
            "and inactive-secret binding gate."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("preparation_directory")
    args = parser.parse_args(argv)
    try:
        result = build_manager_identity_live_runtime_gate(
            args.driver_contract_file,
            args.preparation_directory,
            runner=runner,
        )
    except (
        ManagerIdentityLiveRuntimeGateError,
        ManagerIdentityProductionDriverContractError,
        ManagerIdentityProductionTransactionAdapterContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager live runtime gate failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["live_runtime_gate_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
