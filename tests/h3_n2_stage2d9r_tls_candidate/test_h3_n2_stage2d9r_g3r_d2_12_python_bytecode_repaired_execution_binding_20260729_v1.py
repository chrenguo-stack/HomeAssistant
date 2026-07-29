#!/usr/bin/env python3
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as upstream_contract
import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1 as upstream_wrapper
import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1 as repair_contract
import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_physical_d2_wrapper_20260729_v1 as wrapper


class D212BindingTests(unittest.TestCase):
    def test_decision_is_exact_and_unauthorized(self) -> None:
        value = contract.validate_decision(
            ROOT
            / "docs/decisions/"
            "h3-n2-stage2d9r-g3r-d2-12-python-bytecode-repaired-"
            "successor-execution-binding-20260729-v1.json"
        )
        self.assertEqual(value["base_pr"], 209)
        self.assertEqual(value["base_head_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(value["d2_request_id"], contract.D2_REQUEST_ID)
        self.assertTrue(value["physical_request_created"])
        self.assertFalse(value["physical_request_authorized"])
        self.assertFalse(value["physical_authorization_created"])

    def test_request_identity_is_new_and_d2_11_is_not_reusable(self) -> None:
        self.assertNotEqual(contract.D2_REQUEST_ID, contract.D2_11_ID)
        self.assertNotEqual(
            contract.D2_11_REQUEST_BINDING_SHA256,
            upstream_contract.D2_10_REQUEST_BINDING_SHA256,
        )
        self.assertEqual(
            contract.D2_11_EXECUTION_PACKAGE_SHA256,
            "0f5a450d8e4560d0969b07e31d8081bbe9961411a5e7a9b1d52a2c229f0fd66a",
        )

    def test_launcher_disables_bytecode_before_python(self) -> None:
        launcher = ROOT / "tools" / contract.LAUNCHER_FILE
        contract.validate_launcher(launcher)
        text = launcher.read_text(encoding="utf-8")
        self.assertLess(
            text.index("PYTHONDONTWRITEBYTECODE=1"),
            text.index("PYTHON_BIN="),
        )

    def test_source_status_preserves_preclaim_and_physical_baseline(self) -> None:
        value = wrapper.source_status()
        self.assertEqual(
            value["status"],
            "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_12_AUTHORIZATION",
        )
        self.assertEqual(value["predecessor_status"], "PRECLAIM_CONTRACT_FAILED")
        self.assertFalse(value["predecessor_authorization_claimed"])
        self.assertFalse(value["predecessor_authorization_consumed"])
        self.assertEqual(
            value["physical_baseline_locked_recovery_outcome"], "UNKNOWN"
        )
        self.assertTrue(value["bytecode_write_disabled_for_current_process"])
        for key in (
            "board_operation",
            "usb_enumeration",
            "serial_operation",
            "esptool_operation",
            "flash_operation",
            "network_operation",
        ):
            self.assertFalse(value[key])

    def test_controlled_contract_leaf_is_preserved(self) -> None:
        leaf = contract.ContractError("AUTHORIZATION_SCHEMA_MISMATCH")
        self.assertEqual(
            wrapper.error_code(leaf), "AUTHORIZATION_SCHEMA_MISMATCH"
        )
        unsafe = contract.ContractError("unsafe leaf text with spaces")
        self.assertEqual(wrapper.error_code(unsafe), "ContractError")
        old_leaf = upstream_contract.ContractError(
            "PACKAGE_MEMBER_INVALID"
        )
        self.assertEqual(
            repair_contract.stable_contract_leaf(old_leaf),
            "PACKAGE_MEMBER_INVALID",
        )

    def test_binding_replaces_upstream_identity_without_execution(self) -> None:
        wrapper.bind_upstream()
        self.assertIs(upstream_wrapper.contract, contract)
        self.assertEqual(upstream_wrapper.D2_REQUEST_ID, contract.D2_REQUEST_ID)
        self.assertEqual(upstream_wrapper.AUTH_SCHEMA, contract.AUTH_SCHEMA)
        self.assertEqual(upstream_wrapper.__file__, wrapper.__file__)

    def test_bind_and_contract_check_sources_have_no_physical_call(self) -> None:
        bind_source = inspect.getsource(wrapper.bind_upstream)
        check_source = inspect.getsource(wrapper.contract_check)
        for forbidden in (
            "serial.Serial(",
            "esptool.main(",
            "list_ports.comports(",
            "subprocess.run(",
            "wait_serial_line",
            "locked_recovery(",
        ):
            self.assertNotIn(forbidden, bind_source)
            self.assertNotIn(forbidden, check_source)

    def test_review_constants_bind_exact_pr209_repair(self) -> None:
        self.assertEqual(
            contract.PR209_REVIEW_BINDING_SHA256,
            "a3abafde375490ccf02743d58c0d4320fea2bbb4d92c4fdcada702be6ff97e1d",
        )
        self.assertEqual(
            contract.BYTECODE_REPAIR_CONTRACT_SHA256,
            "64be3c73fb5b635b8dba8f006f58e5c37d7fa3725944e4cd48e498e60fddf331",
        )
        self.assertEqual(
            contract.BYTECODE_REPAIR_WRAPPER_SHA256,
            "9273f22b97747bdbed83ae2aa730a32ac0f2c0fe1fb492dd3ffd50abcb3b2dd7",
        )


if __name__ == "__main__":
    unittest.main()
