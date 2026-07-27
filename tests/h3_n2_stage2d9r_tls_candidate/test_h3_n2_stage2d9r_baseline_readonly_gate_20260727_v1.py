#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_baseline_readonly_gate_20260727_v1.py"
SPEC = importlib.util.spec_from_file_location("stage2d9r_baseline_gate_test", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)
D = "a" * 64


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


class BaselineReadonlyGateTests(unittest.TestCase):
    def executable(self, root: Path, name: str) -> Path:
        path = root / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(path, 0o700)
        return path

    def authorization(
        self,
        root: Path,
        *,
        python_path: Path,
        esptool_path: Path,
        package_sha256: str = D,
    ) -> Path:
        value = {
            "schema": MODULE.AUTH_SCHEMA,
            "stage": MODULE.STAGE,
            "d1_decision_id": MODULE.D1_ID,
            "authorization_id": MODULE.AUTHORIZATION_ID,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "expected_serial_candidate_count": 1,
            "allowed_operations": list(MODULE.ALLOWED_OPERATIONS),
            "issued_at": "2026-07-27T07:30:00Z",
            "expires_at": "2026-07-27T09:30:00Z",
            "package_sha256": package_sha256,
            "execution_script_sha256": MODULE.sha256_file(TOOL),
            "python_executable_sha256": MODULE.sha256_file(python_path),
            "esptool_executable_sha256": MODULE.sha256_file(esptool_path),
            "erase_flash_authorized": False,
            "write_flash_authorized": False,
            "verify_flash_authorized": False,
            "physical_nvs_authorized": False,
            "network_authorized": False,
            "broker_authorized": False,
            "prepare_authorized": False,
            "verify_command_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
        }
        value["authorization_record_sha256"] = MODULE.canonical_sha256(value)
        path = root / "authorization.json"
        write_json(path, value)
        return path

    def selected(self) -> MODULE.SerialIdentity:
        return MODULE.SerialIdentity(
            device="/dev/fake",
            vid=MODULE.ESPRESSIF_USB_VID,
            pid=0x1001,
            serial_number="SERIAL",
            manufacturer="Espressif",
            product="USB JTAG/serial debug unit",
            location="1-1",
            hwid="FAKE",
        )

    def baseline(self, selected, esptool, work):
        value = {
            "schema": "gh.h3.n2.stage2d9r-successor-board-baseline/1",
            "board_identity_sha256": MODULE.canonical_sha256(
                selected.board_binding()
            ),
            "serial_identity_sha256": MODULE.canonical_sha256(
                selected.serial_binding()
            ),
            "chip_id_output_sha256": "1" * 64,
            "flash_id_output_sha256": "2" * 64,
            "test_partition_sha256": "3" * 64,
            "test_partition_size": MODULE.TEST_PARTITION_SIZE,
        }
        return {**value, "baseline_state_sha256": MODULE.canonical_sha256(value)}

    def test_success_claims_once_and_emits_hash_only_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python_path = self.executable(root, "python")
            esptool_path = self.executable(root, "esptool")
            auth = self.authorization(
                root, python_path=python_path, esptool_path=esptool_path
            )
            marker = root / "marker.json"
            result_path = root / "result.json"
            result = MODULE.execute(
                authorization_path=auth,
                marker_path=marker,
                result_output=result_path,
                package_sha256=D,
                python_path=python_path,
                esptool_path=esptool_path,
                serial_enumerator=lambda: [self.selected()],
                baseline_collector=self.baseline,
                now=NOW,
            )
            self.assertEqual(result["status"], "CONSUMED_PASS")
            self.assertEqual(result["board_write_operation"], False)
            self.assertNotIn("/dev/fake", result_path.read_text())
            marker_value = json.loads(marker.read_text())
            self.assertEqual(marker_value["status"], "CONSUMED_PASS")
            with self.assertRaisesRegex(
                MODULE.BaselineGateError,
                "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED",
            ):
                MODULE.execute(
                    authorization_path=auth,
                    marker_path=marker,
                    result_output=root / "second.json",
                    package_sha256=D,
                    python_path=python_path,
                    esptool_path=esptool_path,
                    serial_enumerator=lambda: [self.selected()],
                    baseline_collector=self.baseline,
                    now=NOW,
                )

    def test_invalid_authorization_fails_before_serial_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python_path = self.executable(root, "python")
            esptool_path = self.executable(root, "esptool")
            auth = self.authorization(
                root, python_path=python_path, esptool_path=esptool_path
            )
            value = json.loads(auth.read_text())
            value["authorized"] = False
            value.pop("authorization_record_sha256")
            value["authorization_record_sha256"] = MODULE.canonical_sha256(value)
            write_json(auth, value)
            called = False

            def enumerate_forbidden():
                nonlocal called
                called = True
                return []

            with self.assertRaisesRegex(
                MODULE.BaselineGateError, "AUTHORIZATION_NOT_GRANTED"
            ):
                MODULE.execute(
                    authorization_path=auth,
                    marker_path=root / "marker.json",
                    result_output=root / "result.json",
                    package_sha256=D,
                    python_path=python_path,
                    esptool_path=esptool_path,
                    serial_enumerator=enumerate_forbidden,
                    baseline_collector=self.baseline,
                    now=NOW,
                )
            self.assertFalse(called)

    def test_collect_baseline_uses_only_read_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            esptool = self.executable(root, "esptool")
            commands = []

            def runner(command, *, timeout, code):
                commands.append(command)
                if "read_flash" in command:
                    Path(command[-1]).write_bytes(
                        b"\xff" * MODULE.TEST_PARTITION_SIZE
                    )
                return subprocess.CompletedProcess(
                    command, 0, stdout=f"{code}\n", stderr=""
                )

            result = MODULE.collect_baseline(
                self.selected(), esptool, root, process_runner=runner
            )
            self.assertEqual(
                [command[5] for command in commands],
                ["chip_id", "flash_id", "read_flash"],
            )
            flattened = " ".join(" ".join(command) for command in commands)
            for forbidden in ("erase_flash", "write_flash", "verify_flash"):
                self.assertNotIn(forbidden, flattened)
            self.assertEqual(
                result["test_partition_size"], MODULE.TEST_PARTITION_SIZE
            )

    def test_candidate_count_failure_consumes_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python_path = self.executable(root, "python")
            esptool_path = self.executable(root, "esptool")
            auth = self.authorization(
                root, python_path=python_path, esptool_path=esptool_path
            )
            marker = root / "marker.json"
            result_path = root / "result.json"
            with self.assertRaisesRegex(
                MODULE.BaselineGateError, "SERIAL_CANDIDATE_COUNT_NOT_ONE"
            ):
                MODULE.execute(
                    authorization_path=auth,
                    marker_path=marker,
                    result_output=result_path,
                    package_sha256=D,
                    python_path=python_path,
                    esptool_path=esptool_path,
                    serial_enumerator=lambda: [],
                    baseline_collector=self.baseline,
                    now=NOW,
                )
            marker_value = json.loads(marker.read_text())
            self.assertEqual(marker_value["status"], "CONSUMED_FAILED")
            self.assertFalse(marker_value["automatic_retry_permitted"])


if __name__ == "__main__":
    unittest.main()
