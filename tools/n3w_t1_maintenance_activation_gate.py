#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-maintenance-transaction/1"
TRANSACTION_ROOT = Path("/var/lib/n3w-t1-maintenance/transactions")
ACTIVE_BLOCKING_STATES = frozenset({"APPLYING", "ROLLING_BACK"})
ACTIVE_ALLOWING_STATES = frozenset({"PREPARING", "READY", "VERIFYING"})
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK", "BLOCKED", "ABORTED"})


class GateError(RuntimeError):
    pass


def _private_root(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise GateError("transaction_root_invalid")
    meta = path.stat()
    if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o700:
        raise GateError("transaction_root_metadata_invalid")


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GateError("transaction_record_invalid")
    meta = path.stat()
    if (
        meta.st_uid != 0
        or meta.st_gid != 0
        or stat.S_IMODE(meta.st_mode) != 0o600
        or meta.st_nlink != 1
    ):
        raise GateError("transaction_record_metadata_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GateError("transaction_record_json_invalid") from error
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise GateError("transaction_record_schema_invalid")
    state = value.get("state")
    if state not in ACTIVE_BLOCKING_STATES | ACTIVE_ALLOWING_STATES | TERMINAL_STATES:
        raise GateError("transaction_record_state_invalid")
    if value.get("replay_allowed") is not False:
        raise GateError("transaction_record_replay_invalid")
    return value


def evaluate(root: Path = TRANSACTION_ROOT) -> tuple[bool, str]:
    if not root.exists():
        return True, "NO_TRANSACTION_ROOT"
    _private_root(root)
    active: list[tuple[str, str]] = []
    for path in sorted(root.glob("*.json")):
        value = _record(path)
        state = str(value["state"])
        if state in ACTIVE_BLOCKING_STATES | ACTIVE_ALLOWING_STATES:
            txid = value.get("transaction_id")
            if not isinstance(txid, str) or not txid:
                raise GateError("transaction_id_invalid")
            active.append((txid, state))
    if len(active) > 1:
        raise GateError("multiple_active_transactions")
    if not active:
        return True, "NO_ACTIVE_TRANSACTION"
    _txid, state = active[0]
    if state in ACTIVE_BLOCKING_STATES:
        return False, "MAINTENANCE_BLOCKING"
    if state in ACTIVE_ALLOWING_STATES:
        return True, "MAINTENANCE_VERIFYING"
    raise GateError("active_state_unhandled")


def main() -> int:
    try:
        allowed, reason = evaluate()
    except GateError as error:
        sys.stderr.write(f"n3w-maintenance-gate: BLOCKED:{error}\n")
        return 1
    if not allowed:
        sys.stderr.write(f"n3w-maintenance-gate: BLOCKED:{reason}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
