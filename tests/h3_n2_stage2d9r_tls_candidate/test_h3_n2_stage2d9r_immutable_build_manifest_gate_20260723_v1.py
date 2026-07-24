#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_immutable_build_manifest_gate_20260723_v1.py"
TEMPLATE = Path(__file__).with_name(
    "stage2d9r_immutable_build_manifest_20260723_v1.json.template"
)
spec = importlib.util.spec_from_file_location("stage2d9r_build", TOOL)
assert spec is not None and spec.loader is not None
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class Stage2D9RImmutableBuildManifestGateTest(unittest.TestCase):
    def locked(self) -> dict:
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def frozen(self) -> dict:
        data = self.locked()
        data["state"] = build.FROZEN
        data["source_sha"] = "1" * 40
        data["build_binding"] = "2" * 40
        data["python_environment_sha256"] = "3" * 64
        data["compile_workflow_sha256"] = "4" * 64
        data["compile_run_ids"] = [30000000001, 30000000002]
        for index, key in enumerate(
            ("ca_pem_sha256", "candidate_digest_sha256", "unlock_digest_sha256"),
            start=5,
        ):
            data["candidate_bindings"][key] = f"{index:x}"[-1] * 64
        data["partition"]["table_sha256"] = "8" * 64
        for index, key in enumerate(
            (
                "bootloader_sha256",
                "partition_table_bin_sha256",
                "application_sha256",
                "merged_image_sha256",
            ),
            start=9,
        ):
            data["firmware"][key] = f"{index:x}"[-1] * 64
        data["firmware"]["merged_image_size"] = 2097152
        data["reproducibility"] = {
            "clean_build_count": 2,
            "all_firmware_hashes_identical": True,
            "all_manifest_hashes_identical": True,
        }
        data["artifact"]["artifact_id"] = 8564000000
        data["artifact"]["artifact_sha256"] = "d" * 64
        data["artifact"]["manifest_sha256"] = "e" * 64
        return data

    def assert_invalid(self, data: dict, message: str) -> None:
        with self.assertRaisesRegex(build.BuildManifestError, message):
            build.validate(data)

    def test_locked_template_passes(self) -> None:
        self.assertEqual(build.validate(self.locked(), build.LOCKED), build.LOCKED)

    def test_frozen_manifest_passes(self) -> None:
        self.assertEqual(build.validate(self.frozen(), build.FROZEN), build.FROZEN)

    def test_candidate_and_partition_identity_are_exact(self) -> None:
        data = self.locked()
        data["candidate_bindings"]["broker_host"] = "localhost"
        self.assert_invalid(data, "broker host mismatch")
        data = self.locked()
        data["partition"]["address"] = 0x410000
        self.assert_invalid(data, "partition address mismatch")
        data = self.locked()
        data["partition"]["size_bytes"] = 0x20000
        self.assert_invalid(data, "partition size mismatch")

    def test_flash_offsets_are_exact(self) -> None:
        data = self.locked()
        data["firmware"]["flash_offsets"]["application"] = 0x20000
        self.assert_invalid(data, "flash offsets mismatch")

    def test_all_execution_and_release_flags_remain_false(self) -> None:
        for key in build.FALSE_FLAGS:
            data = self.locked()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_locked_state_cannot_claim_build_or_artifact_evidence(self) -> None:
        data = self.locked()
        data["compile_run_ids"] = [1]
        self.assert_invalid(data, "locked compile runs must be empty")
        data = self.locked()
        data["reproducibility"]["clean_build_count"] = 1
        self.assert_invalid(data, "locked clean build count must be zero")
        data = self.locked()
        data["artifact"]["artifact_id"] = 1
        self.assert_invalid(data, "locked artifact id must be null")

    def test_frozen_manifest_requires_two_unique_builds(self) -> None:
        for value in ([1], [1, 1], [0, 2], ["1", 2]):
            data = self.frozen()
            data["compile_run_ids"] = value
            self.assert_invalid(data, "compile_run_ids must contain two unique positive ids")

    def test_frozen_manifest_requires_all_hashes(self) -> None:
        data = self.frozen()
        data["python_environment_sha256"] = "bad"
        self.assert_invalid(data, "python_environment_sha256 invalid")
        data = self.frozen()
        data["candidate_bindings"]["ca_pem_sha256"] = "bad"
        self.assert_invalid(data, "ca_pem_sha256 invalid")
        data = self.frozen()
        data["firmware"]["application_sha256"] = "bad"
        self.assert_invalid(data, "application_sha256 invalid")
        data = self.frozen()
        data["artifact"]["artifact_sha256"] = "bad"
        self.assert_invalid(data, "artifact_sha256 invalid")

    def test_frozen_manifest_requires_reproducibility(self) -> None:
        data = self.frozen()
        data["reproducibility"]["clean_build_count"] = 1
        self.assert_invalid(data, "frozen clean build count must be two")
        data = self.frozen()
        data["reproducibility"]["all_firmware_hashes_identical"] = False
        self.assert_invalid(data, "firmware hashes are not reproducible")
        data = self.frozen()
        data["reproducibility"]["all_manifest_hashes_identical"] = False
        self.assert_invalid(data, "manifest hashes are not reproducible")

    def test_frozen_manifest_rejects_invalid_image_and_artifact_metadata(self) -> None:
        data = self.frozen()
        data["firmware"]["merged_image_size"] = 0
        self.assert_invalid(data, "merged image size invalid")
        data = self.frozen()
        data["artifact"]["artifact_id"] = 0
        self.assert_invalid(data, "artifact id invalid")
        data = self.frozen()
        data["artifact"]["expired"] = True
        self.assert_invalid(data, "artifact must not be expired")

    def test_validation_does_not_mutate_input(self) -> None:
        data = self.frozen()
        original = deepcopy(data)
        build.validate(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
