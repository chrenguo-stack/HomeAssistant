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

import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_capture_20260729_v1 as capture
import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_packager_20260729_v1 as packager
import h3_n2_stage2d9r_g3r_corrected_execution_closure_builder_20260729_v1 as builder


class BaselineAggregateDigestCorrectionTests(unittest.TestCase):
    def test_corrected_digest_recomputes_from_exact_frozen_components(self) -> None:
        self.assertEqual(contract.recompute_corrected_legacy_baseline_sha256(), contract.CORRECTED_LEGACY_BASELINE_SHA256)
        self.assertNotEqual(contract.CORRECTED_LEGACY_BASELINE_SHA256, contract.INVALID_LEGACY_BASELINE_SHA256)

    def test_invalid_digest_disposition_is_permanent_and_component_preserving(self) -> None:
        value = contract.invalid_legacy_digest_disposition()
        self.assertEqual(value["state"], "INVALID_DERIVED_AGGREGATE_DIGEST_PERMANENTLY_REJECTED")
        self.assertFalse(value["component_values_changed"])
        self.assertFalse(value["invalid_digest_reuse_permitted"])

    def test_b2_result_is_exact_consumed_pass(self) -> None:
        value = contract.expected_b2_result()
        self.assertEqual(value["status"], "CONSUMED_PASS")
        self.assertTrue(value["authorization_consumed"])
        self.assertFalse(value["flash_write"])
        contract.validate_b2_result(value)

    def test_b2_tamper_is_rejected(self) -> None:
        value = contract.expected_b2_result()
        value["baseline_evidence"]["test_partition_size"] = 1
        with self.assertRaisesRegex(contract.ContractError, "B2_RESULT_.*_MISMATCH"):
            contract.validate_b2_result(value)

    def test_corrected_candidate_does_not_create_or_authorize_physical_request(self) -> None:
        value = contract.corrected_baseline_candidate()
        self.assertFalse(value["accepted_for_physical_execution"])
        self.assertFalse(value["physical_request_created"])
        self.assertFalse(value["physical_request_authorized"])

    def test_mac_candidate_policy_preserves_ambiguous_hash_set(self) -> None:
        first = ":".join(("aa", "bb", "cc", "dd", "ee", "01"))
        second = ":".join(("aa", "bb", "cc", "dd", "ee", "02"))
        value = contract.extract_chip_mac_candidate_evidence(f"MAC: {first}\nUSB MAC: {second}\n")
        self.assertEqual(value["selection_state"], "AMBIGUOUS_CANDIDATES")
        self.assertEqual(value["candidate_count"], 2)
        self.assertIsNone(value["selected_chip_mac_sha256"])
        self.assertEqual(len(value["candidate_records"]), 2)
        self.assertFalse(value["raw_mac_values_included"])

    def test_mac_candidate_policy_selects_only_unique_candidate(self) -> None:
        value_text = ":".join(("aa", "bb", "cc", "dd", "ee", "03"))
        value = contract.extract_chip_mac_candidate_evidence(f"MAC: {value_text}\nRepeated: {value_text}\n")
        self.assertEqual(value["selection_state"], "UNIQUE_CANDIDATE")
        self.assertEqual(value["candidate_count"], 1)
        self.assertEqual(value["selected_chip_mac_sha256"], contract.sha256_text(value_text))

    def test_closure_binds_corrected_digest_and_b2_without_physical_request(self) -> None:
        value = contract.build_corrected_execution_closure("a" * 40, "b" * 64)
        self.assertEqual(value["corrected_legacy_baseline_sha256"], contract.CORRECTED_LEGACY_BASELINE_SHA256)
        self.assertEqual(value["b2_result_sha256"], contract.B2_RESULT_SHA256)
        self.assertFalse(value["physical_request_created"])
        self.assertFalse(value["physical_request_authorized"])

    def test_h5_request_is_unauthorized_host_only_next_gate(self) -> None:
        value = contract.build_h5_request_draft("a" * 40, "b" * 64)
        self.assertEqual(value["authorization_id"], contract.H5_AUTHORIZATION_ID)
        self.assertFalse(value["authorized"])
        self.assertFalse(value["physical_request_created"])

    def test_h5_authorization_is_exact_and_time_limited(self) -> None:
        now = datetime(2026, 7, 29, 1, 0, tzinfo=timezone.utc)
        closure = contract.build_corrected_execution_closure("a" * 40, "b" * 64)
        closure_sha = contract.canonical_json_sha256(closure)
        value = {
            "schema": contract.H5_AUTH_SCHEMA,
            "authorization_id": contract.H5_AUTHORIZATION_ID,
            "operation": contract.H5_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "source_sha": "a" * 40,
            "review_binding_sha256": "b" * 64,
            "corrected_execution_closure_sha256": closure_sha,
            "b2_result_sha256": contract.B2_RESULT_SHA256,
            "invalid_legacy_baseline_sha256": contract.INVALID_LEGACY_BASELINE_SHA256,
            "corrected_legacy_baseline_sha256": contract.CORRECTED_LEGACY_BASELINE_SHA256,
            "host_only": True,
            "board_operation_authorized": False,
            "usb_enumeration_authorized": False,
            "esptool_operation_authorized": False,
            "flash_write_authorized": False,
            "flash_erase_authorized": False,
            "network_after_authorization_authorized": False,
            "broker_operation_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "physical_request_generation_authorized": True,
            "physical_request_execution_authorized": False,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
        }
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        validated = contract.validate_h5_authorization(
            value, source_sha="a" * 40, review_binding_sha256="b" * 64,
            closure_sha256=closure_sha, now=now + timedelta(minutes=1),
        )
        self.assertEqual(validated["authorization_record_sha256"], value["authorization_record_sha256"])

    def test_capture_validates_exact_b2_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "b2-result.json"
            path.write_text(json.dumps(contract.expected_b2_result()), encoding="utf-8")
            result = capture.capture(path)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["physical_request_created"])

    def test_builder_does_not_generate_physical_request(self) -> None:
        value = builder.build("a" * 40, "b" * 64)
        self.assertFalse(value["physical_request_created"])
        self.assertFalse(value["physical_request_authorized"])
        self.assertEqual(value["h5_request_draft"]["authorization_id"], contract.H5_AUTHORIZATION_ID)

    @unittest.skipUnless(os.environ.get("STAGE2D9R_AGGREGATE_CORRECTION_UPSTREAM_ARTIFACT_ZIP"), "real upstream Artifact not supplied")
    def test_real_artifact_packaging_is_deterministic(self) -> None:
        artifact = Path(os.environ["STAGE2D9R_AGGREGATE_CORRECTION_UPSTREAM_ARTIFACT_ZIP"])
        with tempfile.TemporaryDirectory() as directory:
            lane_a = Path(directory) / "a"
            lane_b = Path(directory) / "b"
            result_a = packager.build(ROOT, artifact, lane_a, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            result_b = packager.build(ROOT, artifact, lane_b, "a" * 40, contract.REPOSITORY_HEAD_AT_REPAIR)
            self.assertEqual(result_a["archive_sha256"], result_b["archive_sha256"])
            self.assertEqual(packager.recursive_files(lane_a), packager.recursive_files(lane_b))
            request = json.loads((lane_a / packager.H5_REQUEST_FILE).read_text())
            self.assertFalse(request["authorized"])
            self.assertFalse(request["physical_request_created"])
            self.assertFalse((lane_a / "PHYSICAL_D2_REQUEST_05.json").exists())


if __name__ == "__main__":
    unittest.main()
