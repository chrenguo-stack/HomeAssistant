from __future__ import annotations

import copy

import pytest

import n3w_t1_maintenance_transaction as tx
import n3w_t1_r10_e03_blocked_postpublish_predecessor_recovery as recovery
import n3w_t1_r10_e03_successor_recovery as successor


def blocked_target() -> dict:
    plan = {
        "deployment_before_fingerprint": "a" * 64,
        "deployment_candidate_fingerprint": "b" * 64,
        "service_before_fingerprint": "c" * 64,
        "service_stopped_fingerprint": "d" * 64,
        "service_running_fingerprint": "c" * 64,
    }
    binding = tx.MaintenanceBinding(
        transaction_id=recovery.EXPECTED_TARGET_TRANSACTION_ID,
        authorization_id_sha256="1" * 64,
        host_binding_sha256="2" * 64,
        current_release_id="3" * 64,
        target_release_id="4" * 64,
        artifact_sha256=successor.TARGET_ARTIFACT_SHA256,
        executor_source_head=recovery.EXPECTED_TARGET_EXECUTOR_SOURCE_HEAD,
        executor_blob="5" * 40,
        module_set_sha256="6" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=("activation_gate_install", "service_stop", "deployment_inputs_publish", "service_start"),
    )
    value = tx.new_transaction(
        binding,
        predecessor_sha256="7" * 64,
        before={"deployment_inputs": "a" * 64},
        intended_after={"deployment_inputs": "b" * 64},
        plan=plan,
    )
    value = tx.mark_ready(value)
    value = tx.claim_authorization(value)
    value = tx.record_execution_session(value, "session-claim-0001", action="claim")
    value = tx.record_execution_session(value, "session-apply-0001", action="apply")
    intent = tx.begin_operation(
        value,
        operation_type="activation_gate_install",
        before_fingerprint="8" * 64,
        intended_after_fingerprint="8" * 64,
        allowed_states={"READY"},
    )
    value = tx.finish_operation(intent, observed_after_fingerprint="8" * 64)
    value = tx.begin_apply(value)
    intent = tx.begin_operation(
        value,
        operation_type="service_stop",
        before_fingerprint="c" * 64,
        intended_after_fingerprint="d" * 64,
        allowed_states={"APPLYING"},
    )
    value = tx.finish_operation(intent, observed_after_fingerprint="d" * 64)
    intent = tx.begin_operation(
        value,
        operation_type="deployment_inputs_publish",
        before_fingerprint="a" * 64,
        intended_after_fingerprint="b" * 64,
        allowed_states={"APPLYING"},
    )
    value = tx.finish_operation(intent, observed_after_fingerprint="b" * 64)
    value = tx.transition(
        value,
        "VERIFYING",
        operation="candidate_published_owner_controlled",
        observed_after={"deployment_inputs": "b" * 64},
    )
    intent = tx.begin_operation(
        value,
        operation_type="service_start",
        before_fingerprint="d" * 64,
        intended_after_fingerprint="c" * 64,
        allowed_states={"VERIFYING"},
    )
    value = tx.finish_operation(
        intent,
        observed_after_fingerprint="d" * 64,
        status="BLOCKED",
        error_code="operation_poststate_unproven",
    )
    return tx.transition(
        value,
        "BLOCKED",
        operation="blocked",
        reason="operation_poststate_unproven",
    )


def record(state: str = "CLAIMED") -> dict:
    plan = {
        "schema": recovery.PLAN_SCHEMA,
        "reason": recovery.REASON,
        "target_transaction_id_sha256": "1" * 64,
        "target_transaction_sha256": "2" * 64,
        "target_generation": recovery.EXPECTED_TARGET_GENERATION,
        "target_operation_seq": recovery.EXPECTED_TARGET_OPERATION_SEQ,
        "recovery_executor_source_head": "3" * 40,
        "recovery_executor_blob": "4" * 40,
        "recovery_module_set_sha256": "5" * 64,
        "product_mutation": True,
        "service_stop_start": True,
        "docker_mutation": True,
        "board_access": False,
    }
    return {
        "schema": recovery.SCHEMA,
        "recovery_id": "postpublish-recovery-0001",
        "recovery_id_sha256": recovery.sha_text("postpublish-recovery-0001"),
        "authorization_id_sha256": "6" * 64,
        "execution_session_id_sha256": "7" * 64,
        "plan_sha256": recovery.sha_bytes(recovery.canonical(plan)),
        "plan": plan,
        "executor_source_head": "3" * 40,
        "executor_blob": "4" * 40,
        "module_set_sha256": "5" * 64,
        "target_transaction_id_sha256": "1" * 64,
        "target_transaction_sha256": "2" * 64,
        "target_generation": recovery.EXPECTED_TARGET_GENERATION,
        "target_operation_seq": recovery.EXPECTED_TARGET_OPERATION_SEQ,
        "reason": recovery.REASON,
        "product_mutation": True,
        "service_stop_start": True,
        "docker_mutation": True,
        "board_access": False,
        "state": state,
        "authorization_consumed": True,
        "replay_allowed": False,
        "generation": 1 if state == "CLAIMED" else 2,
        "last_operation": {
            "CLAIMED": "authorization_claimed",
            "COMMITTED": "predecessor_runtime_restored",
            "BLOCKED": "recovery_blocked",
        }[state],
        "last_reason": "test" if state == "BLOCKED" else None,
    }


def test_exact_live_failure_shape() -> None:
    value = blocked_target()
    assert value["generation"] == recovery.EXPECTED_TARGET_GENERATION
    assert value["operation_seq"] == recovery.EXPECTED_TARGET_OPERATION_SEQ
    assert recovery._assert_target_shape(value) == value


def test_target_shape_rejects_drift() -> None:
    value = blocked_target()
    value["operations"][3]["status"] = "FAILED"
    with pytest.raises(recovery.RecoveryError, match="target_operation_shape_invalid"):
        recovery._assert_target_shape(value)


@pytest.mark.parametrize("state", ["CLAIMED", "COMMITTED", "BLOCKED"])
def test_record_contract(state: str) -> None:
    assert recovery.validate_record(record(state))["state"] == state


def test_record_scope_is_exact() -> None:
    value = record()
    value["product_mutation"] = False
    with pytest.raises(recovery.RecoveryError, match="recovery_scope_invalid"):
        recovery.validate_record(value)


def test_candidate_stopped_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = {
        "deployment_before_fingerprint": "a" * 64,
        "deployment_candidate_fingerprint": "b" * 64,
        "service_stopped_fingerprint": "c" * 64,
        "gate_source_sha256_before": "d" * 64,
        "gate_source_sha256_after": "e" * 64,
    }
    monkeypatch.setattr(recovery.e03, "_deployment_reality", lambda _plan: "b" * 64)
    monkeypatch.setattr(recovery.e03, "_service_fingerprint", lambda: "c" * 64)
    monkeypatch.setattr(recovery, "sha_file", lambda _path: "d" * 64)
    assert recovery._classify_recovery_reality(plan, {}) == (
        "CANDIDATE_STOPPED_BEFORE_GATE",
        None,
    )


def test_unknown_deployment_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = {
        "deployment_before_fingerprint": "a" * 64,
        "deployment_candidate_fingerprint": "b" * 64,
        "service_stopped_fingerprint": "c" * 64,
        "gate_source_sha256_before": "d" * 64,
        "gate_source_sha256_after": "e" * 64,
    }
    monkeypatch.setattr(recovery.e03, "_deployment_reality", lambda _plan: "9" * 64)
    monkeypatch.setattr(recovery, "sha_file", lambda _path: "e" * 64)
    with pytest.raises(recovery.RecoveryError, match="recovery_deployment_reality_unknown"):
        recovery._classify_recovery_reality(plan, {})


def test_transition_is_one_shot() -> None:
    committed = recovery._transition(
        record(),
        state="COMMITTED",
        operation="predecessor_runtime_restored",
        reason=None,
    )
    assert committed["generation"] == 2
    with pytest.raises(recovery.RecoveryError, match="recovery_transition_state_invalid"):
        recovery._transition(
            committed,
            state="COMMITTED",
            operation="predecessor_runtime_restored",
            reason=None,
        )


def test_target_generation_is_frozen() -> None:
    value = copy.deepcopy(blocked_target())
    value["generation"] += 1
    with pytest.raises(recovery.RecoveryError, match="target_transaction_shape_invalid"):
        recovery._assert_target_shape(value)
