from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
LOADER = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.py"
PARTS = [ROOT / "tools" / f"h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part{i}.pyfrag" for i in range(1, 5)]
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g04-physical-execution-20260730-v1.json"
PENDING = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g04-physical-execution-authorized-pending-20260730-v1.json"
LAUNCHER = ROOT / "tools/run_h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_20260730_v1.sh"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

class TestG04PhysicalDecision(unittest.TestCase):
    def test_decision_bindings_and_closed_boundaries(self):
        value = json.loads(DECISION.read_text())
        self.assertEqual(value["decision_id"], "D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PHYSICAL-EXECUTION-20260730-01")
        self.assertEqual(value["base_head_sha"], "e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7")
        self.assertEqual(value["acceptance_artifact_id"], 8762446382)
        self.assertEqual(value["decision_driver_sha256"], sha(LOADER))
        self.assertEqual(value["decision_driver_assembled_sha256"], hashlib.sha256(b"".join(p.read_bytes() for p in PARTS)).hexdigest())
        self.assertEqual(value["decision_driver_part_sha256"], {p.name: sha(p) for p in PARTS})
        self.assertEqual(value["decision_launcher_sha256"], sha(LAUNCHER))
        binding = value.pop("decision_binding_sha256")
        self.assertEqual(binding, canonical(value))
        self.assertEqual(value["terminal_record_digest_semantics"], "CANONICAL_JSON_WITH_TERMINAL_RECORD_SHA256_REMOVED")
        self.assertFalse(value["replay_permitted"])
        for key in ("activate_authorized", "cleanup_authorized", "ready_authorized", "merge_authorized", "release_authorized", "tag_authorized", "deployment_authorized"):
            self.assertFalse(value[key])
        pending = json.loads(PENDING.read_text())
        pending_binding = pending.pop("acceptance_binding_sha256")
        self.assertEqual(pending_binding, canonical(pending))
        self.assertTrue(pending["authorization_created"])
        self.assertFalse(pending["authorization_claimed"])
        self.assertFalse(pending["authorization_consumed"])

    def test_loader_fragments_reassemble_exactly(self):
        text = LOADER.read_text()
        self.assertNotIn("/Users/", text + "".join(p.read_text() for p in PARTS))
        for part in PARTS:
            self.assertTrue(part.is_file())

    def test_real_shell_host_only_self_test(self):
        execution = Path(os.environ["D2_17_G04_EXECUTION_ROOT"]).resolve()
        completed = subprocess.run([sys.executable, "-B", str(LOADER), "--self-test-execution-root", str(execution)], text=True, capture_output=True, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        value = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(value["status"], "PASS")
        self.assertTrue(value["terminal_formatting_independent"])
        self.assertTrue(value["terminal_semantic_tamper_rejected"])
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["board_operation"])

    def test_launcher_no_arguments_and_exact_python(self):
        text = LAUNCHER.read_text()
        self.assertIn('if [ "$#" -ne 0 ]', text)
        self.assertIn('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11', text)

if __name__ == "__main__":
    unittest.main()
