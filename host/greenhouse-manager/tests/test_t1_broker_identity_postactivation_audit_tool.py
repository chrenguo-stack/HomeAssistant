from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_broker_postactivation_audit_tool_bootstraps_local_source(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    tool = root / "tools/run_t1_broker_identity_postactivation_audit.py"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-S", str(tool), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Run a read-only Broker identity postactivation audit" in result.stdout
