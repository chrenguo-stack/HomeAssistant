from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_maintenance_transaction as tx  # noqa: E402
import n3w_t1_r10_e03_blocked_prepublish_predecessor_recovery as recovery  # noqa: E402
import n3w_t1_r10_e03_successor_recovery as successor  # noqa: E402


def _target() -> dict:
    plan = {
        "service_before_fingerprint": "1" * 64,
        "service_stopped_fingerprint": "2" * 64,
        "service_running_fingerprint": "3" * 64,
        "deployment_before_fingerprint": "4" * 64,
        "deployment_candidate_fingerprint": "5" * 64,
        "manager_predecessor_container_id": "old-manager",
        "services_nrestarts": 0,
        "ha_mqtt_sha256": "6" * 64,
        "broker_baseline": {
            "container_id": "broker",
            "image_id": successor.BROKER_IMAGE_ID,
            "image_ref": successor.BROKER_IMAGE,
            "network_mode": "n3wfc4-private",
            "restart_count": 0,
            "started_at": "2026-10-30T14:04:04.311501262Z",
        },
        "preauth_ledger": {"mode": "RECONCILED_TERMINAL"},
    }
    binding = tx.MaintenanceBinding(
        transaction_id="txn-blocked-prepublish-0001",
        authorization_id_sha256="7" * 64,
        host_binding_sha256="8" * 64,
        current_release_id="9" * 64,
        target_release_id="a" * 64,
        artifact_sha256=successor.TARGET_ARTIFACT_SHA256,
        executor_source_head=recovery.EXPECTED_TARGET_EXECUTOR_SOURCE_HEAD,
        executor_blob="b" * 40,
        module_set_sha256="c" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=("activation_gate_install", "service_stop"),
    )
    value = tx.new_transaction(
        binding,
        predecessor_sha256="d" * 64,
        before={"deployment_inputs": "4" * 64},
        intended_after={"deployment_inputs": "5" * 64},
        plan=plan,
    )
    value = tx.mark_ready(value)
    value = tx.claim_authorization(value)
    gate_intent = tx.begin_operation(
        value,
        operation_type="activation_gate_install",
        before_fingerprint="e" * 64,
        intended_after_fingerprint="e" * 64,
        allowed_states={"READY"},
    )
    value = tx.finish_operation(
        gate_intent,
        observed_after_fingerprint="e" * 64,
    )
    value = tx.begin_apply(value)
    stop_intent = tx.begin_operation(
        value,
        operation_type="service_stop",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
        allowed_states={"APPLYING"},
    )
    value = tx.finish_operation(
        stop_intent,
        observed_after_fingerprint="f" * 64,
        status="BLOCKED",
        error_code="application_owner_not_stopped",
    )
    return tx.transition(
        value,
        "BLOCKED",
        operation="blocked",
        reason="operation_reality_unknown",
    )


def _plan() -> dict:
    return {
        "schema": recovery.PLAN_SCHEMA,
        "reason": recovery.REASON,
        "target_transaction_id_sha256": "1" * 64,
        "target_transaction_sha256": "2" * 64,
        "target_generation": 11,
        "target_operation_seq": 2,
        "target_executor_source_head": recovery.EXPECTED_TARGET_EXECUTOR_SOURCE_HEAD,
        "target_artifact_sha256": successor.TARGET_ARTIFACT_SHA256,
        "deployment_before_fingerprint": "3" * 64,
        "service_stopped_fingerprint": "4" * 64,
        "service_running_fingerprint": "5" * 64,
        "manager_predecessor_container_id": "old-manager",
        "services_nrestarts": 0,
        "ha_mqtt_sha256": "6" * 64,
        "broker_baseline": {},
        "preauth_ledger": {},
        "raw_service_active_state": "failed",
        "gate_source_sha256_before": "7" * 64,
        "gate_source_sha256_after": "8" * 64,
        "recovery_executor_source_head": "9" * 40,
        "recovery_executor_blob": "a" * 40,
        "recovery_module_set_sha256": "b" * 64,
        "product_mutation": False,
        "service_stop_start": True,
        "docker_mutation": True,
        "board_access": False,
    }


def test_exact_blocked_prepublish_target_is_eligible() -> None:
    value = recovery._assert_target_shape(_target())
    assert value["state"] == "BLOCKED"
    assert value["operation_seq"] == 2
    assert value["operations"][1]["operation_type"] == "service_stop"
    assert value["operations"][1]["last_error_code"] == "application_owner_not_stopped"


def test_target_with_candidate_publish_is_not_eligible() -> None:
    value = _target()
    value["operations"][1]["operation_type"] = "deployment_inputs_publish"
    with pytest.raises(
        recovery.RecoveryError,
        match="target_service_stop_operation_invalid",
    ):
        recovery._assert_target_shape(value)


def test_claimed_recovery_record_is_one_shot_and_scope_bound() -> None:
    plan = _plan()
    record = recovery._record_from_plan(
        plan=plan,
        recovery_id="recovery-blocked-prepublish-0001",
        authorization_id=(
            recovery.AUTHORIZATION_PREFIX + "20261031_01"
        ),
        execution_session_id="session-recovery-claim-0001",
    )
    validated = recovery.validate_record(record)
    assert validated["state"] == "CLAIMED"
    assert validated["authorization_consumed"] is True
    assert validated["replay_allowed"] is False
    assert validated["product_mutation"] is False
    assert validated["service_stop_start"] is True
    assert validated["docker_mutation"] is True
    assert validated["board_access"] is False


def test_recovery_record_scope_tamper_is_rejected() -> None:
    plan = _plan()
    record = recovery._record_from_plan(
        plan=plan,
        recovery_id="recovery-blocked-prepublish-0001",
        authorization_id=(
            recovery.AUTHORIZATION_PREFIX + "20261031_01"
        ),
        execution_session_id="session-recovery-claim-0001",
    )
    record["product_mutation"] = True
    with pytest.raises(recovery.RecoveryError, match="recovery_scope_invalid"):
        recovery.validate_record(record)


@pytest.mark.parametrize("active", ["failed", "inactive"])
def test_stopped_semantic_accepts_only_empty_owner(
    monkeypatch: pytest.MonkeyPatch,
    active: str,
) -> None:
    monkeypatch.setattr(
        successor,
        "_service_semantic",
        lambda: {
            "active": active,
            "enabled": "enabled",
            "manager_count": 0,
            "homeassistant_count": 0,
        },
    )
    assert recovery._raw_stopped_semantic()["active"] == active


def test_stopped_semantic_rejects_partial_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        successor,
        "_service_semantic",
        lambda: {
            "active": "failed",
            "enabled": "enabled",
            "manager_count": 1,
            "homeassistant_count": 0,
        },
    )
    with pytest.raises(
        recovery.RecoveryError,
        match="application_owner_not_stopped",
    ):
        recovery._raw_stopped_semantic()


def test_blocked_recovery_record_is_terminal_no_replay() -> None:
    record = recovery._record_from_plan(
        plan=_plan(),
        recovery_id="recovery-blocked-prepublish-0001",
        authorization_id=recovery.AUTHORIZATION_PREFIX + "20261031_01",
        execution_session_id="session-recovery-claim-0001",
    )
    blocked = recovery._transition(
        record,
        state="BLOCKED",
        operation="recovery_blocked",
        reason="runtime_unproven",
    )
    assert blocked["state"] == "BLOCKED"
    assert blocked["authorization_consumed"] is True
    assert blocked["replay_allowed"] is False
    assert blocked["generation"] == 2
