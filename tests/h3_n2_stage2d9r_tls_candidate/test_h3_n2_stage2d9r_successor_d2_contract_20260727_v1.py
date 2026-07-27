#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_contract_20260727_v1.py"
SPEC = importlib.util.spec_from_file_location("contract", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = "a" * 40
D = "b" * 64

class ContractTests(unittest.TestCase):
    def test_contract_is_review_only_and_complete(self) -> None:
        contract = MODULE.build_contract(SOURCE)
        self.assertEqual(contract["state"], "D2_REVIEWED")
        self.assertFalse(contract["authorization_record_included"])
        self.assertFalse(contract["execution_launcher_included"])
        self.assertFalse(contract["board_operation"])
        self.assertFalse(contract["serial_operation"])
        self.assertFalse(contract["flash_operation"])
        self.assertEqual(contract["state_machine"]["prepare_max_count"], 1)
        self.assertEqual(contract["state_machine"]["verify_max_count"], 1)
        self.assertEqual(contract["state_machine"]["locked_recovery_max_count"], 1)
        self.assertIn("ACTIVATE", contract["prohibited_operations"])
        self.assertIn("CLEANUP", contract["prohibited_operations"])

    def test_state_machine_blocks_second_prepare_path(self) -> None:
        MODULE.validate_transition("AUTO_RESET_COMPLETED", "ISOLATED_BROKER_STARTED")
        MODULE.validate_transition("ISOLATED_BROKER_STARTED", "PREPARE_EXECUTED_ONCE")
        with self.assertRaisesRegex(MODULE.ContractError, "STATE_TRANSITION_NOT_ALLOWED"):
            MODULE.validate_transition("PREPARE_EXECUTED_ONCE", "PREPARE_EXECUTED_ONCE")

    def test_preclaim_and_postclaim_failure_policy(self) -> None:
        pre = MODULE.failure_policy("PRECLAIM_CI_OR_ARTIFACT_DRIFT")
        post = MODULE.failure_policy("FLASH_ERASE_WRITE_OR_VERIFY_FAILED")
        self.assertFalse(pre["authorization_consumed"])
        self.assertEqual(pre["terminal_state"], "INVALIDATED_BEFORE_CLAIM")
        self.assertTrue(post["authorization_consumed"])
        self.assertTrue(post["locked_recovery_eligible"])

    def test_exact_request_needs_all_exact_bindings(self) -> None:
        contract = MODULE.build_contract(SOURCE)
        request = MODULE.build_exact_authorization_request(
            contract,
            review_artifact_id=1,
            review_artifact_digest_sha256=D,
            review_binding_sha256=D,
            public_preflight_artifact_id=2,
            public_preflight_artifact_digest_sha256=D,
            private_preflight_result_sha256=D,
            u1_02_consumed_marker_sha256=D,
            board_identity_sha256=D,
            serial_identity_sha256=D,
            baseline_state_sha256=D,
            execution_package_sha256=D,
            execution_script_sha256=D,
            execution_launcher_sha256=D,
            execution_marker_name_sha256=D,
            locked_recovery_package_sha256=D,
            issued_at="2026-07-27T00:00:00Z",
            expires_at="2026-07-27T02:00:00Z",
        )
        self.assertFalse(request["authorized"])
        self.assertEqual(request["prepare_max_count"], 1)
        self.assertEqual(request["verify_max_count"], 1)
        with self.assertRaisesRegex(MODULE.ContractError, "EXACT_BINDING_INVALID_BOARD_IDENTITY_SHA256"):
            MODULE.build_exact_authorization_request(
                contract,
                review_artifact_id=1,
                review_artifact_digest_sha256=D,
                review_binding_sha256=D,
                public_preflight_artifact_id=2,
                public_preflight_artifact_digest_sha256=D,
                private_preflight_result_sha256=D,
                u1_02_consumed_marker_sha256=D,
                board_identity_sha256="bad",
                serial_identity_sha256=D,
                baseline_state_sha256=D,
                execution_package_sha256=D,
                execution_script_sha256=D,
                execution_launcher_sha256=D,
                execution_marker_name_sha256=D,
                locked_recovery_package_sha256=D,
                issued_at="2026-07-27T00:00:00Z",
                expires_at="2026-07-27T02:00:00Z",
            )

    def test_authorization_window_is_strictly_bounded(self) -> None:
        contract = MODULE.build_contract(SOURCE)
        kwargs = dict(
            review_artifact_id=1,
            review_artifact_digest_sha256=D,
            review_binding_sha256=D,
            public_preflight_artifact_id=2,
            public_preflight_artifact_digest_sha256=D,
            private_preflight_result_sha256=D,
            u1_02_consumed_marker_sha256=D,
            board_identity_sha256=D,
            serial_identity_sha256=D,
            baseline_state_sha256=D,
            execution_package_sha256=D,
            execution_script_sha256=D,
            execution_launcher_sha256=D,
            execution_marker_name_sha256=D,
            locked_recovery_package_sha256=D,
        )
        with self.assertRaisesRegex(MODULE.ContractError, "AUTHORIZATION_WINDOW_EXCEEDS_MAXIMUM"):
            MODULE.build_exact_authorization_request(
                contract, **kwargs,
                issued_at="2026-07-27T00:00:00Z",
                expires_at="2026-07-27T02:00:01Z",
            )
        with self.assertRaisesRegex(MODULE.ContractError, "AUTHORIZATION_WINDOW_NOT_POSITIVE"):
            MODULE.build_exact_authorization_request(
                contract, **kwargs,
                issued_at="2026-07-27T02:00:00Z",
                expires_at="2026-07-27T02:00:00Z",
            )

    def test_wrong_main_fails_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "MAIN_SHA_MISMATCH"):
            MODULE.build_contract(SOURCE, "c" * 40)

if __name__ == "__main__":
    unittest.main()
