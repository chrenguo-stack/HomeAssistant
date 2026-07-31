#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g11_preclaim_blocked_forensic_contract_20260731_v1.py"


def main() -> int:
    completed = subprocess.run([sys.executable, "-B", str(TOOL)], cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        return completed.returncode
    value = json.loads(completed.stdout)
    assert value["status"] == "PASS"
    assert value["physical_operation"] is False
    assert value["disposition_binding_sha256"] == "101f96fc0c09f71ccf022e931fcaf07b0e962b09fdd8b76f86008e75e28c4bb9"
    assert value["pending_binding_sha256"] == "307112236b4bb5d668e7be3d9ef41d3fb904cd5b04a362c4de4831c7730078b4"
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
