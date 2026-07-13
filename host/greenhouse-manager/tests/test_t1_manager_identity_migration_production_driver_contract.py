from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
    ManagerIdentityProductionDriverDisabledError,
    build_manager_production_driver_contract,
    execute_manager_production_driver_contract,
    verify_manager_production_driver_contract,
)

SHA_FIELDS = (
    "preparation_manifest_sha256",
    "manager_runtime_binding_sha256",
    "transaction_plan_sha256",
    "manager_env_sha256",
    "manager_password_sha256",
    "manager_fragment_sha256",
    "postactivation_manifest_sha256",
    "migration_stage_manifest_sha256",
)
FINGERPRINT_FIELDS = (
    "manager_runtime_fingerprint",
    "compose_binding_fingerprint",
    "compose_project_fingerprint",
    "compose_working_directory_fingerprint",
    "compose_config_set_fingerprint",
    "active_secret_root_fingerprint",
    "active_password_target_fingerprint",
    "manager_username_fingerprint",
    "manager_client_id_fingerprint",
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _adapter() -> dict[str, object]:
    document: dict[str, object] = {
        "schema": "gh.m2.t1-manager-identity-production-transaction-adapter-contract/1",
        **{field: str(index + 1) * 64 for index, field in enumerate(SHA_FIELDS)},
        **{
            field: format(index + 1, "016x")
            for index, field in enumerate(FINGERPRINT_FIELDS)
        },
        "authorization_claim": {
            "claim_enabled": False,
        },
        "filesystem_transaction": {
            "allowed_mutations": [
                "manager_password_atomic_write",
                "manager_auth_environment_atomic_write",
                "manager_compose_overlay_atomic_write",
            ],
        },
        "runtime_controller": {
            "allowed_commands": [
                {
                    "name": "inspect_greenhouse_manager",
                    "argv": ["docker", "inspect", "greenhouse-manager"],
                    "mutation": False,
                },
                {
                    "name": "compose_recreate_greenhouse_manager",
                    "argv_template": [
                        "docker",
                        "compose",
                        "--project-name",
                        "<bound-project>",
                        "--project-directory",
                        "<bound-working-directory>",
                        "--file",
                        "<each-bound-config-file>",
                        "--file",
                        "<bound-manager-auth-overlay>",
                        "up",
                        "-d",
                        "--no-deps",
                        "--force-recreate",
                        "greenhouse-manager",
                    ],
                    "mutation": True,
                },
            ],
            "mosquitto_target_allowed": False,
            "homeassistant_target_allowed": False,
            "node_target_allowed": False,
        },
        "postactivation": {
            "existing_homeassistant_entities_refresh_required": True,
        },
        "rollback": {
            "rollback_failure_is_terminal": True,
        },
        "contract_review_complete": True,
        "production_transaction_adapter_contract_available": True,
        "production_transaction_adapters_installed": False,
        "authorization_claimed": False,
        "claim_enabled": False,
        "fresh_rollback_bound": False,
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
    document["adapter_contract_sha256"] = _digest(document)
    return document


def _write_adapter(tmp_path: Path, document: dict[str, object] | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "adapter-contract.json"
    path.write_text(_json(document or _adapter()) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _verifier(document: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "adapter_contract_sha256": document["adapter_contract_sha256"],
    }


def _build(tmp_path: Path) -> dict[str, object]:
    return build_manager_production_driver_contract(
        _write_adapter(tmp_path),
        adapter_verifier=_verifier,
    )


def test_builds_default_disabled_manager_driver_contract(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    verified = verify_manager_production_driver_contract(contract)

    assert verified["verified"] is True
    assert contract["production_manager_driver_contract_available"] is True
    assert contract["production_manager_driver_installed"] is False
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
    assert contract["preserve_anonymous"] is True
    assert contract["anonymous_closure_enabled"] is False
    assert contract["runtime_driver"]["container"] == "greenhouse-manager"
    assert contract["runtime_driver"]["mosquitto_target_allowed"] is False
    assert contract["filesystem_driver"]["host_paths_resolved"] is False
    assert contract["verification_driver"]["mqtt_probe_implementation_selected"] is False
    assert contract["fresh_rollback_driver"]["fresh_rollback_bound"] is False
    assert all(
        all(value is False for value in method.values())
        for method in contract["methods"].values()
    )


def test_contract_is_hash_bound_and_json_round_trippable(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    assert len(contract["driver_contract_sha256"]) == 64
    parsed = json.loads(json.dumps(contract))
    assert verify_manager_production_driver_contract(parsed)["verified"] is True


def test_rejects_adapter_safety_or_command_scope_drift(tmp_path: Path) -> None:
    adapter = _adapter()
    adapter["apply_enabled"] = True
    path = _write_adapter(tmp_path, adapter)
    with pytest.raises(
        ManagerIdentityProductionDriverContractError,
        match="safety flag failed: apply_enabled",
    ):
        build_manager_production_driver_contract(path, adapter_verifier=_verifier)

    adapter = _adapter()
    adapter["runtime_controller"]["mosquitto_target_allowed"] = True
    path = _write_adapter(tmp_path, adapter)
    with pytest.raises(
        ManagerIdentityProductionDriverContractError,
        match="runtime scope drifted",
    ):
        build_manager_production_driver_contract(path, adapter_verifier=_verifier)


def test_rejects_private_file_and_driver_capability_tampering(tmp_path: Path) -> None:
    path = _write_adapter(tmp_path)
    path.chmod(0o644)
    with pytest.raises(
        ManagerIdentityProductionDriverContractError,
        match="not mode 0600",
    ):
        build_manager_production_driver_contract(path, adapter_verifier=_verifier)

    contract = _build(tmp_path / "tamper")
    contract["methods"]["recreate_manager"]["docker_mutation_capability"] = True
    with pytest.raises(
        ManagerIdentityProductionDriverContractError,
        match="fingerprint does not match",
    ):
        verify_manager_production_driver_contract(contract)


def test_execution_entrypoint_is_unconditionally_disabled() -> None:
    with pytest.raises(
        ManagerIdentityProductionDriverDisabledError,
        match="not installed",
    ):
        execute_manager_production_driver_contract()


def test_cli_exposes_no_execute_claim_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_manager_identity_migration_production_driver_contract.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "adapter_contract_file" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
