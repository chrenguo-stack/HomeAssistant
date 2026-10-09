from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

import fresh_manager_deploy as deploy
import fresh_manager_operator as operator
import fresh_manager_systemd_unit as unit


class SupervisedManagerGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)

    def test_authorized_main_reaches_guarded_final_check_and_seals_first(self):
        argv = [
            "operator", "execute", "--private-root", str(self.private),
            "--authorization-id", deploy.AUTHORIZATION_ID,
            "--permit-live-manager-replacement",
        ]
        actions = []
        with mock.patch("sys.argv", argv):
            with patch.object(operator.snapshot, "private_root", return_value=self.private):
                with patch.object(operator, "non_mutating_preflight", return_value="verified-unit"):
                    with patch.object(operator.r4_seal, "seal_r3_for_r4", side_effect=lambda p: actions.append("seal")) as seal:
                        with patch.object(operator, "execute", side_effect=lambda p, text: actions.append("guarded-execute")) as guarded:
                            operator.main()
                            seal.assert_called_once_with(self.private)
                            guarded.assert_called_once_with(self.private, text="verified-unit")
        self.assertEqual(actions, ["seal", "guarded-execute"])

    def test_unauthorized_main_never_seals_or_executes(self):
        argv = ["operator", "execute", "--private-root", str(self.private)]
        with mock.patch("sys.argv", argv):
            with patch.object(operator.snapshot, "private_root", return_value=self.private):
                with patch.object(operator, "non_mutating_preflight", return_value="verified-unit"):
                    with patch.object(operator.r4_seal, "seal_r3_for_r4") as seal:
                        with patch.object(operator, "execute") as guarded:
                            with self.assertRaisesRegex(operator.OperatorStop, "AUTHORIZATION_ID_MISMATCH"):
                                operator.main()
                            seal.assert_not_called()
                            guarded.assert_not_called()

    def test_systemd_never_claims_success_without_started_job(self):
        values = {
            "LoadState": "loaded", "ActiveState": "inactive",
            "Result": "success", "ExecMainStartTimestampMonotonic": "0",
        }
        times = iter([0, 0, 430, 431])
        with patch.object(operator, "unit_status", return_value=values):
            with self.assertRaisesRegex(operator.OperatorStop, "SYSTEMD_TRANSACTION_WAIT_TIMEOUT"):
                operator.wait_for_unit(now=lambda: next(times), sleep=lambda _: None)

    def test_systemd_failure_does_not_produce_pass(self):
        values = {
            "LoadState": "loaded", "ActiveState": "failed",
            "Result": "exit-code", "ExecMainStartTimestampMonotonic": "100",
        }
        with patch.object(operator, "unit_status", return_value=values):
            with self.assertRaisesRegex(operator.OperatorStop, "FRESH_MANAGER_SYSTEMD_TRANSACTION_FAILED"):
                operator.wait_for_unit(now=lambda: 0, sleep=lambda _: None)

    def test_systemd_success_requires_completed_started_job(self):
        states = iter([
            {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success",
             "ExecMainStartTimestampMonotonic": "0"},
            {"LoadState": "loaded", "ActiveState": "activating", "Result": "success",
             "ExecMainStartTimestampMonotonic": "15"},
            {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success",
             "ExecMainStartTimestampMonotonic": "15"},
        ])
        with patch.object(operator, "unit_status", side_effect=lambda: next(states)):
            operator.wait_for_unit(now=lambda: 0, sleep=lambda _: None)

    def test_unexpected_unit_disappearance_stops(self):
        values = {"LoadState": "not-found", "ActiveState": "inactive", "Result": "success",
                  "ExecMainStartTimestampMonotonic": "50"}
        with patch.object(operator, "unit_status", return_value=values):
            with self.assertRaisesRegex(operator.OperatorStop, "SYSTEMD_UNIT_NO_LONGER_LOADED"):
                operator.wait_for_unit(now=lambda: 0, sleep=lambda _: None)

    def test_preflight_and_execute_are_not_equivalent_to_authorization(self):
        with patch.object(operator, "non_mutating_preflight", return_value="source") as preflight:
            with patch.object(operator, "install_unit") as install:
                with patch.object(operator, "checked") as checked:
                    value = operator.non_mutating_preflight(self.private)
                    self.assertEqual(value, "source")
                    preflight.assert_called_once()
                    install.assert_not_called()
                    checked.assert_not_called()

    def test_final_operator_failure_attempts_rollback_and_never_reports_pass(self):
        with patch.object(operator, "non_mutating_preflight", return_value="unit"):
            with patch.object(operator, "install_unit"):
                with patch.object(operator, "checked"):
                    with patch.object(operator, "wait_for_unit"):
                        with patch.object(operator, "verify_success",
                                          side_effect=operator.OperatorStop("INJECTED_FINAL_CHECK")):
                            with patch.object(operator.recovery, "rollback_after_operator_final_check_failure") as rollback:
                                with self.assertRaisesRegex(
                                    operator.OperatorStop,
                                    "FINAL_VERIFICATION_FAILED_OLD_MANAGER_RESTORED",
                                ):
                                    operator.execute(self.private)
                                rollback.assert_called_once_with(self.private)

    def test_final_operator_failure_with_failed_rollback_is_manual_stop(self):
        with patch.object(operator, "non_mutating_preflight", return_value="unit"):
            with patch.object(operator, "install_unit"):
                with patch.object(operator, "checked"):
                    with patch.object(operator, "wait_for_unit"):
                        with patch.object(operator, "verify_success",
                                          side_effect=operator.OperatorStop("INJECTED_FINAL_CHECK")):
                            with patch.object(
                                operator.recovery,
                                "rollback_after_operator_final_check_failure",
                                side_effect=operator.recovery.RecoveryStop("SYNTHETIC_RESCUE_FAILURE"),
                            ):
                                with self.assertRaisesRegex(
                                    operator.OperatorStop,
                                    "FINAL_VERIFICATION_FAILED_ROLLBACK_INCOMPLETE",
                                ):
                                    operator.execute(self.private)

    def test_postflight_rejects_uncommitted_state(self):
        with patch.object(operator, "_private_json", return_value={"committed": False}):
            with self.assertRaisesRegex(operator.OperatorStop, "TRANSACTION_STATE_NOT_COMMITTED"):
                operator.verify_success(self.private)

    def test_postflight_rejects_changed_candidate_identity(self):
        state = {"committed": True, "candidate_id": "expected", "candidate_image_id": "immutable"}
        with patch.object(operator, "_private_json", return_value=state):
            with patch.object(operator.deploy, "docker_json", return_value={
                "Id": "unexpected", "Image": "immutable", "State": {"Running": True}
            }):
                with self.assertRaisesRegex(operator.OperatorStop, "COMMITTED_CANDIDATE_RUNTIME_MISMATCH"):
                    operator.verify_success(self.private)

    def test_supervised_unit_has_stop_post_rescue_and_no_restart(self):
        stage = self.private / unit.STAGE_DIR
        stage.mkdir(mode=0o700)
        for name in unit.PROTECTED_SCRIPTS:
            (stage / name).write_text("synthetic", encoding="utf-8")
            (stage / name).chmod(0o600)
        python = Path("/usr/bin/python3")
        if not python.is_file():
            import sys
            python = Path(sys.executable).resolve()
        with patch.object(unit.snapshot, "private_root", return_value=self.private):
            source = unit.render_unit(self.private, stage, python)
        self.assertIn("ExecStopPost=", source)
        self.assertIn("--systemd-stop-post", source)
        self.assertIn("Restart=no", source)
        self.assertIn("KillMode=control-group", source)
        self.assertIn("--permit-live-manager-replacement", source)


if __name__ == "__main__":
    unittest.main()
