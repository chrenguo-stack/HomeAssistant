from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.h3_n2_stage2d9_v69_serial_capture_model_20260723_v1 import (
    CaptureFailure,
    capture_event_stream,
)


class Stage2D9V69SerialCaptureModelTest(unittest.TestCase):
    def assert_log(self, path: Path, expected: bytes, expected_sha: str) -> None:
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), expected_sha)

    def test_fail_marker_is_persisted_before_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prepare.log"
            events = [
                "stage2d9_v69_command_ready=PREPARE",
                "stage2d9_v69_executor=fail reason=command_execution",
            ]
            with self.assertRaises(CaptureFailure) as caught:
                capture_event_stream(events, path)
            state = caught.exception.state
            expected = ("\n".join(events) + "\n").encode()
            self.assertTrue(state.host_write_attempted)
            self.assertFalse(state.device_command_accepted)
            self.assertFalse(state.transaction_succeeded)
            self.assertEqual(state.terminal_reason, "device_fail_marker")
            self.assert_log(path, expected, state.log_sha256)

    def test_timeout_preserves_partial_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timeout.log"
            events = ["stage2d9_v69_command_ready=PREPARE"]
            with self.assertRaises(CaptureFailure) as caught:
                capture_event_stream(events, path)
            state = caught.exception.state
            expected = (events[0] + "\n").encode()
            self.assertTrue(state.host_write_attempted)
            self.assertFalse(state.device_command_accepted)
            self.assertFalse(state.transaction_succeeded)
            self.assertEqual(state.terminal_reason, "timeout")
            self.assert_log(path, expected, state.log_sha256)

    def test_host_exception_preserves_prior_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "exception.log"
            events = [
                "stage2d9_v69_command_ready=PREPARE",
                "unread-event",
            ]
            with self.assertRaises(CaptureFailure) as caught:
                capture_event_stream(events, path, inject_exception_at=1)
            state = caught.exception.state
            expected = (events[0] + "\n").encode()
            self.assertTrue(state.host_write_attempted)
            self.assertFalse(state.device_command_accepted)
            self.assertFalse(state.transaction_succeeded)
            self.assertEqual(state.terminal_reason, "host_exception")
            self.assert_log(path, expected, state.log_sha256)

    def test_pass_separates_acceptance_and_transaction_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pass.log"
            events = [
                "stage2d9_v69_command_accepted=true action=PREPARE",
                "stage2d9_v69_prepare=pass active_generation=0 candidate_generation=1",
            ]
            state = capture_event_stream(events, path)
            expected = ("\n".join(events) + "\n").encode()
            self.assertTrue(state.host_write_attempted)
            self.assertTrue(state.device_command_accepted)
            self.assertTrue(state.transaction_succeeded)
            self.assertEqual(state.terminal_reason, "pass")
            self.assert_log(path, expected, state.log_sha256)


if __name__ == "__main__":
    unittest.main()
