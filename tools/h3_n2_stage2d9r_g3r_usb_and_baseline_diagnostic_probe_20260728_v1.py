#!/usr/bin/env python3
"""Future one-shot read-only B2 probe; inert without exact authorization."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_usb_identity_evidence_capture_20260728_v1 as capture
import h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_contract_20260728_v1 as contract

ADDR = 0x400000
SIZE = 0x10000


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def read_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink() and mode(path) == "0600", code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(code) from exc
    require(isinstance(value, dict), code)
    return value


def write_json(path: Path, value: Mapping[str, Any], replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    target = path.with_name(path.name + ".tmp") if replace else path
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    if replace:
        os.replace(target, path)
    os.chmod(path, 0o600)


def executable(value: str | None, name: str) -> Path:
    candidate = value or shutil.which(name)
    require(candidate is not None, name.upper() + "_UNAVAILABLE")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(path.is_file() and not path.is_symlink() and os.access(path, os.X_OK), name.upper() + "_INVALID")
    return path


@dataclass(frozen=True)
class Identity:
    device: str
    vid: int
    pid: int
    serial_number: str
    manufacturer: str
    product: str
    location: str
    hwid: str


def enumerate_candidates() -> list[Identity]:
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError as exc:
        raise ProbeError("PYSERIAL_UNAVAILABLE") from exc
    result: list[Identity] = []
    for port in list_ports.comports():
        if port.vid is None or port.pid is None:
            continue
        text = " ".join(filter(None, [port.manufacturer, port.product, port.description, port.hwid])).lower()
        if not any(token in text for token in ("espressif", "esp32", "usb jtag", "usb serial")):
            continue
        result.append(Identity(
            str(port.device or ""), int(port.vid), int(port.pid), str(port.serial_number or ""),
            str(port.manufacturer or ""), str(port.product or port.description or ""),
            str(port.location or ""), str(port.hwid or ""),
        ))
    return result


def run(command: list[str], timeout: float, code: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, check=False, text=True, capture_output=True, timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    require(completed.returncode == 0, code)
    return completed


def esptool_command(tool: Path, port: str, *args: str) -> list[str]:
    return [str(tool), "--chip", "esp32c6", "--port", port, *args]


def marker_path(root: Path) -> Path:
    return root / (hashlib.sha256(contract.FUTURE_B2_AUTHORIZATION_ID.encode("utf-8")).hexdigest() + ".json")


def claim(marker: Path, authorization: Mapping[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json(marker, {
        "schema": contract.B2_MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
        "status": "CLAIMED",
        "authorization_record_sha256": authorization["authorization_record_sha256"],
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "flash_write": False,
        "flash_erase": False,
        "serial_open": False,
        "network_operation": False,
        "broker_started": False,
    })


def finish(marker: Path, status: str, digest: str, failure: str | None) -> None:
    write_json(marker, {
        "schema": contract.B2_MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
        "status": status,
        "diagnostic_result_sha256": digest,
        "failure_code": failure,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "flash_write": False,
        "flash_erase": False,
        "serial_open": False,
        "network_operation": False,
        "broker_started": False,
    }, replace=True)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    source = contract.validate_sha40(args.source_sha, "SOURCE_SHA_INVALID")
    review = contract.validate_sha256(args.review_binding_sha256, "REVIEW_BINDING_INVALID")
    b1_result = read_json(args.b1_result.expanduser().resolve(strict=True), "B1_RESULT_INVALID")
    contract.validate_b1_result(b1_result)
    python = Path(sys.executable).resolve(strict=True)
    tool = executable(args.esptool, "esptool")
    script = Path(__file__).resolve(strict=True)
    authorization = read_json(args.authorization.expanduser().resolve(strict=True), "AUTHORIZATION_INVALID")
    authorization = contract.validate_b2_authorization(
        authorization,
        source_sha=source,
        review_binding_sha256=review,
        diagnostic_script_sha256=contract.sha256_file(script),
        python_executable_sha256=contract.sha256_file(python),
        esptool_executable_sha256=contract.sha256_file(tool),
    )
    state = args.state_root.expanduser().resolve(strict=True)
    require(state.is_dir() and not state.is_symlink() and mode(state) == "0700", "STATE_ROOT_INVALID")
    marker = marker_path(state)
    claim(marker, authorization)
    observed_transport: dict[str, Any] | None = None
    try:
        candidates = enumerate_candidates()
        require(len(candidates) == 1, "USB_CANDIDATE_COUNT_NOT_ONE")
        selected = candidates[0]
        observed_transport = capture.capture_transport(selected)
        with tempfile.TemporaryDirectory(prefix="stage2d9r-usb-baseline-diagnostic-") as directory:
            work = Path(directory)
            chip = run(esptool_command(tool, selected.device, "chip_id"), 30, "DIAGNOSTIC_CHIP_ID_FAILED")
            flash = run(esptool_command(tool, selected.device, "flash_id"), 30, "DIAGNOSTIC_FLASH_ID_FAILED")
            partition = work / "test-partition.bin"
            run(
                esptool_command(tool, selected.device, "read_flash", hex(ADDR), hex(SIZE), str(partition)),
                45,
                "DIAGNOSTIC_PARTITION_READ_FAILED",
            )
            require(partition.is_file() and partition.stat().st_size == SIZE, "DIAGNOSTIC_PARTITION_SIZE_MISMATCH")
            evidence = capture.build_complete_evidence(
                identity=selected,
                chip_stdout=chip.stdout,
                flash_stdout=flash.stdout,
                test_partition_sha256=contract.sha256_file(partition),
                test_partition_size=SIZE,
            )
        result: dict[str, Any] = {
            "schema": contract.B2_RESULT_SCHEMA,
            "state": "USB_AND_PATH_NEUTRAL_BASELINE_EVIDENCE_CAPTURED_AWAITING_ACCEPTANCE_DECISION",
            "status": "CONSUMED_PASS",
            "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
            "source_sha": source,
            "review_binding_sha256": review,
            "b1_result_sha256": contract.B1_RESULT_SHA256,
            "operator_report_id": contract.OPERATOR_REPORT_ID,
            "operator_reported_usb_port_changed": True,
            "baseline_evidence": evidence,
            "future_physical_request_id": contract.FUTURE_PHYSICAL_REQUEST_ID,
            "future_physical_request_created": False,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_operation": True,
            "usb_enumeration": True,
            "esptool_readonly_operation": True,
            "serial_open": False,
            "flash_write": False,
            "flash_erase": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        result["diagnostic_result_sha256"] = contract.canonical_json_sha256(result)
        write_json(args.result_output.expanduser(), result)
        finish(marker, "CONSUMED_PASS", result["diagnostic_result_sha256"], None)
        return result
    except Exception as exc:
        failure = str(exc.args[0]) if exc.args else type(exc).__name__
        result = {
            "schema": contract.B2_RESULT_SCHEMA,
            "status": "CONSUMED_FAILED",
            "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
            "failure_code": failure,
            "observed_transport_evidence": observed_transport,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "future_physical_request_created": False,
            "flash_write": False,
            "flash_erase": False,
            "serial_open": False,
            "network_operation": False,
            "broker_started": False,
        }
        result["diagnostic_result_sha256"] = contract.canonical_json_sha256(result)
        write_json(args.result_output.expanduser(), result)
        finish(marker, "CONSUMED_FAILED", result["diagnostic_result_sha256"], failure)
        raise


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_EXACT_B2_READONLY_AUTHORIZATION",
            "authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
            "authorization_created": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_open": False,
            "esptool_operation": False,
            "flash_write": False,
            "flash_erase": False,
            "network_operation": False,
            "broker_started": False,
            "future_physical_request_created": False,
        }, sort_keys=True))
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--review-binding-sha256", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--b1-result", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--esptool")
    args = parser.parse_args()
    try:
        result = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (ProbeError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({
            "status": "FAIL",
            "failure_code": str(code),
            "flash_write": False,
            "flash_erase": False,
            "serial_open": False,
            "network_operation": False,
            "broker_started": False,
            "future_physical_request_created": False,
        }, sort_keys=True))
        return 2
    evidence = result["baseline_evidence"]
    print(json.dumps({
        "status": result["status"],
        "diagnostic_result_sha256": result["diagnostic_result_sha256"],
        "legacy_board_identity_matches": evidence["legacy_board_identity_matches"],
        "legacy_serial_identity_matches": evidence["legacy_serial_identity_matches"],
        "legacy_baseline_matches": evidence["legacy_baseline_matches"],
        "future_physical_request_created": False,
        "flash_write": False,
        "flash_erase": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
