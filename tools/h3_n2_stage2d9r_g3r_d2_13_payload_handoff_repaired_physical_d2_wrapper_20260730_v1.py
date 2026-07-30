#!/usr/bin/env python3
"""D2-13 adapter repairing shell-to-Python payload handoff before parsing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_physical_d2_wrapper_20260729_v1 as predecessor
import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_contract_20260730_v1 as contract

LAUNCHER_ROOT_ENV = "GH_D2_13_LAUNCHER_PACKAGE_ROOT"


class PayloadHandoffRepairError(RuntimeError):
    """Stable preclaim payload-handoff failure."""


def _fail(code: str) -> None:
    raise PayloadHandoffRepairError(code)


def _normalize(value: str | Path, *, strict: bool, code: str) -> Path:
    try:
        return Path(value).expanduser().resolve(strict=strict)
    except (OSError, RuntimeError) as exc:
        raise PayloadHandoffRepairError(code) from exc


def _option_values(argv: list[str], name: str) -> list[str]:
    values: list[str] = []
    index = 0
    prefix = name + "="
    while index < len(argv):
        item = argv[index]
        if item == name:
            if index + 1 >= len(argv):
                _fail("HANDOFF_OPTION_VALUE_MISSING")
            values.append(argv[index + 1])
            index += 2
            continue
        if item.startswith(prefix):
            values.append(item[len(prefix):])
        index += 1
    return values


def _one(argv: list[str], name: str, *, required: bool, code: str) -> str | None:
    values = _option_values(argv, name)
    if len(values) > 1:
        _fail(code + "_DUPLICATE")
    if not values:
        if required:
            _fail(code + "_MISSING")
        return None
    if not values[0]:
        _fail(code + "_EMPTY")
    return values[0]


def _append_or_validate(
    argv: list[str],
    option: str,
    expected: Path,
    *,
    code: str,
) -> list[str]:
    supplied = _one(argv, option, required=False, code=code)
    if supplied is None:
        return [*argv, option, str(expected)]
    actual = _normalize(supplied, strict=True, code=code + "_INVALID")
    if actual != expected:
        _fail(code + "_MISMATCH")
    return argv


def repair_execute_argv(argv: list[str], *, environ: dict[str, str] | None = None) -> list[str]:
    """Bind both payload TARs to the normalized execution package root."""
    env = os.environ if environ is None else environ
    package_raw = _one(argv, "--package-root", required=True, code="PACKAGE_ROOT")
    assert package_raw is not None
    package_root = _normalize(package_raw, strict=True, code="PACKAGE_ROOT_INVALID")
    if not package_root.is_dir() or package_root.is_symlink():
        _fail("PACKAGE_ROOT_INVALID")

    launcher_raw = env.get(LAUNCHER_ROOT_ENV)
    if not launcher_raw:
        _fail("LAUNCHER_PACKAGE_ROOT_MISSING")
    launcher_root = _normalize(launcher_raw, strict=True, code="LAUNCHER_PACKAGE_ROOT_INVALID")
    if launcher_root != package_root:
        _fail("LAUNCHER_PACKAGE_ROOT_MISMATCH")

    immutable = _normalize(
        package_root / contract.IMMUTABLE_PAYLOAD_FILE,
        strict=True,
        code="IMMUTABLE_PAYLOAD_TAR_MISSING",
    )
    recovery = _normalize(
        package_root / contract.RECOVERY_PAYLOAD_FILE,
        strict=True,
        code="RECOVERY_PAYLOAD_TAR_MISSING",
    )
    if not immutable.is_file() or immutable.is_symlink():
        _fail("IMMUTABLE_PAYLOAD_TAR_INVALID")
    if not recovery.is_file() or recovery.is_symlink():
        _fail("RECOVERY_PAYLOAD_TAR_INVALID")

    repaired = _append_or_validate(
        argv,
        "--immutable-payload-tar",
        immutable,
        code="IMMUTABLE_PAYLOAD_TAR",
    )
    repaired = _append_or_validate(
        repaired,
        "--recovery-payload-tar",
        recovery,
        code="RECOVERY_PAYLOAD_TAR",
    )
    return repaired


def bind_upstream() -> None:
    if not sys.dont_write_bytecode:
        raise contract.ContractError("PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START")
    predecessor.contract = contract
    predecessor.bind_upstream()


def _stable_error(exc: BaseException) -> str:
    if isinstance(exc, PayloadHandoffRepairError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    if isinstance(exc, contract.ContractError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return type(exc).__name__


def _safe_path_from_argv(argv: list[str], option: str) -> Path | None:
    try:
        raw = _one(argv, option, required=False, code=option.strip("-").upper())
    except PayloadHandoffRepairError:
        return None
    if raw is None:
        return None
    try:
        return Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _authorization_created(path: Path | None) -> bool:
    return path is not None and path.is_file() and not path.is_symlink()


def _marker_path(state_root: Path | None) -> Path | None:
    if state_root is None:
        return None
    return state_root / (hashlib.sha256(contract.D2_REQUEST_ID.encode()).hexdigest() + ".json")


def _write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def write_preclaim_handoff_failure(argv: list[str], code: str) -> dict[str, Any]:
    auth = _safe_path_from_argv(argv, "--authorization-record")
    result_path = _safe_path_from_argv(argv, "--result-output")
    state_root = _safe_path_from_argv(argv, "--state-root")
    created = _authorization_created(auth)
    marker = _marker_path(state_root)
    claimed = marker is not None and marker.exists()
    value: dict[str, Any] = {
        "schema": contract.PRE_RESULT_SCHEMA,
        "stage": contract.STAGE,
        "d2_request_id": contract.D2_REQUEST_ID,
        "status": "CONSUMED_FAILED" if created else "FAIL",
        "terminal_state": "CONSUMED_FAILED_PRECLAIM" if created else "PRECLAIM_REJECTED",
        "failure_code": code,
        "failure_stage": "OUTER_TO_INNER_PAYLOAD_HANDOFF",
        "authorization_created": created,
        "authorization_claimed": claimed,
        "authorization_consumed": created,
        "authorization_record_sha256": contract.sha256_file(auth) if created and auth is not None else None,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    value["terminal_result_sha256"] = contract.canonical_sha256(value)
    if result_path is not None and not result_path.exists():
        _write_exclusive_json(result_path, value)
    if created and marker is not None and not marker.exists():
        marker_value = {
            "schema": contract.PRE_MARKER_SCHEMA,
            "stage": contract.STAGE,
            "d2_request_id": contract.D2_REQUEST_ID,
            "status": "CONSUMED_FAILED",
            "failure_code": code,
            "failure_stage": "OUTER_TO_INNER_PAYLOAD_HANDOFF",
            "authorization_created": True,
            "authorization_claimed": False,
            "authorization_consumed": True,
            "authorization_record_sha256": value["authorization_record_sha256"],
            "terminal_result_sha256": value["terminal_result_sha256"],
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        _write_exclusive_json(marker, marker_value)
    return value


def source_status() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-execution-binding-source/1",
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_13_AUTHORIZATION",
        "decision_id": contract.DECISION_ID,
        "d2_request_id": contract.D2_REQUEST_ID,
        "predecessor_request_id": contract.D2_12_ID,
        "predecessor_status": contract.D2_12_STATUS,
        "predecessor_failure_code": contract.D2_12_FAILURE_CODE,
        "shell_to_python_package_root_handoff_required": True,
        "payload_arguments_injected_before_upstream_parser": True,
        "macos_path_normalization_required": True,
        "preclaim_failure_evidence_required": True,
        "bytecode_write_disabled_for_current_process": sys.dont_write_bytecode,
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
        authorization = json.loads(args.authorization_record.read_text(encoding="utf-8"))
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc) if args.now else None
        contract.validate_authorization_contract(authorization, request, root, now=now)
        result: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-authorization-contract-check/1",
            "status": "PASS",
            "d2_request_id": contract.D2_REQUEST_ID,
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
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-authorization-contract-check/1",
            "status": "FAIL",
            "failure_code": _stable_error(exc),
            "d2_request_id": contract.D2_REQUEST_ID,
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
    args.result_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return rc


def handoff_check(argv: list[str]) -> int:
    check = argparse.ArgumentParser()
    check.add_argument("--package-root", required=True)
    check.add_argument("--immutable-payload-tar")
    check.add_argument("--recovery-payload-tar")
    check.add_argument("--result-output", type=Path, required=True)
    args = check.parse_args(argv)
    raw = ["--package-root", args.package_root]
    if args.immutable_payload_tar is not None:
        raw.extend(["--immutable-payload-tar", args.immutable_payload_tar])
    if args.recovery_payload_tar is not None:
        raw.extend(["--recovery-payload-tar", args.recovery_payload_tar])
    try:
        repaired = repair_execute_argv(raw)
        immutable = Path(repaired[repaired.index("--immutable-payload-tar") + 1])
        recovery = Path(repaired[repaired.index("--recovery-payload-tar") + 1])
        result: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-check/1",
            "status": "PASS",
            "d2_request_id": contract.D2_REQUEST_ID,
            "payload_arguments_injected": (
                args.immutable_payload_tar is None
                and args.recovery_payload_tar is None
            ),
            "launcher_package_root_matches": True,
            "immutable_payload_sha256_matches": (
                contract.sha256_file(immutable)
                == contract.IMMUTABLE_PAYLOAD_TAR_SHA256
            ),
            "recovery_payload_sha256_matches": (
                contract.sha256_file(recovery)
                == contract.RECOVERY_PAYLOAD_TAR_SHA256
            ),
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
        }
        if not (
            result["immutable_payload_sha256_matches"]
            and result["recovery_payload_sha256_matches"]
        ):
            raise PayloadHandoffRepairError("PAYLOAD_TAR_DIGEST_MISMATCH")
        rc = 0
    except Exception as exc:
        result = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-check/1",
            "status": "FAIL",
            "failure_code": _stable_error(exc),
            "d2_request_id": contract.D2_REQUEST_ID,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
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
        value.update({"status": "FAIL", "failure_code": "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"})
        print(json.dumps(value, sort_keys=True))
        return 2
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
        return 0
    if sys.argv[1] == "contract-check":
        return contract_check(sys.argv[2:])
    if sys.argv[1] == "handoff-check":
        return handoff_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print("first argument must be contract-check, handoff-check or execute", file=sys.stderr)
        return 2
    original = sys.argv[2:]
    try:
        bind_upstream()
        repaired = repair_execute_argv(original)
    except Exception as exc:
        code = _stable_error(exc)
        value = write_preclaim_handoff_failure(original, code)
        print(json.dumps({
            "status": value["status"],
            "failure_code": code,
            "d2_request_id": contract.D2_REQUEST_ID,
            "authorization_claimed": value["authorization_claimed"],
            "authorization_consumed": value["authorization_consumed"],
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 2
    sys.argv = [sys.argv[0], "execute", *repaired]
    return predecessor.upstream.main()


if __name__ == "__main__":
    raise SystemExit(main())
