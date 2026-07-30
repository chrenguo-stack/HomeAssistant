from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.py"
SHELL = ROOT / "tools/run_h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_20260730_v1.sh"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g02-physical-execution-20260730-v1.json"
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g02-physical-execution-authorized-pending-20260730-v1.json"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def module():
    spec = importlib.util.spec_from_file_location("d2_17_g02_physical_driver", DRIVER)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class PhysicalDecisionTest(unittest.TestCase):
    def test_decision_and_acceptance_bindings(self) -> None:
        decision = json.loads(DECISION.read_text())
        supplied = decision.pop("decision_binding_sha256")
        self.assertEqual(canonical_sha256(decision), supplied)
        acceptance = json.loads(ACCEPTANCE.read_text())
        supplied_acceptance = acceptance.pop("acceptance_binding_sha256")
        self.assertEqual(canonical_sha256(acceptance), supplied_acceptance)
        self.assertEqual(acceptance["decision_binding_sha256"], supplied)

    def test_driver_and_launcher_hashes_bound(self) -> None:
        decision = json.loads(DECISION.read_text())
        self.assertEqual(hashlib.sha256(DRIVER.read_bytes()).hexdigest(), decision["decision_driver_sha256"])
        self.assertEqual(hashlib.sha256(SHELL.read_bytes()).hexdigest(), decision["decision_launcher_sha256"])
        self.assertNotIn("/Users/", DRIVER.read_text())
        self.assertNotIn("chenrenguo", DRIVER.read_text().lower())

    def test_environment_propagation(self) -> None:
        value = module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            env = value.execution_environment(root, Path(sys.executable).resolve())
            for name in (
                "GH_D2_13_LAUNCHER_PACKAGE_ROOT",
                "GH_D2_14_LAUNCHER_PACKAGE_ROOT",
                "GH_D2_15_LAUNCHER_PACKAGE_ROOT",
                "GH_D2_16_LAUNCHER_PACKAGE_ROOT",
            ):
                self.assertEqual(env[name], str(root))
            self.assertEqual(env["GH_D2_17_DELIVERY_PROFILE"], "private-package")
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_real_shell_chain_stops_before_claim(self) -> None:
        execution_root_raw = os.environ.get("D2_17_G02_EXECUTION_ROOT")
        if not execution_root_raw:
            self.skipTest("D2_17_G02_EXECUTION_ROOT not provided")
        cp = subprocess.run(
            [sys.executable, "-B", str(DRIVER), "--self-test-execution-root", execution_root_raw],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        result = json.loads(cp.stdout.strip().splitlines()[-1])
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["inherited_launcher_environment_propagated"])
        self.assertTrue(result["required_physical_arguments_supplied"])
        self.assertTrue(result["failure_advanced_beyond_launcher_and_argparse"])
        self.assertFalse(result["authorization_claimed"])
        self.assertFalse(result["authorization_consumed"])
        self.assertFalse(result["board_operation"])


if __name__ == "__main__":
    unittest.main()
