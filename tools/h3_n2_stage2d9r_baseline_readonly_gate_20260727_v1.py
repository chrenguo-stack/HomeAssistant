#!/usr/bin/env python3
"""Exact one-shot read-only board-baseline collector for Stage2D9R successor.

This module is inert without a current exact authorization record. It performs
no USB enumeration or board operation before an atomic authorization claim.
After claim it permits only one Espressif USB serial candidate and the read-only
esptool operations chip_id, flash_id and read_flash for the isolated 64 KiB test
partition. It contains no erase, write, verify, NVS, Wi-Fi, MQTT or Broker path.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any, Callable

STAGE = "H3/N2 Stage 2D-9R G3R successor"
D1_ID = "D1-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-GATE-20260727-01"
AUTHORIZATION_ID = (
    "D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01"
)
AUTH_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-baseline-readonly-authorization/1"
)
RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-board-baseline-readonly-result/1"
)
MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-baseline-readonly-consumed-marker/1"
)
TEST_PARTITION_ADDRESS = 0x400000
TEST_PARTITION_SIZE = 0x10000
ESPRESSIF_USB_VID = 0x303A
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_OPERATIONS = (
    "ENUMERATE_ONE_ESPRESSIF_USB_SERIAL_CANDIDATE",
    "READ_CHIP_ID",
    "READ_FLASH_ID",
    "READ_TEST_PARTITION_0X400000_0X10000",
)
FORBIDDEN_AUTHORIZATION_KEYS = (
    "erase_flash_authorized",
    "write_flash_authorized",
    "verify_flash_authorized",
    "physical_nvs_authorized",
    "network_authorized",
    "broker_authorized",
    "prepare_authorized",
    "verify_command_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "automatic_retry_permitted",
    "replay_permitted",
)


class BaselineGateError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise BaselineGateError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def require_regular(path: Path, expected_mode: str, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == expected_mode, code)


def load_json(path: Path, expected_mode: str, code: str) -> dict[str, Any]:
    require_regular(path, expected_mode, code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code)
    return value


def write_json_exclusive(
    path: Path, value: object, file_mode_value: int = 0o600
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, file_mode_value)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, file_mode_value)


def replace_json(path: Path, value: object) -> None:
    require(path.is_file() and not path.is_symlink(), "MARKER_INVALID")
    temp = path.with_name(path.name + ".tmp")
    require(not temp.exists(), "MARKER_TEMP_EXISTS")
    write_json_exclusive(temp, value)
    os.replace(temp, path)
    os.chmod(path, 0o600)


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineGateError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def executable(value: str | None, name: str) -> Path:
    candidate = value or shutil.which(name)
    require(candidate is not None, f"{name.upper()}_UNAVAILABLE")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(
        path.is_file() and not path.is_symlink() and os.access(path, os.X_OK),
        f"{name.upper()}_INVALID",
    )
    return path


def validate_authorization(
    path: Path,
    *,
    package_sha256: str,
    python_path: Path,
    esptool_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    value = load_json(path, "0600", "AUTHORIZATION_RECORD_INVALID")
    require(value.get("schema") == AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(value.get("stage") == STAGE, "AUTHORIZATION_STAGE_MISMATCH")
    require(value.get("d1_decision_id") == D1_ID, "AUTHORIZATION_D1_MISMATCH")
    require(
        value.get("authorization_id") == AUTHORIZATION_ID,
        "AUTHORIZATION_ID_MISMATCH",
    )
    require(value.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(value.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_EXPANDED")
    require(
        value.get("automatic_retry_permitted") is False,
        "AUTHORIZATION_RETRY_EXPANDED",
    )
    require(value.get("expected_serial_candidate_count") == 1,
            "AUTHORIZATION_CANDIDATE_COUNT_INVALID")
    require(tuple(value.get("allowed_operations", ())) == ALLOWED_OPERATIONS,
            "AUTHORIZATION_OPERATION_SET_MISMATCH")
    for key in FORBIDDEN_AUTHORIZATION_KEYS:
        require(value.get(key) is False, f"AUTHORIZATION_{key.upper()}")

    issued = utc(value.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require(
        0 < (expires - issued).total_seconds() <= 7200,
        "AUTHORIZATION_WINDOW_INVALID",
    )

    required = {
        "package_sha256": package_sha256,
        "execution_script_sha256": sha256_file(Path(__file__).resolve(strict=True)),
        "python_executable_sha256": sha256_file(python_path),
        "esptool_executable_sha256": sha256_file(esptool_path),
    }
    for key, expected in required.items():
        require(value.get(key) == expected, f"AUTHORIZATION_{key.upper()}_MISMATCH")

    without_binding = dict(value)
    observed = without_binding.pop("authorization_record_sha256", None)
    require(
        observed == canonical_sha256(without_binding),
        "AUTHORIZATION_RECORD_DIGEST_MISMATCH",
    )
    return value


@dataclass(frozen=True)
class SerialIdentity:
    device: str
    vid: int
    pid: int
    serial_number: str
    manufacturer: str
    product: str
    location: str
    hwid: str

    def board_binding(self) -> dict[str, Any]:
        return {
            "schema": "gh.h3.n2.stage2d9r-successor-board-identity/1",
            "vid": self.vid,
            "pid": self.pid,
            "serial_number": self.serial_number,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "location": self.location,
        }

    def serial_binding(self) -> dict[str, Any]:
        return {
            "schema": "gh.h3.n2.stage2d9r-successor-serial-identity/1",
            "device": self.device,
            "vid": self.vid,
            "pid": self.pid,
            "serial_number": self.serial_number,
            "location": self.location,
            "hwid": self.hwid,
        }


def enumerate_serial() -> list[SerialIdentity]:
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError as exc:
        raise BaselineGateError("PYSERIAL_UNAVAILABLE") from exc

    result: list[SerialIdentity] = []
    for port in list_ports.comports():
        if port.vid != ESPRESSIF_USB_VID or port.pid is None:
            continue
        text = " ".join(
            filter(
                None,
                [
                    port.manufacturer,
                    port.product,
                    port.description,
                    port.hwid,
                ],
            )
        ).lower()
        if not any(token in text for token in ("espressif", "esp32", "usb jtag", "usb serial")):
            continue
        result.append(
            SerialIdentity(
                device=str(port.device or ""),
                vid=int(port.vid),
                pid=int(port.pid),
                serial_number=str(port.serial_number or ""),
                manufacturer=str(port.manufacturer or ""),
                product=str(port.product or port.description or ""),
                location=str(port.location or ""),
                hwid=str(port.hwid or ""),
            )
        )
    return result


def run_process(
    command: list[str],
    *,
    timeout: float,
    code: str,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    require(completed.returncode == 0, code)
    return completed


def esptool_command(esptool_path: Path, port: str, *args: str) -> list[str]:
    return [str(esptool_path), "--chip", "esp32c6", "--port", port, *args]


def collect_baseline(
    selected: SerialIdentity,
    esptool_path: Path,
    work: Path,
    *,
    process_runner: Callable[..., subprocess.CompletedProcess[str]] = run_process,
) -> dict[str, Any]:
    chip = process_runner(
        esptool_command(esptool_path, selected.device, "chip_id"),
        timeout=30,
        code="BASELINE_CHIP_ID_FAILED",
    )
    flash = process_runner(
        esptool_command(esptool_path, selected.device, "flash_id"),
        timeout=30,
        code="BASELINE_FLASH_ID_FAILED",
    )
    partition = work / "baseline-test-partition.bin"
    process_runner(
        esptool_command(
            esptool_path,
            selected.device,
            "read_flash",
            hex(TEST_PARTITION_ADDRESS),
            hex(TEST_PARTITION_SIZE),
            str(partition),
        ),
        timeout=45,
        code="BASELINE_PARTITION_READ_FAILED",
    )
    require(
        partition.is_file() and not partition.is_symlink(),
        "BASELINE_PARTITION_OUTPUT_INVALID",
    )
    require(
        partition.stat().st_size == TEST_PARTITION_SIZE,
        "BASELINE_PARTITION_SIZE_MISMATCH",
    )
    value = {
        "schema": "gh.h3.n2.stage2d9r-successor-board-baseline/1",
        "board_identity_sha256": canonical_sha256(selected.board_binding()),
        "serial_identity_sha256": canonical_sha256(selected.serial_binding()),
        "chip_id_output_sha256": sha256_bytes(chip.stdout.encode("utf-8")),
        "flash_id_output_sha256": sha256_bytes(flash.stdout.encode("utf-8")),
        "test_partition_sha256": sha256_file(partition),
        "test_partition_size": partition.stat().st_size,
    }
    return {
        **value,
        "baseline_state_sha256": canonical_sha256(value),
    }


def claim(marker: Path, authorization: dict[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(
        marker,
        {
            "schema": MARKER_SCHEMA,
            "stage": STAGE,
            "authorization_id": AUTHORIZATION_ID,
            "status": "CLAIMED",
            "authorization_record_sha256": authorization[
                "authorization_record_sha256"
            ],
            "claimed_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
            "private_paths_included": False,
        },
    )


def finish_marker(
    marker: Path,
    *,
    status: str,
    terminal_result_sha256: str,
    failure_code: str | None,
) -> None:
    replace_json(
        marker,
        {
            "schema": MARKER_SCHEMA,
            "stage": STAGE,
            "authorization_id": AUTHORIZATION_ID,
            "status": status,
            "terminal_result_sha256": terminal_result_sha256,
            "failure_code": failure_code,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
            "private_paths_included": False,
        },
    )


def execute(
    *,
    authorization_path: Path,
    marker_path: Path,
    result_output: Path,
    package_sha256: str,
    python_path: Path,
    esptool_path: Path,
    serial_enumerator: Callable[[], list[SerialIdentity]] = enumerate_serial,
    baseline_collector: Callable[[SerialIdentity, Path, Path], dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    require(HEX64.fullmatch(package_sha256) is not None, "PACKAGE_SHA_INVALID")
    authorization = validate_authorization(
        authorization_path,
        package_sha256=package_sha256,
        python_path=python_path,
        esptool_path=esptool_path,
        now=now,
    )
    require(not marker_path.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    require(not result_output.exists(), "RESULT_OUTPUT_ALREADY_EXISTS")

    claim(marker_path, authorization)
    try:
        candidates = serial_enumerator()
        require(len(candidates) == 1, "SERIAL_CANDIDATE_COUNT_NOT_ONE")
        selected = candidates[0]
        require(selected.vid == ESPRESSIF_USB_VID, "SERIAL_VENDOR_MISMATCH")

        collector = baseline_collector or (
            lambda identity, esptool, work: collect_baseline(
                identity, esptool, work
            )
        )
        with tempfile.TemporaryDirectory(
            prefix="stage2d9r-baseline-readonly-"
        ) as td:
            baseline = collector(selected, esptool_path, Path(td))

        for key in (
            "board_identity_sha256",
            "serial_identity_sha256",
            "chip_id_output_sha256",
            "flash_id_output_sha256",
            "test_partition_sha256",
            "baseline_state_sha256",
        ):
            require(
                isinstance(baseline.get(key), str)
                and HEX64.fullmatch(baseline[key]) is not None,
                f"BASELINE_{key.upper()}_INVALID",
            )
        require(
            baseline.get("test_partition_size") == TEST_PARTITION_SIZE,
            "BASELINE_TEST_PARTITION_SIZE_INVALID",
        )

        terminal = {
            "schema": RESULT_SCHEMA,
            "stage": STAGE,
            "d1_decision_id": D1_ID,
            "authorization_id": AUTHORIZATION_ID,
            "status": "CONSUMED_PASS",
            "board_identity_sha256": baseline["board_identity_sha256"],
            "serial_identity_sha256": baseline["serial_identity_sha256"],
            "baseline_state_sha256": baseline["baseline_state_sha256"],
            "chip_id_output_sha256": baseline["chip_id_output_sha256"],
            "flash_id_output_sha256": baseline["flash_id_output_sha256"],
            "test_partition_sha256": baseline["test_partition_sha256"],
            "test_partition_size": TEST_PARTITION_SIZE,
            "allowed_operations_observed": list(ALLOWED_OPERATIONS),
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_write_operation": False,
            "flash_erase_operation": False,
            "flash_write_operation": False,
            "flash_verify_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "secret_values_included": False,
            "private_paths_included": False,
        }
        terminal["result_sha256"] = canonical_sha256(terminal)
        write_json_exclusive(result_output, terminal)
        finish_marker(
            marker_path,
            status="CONSUMED_PASS",
            terminal_result_sha256=terminal["result_sha256"],
            failure_code=None,
        )
        return terminal
    except Exception as exc:
        failure_code = (
            str(exc.args[0])
            if isinstance(exc, BaselineGateError) and exc.args
            else type(exc).__name__
        )
        terminal = {
            "schema": RESULT_SCHEMA,
            "stage": STAGE,
            "d1_decision_id": D1_ID,
            "authorization_id": AUTHORIZATION_ID,
            "status": "CONSUMED_FAILED",
            "failure_code": failure_code,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_write_operation": False,
            "flash_erase_operation": False,
            "flash_write_operation": False,
            "flash_verify_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "secret_values_included": False,
            "private_paths_included": False,
        }
        terminal["result_sha256"] = canonical_sha256(terminal)
        if not result_output.exists():
            write_json_exclusive(result_output, terminal)
        finish_marker(
            marker_path,
            status="CONSUMED_FAILED",
            terminal_result_sha256=terminal["result_sha256"],
            failure_code=failure_code,
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--package-sha256", required=True)
    parser.add_argument("--python", dest="python_executable")
    parser.add_argument("--esptool")
    args = parser.parse_args()

    try:
        python_path = executable(args.python_executable or shutil.which("python3"), "python3")
        esptool_path = executable(args.esptool, "esptool")
        result = execute(
            authorization_path=args.authorization,
            marker_path=args.marker,
            result_output=args.result_output,
            package_sha256=args.package_sha256,
            python_path=python_path,
            esptool_path=esptool_path,
        )
    except Exception as exc:
        code = (
            str(exc.args[0])
            if isinstance(exc, BaselineGateError) and exc.args
            else type(exc).__name__
        )
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "failure_code": code,
                    "authorization_created": False,
                    "automatic_retry_permitted": False,
                },
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": result["status"],
                "result_sha256": result["result_sha256"],
                "board_identity_sha256": result["board_identity_sha256"],
                "serial_identity_sha256": result["serial_identity_sha256"],
                "baseline_state_sha256": result["baseline_state_sha256"],
                "authorization_consumed": True,
                "replay_permitted": False,
                "board_write_operation": False,
                "network_operation": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
