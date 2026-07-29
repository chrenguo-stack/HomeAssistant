#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

contract = importlib.import_module(
    "h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_contract_20260729_v1"
)
parser = importlib.import_module(
    "h3_n2_stage2d9r_g3r_task_watchdog_parser_20260729_v1"
)

EXECUTOR_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_executor_20260723_v1.cpp"
EXECUTOR_H = ROOT / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_executor_20260723_v1.h"
REPAIR_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.cpp"
REPAIR_H = ROOT / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.h"
COMPONENT_INIT = ROOT / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/__init__.py"

SYNTHETIC_COMPLETE = [
    "E (6684) task_wdt: Task watchdog got triggered. The following tasks/users did not reset the watchdog in time:",
    "E (6684) task_wdt:  - loopTask (CPU 0)",
    "E (6684) task_wdt: Aborting.",
    "E (6684) task_wdt: Print CPU 0 (current core) registers",
    "MEPC    : 0x4080211c    RA      : 0x4080210a",
    "Saved PC: 0x4001975a",
    "Rebooting...",
]


class LoopTaskWatchdogRepairTests(unittest.TestCase):
    def test_01_predecessor_is_permanently_consumed_failed(self):
        self.assertEqual(contract.D2_09_STATUS, "CONSUMED_FAILED")
        self.assertEqual(contract.D2_09_FAILURE_CODE, "PREPARE_RESULT_TIMEOUT")
        self.assertEqual(contract.D2_09_TERMINAL_STATE, "LOCKED_RECOVERY_COMPLETED")
        self.assertEqual(contract.D2_09_RESET_LOOP_COUNT, 9)
        self.assertEqual(contract.D2_09_POST_COMMAND_RESET_COUNT, 9)

    def test_02_old_executor_has_blocking_read_risk(self):
        source = EXECUTOR_CPP.read_text(encoding="utf-8")
        self.assertIn("::read(STDIN_FILENO", source)
        self.assertIn("EAGAIN", source)
        self.assertIn("EWOULDBLOCK", source)
        self.assertNotIn("F_SETFL", source)
        self.assertNotIn("O_NONBLOCK", source)

    def test_03_repair_sets_and_verifies_nonblocking_stdin(self):
        source = REPAIR_CPP.read_text(encoding="utf-8")
        self.assertIn("F_GETFL", source)
        self.assertIn("F_SETFL", source)
        self.assertGreaterEqual(source.count("O_NONBLOCK"), 3)
        self.assertIn("Stage2D9RG3RPrepareExecutorV1::setup()", source)
        self.assertIn("this->read_console_()", source)
        self.assertIn("console_nonblocking_configuration", source)
        self.assertIn("console_loop_time_bound", source)

    def test_04_repair_does_not_bypass_watchdog(self):
        source = REPAIR_CPP.read_text(encoding="utf-8")
        forbidden = (
            "esp_task_wdt_reset",
            "esp_task_wdt_delete",
            "esp_task_wdt_deinit",
            "CONFIG_ESP_TASK_WDT_TIMEOUT_S",
            "CONFIG_ESP_TASK_WDT_EN",
        )
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("watchdog_disabled=false", source)
        self.assertIn("watchdog_timeout_extended=false", source)

    def test_05_component_instantiates_repaired_class(self):
        header = EXECUTOR_H.read_text(encoding="utf-8")
        repair_header = REPAIR_H.read_text(encoding="utf-8")
        init = COMPONENT_INIT.read_text(encoding="utf-8")
        self.assertNotIn("Stage2D9RG3RPrepareExecutorV1 final", header)
        self.assertIn("Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1 final", repair_header)
        self.assertIn('"Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1"', init)
        self.assertNotIn('cv.declare_id(Stage2D9RG3RPrepareExecutorV1)', init)

    def test_06_task_watchdog_complete_cycle_parser(self):
        value = parser.parse_task_watchdog_cycle(SYNTHETIC_COMPLETE)
        self.assertEqual(value["classification"], "TASK_WATCHDOG")
        self.assertTrue(value["triggered"])
        self.assertEqual(value["starved_task"], "loopTask")
        self.assertEqual(value["starved_task_cpu"], 0)
        self.assertTrue(value["abort_observed"])
        self.assertEqual(value["register_dump_cpu"], 0)
        self.assertEqual(value["mepc"], "0x4080211c")
        self.assertEqual(value["ra"], "0x4080210a")
        self.assertEqual(value["saved_pc"], "0x4001975a")
        self.assertTrue(value["cycle_complete"])

    def test_07_task_watchdog_incomplete_cycle_parser(self):
        value = parser.parse_task_watchdog_cycle(SYNTHETIC_COMPLETE[:3])
        self.assertEqual(value["classification"], "TASK_WATCHDOG")
        self.assertFalse(value["cycle_complete"])
        self.assertTrue(value["abort_observed"])
        self.assertFalse(value["reboot_observed"])

    def test_08_multiple_task_watchdog_cycles(self):
        values = parser.split_and_parse_cycles(
            [*SYNTHETIC_COMPLETE, *SYNTHETIC_COMPLETE]
        )
        self.assertEqual(len(values), 2)
        self.assertTrue(all(value["cycle_complete"] for value in values))
        self.assertEqual(
            values[0]["signature_sha256"], values[1]["signature_sha256"]
        )

    def test_09_source_tools_are_inert(self):
        for name in (
            "h3_n2_stage2d9r_g3r_task_watchdog_parser_20260729_v1.py",
            "h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_contract_20260729_v1.py",
        ):
            result = subprocess.run(
                [sys.executable, str(TOOLS / name)],
                check=True,
                capture_output=True,
                text=True,
            )
            value = json.loads(result.stdout)
            self.assertFalse(value["physical_authorization_created"])
            self.assertFalse(value["board_operation"])
            self.assertFalse(value["network_operation"])

    def test_10_old_symbolication_when_supplied(self):
        root = os.environ.get("OLD_SYMBOLICATION_ROOT")
        if not root:
            self.skipTest("OLD_SYMBOLICATION_ROOT not supplied")
        value = contract.validate_old_symbolication(Path(root))
        self.assertEqual(value["old_application_sha256"], contract.OLD_APPLICATION_SHA256)
        self.assertEqual(value["addr2line"].count("esp_cpu_wait_for_intr"), 2)

    def test_11_repaired_build_when_supplied(self):
        root = os.environ.get("REPAIRED_BUILD_ROOT")
        source_sha = os.environ.get("REPAIRED_SOURCE_SHA")
        if not root or not source_sha:
            self.skipTest("REPAIRED_BUILD_ROOT or REPAIRED_SOURCE_SHA not supplied")
        value = contract.validate_repaired_build(Path(root), source_sha=source_sha)
        self.assertNotEqual(
            value["record"]["firmware"]["application_sha256"],
            contract.OLD_APPLICATION_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
