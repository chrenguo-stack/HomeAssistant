#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_u1_public_closure_20260727_v1.py"
U1_01 = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-private-content-binding-u1-01-invalidation-l1-v1.json"
U1_02 = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-private-content-binding-u1-02-success-l1-v1.json"
SPEC = importlib.util.spec_from_file_location("closure", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ClosureTests(unittest.TestCase):
    def test_public_closure_passes(self) -> None:
        result = MODULE.validate(U1_01, U1_02)
        self.assertEqual(result["u1_01_disposition"], "INVALIDATED_BEFORE_CLAIM")
        self.assertEqual(result["u1_02_status"], "CONSUMED_PASS")
        self.assertTrue(result["u1_02_consumed_marker_live_preflight_required"])
        self.assertFalse(result["replay_permitted"])
        self.assertFalse(result["d2_authorized"])

    def test_u1_01_claim_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            value = json.loads(U1_01.read_text())
            value["authorization_state"]["authorization_claimed"] = True
            path = Path(temp) / "u1-01.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ClosureError, "U1_01_AUTHORIZATION_CLAIMED_MISMATCH"):
                MODULE.validate(path, U1_02)

    def test_u1_02_replay_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            value = json.loads(U1_02.read_text())
            value["authorization_state"]["replay_permitted"] = True
            path = Path(temp) / "u1-02.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ClosureError, "U1_02_REPLAY_EXPANDED"):
                MODULE.validate(U1_01, path)

    def test_private_path_pattern_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            value = json.loads(U1_02.read_text())
            value["unsafe"] = "/Users/example/private"
            path = Path(temp) / "u1-02.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ClosureError, "PUBLIC_RECORD_SECRET_OR_PATH_PATTERN"):
                MODULE.validate(U1_01, path)

if __name__ == "__main__":
    unittest.main()
