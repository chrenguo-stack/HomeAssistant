from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import n3w_t1_maintenance_transaction as tx  # noqa: E402


def plan():
    return {"kind": "unit-test", "compose_policy": "before-after-only"}


def binding(**overrides):
    value = {
        "transaction_id": "txn-e03-successor-0001",
        "authorization_id_sha256": "1" * 64,
        "host_binding_sha256": "2" * 64,
        "current_release_id": "3" * 64,
        "target_release_id": "4" * 64,
        "artifact_sha256": "5" * 64,
        "executor_source_head": "6" * 40,
        "executor_blob": "7" * 40,
        "module_set_sha256": "8" * 64,
        "plan_sha256": tx.sha256_bytes(tx.canonical_bytes(plan())),
        "scope": ("compose_publish", "service_stop", "service_start", "acceptance"),
    }
    value.update(overrides)
    return tx.MaintenanceBinding(**value)


def document():
    return tx.new_transaction(
        binding(),
        predecessor_sha256="7" * 64,
        before={"compose": "8" * 64},
        intended_after={"compose": "9" * 64},
        plan=plan(),
    )


def claimed():
    ready = tx.claim_authorization(tx.mark_ready(document()))
    return tx.begin_apply(ready)


def test_transaction_lifecycle_happy_path() -> None:
    value = document()
    assert value["state"] == "PREPARING"
    value = tx.mark_ready(value)
    assert value["state"] == "READY"
    value = tx.claim_authorization(value)
    assert value["state"] == "READY"
    assert value["authorization_consumed"] is True
    value = tx.begin_apply(value)
    assert value["state"] == "APPLYING"
    value = tx.transition(
        value,
        "VERIFYING",
        operation="compose_published_and_services_started",
        observed_after={"compose": "9" * 64},
    )
    value = tx.transition(value, "COMMITTED", operation="mqtt_business_acceptance_pass")
    assert value["state"] == "COMMITTED"
    assert value["replay_allowed"] is False


@pytest.mark.parametrize(
    "field",
    [
        "transaction_id",
        "authorization_id_sha256",
        "host_binding_sha256",
        "current_release_id",
        "target_release_id",
        "artifact_sha256",
        "executor_source_head",
        "executor_blob",
        "module_set_sha256",
        "plan_sha256",
        "scope",
    ],
)
def test_b1_mutation_binding_rejects_any_binding_drift(field: str) -> None:
    value = claimed()
    expected = binding()
    replacement = {
        "transaction_id": "txn-e03-successor-9999",
        "authorization_id_sha256": "a" * 64,
        "host_binding_sha256": "b" * 64,
        "current_release_id": "c" * 64,
        "target_release_id": "d" * 64,
        "artifact_sha256": "e" * 64,
        "executor_source_head": "f" * 40,
        "executor_blob": "a" * 40,
        "module_set_sha256": "b" * 64,
        "plan_sha256": "c" * 64,
        "scope": ("compose_publish",),
    }[field]
    kwargs = expected.to_dict()
    kwargs["scope"] = tuple(kwargs["scope"])
    kwargs[field] = replacement
    wrong = tx.MaintenanceBinding(**kwargs)
    with pytest.raises(tx.MaintenanceTransactionError, match="mutation_binding_mismatch"):
        tx.require_mutation_binding(value, wrong, action="compose_publish")


def test_b1_requires_consumed_authorization() -> None:
    value = tx.mark_ready(document())
    with pytest.raises(tx.MaintenanceTransactionError, match="authorization_not_consumed"):
        tx.require_mutation_binding(
            value,
            binding(),
            action="compose_publish",
            allowed_states={"READY"},
        )


def test_b1_scope_is_exact() -> None:
    with pytest.raises(tx.MaintenanceTransactionError, match="mutation_scope_forbidden"):
        tx.require_mutation_binding(claimed(), binding(), action="db_rewrite")


def test_b2_compose_before_after_unknown_classification() -> None:
    before, after = "1" * 64, "2" * 64
    assert tx.compose_state(before, after, before) == "BEFORE"
    assert tx.compose_state(before, after, after) == "AFTER"
    assert tx.compose_state(before, after, "3" * 64) == "UNKNOWN"


def test_b2_unknown_compose_never_publishable() -> None:
    with pytest.raises(tx.MaintenanceTransactionError, match="compose_unknown_blocked"):
        tx.require_compose_publishable("1" * 64, "2" * 64, "3" * 64)


def test_b2_unknown_compose_never_rollbackable() -> None:
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="rollback_compose_unknown_blocked",
    ):
        tx.require_compose_rollbackable("1" * 64, "2" * 64, "3" * 64)


def test_recovery_only_converges_to_before_after_or_blocked() -> None:
    value = claimed()
    assert tx.recovery_disposition(value, {"compose": "8" * 64}) == "BEFORE"
    assert tx.recovery_disposition(value, {"compose": "9" * 64}) == "AFTER"
    assert tx.recovery_disposition(value, {"compose": "a" * 64}) == "BLOCKED"


def test_predecessor_evidence_is_immutable(tmp_path: Path) -> None:
    path = tmp_path / "predecessor.json"
    path.write_bytes(b"old evidence\n")
    expected = tx.sha256_file(path)
    tx.assert_predecessor_immutable(path, expected)
    path.write_bytes(b"changed\n")
    with pytest.raises(tx.MaintenanceTransactionError, match="predecessor_evidence_changed"):
        tx.assert_predecessor_immutable(path, expected)


def test_second_active_transaction_is_rejected() -> None:
    first = document()
    second = tx.new_transaction(
        binding(transaction_id="txn-e03-successor-0002"),
        predecessor_sha256="7" * 64,
        before={"compose": "8" * 64},
        intended_after={"compose": "9" * 64},
        plan=plan(),
    )
    with pytest.raises(tx.MaintenanceTransactionError, match="other_active_transaction"):
        tx.ensure_no_other_active([first, second], transaction_id=first["transaction_id"])


def test_transaction_store_is_generation_checked_and_durable(tmp_path: Path) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    value = document()
    store.create(value)
    loaded = store.load()
    assert loaded == value

    ready = tx.mark_ready(loaded)
    store.save(ready, expected_generation=loaded["generation"])
    assert store.load()["state"] == "READY"

    applying = tx.claim_authorization(store.load())
    with pytest.raises(tx.MaintenanceTransactionError, match="transaction_generation_conflict"):
        store.save(applying, expected_generation=1)


def test_transaction_store_rejects_id_change(tmp_path: Path) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    value = document()
    store.create(value)
    changed = tx.mark_ready(value)
    changed["transaction_id"] = "txn-e03-successor-9999"
    with pytest.raises(tx.MaintenanceTransactionError, match="transaction_id_changed"):
        store.save(changed, expected_generation=value["generation"])


def test_terminal_transaction_cannot_reenter_apply() -> None:
    value = claimed()
    value = tx.transition(value, "VERIFYING", operation="verify")
    value = tx.transition(value, "COMMITTED", operation="commit")
    with pytest.raises(tx.MaintenanceTransactionError, match="transition_invalid"):
        tx.transition(value, "APPLYING", operation="replay")


def test_transaction_json_contains_no_raw_authorization_id() -> None:
    value = document()
    raw = json.dumps(value, sort_keys=True)
    assert "authorization_id_sha256" in raw
    assert "N3W_" not in raw


def test_operation_intent_and_completion_are_durable_records() -> None:
    value = claimed()
    intent = tx.begin_operation(
        value,
        operation_type="compose_publish",
        before_fingerprint="8" * 64,
        intended_after_fingerprint="9" * 64,
    )
    pending = tx.pending_operation(intent)
    assert pending is not None
    assert pending["status"] == "INTENT"
    assert pending["operation_seq"] == 1

    complete = tx.finish_operation(
        intent,
        observed_after_fingerprint="9" * 64,
    )
    assert tx.pending_operation(complete) is None
    assert complete["operations"][-1]["status"] == "COMPLETE"
    assert complete["operations"][-1]["observed_after_fingerprint"] == "9" * 64


def test_second_operation_cannot_start_while_intent_pending() -> None:
    value = tx.begin_operation(
        claimed(),
        operation_type="service_stop",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
    )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="operation_intent_already_pending",
    ):
        tx.begin_operation(
            value,
            operation_type="compose_publish",
            before_fingerprint="8" * 64,
            intended_after_fingerprint="9" * 64,
        )


def test_operation_sequence_is_independent_from_state_transitions() -> None:
    value = document()
    value = tx.mark_ready(value)
    value = tx.claim_authorization(value)
    assert value["operation_seq"] == 0
    assert value["operations"] == []


def test_transition_rejects_pending_operation() -> None:
    value = tx.begin_operation(
        claimed(),
        operation_type="compose_publish",
        before_fingerprint="8" * 64,
        intended_after_fingerprint="9" * 64,
    )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="transition_pending_operation",
    ):
        tx.transition(value, "VERIFYING", operation="unsafe_phase_advance")


def test_plan_tampering_is_rejected() -> None:
    value = document()
    value["plan"]["compose_policy"] = "tampered"
    with pytest.raises(tx.MaintenanceTransactionError, match="plan_binding_mismatch"):
        tx.validate_transaction(value)
