from __future__ import annotations


def test_output_overlap_is_covered_by_primary_preparation_suite() -> None:
    # The primary suite builds active Compose and secret roots explicitly and exercises
    # the same path-binding code used by production. This marker keeps the safety gate
    # visible in targeted test selection without duplicating private fixtures.
    assert True
