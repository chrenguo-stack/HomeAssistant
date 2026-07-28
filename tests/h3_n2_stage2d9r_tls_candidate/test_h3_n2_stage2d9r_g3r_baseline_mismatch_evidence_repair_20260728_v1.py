#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_capture_20260728_v1 as capture
import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_packager_20260728_v1 as packager

H4_RESULT = json.loads('{"activate_executed": false, "authorization_consumed": true, "authorization_id": "H4-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01", "automatic_retry_permitted": false, "board_operation": false, "broker_started": false, "cleanup_executed": false, "completed_at": "2026-07-28T14:48:37.280394Z", "esptool_operation": false, "execution_closure_role": "BLOCKING", "execution_closure_sha256": "d74b1b1995d35d76075b52c68f2e61f7ec67306a1615c01bfdcbaa6679d44275", "execution_package_sha256": "f3349fbd5a09509c20c66b525e50811150168c5375ef4b7a3518f30523829292", "flash_operation": false, "host_preflight_result_sha256": "5ae7d046181710ab2746c1c04bc45ea94f5097cb24b2ba78f415f2417b35c7ad", "network_operation": false, "new_physical_d2_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04", "non_execution_drift_files": [], "one_shot": true, "physical_nvs_operation": false, "physical_request_authorized": false, "prepare_executed": false, "private_paths_included": false, "private_values_included": false, "replay_permitted": false, "repository_head_enforced": false, "repository_head_role": "AUDIT_ONLY", "repository_head_sha": "64c6b093c3ba6a8476c9392c8d106394b2542fb5", "review_binding_sha256": "3bf6f69ca37e4a4037054e581274bf73057f04ad980c1685edfbeca091ec4ea7", "schema": "gh.h3.n2.stage2d9r-g3r-execution-closure-host-preflight-result/1", "secret_values_included": false, "serial_operation": false, "source_sha": "1fd6bc19246481835c1e836f5daaefcaf6c97836", "state": "EXECUTION_CLOSURE_HOST_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION", "status": "CONSUMED_PASS", "usb_enumeration": false, "verify_executed": false}')
REQUEST_04 = json.loads('{"activate_executed": false, "authorization_claimed": false, "authorization_consumed": false, "authorization_created": false, "authorized": false, "board_operation": false, "broker_started": false, "cleanup_executed": false, "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04", "decision_id": "D1-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01", "deployment": false, "esptool_operation": false, "execution_closure_policy_version": 1, "execution_closure_role": "BLOCKING", "execution_closure_sha256": "d74b1b1995d35d76075b52c68f2e61f7ec67306a1615c01bfdcbaa6679d44275", "execution_launcher_sha256": "1f1008b51c7e426b69ff2097e718361941a1ed5701ee64bca0a3859a7b287be2", "execution_package_sha256": "f3349fbd5a09509c20c66b525e50811150168c5375ef4b7a3518f30523829292", "execution_wrapper_sha256": "3a7bf7ac67b04441847d1e56069976700751dfafd1a650be2406335dd677f3d5", "expires_at": null, "flash_operation": false, "future_host_authorization_id": "H4-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01", "host_final_preflight_source_sha": "1fd6bc19246481835c1e836f5daaefcaf6c97836", "host_preflight_result_sha256": "5ae7d046181710ab2746c1c04bc45ea94f5097cb24b2ba78f415f2417b35c7ad", "issued_at": null, "merge": false, "network_operation": false, "non_execution_drift_files": [], "physical_nvs_operation": false, "prepare_executed": false, "previous_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03", "previous_request_raw_sha256": "e7c15a1d8d32379c9fb00058c29ef70e235b34f80ccb9678cf9d1dfe3b3a8937", "previous_request_reuse_permitted": false, "previous_request_state": "SUPERSEDED_BY_EXECUTION_CLOSURE_POLICY_BEFORE_AUTHORIZATION", "private_paths_included": false, "private_values_included": false, "ready": false, "release": false, "repository_head_enforced": false, "repository_head_role": "AUDIT_ONLY", "repository_head_sha": "64c6b093c3ba6a8476c9392c8d106394b2542fb5", "request_binding_sha256": "1058abf2c944ac5303c688b2b220ad208f22a920a984e44424b5ce5ab238d292", "review_binding_sha256": "3bf6f69ca37e4a4037054e581274bf73057f04ad980c1685edfbeca091ec4ea7", "schema": "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-request/1", "secret_values_included": false, "serial_operation": false, "source_sha": "1fd6bc19246481835c1e836f5daaefcaf6c97836", "stage": "H3/N2 Stage 2D-9R G3R execution-closure binding successor", "state": "EXECUTION_CLOSURE_BOUND_PHYSICAL_D2_REQUEST_AWAITING_EXACT_AUTHORIZATION", "tag": false, "upstream_artifact_id": 8688476229, "upstream_artifact_sha256": "89e25e287c33de0d88c714c748329c5d4cdbe12f83343fdd18eff8debf351a04", "usb_enumeration": false, "verify_executed": false}')


class BaselineMismatchEvidenceRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        capture.clear_last_baseline_evidence()

    def test_source_contract_is_unauthorized(self) -> None:
        value = contract.source_contract("a" * 40)
        self.assertEqual(value["base_pr"], 195)
        self.assertEqual(value["predecessor_state"], "CONSUMED_FAILED")
        self.assertEqual(value["predecessor_failure_code"], "BASELINE_STATE_MISMATCH")
        self.assertEqual(value["invalidated_request_state"], contract.INVALIDATED_REQUEST_STATE)
        self.assertFalse(value["future_physical_request_created"])
        for key in contract.FALSE_BOUNDARY:
            self.assertFalse(value[key], key)

    def test_exact_predecessor_consumed_failure_validates(self) -> None:
        value = contract.expected_predecessor_result()
        validated = contract.validate_predecessor_result(value)
        self.assertEqual(validated["terminal_result_sha256"], contract.PREDECESSOR_TERMINAL_RESULT_SHA256)
        self.assertIsNone(validated["observed_baseline_sha256"])
        self.assertIsNone(validated["flash_sha256"])
        self.assertEqual(validated["prepare_count"], 0)
        self.assertEqual(validated["verify_count"], 0)

    def test_predecessor_tamper_is_rejected(self) -> None:
        value = contract.expected_predecessor_result()
        value["failure_code"] = "OTHER"
        with self.assertRaisesRegex(contract.ContractError, "PREDECESSOR_RESULT_MISMATCH"):
            contract.validate_predecessor_result(value)

    def test_h4_and_request04_exact_bindings_validate(self) -> None:
        self.assertEqual(
            contract.sha256_bytes((json.dumps(H4_RESULT, indent=2, sort_keys=True) + "\n").encode()),
            contract.H4_RESULT_FILE_SHA256,
        )
        self.assertEqual(
            contract.sha256_bytes((json.dumps(REQUEST_04, indent=2, sort_keys=True) + "\n").encode()),
            contract.INVALIDATED_REQUEST_FILE_SHA256,
        )
        contract.validate_h4_result(H4_RESULT)
        contract.validate_request_04(REQUEST_04)

    def test_request04_is_invalidated_not_rebound(self) -> None:
        value = contract.invalidated_request_04_disposition()
        self.assertEqual(value["state"], contract.INVALIDATED_REQUEST_STATE)
        self.assertEqual(value["actual_predecessor_state"], "CONSUMED_FAILED")
        self.assertEqual(value["actual_predecessor_failure_code"], "BASELINE_STATE_MISMATCH")
        self.assertFalse(value["physical_authorization_created"])
        self.assertFalse(value["request_reuse_permitted"])

    def test_baseline_evidence_v2_preserves_hash_only_components(self) -> None:
        value = contract.build_baseline_evidence(
            board_identity_sha256=contract.BOARD_IDENTITY_SHA256,
            serial_identity_sha256=contract.SERIAL_IDENTITY_SHA256,
            chip_id_output_sha256="1" * 64,
            flash_id_output_sha256="2" * 64,
            test_partition_sha256="3" * 64,
            test_partition_size=0x10000,
        )
        self.assertEqual(value["policy_version"], 2)
        self.assertFalse(value["legacy_baseline_matches"])
        self.assertFalse(value["raw_chip_output_included"])
        self.assertFalse(value["raw_flash_output_included"])
        self.assertTrue(value["before_destructive_operation"])
        self.assertRegex(value["observed_legacy_baseline_sha256"], r"^[0-9a-f]{64}$")

    def test_capture_records_observed_baseline_before_raising(self) -> None:
        selected = types.SimpleNamespace(
            device="/dev/cu.test",
            board_binding=lambda: {"board": "one"},
            serial_binding=lambda: {"serial": "one"},
        )

        def canonical_sha256(value: object) -> str:
            return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

        def run_process(command: list[str], *, timeout: float, code: str):
            del timeout, code
            if "read_flash" in command:
                Path(command[-1]).write_bytes(b"\xff" * 0x10000)
                return subprocess.CompletedProcess(command, 0, "", "")
            text = "chip-output\n" if "chip_id" in command else "flash-output\n"
            return subprocess.CompletedProcess(command, 0, text, "")

        def require(condition: bool, code: str) -> None:
            if not condition:
                raise RuntimeError(code)

        def original_result_object(*args, **kwargs):
            del args
            return {
                "failure_code": kwargs.get("failure_code"),
                "flash_sha256": kwargs.get("flash_sha256"),
                "prepare_count": 0,
                "verify_count": 0,
                "observed_baseline_sha256": None,
                "terminal_result_sha256": "old",
            }

        core = types.SimpleNamespace(
            result_object=original_result_object,
            TEST_PARTITION_ADDRESS=0x400000,
            TEST_PARTITION_SIZE=0x10000,
            run_process=run_process,
            esptool_command=lambda p, port, *args: [str(p), "--port", port, *args],
            canonical_sha256=canonical_sha256,
            sha256_bytes=lambda b: hashlib.sha256(b).hexdigest(),
            sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
            require=require,
        )
        capture.install(core)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "BASELINE_STATE_MISMATCH"):
                core.baseline(
                    selected,
                    Path("/tmp/esptool"),
                    Path(directory),
                    {"baseline_state_sha256": contract.EXPECTED_BASELINE_STATE_SHA256},
                )
        evidence = capture.last_baseline_evidence()
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence["legacy_baseline_matches"])
        result = core.result_object(
            authorization={},
            status="CONSUMED_FAILED",
            terminal_state="CONSUMED_FAILED",
            failure_code="BASELINE_STATE_MISMATCH",
            baseline_value=None,
            flash_sha256=None,
            prepare_log=None,
            verify_log=None,
            broker_log=None,
            recovery_attempted=False,
            recovery_succeeded=False,
        )
        self.assertEqual(result["observed_baseline_sha256"], evidence["observed_legacy_baseline_sha256"])
        self.assertTrue(result["baseline_mismatch_before_destructive_operation"])
        self.assertEqual(result["baseline_evidence_policy_version"], 2)

    def test_diagnostic_authorization_is_exact_and_time_limited(self) -> None:
        now = datetime(2026, 7, 28, 16, 0, tzinfo=timezone.utc)
        value = {
            "schema": contract.DIAGNOSTIC_AUTH_SCHEMA,
            "authorization_id": contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,
            "operation": contract.FUTURE_DIAGNOSTIC_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "source_sha": "a" * 40,
            "review_binding_sha256": "b" * 64,
            "predecessor_terminal_result_sha256": contract.PREDECESSOR_TERMINAL_RESULT_SHA256,
            "h4_result_sha256": contract.H4_RESULT_SHA256,
            "invalidated_request_binding_sha256": contract.INVALIDATED_REQUEST_BINDING_SHA256,
            "expected_board_identity_sha256": contract.BOARD_IDENTITY_SHA256,
            "expected_serial_identity_sha256": contract.SERIAL_IDENTITY_SHA256,
            "expected_legacy_baseline_sha256": contract.EXPECTED_BASELINE_STATE_SHA256,
            "diagnostic_script_sha256": "c" * 64,
            "python_executable_sha256": "d" * 64,
            "esptool_executable_sha256": "e" * 64,
            "board_operation_authorized": True,
            "usb_enumeration_authorized": True,
            "esptool_readonly_authorized": True,
            "serial_open_authorized": False,
            "flash_write_authorized": False,
            "flash_erase_authorized": False,
            "physical_nvs_operation_authorized": False,
            "network_operation_authorized": False,
            "broker_operation_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "future_physical_request_created": False,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
        }
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        validated = contract.validate_diagnostic_authorization(
            value,
            source_sha="a" * 40,
            review_binding_sha256="b" * 64,
            diagnostic_script_sha256="c" * 64,
            python_executable_sha256="d" * 64,
            esptool_executable_sha256="e" * 64,
            now=now + timedelta(minutes=1),
        )
        self.assertEqual(validated["authorization_record_sha256"], value["authorization_record_sha256"])

    def test_diagnostic_source_has_readonly_command_boundary(self) -> None:
        source = (TOOLS / "h3_n2_stage2d9r_g3r_baseline_evidence_diagnostic_probe_20260728_v1.py").read_text()
        self.assertIn('"chip_id"', source)
        self.assertIn('"flash_id"', source)
        self.assertIn('"read_flash"', source)
        for forbidden in (
            "serial.Serial(", '"write_flash"', '"erase_flash"', '"erase_region"',
            "import socket", "mosquitto", "GH2D9R_PREPARE", "GH2D9R_VERIFY",
        ):
            self.assertNotIn(forbidden, source, forbidden)

    @unittest.skipUnless(os.environ.get("STAGE2D9R_BASELINE_REPAIR_UPSTREAM_ARTIFACT_ZIP"),
                         "real upstream Artifact not supplied")
    def test_real_artifact_packaging_is_deterministic(self) -> None:
        artifact = Path(os.environ["STAGE2D9R_BASELINE_REPAIR_UPSTREAM_ARTIFACT_ZIP"])
        with tempfile.TemporaryDirectory() as directory:
            lane_a = Path(directory) / "a"
            lane_b = Path(directory) / "b"
            result_a = packager.build(ROOT, artifact, lane_a, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            result_b = packager.build(ROOT, artifact, lane_b, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            self.assertEqual(result_a["archive_sha256"], result_b["archive_sha256"])
            self.assertEqual(packager.recursive_files(lane_a), packager.recursive_files(lane_b))
            invalidation = json.loads((lane_a / packager.INVALIDATED_REQUEST_FILE).read_text())
            self.assertEqual(invalidation["state"], contract.INVALIDATED_REQUEST_STATE)
            diagnostic = json.loads((lane_a / packager.DIAGNOSTIC_REQUEST_FILE).read_text())
            self.assertFalse(diagnostic["authorized"])
            self.assertFalse(diagnostic["future_physical_request_created"])


if __name__ == "__main__":
    unittest.main()
