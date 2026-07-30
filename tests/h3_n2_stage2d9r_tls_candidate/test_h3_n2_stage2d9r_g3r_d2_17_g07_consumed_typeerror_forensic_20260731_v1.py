from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g07_consumed_typeerror_forensic_20260731_v1.py"
FAILURE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g07-consumed-typeerror-failure-disposition-20260731-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g07-consumed-typeerror-forensic-closure-20260731-v1.json"
SPEC = importlib.util.spec_from_file_location("forensic", TOOL)
assert SPEC and SPEC.loader
forensic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forensic)

class TestG07ConsumedTypeErrorForensic(unittest.TestCase):
    def test_bindings_and_safety(self):
        failure = json.loads(FAILURE.read_text())
        binding = failure.pop("failure_disposition_binding_sha256")
        self.assertEqual(binding, forensic.canonical(failure))
        decision = json.loads(DECISION.read_text())
        db = decision.pop("decision_binding_sha256")
        self.assertEqual(db, forensic.canonical(decision))
        self.assertEqual(decision["failure_disposition_binding_sha256"], binding)
        self.assertTrue(failure["authorization_consumed"])
        self.assertFalse(failure["replay_permitted"])
        self.assertFalse(failure["flash_operation"])
        self.assertFalse(failure["prepare_executed"])

    def test_exact_terminal_semantics(self):
        terminal = {
            "activate_executed": False, "authorization_claimed": True,
            "authorization_consumed": True,
            "authorization_marker_sha256": "c9250960ee5418739cda4d670f01d215229386b7c44edde6c4738337658a359a",
            "authorization_record_sha256": "37fa9803c4ce96083f2b58d4b973c8373326c179d609645f35af1ec72076a601",
            "automatic_retry_permitted": False, "board_operation": True,
            "broker_started": False, "cleanup_executed": False,
            "d2_request_id": forensic.EXPECTED_D2,
            "decision_id": forensic.EXPECTED_DECISION, "deployment": False,
            "esptool_operation": True,
            "execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c",
            "failure_code": "TypeError", "flash_operation": False, "merge": False,
            "physical_nvs_operation": True,
            "physical_result_sha256": forensic.EXPECTED_RESULT_SHA256,
            "prepare_executed": False, "ready": False, "recovery_executed": False,
            "recovery_succeeded": False, "release": False, "replay_permitted": False,
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-physical-decision-terminal/1",
            "serial_operation": True, "status": "FAIL", "tag": False,
            "terminal_state": "CONSUMED_FAILED_PRECLAIM", "usb_enumeration": True,
            "verify_executed": False,
        }
        terminal["terminal_record_sha256"] = forensic.canonical(terminal)
        self.assertEqual(terminal["terminal_record_sha256"], forensic.EXPECTED_TERMINAL_SHA256)
        safe = forensic.validate_terminal(terminal)
        self.assertEqual(safe["failure_code"], "TypeError")
        self.assertNotIn("private_path", safe)

    def test_tamper_rejected(self):
        value = json.loads(FAILURE.read_text())
        value["failure_code"] = "Other"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "terminal.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(forensic.ForensicError):
                forensic.validate_terminal(value)

    def test_tool_has_fixed_whitelists_and_no_board_calls(self):
        text = TOOL.read_text()
        self.assertIn("TERMINAL_KEYS", text)
        self.assertIn("RESULT_KEYS", text)
        for token in ("import serial", "subprocess.run", "socket.", "chmod("):
            self.assertNotIn(token, text)

if __name__ == "__main__":
    unittest.main()
