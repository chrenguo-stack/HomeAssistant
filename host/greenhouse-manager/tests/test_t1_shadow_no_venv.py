from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_shadow_service_module_imports_without_paho() -> None:
    project = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPaho(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "paho" or fullname.startswith("paho."):
                    raise ModuleNotFoundError("blocked for no-install host test", name=fullname)
                return None

        sys.meta_path.insert(0, BlockPaho())

        from greenhouse_manager.t1_shadow_services import build_identity_bundle

        bundle = build_identity_bundle(system_id="greenhouse", node_id="gh-n1-a9f2f8")
        assert bundle.node_plan.client_id == "gh-n1-a9f2f8"
        assert bundle.service_plans["manager"].client_id == "gh-manager-greenhouse"
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "tools/run_t1_shadow_services.py", "--help"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
