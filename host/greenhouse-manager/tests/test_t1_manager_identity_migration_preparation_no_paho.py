from __future__ import annotations

import builtins
import importlib


def test_manager_preparation_import_does_not_require_paho(monkeypatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and (name == "paho" or name.startswith("paho.")):
            error = ModuleNotFoundError("No module named 'paho'")
            error.name = "paho"
            raise error
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module = importlib.import_module(
        "greenhouse_manager.t1_manager_identity_migration_preparation"
    )
    assert callable(module.prepare_manager_identity_migration)
