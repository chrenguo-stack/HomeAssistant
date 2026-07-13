from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from greenhouse_manager.t1_manager_identity_migration_execution_preparation_constants import (
    GATE_CHECKS,
)


def write_text(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def write_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    write_text(path, json.dumps(value, sort_keys=True), mode)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
        "size": stat.st_size,
        "sha256": sha(path),
    }


def record(path: Path, root: Path, contains_secret: bool) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha(path),
        "size": path.stat().st_size,
        "mode": "0600",
        "contains_secret": contains_secret,
    }


def build_preparation(
    tmp_path: Path,
    *,
    include_environment: bool,
) -> tuple[Path, Path, Path, dict[str, object]]:
    tmp_path.chmod(0o700)
    compose_root = tmp_path / "compose"
    compose_root.mkdir(mode=0o700)
    compose_file = compose_root / "compose.yaml"
    write_text(compose_file, "services:\n  greenhouse-manager:\n    image: test\n", 0o644)

    environment_record: dict[str, object] | None = None
    if include_environment:
        environment_path = compose_root / ".env"
        write_text(environment_path, "TEST_VALUE=1\n", 0o600)
        environment_record = path_record(environment_path)

    secret_root = tmp_path / "active-secrets" / "mqtt"
    password_target = secret_root / "manager" / "password"
    preparation = tmp_path / "greenhouse-manager-migration-preparation-test"
    preparation.mkdir(mode=0o700)

    manager = preparation / "material" / "manager"
    env_path = manager / "manager.env"
    password_path = manager / "password"
    fragment_path = manager / "compose-secret-fragment.yaml"
    write_text(
        env_path,
        "GH_MQTT_USERNAME=gh-manager\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        "GH_MQTT_CLIENT_ID=gh-manager-client\n",
    )
    write_text(password_path, "manager-password\n")
    write_text(fragment_path, "services: {}\n")

    runtime_path = preparation / "manager-runtime-binding.json"
    runtime = {
        "schema": "gh.m2.t1-manager-runtime-binding/1",
        "created_at": "2026-07-13T04:00:00Z",
        "container": {
            "container_id": "container-id",
            "image_id": "sha256:image",
            "image_ref": "greenhouse-manager:test",
            "started_at": "2026-07-13T03:00:00Z",
            "state": "running",
            "restart_count": 0,
            "legacy_client_id_present": False,
            "legacy_client_id_fingerprint": None,
            "mqtt_username_present": False,
            "mqtt_password_present": False,
            "mqtt_password_file_present": False,
        },
        "compose": {
            "project": "homeassistant",
            "working_dir": str(compose_root.resolve()),
            "config_files": [path_record(compose_file)],
            "environment": environment_record,
        },
        "target_secret_root": str(secret_root.resolve()),
        "target_password_file": str(password_target.resolve()),
        "read_only_capture": True,
        "current_services_modified": False,
    }
    write_json(runtime_path, runtime)

    plan_path = preparation / "transaction-plan.json"
    runbook_path = preparation / "operator-runbook.txt"
    write_json(plan_path, {"schema": "test-plan"})
    write_text(runbook_path, "test runbook\n")

    records = [
        record(env_path, preparation, True),
        record(password_path, preparation, True),
        record(fragment_path, preparation, True),
        record(runtime_path, preparation, True),
        record(plan_path, preparation, False),
        record(runbook_path, preparation, False),
    ]
    manifest = {
        "schema": "gh.m2.t1-manager-identity-migration-preparation/1",
        "created_at": "2026-07-13T04:00:00Z",
        "classification": "secret-local-manager-migration-preparation",
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "broker_identity_activated": True,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_authorization": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "bindings": {"manager_runtime_binding_sha256": sha(runtime_path)},
        "records": records,
        "secret_values_included": True,
        "normal_report_contains_secrets": False,
        "normal_report_contains_source_paths": False,
    }
    manifest_path = preparation / "manifest.json"
    write_json(manifest_path, manifest)

    driver = tmp_path / "driver-contract.json"
    write_json(driver, {"schema": "test-driver"})
    output = tmp_path / "greenhouse-m2-manager-execution-preparations.test"
    output.mkdir(mode=0o700)
    gate = live_gate(runtime_path)
    return preparation, driver, output, gate


def live_gate(runtime_path: Path, *, live_binding: str = "4" * 64) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-manager-identity-live-runtime-gate/1",
        "read_only": True,
        "driver_contract_sha256": "1" * 64,
        "adapter_contract_sha256": "2" * 64,
        "runtime_binding_sha256": sha(runtime_path),
        "live_binding_sha256": live_binding,
        "live_binding": {},
        "checks": {name: True for name in GATE_CHECKS},
        "live_runtime_gate_ready": True,
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
