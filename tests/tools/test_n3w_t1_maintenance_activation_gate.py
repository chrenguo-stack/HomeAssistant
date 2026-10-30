from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import n3w_t1_maintenance_activation_gate as gate  # noqa: E402
import n3w_t1_maintenance_transaction as tx  # noqa: E402


def _write(root: Path, name: str, state: str) -> Path:
    path = root / name
    path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA,
                "transaction_id": name.removesuffix(".json"),
                "state": state,
                "replay_allowed": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


@pytest.fixture
def private_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "transactions"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(gate, "_private_root", lambda path: None)
    original = gate._record

    def record(path: Path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != gate.SCHEMA:
            raise gate.GateError("transaction_record_schema_invalid")
        state = value.get("state")
        if state not in (
            gate.ACTIVE_BLOCKING_STATES
            | gate.ACTIVE_ALLOWING_STATES
            | gate.TERMINAL_STATES
        ):
            raise gate.GateError("transaction_record_state_invalid")
        if value.get("replay_allowed") is not False:
            raise gate.GateError("transaction_record_replay_invalid")
        return value

    monkeypatch.setattr(gate, "_record", record)
    return root


@pytest.mark.parametrize("state", sorted(gate.ACTIVE_BLOCKING_STATES))
def test_active_mutation_states_block(private_root: Path, state: str) -> None:
    _write(private_root, "tx.json", state)
    allowed, reason = gate.evaluate(private_root)
    assert allowed is False
    assert reason == "MAINTENANCE_BLOCKING"


@pytest.mark.parametrize("state", ["PREPARING", "READY"])
def test_non_mutating_active_states_allow_application_start(
    private_root: Path,
    state: str,
) -> None:
    _write(private_root, "tx.json", state)
    assert gate.evaluate(private_root) == (True, "MAINTENANCE_VERIFYING")


@pytest.mark.parametrize("state", sorted(gate.TERMINAL_STATES))
def test_terminal_transactions_do_not_block(
    private_root: Path,
    state: str,
) -> None:
    _write(private_root, "tx.json", state)
    assert gate.evaluate(private_root) == (True, "NO_ACTIVE_TRANSACTION")


def test_multiple_active_transactions_fail_closed(private_root: Path) -> None:
    _write(private_root, "a.json", "APPLYING")
    _write(private_root, "b.json", "VERIFYING")
    with pytest.raises(gate.GateError, match="multiple_active_transactions"):
        gate.evaluate(private_root)


def test_malformed_transaction_fails_closed(
    private_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = private_root / "bad.json"
    bad.write_text("not-json\n", encoding="utf-8")
    bad.chmod(0o600)
    monkeypatch.undo()
    monkeypatch.setattr(gate, "_private_root", lambda path: None)
    monkeypatch.setattr(
        gate,
        "_record",
        lambda _path: (_ for _ in ()).throw(
            gate.GateError("transaction_record_json_invalid")
        ),
    )
    with pytest.raises(gate.GateError, match="transaction_record_json_invalid"):
        gate.evaluate(private_root)


def test_absent_transaction_root_allows_start(tmp_path: Path) -> None:
    assert gate.evaluate(tmp_path / "absent") == (True, "NO_TRANSACTION_ROOT")


def _valid_transaction(state: str) -> dict:
    plan = {"kind": "activation-gate-test"}
    binding = tx.MaintenanceBinding(
        transaction_id="txn-activation-gate-0001",
        authorization_id_sha256="1" * 64,
        host_binding_sha256="2" * 64,
        current_release_id="3" * 64,
        target_release_id="4" * 64,
        artifact_sha256="5" * 64,
        executor_source_head="6" * 40,
        executor_blob="7" * 40,
        module_set_sha256="8" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=("compose_publish",),
    )
    value = tx.new_transaction(
        binding,
        predecessor_sha256="9" * 64,
        before={"compose": "a" * 64},
        intended_after={"compose": "b" * 64},
        plan=plan,
    )
    if state == "PREPARING":
        return value
    value = tx.mark_ready(value)
    value = tx.claim_authorization(value)
    if state == "READY":
        return value
    value = tx.begin_apply(value)
    if state == "APPLYING":
        return value
    if state == "BLOCKED":
        return tx.transition(
            value,
            "BLOCKED",
            operation="blocked",
            reason="unknown_reality",
        )
    publish = tx.begin_operation(
        value,
        operation_type="compose_publish",
        before_fingerprint="a" * 64,
        intended_after_fingerprint="b" * 64,
        allowed_states={"APPLYING"},
    )
    value = tx.finish_operation(
        publish,
        observed_after_fingerprint="b" * 64,
    )
    value = tx.transition(
        value,
        "VERIFYING",
        operation="candidate_published_owner_controlled",
        observed_after={"compose": "b" * 64},
    )
    if state == "VERIFYING":
        return value
    value = tx.transition(
        value,
        "ROLLING_BACK",
        operation="rollback_begin",
        reason="test",
    )
    if state == "ROLLING_BACK":
        return value
    value = tx.transition(
        value,
        "ROLLED_BACK",
        operation="rollback_complete",
        reason="test",
        observed_after={"compose": "a" * 64},
    )
    return value


def test_gate_schema_keys_match_transaction_module() -> None:
    assert gate.TRANSACTION_KEYS == tx.TRANSACTION_KEYS


@pytest.mark.parametrize(
    "state",
    ["PREPARING", "READY", "APPLYING", "BLOCKED", "VERIFYING", "ROLLING_BACK", "ROLLED_BACK"],
)
def test_gate_validates_real_transaction_records(state: str) -> None:
    value = _valid_transaction(state)
    assert gate._validate_record(value)["state"] == state


def test_gate_rejects_verify_state_without_completed_publish() -> None:
    value = _valid_transaction("APPLYING")
    value = tx.transition(
        value,
        "VERIFYING",
        operation="unsafe_verify",
        observed_after={"compose": "b" * 64},
    )
    with pytest.raises(gate.GateError, match="verifying_publish_not_proven"):
        gate._validate_record(value)


def test_gate_rejects_plan_hash_corruption() -> None:
    value = _valid_transaction("READY")
    value["plan"]["kind"] = "tampered"
    with pytest.raises(gate.GateError, match="transaction_record_plan_hash_invalid"):
        gate._validate_record(value)


def test_successor_dropin_uses_service_exec_condition() -> None:
    import n3w_t1_r10_e03_successor_recovery as successor

    assert successor.GATE_DROPIN_BYTES.startswith(b"[Service]\nExecCondition=")


def test_blocked_real_transaction_remains_boot_blocking() -> None:
    value = _valid_transaction("BLOCKED")
    assert gate._validate_record(value)["state"] == "BLOCKED"


def test_rolling_back_blocks_before_predecessor_compose_restore(
    private_root: Path,
) -> None:
    _write(private_root, "tx.json", "ROLLING_BACK")
    assert gate.evaluate(private_root) == (False, "MAINTENANCE_BLOCKING")


def test_rolling_back_allows_start_only_after_proven_compose_restore(
    private_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _valid_transaction("ROLLING_BACK")
    intent = tx.begin_operation(
        value,
        operation_type="compose_rollback",
        before_fingerprint="b" * 64,
        intended_after_fingerprint="a" * 64,
        allowed_states={"ROLLING_BACK"},
    )
    value = tx.finish_operation(
        intent,
        observed_after_fingerprint="a" * 64,
    )
    path = private_root / "real.json"
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    assert gate._rollback_predecessor_restored(value) is True
    monkeypatch.setattr(gate, "_current_compose_sha256", lambda: "a" * 64)
    assert gate.evaluate(private_root) == (
        True,
        "MAINTENANCE_ROLLBACK_RESTORED",
    )


def test_rollback_restore_proof_rejects_wrong_target() -> None:
    value = _valid_transaction("ROLLING_BACK")
    intent = tx.begin_operation(
        value,
        operation_type="compose_rollback",
        before_fingerprint="b" * 64,
        intended_after_fingerprint="c" * 64,
        allowed_states={"ROLLING_BACK"},
    )
    value = tx.finish_operation(
        intent,
        observed_after_fingerprint="c" * 64,
    )
    assert gate._rollback_predecessor_restored(value) is False


def _write_real_transaction(root: Path, value: dict) -> None:
    path = root / "real.json"
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_verifying_allows_start_only_when_current_compose_is_candidate(
    private_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _valid_transaction("VERIFYING")
    _write_real_transaction(private_root, value)
    monkeypatch.setattr(gate, "_current_compose_sha256", lambda: "b" * 64)
    assert gate.evaluate(private_root) == (True, "MAINTENANCE_VERIFYING")


def test_verifying_unknown_current_compose_blocks_boot_owner_start(
    private_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _valid_transaction("VERIFYING")
    _write_real_transaction(private_root, value)
    monkeypatch.setattr(gate, "_current_compose_sha256", lambda: "c" * 64)
    assert gate.evaluate(private_root) == (False, "MAINTENANCE_BLOCKING")


def test_rollback_restore_record_cannot_override_later_compose_drift(
    private_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _valid_transaction("ROLLING_BACK")
    intent = tx.begin_operation(
        value,
        operation_type="compose_rollback",
        before_fingerprint="b" * 64,
        intended_after_fingerprint="a" * 64,
        allowed_states={"ROLLING_BACK"},
    )
    value = tx.finish_operation(
        intent,
        observed_after_fingerprint="a" * 64,
    )
    _write_real_transaction(private_root, value)
    monkeypatch.setattr(gate, "_current_compose_sha256", lambda: "c" * 64)
    assert gate.evaluate(private_root) == (False, "MAINTENANCE_BLOCKING")


def test_missing_or_symlink_compose_reality_fails_closed(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-compose.yml"
    with pytest.raises(gate.GateError, match="compose_reality_unavailable"):
        gate._current_compose_sha256(missing)
