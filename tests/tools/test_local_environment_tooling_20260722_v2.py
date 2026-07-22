from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_V2_PATH = REPO_ROOT / "tools/dev/local_environment_doctor_20260722_v2.py"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


DOCTOR_V2 = load_module("local_environment_doctor_v2", DOCTOR_V2_PATH)


class LocalEnvironmentDoctorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "tooling": {
                "expected_versions": {
                    "esphome": "2026.4.3",
                }
            }
        }

    @staticmethod
    def missing_venv_esphome(_policy, results, _venv) -> None:
        DOCTOR_V2.BASE.add(
            results,
            "FAIL",
            "python.package.esphome",
            "missing",
        )

    def test_pipx_esphome_exact_version_is_accepted(self) -> None:
        results = []
        with (
            mock.patch.object(
                DOCTOR_V2,
                "ORIGINAL_CHECK_PYTHON",
                self.missing_venv_esphome,
            ),
            mock.patch.object(
                DOCTOR_V2.shutil,
                "which",
                return_value="/home/test/.local/bin/esphome",
            ),
            mock.patch.object(
                DOCTOR_V2.BASE,
                "run_text",
                return_value=(0, "Version: 2026.4.3"),
            ),
            mock.patch.object(
                DOCTOR_V2.Path,
                "resolve",
                return_value=Path(
                    "/home/test/.local/pipx/venvs/esphome/bin/esphome"
                ),
            ),
        ):
            DOCTOR_V2.check_python(self.policy, results, Path("/tmp/venv"))

        statuses = {item.code: item.status for item in results}
        self.assertNotIn("python.package.esphome", statuses)
        self.assertEqual(statuses["tool.esphome"], "PASS")
        self.assertEqual(statuses["python.package.esphome_isolation"], "INFO")

    def test_isolated_esphome_wrong_version_fails(self) -> None:
        results = []
        with (
            mock.patch.object(
                DOCTOR_V2,
                "ORIGINAL_CHECK_PYTHON",
                self.missing_venv_esphome,
            ),
            mock.patch.object(
                DOCTOR_V2.shutil,
                "which",
                return_value="/tmp/esphome",
            ),
            mock.patch.object(
                DOCTOR_V2.BASE,
                "run_text",
                return_value=(0, "Version: 2026.5.0"),
            ),
        ):
            DOCTOR_V2.check_python(self.policy, results, Path("/tmp/venv"))

        statuses = {item.code: item.status for item in results}
        self.assertEqual(statuses["tool.esphome"], "FAIL")
        self.assertNotIn("python.package.esphome_isolation", statuses)


if __name__ == "__main__":
    unittest.main()
