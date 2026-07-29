#!/usr/bin/env python3
"""Source-only D2-11 bytecode and leaf-error repair adapter.

The shell launcher must disable Python bytecode before this module is imported.
Any later physical use requires a new D2-12 request, package and authorization.
"""
from __future__ import annotations

import json
import sys

import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1 as repair_contract
import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as upstream_contract
import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1 as upstream

_UPSTREAM_ERROR_CODE = upstream._error_code


def repaired_error_code(exc: BaseException) -> str:
    if isinstance(exc, upstream_contract.ContractError):
        return repair_contract.stable_contract_leaf(exc)
    return _UPSTREAM_ERROR_CODE(exc)


def install() -> None:
    """Install only the controlled leaf-code adapter."""
    upstream._error_code = repaired_error_code


def source_status() -> dict[str, object]:
    value = repair_contract.source_status()
    value["bytecode_write_disabled_for_current_process"] = (
        sys.dont_write_bytecode
    )
    return value


def main() -> int:
    if not sys.dont_write_bytecode:
        value = repair_contract.source_status()
        value.update(
            {
                "status": "FAIL",
                "failure_code": (
                    "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"
                ),
                "bytecode_write_disabled_for_current_process": False,
            }
        )
        print(json.dumps(value, sort_keys=True))
        return 2
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
        return 0
    if sys.argv[1] == "execute":
        value = source_status()
        value.update(
            {
                "status": "FAIL",
                "failure_code": "D2_12_EXECUTION_BINDING_REQUIRED",
            }
        )
        print(json.dumps(value, sort_keys=True))
        return 2
    install()
    return upstream.main()


if __name__ == "__main__":
    raise SystemExit(main())
