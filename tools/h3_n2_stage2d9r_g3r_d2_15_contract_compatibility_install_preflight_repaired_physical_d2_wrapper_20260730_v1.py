#!/usr/bin/env python3
"""D2-15 adapter: host install preflight plus stable preclaim terminalization."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_wrapper_20260730_v1 as predecessor
import h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repair_execution_binding_contract_20260730_v1 as contract

LAUNCHER_ROOT_ENV = "GH_D2_15_LAUNCHER_PACKAGE_ROOT"


def bind_predecessor() -> None:
    if not sys.dont_write_bytecode:
        raise contract.ContractError("PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START")
    predecessor.contract = contract
    predecessor.bind_predecessor()


def _option(argv: list[str], name: str) -> Path | None:
    values: list[str] = []
    for index, item in enumerate(argv):
        if item == name and index + 1 < len(argv): values.append(argv[index + 1])
        elif item.startswith(name + "="): values.append(item.split("=", 1)[1])
    if len(values) != 1 or not values[0]: return None
    try: return Path(values[0]).expanduser().resolve(strict=False)
    except (OSError, RuntimeError): return None


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            json.dump(value, handle, sort_keys=True, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    finally: os.close(fd)


def _failure(argv: list[str], exc: BaseException) -> dict[str, Any]:
    auth = _option(argv, "--authorization-record")
    result = _option(argv, "--result-output")
    state = _option(argv, "--state-root")
    created = auth is not None and auth.is_file() and not auth.is_symlink()
    code = exc.args[0] if isinstance(exc, contract.ContractError) and exc.args and isinstance(exc.args[0], str) else type(exc).__name__
    marker = None if state is None else state / (hashlib.sha256(contract.D2_REQUEST_ID.encode()).hexdigest() + ".json")
    value: dict[str, Any] = {
        "schema": contract.PRE_RESULT_SCHEMA, "stage": contract.STAGE, "d2_request_id": contract.D2_REQUEST_ID,
        "status": "CONSUMED_FAILED" if created else "FAIL",
        "terminal_state": "CONSUMED_FAILED_PRECLAIM" if created else "PRECLAIM_REJECTED",
        "failure_code": code, "failure_stage": "HOST_INSTALL_PREFLIGHT",
        "authorization_created": created, "authorization_claimed": bool(marker and marker.exists()),
        "authorization_consumed": created, "authorization_record_sha256": contract.sha256_file(auth) if created and auth else None,
        "one_shot": True, "replay_permitted": False, "automatic_retry_permitted": False,
        "board_operation": False, "usb_enumeration": False, "serial_operation": False,
        "esptool_operation": False, "flash_operation": False, "physical_nvs_operation": False,
        "network_operation": False, "broker_started": False, "prepare_executed": False,
        "verify_executed": False, "activate_executed": False, "cleanup_executed": False,
        "production_operation": False, "private_paths_included": False, "secret_values_included": False,
    }
    value["terminal_result_sha256"] = contract.canonical_sha256(value)
    if result and not result.exists(): _atomic_json(result, value)
    if created and marker and not marker.exists():
        _atomic_json(marker, {
            "schema": contract.PRE_MARKER_SCHEMA, "stage": contract.STAGE, "d2_request_id": contract.D2_REQUEST_ID,
            "status": "CONSUMED_FAILED", "failure_code": code, "failure_stage": "HOST_INSTALL_PREFLIGHT",
            "authorization_created": True, "authorization_claimed": False, "authorization_consumed": True,
            "authorization_record_sha256": value["authorization_record_sha256"],
            "terminal_result_sha256": value["terminal_result_sha256"], "one_shot": True,
            "replay_permitted": False, "automatic_retry_permitted": False,
            "private_paths_included": False, "secret_values_included": False,
        })
    return value


def install_preflight_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        package = args.package_root.expanduser().resolve(strict=True)
        launcher = os.environ.get(LAUNCHER_ROOT_ENV)
        if not package.is_dir() or package.is_symlink() or launcher is None or Path(launcher).resolve(strict=True) != package:
            raise contract.ContractError("LAUNCHER_PACKAGE_ROOT_MISMATCH")
        contract.validate_execution_package(package)
        bind_predecessor()
        d2_11 = predecessor.predecessor.predecessor.upstream
        d2_11.install()
        value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-check/1",
            "status": "PASS", "d2_request_id": contract.D2_REQUEST_ID,
            "contract_compatibility_symbol_present": callable(contract.canonical_package_digest),
            "inherited_d2_11_install_completed": True, "authorization_created": False,
            "authorization_claimed": False, "authorization_consumed": False,
            "board_operation": False, "usb_enumeration": False, "serial_operation": False,
            "esptool_operation": False, "flash_operation": False, "network_operation": False,
            "prepare_executed": False, "verify_executed": False,
        }; rc = 0
    except Exception as exc:
        value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-check/1",
            "status": "FAIL", "failure_code": type(exc).__name__, "d2_request_id": contract.D2_REQUEST_ID,
            "authorization_created": False, "authorization_claimed": False, "authorization_consumed": False,
            "board_operation": False, "usb_enumeration": False, "serial_operation": False,
            "esptool_operation": False, "flash_operation": False, "network_operation": False,
            "prepare_executed": False, "verify_executed": False,
        }; rc = 2
    args.result_output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True)); return rc


def source_status() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-source/1",
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_15_AUTHORIZATION",
        "decision_id": contract.DECISION_ID, "d2_request_id": contract.D2_REQUEST_ID,
        "predecessor_request_id": contract.D2_14_ID, "predecessor_terminal_state": contract.D2_14_TERMINAL_STATE,
        "predecessor_failure_code": contract.D2_14_FAILURE_CODE,
        "canonical_package_digest_exported": callable(contract.canonical_package_digest),
        "host_install_preflight_required": True, "physical_request_created": False,
        "physical_authorization_created": False, "board_operation": False, "usb_enumeration": False,
        "serial_operation": False, "esptool_operation": False, "flash_operation": False,
        "network_operation": False, "replay_permitted": False, "automatic_retry_permitted": False,
    }


def main() -> int:
    if not sys.dont_write_bytecode:
        print(json.dumps({**source_status(), "status": "FAIL", "failure_code": "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"}, sort_keys=True)); return 2
    if len(sys.argv) == 1: print(json.dumps(source_status(), sort_keys=True)); return 0
    if sys.argv[1] == "install-preflight-check": return install_preflight_check(sys.argv[2:])
    if sys.argv[1] == "root-ownership-check":
        predecessor.contract = contract; return predecessor.root_ownership_check(sys.argv[2:])
    if sys.argv[1] == "contract-check":
        predecessor.contract = contract; return predecessor.predecessor.contract_check(sys.argv[2:])
    if sys.argv[1] != "execute": print("first argument must be contract-check, root-ownership-check, install-preflight-check or execute", file=sys.stderr); return 2
    original = sys.argv[2:]
    try:
        package = _option(original, "--package-root")
        if package is not None:
            contract.validate_execution_package(package.resolve(strict=True))
        bind_predecessor()
        d2_11 = predecessor.predecessor.predecessor.upstream
        d2_11.install()
        predecessor.contract = contract
        sys.argv = [sys.argv[0], "execute", *original]
        return predecessor.main()
    except Exception as exc:
        value = _failure(original, exc)
        print(json.dumps({"status": value["status"], "failure_code": value["failure_code"],
            "d2_request_id": contract.D2_REQUEST_ID, "authorization_claimed": value["authorization_claimed"],
            "authorization_consumed": value["authorization_consumed"], "board_operation": False,
            "usb_enumeration": False, "serial_operation": False, "esptool_operation": False,
            "flash_operation": False, "network_operation": False, "replay_permitted": False,
            "automatic_retry_permitted": False}, sort_keys=True)); return 2


if __name__ == "__main__": raise SystemExit(main())
