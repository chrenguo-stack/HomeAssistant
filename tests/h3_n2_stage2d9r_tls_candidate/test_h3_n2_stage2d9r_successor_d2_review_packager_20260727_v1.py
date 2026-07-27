#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_review_packager_20260727_v1.py"
SPEC = importlib.util.spec_from_file_location("review", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = "d" * 40

class ReviewPackagerTests(unittest.TestCase):
    def test_assemble_public_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            summary = MODULE.assemble(output, SOURCE, MODULE.CONTRACT.EXPECTED_MAIN_SHA)
            binding = json.loads((output / "D2_REVIEW_BINDING.json").read_text())
            contract = json.loads((output / "D2_CONTRACT.json").read_text())
            preflight = json.loads((output / "READ_ONLY_PREFLIGHT_CONTRACT.json").read_text())
            request_schema = json.loads((output / "EXACT_D2_AUTHORIZATION_REQUEST_SCHEMA.json").read_text())
            result_schema = json.loads((output / "D2_PUBLIC_RESULT_SCHEMA.json").read_text())
            marker_schema = json.loads((output / "D2_CONSUMED_MARKER_SCHEMA.json").read_text())
            execution_contract = json.loads((output / "D2_EXECUTION_PACKAGE_CONTRACT.json").read_text())
            self.assertEqual(summary["state"], "D2_REVIEWED")
            self.assertFalse(binding["exact_authorization_request_included"])
            self.assertFalse(binding["authorization_record_included"])
            self.assertTrue(binding["execution_package_contract_included"])
            self.assertFalse(binding["execution_launcher_included"])
            self.assertFalse(binding["board_operation"])
            self.assertFalse(binding["serial_operation"])
            self.assertEqual(contract["state_machine"]["prepare_max_count"], 1)
            self.assertIn("ACTIVATE", contract["prohibited_operations"])
            self.assertIn("TARGET_BOARD_CONNECTION", preflight["deferred_until_exact_d2_claim"])
            self.assertIn("baseline_state_sha256", request_schema["required_fields"])
            self.assertIn("CONSUMED_FAILED", result_schema["terminal_results"])
            self.assertFalse(marker_schema["replay_permitted"])
            self.assertEqual(execution_contract["locked_recovery_max_count"], 1)
            covered = {
                line.split("  ", 1)[1]
                for line in (output / "SHA256SUMS").read_text().splitlines()
            }
            observed = {p.name for p in output.iterdir() if p.name != "SHA256SUMS"}
            self.assertEqual(covered, observed)

    def test_wrong_main_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(MODULE.CONTRACT.ContractError, "MAIN_SHA_MISMATCH"):
                MODULE.assemble(Path(temp) / "review", SOURCE, "e" * 40)

    def test_existing_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            output.mkdir()
            with self.assertRaisesRegex(MODULE.ReviewError, "OUTPUT_ALREADY_EXISTS"):
                MODULE.assemble(output, SOURCE, MODULE.CONTRACT.EXPECTED_MAIN_SHA)

    def test_package_has_no_secret_or_exact_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            MODULE.assemble(output, SOURCE, MODULE.CONTRACT.EXPECTED_MAIN_SHA)
            joined = b"\n".join(path.read_bytes() for path in output.iterdir())
            for forbidden in (
                b"BEGIN PRIVATE KEY",
                b"BEGIN RSA PRIVATE KEY",
                b"BEGIN EC PRIVATE KEY",
                b"/Users/",
                b"/private/tmp/",
                b"authorized\": true",
                b"authorization_record_created\": true",
            ):
                self.assertNotIn(forbidden, joined)

if __name__ == "__main__":
    unittest.main()
