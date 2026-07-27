#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[2]
PROBE = (
    REPOSITORY
    / "tools"
    / "h3_n2_stage2d9r_successor_private_execution_material_success_marker_probe_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_success_marker_probe", PROBE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def marker_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": MODULE.MARKER_SCHEMA,
        "authorization_id": MODULE.AUTHORIZATION_ID,
        "status": "CONSUMED",
        "record_sha256": MODULE.RECORD_SHA256,
        "public_descriptor_sha256": MODULE.PUBLIC_DESCRIPTOR_SHA256,
        "claimed_at": "2026-07-25T05:30:00Z",
        "consumed_at": "2026-07-25T05:31:00Z",
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
        "failure_code": None,
    }
    payload.update(overrides)
    return payload


class SuccessMarkerProbeTests(unittest.TestCase):
    def write_marker(self, root: Path, payload: dict[str, object]) -> Path:
        marker = root / "marker.json"
        marker.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return marker

    def test_valid_consumed_marker_passes_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = self.write_marker(Path(temporary), marker_payload())
            before = marker.read_bytes()
            result = MODULE.validate_marker(marker)
            self.assertEqual(result["status"], "CONSUMED")
            self.assertEqual(result["record_sha256"], MODULE.RECORD_SHA256)
            self.assertEqual(
                result["public_descriptor_sha256"], MODULE.PUBLIC_DESCRIPTOR_SHA256
            )
            self.assertFalse(result["marker_modified"])
            self.assertFalse(result["private_content_read"])
            self.assertEqual(marker.read_bytes(), before)

    def test_failed_or_claimed_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = self.write_marker(
                Path(temporary), marker_payload(status="CONSUMED_FAILED")
            )
            with self.assertRaisesRegex(MODULE.ProbeError, "MARKER_STATUS_MISMATCH"):
                MODULE.validate_marker(marker)

    def test_record_and_public_descriptor_drift_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = self.write_marker(root, marker_payload(record_sha256="0" * 64))
            with self.assertRaisesRegex(MODULE.ProbeError, "RECORD_SHA256_MISMATCH"):
                MODULE.validate_marker(marker)
            marker.write_text(
                json.dumps(marker_payload(public_descriptor_sha256="0" * 64)) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MODULE.ProbeError, "PUBLIC_DESCRIPTOR_SHA256_MISMATCH"
            ):
                MODULE.validate_marker(marker)

    def test_failure_code_and_replay_flags_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = self.write_marker(root, marker_payload(failure_code="X"))
            with self.assertRaisesRegex(
                MODULE.ProbeError, "MARKER_FAILURE_CODE_PRESENT"
            ):
                MODULE.validate_marker(marker)
            marker.write_text(
                json.dumps(marker_payload(replay_permitted=True)) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MODULE.ProbeError, "REPLAY_BOUNDARY_MISMATCH"
            ):
                MODULE.validate_marker(marker)

    def test_timestamp_order_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = self.write_marker(
                Path(temporary),
                marker_payload(
                    claimed_at="2026-07-25T05:32:00Z",
                    consumed_at="2026-07-25T05:31:00Z",
                ),
            )
            with self.assertRaisesRegex(
                MODULE.ProbeError, "MARKER_TIMESTAMP_ORDER_INVALID"
            ):
                MODULE.validate_marker(marker)

    def test_source_contains_no_execution_or_private_material_reads(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        for forbidden in (
            "serial.Serial",
            "esptool",
            "socket.socket",
            "subprocess",
            "mosquitto_pub",
            "mosquitto_sub",
            "mqtt-password.hex",
            "persistence-key.hex",
            "unlock-token.hex",
            "prepare-command.txt",
            "verify-command.txt",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
