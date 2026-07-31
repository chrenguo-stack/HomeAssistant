#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g12_target_mac_static_check_acceptance_contract_20260731_v1.py"


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-B", str(TOOL)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        raise SystemExit(completed.returncode)
    value = json.loads(completed.stdout.strip())
    assert value["status"] == "PASS"
    assert value["acceptance_binding_sha256"] == "f7bcfce8d3c10f337076fbaba916526fde54f152fda3876e321ab304bdcc37ff"
    assert value["physical_pending_binding_sha256"] == "b7b1d4b71e815b28a2bb7468715abcdd5b9977962890f207a36c723122a3c64f"
    assert value["physical_operation"] is False
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
