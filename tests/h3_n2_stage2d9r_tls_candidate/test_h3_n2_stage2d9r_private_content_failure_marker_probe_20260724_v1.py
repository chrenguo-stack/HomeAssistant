#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/h3_n2_stage2d9r_private_content_failure_marker_probe_20260724_v1.py"
SPEC = importlib.util.spec_from_file_location("failure_marker_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class FailureMarkerProbeTest(unittest.TestCase):
    def _write_marker(self, home: Path, **overrides: object) -> tuple[Path, bytes]:
        auth = home / probe.AUTH_RELATIVE
        auth.mkdir(parents=True, mode=0o700)
        os.chmod(auth, 0o700)
        claimed = datetime.now(timezone.utc).replace(microsecond=0)
        value = {
            "schema": "gh.h3.n2.stage2d9r-private-content-binding-u1-consumption/1",
            "authorization_id": probe.AUTHORIZATION_ID,
            "status": "CONSUMED_FAILED",
            "record_sha256": probe.EXPECTED_RECORD_SHA256,
            "claimed_at": claimed.isoformat().replace("+00:00", "Z"),
            "consumed_at": (claimed + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            "result_sha256": None,
            "failure_code": probe.EXPECTED_FAILURE_CODE,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
        }
        value.update(overrides)
        raw = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
        path = probe.marker_path(home)
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        return path, raw

    def test_probe_reports_only_safe_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            _, raw = self._write_marker(home)
            result = probe.probe(home)
            self.assertEqual(result["marker_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result["status"], "CONSUMED_FAILED")
            self.assertFalse(result["private_content_read"])
            self.assertFalse(result["private_paths_included"])
            self.assertFalse(result["secret_values_included"])
            self.assertFalse(result["marker_modified"])

    def test_probe_rejects_wrong_failure_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self._write_marker(home, failure_code="OTHER")
            with self.assertRaisesRegex(probe.MarkerProbeError, "U1_03_FAILURE_CODE_MISMATCH"):
                probe.probe(home)

    def test_probe_rejects_marker_mode_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            path, _ = self._write_marker(home)
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(probe.MarkerProbeError, "U1_03_MARKER_MODE_MISMATCH"):
                probe.probe(home)

    def test_source_has_no_write_network_or_board_operations(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "import socket",
            "import serial",
            "esptool",
            "mosquitto_sub",
            "mosquitto_pub",
            "write_text(",
            "write_bytes(",
            "os.open(",
            "subprocess",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
