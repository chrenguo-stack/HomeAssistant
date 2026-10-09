from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import one_shot_operator as one


class OneShotMockedExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_status_wait_requires_submitted_job_actually_started(self) -> None:
        observations = iter([
            {
                "LoadState": "loaded", "ActiveState": "inactive",
                "Result": "success", "ExecMainStartTimestampMonotonic": "0",
            },
            {
                "LoadState": "loaded", "ActiveState": "activating",
                "Result": "success", "ExecMainStartTimestampMonotonic": "100",
            },
            {
                "LoadState": "loaded", "ActiveState": "inactive",
                "Result": "success", "ExecMainStartTimestampMonotonic": "100",
            },
        ])
        times = iter([0, 0, 0, 0, 0, 0])
        with patch.object(one, "one_shot_status", side_effect=lambda: next(observations)) as status:
            one.wait_for_completed_unit(now=lambda: next(times), sleep=lambda _: None)
        self.assertEqual(status.call_count, 3)

    def test_failed_systemd_result_never_counts_as_pass(self) -> None:
        result = {
            "LoadState": "loaded", "ActiveState": "failed",
            "Result": "exit-code", "ExecMainStartTimestampMonotonic": "100",
        }
        with patch.object(one, "one_shot_status", return_value=result):
            with self.assertRaisesRegex(one.GateError, "ONE_SHOT_UNIT_FAILED"):
                one.wait_for_completed_unit(now=lambda: 0, sleep=lambda _: None)

    def test_no_started_job_never_false_passes(self) -> None:
        result = {
            "LoadState": "loaded", "ActiveState": "inactive",
            "Result": "success", "ExecMainStartTimestampMonotonic": "0",
        }
        times = iter([0, 0, 390, 391])
        with patch.object(one, "one_shot_status", return_value=result):
            with self.assertRaisesRegex(one.GateError, "ONE_SHOT_WAIT_LIMIT_REACHED"):
                one.wait_for_completed_unit(now=lambda: next(times), sleep=lambda _: None)

    def test_one_shot_unit_collision_refuses_even_if_run_dir_empty(self) -> None:
        with patch.object(one, "UNIT_DEST", self.root / "not-present.service"):
            with patch.object(one, "invoke") as runner:
                runner.return_value.returncode = 0
                runner.return_value.stdout = "loaded\n"
                self.assertNotEqual(runner.return_value.stdout.strip(), "not-found")

    def test_reject_other_host_process_holding_sqlite(self) -> None:
        with patch.object(one, "manager_process_opener_owner", return_value=False):
            with patch.object(one, "invoke") as proc:
                proc.return_value.returncode = 0
                proc.return_value.stdout = "1000"
                manager = {"State": {"Pid": 25}}
                sources = {
                    one.snapshot.RW["registration"]: self.root,
                    one.snapshot.RW["n3w"]: self.root,
                    one.snapshot.RW["relay_keys"]: self.root,
                }
                for _, name in one.snapshot.DATABASES:
                    (self.root / name).write_bytes(b"synthetic")
                with self.assertRaisesRegex(one.GateError, "OTHER_HOST_PROCESS_DB_OPENER_BLOCKED"):
                    one.check_db_openers_owned_by_old_manager(manager, sources)

    def test_restore_status_refuses_missing_semantic_evidence(self) -> None:
        current = {
            "Id": "old", "State": {"Running": True},
        }
        broker = {
            "State": {"StartedAt": "same"}, "RestartCount": 0,
        }
        with patch.object(one.window, "get_private_origin", return_value=(current, broker)):
            with patch.object(one.window, "check_old_running"):
                with patch.object(one.snapshot, "inspect", side_effect=[current, broker]):
                    with self.assertRaisesRegex(one.GateError, "BUSINESS_EVIDENCE_MISSING"):
                        one.verify_old_manager_and_report(self.root)


if __name__ == "__main__":
    unittest.main()
