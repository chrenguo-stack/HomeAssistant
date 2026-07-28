#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_usb_identity_evidence_capture_20260728_v1 as capture
import h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_packager_20260728_v1 as packager


class UsbIdentityEvidenceRepairTests(unittest.TestCase):
    def identity(self, *, device: str = "/dev/cu.usbmodem-a", location: str = "1-1", hwid: str = "USB VID:PID=303A:1001 LOCATION=1-1"):
        return {
            "device": device,
            "vid": 0x303A,
            "pid": 0x1001,
            "serial_number": "ABC123",
            "manufacturer": "Espressif",
            "product": "USB JTAG/serial debug unit",
            "location": location,
            "hwid": hwid,
        }

    def test_b1_result_is_exact_consumed_failure(self) -> None:
        value = contract.expected_b1_result()
        self.assertEqual(value["status"], "CONSUMED_FAILED")
        self.assertEqual(value["failure_code"], "BOARD_IDENTITY_MISMATCH")
        self.assertTrue(value["authorization_consumed"])
        self.assertFalse(value["replay_permitted"])
        contract.validate_b1_result(value)

    def test_b1_tamper_is_rejected(self) -> None:
        value = contract.expected_b1_result()
        value["failure_code"] = "OTHER"
        with self.assertRaisesRegex(contract.ContractError, "B1_RESULT_MISMATCH"):
            contract.validate_b1_result(value)

    def test_operator_report_is_explanatory_not_proof(self) -> None:
        value = contract.operator_usb_port_change_report()
        self.assertTrue(value["reported_usb_port_changed"])
        self.assertTrue(value["reported_same_test_board"])
        self.assertEqual(value["evidence_role"], "EXPLANATORY_NOT_CRYPTOGRAPHIC_PROOF")
        self.assertFalse(value["cryptographically_proves_same_hardware"])

    def test_location_change_alters_legacy_but_not_path_neutral_identity(self) -> None:
        first = contract.build_transport_evidence(self.identity())
        second = contract.build_transport_evidence(self.identity(
            device="/dev/cu.usbmodem-b",
            location="2-3",
            hwid="USB VID:PID=303A:1001 LOCATION=2-3",
        ))
        self.assertNotEqual(first["legacy_board_identity_sha256"], second["legacy_board_identity_sha256"])
        self.assertNotEqual(first["legacy_serial_identity_sha256"], second["legacy_serial_identity_sha256"])
        self.assertEqual(first["path_neutral_usb_identity_sha256"], second["path_neutral_usb_identity_sha256"])
        self.assertTrue(capture.transport_path_changed(first, second))
        self.assertTrue(capture.path_neutral_identity_matches(first, second))

    def test_transport_evidence_is_hash_only_and_precomparison(self) -> None:
        value = contract.build_transport_evidence(self.identity())
        self.assertTrue(value["captured_before_identity_comparison"])
        self.assertTrue(value["transport_path_is_audit_only"])
        self.assertFalse(value["location_is_hardware_identity"])
        self.assertFalse(value["raw_device_path_included"])
        self.assertFalse(value["raw_location_included"])
        for key in ("device_path_sha256", "location_sha256", "hwid_sha256", "path_neutral_usb_identity_sha256"):
            self.assertRegex(value[key], r"^[0-9a-f]{64}$")

    def test_chip_mac_is_hashed_not_exposed(self) -> None:
        digest, count = contract.extract_chip_mac_sha256("Chip is ESP32-C6\nMAC: aa:bb:cc:dd:ee:ff\n")
        self.assertEqual(count, 1)
        self.assertEqual(digest, contract.sha256_text("aa:bb:cc:dd:ee:ff"))
        self.assertNotIn("aa:bb", digest or "")

    def test_path_neutral_baseline_retains_legacy_comparison(self) -> None:
        transport = contract.build_transport_evidence(self.identity(location="different"))
        value = contract.build_path_neutral_baseline_evidence(
            transport_evidence=transport,
            chip_id_output_sha256="1" * 64,
            flash_id_output_sha256="2" * 64,
            test_partition_sha256="3" * 64,
            test_partition_size=0x10000,
            chip_mac_sha256="4" * 64,
            chip_mac_candidate_count=1,
        )
        self.assertEqual(value["policy_version"], 3)
        self.assertFalse(value["legacy_board_identity_matches"])
        self.assertRegex(value["observed_path_neutral_baseline_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(value["before_destructive_operation"])
        self.assertFalse(value["raw_chip_output_included"])

    def test_b2_request_is_unauthorized_and_creates_no_physical_request(self) -> None:
        value = contract.build_b2_request_draft("a" * 40, "b" * 64)
        self.assertEqual(value["authorization_id"], contract.FUTURE_B2_AUTHORIZATION_ID)
        self.assertFalse(value["authorized"])
        self.assertFalse(value["future_physical_request_created"])
        self.assertFalse(value["legacy_board_identity_is_blocking"])
        self.assertTrue(value["transport_observation_must_be_saved_before_comparison"])

    def test_b2_authorization_is_exact_and_time_limited(self) -> None:
        now = datetime(2026, 7, 28, 17, 0, tzinfo=timezone.utc)
        value = {
            "schema": contract.B2_AUTH_SCHEMA,
            "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
            "operation": contract.FUTURE_B2_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "source_sha": "a" * 40,
            "review_binding_sha256": "b" * 64,
            "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
            "b1_authorization_id": contract.B1_AUTHORIZATION_ID,
            "b1_result_sha256": contract.B1_RESULT_SHA256,
            "b1_failure_code": contract.B1_FAILURE_CODE,
            "operator_report_id": contract.OPERATOR_REPORT_ID,
            "operator_reported_usb_port_changed": True,
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
            "legacy_board_identity_is_blocking": False,
            "legacy_serial_identity_is_blocking": False,
            "future_physical_request_created": False,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
        }
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        validated = contract.validate_b2_authorization(
            value,
            source_sha="a" * 40,
            review_binding_sha256="b" * 64,
            diagnostic_script_sha256="c" * 64,
            python_executable_sha256="d" * 64,
            esptool_executable_sha256="e" * 64,
            now=now + timedelta(minutes=1),
        )
        self.assertEqual(validated["authorization_record_sha256"], value["authorization_record_sha256"])

    def test_b2_probe_has_readonly_boundary_and_no_legacy_block(self) -> None:
        source = (TOOLS / "h3_n2_stage2d9r_g3r_usb_and_baseline_diagnostic_probe_20260728_v1.py").read_text()
        self.assertIn('"chip_id"', source)
        self.assertIn('"flash_id"', source)
        self.assertIn('"read_flash"', source)
        self.assertNotIn("BOARD_IDENTITY_MISMATCH", source)
        self.assertNotIn("SERIAL_IDENTITY_MISMATCH", source)
        for forbidden in (
            "serial.Serial(", '"write_flash"', '"erase_flash"', '"erase_region"',
            "import socket", "mosquitto", "GH2D9R_PREPARE", "GH2D9R_VERIFY",
        ):
            self.assertNotIn(forbidden, source, forbidden)

    @unittest.skipUnless(os.environ.get("STAGE2D9R_USB_REPAIR_UPSTREAM_ARTIFACT_ZIP"), "real upstream Artifact not supplied")
    def test_real_artifact_packaging_is_deterministic(self) -> None:
        artifact = Path(os.environ["STAGE2D9R_USB_REPAIR_UPSTREAM_ARTIFACT_ZIP"])
        with tempfile.TemporaryDirectory() as directory:
            lane_a = Path(directory) / "a"
            lane_b = Path(directory) / "b"
            result_a = packager.build(ROOT, artifact, lane_a, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            result_b = packager.build(ROOT, artifact, lane_b, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            self.assertEqual(result_a["archive_sha256"], result_b["archive_sha256"])
            self.assertEqual(packager.recursive_files(lane_a), packager.recursive_files(lane_b))
            request = json.loads((lane_a / packager.B2_REQUEST_FILE).read_text())
            self.assertFalse(request["authorized"])
            self.assertFalse(request["future_physical_request_created"])
            report = json.loads((lane_a / packager.OPERATOR_REPORT_FILE).read_text())
            self.assertEqual(report["evidence_role"], contract.OPERATOR_REPORT_EVIDENCE_ROLE)


if __name__ == "__main__":
    unittest.main()
