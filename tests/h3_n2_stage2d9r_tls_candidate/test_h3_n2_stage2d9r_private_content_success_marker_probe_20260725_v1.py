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
    / "h3_n2_stage2d9r_private_content_success_marker_probe_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_u1_04_success_marker_probe", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SuccessMarkerProbeTests(unittest.TestCase):
    def marker(self) -> dict[str, object]:
        return {
            "schema": "gh.h3.n2.stage2d9r-private-content-binding-u1-consumption/1",
            "authorization_id": MODULE.AUTHORIZATION_ID,
            "status": "CONSUMED",
            "record_sha256": MODULE.EXPECTED_RECORD_SHA256,
            "claimed_at": "2026-07-24T16:08:00Z",
            "consumed_at": "2026-07-24T16:08:01Z",
            "result_sha256": MODULE.EXPECTED_RESULT_SHA256,
            "failure_code": None,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
        }

    def write_marker(self, home: Path, payload: dict[str, object]) -> Path:
        auth = home / MODULE.AUTH_RELATIVE
        auth.mkdir(parents=True, mode=0o700)
        os.chmod(auth, 0o700)
        path = MODULE.marker_path(home)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def test_valid_marker_is_read_only_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            os.chmod(home, 0o700)
            path = self.write_marker(home, self.marker())
            before = path.read_bytes()
            result = MODULE.probe(home)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result["status"], "CONSUMED")
            self.assertEqual(result["result_sha256"], MODULE.EXPECTED_RESULT_SHA256)
            self.assertEqual(result["record_sha256"], MODULE.EXPECTED_RECORD_SHA256)
            self.assertEqual(result["marker_sha256"], MODULE.sha256_bytes(before))
            self.assertFalse(result["private_content_read"])
            self.assertFalse(result["marker_modified"])
            self.assertFalse(result["network_operation"])
            self.assertFalse(result["board_operation"])
            self.assertFalse(result["prepare_executed"])
            self.assertFalse(result["verify_executed"])

    def test_missing_authorization_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            os.chmod(home, 0o700)
            with self.assertRaisesRegex(
                MODULE.MarkerProbeError, "AUTHORIZATION_DIRECTORY_INVALID"
            ):
                MODULE.probe(home)

    def test_wrong_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            os.chmod(home, 0o700)
            payload = self.marker()
            payload["status"] = "CONSUMED_FAILED"
            self.write_marker(home, payload)
            with self.assertRaisesRegex(MODULE.MarkerProbeError, "U1_04_STATUS_MISMATCH"):
                MODULE.probe(home)

    def test_wrong_result_digest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            os.chmod(home, 0o700)
            payload = self.marker()
            payload["result_sha256"] = "0" * 64
            self.write_marker(home, payload)
            with self.assertRaisesRegex(MODULE.MarkerProbeError, "U1_04_RESULT_MISMATCH"):
                MODULE.probe(home)


if __name__ == "__main__":
    unittest.main()
