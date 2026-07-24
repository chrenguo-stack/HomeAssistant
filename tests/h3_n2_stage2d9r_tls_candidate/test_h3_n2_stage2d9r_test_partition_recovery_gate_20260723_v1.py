#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_test_partition_recovery_gate_20260723_v1.py"
TEMPLATE = Path(__file__).with_name(
    "stage2d9r_test_partition_recovery_manifest_20260723_v1.json.template"
)
spec = importlib.util.spec_from_file_location("stage2d9r_recovery", TOOL)
assert spec is not None and spec.loader is not None
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class Stage2D9RTestPartitionRecoveryGateTest(unittest.TestCase):
    def locked(self) -> dict:
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def authorized(self) -> dict:
        data = self.locked()
        data["state"] = recovery.AUTHORIZED
        data["source_sha"] = "1" * 40
        data["recovery_tool_sha256"] = "2" * 64
        data["python_environment_sha256"] = "3" * 64
        data["serial_path"] = "/dev/cu.usbmodem-stage2d9r"
        data["board_binding_sha256"] = "4" * 64
        data["current_firmware_artifact_sha256"] = "5" * 64
        data["current_candidate_digest_sha256"] = "6" * 64
        data["current_partition_sha256"] = "7" * 64
        data["authorization"] = {
            "authorization_id": "D2-H3N2-STAGE2D9R-RECOVERY-20260723-01",
            "operation": "ERASE_TEST_PARTITION",
            "one_shot": True,
            "replay_permitted": False,
            "authorized": True,
            "consumed": False,
            "issued_at": "2026-07-23T12:00:00Z",
            "expires_at": "2026-07-23T14:00:00Z",
            "record_sha256": "8" * 64,
        }
        for key in (
            "recovery_authorized",
            "board_operation_authorized",
            "serial_operation_authorized",
            "flash_operation_authorized",
        ):
            data[key] = True
        return data

    def assert_invalid(self, data: dict, message: str) -> None:
        with self.assertRaisesRegex(recovery.RecoveryError, message):
            recovery.validate(data)

    def test_locked_template_passes(self) -> None:
        self.assertEqual(recovery.validate(self.locked(), recovery.LOCKED), recovery.LOCKED)

    def test_authorized_manifest_passes(self) -> None:
        self.assertEqual(
            recovery.validate(self.authorized(), recovery.AUTHORIZED),
            recovery.AUTHORIZED,
        )

    def test_partition_geometry_and_erased_hash_are_exact(self) -> None:
        for key, value in (
            ("address", 0x410000),
            ("size_bytes", 0x20000),
            ("expected_erased_byte", 0),
            ("expected_erased_sha256", "0" * 64),
        ):
            data = self.locked()
            data["partition"][key] = value
            self.assert_invalid(data, "partition contract mismatch")

    def test_recovery_counts_cannot_expand(self) -> None:
        for key in recovery.EXPECTED_COUNTS:
            data = self.locked()
            data["allowed_counts"][key] += 1
            self.assert_invalid(data, "allowed counts mismatch")

    def test_pre_and_post_states_are_exact(self) -> None:
        data = self.locked()
        data["expected_pre_state"]["candidate_state"] = "ACTIVE"
        self.assert_invalid(data, "expected pre-state mismatch")
        data = self.locked()
        data["expected_post_state"]["candidate_generation"] = 1
        self.assert_invalid(data, "expected post-state mismatch")

    def test_locked_template_has_no_destructive_authorization(self) -> None:
        for key in (
            "recovery_authorized",
            "board_operation_authorized",
            "serial_operation_authorized",
            "flash_operation_authorized",
        ):
            data = self.locked()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false while locked")

    def test_network_firmware_commands_and_security_operations_stay_false(self) -> None:
        for key in recovery.ALWAYS_FALSE:
            data = self.authorized()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_authorized_manifest_requires_exact_hashes_and_absolute_serial(self) -> None:
        data = self.authorized()
        data["source_sha"] = "bad"
        self.assert_invalid(data, "source_sha invalid")
        data = self.authorized()
        data["recovery_tool_sha256"] = "bad"
        self.assert_invalid(data, "recovery_tool_sha256 invalid")
        data = self.authorized()
        data["serial_path"] = "relative/device"
        self.assert_invalid(data, "serial_path must be absolute")

    def test_authorization_is_d2_one_shot_unconsumed_and_short_lived(self) -> None:
        data = self.authorized()
        data["authorization"]["authorization_id"] = "U1-wrong"
        self.assert_invalid(data, "authorization id invalid")
        data = self.authorized()
        data["authorization"]["consumed"] = True
        self.assert_invalid(data, "pre-execution manifest must not be consumed")
        data = self.authorized()
        data["authorization"]["expires_at"] = "2026-07-23T14:00:01Z"
        self.assert_invalid(data, "authorization interval exceeds two hours")

    def test_locked_template_rejects_bound_authorization_metadata(self) -> None:
        data = self.locked()
        data["authorization"]["authorization_id"] = "D2-placeholder"
        self.assert_invalid(data, "locked authorization id must be null")
        data = self.locked()
        data["authorization"]["issued_at"] = "2026-07-23T12:00:00Z"
        self.assert_invalid(data, "locked issued_at must be null")

    def test_validation_does_not_mutate_input(self) -> None:
        data = self.authorized()
        original = deepcopy(data)
        recovery.validate(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
