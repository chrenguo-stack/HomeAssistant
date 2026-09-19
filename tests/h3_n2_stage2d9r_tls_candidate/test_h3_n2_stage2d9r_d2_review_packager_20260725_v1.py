#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

TOOL = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "h3_n2_stage2d9r_d2_review_packager_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_d2_review_packager", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SOURCE = "a" * 40


class D2ReviewPackagerTests(unittest.TestCase):
    def test_assemble_exact_public_review_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "package"
            summary = MODULE.assemble(output, SOURCE, MODULE.EXPECTED_MAIN_SHA)
            binding = json.loads((output / "D2_REVIEW_BINDING.json").read_text())
            self.assertEqual(summary["state"], "PENDING_EXACT_D2_REVIEW")
            self.assertEqual(binding["source_sha"], SOURCE)
            self.assertEqual(binding["d2_request_id"], MODULE.D2_REQUEST_ID)
            self.assertFalse(binding["authorization_record_included"])
            self.assertFalse(binding["authorized_execution_launcher_included"])
            self.assertFalse(binding["private_content_included"])
            self.assertFalse(binding["network_operation"])
            self.assertFalse(binding["board_operation"])
            self.assertFalse(binding["flash_operation"])
            self.assertFalse(binding["prepare_executed"])
            self.assertFalse(binding["verify_executed"])

            copied = dict(binding)
            observed = copied.pop("review_binding_sha256")
            self.assertEqual(observed, MODULE.sha256_bytes(MODULE.canonical_json_bytes(copied)))

            covered = {
                line.split("  ", 1)[1]
                for line in (output / "SHA256SUMS").read_text().splitlines()
            }
            observed_files = {
                path.name for path in output.iterdir() if path.name != "SHA256SUMS"
            }
            self.assertEqual(covered, observed_files)

    def test_wrong_main_fails_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.ReviewPackageError, "MAIN_SHA_MISMATCH"):
            MODULE.build_binding(SOURCE, "b" * 40)

    def test_existing_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "package"
            output.mkdir()
            with self.assertRaisesRegex(MODULE.ReviewPackageError, "OUTPUT_ALREADY_EXISTS"):
                MODULE.assemble(output, SOURCE, MODULE.EXPECTED_MAIN_SHA)

    def test_package_contains_no_private_material_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "package"
            MODULE.assemble(output, SOURCE, MODULE.EXPECTED_MAIN_SHA)
            joined = b"\n".join(path.read_bytes() for path in output.iterdir())
            for forbidden in (
                b"BEGIN PRIVATE KEY",
                b"BEGIN RSA PRIVATE KEY",
                b"BEGIN EC PRIVATE KEY",
                b"unlock-token.hex",
                b"/Users/",
                b"/private/tmp/",
            ):
                self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
