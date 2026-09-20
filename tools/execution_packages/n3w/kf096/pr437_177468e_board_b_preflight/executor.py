from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "n3w.kf096.pr437-177468e.boardb-preflight/1"

PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
PRODUCT_SOURCE_TREE = "a50ff98887b14b70cf9d278c6f8b7edf536eae88"
TARGET_CONFIG = "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
TARGET_BLOB_SHA = "37654481747b21ca51ccecc246bf84ca437ab7a9"

ARTIFACT_ID = 10607030747
ARTIFACT_NAME = "n3w-pr437-boardb-exact-source"
ARTIFACT_ZIP_SHA256 = "371d4369b791df527c595bc43ac203487f18a000b47ec73692d728ce58483dd8"
APPLICATION_SIZE = 1145984
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
MANIFEST_SHA256 = "6b8fa94206440ab1b44839cadc5e38608dfe4c828d1aefb8301bcf095519bd2b"

# Repository-frozen historical Board B public-safe identity reference.
# The 2026-09-19 operator identity override was explicitly non-reusable.
REFERENCE_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"

PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"

MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
ESPTOOL_VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)


class StopExecution(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardware_id_from_mac(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(raw_mac: str) -> str:
    return sha256_bytes(hardware_id_from_mac(raw_mac).encode("utf-8"))


def redacted_command(args: list[str], port: str) -> str:
    return " ".join("<PORT>" if item == port else item for item in args)


def run_capture(args: list[str], *, port: str) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise StopExecution(
            f"command failed rc={proc.returncode}: {redacted_command(args, port)}"
        )
    return output


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_esptool_version(port: str) -> str:
    output = run_capture(esptool_base() + ["version"], port=port)
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("unable to parse esptool version")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("esptool major version must be 5")
    return f"{major}.{minor}.{patch}"


def read_identity(port: str) -> str:
    output = run_capture(
        esptool_base()
        + ["--chip", "esp32c6", "--port", port, "--no-stub", "read-mac"],
        port=port,
    )
    match = MAC_RE.search(output)
    if match is None:
        raise StopExecution("ROM MAC was not observed")
    return public_identity_sha256(match.group(1))


def verify_security(port: str) -> None:
    output = run_capture(
        esptool_base()
        + ["--chip", "esp32c6", "--port", port, "--no-stub", "get-security-info"],
        port=port,
    )
    if "ESP32-C6" not in output.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")
    if SECURE_BOOT_DISABLED_RE.search(output) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(output) is None:
        raise StopExecution("Flash Encryption is not proven disabled")


def verify_flash_size(port: str) -> None:
    output = run_capture(
        esptool_base()
        + ["--chip", "esp32c6", "--port", port, "--no-stub", "flash-id"],
        port=port,
    )
    if FLASH_8MB_RE.search(output) is None:
        raise StopExecution("8MB flash is not proven")


def verify_partition_table(port: str) -> str:
    with tempfile.TemporaryDirectory(prefix="n3w-pr437-177468e-preflight-") as td:
        destination = Path(td) / "partition-table.bin"
        run_capture(
            esptool_base()
            + [
                "--chip",
                "esp32c6",
                "--port",
                port,
                "--no-stub",
                "read-flash",
                hex(PARTITION_TABLE_OFFSET),
                hex(PARTITION_TABLE_SIZE),
                str(destination),
            ],
            port=port,
        )
        if not destination.is_file() or destination.stat().st_size != PARTITION_TABLE_SIZE:
            raise StopExecution("partition table readback size mismatch")
        digest = sha256_file(destination)
        if digest != PARTITION_TABLE_SHA256:
            raise StopExecution("partition table binding mismatch")
        return digest


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def artifact_binding() -> dict[str, object]:
    return {
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "archive_sha256": ARTIFACT_ZIP_SHA256,
        "application_size": APPLICATION_SIZE,
        "application_sha256": APPLICATION_SHA256,
        "otadata_size": OTADATA_SIZE,
        "otadata_sha256": OTADATA_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "product_source_tree": PRODUCT_SOURCE_TREE,
        "target_config": TARGET_CONFIG,
        "target_blob_sha": TARGET_BLOB_SHA,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    port = args.port
    output = Path(args.output)

    payload: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "created_at": utc_now(),
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "artifact": artifact_binding(),
        "read_only": True,
        "rom_esptool_access": True,
        "application_serial_open": False,
        "flash_write": False,
        "product_nvs_write": False,
        "t1_mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "identity_override_permitted": False,
    }

    try:
        if not port.startswith("/dev/cu.usbmodem") or any(ch.isspace() for ch in port):
            raise StopExecution("serial port locator is not an allowed usbmodem path")
        if not os.path.exists(port):
            raise StopExecution("serial port does not exist")

        esptool_version = verify_esptool_version(port)
        identity_hash = read_identity(port)
        payload["esptool_version"] = esptool_version
        payload["observed_hardware_id_sha256"] = identity_hash
        payload["reference_hardware_id_sha256"] = REFERENCE_HARDWARE_ID_SHA256
        payload["automated_identity_match"] = (
            identity_hash == REFERENCE_HARDWARE_ID_SHA256
        )

        if identity_hash != REFERENCE_HARDWARE_ID_SHA256:
            raise StopExecution(
                "connected target does not match repository-frozen Board B identity"
            )

        verify_security(port)
        verify_flash_size(port)
        partition_sha = verify_partition_table(port)

        payload["chip"] = "ESP32-C6"
        payload["flash_size"] = "8MB"
        payload["secure_boot"] = False
        payload["flash_encryption"] = False
        payload["partition_table_offset"] = hex(PARTITION_TABLE_OFFSET)
        payload["partition_table_size"] = PARTITION_TABLE_SIZE
        payload["partition_table_sha256"] = partition_sha
        payload["status"] = "PASS"
        write_json(output, payload)

        print("PREFLIGHT=PASS")
        print(f"HARDWARE_ID_SHA256={identity_hash}")
        print("AUTOMATED_IDENTITY_MATCH=PASS")
        print("CHIP=ESP32-C6")
        print("FLASH_SIZE=8MB")
        print("SECURE_BOOT=false")
        print("FLASH_ENCRYPTION=false")
        print(f"PARTITION_TABLE_SHA256={partition_sha}")
        print(f"ARTIFACT_ID={ARTIFACT_ID}")
        print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
        print("FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("T1_MUTATION=false")
        return 0

    except StopExecution as exc:
        payload["stop_reason"] = str(exc)
        write_json(output, payload)
        print(f"PREFLIGHT=STOP reason={exc}", file=sys.stderr)
        if "observed_hardware_id_sha256" in payload:
            print(
                f"HARDWARE_ID_SHA256={payload['observed_hardware_id_sha256']}",
                file=sys.stderr,
            )
            print(
                "AUTOMATED_IDENTITY_MATCH="
                + ("PASS" if payload.get("automated_identity_match") else "FAIL"),
                file=sys.stderr,
            )
        print("FLASH_WRITE=false", file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
