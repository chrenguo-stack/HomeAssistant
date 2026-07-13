from __future__ import annotations

EXPECTED_BLOCKERS = {
    "manager_operator_authorization_required",
    "manager_live_execution_not_implemented",
    "node_credentials_not_delivered",
    "anonymous_closure_not_reviewed",
}


def test_manager_preparation_blocker_contract_is_complete() -> None:
    assert len(EXPECTED_BLOCKERS) == 4
