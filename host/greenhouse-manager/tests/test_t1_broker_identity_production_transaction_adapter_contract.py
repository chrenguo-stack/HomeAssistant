from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_production_transaction_adapter_contract import (
    BrokerIdentityProductionTransactionAdapterContractError,
    BrokerIdentityProductionTransactionAdapterDisabledError,
    build_production_transaction_adapter_contract,
    execute_production_transaction_adapter_contract,
    verify_production_transaction_adapter_contract,
)

PLAN_SHA = "a" * 64
AUTH_SHA = "b" * 64
BUNDLE_SHA = "c" * 64
DRIVER_SHA = "d" * 64
CONTRACT_SHA = "e" * 64
MOUNT_SHA = "f" * 64
MANIFEST_SHA = "1" * 64
PREFLIGHT_SHA = "2" * 64
HA_GATE_SHA = "3" * 64


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _plan() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-transaction-plan/1",
        "plan_sha256": PLAN_SHA,
        "authorization_document_sha256": AUTH_SHA,
        "bundle_sha256": BUNDLE_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
        "production_driver_preflight_sha256": PREFLIGHT_SHA,
        "homeassistant_target_gate_sha256": HA_GATE_SHA,
        "transaction_contract": {
            "authorization_claim_required": True,
            "authorization_claim_method": "same_filesystem_hardlink_then_unlink",
            "private_journal_required": True,
            "postactivation_audit_required": True,
            "rollback_mandatory_on_failure": True,
            "successful_activation_restart_count": 1,
            "rollback_may_require_additional_restart": True,
            "homeassistant_reconfigure_after_activation_only": True,
            "node_credential_delivery_after_activation_only": True,
            "anonymous_closure_forbidden": True,
        },
        "transaction_plan_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_transaction_adapters_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _build(tmp_path: Path) -> dict[str, object]:
    plan = _write_private(tmp_path / "plan.json", _plan())
    return build_production_transaction_adapter_contract(
        plan,
        plan_verifier=lambda _document: {
            "verified": True,
            "plan_sha256": PLAN_SHA,
        },
    )


def test_builds_strict_non_callable_adapter_contract(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    verified = verify_production_transaction_adapter_contract(contract)

    assert verified["verified"] is True
    assert contract["production_transaction_adapter_contract_available"] is True
    assert contract["production_transaction_adapters_installed"] is False
    assert contract["authorization_claimed"] is False
    assert contract["claim_enabled"] is False
    assert contract["production_executor_available"] is False
    assert contract["execution_enabled"] is False
    assert contract["apply_enabled"] is False
    assert contract["operator_action_authorized"] is True
    assert contract["ready_for_live_activation"] is False
    assert contract["current_services_modified"] is False
    assert contract["preserve_anonymous"] is True
    assert contract["anonymous_closure_enabled"] is False
    assert contract["secret_values_included"] is False
    assert contract["path_values_redacted"] is True
    assert contract["phase_order"] == [
        "authorization_claim",
        "runtime_revalidation",
        "snapshot",
        "mutation",
        "broker_restart",
        "dynamic_security_state_wait",
        "dynamic_security_request",
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
    assert contract["runtime_controller"]["allowed_commands"] == [
        {
            "name": "inspect_mosquitto",
            "argv": ["docker", "inspect", "mosquitto"],
            "mutation": False,
        },
        {
            "name": "restart_mosquitto",
            "argv": ["docker", "restart", "mosquitto"],
            "mutation": True,
        },
    ]
    assert contract["mqtt_control_transport"]["implementation"] == (
        "paho_mqtt_in_process"
    )


def test_contract_survives_json_round_trip(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    parsed = json.loads(json.dumps(contract))
    assert verify_production_transaction_adapter_contract(parsed)["verified"] is True


def test_rejects_plan_safety_drift(tmp_path: Path) -> None:
    document = _plan()
    document["claim_enabled"] = True
    plan = _write_private(tmp_path / "plan.json", document)

    with pytest.raises(
        BrokerIdentityProductionTransactionAdapterContractError,
        match="transaction plan safety flag failed: claim_enabled",
    ):
        build_production_transaction_adapter_contract(
            plan,
            plan_verifier=lambda _document: {
                "verified": True,
                "plan_sha256": PLAN_SHA,
            },
        )


def test_rejects_adapter_capability_tampering(tmp_path: Path) -> None:
    contract = _build(tmp_path)
    contract["adapters"]["mutation"]["host_write_capability"] = True

    with pytest.raises(
        BrokerIdentityProductionTransactionAdapterContractError,
        match="fingerprint does not match",
    ):
        verify_production_transaction_adapter_contract(contract)


def test_execution_entrypoint_is_unconditionally_disabled() -> None:
    with pytest.raises(
        BrokerIdentityProductionTransactionAdapterDisabledError,
        match="not installed",
    ):
        execute_production_transaction_adapter_contract()


def test_cli_exposes_no_claim_execute_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_production_transaction_adapter_contract.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "transaction_plan_file" in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
