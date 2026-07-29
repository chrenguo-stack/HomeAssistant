#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as upstream_contract
import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1 as upstream
import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_wrapper_20260729_v1 as repair


class BytecodeRepairTests(unittest.TestCase):
    def test_decision_binding_and_failed_preclaim_boundary(self) -> None:
        value = contract.validate_decision(
            ROOT
            / "docs/decisions/"
            "h3-n2-stage2d9r-g3r-d2-11-python-bytecode-"
            "self-contamination-repair-20260729-v1.json"
        )
        self.assertEqual(value["base_pr"], 208)
        self.assertEqual(value["base_head_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(
            value["failed_private_package_state"],
            "PRECLAIM_CONTRACT_FAILED",
        )
        self.assertFalse(value["failed_authorization_claimed"])
        self.assertFalse(value["failed_authorization_consumed"])
        self.assertFalse(value["failed_authorization_reuse_permitted"])
        self.assertFalse(value["failed_package_replay_permitted"])
        self.assertFalse(value["d2_12_request_created"])

    def test_source_status_is_inert_and_requires_d2_12_rebind(self) -> None:
        status = contract.source_status()
        self.assertEqual(status["status"], "SOURCE_ONLY_D2_12_REBIND_REQUIRED")
        self.assertEqual(status["root_cause"], contract.ROOT_CAUSE)
        for key in (
            "failed_authorization_claimed",
            "failed_authorization_consumed",
            "failed_authorization_reuse_permitted",
            "failed_package_replay_permitted",
            "d2_12_request_created",
            "d2_12_authorization_created",
            "d2_12_execution_package_created",
            "physical_execute_enabled",
            "board_operation",
            "usb_enumeration",
            "serial_operation",
            "esptool_operation",
            "flash_operation",
            "network_operation",
            "replay_permitted",
        ):
            self.assertFalse(status[key])

    def test_launcher_exports_guard_before_python_selection_or_exec(self) -> None:
        launcher = TOOLS / contract.REPAIRED_LAUNCHER_FILE
        contract.validate_launcher(launcher)
        source = launcher.read_text(encoding="utf-8")
        self.assertLess(
            source.index("PYTHONDONTWRITEBYTECODE=1"),
            source.index("PYTHON_BIN="),
        )
        self.assertLess(
            source.index("export PYTHONDONTWRITEBYTECODE"),
            source.index('exec "$PYTHON_BIN"'),
        )

    def test_contract_error_leaf_is_preserved(self) -> None:
        exc = upstream_contract.ContractError("PACKAGE_MEMBER_INVALID")
        self.assertEqual(
            repair.repaired_error_code(exc),
            "PACKAGE_MEMBER_INVALID",
        )
        repair.install()
        self.assertEqual(upstream._error_code(exc), "PACKAGE_MEMBER_INVALID")

    def test_uncontrolled_contract_text_is_not_exposed(self) -> None:
        private_path = "/" + "Users/" + "private/secret"
        exc = upstream_contract.ContractError(private_path)
        self.assertEqual(repair.repaired_error_code(exc), "ContractError")
        self.assertNotIn(private_path, repair.repaired_error_code(exc))

    def test_non_contract_exception_keeps_class_only_mapping(self) -> None:
        private_path = "/" + "dev/" + "cu.private-device"
        exc = OSError(f"failed on {private_path}")
        self.assertEqual(repair.repaired_error_code(exc), "OSError")
        self.assertNotIn(private_path, repair.repaired_error_code(exc))

    def test_repair_install_does_not_install_or_execute_physical_core(self) -> None:
        source = inspect.getsource(repair.install)
        self.assertIn("upstream._error_code = repaired_error_code", source)
        for forbidden in (
            "upstream.install(",
            "upstream.configure_core(",
            "upstream.prepare_payload_handoff(",
            "serial",
            "esptool",
        ):
            self.assertNotIn(forbidden, source)

    def test_source_wrapper_blocks_execute_until_d2_12_binding(self) -> None:
        source = inspect.getsource(repair.main)
        self.assertIn('sys.argv[1] == "execute"', source)
        self.assertIn("D2_12_EXECUTION_BINDING_REQUIRED", source)
        self.assertLess(
            source.index('sys.argv[1] == "execute"'),
            source.index("install()"),
        )

    def test_source_inventory_contract(self) -> None:
        value = contract.validate_review_source(ROOT)
        for key in (
            "decision_binding_sha256",
            "launcher_sha256",
            "wrapper_sha256",
            "contract_sha256",
        ):
            self.assertRegex(value[key], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
