from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

CONTRACT = "h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1"
WRAPPER = "h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1"


class D217ExecutionIdentityFreezeTests(unittest.TestCase):
    def test_decision_and_d2_16_failure_disposition(self) -> None:
        contract = importlib.import_module(CONTRACT)
        decision = contract.validate_decision(ROOT / "docs/decisions" / contract.DECISION_FILE)
        disposition = contract.validate_failure_disposition(
            ROOT / "docs/acceptance" / contract.FAILURE_DISPOSITION_FILE
        )
        self.assertEqual(decision["base_pr"], 215)
        self.assertEqual(disposition["terminal_state"], "STATIC_CHECK_FAILED_RETIRED")
        self.assertEqual(
            disposition["leaf_failure_code"],
            "AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH",
        )
        self.assertFalse(disposition["authorization_claimed"])
        self.assertFalse(disposition["authorization_consumed"])
        self.assertFalse(disposition["execute_permitted"])

    def test_source_status_has_no_physical_authority(self) -> None:
        wrapper = importlib.import_module(WRAPPER)
        value = wrapper.source_status()
        self.assertEqual(
            value["predecessor_terminal_state"], "STATIC_CHECK_FAILED_RETIRED"
        )
        self.assertTrue(value["execution_identity_freeze_required"])
        self.assertTrue(value["target_mac_static_check_required_before_physical_decision"])
        self.assertFalse(value["physical_authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_final_payload_digests_are_not_retired_authorization_values(self) -> None:
        contract = importlib.import_module(CONTRACT)
        self.assertEqual(
            contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
            "ed8e4c673e89107750743702c7e4f4cb9bfada9c53519edcc4ee31719045b2de",
        )
        self.assertEqual(
            contract.RECOVERY_PAYLOAD_TAR_SHA256,
            "9a1b75a39edc4b47d7e54417bdb1e6a07671f37a9100e7f4364e63383e11eeb2",
        )
        self.assertNotEqual(
            contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
            contract.D2_16_AUTH_IMMUTABLE_PAYLOAD_TAR_SHA256,
        )
        self.assertNotEqual(
            contract.RECOVERY_PAYLOAD_TAR_SHA256,
            contract.D2_16_AUTH_RECOVERY_PAYLOAD_TAR_SHA256,
        )

    def test_shell_generated_results(self) -> None:
        result_root = os.environ.get("D2_17_SHELL_RESULT_ROOT")
        if not result_root:
            self.skipTest("shell integration supplies result root")
        root = Path(result_root)
        identity = json.loads((root / "execution-identity.json").read_text())
        authorization = json.loads((root / "synthetic-authorization.json").read_text())
        passed = json.loads((root / "static-check-pass.json").read_text())
        public_bytes = (root / "static-check-pass-public-ci.json").read_bytes()
        private_bytes = (root / "static-check-pass-private-package.json").read_bytes()
        mac_bytes = (root / "static-check-pass-target-mac-static-check.json").read_bytes()
        failed = json.loads((root / "static-check-tampered.json").read_text())
        idem = json.loads((root / "idempotency.json").read_text())
        sentinels = json.loads((root / "hardware-sentinels.json").read_text())
        self.assertEqual(identity["install_call_count"], 1)
        self.assertEqual(identity["bind_call_count"], 2)
        self.assertEqual(
            authorization["execution_identity_sha256"],
            identity["execution_identity_sha256"],
        )
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(public_bytes, private_bytes)
        self.assertEqual(public_bytes, mac_bytes)
        self.assertFalse((root / "forbidden-pre-freeze-authorization.json").exists())
        self.assertTrue(passed["full_inherited_validator_executed"])
        self.assertTrue(passed["hardware_sentinels_untouched"])
        self.assertFalse(passed["authorization_claimed"])
        self.assertFalse(passed["authorization_consumed"])
        self.assertEqual(idem["bind_call_count"], 3)
        self.assertEqual(idem["install_call_count"], 1)
        self.assertEqual(sentinels["status"], "PASS")
        self.assertIn("usb_enumeration", sentinels["observed_sentinels"])
        self.assertIn("serial_operation", sentinels["observed_sentinels"])
        self.assertIn("esptool_operation", sentinels["observed_sentinels"])
        self.assertIn("flash_operation", sentinels["observed_sentinels"])
        self.assertIn("broker_started", sentinels["observed_sentinels"])
        self.assertIn("recovery_executed", sentinels["observed_sentinels"])
        self.assertIn("network_operation", sentinels["observed_sentinels"])
        self.assertFalse(sentinels["physical_operation_completed"])
        self.assertEqual(failed["status"], "FAIL")
        self.assertEqual(
            failed["failure_code"],
            "AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH",
        )
        self.assertEqual(failed["failure_stage"], "FULL_INHERITED_AUTHORIZATION_PREFLIGHT")
        self.assertTrue(failed["full_inherited_validator_executed"])
        self.assertEqual(failed["digest_field"], "immutable_payload_tar_sha256")
        self.assertEqual(
            failed["expected_digest"], identity["immutable_payload_tar_sha256"]
        )
        self.assertEqual(failed["actual_digest"], "0" * 64)
        self.assertFalse(failed["authorization_claimed"])
        self.assertFalse(failed["authorization_consumed"])
        self.assertTrue(failed["hardware_sentinels_untouched"])


if __name__ == "__main__":
    unittest.main()
