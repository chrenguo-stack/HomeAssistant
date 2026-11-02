from __future__ import annotations

import errno
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


def ready_claimed_document():
    return tx.claim_authorization(tx.mark_ready(document()))


def test_abort_claimed_ready_before_apply_happy_path() -> None:
    value = ready_claimed_document()
    result = tx.abort_claimed_ready_before_apply(
        value,
        reason="SOURCE_REPAIR_BEFORE_APPLY",
    )
    assert result["state"] == "ABORTED"
    assert result["authorization_consumed"] is True
    assert result["replay_allowed"] is False
    assert result["operation_seq"] == 0
    assert result["operations"] == []
    assert result["observed_after"] == {}
    assert result["last_operation"] == "retired_before_apply"
    assert result["last_reason"] == "SOURCE_REPAIR_BEFORE_APPLY"


@pytest.mark.parametrize(
    "mutator,error",
    [
        (
            lambda value: tx.begin_apply(value),
            "abort_before_apply_state_invalid",
        ),
        (
            lambda value: {**value, "authorization_consumed": False},
            "abort_before_apply_authorization_not_consumed",
        ),
    ],
)
def test_abort_claimed_ready_before_apply_rejects_ineligible_state(
    mutator,
    error: str,
) -> None:
    value = mutator(ready_claimed_document())
    with pytest.raises(tx.MaintenanceTransactionError, match=error):
        tx.abort_claimed_ready_before_apply(
            value,
            reason="SOURCE_REPAIR_BEFORE_APPLY",
        )


def test_abort_claimed_ready_before_apply_rejects_operation_history() -> None:
    value = tx.begin_apply(ready_claimed_document())
    value = tx.begin_operation(
        value,
        operation_type="service_stop",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
    )
    value["state"] = "READY"
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="abort_before_apply_operation_history_present",
    ):
        tx.abort_claimed_ready_before_apply(
            value,
            reason="SOURCE_REPAIR_BEFORE_APPLY",
        )


def test_abort_claimed_ready_before_apply_rejects_observed_after() -> None:
    value = ready_claimed_document()
    value["observed_after"] = {"compose": "8" * 64}
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="abort_before_apply_observed_after_present",
    ):
        tx.abort_claimed_ready_before_apply(
            value,
            reason="SOURCE_REPAIR_BEFORE_APPLY",
        )


def test_abort_claimed_ready_before_apply_rejects_apply_session() -> None:
    value = tx.record_execution_session(
        ready_claimed_document(),
        "execution-session-retirement-test",
        action="apply",
    )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="abort_before_apply_execution_session_present",
    ):
        tx.abort_claimed_ready_before_apply(
            value,
            reason="SOURCE_REPAIR_BEFORE_APPLY",
        )


@pytest.mark.parametrize(
    "state",
    ["APPLYING", "VERIFYING", "ROLLING_BACK"],
)
def test_abort_claimed_ready_before_apply_rejects_started_states(
    state: str,
) -> None:
    value = ready_claimed_document()
    value = tx.begin_apply(value)
    if state in {"VERIFYING", "ROLLING_BACK"}:
        value = tx.transition(
            value,
            "VERIFYING",
            operation="test_verify",
        )
    if state == "ROLLING_BACK":
        value = tx.transition(
            value,
            "ROLLING_BACK",
            operation="test_rollback",
        )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="abort_before_apply_state_invalid",
    ):
        tx.abort_claimed_ready_before_apply(
            value,
            reason="SOURCE_REPAIR_BEFORE_APPLY",
        )


def test_aborted_transaction_cannot_reenter_apply() -> None:
    value = tx.abort_claimed_ready_before_apply(
        ready_claimed_document(),
        reason="SOURCE_REPAIR_BEFORE_APPLY",
    )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="begin_apply_state_invalid",
    ):
        tx.begin_apply(value)


def test_aborted_transaction_is_not_an_active_transaction() -> None:
    aborted = tx.abort_claimed_ready_before_apply(
        ready_claimed_document(),
        reason="SOURCE_REPAIR_BEFORE_APPLY",
    )
    tx.ensure_no_other_active(
        [aborted],
        transaction_id="txn-e03-successor-replacement-0002",
    )


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


def test_execution_session_is_distinct_and_idempotent_per_action() -> None:
    value = tx.claim_authorization(tx.mark_ready(document()))
    first = tx.record_execution_session(
        value,
        "execution-session-0001",
        action="apply",
    )
    repeated = tx.record_execution_session(
        first,
        "execution-session-0001",
        action="apply",
    )
    assert repeated == first
    assert repeated["authorization_id_sha256"] == value["authorization_id_sha256"]
    assert repeated["transaction_id"] == value["transaction_id"]
    assert len(repeated["execution_sessions"]) == 1


def test_execution_session_cannot_be_reused_for_different_action() -> None:
    value = tx.record_execution_session(
        tx.claim_authorization(tx.mark_ready(document())),
        "execution-session-0002",
        action="apply",
    )
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="execution_session_reused",
    ):
        tx.record_execution_session(
            value,
            "execution-session-0002",
            action="rollback",
        )


@pytest.mark.parametrize(
    "field",
    [
        "authorization_id_sha256",
        "host_binding_sha256",
        "current_release_id",
        "target_release_id",
        "artifact_sha256",
        "executor_source_head",
        "executor_blob",
        "module_set_sha256",
        "plan_sha256",
        "predecessor_sha256",
    ],
)
def test_store_rejects_immutable_authority_drift(
    tmp_path: Path,
    field: str,
) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    original = document()
    store.create(original)
    changed = tx.mark_ready(original)
    changed[field] = (
        "f" * 40
        if field in {"executor_source_head", "executor_blob"}
        else "f" * 64
    )
    if field == "plan_sha256":
        changed["plan"] = {"kind": "changed", "compose_policy": "before-after-only"}
        changed[field] = tx.sha256_bytes(tx.canonical_bytes(changed["plan"]))
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="transaction_immutable_binding_changed",
    ):
        store.save(changed, expected_generation=original["generation"])


def test_store_rejects_direct_state_jump(tmp_path: Path) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    original = document()
    store.create(original)
    changed = dict(original)
    changed["state"] = "COMMITTED"
    changed["generation"] += 1
    changed["last_operation"] = "unsafe_direct_commit"
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="transaction_state_jump_invalid",
    ):
        store.save(changed, expected_generation=original["generation"])


def test_store_rejects_authorization_consumed_revert(tmp_path: Path) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    value = tx.claim_authorization(tx.mark_ready(document()))
    store.create(value)
    changed = tx.begin_apply(value)
    changed["authorization_consumed"] = False
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="authorization_consumed_reverted",
    ):
        store.save(changed, expected_generation=value["generation"])


def test_transaction_rejects_nonterminal_intent_in_operation_history() -> None:
    value = claimed()
    first = tx.begin_operation(
        value,
        operation_type="service_stop",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
    )
    first["operations"].append(
        {
            "operation_seq": 2,
            "operation_type": "compose_publish",
            "before_fingerprint": "3" * 64,
            "intended_after_fingerprint": "4" * 64,
            "observed_after_fingerprint": "4" * 64,
            "status": "COMPLETE",
            "last_error_code": None,
        }
    )
    first["operation_seq"] = 2
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="operation_intent_position_invalid",
    ):
        tx.validate_transaction(first)


def test_transaction_rejects_completed_operation_without_observation() -> None:
    value = claimed()
    value["operations"] = [
        {
            "operation_seq": 1,
            "operation_type": "compose_publish",
            "before_fingerprint": "1" * 64,
            "intended_after_fingerprint": "2" * 64,
            "observed_after_fingerprint": None,
            "status": "COMPLETE",
            "last_error_code": None,
        }
    ]
    value["operation_seq"] = 1
    with pytest.raises(
        tx.MaintenanceTransactionError,
        match="operation_observation_missing",
    ):
        tx.validate_transaction(value)


def test_transaction_create_fsync_failure_does_not_leave_claimable_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    original_fsync = tx.os.fsync
    calls = {"count": 0}

    def failing_fsync(fd: int) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError(errno.ENOSPC, "simulated fsync ENOSPC")
        original_fsync(fd)

    monkeypatch.setattr(tx.os, "fsync", failing_fsync)
    with pytest.raises(OSError):
        store.create(document())
    assert path.exists() is False


def test_transaction_save_disk_full_before_replace_preserves_old_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    original = document()
    store.create(original)

    def no_space(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "simulated disk full")

    monkeypatch.setattr(tx.tempfile, "mkstemp", no_space)
    ready = tx.mark_ready(original)
    with pytest.raises(OSError):
        store.save(ready, expected_generation=original["generation"])
    assert store.load() == original


def test_transaction_save_fsync_failure_before_replace_preserves_old_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "txn.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    original = document()
    store.create(original)
    ready = tx.mark_ready(original)

    original_fsync = tx.os.fsync
    calls = {"count": 0}

    def failing_fsync(fd: int) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError(errno.ENOSPC, "simulated temp fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(tx.os, "fsync", failing_fsync)
    with pytest.raises(OSError):
        store.save(ready, expected_generation=original["generation"])
    assert store.load() == original
