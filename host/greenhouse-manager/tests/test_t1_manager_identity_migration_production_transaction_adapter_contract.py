from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_production_transaction_adapter_contract import (
    ManagerIdentityProductionTransactionAdapterContractError,
    ManagerIdentityProductionTransactionAdapterDisabledError,
    build_manager_production_transaction_adapter_contract,
    execute_manager_production_transaction_adapter_contract,
    verify_manager_production_transaction_adapter_contract,
)

USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
PASSWORD = "manager-password-secret"
WORKING_DIR = "/opt/HomeAssistant/infra/compose/t1"
SECRET_ROOT = "/opt/greenhouse-secrets/mqtt"
PASSWORD_TARGET = "/opt/greenhouse-secrets/mqtt/manager/password"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, _json(value) + "\n")


def _record(path: Path, root: Path, secret: bool) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha(path),
        "mode": "0600",
        "contains_secret": secret,
    }


def _path_record(path: str, digest: str) -> dict[str, object]:
    return {
        "path": path,
        "device": 1,
        "inode": 2,
        "mode": 0o600,
        "uid": 0,
        "gid": 0,
        "size": 100,
        "sha256": digest,
    }


def _preparation(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = tmp_path / "greenhouse-manager-migration-preparation-test"
    root.mkdir(mode=0o700)

    manager_env = root / "material/manager/manager.env"
    password = root / "material/manager/password"
    fragment = root / "material/manager/compose-secret-fragment.yaml"
    _write(
        manager_env,
        f"GH_MQTT_USERNAME={USERNAME}\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    _write(password, PASSWORD + "\n")
    _write(fragment, "services:\n  greenhouse-manager:\n    environment: {}\n")

    container = {
        "container_id": "manager-container-id",
        "image_id": "sha256:manager-image-id",
        "image_ref": "greenhouse-manager:0.4.46",
        "started_at": "2026-07-13T00:00:00Z",
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": True,
        "legacy_client_id_fingerprint": _fingerprint("greenhouse-manager"),
        "mqtt_username_present": False,
        "mqtt_password_present": False,
        "mqtt_password_file_present": False,
    }
    compose = {
        "project": "t1",
        "working_dir": WORKING_DIR,
        "config_files": [
            _path_record(
                f"{WORKING_DIR}/docker-compose.manager.yml",
                "3" * 64,
            )
        ],
        "environment": _path_record(f"{WORKING_DIR}/.env", "4" * 64),
    }
    runtime = {
        "schema": "gh.m2.t1-manager-runtime-binding/1",
        "created_at": "2026-07-13T02:00:00Z",
        "container": container,
        "compose": compose,
        "target_secret_root": SECRET_ROOT,
        "target_password_file": PASSWORD_TARGET,
        "read_only_capture": True,
        "current_services_modified": False,
    }
    runtime_path = root / "manager-runtime-binding.json"
    _write_json(runtime_path, runtime)

    plan = {
        "schema": "gh.m2.t1-manager-identity-migration-transaction-plan/1",
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_apply": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "restart_scope": ["greenhouse-manager"],
        "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
        "required_sequence": [
            "refresh_postactivation_and_runtime_bindings",
            "capture_fresh_manager_compose_and_secret_rollback",
            "create_short_lived_single_use_authorization",
            "atomically_install_manager_password",
            "apply_exact_manager_compose_overlay",
            "recreate_only_greenhouse_manager",
            "verify_manager_authenticated_client_id",
            "verify_ingress_subscription",
            "verify_canonical_and_discovery_publication",
            "verify_reconnect_and_existing_entities",
            "rollback_on_any_failure",
        ],
        "node_credentials_delivered": False,
    }
    plan_path = root / "transaction-plan.json"
    _write_json(plan_path, plan)
    runbook = root / "operator-runbook.txt"
    _write(runbook, "Preparation only.\n")

    records = [
        _record(manager_env, root, True),
        _record(password, root, True),
        _record(fragment, root, True),
        _record(runtime_path, root, True),
        _record(plan_path, root, False),
        _record(runbook, root, False),
    ]
    bindings = {
        "postactivation_manifest_sha256": "1" * 64,
        "migration_stage_manifest_sha256": "2" * 64,
        "manager_username_fingerprint": _fingerprint(USERNAME),
        "manager_client_id_fingerprint": _fingerprint(CLIENT_ID),
        "manager_runtime_binding_sha256": _sha(runtime_path),
        "manager_runtime_fingerprint": _fingerprint(_json(container)),
        "compose_binding_fingerprint": _fingerprint(_json(compose)),
    }
    manifest = {
        "schema": "gh.m2.t1-manager-identity-migration-preparation/1",
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
        "bindings": bindings,
        "records": records,
    }
    _write_json(root / "manifest.json", manifest)
    return root


def _build(tmp_path: Path) -> dict[str, object]:
    return build_manager_production_transaction_adapter_contract(
        _preparation(tmp_path)
    )


def test_builds_strict_non_callable_manager_adapter_contract(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    verified = verify_manager_production_transaction_adapter_contract(contract)

    assert verified["verified"] is True
    assert contract["production_transaction_adapter_contract_available"] is True
    assert contract["production_transaction_adapters_installed"] is False
    assert contract["authorization_claimed"] is False
    assert contract["claim_enabled"] is False
    assert contract["fresh_rollback_bound"] is False
    assert contract["production_executor_available"] is False
    assert contract["execution_enabled"] is False
    assert contract["apply_enabled"] is False
    assert contract["operator_action_authorized"] is False
    assert contract["ready_for_manager_migration_apply"] is False
    assert contract["manager_identity_migrated"] is False
    assert contract["node_credentials_delivered"] is False
    assert contract["current_services_modified"] is False
    assert contract["preserve_anonymous"] is True
    assert contract["anonymous_closure_enabled"] is False
    assert contract["secret_values_included"] is False
    assert contract["path_values_redacted"] is True
    assert contract["phase_order"] == [
        "authorization_claim",
        "runtime_revalidation",
        "fresh_rollback_verification",
        "password_write",
        "environment_write",
        "overlay_write",
        "manager_recreate",
        "identity_check",
        "ingress_check",
        "canonical_check",
        "discovery_check",
        "reconnect_check",
        "existing_entities_check",
        "postactivation_audit",
        "journal_commit",
    ]
    assert all(
        adapter["installed"] is False
        and adapter["callable"] is False
        and adapter["host_write_capability"] is False
        and adapter["docker_mutation_capability"] is False
        and adapter["mqtt_publish_capability"] is False
        and adapter["authorization_claim_capability"] is False
        for adapter in contract["adapters"].values()
    )
    assert contract["runtime_controller"]["allowed_commands"][0] == {
        "name": "inspect_greenhouse_manager",
        "argv": ["docker", "inspect", "greenhouse-manager"],
        "mutation": False,
    }
    assert contract["runtime_controller"]["mosquitto_target_allowed"] is False
    assert contract["runtime_controller"]["homeassistant_target_allowed"] is False
    assert contract["runtime_controller"]["node_target_allowed"] is False
    assert contract["fresh_rollback"]["complete_compose_tree_snapshot_required"] is True
    assert contract["postactivation"]["existing_homeassistant_entities_refresh_required"] is True


def test_contract_is_redacted_and_survives_json_round_trip(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    serialized = json.dumps(contract)
    protected_values = (
        USERNAME,
        CLIENT_ID,
        PASSWORD,
        WORKING_DIR,
        SECRET_ROOT,
        PASSWORD_TARGET,
    )
    assert all(value not in serialized for value in protected_values)
    parsed = json.loads(serialized)
    assert verify_manager_production_transaction_adapter_contract(parsed)["verified"] is True


def test_rejects_preparation_safety_drift(tmp_path: Path) -> None:
    preparation = _preparation(tmp_path)
    manifest_path = preparation / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["apply_enabled"] = True
    _write_json(manifest_path, manifest)

    with pytest.raises(
        ManagerIdentityProductionTransactionAdapterContractError,
        match="preparation manifest safety flag failed: apply_enabled",
    ):
        build_manager_production_transaction_adapter_contract(preparation)


def test_rejects_record_or_runtime_target_drift(tmp_path: Path) -> None:
    preparation = _preparation(tmp_path / "record")
    (preparation / "material/manager/password").write_text("tampered\n")
    with pytest.raises(
        ManagerIdentityProductionTransactionAdapterContractError,
        match="record verification failed",
    ):
        build_manager_production_transaction_adapter_contract(preparation)

    preparation = _preparation(tmp_path / "target")
    runtime_path = preparation / "manager-runtime-binding.json"
    runtime = json.loads(runtime_path.read_text())
    runtime["target_password_file"] = "/tmp/escaped-password"
    _write_json(runtime_path, runtime)
    manifest_path = preparation / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["records"]:
        if record["path"] == "manager-runtime-binding.json":
            record["size"] = runtime_path.stat().st_size
            record["sha256"] = _sha(runtime_path)
    manifest["bindings"]["manager_runtime_binding_sha256"] = _sha(runtime_path)
    _write_json(manifest_path, manifest)
    with pytest.raises(
        ManagerIdentityProductionTransactionAdapterContractError,
        match="escaped the secret root",
    ):
        build_manager_production_transaction_adapter_contract(preparation)


def test_rejects_adapter_capability_tampering(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    contract["adapters"]["password_write"]["host_write_capability"] = True

    with pytest.raises(
        ManagerIdentityProductionTransactionAdapterContractError,
        match="fingerprint does not match",
    ):
        verify_manager_production_transaction_adapter_contract(contract)


def test_execution_entrypoint_is_unconditionally_disabled() -> None:
    with pytest.raises(
        ManagerIdentityProductionTransactionAdapterDisabledError,
        match="not installed",
    ):
        execute_manager_production_transaction_adapter_contract()


def test_cli_exposes_no_claim_execute_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_manager_identity_migration_production_transaction_adapter_contract.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "preparation_directory" in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
