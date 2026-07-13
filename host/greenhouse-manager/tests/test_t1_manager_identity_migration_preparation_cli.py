from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_manager_identity_migration_preparation_launcher_help() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "tools/run_t1_manager_identity_migration_preparation.py"),
            "--help",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert "manager" in completed.stdout.lower()
    assert "--expected-retained-topic" in completed.stdout
