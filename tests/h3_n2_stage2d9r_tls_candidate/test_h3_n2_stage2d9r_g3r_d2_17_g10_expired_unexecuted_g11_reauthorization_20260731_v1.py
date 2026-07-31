#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g10_expired_unexecuted_g11_reauthorization_contract_20260731_v1.py"
DISPOSITION = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g10-expired-unexecuted-disposition-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g11-private-package-static-check-authorization-pending-20260731-v1.json"
FIXED_NOW = "2026-07-31T06:43:12Z"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), "--now", FIXED_NOW, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


positive = run()
if positive.returncode != 0:
    raise SystemExit(f"POSITIVE_FAILED stdout={positive.stdout} stderr={positive.stderr}")
summary = json.loads(positive.stdout)
assert summary["status"] == "PASS"
assert summary["g10_state"] == "EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY"
assert summary["g11_private_material_created"] is False

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    disposition = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    disposition["authorization_claimed"] = True
    bad_disposition = tmp_path / "bad-disposition.json"
    bad_disposition.write_text(json.dumps(disposition), encoding="utf-8")
    result = run("--disposition", str(bad_disposition))
    assert result.returncode != 0
    assert "AUTHORIZATION_CLAIMED_MUST_BE_FALSE" in result.stderr

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    pending["g11_private_package_created"] = True
    bad_pending = tmp_path / "bad-pending.json"
    bad_pending.write_text(json.dumps(pending), encoding="utf-8")
    result = run("--pending", str(bad_pending))
    assert result.returncode != 0
    assert "G11_PRIVATE_PACKAGE_CREATED_MUST_BE_FALSE" in result.stderr

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    pending["next_gate"] = pending["next_gate"] + "-DRIFT"
    bad_pending = tmp_path / "drift-pending.json"
    bad_pending.write_text(json.dumps(pending), encoding="utf-8")
    result = run("--pending", str(bad_pending))
    assert result.returncode != 0
    assert "PENDING_NEXT_GATE_MISMATCH" in result.stderr

pre_expiry = subprocess.run(
    [
        sys.executable,
        "-B",
        str(TOOL),
        "--now",
        "2026-07-31T06:43:11Z",
    ],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
assert pre_expiry.returncode != 0
assert "AUTHORIZATION_NOT_YET_EXPIRED" in pre_expiry.stderr

print("PASS")
