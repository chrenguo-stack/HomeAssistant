from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

SCHEMA_PREFLIGHT = "n3w.board-d.post-r4-write-target-preflight/2"
MERGED_MAIN = "e24b5af4a271867c613dd52012bc83a6d40b06a5"
PRODUCT_SOURCE = "ec5f6d68e33db7757d91c807fff708ca81b075dc"
PRODUCT_TREE = "16740efa8ad24d423adc0b2de32b99d56e2d23d1"
ARTIFACT_RUN_ID = 39901919230
ARTIFACT_ID = 12478974186
ARTIFACT_NAME = "n3w-board-d-r4-f1rc2-ec5f6d68-exact-source"
GITHUB_ARTIFACT_SHA256 = "898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f"
RELEASE_BUNDLE_NAME = "n3w-board-d-r4-f1rc2-ec5f6d68-exact-source.zip"
RELEASE_BUNDLE_SHA256 = "b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5"
MANIFEST_SHA256 = "173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb"
PARTITION_TABLE_OFFSET = 0x8000
BOOTLOADER_OFFSET = 0x0
EXPECTED_MEMBERS = {
    "MANIFEST.txt",
    "bootloader.bin",
    "firmware.bin",
    "firmware.factory.bin",
    "firmware.ota.bin",
    "flash_args",
    "ota_data_initial.bin",
    "partitions.bin",
}
MEMBER_BINDINGS = {
    "MANIFEST.txt": (2163, "173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb"),
    "bootloader.bin": (22576, "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46"),
    "firmware.bin": (1413616, "ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08"),
    "firmware.factory.bin": (1479152, "c982c5d56f62ddddbba5b4734c1d9f0c36d4ce6996754157b017159ac630e2c6"),
    "firmware.ota.bin": (1413616, "ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"),
    "partitions.bin": (3072, "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"),
}
EXPECTED_MANIFEST = {
    "BINDING_SCHEMA": "N3W_BOARD_D_R4_PRODUCTION_EXACT_ARTIFACT_V2",
    "SOURCE_HEAD": PRODUCT_SOURCE,
    "SOURCE_TREE": PRODUCT_TREE,
    "TARGET_CONFIG": "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml",
    "TARGET_BLOB_SHA": "176ef5a2839ba8d58b4675c5f5097eba5c662236",
    "TELEMETRY_BRIDGE_BLOB_SHA": "ce16f2389d146f9b25e95cbb628547e11ce36bd6",
    "TRANSPORT_BLOB_SHA": "6458c2bb5d52a9050859c75feefcd8f03b49b73c",
    "ACTIVE_CORE_INIT_BLOB_SHA": "5e91cb475eb6a194a1980b0b30ea24180104ab82",
    "ACTIVE_CORE_HEADER_BLOB_SHA": "c231e66a68a3a2f185c58bceddc5add1f4364b43",
    "PRODUCT_COMPONENT_HEADER_BLOB_SHA": "19c7f1557ad14e021c0f208de5963d13e25c2f85",
    "DIAGNOSTICS_STUB_BLOB_SHA": "409696edcd27a4ae23e07e8057c3eabe8bb0fcb5",
    "DIAGNOSTICS_SUPPORT_BLOB_SHA": "05276bea109779adbbe3dab2372e852c0625c617",
    "PHASE4_SUPPORT_BLOB_SHA": "b485e576693ee7d105c44ad31b36dedf91ff41aa",
    "RTC_SUPPORT_BLOB_SHA": "241a7fa7b02d7b78e7f6f78312818c5cc4fdc6cb",
    "BROKER_RELOCATION_BLOB_SHA": "1c3afa2497a624b4026409b3e6bc2085681ae45b",
    "PRODUCT_RUNTIME_BLOB_SHA": "8abf899fc7a1e1e69007fa66be85247c22775187",
    "RADIO_BLOB_SHA": "e6ae3c4512a4d7f171fdcc5e0f2a0a9eb36770f4",
    "PYTHON_VERSION": "3.11",
    "ESPHOME_VERSION": "2026.4.3",
    "ESP_IDF_VERSION": "5.5.4",
    "WORKFLOW_TRIGGER_SHA": "726d5593ab8cf7a46972153f2c30558fea76ecca",
    "WORKFLOW_RUN_ID": str(ARTIFACT_RUN_ID),
    "BINARY_DEHARNESS_PROOF": "PASS",
    "PHASE4_HARNESS_PRESENT": "false",
    "LAB_DIAGNOSTICS_PRESENT": "false",
    "RTC_BREADCRUMB_PRESENT": "false",
    "FIRMWARE_BIN_SIZE": "1413616",
    "FIRMWARE_BIN_SHA256": "ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08",
    "FIRMWARE_OTA_BIN_SIZE": "1413616",
    "FIRMWARE_OTA_BIN_SHA256": "ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08",
    "FIRMWARE_FACTORY_BIN_SIZE": "1479152",
    "FIRMWARE_FACTORY_BIN_SHA256": "c982c5d56f62ddddbba5b4734c1d9f0c36d4ce6996754157b017159ac630e2c6",
    "BOOTLOADER_BIN_SIZE": "22576",
    "BOOTLOADER_BIN_SHA256": "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46",
    "PARTITIONS_BIN_SIZE": "3072",
    "PARTITIONS_BIN_SHA256": "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca",
    "OTA_DATA_INITIAL_BIN_SIZE": "8192",
    "OTA_DATA_INITIAL_BIN_SHA256": "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f",
    "FLASH_ARGS_SIZE": "167",
    "FLASH_ARGS_SHA256": "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713",
}
BASE_MAC_RE = re.compile(r"(?m)^[ \t]*BASE MAC:[ \t]*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})[ \t]*$")
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
        raise StopExecution("invalid base MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(raw_mac: str) -> str:
    return sha256_bytes(hardware_id_from_mac(raw_mac).encode("utf-8"))


def base_mac_from_esptool_output(output: str) -> str:
    matches = BASE_MAC_RE.findall(output)
    if len(matches) != 1:
        raise StopExecution("exactly one ESP32-C6 BASE MAC was not observed")
    return matches[0]


def parse_manifest(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw:
            continue
        if "=" not in raw:
            raise StopExecution("manifest contains a non key=value line")
        key, value = raw.split("=", 1)
        if not key or key in result:
            raise StopExecution("manifest contains invalid or duplicate key")
        result[key] = value
    return result


def validate_release_bundle(archive: Path, extract_root: Path) -> dict[str, Path]:
    if not archive.is_file():
        raise StopExecution("release bundle is missing")
    if sha256_file(archive) != RELEASE_BUNDLE_SHA256:
        raise StopExecution("release bundle SHA256 mismatch")

    with zipfile.ZipFile(archive, "r") as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]
        if set(names) != EXPECTED_MEMBERS or len(names) != len(EXPECTED_MEMBERS):
            raise StopExecution("release member set mismatch")
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                raise StopExecution("release ZIP timestamp is not deterministic")
            if info.compress_type != zipfile.ZIP_STORED:
                raise StopExecution("release ZIP member compression drifted")
            data = zf.read(info.filename)
            expected_size, expected_sha = MEMBER_BINDINGS[info.filename]
            if len(data) != expected_size or sha256_bytes(data) != expected_sha:
                raise StopExecution(f"release member binding mismatch: {info.filename}")
            target = extract_root / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    manifest = extract_root / "MANIFEST.txt"
    if sha256_file(manifest) != MANIFEST_SHA256:
        raise StopExecution("MANIFEST.txt binding mismatch")
    parsed = parse_manifest(manifest.read_text(encoding="utf-8"))
    if parsed != EXPECTED_MANIFEST:
        raise StopExecution("MANIFEST.txt content binding mismatch")

    return {name: extract_root / name for name in EXPECTED_MEMBERS}


def _redacted_command(args: Iterable[str], port: str | None = None) -> str:
    return " ".join("<PORT>" if port is not None and item == port else item for item in args)


def run_capture(args: list[str], *, port: str | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise StopExecution(f"command failed rc={proc.returncode}: {_redacted_command(args, port)}")
    return output


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_esptool_version() -> str:
    output = run_capture(esptool_base() + ["version"])
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("unable to parse esptool version")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("esptool major version must be 5")
    return f"{major}.{minor}.{patch}"


def verify_image(path: Path) -> None:
    output = run_capture(esptool_base() + ["--chip", "esp32c6", "image-info", str(path)])
    if "ESP32-C6" not in output.upper():
        raise StopExecution(f"image is not identified as ESP32-C6: {path.name}")


def read_flash_region(port: str, offset: int, size: int, destination: Path) -> str:
    command = esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
        "read-flash",
        hex(offset),
        hex(size),
        str(destination),
    ]
    run_capture(command, port=port)
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    return sha256_file(destination)


def classify_write_mode(bootloader_matches: bool, partition_table_matches: bool) -> str:
    if bootloader_matches and partition_table_matches:
        return "APP_PLUS_OTADATA_CANDIDATE"
    return "FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED"


def probe_board(port: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")

    security = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "get-security-info"],
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")
    base_mac = base_mac_from_esptool_output(security)
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption is not proven disabled")

    flash = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "flash-id"],
        port=port,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash is not proven")

    with tempfile.TemporaryDirectory(prefix="n3w-board-d-readback-") as td:
        root = Path(td)
        bootloader_sha = read_flash_region(
            port,
            BOOTLOADER_OFFSET,
            MEMBER_BINDINGS["bootloader.bin"][0],
            root / "bootloader.bin",
        )
        partition_sha = read_flash_region(
            port,
            PARTITION_TABLE_OFFSET,
            MEMBER_BINDINGS["partitions.bin"][0],
            root / "partitions.bin",
        )

    bootloader_matches = bootloader_sha == MEMBER_BINDINGS["bootloader.bin"][1]
    partition_table_matches = partition_sha == MEMBER_BINDINGS["partitions.bin"][1]
    return {
        "hardware_id_sha256": public_identity_sha256(base_mac),
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "bootloader_offset": hex(BOOTLOADER_OFFSET),
        "bootloader_sha256": bootloader_sha,
        "bootloader_matches_release": bootloader_matches,
        "partition_table_offset": hex(PARTITION_TABLE_OFFSET),
        "partition_table_sha256": partition_sha,
        "partition_table_matches_release": partition_table_matches,
        "write_mode_candidate": classify_write_mode(bootloader_matches, partition_table_matches),
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def artifact_binding_payload() -> dict[str, object]:
    return {
        "merged_main": MERGED_MAIN,
        "product_source": PRODUCT_SOURCE,
        "product_tree": PRODUCT_TREE,
        "artifact_run_id": ARTIFACT_RUN_ID,
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "github_artifact_sha256": GITHUB_ARTIFACT_SHA256,
        "release_bundle_name": RELEASE_BUNDLE_NAME,
        "release_bundle_sha256": RELEASE_BUNDLE_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
    }


def run_preflight(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="n3w-board-d-preflight-") as td:
        files = validate_release_bundle(Path(args.release_bundle), Path(td))
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        verify_image(files["firmware.factory.bin"])
        board = probe_board(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "identity_enrollment_status": "OBSERVED_REQUIRES_OPERATOR_BOARD_D_CONFIRMATION",
        "raw_flash_args_direct_execution_allowed": False,
        "persistent_mutation": False,
        "flash_write": False,
        "nvs_write": False,
        "board_reset_may_occur": True,
        "write_command_present": False,
        "write_authorization_granted": False,
        "replay_permitted": False,
    }
    write_json(Path(args.output), payload)
    print("PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print("CHIP=ESP32-C6")
    print("FLASH_SIZE=8MB")
    print("SECURE_BOOT=false")
    print("FLASH_ENCRYPTION=false")
    print(f"BOOTLOADER_MATCHES_RELEASE={str(board['bootloader_matches_release']).lower()}")
    print(f"PARTITION_TABLE_MATCHES_RELEASE={str(board['partition_table_matches_release']).lower()}")
    print(f"WRITE_MODE_CANDIDATE={board['write_mode_candidate']}")
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("PERSISTENT_MUTATION=false")
    print("WRITE_AUTHORIZATION_GRANTED=false")
    print("RAW_FLASH_ARGS_DIRECT_EXECUTION_ALLOWED=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--port", required=True)
    preflight.add_argument("--release-bundle", required=True)
    preflight.add_argument("--output", required=True)
    preflight.set_defaults(func=run_preflight)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
