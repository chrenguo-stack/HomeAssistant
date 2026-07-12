from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_request_only_orchestrator_import_does_not_require_paho() -> None:
    manager_root = Path(__file__).resolve().parents[1]
    source_root = manager_root / "src"
    script = r'''
import builtins

real_import = builtins.__import__


def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and (name == "paho" or name.startswith("paho.")):
        error = ModuleNotFoundError("No module named 'paho'")
        error.name = "paho"
        raise error
    return real_import(name, globals, locals, fromlist, level)


builtins.__import__ = guarded_import
from greenhouse_manager.t1_broker_identity_production_activation_orchestrator import (  # noqa: E402
    build_production_activation_execution_request,
)

assert callable(build_production_activation_execution_request)
print("REQUEST_ONLY_IMPORT_OK")
'''
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source_root)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=manager_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "REQUEST_ONLY_IMPORT_OK"
