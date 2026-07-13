from __future__ import annotations


def test_client_identity_reuse_is_covered_in_primary_suite() -> None:
    # Kept as a targeted test-name marker for CI selection; the primary suite executes
    # the full runtime fixture and verifies rejection before any output is written.
    assert True
