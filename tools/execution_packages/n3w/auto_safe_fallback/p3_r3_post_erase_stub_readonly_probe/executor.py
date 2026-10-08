from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

GATE = "N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_R3_POST_ERASE_STUB_READONLY_PROBE_20261008_01"
EXPECTED_SILICON_SHA256 = "4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc"
MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)


class StopExecution(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution("COMMAND_TIMEOUT") from error


def save_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def ensure_single_port() -> str:
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if len(ports) != 1:
        raise StopExecution("USB_MODEM_COUNT_NOT_1")
    port = ports[0]
    for _ in range(2):
        proc = run(["lsof", "-t", "--", port], timeout=10)
        if proc.returncode == 0 and (proc.stdout or "").strip():
            raise StopExecution("SERIAL_PORT_BUSY")
        if proc.returncode not in (0, 1):
            raise StopExecution("SERIAL_OWNER_CHECK_FAILED")
        time.sleep(1)
    return port


def verify_esptool() -> str:
    proc = run([sys.executable, "-m", "esptool", "version"], timeout=30)
    if proc.returncode != 0:
        raise StopExecution("ESPTOOL_VERSION_FAILED")
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = VERSION_RE.search(output)
    if match is None:
        raise StopExecution("ESPTOOL_VERSION_UNPARSEABLE")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("ESPTOOL_MAJOR_NOT_5")
    return f"{major}.{minor}.{patch}"


def silicon_sha256(output: str) -> str:
    if "ESP32-C6" not in output.upper():
        raise StopExecution("TARGET_NOT_ESP32_C6")
    match = MAC_RE.search(output)
    if match is None:
        raise StopExecution("ROM_MAC_MISSING")
    compact = match.group(1).replace(":", "").lower()
    return sha256_bytes(("rom-c6-" + compact).encode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-dir",
        default=str(Path.home() / "N3W_PRIVATE_EVIDENCE" / GATE),
    )
    args = parser.parse_args()

    out: dict[str, object] = {
        "STAGE": "P3_R3_POST_ERASE_STUB_READONLY_PROBE",
        "AUTHORIZATION_GRANTED": True,
        "AUTHORIZATION_CLAIMED": False,
        "AUTHORIZATION_CONSUMED": False,
        "BOARD_ACCESS": False,
        "FLASH_ERASE": False,
        "FLASH_WRITE": False,
        "ROM_IDENTITY_PASS": False,
        "STUB_READ_ATTEMPTED": False,
        "POST_ERASE_PARTITION_WINDOW_BLANK": False,
        "READY_FOR_WRITE_ONLY_SUCCESSOR": False,
        "PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED": False,
        "AUTO_WRITE": False,
        "AUTO_P4": False,
        "STOP": True,
    }

    private_dir = Path(args.private_dir).expanduser().resolve()
    if private_dir.exists() or private_dir.is_symlink():
        out["ERROR"] = "PRIVATE_EVIDENCE_DIRECTORY_ALREADY_EXISTS"
        print(json.dumps(out, indent=2, sort_keys=True))
        return 2

    try:
        private_dir.mkdir(parents=True, mode=0o700)
        os.chmod(private_dir, 0o700)

        out["ESPTOOL_VERSION"] = verify_esptool()
        port = ensure_single_port()
        out["SERIAL_PORT_SHA256"] = sha256_bytes(port.encode("utf-8"))

        out["AUTHORIZATION_CLAIMED"] = True
        out["AUTHORIZATION_CONSUMED"] = True
        out["BOARD_ACCESS"] = True

        security = run(
            [
                sys.executable, "-m", "esptool",
                "--chip", "esp32c6",
                "--port", port,
                "--before", "no-reset",
                "--after", "no-reset",
                "--no-stub",
                "get-security-info",
            ],
            timeout=60,
        )
        save_text(private_dir / "security.stdout.txt", security.stdout or "")
        save_text(private_dir / "security.stderr.txt", security.stderr or "")
        if security.returncode != 0:
            raise StopExecution("ROM_SECURITY_INFO_FAILED")

        security_output = (security.stdout or "") + "\n" + (security.stderr or "")
        observed = silicon_sha256(security_output)
        out["SILICON_BINDING_SHA256"] = observed
        if observed != EXPECTED_SILICON_SHA256:
            raise StopExecution("SILICON_BINDING_MISMATCH")
        out["ROM_IDENTITY_PASS"] = True

        destination = private_dir / "post_erase_partition_probe.bin"
        out["STUB_READ_ATTEMPTED"] = True
        read_proc = run(
            [
                sys.executable, "-m", "esptool",
                "--chip", "esp32c6",
                "--port", port,
                "--before", "no-reset",
                "--after", "no-reset",
                "read-flash",
                "0x8000",
                "0x1000",
                str(destination),
            ],
            timeout=180,
        )
        save_text(private_dir / "stub_read.stdout.txt", read_proc.stdout or "")
        save_text(private_dir / "stub_read.stderr.txt", read_proc.stderr or "")

        out["STUB_READ_RETURN_CODE"] = read_proc.returncode
        out["STUB_READ_STDOUT_SHA256"] = sha256_bytes((read_proc.stdout or "").encode("utf-8"))
        out["STUB_READ_STDERR_SHA256"] = sha256_bytes((read_proc.stderr or "").encode("utf-8"))

        if read_proc.returncode != 0:
            raise StopExecution("STUB_POST_ERASE_READ_FAILED")
        if not destination.is_file():
            raise StopExecution("POST_ERASE_PROBE_FILE_MISSING")

        data = destination.read_bytes()
        out["POST_ERASE_PROBE_SIZE"] = len(data)
        out["POST_ERASE_PROBE_SHA256"] = sha256_bytes(data)
        if len(data) != 0x1000:
            raise StopExecution("POST_ERASE_PROBE_SIZE_MISMATCH")
        if any(value != 0xFF for value in data):
            raise StopExecution("POST_ERASE_PARTITION_WINDOW_NOT_BLANK")

        out["POST_ERASE_PARTITION_WINDOW_BLANK"] = True
        out["READY_FOR_WRITE_ONLY_SUCCESSOR"] = True
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    except StopExecution as error:
        out["ERROR"] = str(error)
        print(json.dumps(out, indent=2, sort_keys=True))
        return 2
    except Exception:
        out["ERROR"] = "UNEXPECTED_P3_R3_EXECUTOR_FAILURE"
        print(json.dumps(out, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
