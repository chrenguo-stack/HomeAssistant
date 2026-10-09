from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cold_snapshot as snapshot
import emergency_resume as rescue
import systemd_recovery_unit as unit


class IndependentRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stage = self.base / unit.STAGE_DIR
        self.stage.mkdir(mode=0o700)
        for name in unit.PROTECTED_SCRIPTS:
            file = self.stage / name
            file.write_text("synthetic")
            file.chmod(0o600)
        self.python = Path("/usr/bin/python3")

    def test_systemd_unit_has_independent_exit_recovery_and_no_install(self) -> None:
        with patch.object(snapshot, "private_root", return_value=self.base):
            with patch.object(unit.snapshot, "private_root", return_value=self.base):
                with patch.object(unit.os, "access", return_value=True):
                    unit_text = unit.render_unit(self.base, self.stage, self.python)
        self.assertIn("ExecStart=", unit_text)
        self.assertIn("ExecStopPost=", unit_text)
        self.assertIn("emergency_resume.py", unit_text)
        self.assertIn("TimeoutStartSec=240", unit_text)
        self.assertIn("Restart=no", unit_text)
        self.assertNotIn("[Install]", unit_text)
        self.assertNotIn("docker rm", unit_text)
        self.assertNotIn("docker compose", unit_text)

    def test_unit_refuses_missing_recovery_script(self) -> None:
        (self.stage / "emergency_resume.py").unlink()
        with patch.object(unit.snapshot, "private_root", return_value=self.base):
            with self.assertRaisesRegex(snapshot.Stop, "PROTECTED_SCRIPT_MISSING_OR_INSECURE"):
                unit.render_unit(self.base, self.stage, self.python)

    def test_unit_refuses_unprivate_recovery_script(self) -> None:
        (self.stage / "emergency_resume.py").chmod(0o644)
        with patch.object(unit.snapshot, "private_root", return_value=self.base):
            with self.assertRaisesRegex(snapshot.Stop, "PROTECTED_SCRIPT_MISSING_OR_INSECURE"):
                unit.render_unit(self.base, self.stage, self.python)

    def test_rescue_checks_original_container_then_resumes(self) -> None:
        old = {
            "Id": "same-id", "Image": "old-image",
            "Config": {"User": "999"}, "HostConfig": {"NetworkMode": "host"},
        }
        broker = {"Id": "same-broker"}
        with patch.object(rescue.snapshot, "private_root", return_value=self.base):
            with patch.object(rescue.window, "get_private_origin", return_value=(old, broker)):
                with patch.object(rescue.snapshot, "inspect", return_value=old):
                    with patch.object(rescue.window, "resume_original_manager") as resume:
                        rescue.recover_original(self.base)
        resume.assert_called_once_with(old, broker)

    def test_rescue_refuses_replacement_container(self) -> None:
        old = {"Id": "old", "Image": "image", "Config": {}, "HostConfig": {}}
        wrong = {"Id": "new", "Image": "image", "Config": {}, "HostConfig": {}}
        with patch.object(rescue.snapshot, "private_root", return_value=self.base):
            with patch.object(rescue.window, "get_private_origin", return_value=(old, {})):
                with patch.object(rescue.snapshot, "inspect", return_value=wrong):
                    with patch.object(rescue.window, "resume_original_manager") as resume:
                        with self.assertRaisesRegex(rescue.window.WindowStop, "ORIGINAL_CONTAINER_ID_MISMATCH"):
                            rescue.recover_original(self.base)
        resume.assert_not_called()


if __name__ == "__main__":
    unittest.main()
