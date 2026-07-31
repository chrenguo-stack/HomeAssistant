#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
tool = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g13_target_mac_static_check_acceptance_contract_20260731_v1.py"
result = subprocess.run([sys.executable, "-B", str(tool)], cwd=ROOT, text=True, capture_output=True)
if result.returncode != 0:
    raise SystemExit(result.stdout + result.stderr)
if '"status": "PASS"' not in result.stdout:
    raise SystemExit("PASS_OUTPUT_MISSING")
print(result.stdout.strip())
