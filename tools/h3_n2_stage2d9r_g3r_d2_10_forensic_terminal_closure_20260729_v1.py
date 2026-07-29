#!/usr/bin/env python3
"""Plan or separately authorize closure of the stale D2-10 host marker.

The tool performs filesystem-only evidence validation. It contains no USB,
serial, esptool, Flash, Broker, PREPARE, or VERIFY code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_contract_20260729_v1 as contract

RESULT_NAME = "D2_10_FORENSIC_TERMINAL_RESULT_PROPOSED.json"
MARKER_NAME = "D2_10_FORENSIC_TERMINAL_MARKER_PROPOSED.json"
PLAN_NAME = "D2_10_FORENSIC_TERMINAL_CLOSURE_PLAN.json"
SUMS_NAME = "SHA256SUMS"


def write_exclusive(path: Path, value: object) -> None:
    data = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def replace_marker(path: Path, value: dict[str, Any]) -> None:
    contract.require(
        path.is_file() and not path.is_symlink(), "MARKER_REPLACE_TARGET"
    )
    contract.require(
        contract.sha256_file(path) == contract.MARKER_FILE_SHA256,
        "MARKER_REPLACE_SOURCE_DIGEST",
    )
    temp = path.with_name(path.name + ".forensic-closure.tmp")
    contract.require(not temp.exists(), "MARKER_REPLACE_TEMP_EXISTS")
    write_exclusive(temp, value)
    os.replace(temp, path)
    os.chmod(path, 0o600)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass


def load_authorization(path: Path) -> dict[str, Any]:
    contract.require(
        path.is_file() and not path.is_symlink(), "CLOSURE_AUTH_FILE"
    )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise contract.ContractError("CLOSURE_AUTH_FILE_JSON") from exc
    contract.require(isinstance(value, dict), "CLOSURE_AUTH_FILE_JSON")
    return value


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    validated = contract.validate_forensic_inputs(
        marker_path=args.marker.expanduser().resolve(strict=True),
        contract_check_path=args.contract_check.expanduser().resolve(strict=True),
        terminal_output_path=args.terminal_output.expanduser().resolve(strict=True),
        evidence_root=args.evidence_root.expanduser().resolve(strict=True),
    )
    result = contract.build_terminal_result(validated)
    marker = contract.build_terminal_marker(result)
    return result, marker


def write_plan(
    output: Path, result: dict[str, Any], marker: dict[str, Any]
) -> dict[str, Any]:
    output = output.expanduser().resolve(strict=False)
    if output.exists():
        contract.require(
            output.is_dir() and not output.is_symlink() and not any(output.iterdir()),
            "PLAN_OUTPUT_NOT_EMPTY",
        )
    else:
        output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    plan: dict[str, Any] = {
        "schema": contract.FORENSIC_PLAN_SCHEMA,
        "decision_id": contract.DECISION_ID,
        "d2_request_id": contract.D2_REQUEST_ID,
        "status": "FORENSIC_TERMINAL_CLOSURE_PLANNED_NOT_APPLIED",
        "stale_marker_sha256": contract.MARKER_FILE_SHA256,
        "terminal_result_sha256": result["terminal_result_sha256"],
        "terminal_marker_sha256": contract.canonical_sha256(marker),
        "closure_authorization_created": False,
        "closure_applied": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    write_exclusive(output / RESULT_NAME, result)
    write_exclusive(output / MARKER_NAME, marker)
    write_exclusive(output / PLAN_NAME, plan)
    lines = []
    for name in sorted((RESULT_NAME, MARKER_NAME, PLAN_NAME)):
        lines.append(f"{contract.sha256_file(output / name)}  {name}")
    sums = ("\n".join(lines) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(output / SUMS_NAME, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(sums)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(output / SUMS_NAME, 0o600)
    return plan


def plan(args: argparse.Namespace) -> int:
    result, marker = build(args)
    value = write_plan(args.output, result, marker)
    print(json.dumps(value, sort_keys=True))
    return 0


def close(args: argparse.Namespace) -> int:
    result, marker = build(args)
    authorization = load_authorization(
        args.closure_authorization.expanduser().resolve(strict=True)
    )
    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        if args.now
        else None
    )
    contract.validate_closure_authorization(
        authorization,
        result=result,
        marker=marker,
        tool_sha256=contract.sha256_file(Path(__file__).resolve(strict=True)),
        now=now,
    )
    result_path = args.result_output.expanduser().resolve(strict=False)
    contract.require(not result_path.exists(), "TERMINAL_RESULT_ALREADY_EXISTS")
    result_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(result_path.parent, 0o700)
    write_exclusive(result_path, result)
    try:
        replace_marker(args.marker.expanduser().resolve(strict=True), marker)
    except BaseException:
        if result_path.is_file() and not result_path.is_symlink():
            failed = result_path.with_name(result_path.name + ".marker-not-closed")
            os.replace(result_path, failed)
        raise
    value = {
        "schema": contract.FORENSIC_PLAN_SCHEMA,
        "decision_id": contract.DECISION_ID,
        "d2_request_id": contract.D2_REQUEST_ID,
        "status": "FORENSIC_TERMINAL_CLOSED",
        "terminal_result_sha256": result["terminal_result_sha256"],
        "terminal_marker_sha256": contract.canonical_sha256(marker),
        "closure_authorization_sha256": authorization[
            "closure_authorization_sha256"
        ],
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    print(json.dumps(value, sort_keys=True))
    return 0


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--contract-check", type=Path, required=True)
    parser.add_argument("--terminal-output", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="command", required=True)
    planned = sub.add_parser("plan")
    common(planned)
    planned.add_argument("--output", type=Path, required=True)
    closing = sub.add_parser("close")
    common(closing)
    closing.add_argument("--closure-authorization", type=Path, required=True)
    closing.add_argument("--result-output", type=Path, required=True)
    closing.add_argument("--now")
    return value


def main() -> int:
    if len(sys.argv) == 1:
        print(
            json.dumps(
                {
                    "status": "SOURCE_ONLY_NO_CLOSURE_AUTHORIZATION",
                    "decision_id": contract.DECISION_ID,
                    "d2_request_id": contract.D2_REQUEST_ID,
                    "closure_authorization_created": False,
                    "closure_applied": False,
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
    args = parser().parse_args()
    try:
        return plan(args) if args.command == "plan" else close(args)
    except Exception as exc:
        code = str(exc.args[0]) if exc.args else type(exc).__name__
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "failure_code": code,
                    "d2_request_id": contract.D2_REQUEST_ID,
                    "closure_applied": False,
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
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
