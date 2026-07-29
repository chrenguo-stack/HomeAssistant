#!/usr/bin/env python3
"""Corrected-baseline physical D2 overlay bound to request -06."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff
import h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1 as repaired

core = repaired.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.REQUEST_06_ID
AUTH_SCHEMA = contract.AUTH_SCHEMA
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA
PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA
_BASE_VALIDATE_AUTHORIZATION = core.validate_authorization
_ORIGINAL_HANDOFF_PARSER = handoff.parser
_ORIGINAL_PREPARE_PAYLOAD_HANDOFF = handoff.prepare_payload_handoff
_BOUND_PHYSICAL_REQUEST: dict[str, Any] | None = None


def _prime_core() -> None:
    bindings = {
        "STAGE": STAGE,
        "D2_REQUEST_ID": D2_REQUEST_ID,
        "AUTH_SCHEMA": AUTH_SCHEMA,
        "RESULT_SCHEMA": RESULT_SCHEMA,
        "MARKER_SCHEMA": MARKER_SCHEMA,
        "IMMUTABLE_ARTIFACT_ID": repaired.IMMUTABLE_ARTIFACT_ID,
        "IMMUTABLE_ARCHIVE_SHA256": repaired.IMMUTABLE_ARCHIVE_SHA256,
        "IMMUTABLE_PAYLOAD_TAR_SHA256": repaired.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE_MERGED_SHA256": repaired.IMMUTABLE_MERGED_SHA256,
        "RECOVERY_ARTIFACT_ID": repaired.IMMUTABLE_ARTIFACT_ID,
        "RECOVERY_ARCHIVE_SHA256": repaired.IMMUTABLE_ARCHIVE_SHA256,
        "RECOVERY_PAYLOAD_TAR_SHA256": repaired.RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY_DESCRIPTOR_SHA256": repaired.RECOVERY_DESCRIPTOR_SHA256,
        "PRIVATE_PACKAGE_SHA256": repaired.PRIVATE_PACKAGE_SHA256,
        "PREPARE_COMMAND_SHA256": repaired.PREPARE_COMMAND_SHA256,
        "VERIFY_COMMAND_SHA256": repaired.VERIFY_COMMAND_SHA256,
        "CANDIDATE_DIGEST_SHA256": repaired.CANDIDATE_DIGEST_SHA256,
        "CA_PEM_SHA256": repaired.CA_PEM_SHA256,
        "BUILD_BINDING": repaired.BUILD_BINDING,
        "CUSTODY_RELATIVE": repaired.CUSTODY_RELATIVE,
        "TEST_PARTITION_ADDRESS": repaired.TEST_PARTITION_ADDRESS,
        "TEST_PARTITION_SIZE": repaired.TEST_PARTITION_SIZE,
        "ERASED_SHA256": repaired.ERASED_SHA256,
        "validate_public_inputs": handoff.validate_public_inputs,
        "locked_recovery": repaired.locked_recovery,
    }
    for key, value in bindings.items():
        setattr(core, key, value)
    core.__file__ = __file__


def configure_core() -> Any:
    _prime_core()

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = _BASE_VALIDATE_AUTHORIZATION(*args, **kwargs)
        package_root = kwargs.get("package_root")
        core.require(isinstance(package_root, Path), "AUTHORIZATION_PACKAGE_ROOT_MISSING")
        core.require(_BOUND_PHYSICAL_REQUEST is not None, "PHYSICAL_REQUEST_NOT_BOUND")
        try:
            contract_value = contract.validate_authorization_contract(
                value,
                _BOUND_PHYSICAL_REQUEST,
                package_root,
            )
        except contract.ContractError as exc:
            raise core.ExecutionError(str(exc)) from exc
        overlay = contract.validate_execution_overlay(package_root)
        required = contract.authorization_contract_required(
            _BOUND_PHYSICAL_REQUEST,
            package_root,
        )
        for key, expected in required.items():
            core.require(contract_value.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
        core.require(
            value.get("execution_wrapper_sha256") == overlay["binding"]["execution_wrapper_sha256"],
            "AUTHORIZATION_EXECUTION_WRAPPER_SHA256_MISMATCH",
        )
        core.require(
            value.get("execution_launcher_sha256") == overlay["binding"]["execution_launcher_sha256"],
            "AUTHORIZATION_EXECUTION_LAUNCHER_SHA256_MISMATCH",
        )
        core.require(value.get("baseline_state_sha256") == contract.CORRECTED_BASELINE_SHA256,
                     "AUTHORIZATION_CORRECTED_BASELINE_MISMATCH")
        core.require(value.get("invalid_legacy_baseline_sha256") == contract.INVALID_BASELINE_SHA256,
                     "AUTHORIZATION_INVALID_BASELINE_DISPOSITION_MISMATCH")
        core.require(value.get("locked_recovery_authorized") is True,
                     "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED")
        return value

    core.validate_authorization = validate_authorization
    repaired.repair.install_repaired_handshake(core)
    return core


def parser() -> argparse.ArgumentParser:
    result = _ORIGINAL_HANDOFF_PARSER()
    result.add_argument("--physical-request", type=Path, required=True)
    return result


def prepare_payload_handoff(args: argparse.Namespace) -> None:
    global _BOUND_PHYSICAL_REQUEST
    _ORIGINAL_PREPARE_PAYLOAD_HANDOFF(args)
    request_path = handoff.normalized_path(args.physical_request, strict=True)
    core.require(request_path.is_file() and not request_path.is_symlink(), "PHYSICAL_REQUEST_FILE_INVALID")
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        core.require(isinstance(raw, dict), "PHYSICAL_REQUEST_FILE_INVALID")
        _BOUND_PHYSICAL_REQUEST = contract.validate_physical_request(raw, args.package_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, contract.ContractError) as exc:
        raise core.ExecutionError(str(exc) if isinstance(exc, contract.ContractError) else "PHYSICAL_REQUEST_FILE_INVALID") from exc
    args.physical_request = request_path


def install() -> None:
    _prime_core()
    handoff.STAGE = STAGE
    handoff.D2_REQUEST_ID = D2_REQUEST_ID
    handoff.AUTH_SCHEMA = AUTH_SCHEMA
    handoff.RESULT_SCHEMA = RESULT_SCHEMA
    handoff.MARKER_SCHEMA = MARKER_SCHEMA
    handoff.PRE_RESULT_SCHEMA = PRE_RESULT_SCHEMA
    handoff.PRE_MARKER_SCHEMA = PRE_MARKER_SCHEMA
    handoff.parser = parser
    handoff.prepare_payload_handoff = prepare_payload_handoff
    handoff.configure_core = configure_core


def _contract_check(argv: list[str]) -> int:
    check = argparse.ArgumentParser()
    check.add_argument("--package-root", type=Path, required=True)
    check.add_argument("--physical-request", type=Path, required=True)
    check.add_argument("--authorization-record", type=Path, required=True)
    check.add_argument("--result-output", type=Path, required=True)
    check.add_argument("--now")
    args = check.parse_args(argv)
    result: dict[str, Any]
    try:
        package_root = args.package_root.expanduser().resolve(strict=True)
        request = json.loads(args.physical_request.read_text(encoding="utf-8"))
        authorization = json.loads(args.authorization_record.read_text(encoding="utf-8"))
        now = None
        if args.now:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc)
        contract.validate_authorization_contract(authorization, request, package_root, now=now)
        result = {
            "schema": "gh.h3.n2.stage2d9r-g3r-corrected-baseline-overlay-authorization-contract-check/1",
            "status": "PASS",
            "d2_request_id": D2_REQUEST_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
        }
        rc = 0
    except Exception as exc:
        result = {
            "schema": "gh.h3.n2.stage2d9r-g3r-corrected-baseline-overlay-authorization-contract-check/1",
            "status": "FAIL",
            "failure_code": str(exc.args[0]) if exc.args else type(exc).__name__,
            "d2_request_id": D2_REQUEST_ID,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
        }
        rc = 2
    args.result_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return rc


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "execution_overlay_role": "BLOCKING_CORRECTED_BASELINE",
            "corrected_baseline_sha256": contract.CORRECTED_BASELINE_SHA256,
            "request_05_state": contract.REQUEST_05_INVALID_STATE,
            "authorization_created": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 0
    if sys.argv[1] == "contract-check":
        return _contract_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print("first argument must be contract-check or execute", file=sys.stderr)
        return 2
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    install()
    return handoff.main()


if __name__ == "__main__":
    raise SystemExit(main())
