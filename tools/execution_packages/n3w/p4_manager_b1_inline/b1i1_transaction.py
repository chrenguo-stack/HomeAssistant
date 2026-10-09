from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from b1i1_contract import Authority, GateStop, Operations, REQUIRED_HEALTH, require
from b1i1_journal import Journal
from b1i1_recovery import RecoveryResult, restore_original
from b1i1_supervisor import Budget, Deadline


@dataclass(frozen=True)
class Result:
    status: str
    reason: str


def _error_code(error: Exception) -> str:
    if isinstance(error, GateStop):
        code = str(error)
        if code.isascii() and code.replace("_", "").isalnum() and len(code) <= 90:
            return code
    return type(error).__name__


def execute(
    root: Path,
    authority: Authority,
    ops: Operations,
    budget: Budget,
    *,
    now: Callable[[], float] = time.monotonic,
    transaction_token: str | None = None,
) -> Result:
    authority.validate()
    deadline = Deadline(budget, now)
    ops.preflight(authority)
    deadline.require_forward(budget.forward_after_old_stop)
    token = transaction_token if transaction_token is not None else secrets.token_hex(24)
    state = Journal.create(root, authority, token)
    try:
        ops.prepare_fresh_and_shadow(authority)
        deadline.before_old_stop()
        ops.verify_pre_stop(authority)
        deadline.before_old_stop()
    except Exception as error:
        if state.uncertain:
            return Result("UNKNOWN_FROZEN", "JOURNAL_DURABILITY_UNKNOWN_FROZEN")
        try:
            state.save(phase="PREPARE_STOP", failure_code=_error_code(error))
        except Exception:
            return Result("UNKNOWN_FROZEN", "JOURNAL_DURABILITY_UNKNOWN_FROZEN")
        return Result("STOP_PREPARE", _error_code(error))

    try:
        state.intent("OLD_STOP_INTENT")
        deadline.require_forward()
        ops.stop_old(authority)
        state.intent("OLD_PARK_INTENT")
        deadline.require_forward()
        ops.park_old(authority)

        state.intent("CANDIDATE_CREATE_INTENT")
        deadline.require_forward()
        candidate_id = ops.create_candidate(authority, token)
        require(isinstance(candidate_id, str) and bool(candidate_id), "CANDIDATE_ID_NOT_RETURNED")
        state.bind_candidate(candidate_id)
        require(
            ops.inspect_candidate(authority, token) == candidate_id,
            "CANDIDATE_CREATE_INSPECT_ID_MISMATCH",
        )
        require(
            ops.verify_candidate_ownership(authority, token, candidate_id) is True,
            "CANDIDATE_CREATE_OWNERSHIP_UNVERIFIED",
        )

        state.intent("CANDIDATE_START_INTENT")
        deadline.require_forward()
        ops.start_candidate(authority, candidate_id)

        state.intent("POSTFLIGHT_INTENT")
        deadline.require_forward()
        ops.verify_candidate_health(candidate_id, REQUIRED_HEALTH)
        ops.verify_fresh_zero_state(authority)
        ops.verify_candidate_mounts_and_security(authority, candidate_id)
        ops.verify_broker_ha_r5(authority)
        ops.verify_old_stopped_and_parked(authority)
        deadline.require_forward(budget.evidence_reserve)

        state.intent("COMMIT_INTENT")
        ops.verify_finalized(authority, candidate_id)
        state.save(phase="CANDIDATE_VERIFIED", committed=True)
    except Exception as error:
        if state.uncertain:
            return Result("UNKNOWN_FROZEN", "JOURNAL_DURABILITY_UNKNOWN_FROZEN")
        deadline.enter_rollback()
        try:
            rollback = restore_original(state, authority, ops)
        except Exception as rollback_error:
            return Result("UNKNOWN_FROZEN", _error_code(rollback_error))
        return Result(rollback.status, _error_code(error) if rollback.status == "FAIL_ROLLED_BACK" else rollback.reason)

    try:
        ops.verify_finalized(authority, candidate_id)
        state.save(phase="FINALIZED")
        return Result("PASS", "COMMITTED_AND_VERIFIED")
    except Exception:
        return Result("UNKNOWN_FROZEN", "COMMITTED_FINAL_CHECK_UNVERIFIED")
