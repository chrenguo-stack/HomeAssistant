#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_review_packager_20260727_v2.py"
SPEC = importlib.util.spec_from_file_location("stage2d9r_d2_review_v2_test", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
SOURCE = "d" * 40


class ReviewV2Tests(unittest.TestCase):
    def test_review_package_binds_exact_recovery_and_execution_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            summary = MODULE.assemble(
                output,
                SOURCE,
                MODULE.V1.CONTRACT.EXPECTED_MAIN_SHA,
            )
            binding = json.loads((output / "D2_REVIEW_BINDING.json").read_text())
            artifact = json.loads(
                (output / "FROZEN_RECOVERY_AND_EXECUTION_BINDING.json").read_text()
            )
            preflight = json.loads(
                (output / "READ_ONLY_PREFLIGHT_CONTRACT.json").read_text()
            )
            self.assertTrue(binding["frozen_locked_recovery_bound"])
            self.assertTrue(binding["frozen_execution_package_bound"])
            self.assertFalse(
                binding["arbitrary_recovery_or_execution_digest_accepted"]
            )
            self.assertEqual(
                binding["execution_package_sha256"],
                MODULE.EXECUTION_PACKAGE_SHA256,
            )
            self.assertEqual(
                binding["locked_recovery_package_sha256"],
                MODULE.RECOVERY_PAYLOAD_SHA256,
            )
            self.assertEqual(
                artifact["execution_package"]["artifact_id"],
                MODULE.EXECUTION_ARTIFACT_ID,
            )
            self.assertEqual(
                artifact["locked_recovery"]["artifact_id"],
                MODULE.RECOVERY_ARTIFACT_ID,
            )
            self.assertIn(
                "NO_ARBITRARY_RECOVERY_OR_EXECUTION_DIGESTS",
                preflight["required_checks"],
            )
            self.assertEqual(
                summary["review_binding_sha256"],
                binding["review_binding_sha256"],
            )
            self.assertTrue(
                (output / "LOCKED_RECOVERY_ARTIFACT_ACCEPTANCE.json").is_file()
            )
            self.assertTrue(
                (output / "D2_EXECUTION_PACKAGE_ACCEPTANCE.json").is_file()
            )
            covered = {
                line.split("  ", 1)[1]
                for line in (output / "SHA256SUMS").read_text().splitlines()
            }
            observed = {path.name for path in output.iterdir() if path.name != "SHA256SUMS"}
            self.assertEqual(covered, observed)

    def test_recovery_artifact_drift_fails_closed(self) -> None:
        recovery = json.loads(MODULE.DEFAULT_RECOVERY_ACCEPTANCE.read_text())
        execution = json.loads(MODULE.DEFAULT_EXECUTION_ACCEPTANCE.read_text())
        recovery["canonical_artifact"]["payload_tar_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            MODULE.ReviewV2Error,
            "RECOVERY_ACCEPTANCE_MISMATCH_PAYLOAD_TAR_SHA256",
        ):
            MODULE.validate_exact_acceptance(recovery, execution)

    def test_execution_authorization_expansion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "execution.json"
            value = json.loads(MODULE.DEFAULT_EXECUTION_ACCEPTANCE.read_text())
            value["protected_boundaries"]["execution_authorized"] = True
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.ReviewV2Error, "ACCEPTANCE_BOUNDARY_EXPANDED"
            ):
                MODULE.load_acceptance(
                    path,
                    MODULE.EXECUTION_SCHEMA,
                    "D2_EXECUTION_PACKAGE_REPRODUCIBLE_AND_FROZEN",
                )

    def test_review_package_contains_no_authorization_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            MODULE.assemble(
                output,
                SOURCE,
                MODULE.V1.CONTRACT.EXPECTED_MAIN_SHA,
            )
            joined = b"\n".join(
                path.read_bytes() for path in output.iterdir() if path.is_file()
            )
            self.assertNotIn(b'"authorized": true', joined)
            self.assertNotIn(b"BEGIN PRIVATE KEY", joined)
            binding = json.loads((output / "D2_REVIEW_BINDING.json").read_text())
            self.assertFalse(binding["exact_authorization_request_included"])
            self.assertFalse(binding["authorization_record_included"])
            self.assertFalse(binding["board_operation"])
            self.assertFalse(binding["serial_operation"])
            self.assertFalse(binding["flash_operation"])


if __name__ == "__main__":
    unittest.main()
