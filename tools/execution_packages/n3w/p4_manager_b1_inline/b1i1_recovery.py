from __future__ import annotations

from dataclasses import dataclass

from b1i1_contract import Authority, GateStop, Operations, require
from b1i1_journal import Journal


@dataclass(frozen=True)
class RecoveryResult:
    status: str
    reason: str


def owned_candidate_id(state: Journal, authority: Authority, ops: Operations) -> str | None:
    token = state.doc["transaction_token"]
    actual = ops.inspect_candidate(authority, token)
    recorded = state.doc.get("candidate_id")
    if actual is None:
        require(recorded is None, "RECORDED_CANDIDATE_MISSING_UNKNOWN")
        return None
    require(isinstance(actual, str) and bool(actual), "CANDIDATE_INSPECTION_UNCERTAIN")
    require(recorded in (None, actual), "UNKNOWN_CANDIDATE_IDENTITY")
    require(
        ops.verify_candidate_ownership(authority, token, actual) is True,
        "UNKNOWN_CANDIDATE_OWNERSHIP",
    )
    if recorded is None:
        state.bind_candidate(actual)
    return actual


def read_only_reconcile(state: Journal, authority: Authority, ops: Operations) -> RecoveryResult:
    state.check_authority(authority)
    if state.doc.get("committed") is True:
        candidate_id = state.doc.get("candidate_id")
        require(isinstance(candidate_id, str) and bool(candidate_id), "COMMITTED_CANDIDATE_NOT_BOUND")
        try:
            ops.verify_finalized(authority, candidate_id)
        except Exception:
            return RecoveryResult("UNKNOWN_FROZEN", "COMMITTED_RUNTIME_UNVERIFIED")
        return RecoveryResult("VERIFIED_COMMITTED", "READ_ONLY_VERIFIED")
    if state.doc.get("rollback_result") == "PASS":
        try:
            ops.verify_old_healthy_and_unchanged(authority)
            ops.verify_broker_ha_r5(authority)
        except Exception:
            return RecoveryResult("UNKNOWN_FROZEN", "ROLLBACK_RUNTIME_UNVERIFIED")
        return RecoveryResult("VERIFIED_ROLLED_BACK", "READ_ONLY_VERIFIED")
    return RecoveryResult("UNKNOWN_FROZEN", "NO_TERMINAL_EVIDENCE")


def restore_original(state: Journal, authority: Authority, ops: Operations) -> RecoveryResult:
    state.check_authority(authority)
    require(state.doc.get("committed") is False, "COMMITTED_NEVER_AUTO_ROLLBACK")
    try:
        candidate_id = owned_candidate_id(state, authority, ops)
        if candidate_id is not None:
            ops.quarantine_owned_candidate(authority, candidate_id)
        ops.restore_old_exact_id(authority)
        ops.verify_old_healthy_and_unchanged(authority)
        ops.verify_broker_ha_r5(authority)
    except Exception as error:
        code = str(error) if isinstance(error, GateStop) else type(error).__name__
        try:
            state.save(rollback_result="INCOMPLETE", phase="FAIL_ROLLBACK_INCOMPLETE")
        except Exception:
            pass
        return RecoveryResult("FAIL_ROLLBACK_INCOMPLETE", code)
    state.save(rollback_result="PASS", phase="FAIL_ROLLED_BACK")
    return RecoveryResult("FAIL_ROLLED_BACK", "OLD_MANAGER_ORIGINAL_VERIFIED")


def controlled_recovery(
    state: Journal, authority: Authority, ops: Operations, *,
    exact_recovery_authorized: bool
) -> RecoveryResult:
    require(exact_recovery_authorized is True, "RECOVERY_NOT_AUTHORIZED")
    result = read_only_reconcile(state, authority, ops)
    if result.status != "UNKNOWN_FROZEN":
        return result
    require(state.doc.get("committed") is False, "COMMITTED_RECONCILE_ONLY")
    require(state.doc.get("phase") not in ("PREPARE_INTENT", "PREPARE_STOP"), "PREPARE_RECONCILE_ONLY")
    return restore_original(state, authority, ops)
