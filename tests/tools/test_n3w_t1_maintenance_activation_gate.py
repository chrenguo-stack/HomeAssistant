from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import n3w_t1_maintenance_activation_gate as gate  # noqa: E402


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


def test_verifying_allows_application_start(private_root: Path) -> None:
    _write(private_root, "tx.json", "VERIFYING")
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
