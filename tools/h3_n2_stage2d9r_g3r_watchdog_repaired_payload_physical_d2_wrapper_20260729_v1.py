#!/usr/bin/env python3
"""Physical D2 successor -10 bound to the watchdog-repaired payload closure.

The module is inert without a separately created exact, one-shot physical
authorization.  Importing or running it without arguments performs no board,
serial, Flash, Broker, PREPARE, or VERIFY operation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1 as upstream
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff
import h3_n2_stage2d9r_serial_handshake_repair_20260727_v1 as serial_repair

core = upstream.core
repaired = handoff.frozen
STAGE = contract.STAGE
D2_REQUEST_ID = contract.REQUEST_10_ID
AUTH_SCHEMA = contract.AUTH_SCHEMA
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA
PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA
_BASE_VALIDATE_AUTHORIZATION = upstream._BASE_VALIDATE_AUTHORIZATION
_ORIGINAL_HANDOFF_PARSER = upstream._ORIGINAL_HANDOFF_PARSER
_ORIGINAL_PREPARE_PAYLOAD_HANDOFF = upstream._ORIGINAL_PREPARE_PAYLOAD_HANDOFF
_BOUND_PHYSICAL_REQUEST: dict[str, Any] | None = None
_EVIDENCE_ROOT: Path | None = None


def _prime_payload_constants() -> None:
    """Rebind dynamic runtime constants to the exact PR204 frozen payload."""
    repaired.BASE_PR = contract.BASE_PR
    repaired.BASE_HEAD_SHA = contract.BASE_HEAD_SHA
    repaired.ACCEPTED_CURRENT_MAIN_SHA = contract.MAIN_SHA_AT_BINDING
    repaired.FINAL_EXECUTION_BINDING = contract.FINAL_EXECUTION_BINDING
    repaired.FINAL_EXECUTION_BINDING_SHA256 = (
        contract.FINAL_EXECUTION_BINDING_SHA256
    )
    repaired.IMMUTABLE_ARTIFACT_ID = contract.PR204_ARTIFACT_ID
    repaired.IMMUTABLE_ARCHIVE_SHA256 = contract.PR204_ARTIFACT_SHA256
    repaired.IMMUTABLE_PAYLOAD_TAR_SHA256 = (
        contract.IMMUTABLE_PAYLOAD_TAR_SHA256
    )
    repaired.IMMUTABLE_MERGED_SHA256 = contract.IMMUTABLE_MERGED_IMAGE_SHA256
    repaired.RECOVERY_PAYLOAD_TAR_SHA256 = contract.RECOVERY_PAYLOAD_TAR_SHA256
    repaired.RECOVERY_DESCRIPTOR_SHA256 = contract.RECOVERY_DESCRIPTOR_SHA256
    repaired.BUILD_BINDING = contract.IMMUTABLE_BUILD_BINDING


def _prime_core() -> None:
    _prime_payload_constants()
    upstream._prime_core()
    bindings = {
        "STAGE": STAGE,
        "D2_REQUEST_ID": D2_REQUEST_ID,
        "AUTH_SCHEMA": AUTH_SCHEMA,
        "RESULT_SCHEMA": RESULT_SCHEMA,
        "MARKER_SCHEMA": MARKER_SCHEMA,
        "IMMUTABLE_ARTIFACT_ID": contract.PR204_ARTIFACT_ID,
        "IMMUTABLE_ARCHIVE_SHA256": contract.PR204_ARTIFACT_SHA256,
        "IMMUTABLE_PAYLOAD_TAR_SHA256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE_MERGED_SHA256": contract.IMMUTABLE_MERGED_IMAGE_SHA256,
        "RECOVERY_ARTIFACT_ID": contract.PR204_ARTIFACT_ID,
        "RECOVERY_ARCHIVE_SHA256": contract.PR204_ARTIFACT_SHA256,
        "RECOVERY_PAYLOAD_TAR_SHA256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY_DESCRIPTOR_SHA256": contract.RECOVERY_DESCRIPTOR_SHA256,
        "BUILD_BINDING": contract.IMMUTABLE_BUILD_BINDING,
        "validate_public_inputs": handoff.validate_public_inputs,
        "locked_recovery": repaired.locked_recovery,
    }
    for key, value in bindings.items():
        setattr(core, key, value)
    core.canonical_package_digest = contract.canonical_package_digest
    core.__file__ = __file__


def configure_core() -> Any:
    _prime_core()

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = _BASE_VALIDATE_AUTHORIZATION(*args, **kwargs)
        package_root = kwargs.get("package_root")
        core.require(
            isinstance(package_root, Path),
            "AUTHORIZATION_PACKAGE_ROOT_MISSING",
        )
        core.require(
            _BOUND_PHYSICAL_REQUEST is not None,
            "PHYSICAL_REQUEST_NOT_BOUND",
        )
        try:
            contract.validate_authorization_contract(
                value,
                _BOUND_PHYSICAL_REQUEST,
                package_root,
            )
        except contract.ContractError as exc:
            raise core.ExecutionError(str(exc)) from exc
        core.require(
            value.get("locked_recovery_authorized") is True,
            "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED",
        )
        return value

    core.validate_authorization = validate_authorization
    try:
        import serial  # type: ignore
    except ImportError as exc:  # pragma: no cover - host-only dependency
        raise serial_repair.HandshakeRepairError("PYSERIAL_UNAVAILABLE") from exc
    repaired_controller = upstream.RealtimeRepairedHandshakeController(
        core, serial.Serial
    )
    repaired_controller.install()
    core.require(
        _EVIDENCE_ROOT is not None,
        "PREPARE_EVIDENCE_ROOT_NOT_BOUND",
    )
    evidence_controller = upstream.PanicTimelineEvidenceExecutionController(
        repaired_controller,
        _EVIDENCE_ROOT,
    )
    evidence_controller.install()
    setattr(
        core,
        "_watchdog_repaired_payload_panic_timeline_controller",
        evidence_controller,
    )
    return core


def parser() -> argparse.ArgumentParser:
    value = _ORIGINAL_HANDOFF_PARSER()
    value.add_argument("--prepare-evidence-root", type=Path, required=True)
    return value


def prepare_payload_handoff(args: argparse.Namespace) -> None:
    global _BOUND_PHYSICAL_REQUEST, _EVIDENCE_ROOT
    _prime_payload_constants()
    _ORIGINAL_PREPARE_PAYLOAD_HANDOFF(args)
    request_path = handoff.normalized_path(args.physical_request, strict=True)
    package_root = args.package_root
    core.require(
        request_path.is_file() and not request_path.is_symlink(),
        "PHYSICAL_REQUEST_FILE_INVALID",
    )
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        core.require(isinstance(raw, dict), "PHYSICAL_REQUEST_FILE_INVALID")
        _BOUND_PHYSICAL_REQUEST = contract.validate_physical_request(
            raw, package_root
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        contract.ContractError,
    ) as exc:
        code = (
            str(exc)
            if isinstance(exc, contract.ContractError)
            else "PHYSICAL_REQUEST_FILE_INVALID"
        )
        raise core.ExecutionError(code) from exc
    evidence_root = handoff.normalized_path(
        args.prepare_evidence_root, strict=False
    )
    if evidence_root.exists():
        core.require(
            evidence_root.is_dir() and not evidence_root.is_symlink(),
            "PREPARE_EVIDENCE_ROOT_INVALID",
        )
        core.require(
            not any(evidence_root.iterdir()),
            "PREPARE_EVIDENCE_ROOT_NOT_EMPTY",
        )
    _EVIDENCE_ROOT = evidence_root
    args.physical_request = request_path
    args.prepare_evidence_root = evidence_root


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
    try:
        package_root = args.package_root.expanduser().resolve(strict=True)
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
            authorization,
            request,
            package_root,
            now=now,
        )
        result: dict[str, Any] = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-"
                "authorization-contract-check/1"
            ),
            "status": "PASS",
            "d2_request_id": D2_REQUEST_ID,
            "request_binding_sha256": request["request_binding_sha256"],
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
                "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-"
                "authorization-contract-check/1"
            ),
            "status": "FAIL",
            "failure_code": (
                str(exc.args[0]) if exc.args else type(exc).__name__
            ),
            "d2_request_id": D2_REQUEST_ID,
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
    if len(sys.argv) == 1:
        print(
            json.dumps(
                {
                    "status": (
                        "SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION"
                    ),
                    "decision_id": contract.DECISION_ID,
                    "d2_request_id": D2_REQUEST_ID,
                    "predecessor_request_id": contract.D2_09_ID,
                    "predecessor_status": contract.D2_09_STATUS,
                    "predecessor_failure_code": contract.D2_09_FAILURE_CODE,
                    "repository_head_role": "AUDIT_ONLY",
                    "repository_head_enforced": False,
                    "execution_closure_role": "BLOCKING",
                    "new_payload_bound": True,
                    "old_payload_reuse_permitted": False,
                    "authorization_created": False,
                    "board_operation": False,
                    "usb_enumeration": False,
                    "serial_operation": False,
                    "esptool_operation": False,
                    "flash_operation": False,
                    "network_operation": False,
                    "replay_permitted": False,
                    "automatic_retry_permitted": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if sys.argv[1] == "contract-check":
        return _contract_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print(
            "first argument must be contract-check or execute",
            file=sys.stderr,
        )
        return 2
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    install()
    return handoff.main()


if __name__ == "__main__":
    raise SystemExit(main())
