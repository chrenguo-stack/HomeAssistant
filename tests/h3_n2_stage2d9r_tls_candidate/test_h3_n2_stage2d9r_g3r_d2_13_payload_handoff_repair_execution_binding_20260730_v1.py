from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_contract_20260730_v1 as contract
import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_wrapper_20260730_v1 as wrapper


class PayloadHandoffRepairTests(unittest.TestCase):
    def _package(self, root: Path) -> Path:
        package = root / "Package With Spaces"
        package.mkdir()
        (package / contract.IMMUTABLE_PAYLOAD_FILE).write_bytes(b"immutable")
        (package / contract.RECOVERY_PAYLOAD_FILE).write_bytes(b"recovery")
        return package

    def test_injects_missing_payload_arguments_with_macos_style_alias(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = self._package(root)
            alias = root / "Package Alias"
            alias.symlink_to(package, target_is_directory=True)
            argv = ["--package-root", str(alias)]
            repaired = wrapper.repair_execute_argv(
                argv,
                environ={wrapper.LAUNCHER_ROOT_ENV: str(package)},
            )
            self.assertEqual(repaired.count("--immutable-payload-tar"), 1)
            self.assertEqual(repaired.count("--recovery-payload-tar"), 1)
            immutable = Path(repaired[repaired.index("--immutable-payload-tar") + 1])
            recovery = Path(repaired[repaired.index("--recovery-payload-tar") + 1])
            self.assertEqual(immutable, (package / contract.IMMUTABLE_PAYLOAD_FILE).resolve())
            self.assertEqual(recovery, (package / contract.RECOVERY_PAYLOAD_FILE).resolve())

    def test_rejects_conflicting_payload_argument(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = self._package(root)
            other = root / "other.tar"
            other.write_bytes(b"other")
            with self.assertRaisesRegex(
                wrapper.PayloadHandoffRepairError,
                "IMMUTABLE_PAYLOAD_TAR_MISMATCH",
            ):
                wrapper.repair_execute_argv(
                    [
                        "--package-root",
                        str(package),
                        "--immutable-payload-tar",
                        str(other),
                    ],
                    environ={wrapper.LAUNCHER_ROOT_ENV: str(package)},
                )

    def test_requires_launcher_root_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            package = self._package(Path(td))
            with self.assertRaisesRegex(
                wrapper.PayloadHandoffRepairError,
                "LAUNCHER_PACKAGE_ROOT_MISSING",
            ):
                wrapper.repair_execute_argv(
                    ["--package-root", str(package)],
                    environ={},
                )

    def test_preclaim_failure_writes_result_and_marker_without_physical_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auth = root / "authorization.json"
            auth.write_text("{}\n", encoding="utf-8")
            state = root / "state"
            result = root / "result.json"
            value = wrapper.write_preclaim_handoff_failure(
                [
                    "--authorization-record",
                    str(auth),
                    "--state-root",
                    str(state),
                    "--result-output",
                    str(result),
                ],
                "IMMUTABLE_PAYLOAD_TAR_MISSING",
            )
            self.assertEqual(value["status"], "CONSUMED_FAILED")
            self.assertTrue(value["authorization_created"])
            self.assertFalse(value["authorization_claimed"])
            self.assertTrue(value["authorization_consumed"])
            for key in (
                "board_operation",
                "usb_enumeration",
                "serial_operation",
                "esptool_operation",
                "flash_operation",
                "network_operation",
                "prepare_executed",
                "verify_executed",
            ):
                self.assertFalse(value[key])
            persisted = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(persisted, value)
            markers = list(state.glob("*.json"))
            self.assertEqual(len(markers), 1)
            marker = json.loads(markers[0].read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], "CONSUMED_FAILED")
            self.assertFalse(marker["authorization_claimed"])
            self.assertTrue(marker["authorization_consumed"])

    def test_decision_binding_and_predecessor_terminal_state(self) -> None:
        decision = (
            Path(__file__).resolve().parents[2]
            / "docs/decisions"
            / contract.DECISION_FILE
        )
        value = contract.validate_decision(decision)
        self.assertEqual(value["predecessor_status"], contract.D2_12_STATUS)
        self.assertEqual(value["predecessor_failure_code"], contract.D2_12_FAILURE_CODE)
        self.assertFalse(value["predecessor_replay_permitted"])

    def test_source_status_is_host_only_and_unauthorized(self) -> None:
        value = wrapper.source_status()
        self.assertEqual(value["d2_request_id"], contract.D2_REQUEST_ID)
        self.assertFalse(value["board_operation"])
        self.assertFalse(value["usb_enumeration"])
        self.assertFalse(value["serial_operation"])
        self.assertFalse(value["flash_operation"])
        self.assertFalse(value["network_operation"])
        self.assertFalse(value["replay_permitted"])


if __name__ == "__main__":
    unittest.main()
