#!/usr/bin/env python3
"""D2-12 execution-bound adapter for the D2-11 bytecode repair."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1 as upstream
import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_wrapper_20260729_v1 as repair
import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_execution_binding_contract_20260729_v1 as contract


def bind_upstream() -> None:
    """Bind the repaired D2-12 identity before contract-check or execute."""
    if not sys.dont_write_bytecode:
        raise contract.ContractError(
            "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"
        )
    upstream.contract = contract
    upstream.STAGE = contract.STAGE
    upstream.D2_REQUEST_ID = contract.D2_REQUEST_ID
    upstream.AUTH_SCHEMA = contract.AUTH_SCHEMA
    upstream.RESULT_SCHEMA = contract.RESULT_SCHEMA
    upstream.MARKER_SCHEMA = contract.MARKER_SCHEMA
    upstream.PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
    upstream.PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA
    upstream.__file__ = __file__
    repair.install()


def error_code(exc: BaseException) -> str:
    if isinstance(exc, contract.ContractError):
        return repair.repair_contract.stable_contract_leaf(exc)
    return repair.repaired_error_code(exc)


def source_status() -> dict[str, Any]:
    return {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
            "execution-binding-source/1"
        ),
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_12_AUTHORIZATION",
        "decision_id": contract.DECISION_ID,
        "d2_request_id": contract.D2_REQUEST_ID,
        "predecessor_request_id": contract.D2_11_ID,
        "predecessor_status": "PRECLAIM_CONTRACT_FAILED",
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "physical_baseline_source_request_id": contract.D2_10_ID,
        "physical_baseline_locked_recovery_outcome": "UNKNOWN",
        "bytecode_write_disabled_for_current_process": sys.dont_write_bytecode,
        "private_outer_runner_bytecode_guard_required": True,
        "stable_leaf_contract_failure_code_required": True,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }


def contract_check(argv: list[str]) -> int:
    check = argparse.ArgumentParser()
    check.add_argument("--package-root", type=Path, required=True)
    check.add_argument("--physical-request", type=Path, required=True)
    check.add_argument("--authorization-record", type=Path, required=True)
    check.add_argument("--result-output", type=Path, required=True)
    check.add_argument("--now")
    args = check.parse_args(argv)
    try:
        bind_upstream()
        root = args.package_root.expanduser().resolve(strict=True)
        request = json.loads(args.physical_request.read_text(encoding="utf-8"))
        authorization = json.loads(
            args.authorization_record.read_text(encoding="utf-8")
        )
        now = (
            datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
            if args.now
            else None
        )
        contract.validate_authorization_contract(
            authorization, request, root, now=now
        )
        result: dict[str, Any] = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
                "authorization-contract-check/1"
            ),
            "status": "PASS",
            "d2_request_id": contract.D2_REQUEST_ID,
            "bytecode_write_disabled_for_current_process": True,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        rc = 0
    except Exception as exc:
        result = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
                "authorization-contract-check/1"
            ),
            "status": "FAIL",
            "failure_code": error_code(exc),
            "d2_request_id": contract.D2_REQUEST_ID,
            "bytecode_write_disabled_for_current_process": sys.dont_write_bytecode,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        rc = 2
    args.result_output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return rc


def main() -> int:
    if not sys.dont_write_bytecode:
        value = source_status()
        value.update(
            {
                "status": "FAIL",
                "failure_code": (
                    "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"
                ),
            }
        )
        print(json.dumps(value, sort_keys=True))
        return 2
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
        return 0
    if sys.argv[1] == "contract-check":
        return contract_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print("first argument must be contract-check or execute", file=sys.stderr)
        return 2
    bind_upstream()
    return upstream.main()


if __name__ == "__main__":
    raise SystemExit(main())
