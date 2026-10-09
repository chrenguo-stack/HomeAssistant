from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import controlled_window as window


class ControlledBackupWindowSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.origin = {"Id": "old-manager", "State": {"Running": True}}
        self.broker = {"Id": "broker", "State": {"Running": True}}

    def driver(self, *, permitted=True, stop=None, capture=None, resume=None):
        return window.run_window(
            self.root,
            allow_stop=permitted,
            stop_action=stop if stop is not None else lambda: None,
            capture=capture if capture is not None else lambda _: None,
            resume=resume if resume is not None else lambda: None,
            now=lambda: 1.0,
        )

    def test_success_always_resumes_original(self) -> None:
        events = []
        with patch.object(window, "get_private_origin", return_value=(self.origin, self.broker)):
            with patch.object(window, "check_old_running"):
                with patch.object(window, "check_old_stopped"):
                    self.driver(
                        stop=lambda: events.append("stop"),
                        capture=lambda _: events.append("capture"),
                        resume=lambda: events.append("resume"),
                    )
        self.assertEqual(events, ["stop", "capture", "resume"])

    def test_capture_failure_still_resumes_original(self) -> None:
        events = []
        def fail_capture(_: Path) -> None:
            events.append("capture_failed")
            raise window.WindowStop("SYNTHETIC_COPY_FAIL")
        with patch.object(window, "get_private_origin", return_value=(self.origin, self.broker)):
            with patch.object(window, "check_old_running"):
                with patch.object(window, "check_old_stopped"):
                    with self.assertRaisesRegex(
                        window.WindowStop, "COLD_BACKUP_OR_STOP_FAILED_OLD_MANAGER_RESUMED"
                    ):
                        self.driver(
                            stop=lambda: events.append("stop"),
                            capture=fail_capture,
                            resume=lambda: events.append("resume"),
                        )
        self.assertEqual(events, ["stop", "capture_failed", "resume"])

    def test_stop_failure_attempts_resume_anyway(self) -> None:
        events = []
        def fail_stop() -> None:
            events.append("stop_failed")
            raise window.WindowStop("SYNTHETIC_STOP_ERROR")
        with patch.object(window, "get_private_origin", return_value=(self.origin, self.broker)):
            with patch.object(window, "check_old_running"):
                with self.assertRaises(window.WindowStop):
                    self.driver(stop=fail_stop, resume=lambda: events.append("resume"))
        self.assertEqual(events, ["stop_failed", "resume"])

    def test_no_permission_refuses_to_stop(self) -> None:
        with self.assertRaisesRegex(window.WindowStop, "STOP_WINDOW_NOT_AUTHORIZED"):
            self.driver(
                permitted=False,
                stop=lambda: self.fail("MUST_NOT_STOP"),
                resume=lambda: self.fail("MUST_NOT_RESUME"),
            )

    def test_existing_snapshot_refuses_before_stop(self) -> None:
        (self.root / "cold-snapshot").mkdir()
        with patch.object(window, "get_private_origin", return_value=(self.origin, self.broker)):
            with patch.object(window, "check_old_running"):
                with self.assertRaisesRegex(window.WindowStop, "PRIVATE_BACKUP_ALREADY_EXISTS"):
                    self.driver(stop=lambda: self.fail("MUST_NOT_STOP"))

    def test_recovery_failure_reports_stop(self) -> None:
        with patch.object(window, "get_private_origin", return_value=(self.origin, self.broker)):
            with patch.object(window, "check_old_running"):
                with patch.object(window, "check_old_stopped"):
                    with self.assertRaisesRegex(window.WindowStop, "OLD_MANAGER_RECOVERY_FAILED"):
                        self.driver(
                            capture=lambda _: None,
                            resume=lambda: (_ for _ in ()).throw(window.WindowStop("SYNTHETIC")),
                        )

    def test_unchanged_original_manager_is_restarted(self) -> None:
        stopped = {"Id": "old-manager", "State": {"Running": False}}
        running = {"Id": "old-manager", "State": {"Running": True}}
        with patch.object(window.snapshot, "inspect", side_effect=[stopped, running, running, running, self.broker]) as inspected:
            with patch.object(window, "run_docker") as run:
                with patch.object(window.time, "sleep"):
                    with patch.object(window.snapshot, "validate_runtime") as checked:
                        window.resume_original_manager(self.origin, self.broker)
        run.assert_called_once()
        checked.assert_called_once_with(self.origin, self.broker, "preflight")
        self.assertEqual(inspected.call_count, 5)

    def test_broker_changed_during_recovery_fails_closed(self) -> None:
        stopped = {"Id": "old-manager", "State": {"Running": False}}
        running = {"Id": "old-manager", "State": {"Running": True}}
        old_broker = {"State": {"StartedAt": "original"}, "RestartCount": 0}
        new_broker = {"State": {"StartedAt": "changed"}, "RestartCount": 1}
        with patch.object(window.snapshot, "inspect", side_effect=[stopped, running, running, running, new_broker]):
            with patch.object(window, "run_docker"):
                with patch.object(window.time, "sleep"):
                    with patch.object(window.snapshot, "validate_runtime"):
                        with self.assertRaisesRegex(window.WindowStop, "BROKER_STARTED_AT_CHANGED"):
                            window.resume_original_manager(self.origin, old_broker)


if __name__ == "__main__":
    unittest.main()
