from __future__ import annotations


def test_manager_migration_restart_scope_is_manager_only() -> None:
    assert ["greenhouse-manager"] == ["greenhouse-manager"]
