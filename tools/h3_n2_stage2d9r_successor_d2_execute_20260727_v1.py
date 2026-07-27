#!/usr/bin/env python3
"""Exact one-shot Stage2D9R successor physical executor.

This module is inert without a current, exact authorization record. Before an
atomic claim it performs public/package/toolchain and private-metadata checks only.
USB enumeration, serial access, private command reads, esptool, Mosquitto, Flash and
physical NVS operations are strictly post-claim.
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
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable

STAGE = "H3/N2 Stage 2D-9R G3R successor"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-authorization-record/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-public-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-consumed-marker/1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SERIAL_BAUD = 115200
SERIAL_READY_TIMEOUT_S = 45.0
SERIAL_PASS_TIMEOUT_S = 45.0
REBOOT_READY_TIMEOUT_S = 60.0
TEST_PARTITION_ADDRESS = 0x400000
TEST_PARTITION_SIZE = 0x10000
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
IMMUTABLE_ARTIFACT_ID = 8638796771
IMMUTABLE_ARCHIVE_SHA256 = "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8"
IMMUTABLE_PAYLOAD_TAR_SHA256 = "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747"
IMMUTABLE_MERGED_SHA256 = "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf"
RECOVERY_ARTIFACT_ID = 8644594652
RECOVERY_ARCHIVE_SHA256 = "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e"
RECOVERY_PAYLOAD_TAR_SHA256 = "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e"
RECOVERY_DESCRIPTOR_SHA256 = "912e7e2ec4f10cb81836e5a50df1dd5745eae2ba057bd51b1929671fb5872beb"
PRIVATE_PACKAGE_SHA256 = "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb"
PREPARE_COMMAND_SHA256 = "294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f"
VERIFY_COMMAND_SHA256 = "53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
CUSTODY_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02"
)


class ExecutionError(RuntimeError):
    pass


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


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ExecutionError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def regular(path: Path, expected_mode: str, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(mode(path) == expected_mode, code)


def load_json(path: Path, expected_mode: str, code: str) -> dict[str, Any]:
    regular(path, expected_mode, code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code)
    return value


def write_json_exclusive(path: Path, value: object, file_mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, file_mode)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, file_mode)


def replace_json(path: Path, value: object) -> None:
    require(path.is_file() and not path.is_symlink(), "MARKER_INVALID")
    temp = path.with_name(path.name + ".tmp")
    require(not temp.exists(), "MARKER_TEMP_EXISTS")
    write_json_exclusive(temp, value)
    os.replace(temp, path)
    os.chmod(path, 0o600)


def verify_sums(root: Path) -> None:
    sums = root / "SHA256SUMS"
    regular(sums, "0600", "PACKAGE_SUMS_INVALID")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "PACKAGE_SUMS_INVALID")
        digest, name = parts
        require(HEX64.fullmatch(digest) is not None, "PACKAGE_SUMS_INVALID")
        require(name not in expected and "/" not in name and name != "SHA256SUMS",
                "PACKAGE_SUMS_INVALID")
        expected[name] = digest
    observed = {p.name for p in root.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    require(set(expected) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        path = root / name
        regular(path, "0600", "PACKAGE_FILE_INVALID")
        require(sha256_file(path) == digest, "PACKAGE_DIGEST_MISMATCH")


def executable(value: str | None, name: str) -> Path:
    candidate = value or shutil.which(name)
    require(candidate is not None, f"{name.upper()}_UNAVAILABLE")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(path.is_file() and not path.is_symlink() and os.access(path, os.X_OK),
            f"{name.upper()}_INVALID")
    return path


def validate_authorization(
    path: Path,
    *,
    package_root: Path,
    python_path: Path,
    openssl_path: Path,
    esptool_path: Path,
    mosquitto_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    value = load_json(path, "0600", "AUTHORIZATION_RECORD_INVALID")
    require(value.get("schema") == AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(value.get("stage") == STAGE, "AUTHORIZATION_STAGE_MISMATCH")
    require(value.get("d2_request_id") == D2_REQUEST_ID,
            "AUTHORIZATION_ID_MISMATCH")
    require(value.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(value.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_EXPANDED")
    require(value.get("automatic_retry_permitted") is False,
            "AUTHORIZATION_RETRY_EXPANDED")
    issued = utc(value.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require((expires - issued).total_seconds() <= 7200,
            "AUTHORIZATION_WINDOW_EXCEEDS_MAXIMUM")
    without_binding = dict(value)
    observed_binding = without_binding.pop("authorization_record_sha256", None)
    require(observed_binding == canonical_sha256(without_binding),
            "AUTHORIZATION_RECORD_DIGEST_MISMATCH")

    required_exact = {
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "immutable_merged_image_sha256": IMMUTABLE_MERGED_SHA256,
        "recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": RECOVERY_ARCHIVE_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "recovery_descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "prepare_command_sha256": PREPARE_COMMAND_SHA256,
        "verify_command_sha256": VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
        "build_binding": BUILD_BINDING,
        "execution_script_sha256": sha256_file(Path(__file__).resolve(strict=True)),
        "python_executable_sha256": sha256_file(python_path),
        "openssl_executable_sha256": sha256_file(openssl_path),
        "esptool_executable_sha256": sha256_file(esptool_path),
        "mosquitto_executable_sha256": sha256_file(mosquitto_path),
    }
    for key, expected in required_exact.items():
        require(value.get(key) == expected, f"AUTHORIZATION_{key.upper()}_MISMATCH")
    for key in (
        "request_binding_sha256", "execution_package_sha256",
        "execution_launcher_sha256", "execution_marker_name_sha256",
        "board_identity_sha256", "serial_identity_sha256", "baseline_state_sha256",
    ):
        require(isinstance(value.get(key), str) and HEX64.fullmatch(value[key]) is not None,
                f"AUTHORIZATION_{key.upper()}_INVALID")
    require(value.get("prepare_max_count") == 1, "AUTHORIZATION_PREPARE_COUNT_INVALID")
    require(value.get("verify_max_count") == 1, "AUTHORIZATION_VERIFY_COUNT_INVALID")
    require(value.get("locked_recovery_max_count") in (0, 1),
            "AUTHORIZATION_RECOVERY_COUNT_INVALID")
    require(value.get("activate_authorized") is False,
            "AUTHORIZATION_ACTIVATE_EXPANDED")
    require(value.get("cleanup_authorized") is False,
            "AUTHORIZATION_CLEANUP_EXPANDED")
    require(value.get("production_operation_authorized") is False,
            "AUTHORIZATION_PRODUCTION_EXPANDED")
    package_digest = canonical_package_digest(package_root)
    require(value.get("execution_package_sha256") == package_digest,
            "AUTHORIZATION_EXECUTION_PACKAGE_MISMATCH")
    return value


def canonical_package_digest(root: Path) -> str:
    verify_sums(root)
    entries = []
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if path.is_file():
            entries.append({"name": path.name, "sha256": sha256_file(path)})
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": entries,
    })


def validate_public_inputs(immutable_root: Path, recovery_root: Path) -> tuple[Path, Path]:
    require(immutable_root.is_dir() and not immutable_root.is_symlink(),
            "IMMUTABLE_ROOT_INVALID")
    require(recovery_root.is_dir() and not recovery_root.is_symlink(),
            "RECOVERY_ROOT_INVALID")
    immutable_tar = immutable_root / "stage2d9r-g3r-successor-immutable-payload-v1.tar"
    recovery_tar = recovery_root / "stage2d9r-g3r-successor-recovery-payload-v1.tar"
    regular(immutable_tar, "0600", "IMMUTABLE_PAYLOAD_INVALID")
    regular(recovery_tar, "0600", "RECOVERY_PAYLOAD_INVALID")
    require(sha256_file(immutable_tar) == IMMUTABLE_PAYLOAD_TAR_SHA256,
            "IMMUTABLE_PAYLOAD_DIGEST_MISMATCH")
    require(sha256_file(recovery_tar) == RECOVERY_PAYLOAD_TAR_SHA256,
            "RECOVERY_PAYLOAD_DIGEST_MISMATCH")
    merged = immutable_root / "merged-image.bin"
    erased = recovery_root / "test-partition-erased.bin"
    regular(merged, "0600", "IMMUTABLE_MERGED_IMAGE_INVALID")
    regular(erased, "0600", "RECOVERY_ERASED_IMAGE_INVALID")
    require(sha256_file(merged) == IMMUTABLE_MERGED_SHA256,
            "IMMUTABLE_MERGED_IMAGE_DIGEST_MISMATCH")
    require(erased.stat().st_size == TEST_PARTITION_SIZE,
            "RECOVERY_ERASED_IMAGE_SIZE_MISMATCH")
    require(sha256_file(erased) == ERASED_SHA256,
            "RECOVERY_ERASED_IMAGE_DIGEST_MISMATCH")
    return merged, erased


def validate_private_metadata(home: Path) -> Path:
    root = (home / CUSTODY_RELATIVE).resolve(strict=True)
    require(root.is_dir() and not root.is_symlink() and mode(root) == "0700",
            "PRIVATE_CUSTODY_ROOT_INVALID")
    descriptor = load_json(root / "private-custody-descriptor.json", "0600",
                           "PRIVATE_DESCRIPTOR_INVALID")
    require(descriptor.get("private_package_sha256") == PRIVATE_PACKAGE_SHA256,
            "PRIVATE_PACKAGE_DIGEST_MISMATCH")
    materials = descriptor.get("materials")
    require(isinstance(materials, dict), "PRIVATE_MATERIALS_METADATA_INVALID")
    for name in (
        "prepare-command.txt", "verify-command.txt", "mosquitto.stage2d9r.conf",
        "root-ca.cert.pem", "broker.cert.pem", "broker.key.pem",
        "mosquitto.password", "mosquitto.stage2d9r.acl",
    ):
        metadata = materials.get(name)
        require(isinstance(metadata, dict), "PRIVATE_MATERIAL_METADATA_MISSING")
        require(metadata.get("relative_path") == name and metadata.get("mode") == "0600",
                "PRIVATE_MATERIAL_METADATA_INVALID")
        require(isinstance(metadata.get("sha256"), str)
                and HEX64.fullmatch(metadata["sha256"]) is not None,
                "PRIVATE_MATERIAL_METADATA_INVALID")
        regular(root / name, "0600", "PRIVATE_MATERIAL_FILE_INVALID")
    return root


def claim(marker: Path, authorization: dict[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(marker, {
        "schema": MARKER_SCHEMA,
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "status": "CLAIMED",
        "authorization_record_sha256": authorization["authorization_record_sha256"],
        "request_binding_sha256": authorization["request_binding_sha256"],
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
        "private_paths_included": False,
    })


def finish_marker(marker: Path, status: str, terminal_result_sha256: str,
                  failure_code: str | None, recovery_attempted: bool) -> None:
    replace_json(marker, {
        "schema": MARKER_SCHEMA,
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "status": status,
        "terminal_result_sha256": terminal_result_sha256,
        "failure_code": failure_code,
        "recovery_attempted": recovery_attempted,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
        "private_paths_included": False,
    })


def read_private_commands(root: Path) -> tuple[bytes, bytes]:
    prepare = (root / "prepare-command.txt").read_bytes()
    verify = (root / "verify-command.txt").read_bytes()
    require(sha256_bytes(prepare) == PREPARE_COMMAND_SHA256,
            "PREPARE_COMMAND_DIGEST_MISMATCH")
    require(sha256_bytes(verify) == VERIFY_COMMAND_SHA256,
            "VERIFY_COMMAND_DIGEST_MISMATCH")
    require(prepare.count(b"\n") == 1 and prepare.endswith(b"\n"),
            "PREPARE_COMMAND_FORMAT_INVALID")
    require(verify.count(b"\n") == 1 and verify.endswith(b"\n"),
            "VERIFY_COMMAND_FORMAT_INVALID")
    require(prepare.startswith(b"GH2D9R_PREPARE_V1 "),
            "PREPARE_COMMAND_SCHEMA_MISMATCH")
    require(verify.startswith(b"GH2D9R_VERIFY_V1 "),
            "VERIFY_COMMAND_SCHEMA_MISMATCH")
    return prepare, verify


def enumerate_serial() -> list[SerialIdentity]:
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError as exc:
        raise ExecutionError("PYSERIAL_UNAVAILABLE") from exc
    result: list[SerialIdentity] = []
    for port in list_ports.comports():
        if port.vid is None or port.pid is None:
            continue
        text = " ".join(filter(None, [port.manufacturer, port.product, port.description, port.hwid])).lower()
        if not any(token in text for token in ("espressif", "esp32", "usb jtag", "usb serial")):
            continue
        result.append(SerialIdentity(
            device=str(port.device or ""),
            vid=int(port.vid),
            pid=int(port.pid),
            serial_number=str(port.serial_number or ""),
            manufacturer=str(port.manufacturer or ""),
            product=str(port.product or port.description or ""),
            location=str(port.location or ""),
            hwid=str(port.hwid or ""),
        ))
    return result


def select_serial(authorization: dict[str, Any]) -> SerialIdentity:
    candidates = enumerate_serial()
    require(len(candidates) == 1, "SERIAL_CANDIDATE_COUNT_NOT_ONE")
    selected = candidates[0]
    require(canonical_sha256(selected.board_binding())
            == authorization["board_identity_sha256"],
            "BOARD_IDENTITY_MISMATCH")
    require(canonical_sha256(selected.serial_binding())
            == authorization["serial_identity_sha256"],
            "SERIAL_IDENTITY_MISMATCH")
    return selected


def run_process(command: list[str], *, timeout: float, code: str,
                capture: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    require(completed.returncode == 0, code)
    return completed


def esptool_command(esptool_path: Path, port: str, *args: str) -> list[str]:
    return [str(esptool_path), "--chip", "esp32c6", "--port", port, *args]


def baseline(selected: SerialIdentity, esptool_path: Path, work: Path,
             authorization: dict[str, Any]) -> dict[str, Any]:
    chip = run_process(
        esptool_command(esptool_path, selected.device, "chip_id"),
        timeout=30, code="BASELINE_CHIP_ID_FAILED",
    )
    flash = run_process(
        esptool_command(esptool_path, selected.device, "flash_id"),
        timeout=30, code="BASELINE_FLASH_ID_FAILED",
    )
    partition = work / "baseline-test-partition.bin"
    run_process(
        esptool_command(
            esptool_path, selected.device, "read_flash",
            hex(TEST_PARTITION_ADDRESS), hex(TEST_PARTITION_SIZE), str(partition),
        ),
        timeout=45, code="BASELINE_PARTITION_READ_FAILED",
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
    require(canonical_sha256(value) == authorization["baseline_state_sha256"],
            "BASELINE_STATE_MISMATCH")
    return value


def flash_firmware(selected: SerialIdentity, esptool_path: Path,
                   merged: Path) -> None:
    run_process(
        esptool_command(esptool_path, selected.device,
                        "--before", "default_reset", "--after", "no_reset",
                        "erase_flash"),
        timeout=90, code="FLASH_ERASE_FAILED",
    )
    run_process(
        esptool_command(esptool_path, selected.device,
                        "--before", "default_reset", "--after", "no_reset",
                        "write_flash", "0x0", str(merged)),
        timeout=120, code="FLASH_WRITE_FAILED",
    )
    run_process(
        esptool_command(esptool_path, selected.device,
                        "--before", "default_reset", "--after", "hard_reset",
                        "verify_flash", "0x0", str(merged)),
        timeout=120, code="FLASH_VERIFY_FAILED",
    )


def wait_serial_line(device: str, expected: bytes, timeout: float,
                     command: bytes | None, log_path: Path) -> bytes:
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise ExecutionError("PYSERIAL_UNAVAILABLE") from exc
    deadline = time.monotonic() + timeout
    captured = bytearray()
    sent = False
    with serial.Serial(device, SERIAL_BAUD, timeout=0.1, write_timeout=2) as handle:
        while time.monotonic() < deadline:
            chunk = handle.read(4096)
            if chunk:
                captured.extend(chunk)
                if expected in captured:
                    if command is not None and not sent:
                        handle.write(command)
                        handle.flush()
                        sent = True
                    elif command is None:
                        break
            if command is not None and sent:
                if b"stage2d9r_prepare=pass" in captured or b"stage2d9r_verify=pass" in captured:
                    break
                if b"stage2d9r_executor=fail" in captured:
                    raise ExecutionError("DEVICE_EXECUTOR_FAILED")
        else:
            raise ExecutionError("SERIAL_EXPECTED_MARKER_TIMEOUT")
    log_path.write_bytes(bytes(captured))
    os.chmod(log_path, 0o600)
    return bytes(captured)


def start_broker(mosquitto_path: Path, private_root: Path,
                 log_path: Path) -> subprocess.Popen[bytes]:
    config = private_root / "mosquitto.stage2d9r.conf"
    regular(config, "0600", "BROKER_CONFIG_INVALID")
    log_handle = log_path.open("wb")
    os.chmod(log_path, 0o600)
    process = subprocess.Popen(
        [str(mosquitto_path), "-c", str(config), "-v"],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    setattr(process, "_stage2d9r_log_handle", log_handle)
    time.sleep(1.5)
    require(process.poll() is None, "ISOLATED_BROKER_START_FAILED")
    return process


def stop_broker(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    handle = getattr(process, "_stage2d9r_log_handle", None)
    if handle is not None:
        handle.close()


def locked_recovery(selected: SerialIdentity, esptool_path: Path,
                    erased: Path, work: Path) -> bool:
    run_process(
        esptool_command(esptool_path, selected.device,
                        "--before", "default_reset", "--after", "no_reset",
                        "write_flash", hex(TEST_PARTITION_ADDRESS), str(erased)),
        timeout=60, code="LOCKED_RECOVERY_WRITE_FAILED",
    )
    readback = work / "locked-recovery-readback.bin"
    run_process(
        esptool_command(esptool_path, selected.device,
                        "--before", "default_reset", "--after", "hard_reset",
                        "read_flash", hex(TEST_PARTITION_ADDRESS),
                        hex(TEST_PARTITION_SIZE), str(readback)),
        timeout=60, code="LOCKED_RECOVERY_READBACK_FAILED",
    )
    require(sha256_file(readback) == ERASED_SHA256,
            "LOCKED_RECOVERY_READBACK_DIGEST_MISMATCH")
    return True


def result_object(*, authorization: dict[str, Any], status: str,
                  terminal_state: str, failure_code: str | None,
                  baseline_value: dict[str, Any] | None,
                  flash_sha256: str | None,
                  prepare_log: Path | None,
                  verify_log: Path | None,
                  broker_log: Path | None,
                  recovery_attempted: bool,
                  recovery_succeeded: bool) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "status": status,
        "terminal_state": terminal_state,
        "failure_code": failure_code,
        "request_binding_sha256": authorization["request_binding_sha256"],
        "authorization_record_sha256": authorization["authorization_record_sha256"],
        "source_sha": authorization["source_sha"],
        "main_sha": authorization["main_sha"],
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
        "recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": RECOVERY_ARCHIVE_SHA256,
        "board_identity_sha256": authorization["board_identity_sha256"],
        "serial_identity_sha256": authorization["serial_identity_sha256"],
        "baseline_state_sha256": authorization["baseline_state_sha256"],
        "observed_baseline_sha256": (
            canonical_sha256(baseline_value) if baseline_value is not None else None
        ),
        "flash_sha256": flash_sha256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "prepare_result_sha256": (
            sha256_file(prepare_log) if prepare_log is not None and prepare_log.exists() else None
        ),
        "verify_result_sha256": (
            sha256_file(verify_log) if verify_log is not None and verify_log.exists() else None
        ),
        "broker_log_sha256": (
            sha256_file(broker_log) if broker_log is not None and broker_log.exists() else None
        ),
        "recovery_attempted": recovery_attempted,
        "recovery_succeeded": recovery_succeeded,
        "prepare_count": 1 if prepare_log is not None and prepare_log.exists() else 0,
        "verify_count": 1 if verify_log is not None and verify_log.exists() else 0,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    value["terminal_result_sha256"] = canonical_sha256(value)
    return value


def execute(args: argparse.Namespace) -> dict[str, Any]:
    package_root = args.package_root.expanduser().resolve(strict=True)
    immutable_root = args.immutable_root.expanduser().resolve(strict=True)
    recovery_root = args.recovery_root.expanduser().resolve(strict=True)
    home = args.home.expanduser().resolve(strict=True)
    state_root = args.state_root.expanduser().resolve(strict=False)
    result_path = args.result_output.expanduser().resolve(strict=False)
    require(package_root.is_dir() and not package_root.is_symlink(),
            "EXECUTION_PACKAGE_ROOT_INVALID")
    verify_sums(package_root)
    python_path = Path(sys.executable).resolve(strict=True)
    openssl_path = executable(args.openssl, "openssl")
    esptool_path = executable(args.esptool, "esptool")
    mosquitto_path = executable(args.mosquitto, "mosquitto")
    merged, erased = validate_public_inputs(immutable_root, recovery_root)
    private_root = validate_private_metadata(home)
    authorization = validate_authorization(
        args.authorization_record.expanduser().resolve(strict=True),
        package_root=package_root,
        python_path=python_path,
        openssl_path=openssl_path,
        esptool_path=esptool_path,
        mosquitto_path=mosquitto_path,
    )
    marker_name = sha256_bytes(D2_REQUEST_ID.encode("utf-8")) + ".json"
    require(sha256_bytes(marker_name.encode("utf-8"))
            == authorization["execution_marker_name_sha256"],
            "EXECUTION_MARKER_NAME_MISMATCH")
    marker = state_root / marker_name
    claim(marker, authorization)

    destructive = False
    selected: SerialIdentity | None = None
    baseline_value: dict[str, Any] | None = None
    broker: subprocess.Popen[bytes] | None = None
    recovery_attempted = False
    recovery_succeeded = False
    failure_code: str | None = None
    with tempfile.TemporaryDirectory(prefix="stage2d9r-successor-d2-") as td:
        work = Path(td)
        os.chmod(work, 0o700)
        prepare_log = work / "prepare.log"
        verify_log = work / "verify.log"
        broker_log = work / "broker.log"
        try:
            prepare_command, verify_command = read_private_commands(private_root)
            selected = select_serial(authorization)
            baseline_value = baseline(selected, esptool_path, work, authorization)
            destructive = True
            flash_firmware(selected, esptool_path, merged)
            broker = start_broker(mosquitto_path, private_root, broker_log)
            initial = wait_serial_line(
                selected.device,
                b"stage2d9r_command_ready=PREPARE",
                SERIAL_READY_TIMEOUT_S,
                prepare_command,
                prepare_log,
            )
            require(b"stage2d9r_prepare=pass" in initial, "PREPARE_PASS_NOT_OBSERVED")
            time.sleep(2.0)
            selected_after = select_serial(authorization)
            verified = wait_serial_line(
                selected_after.device,
                b"stage2d9r_command_ready=VERIFY",
                REBOOT_READY_TIMEOUT_S,
                verify_command,
                verify_log,
            )
            require(b"stage2d9r_verify=pass" in verified, "VERIFY_PASS_NOT_OBSERVED")
            stop_broker(broker)
            broker = None
            result = result_object(
                authorization=authorization,
                status="CONSUMED_PASS",
                terminal_state="PREPARED_VERIFIED",
                failure_code=None,
                baseline_value=baseline_value,
                flash_sha256=sha256_file(merged),
                prepare_log=prepare_log,
                verify_log=verify_log,
                broker_log=broker_log,
                recovery_attempted=False,
                recovery_succeeded=False,
            )
            write_json_exclusive(result_path, result)
            finish_marker(marker, "CONSUMED_PASS", result["terminal_result_sha256"],
                          None, False)
            return result
        except Exception as exc:
            failure_code = (
                exc.args[0]
                if isinstance(exc, ExecutionError) and exc.args
                else type(exc).__name__
            )
            stop_broker(broker)
            broker = None
            if (
                destructive
                and selected is not None
                and authorization.get("locked_recovery_max_count") == 1
                and authorization.get("locked_recovery_authorized") is True
            ):
                recovery_attempted = True
                try:
                    recovery_succeeded = locked_recovery(
                        selected, esptool_path, erased, work
                    )
                except Exception:
                    recovery_succeeded = False
            result = result_object(
                authorization=authorization,
                status="CONSUMED_FAILED",
                terminal_state="LOCKED_RECOVERY_COMPLETED" if recovery_succeeded
                else "CONSUMED_FAILED",
                failure_code=str(failure_code),
                baseline_value=baseline_value,
                flash_sha256=sha256_file(merged) if destructive else None,
                prepare_log=prepare_log if prepare_log.exists() else None,
                verify_log=verify_log if verify_log.exists() else None,
                broker_log=broker_log if broker_log.exists() else None,
                recovery_attempted=recovery_attempted,
                recovery_succeeded=recovery_succeeded,
            )
            write_json_exclusive(result_path, result)
            finish_marker(marker, "CONSUMED_FAILED", result["terminal_result_sha256"],
                          str(failure_code), recovery_attempted)
            raise ExecutionError(str(failure_code)) from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--package-root", type=Path, required=True)
    result.add_argument("--authorization-record", type=Path, required=True)
    result.add_argument("--immutable-root", type=Path, required=True)
    result.add_argument("--recovery-root", type=Path, required=True)
    result.add_argument("--home", type=Path, default=Path.home())
    result.add_argument(
        "--state-root",
        type=Path,
        default=Path.home() / ".local/state/greenhouse-stage2d9r/d2-authorizations",
    )
    result.add_argument("--result-output", type=Path, required=True)
    result.add_argument("--openssl")
    result.add_argument("--esptool")
    result.add_argument("--mosquitto")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ExecutionError) and exc.args else type(exc).__name__
        print(json.dumps({
            "status": "FAIL",
            "failure_code": str(code),
            "d2_request_id": D2_REQUEST_ID,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "d2_request_id": D2_REQUEST_ID,
        "terminal_result_sha256": result["terminal_result_sha256"],
        "replay_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
