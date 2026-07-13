from __future__ import annotations

import importlib


def test_manager_preparation_module_imports_without_live_dependencies() -> None:
    module = importlib.import_module(
        "greenhouse_manager.t1_manager_identity_migration_preparation"
    )
    assert callable(module.prepare_manager_identity_migration)
