from __future__ import annotations

from greenhouse_manager.t1_manager_identity_migration_preparation import SCHEMA


def test_manager_migration_preparation_schema_is_versioned() -> None:
    assert SCHEMA == "gh.m2.t1-manager-identity-migration-preparation/1"
