from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

SCHEMA_PREFLIGHT = "n3w.production.gwsel-v1.three-board-write-preflight/1"
SCHEMA_WRITE = "n3w.production.gwsel-v1.three-board-write/1"

PRODUCT_SOURCE = "8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c"
PRODUCT_TREE = "e9c0216c4a25e99038ff81e54036455cb32b4181"
TARGET_CONFIG = "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
TARGET_BLOB = "32a2b3cb29be4e1bce46807d8825b6a4c37999ec"
TELEMETRY_BRIDGE_BLOB = "ce16f2389d146f9b25e95cbb628547e11ce36bd6"
TRANSPORT_BLOB = "aa39d4b083f2db1b30a76efb1afef156db355a35"
PRODUCT_CORE_INIT_BLOB = "7e86aa2f3fb1bff6f5813e431da501970263e33a"
WORKFLOW_TRIGGER_SHA = "4e662a67ed24b258a4c17ace4e08fb370f06f26e"
WORKFLOW_RUN_ID = 35727909715

ARTIFACT_ID = 10693728323
ARTIFACT_NAME = "n3w-production-gwsel-v1-r2-8c445f2-exact-source"
ARTIFACT_ZIP_SIZE = 4281423
ARTIFACT_ZIP_SHA256 = "e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814"

RELEASE_BUNDLE = "n3w-production-gwsel-v1-r2-8c445f2-exact-source.zip"
RELEASE_BUNDLE_SIZE = 4280881
RELEASE_BUNDLE_SHA256 = "f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598"
RELEASE_SIDECAR = RELEASE_BUNDLE + ".sha256"

EXPECTED_OUTER_MEMBERS = {RELEASE_BUNDLE, RELEASE_SIDECAR}
EXPECTED_RELEASE_MEMBERS = {
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
    "MANIFEST.txt": (1592, "eefa4580940302094d74e5e6228e82c683ba9b2a4c3c5e5b8d59fbee5ad0851e"),
    "bootloader.bin": (22576, "de9616925b2a868feb7c616762d9173899e5b947d0de5da7117268872c8297d1"),
    "firmware.bin": (1392960, "c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a"),
    "firmware.factory.bin": (1458496, "d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304"),
    "firmware.ota.bin": (1392960, "c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"),
    "partitions.bin": (3072, "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"),
}

EXPECTED_MANIFEST = {
    "BINDING_SCHEMA": "N3W_PRODUCTION_EXACT_ARTIFACT_V1",
    "SOURCE_HEAD": PRODUCT_SOURCE,
    "SOURCE_TREE": PRODUCT_TREE,
    "TARGET_CONFIG": TARGET_CONFIG,
    "TARGET_BLOB_SHA": TARGET_BLOB,
    "TELEMETRY_BRIDGE_BLOB_SHA": TELEMETRY_BRIDGE_BLOB,
    "TRANSPORT_BLOB_SHA": TRANSPORT_BLOB,
    "PRODUCT_CORE_INIT_BLOB_SHA": PRODUCT_CORE_INIT_BLOB,
    "PYTHON_VERSION": "3.11",
    "ESPHOME_VERSION": "2026.4.3",
    "ESP_IDF_VERSION": "5.5.4",
    "WORKFLOW_TRIGGER_SHA": WORKFLOW_TRIGGER_SHA,
    "WORKFLOW_RUN_ID": str(WORKFLOW_RUN_ID),
    "BINARY_DEHARNESS_PROOF": "PASS",
    "GATEWAY_SELECTION_R2_LINK_PROOF": "PASS",
    "PHASE4_HARNESS_PRESENT": "false",
    "LAB_DIAGNOSTICS_PRESENT": "false",
    "RTC_BREADCRUMB_PRESENT": "false",
    "FIRMWARE_BIN_SIZE": str(MEMBER_BINDINGS["firmware.bin"][0]),
    "FIRMWARE_BIN_SHA256": MEMBER_BINDINGS["firmware.bin"][1],
    "FIRMWARE_OTA_BIN_SIZE": str(MEMBER_BINDINGS["firmware.ota.bin"][0]),
    "FIRMWARE_OTA_BIN_SHA256": MEMBER_BINDINGS["firmware.ota.bin"][1],
    "FIRMWARE_FACTORY_BIN_SIZE": str(MEMBER_BINDINGS["firmware.factory.bin"][0]),
    "FIRMWARE_FACTORY_BIN_SHA256": MEMBER_BINDINGS["firmware.factory.bin"][1],
    "BOOTLOADER_BIN_SIZE": str(MEMBER_BINDINGS["bootloader.bin"][0]),
    "BOOTLOADER_BIN_SHA256": MEMBER_BINDINGS["bootloader.bin"][1],
    "PARTITIONS_BIN_SIZE": str(MEMBER_BINDINGS["partitions.bin"][0]),
    "PARTITIONS_BIN_SHA256": MEMBER_BINDINGS["partitions.bin"][1],
    "OTA_DATA_INITIAL_BIN_SIZE": str(MEMBER_BINDINGS["ota_data_initial.bin"][0]),
    "OTA_DATA_INITIAL_BIN_SHA256": MEMBER_BINDINGS["ota_data_initial.bin"][1],
    "FLASH_ARGS_SIZE": str(MEMBER_BINDINGS["flash_args"][0]),
    "FLASH_ARGS_SHA256": MEMBER_BINDINGS["flash_args"][1],
}

EXPECTED_FLASH_ARGS = (
    "--flash_mode dio --flash_freq 80m --flash_size 8MB\n"
    "0x0 bootloader/bootloader.bin\n"
    "0x10000 gh.bin\n"
    "0x8000 partition_table/partition-table.bin\n"
    "0x9000 ota_data_initial.bin\n"
)

PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = MEMBER_BINDINGS["partitions.bin"][1]
OTADATA_OFFSET = 0x9000
OTADATA_SIZE = 0x2000
OTADATA_SECTOR_SIZE = 0x1000
APPLICATION_OFFSET = 0x10000
APPLICATION_SIZE = MEMBER_BINDINGS["firmware.bin"][0]
APPLICATION_SHA256 = MEMBER_BINDINGS["firmware.bin"][1]

OTADATA_INITIAL_SHA256 = MEMBER_BINDINGS["ota_data_initial.bin"][1]
OTADATA_POSTRESET_RUNTIME_SHA256 = (
    "8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3"
)
OTADATA_POSTRESET_OTA_SEQ = 1
OTADATA_POSTRESET_STATE_VALID = 2
OTADATA_POSTRESET_CRC = 0x4743989A

# Backward-compatible artifact-image name.  Post-reset readback must use the
# runtime contract above because the bootloader legitimately materializes OTA0.
OTADATA_SHA256 = OTADATA_INITIAL_SHA256

EXPECTED_PARTITIONS = (
    ("otadata", 0x01, 0x00, 0x9000, 0x2000, 0),
    ("phy_init", 0x01, 0x01, 0xB000, 0x1000, 0),
    ("app0", 0x00, 0x10, 0x10000, 0x3C0000, 0),
    ("app1", 0x00, 0x11, 0x3D0000, 0x3C0000, 0),
    ("nvs", 0x01, 0x02, 0x790000, 0x70000, 0),
)

BOARD_PROFILES = {
    "A": {
        "hardware_id_sha256": "f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb",
        "target_confirmation": "BOARD_A_CONNECTED_FOR_GWSEL_V1_EXACT_WRITE_PREFLIGHT",
        "write_confirmation": "GWSEL_V1_BOARD_A_EXACT_WRITE_AUTHORIZED",
    },
    "B": {
        "hardware_id_sha256": "cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0",
        "target_confirmation": "BOARD_B_CONNECTED_FOR_GWSEL_V1_EXACT_WRITE_PREFLIGHT",
        "write_confirmation": "GWSEL_V1_BOARD_B_EXACT_WRITE_AUTHORIZED",
    },
    "C": {
        "hardware_id_sha256": "d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2",
        "target_confirmation": "BOARD_C_CONNECTED_FOR_GWSEL_V1_EXACT_WRITE_PREFLIGHT",
        "write_confirmation": "GWSEL_V1_BOARD_C_EXACT_WRITE_AUTHORIZED",
    },
}

PREFLIGHT_MAX_AGE_SECONDS = 900

BASE_MAC_RE = re.compile(r"\bBASE MAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b", re.I)
EUI64_MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){7})\b", re.I)
MAC48_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b", re.I)
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


def canonical_base_mac(security_output: str) -> str:
    direct = BASE_MAC_RE.search(security_output)
    if direct is not None:
        return direct.group(1).lower()

    extended = EUI64_MAC_RE.search(security_output)
    if extended is not None:
        parts = extended.group(1).lower().split(":")
        if parts[3:5] != ["ff", "fe"]:
            raise StopExecution("unsupported ESP32-C6 EUI-64 format")
        return ":".join(parts[:3] + parts[5:])

    legacy = MAC48_RE.search(security_output)
    if legacy is not None:
        return legacy.group(1).lower()

    raise StopExecution("ROM base MAC was not observed")


def hardware_id_from_mac(base_mac: str) -> str:
    compact = base_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid base MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(base_mac: str) -> str:
    return sha256_bytes(hardware_id_from_mac(base_mac).encode("utf-8"))


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


def parse_partition_table(data: bytes) -> tuple[tuple[str, int, int, int, int, int], ...]:
    entries: list[tuple[str, int, int, int, int, int]] = []
    if len(data) != PARTITION_TABLE_SIZE:
        raise StopExecution("partition table size mismatch")

    for offset in range(0, len(data), 32):
        entry = data[offset : offset + 32]
        if len(entry) != 32:
            raise StopExecution("truncated partition table entry")

        magic = struct.unpack_from("<H", entry, 0)[0]
        if magic == 0x50AA:
            part_type = entry[2]
            subtype = entry[3]
            part_offset, part_size = struct.unpack_from("<II", entry, 4)
            label = entry[12:28].split(b"\0", 1)[0].decode("ascii")
            flags = struct.unpack_from("<I", entry, 28)[0]
            entries.append((label, part_type, subtype, part_offset, part_size, flags))
            continue

        if entry[:2] == b"\xeb\xeb" or entry == b"\xff" * 32:
            break

        raise StopExecution("unsupported partition table entry")

    return tuple(entries)


def validate_postreset_otadata(data: bytes) -> dict[str, object]:
    """Validate the deterministic OTA0 runtime state after the write hard-reset.

    The exact artifact writes an all-0xFF ota_data_initial.bin.  This product has
    OTA app slots but no factory app partition, so ESP-IDF's bootloader selects
    OTA0 on the first boot and persists a valid ota_seq=1 record before the
    executor performs its post-write readback.
    """
    if len(data) != OTADATA_SIZE:
        raise StopExecution("post-reset OTA-data size mismatch")

    ota_seq = struct.unpack_from("<I", data, 0)[0]
    seq_label = data[4:24]
    ota_state = struct.unpack_from("<I", data, 24)[0]
    crc = struct.unpack_from("<I", data, 28)[0]
    digest = sha256_bytes(data)

    if ota_seq != OTADATA_POSTRESET_OTA_SEQ:
        raise StopExecution("post-reset OTA-data ota_seq mismatch")
    if seq_label != b"\xff" * 20:
        raise StopExecution("post-reset OTA-data seq_label mismatch")
    if ota_state != OTADATA_POSTRESET_STATE_VALID:
        raise StopExecution("post-reset OTA-data state is not VALID")
    if crc != OTADATA_POSTRESET_CRC:
        raise StopExecution("post-reset OTA-data CRC mismatch")
    if data[32:OTADATA_SECTOR_SIZE] != b"\xff" * (OTADATA_SECTOR_SIZE - 32):
        raise StopExecution("post-reset OTA-data first sector tail mismatch")
    if data[OTADATA_SECTOR_SIZE:OTADATA_SIZE] != b"\xff" * OTADATA_SECTOR_SIZE:
        raise StopExecution("post-reset OTA-data second sector is not initial")
    if digest != OTADATA_POSTRESET_RUNTIME_SHA256:
        raise StopExecution("post-reset OTA-data runtime SHA256 mismatch")

    return {
        "sha256": digest,
        "ota_seq": ota_seq,
        "ota_state": "VALID",
        "ota_state_raw": ota_state,
        "crc": f"0x{crc:08x}",
    }


def _safe_exact_members(zf: zipfile.ZipFile, expected: set[str], label: str) -> None:
    members = {name for name in zf.namelist() if not name.endswith("/")}
    if members != expected:
        raise StopExecution(f"{label} member set mismatch")
    if any(Path(name).name != name for name in members):
        raise StopExecution(f"{label} contains non-flat member path")


def validate_write_route(files: dict[str, Path]) -> None:
    partitions = files["partition_table"].read_bytes()
    if parse_partition_table(partitions) != EXPECTED_PARTITIONS:
        raise StopExecution("partition layout does not match frozen write route")

    if OTADATA_SIZE != next(item[4] for item in EXPECTED_PARTITIONS if item[0] == "otadata"):
        raise StopExecution("OTA-data image size does not match OTA-data partition")

    app0 = next(item for item in EXPECTED_PARTITIONS if item[0] == "app0")
    if app0[3] != APPLICATION_OFFSET or APPLICATION_SIZE > app0[4]:
        raise StopExecution("application image does not fit frozen app0 route")

    if files["flash_args"].read_text(encoding="utf-8") != EXPECTED_FLASH_ARGS:
        raise StopExecution("flash_args content binding mismatch")

    app = files["application"].read_bytes()
    ota_app = files["ota_application"].read_bytes()
    if app != ota_app:
        raise StopExecution("firmware.bin and firmware.ota.bin differ")

    factory = files["factory"].read_bytes()
    checks = (
        (0x0, files["bootloader"].read_bytes(), "bootloader"),
        (PARTITION_TABLE_OFFSET, partitions, "partition table"),
        (OTADATA_OFFSET, files["otadata"].read_bytes(), "OTA-data"),
        (APPLICATION_OFFSET, app, "application"),
    )
    for offset, expected, label in checks:
        if factory[offset : offset + len(expected)] != expected:
            raise StopExecution(f"factory image does not embed exact {label} bytes")

    if len(factory) != APPLICATION_OFFSET + len(app):
        raise StopExecution("factory image extent does not match application end")


def validate_artifact(archive: Path, extract_root: Path) -> dict[str, Path]:
    if not archive.is_file():
        raise StopExecution("GitHub artifact ZIP is missing")
    if archive.stat().st_size != ARTIFACT_ZIP_SIZE:
        raise StopExecution("GitHub artifact ZIP size mismatch")
    if sha256_file(archive) != ARTIFACT_ZIP_SHA256:
        raise StopExecution("GitHub artifact ZIP SHA256 mismatch")

    release_path = extract_root / RELEASE_BUNDLE
    with zipfile.ZipFile(archive, "r") as outer:
        _safe_exact_members(outer, EXPECTED_OUTER_MEMBERS, "GitHub artifact")
        release_bytes = outer.read(RELEASE_BUNDLE)
        sidecar = outer.read(RELEASE_SIDECAR).decode("utf-8")

    if len(release_bytes) != RELEASE_BUNDLE_SIZE:
        raise StopExecution("release bundle size mismatch")
    if sha256_bytes(release_bytes) != RELEASE_BUNDLE_SHA256:
        raise StopExecution("release bundle SHA256 mismatch")

    if sidecar != f"{RELEASE_BUNDLE_SHA256}  {RELEASE_BUNDLE}\n":
        raise StopExecution("release SHA256 sidecar mismatch")

    release_path.write_bytes(release_bytes)

    with zipfile.ZipFile(release_path, "r") as inner:
        _safe_exact_members(inner, EXPECTED_RELEASE_MEMBERS, "release bundle")
        for name, (expected_size, expected_sha) in MEMBER_BINDINGS.items():
            data = inner.read(name)
            if len(data) != expected_size:
                raise StopExecution(f"{name} size mismatch")
            if sha256_bytes(data) != expected_sha:
                raise StopExecution(f"{name} SHA256 mismatch")
            (extract_root / name).write_bytes(data)

    manifest = extract_root / "MANIFEST.txt"
    if parse_manifest(manifest.read_text(encoding="utf-8")) != EXPECTED_MANIFEST:
        raise StopExecution("MANIFEST.txt content binding mismatch")

    files = {
        "release_bundle": release_path,
        "manifest": manifest,
        "bootloader": extract_root / "bootloader.bin",
        "application": extract_root / "firmware.bin",
        "factory": extract_root / "firmware.factory.bin",
        "ota_application": extract_root / "firmware.ota.bin",
        "flash_args": extract_root / "flash_args",
        "otadata": extract_root / "ota_data_initial.bin",
        "partition_table": extract_root / "partitions.bin",
    }
    validate_write_route(files)
    return files


def _redacted_command(args: Iterable[str], port: str | None = None) -> str:
    items = ["<PORT>" if port is not None and item == port else item for item in args]
    return " ".join(items)


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


def verify_application_image(application: Path) -> None:
    output = run_capture(
        esptool_base() + ["--chip", "esp32c6", "image-info", str(application)]
    )
    normalized = output.upper().replace("_", "-")
    if "ESP32-C6" not in normalized:
        raise StopExecution("firmware.bin is not identified as ESP32-C6 image")


def _rom_command(port: str, command: list[str]) -> list[str]:
    return esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
        *command,
    ]


def read_flash_region(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        _rom_command(
            port,
            ["read-flash", hex(offset), hex(size), str(destination)],
        ),
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    return sha256_file(destination)


def board_profile(board_label: str) -> dict[str, str]:
    try:
        return BOARD_PROFILES[board_label]
    except KeyError as exc:
        raise StopExecution("unsupported board label") from exc


def probe_board(port: str, board_label: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")

    profile = board_profile(board_label)

    security = run_capture(
        _rom_command(port, ["get-security-info"]),
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")

    base_mac = canonical_base_mac(security)
    identity_hash = public_identity_sha256(base_mac)
    if identity_hash != profile["hardware_id_sha256"]:
        raise StopExecution(f"connected target does not match frozen Board {board_label} identity")

    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption is not proven disabled")

    flash = run_capture(
        _rom_command(port, ["flash-id"]),
        port=port,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash is not proven")

    with tempfile.TemporaryDirectory(prefix=f"n3w-gwsel-v1-board-{board_label.lower()}-fresh-") as td:
        root = Path(td)
        partition = root / "partition-table.bin"
        current_otadata = root / "current-otadata.bin"

        partition_sha = read_flash_region(
            port,
            PARTITION_TABLE_OFFSET,
            PARTITION_TABLE_SIZE,
            partition,
        )
        if partition_sha != PARTITION_TABLE_SHA256:
            raise StopExecution("partition table binding mismatch")

        current_otadata_sha = read_flash_region(
            port,
            OTADATA_OFFSET,
            OTADATA_SIZE,
            current_otadata,
        )

    return {
        "operator_board_label": board_label,
        "hardware_id_sha256": identity_hash,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(PARTITION_TABLE_OFFSET),
        "partition_table_size": PARTITION_TABLE_SIZE,
        "partition_table_sha256": partition_sha,
        "current_otadata_sha256": current_otadata_sha,
    }


def artifact_binding_payload() -> dict[str, object]:
    return {
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "github_artifact_size": ARTIFACT_ZIP_SIZE,
        "github_artifact_sha256": ARTIFACT_ZIP_SHA256,
        "release_bundle": RELEASE_BUNDLE,
        "release_bundle_size": RELEASE_BUNDLE_SIZE,
        "release_bundle_sha256": RELEASE_BUNDLE_SHA256,
        "application_offset": hex(APPLICATION_OFFSET),
        "application_size": APPLICATION_SIZE,
        "application_sha256": APPLICATION_SHA256,
        "otadata_offset": hex(OTADATA_OFFSET),
        "otadata_size": OTADATA_SIZE,
        "otadata_sha256": OTADATA_INITIAL_SHA256,
        "otadata_initial_sha256": OTADATA_INITIAL_SHA256,
        "otadata_postreset_runtime_sha256": OTADATA_POSTRESET_RUNTIME_SHA256,
        "otadata_postreset_ota_seq": OTADATA_POSTRESET_OTA_SEQ,
        "otadata_postreset_state": "VALID",
        "otadata_postreset_crc": f"0x{OTADATA_POSTRESET_CRC:08x}",
        "partition_table_sha256": PARTITION_TABLE_SHA256,
        "product_source": PRODUCT_SOURCE,
        "product_tree": PRODUCT_TREE,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "workflow_trigger_sha": WORKFLOW_TRIGGER_SHA,
        "minimal_write_route": True,
        "bootloader_write": False,
        "partition_table_write": False,
        "product_nvs_write": False,
        "factory_image_write": False,
        "full_flash_erase": False,
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run_preflight(args: argparse.Namespace) -> int:
    profile = board_profile(args.board)
    if args.confirm_target != profile["target_confirmation"]:
        raise StopExecution("operator target confirmation token mismatch")

    with tempfile.TemporaryDirectory(prefix=f"n3w-gwsel-v1-board-{args.board.lower()}-preflight-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_application_image(files["application"])
        board = probe_board(args.port, args.board)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "valid_for_seconds": PREFLIGHT_MAX_AGE_SECONDS,
        "operator_board_label": args.board,
        "operator_target_confirmation": True,
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "persistent_mutation": False,
        "rom_probe_may_reset_target": True,
        "application_serial_open": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
        "partition_table_write": False,
        "bootloader_write": False,
        "factory_image_write": False,
        "full_flash_erase": False,
        "write_authorization_granted": False,
    }
    write_json(Path(args.output), payload)

    print(f"N3W_PRODUCTION_GWSEL_V1_BOARD_{args.board}_EXACT_WRITE_PREFLIGHT=PASS")
    print(f"BOARD_LABEL={args.board}")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print("CHIP=ESP32-C6")
    print("FLASH_SIZE=8MB")
    print("SECURE_BOOT=false")
    print("FLASH_ENCRYPTION=false")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"CURRENT_OTADATA_SHA256={board['current_otadata_sha256']}")
    print(f"CANDIDATE_ARTIFACT_ID={ARTIFACT_ID}")
    print(f"CANDIDATE_RELEASE_SHA256={RELEASE_BUNDLE_SHA256}")
    print("MINIMAL_WRITE_ROUTE_READY=true")
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("WRITE_AUTHORIZATION_GRANTED=false")
    return 0


def load_preflight(path: Path, board_label: str, port: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight closure is unreadable") from exc

    if payload.get("schema") != SCHEMA_PREFLIGHT or payload.get("status") != "PASS":
        raise StopExecution("preflight closure is not PASS")
    if payload.get("operator_board_label") != board_label:
        raise StopExecution("preflight board label mismatch")
    if payload.get("artifact") != artifact_binding_payload():
        raise StopExecution("preflight artifact binding drifted")
    if payload.get("authorization_claimed") is not False:
        raise StopExecution("preflight authorization is already claimed")
    if payload.get("authorization_consumed") is not False:
        raise StopExecution("preflight authorization is already consumed")
    if payload.get("replay_permitted") is not False:
        raise StopExecution("preflight replay policy is invalid")

    board = payload.get("board")
    if not isinstance(board, dict):
        raise StopExecution("preflight board binding missing")

    profile = board_profile(board_label)
    if board.get("hardware_id_sha256") != profile["hardware_id_sha256"]:
        raise StopExecution("preflight target identity mismatch")
    if board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("serial port locator changed since preflight")
    if board.get("chip") != "ESP32-C6" or board.get("flash_size") != "8MB":
        raise StopExecution("preflight silicon/flash binding mismatch")
    if board.get("secure_boot") is not False or board.get("flash_encryption") is not False:
        raise StopExecution("preflight security state mismatch")
    if board.get("partition_table_offset") != hex(PARTITION_TABLE_OFFSET):
        raise StopExecution("preflight partition table offset mismatch")
    if board.get("partition_table_size") != PARTITION_TABLE_SIZE:
        raise StopExecution("preflight partition table size mismatch")
    if board.get("partition_table_sha256") != PARTITION_TABLE_SHA256:
        raise StopExecution("preflight partition table binding mismatch")

    raw_time = payload.get("created_at")
    if not isinstance(raw_time, str):
        raise StopExecution("preflight timestamp missing")
    try:
        created = dt.datetime.fromisoformat(raw_time)
    except ValueError as exc:
        raise StopExecution("preflight timestamp invalid") from exc
    if created.tzinfo is None:
        raise StopExecution("preflight timestamp must be timezone-aware")

    age = (utc_now() - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("preflight is stale; rerun preflight before write")

    return payload


def claim_preflight(path: Path, board_label: str, port: str) -> tuple[Path, dict[str, object]]:
    payload = load_preflight(path, board_label, port)

    if path.is_symlink() or not path.is_file():
        raise StopExecution("preflight closure path is unsafe")

    claimed = path.with_name("claimed-" + path.name)
    if claimed.exists() or claimed.is_symlink():
        raise StopExecution("preflight authorization was already claimed")

    try:
        source_inode = path.stat().st_ino
        os.link(path, claimed, follow_symlinks=False)
    except OSError as exc:
        raise StopExecution("preflight authorization claim failed") from exc

    try:
        path.unlink()
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        raise StopExecution("preflight authorization claim could not remove source") from exc

    if path.exists() or not claimed.is_file() or claimed.is_symlink():
        raise StopExecution("preflight authorization claim verification failed")
    if claimed.stat().st_ino != source_inode:
        raise StopExecution("preflight authorization claim inode mismatch")

    payload["authorization_claimed"] = True
    payload["authorization_consumed"] = True
    payload["replay_permitted"] = False
    payload["consumed_at"] = utc_now().isoformat()
    write_json(claimed, payload)
    return claimed, payload


def build_write_command(port: str, otadata: Path, application: Path) -> list[str]:
    return esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--baud",
        "460800",
        "--before",
        "default-reset",
        "--after",
        "hard-reset",
        "write-flash",
        hex(OTADATA_OFFSET),
        str(otadata),
        hex(APPLICATION_OFFSET),
        str(application),
    ]


def verify_postwrite_readback(port: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="n3w-gwsel-v1-postwrite-readback-") as td:
        root = Path(td)
        otadata = root / "otadata.bin"
        application = root / "application.bin"
        partition = root / "partition-table.bin"

        read_flash_region(port, OTADATA_OFFSET, OTADATA_SIZE, otadata)
        application_sha = read_flash_region(
            port,
            APPLICATION_OFFSET,
            APPLICATION_SIZE,
            application,
        )
        partition_sha = read_flash_region(
            port,
            PARTITION_TABLE_OFFSET,
            PARTITION_TABLE_SIZE,
            partition,
        )

        otadata_runtime = validate_postreset_otadata(otadata.read_bytes())

    if application_sha != APPLICATION_SHA256:
        raise StopExecution("post-write application readback SHA256 mismatch")
    if partition_sha != PARTITION_TABLE_SHA256:
        raise StopExecution("post-write partition table readback SHA256 mismatch")

    return {
        "otadata_sha256": otadata_runtime["sha256"],
        "otadata_runtime_ota_seq": otadata_runtime["ota_seq"],
        "otadata_runtime_state": otadata_runtime["ota_state"],
        "otadata_runtime_state_raw": otadata_runtime["ota_state_raw"],
        "otadata_runtime_crc": otadata_runtime["crc"],
        "application_sha256": application_sha,
        "partition_table_sha256": partition_sha,
    }


def run_write(args: argparse.Namespace) -> int:
    profile = board_profile(args.board)
    if args.confirm_write != profile["write_confirmation"]:
        raise StopExecution("write confirmation token mismatch")

    preflight_path = Path(args.preflight)
    load_preflight(preflight_path, args.board, args.port)

    with tempfile.TemporaryDirectory(prefix=f"n3w-gwsel-v1-board-{args.board.lower()}-write-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_application_image(files["application"])

        fresh_board = probe_board(args.port, args.board)
        if fresh_board["port_sha256"] != sha256_bytes(args.port.encode("utf-8")):
            raise StopExecution("fresh port binding mismatch")
        if fresh_board["partition_table_sha256"] != PARTITION_TABLE_SHA256:
            raise StopExecution("fresh partition table binding mismatch")

        claimed_preflight, _ = claim_preflight(preflight_path, args.board, args.port)

        command = build_write_command(
            args.port,
            files["otadata"],
            files["application"],
        )
        run_capture(command, port=args.port)

        readback = verify_postwrite_readback(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "operator_board_label": args.board,
        "esptool_version": esptool_version,
        "board": fresh_board,
        "artifact": artifact_binding_payload(),
        "authorization": {
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "claim_file_sha256": sha256_bytes(claimed_preflight.name.encode("utf-8")),
        },
        "write_scope": {
            "otadata_offset": hex(OTADATA_OFFSET),
            "application_offset": hex(APPLICATION_OFFSET),
            "bootloader_write": False,
            "partition_table_write": False,
            "product_nvs_write": False,
            "factory_image_write": False,
            "full_flash_erase": False,
        },
        "postwrite_readback": readback,
    }
    write_json(Path(args.output), payload)

    print(f"N3W_PRODUCTION_GWSEL_V1_BOARD_{args.board}_EXACT_WRITE=PASS")
    print(f"BOARD_LABEL={args.board}")
    print(f"HARDWARE_ID_SHA256={fresh_board['hardware_id_sha256']}")
    print(f"OTADATA_WRITE_SHA256={OTADATA_INITIAL_SHA256}")
    print(f"APPLICATION_WRITE_SHA256={APPLICATION_SHA256}")
    print(f"OTADATA_READBACK_SHA256={readback['otadata_sha256']}")
    print(f"OTADATA_POSTRESET_OTA_SEQ={readback['otadata_runtime_ota_seq']}")
    print(f"OTADATA_POSTRESET_STATE={readback['otadata_runtime_state']}")
    print(f"OTADATA_POSTRESET_CRC={readback['otadata_runtime_crc']}")
    print(f"APPLICATION_READBACK_SHA256={readback['application_sha256']}")
    print(f"PARTITION_TABLE_READBACK_SHA256={readback['partition_table_sha256']}")
    print("AUTHORIZATION_CLAIMED=true")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    print("BOOTLOADER_WRITE=false")
    print("PARTITION_TABLE_WRITE=false")
    print("PRODUCT_NVS_WRITE=false")
    print("FACTORY_IMAGE_WRITE=false")
    print("FULL_FLASH_ERASE=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--board", required=True, choices=sorted(BOARD_PROFILES))
    preflight.add_argument("--port", required=True)
    preflight.add_argument("--artifact-zip", required=True)
    preflight.add_argument("--output", required=True)
    preflight.add_argument("--confirm-target", required=True)
    preflight.set_defaults(func=run_preflight)

    write = sub.add_parser("write")
    write.add_argument("--board", required=True, choices=sorted(BOARD_PROFILES))
    write.add_argument("--port", required=True)
    write.add_argument("--artifact-zip", required=True)
    write.add_argument("--preflight", required=True)
    write.add_argument("--output", required=True)
    write.add_argument("--confirm-write", required=True)
    write.set_defaults(func=run_write)

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
