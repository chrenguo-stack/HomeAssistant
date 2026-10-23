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
import zipfile
from pathlib import Path
from typing import Iterable

SCHEMA_PREFLIGHT = "n3w.board-d.r4-dual-slot-normalization-write-preflight/2"
SCHEMA_WRITE = "n3w.board-d.r4-dual-slot-normalization-write/2"

PRODUCT_SOURCE = "ec5f6d68e33db7757d91c807fff708ca81b075dc"
PRODUCT_TREE = "16740efa8ad24d423adc0b2de32b99d56e2d23d1"
ARTIFACT_RUN_ID = 39901919230
ARTIFACT_ID = 12478974186
ARTIFACT_NAME = "n3w-board-d-r4-f1rc2-ec5f6d68-exact-source"
GITHUB_ARTIFACT_SHA256 = "898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f"
RELEASE_BUNDLE_NAME = "n3w-board-d-r4-f1rc2-ec5f6d68-exact-source.zip"
RELEASE_BUNDLE_SHA256 = "b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5"
MANIFEST_SHA256 = "173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb"
EXPECTED_HARDWARE_ID_SHA256 = "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"

BOOTLOADER_OFFSET = 0x0
PARTITION_TABLE_OFFSET = 0x8000
OTADATA_OFFSET = 0x9000
PHY_INIT_OFFSET = 0xB000
APP0_OFFSET = 0x10000
APP1_OFFSET = 0x3D0000
NVS_OFFSET = 0x790000
PHY_INIT_SIZE = 0x1000
NVS_SIZE = 0x70000
OTA_SLOT_SIZE = 0x3C0000
FLASH_SECTOR_SIZE = 0x1000
ROM_FLASH_SIZE = "8MB"
SELECTED_WRITE_ROUTE = "DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA"
NORMALIZED_SLOT_SHA256 = "539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195"
NORMALIZATION_TAIL_SHA256 = "50b46211550f22ac7f9bcb795c7a784f2a14f96de618032f600e722f0418b12e"
WRITE_CONFIRMATION = "N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900
EXPECTED_FLASH_ARGS = """--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
"""

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
    extract_root.mkdir(parents=True, exist_ok=True)

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
            target.write_bytes(data)

    manifest = extract_root / "MANIFEST.txt"
    if sha256_file(manifest) != MANIFEST_SHA256:
        raise StopExecution("manifest SHA256 mismatch")
    if parse_manifest(manifest.read_text(encoding="utf-8")) != EXPECTED_MANIFEST:
        raise StopExecution("manifest content binding mismatch")
    if (extract_root / "flash_args").read_text(encoding="utf-8") != EXPECTED_FLASH_ARGS:
        raise StopExecution("flash_args semantic binding mismatch")
    validate_otadata_erased(extract_root / "ota_data_initial.bin")
    return {name: extract_root / name for name in EXPECTED_MEMBERS}


def validate_otadata_erased(path: Path) -> None:
    expected_size = MEMBER_BINDINGS["ota_data_initial.bin"][0]
    data = path.read_bytes()
    if len(data) != expected_size or data != b"\xff" * expected_size:
        raise StopExecution("ota_data_initial.bin is not the expected erased state")


def derive_normalized_slot(application: Path, destination: Path) -> Path:
    expected_size, expected_sha = MEMBER_BINDINGS["firmware.bin"]
    if application.stat().st_size != expected_size or sha256_file(application) != expected_sha:
        raise StopExecution("normalized-slot source application binding mismatch")
    if expected_size >= OTA_SLOT_SIZE:
        raise StopExecution("application does not fit in the OTA slot")
    destination.parent.mkdir(parents=True, exist_ok=True)
    remaining = OTA_SLOT_SIZE - expected_size
    with application.open("rb") as source, destination.open("wb") as target:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            target.write(chunk)
        fill = b"\xff" * (64 * 1024)
        while remaining:
            chunk_size = min(remaining, len(fill))
            target.write(fill[:chunk_size])
            remaining -= chunk_size
    if destination.stat().st_size != OTA_SLOT_SIZE:
        raise StopExecution("normalized-slot size mismatch")
    if sha256_file(destination) != NORMALIZED_SLOT_SHA256:
        raise StopExecution("normalized-slot SHA256 mismatch")
    return destination


def normalized_slot_binding_payload() -> dict[str, object]:
    return {
        "size": OTA_SLOT_SIZE,
        "sha256": NORMALIZED_SLOT_SHA256,
        "source_application_size": MEMBER_BINDINGS["firmware.bin"][0],
        "source_application_sha256": MEMBER_BINDINGS["firmware.bin"][1],
        "tail_size": OTA_SLOT_SIZE - MEMBER_BINDINGS["firmware.bin"][0],
        "tail_sha256": NORMALIZATION_TAIL_SHA256,
    }


def validate_write_erase_boundaries() -> dict[str, tuple[int, int]]:
    if APP0_OFFSET + OTA_SLOT_SIZE != APP1_OFFSET:
        raise StopExecution("app0 boundary does not meet app1")
    if APP1_OFFSET + OTA_SLOT_SIZE != NVS_OFFSET:
        raise StopExecution("app1 boundary does not meet NVS")
    write_ranges = {
        "bootloader": (BOOTLOADER_OFFSET, MEMBER_BINDINGS["bootloader.bin"][0]),
        "otadata": (OTADATA_OFFSET, MEMBER_BINDINGS["ota_data_initial.bin"][0]),
        "app0": (APP0_OFFSET, OTA_SLOT_SIZE),
        "app1": (APP1_OFFSET, OTA_SLOT_SIZE),
    }
    protected_ranges = {
        "partition_table": (
            PARTITION_TABLE_OFFSET,
            PARTITION_TABLE_OFFSET + FLASH_SECTOR_SIZE,
        ),
        "phy_init": (PHY_INIT_OFFSET, PHY_INIT_OFFSET + PHY_INIT_SIZE),
        "nvs": (NVS_OFFSET, NVS_OFFSET + NVS_SIZE),
    }
    erased: dict[str, tuple[int, int]] = {}
    for write_name, (offset, size) in write_ranges.items():
        erase_start = offset - (offset % FLASH_SECTOR_SIZE)
        end = offset + size
        erase_end = ((end + FLASH_SECTOR_SIZE - 1) // FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE
        for protected_name, (protected_start, protected_end) in protected_ranges.items():
            if erase_start < protected_end and protected_start < erase_end:
                raise StopExecution(
                    f"write erase range overlaps protected region: {write_name}->{protected_name}"
                )
        erased[write_name] = (erase_start, erase_end)
    return erased


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


def read_flash_region(
    port: str,
    offset: int,
    size: int,
    destination: Path,
    *,
    use_stub: bool = False,
) -> str:
    if use_stub:
        command = esptool_base() + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--before",
            "no-reset-no-sync",
            "--after",
            "no-reset-stub",
            "read-flash",
            hex(offset),
            hex(size),
            str(destination),
        ]
    else:
        command = esptool_base() + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--before",
            "no-reset",
            "--after",
            "no-reset",
            "--no-stub",
            "read-flash",
            "--flash-size",
            ROM_FLASH_SIZE,
            hex(offset),
            hex(size),
            str(destination),
        ]
    run_capture(command, port=port)
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    return sha256_file(destination)


def observe_board_identity_security(port: str, *, before: str) -> str:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")
    security = run_capture(
        esptool_base()
        + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--before",
            before,
            "--after",
            "no-reset",
            "--no-stub",
            "get-security-info",
        ],
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")
    mac_match = MAC_RE.search(security)
    if mac_match is None:
        raise StopExecution("ROM MAC was not observed")
    identity_hash = public_identity_sha256(mac_match.group(1))
    if identity_hash != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target does not match frozen Board D identity")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption is not proven disabled")
    return identity_hash


def probe_board(port: str) -> dict[str, object]:
    identity_hash = observe_board_identity_security(port, before="default-reset")

    flash = run_capture(
        esptool_base()
        + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--before",
            "no-reset",
            "--after",
            "no-reset",
            "--no-stub",
            "flash-id",
        ],
        port=port,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash is not proven")

    with tempfile.TemporaryDirectory(prefix="n3w-board-d-r4-write-probe-") as td:
        root = Path(td)
        partition_sha = read_flash_region(
            port,
            PARTITION_TABLE_OFFSET,
            MEMBER_BINDINGS["partitions.bin"][0],
            root / "partitions.bin",
        )
        bootloader_sha = read_flash_region(
            port,
            BOOTLOADER_OFFSET,
            MEMBER_BINDINGS["bootloader.bin"][0],
            root / "bootloader.bin",
        )
        phy_init_sha = read_flash_region(
            port,
            PHY_INIT_OFFSET,
            PHY_INIT_SIZE,
            root / "phy-init.bin",
        )
        nvs_sha = read_flash_region(
            port,
            NVS_OFFSET,
            NVS_SIZE,
            root / "nvs.bin",
        )

    if partition_sha != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("Board D partition table does not match the R4 release")

    return {
        "hardware_id_sha256": identity_hash,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(PARTITION_TABLE_OFFSET),
        "partition_table_sha256": partition_sha,
        "bootloader_offset": hex(BOOTLOADER_OFFSET),
        "bootloader_sha256": bootloader_sha,
        "bootloader_matches_release": bootloader_sha == MEMBER_BINDINGS["bootloader.bin"][1],
        "phy_init_offset": hex(PHY_INIT_OFFSET),
        "phy_init_size": PHY_INIT_SIZE,
        "phy_init_sha256": phy_init_sha,
        "nvs_offset": hex(NVS_OFFSET),
        "nvs_size": NVS_SIZE,
        "nvs_sha256": nvs_sha,
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def require_output_absent(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise StopExecution(f"output already exists: {path}")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def artifact_binding_payload() -> dict[str, object]:
    return {
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
    require_output_absent(Path(args.output))
    erase_ranges = validate_write_erase_boundaries()
    with tempfile.TemporaryDirectory(prefix="n3w-board-d-r4-dual-slot-preflight-") as td:
        root = Path(td)
        files = validate_release_bundle(Path(args.release_bundle), root / "release")
        normalized_slot = derive_normalized_slot(files["firmware.bin"], root / "normalized_slot.bin")
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        board = probe_board(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "selected_write_route": SELECTED_WRITE_ROUTE,
        "normalized_slot": normalized_slot_binding_payload(),
        "erase_ranges": {name: [hex(start), hex(end)] for name, (start, end) in erase_ranges.items()},
        "manual_reset_allowed_before_claim": True,
        "manual_reset_allowed_after_claim": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
        "persistent_mutation": False,
    }
    write_json(Path(args.output), payload)
    print("PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"BOOTLOADER_MATCHES_RELEASE={str(board['bootloader_matches_release']).lower()}")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"PHY_INIT_SHA256={board['phy_init_sha256']}")
    print(f"NVS_SHA256={board['nvs_sha256']}")
    print(f"NORMALIZED_SLOT_SHA256={NORMALIZED_SLOT_SHA256}")
    print("APP0_FULL_SLOT_PLANNED=true")
    print("APP1_FULL_SLOT_PLANNED=true")
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("WRITE_AUTHORIZATION_CLAIMED=false")
    return 0


def load_preflight(path: Path, port: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight closure is unreadable") from exc

    if payload.get("schema") != SCHEMA_PREFLIGHT or payload.get("status") != "PASS":
        raise StopExecution("preflight closure is not PASS")
    if payload.get("artifact") != artifact_binding_payload():
        raise StopExecution("preflight artifact binding drifted")
    if payload.get("selected_write_route") != SELECTED_WRITE_ROUTE:
        raise StopExecution("preflight write route mismatch")
    if payload.get("normalized_slot") != normalized_slot_binding_payload():
        raise StopExecution("preflight normalized-slot binding mismatch")
    expected_erase_ranges = {
        name: [hex(start), hex(end)]
        for name, (start, end) in validate_write_erase_boundaries().items()
    }
    if payload.get("erase_ranges") != expected_erase_ranges:
        raise StopExecution("preflight erase-range binding mismatch")
    if payload.get("authorization_claimed") is not False:
        raise StopExecution("preflight authorization is already claimed")
    if payload.get("authorization_consumed") is not False:
        raise StopExecution("preflight authorization is already consumed")
    if payload.get("replay_permitted") is not False:
        raise StopExecution("preflight replay policy is invalid")
    if payload.get("flash_write") is not False or payload.get("nvs_write") is not False:
        raise StopExecution("preflight mutation state is invalid")

    board = payload.get("board")
    if not isinstance(board, dict):
        raise StopExecution("preflight board binding missing")
    if board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("preflight target identity mismatch")
    if board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("serial port locator changed since preflight")
    if board.get("chip") != "ESP32-C6" or board.get("flash_size") != "8MB":
        raise StopExecution("preflight silicon/flash binding mismatch")
    if board.get("secure_boot") is not False or board.get("flash_encryption") is not False:
        raise StopExecution("preflight security state mismatch")
    if board.get("partition_table_sha256") != MEMBER_BINDINGS["partitions.bin"][1]:
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


def _validate_fresh_prewrite_board(fresh_board: dict[str, object], port: str) -> None:
    if fresh_board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("fresh prewrite target identity mismatch")
    if fresh_board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("fresh prewrite serial port binding mismatch")
    if fresh_board.get("chip") != "ESP32-C6" or fresh_board.get("flash_size") != ROM_FLASH_SIZE:
        raise StopExecution("fresh prewrite silicon/flash binding mismatch")
    if fresh_board.get("secure_boot") is not False or fresh_board.get("flash_encryption") is not False:
        raise StopExecution("fresh prewrite security state mismatch")
    if fresh_board.get("partition_table_sha256") != MEMBER_BINDINGS["partitions.bin"][1]:
        raise StopExecution("fresh prewrite partition table binding mismatch")
    for key in ("phy_init_sha256", "nvs_sha256"):
        value = fresh_board.get(key)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise StopExecution(f"fresh prewrite {key} binding is invalid")


def claim_preflight(
    path: Path,
    port: str,
    fresh_board: dict[str, object],
) -> tuple[Path, dict[str, object]]:
    payload = load_preflight(path, port)
    _validate_fresh_prewrite_board(fresh_board, port)
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
    claimed_at = utc_now().isoformat()
    payload["authorization_claimed"] = True
    payload["authorization_consumed"] = True
    payload["replay_permitted"] = False
    payload["consumed_at"] = claimed_at
    payload["fresh_prewrite"] = {
        "captured_at": claimed_at,
        "board": fresh_board,
    }
    payload["execution_state"] = {
        "fresh_prewrite_persisted": True,
        "write_flash_returned_success": False,
        "postwrite_integrity_pass": False,
        "postwrite_identity_pass": False,
    }
    write_json(claimed, payload)
    return claimed, payload


def persist_claimed_execution_state(
    claimed: Path,
    payload: dict[str, object],
    **updates: object,
) -> None:
    if claimed.is_symlink() or not claimed.is_file():
        raise StopExecution("claimed authorization evidence is missing or unsafe")
    state = payload.get("execution_state")
    if not isinstance(state, dict):
        raise StopExecution("claimed authorization execution state is missing")
    state.update(updates)
    payload["execution_state_updated_at"] = utc_now().isoformat()
    write_json(claimed, payload)


def build_write_command(
    port: str,
    files: dict[str, Path],
    normalized_slot: Path,
) -> list[str]:
    return esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--baud",
        "460800",
        "--before",
        "no-reset",
        "--after",
        "no-reset-stub",
        "write-flash",
        "--flash-mode",
        "keep",
        "--flash-freq",
        "keep",
        "--flash-size",
        "keep",
        hex(BOOTLOADER_OFFSET),
        str(files["bootloader.bin"]),
        hex(OTADATA_OFFSET),
        str(files["ota_data_initial.bin"]),
        hex(APP0_OFFSET),
        str(normalized_slot),
        hex(APP1_OFFSET),
        str(normalized_slot),
    ]


def verify_postwrite_integrity(
    port: str,
    root: Path,
    *,
    prewrite_phy_init_sha256: str,
    prewrite_nvs_sha256: str,
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)

    def postwrite_read(offset: int, size: int, destination: Path) -> str:
        return read_flash_region(
            port,
            offset,
            size,
            destination,
            use_stub=True,
        )

    fixed_checks = {
        "bootloader": (
            BOOTLOADER_OFFSET,
            MEMBER_BINDINGS["bootloader.bin"][0],
            MEMBER_BINDINGS["bootloader.bin"][1],
        ),
        "partition_table": (
            PARTITION_TABLE_OFFSET,
            MEMBER_BINDINGS["partitions.bin"][0],
            MEMBER_BINDINGS["partitions.bin"][1],
        ),
        "otadata": (
            OTADATA_OFFSET,
            MEMBER_BINDINGS["ota_data_initial.bin"][0],
            MEMBER_BINDINGS["ota_data_initial.bin"][1],
        ),
    }
    result: dict[str, object] = {}
    for name, (offset, size, expected_sha) in fixed_checks.items():
        actual_sha = postwrite_read(port, offset, size, root / f"{name}.bin")
        if actual_sha != expected_sha:
            raise StopExecution(f"post-write {name} SHA256 mismatch")
        result[f"{name}_sha256"] = actual_sha
        result[f"{name}_match"] = True

    app0_sha = postwrite_read(port, APP0_OFFSET, OTA_SLOT_SIZE, root / "app0-full-slot.bin")
    app1_sha = postwrite_read(port, APP1_OFFSET, OTA_SLOT_SIZE, root / "app1-full-slot.bin")
    if app0_sha != NORMALIZED_SLOT_SHA256:
        raise StopExecution("post-write app0 full-slot SHA256 mismatch")
    if app1_sha != NORMALIZED_SLOT_SHA256:
        raise StopExecution("post-write app1 full-slot SHA256 mismatch")
    result["app0_full_slot_sha256"] = app0_sha
    result["app0_full_slot_match"] = True
    result["app1_full_slot_sha256"] = app1_sha
    result["app1_full_slot_match"] = True
    result["app0_tail_erased"] = True
    result["app1_tail_erased"] = True
    result["old_application_code_remains"] = False

    phy_init_sha = postwrite_read(port, PHY_INIT_OFFSET, PHY_INIT_SIZE, root / "phy-init.bin")
    nvs_sha = postwrite_read(port, NVS_OFFSET, NVS_SIZE, root / "nvs.bin")
    if phy_init_sha != prewrite_phy_init_sha256:
        raise StopExecution("protected phy_init region changed during write")
    if nvs_sha != prewrite_nvs_sha256:
        raise StopExecution("protected NVS region changed during write")
    result["phy_init_sha256"] = phy_init_sha
    result["phy_init_unchanged"] = True
    result["nvs_sha256"] = nvs_sha
    result["nvs_unchanged"] = True
    return result


def run_write(args: argparse.Namespace) -> int:
    if args.confirm != WRITE_CONFIRMATION:
        raise StopExecution("write confirmation token mismatch")
    require_output_absent(Path(args.output))
    erase_ranges = validate_write_erase_boundaries()

    preflight_path = Path(args.preflight)
    load_preflight(preflight_path, args.port)

    with tempfile.TemporaryDirectory(prefix="n3w-board-d-r4-dual-slot-write-") as td:
        root = Path(td)
        files = validate_release_bundle(Path(args.release_bundle), root / "release")
        normalized_slot = derive_normalized_slot(files["firmware.bin"], root / "normalized_slot.bin")
        esptool_version = verify_esptool_version()
        verify_image(files["firmware.bin"])
        fresh_board = probe_board(args.port)
        claimed_preflight, claimed_payload = claim_preflight(
            preflight_path,
            args.port,
            fresh_board,
        )
        command = build_write_command(args.port, files, normalized_slot)
        run_capture(command, port=args.port)
        persist_claimed_execution_state(
            claimed_preflight,
            claimed_payload,
            write_flash_returned_success=True,
            write_flash_completed_at=utc_now().isoformat(),
        )
        postwrite = verify_postwrite_integrity(
            args.port,
            root / "readback",
            prewrite_phy_init_sha256=str(fresh_board["phy_init_sha256"]),
            prewrite_nvs_sha256=str(fresh_board["nvs_sha256"]),
        )
        claimed_payload["postwrite"] = postwrite
        persist_claimed_execution_state(
            claimed_preflight,
            claimed_payload,
            postwrite_integrity_pass=True,
            postwrite_integrity_completed_at=utc_now().isoformat(),
        )
        postwrite_identity = observe_board_identity_security(args.port, before="default-reset")
        postwrite["hardware_id_sha256"] = postwrite_identity
        postwrite["hardware_id_match"] = postwrite_identity == EXPECTED_HARDWARE_ID_SHA256
        persist_claimed_execution_state(
            claimed_preflight,
            claimed_payload,
            postwrite_identity_pass=True,
            postwrite_identity_completed_at=utc_now().isoformat(),
        )

    payload: dict[str, object] = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": fresh_board,
        "fresh_prewrite": claimed_payload["fresh_prewrite"],
        "execution_state": claimed_payload["execution_state"],
        "artifact": artifact_binding_payload(),
        "normalized_slot": normalized_slot_binding_payload(),
        "erase_ranges": {name: [hex(start), hex(end)] for name, (start, end) in erase_ranges.items()},
        "authorization": {
            "label": WRITE_CONFIRMATION,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "claim_file_sha256": sha256_file(claimed_preflight),
        },
        "write_scope": {
            "selected_write_route": SELECTED_WRITE_ROUTE,
            "bootloader_offset": hex(BOOTLOADER_OFFSET),
            "otadata_offset": hex(OTADATA_OFFSET),
            "app0_offset": hex(APP0_OFFSET),
            "app1_offset": hex(APP1_OFFSET),
            "ota_slot_size": OTA_SLOT_SIZE,
            "partition_table_write": False,
            "phy_init_write": False,
            "nvs_write": False,
            "factory_image_direct_write": False,
            "raw_flash_args_direct_execution": False,
            "full_flash_erase": False,
            "erase_region_command_used": False,
            "manual_reset_allowed_after_claim": False,
        },
        "postwrite": postwrite,
    }
    write_json(Path(args.output), payload)
    print("BOARD_D_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={fresh_board['hardware_id_sha256']}")
    print(f"BOOTLOADER_SHA256={postwrite['bootloader_sha256']}")
    print(f"PARTITION_TABLE_SHA256={postwrite['partition_table_sha256']}")
    print(f"OTADATA_SHA256={postwrite['otadata_sha256']}")
    print(f"APP0_FULL_SLOT_SHA256={postwrite['app0_full_slot_sha256']}")
    print(f"APP1_FULL_SLOT_SHA256={postwrite['app1_full_slot_sha256']}")
    print(f"PHY_INIT_SHA256={postwrite['phy_init_sha256']}")
    print(f"NVS_SHA256={postwrite['nvs_sha256']}")
    print(f"POSTWRITE_HARDWARE_ID_SHA256={postwrite['hardware_id_sha256']}")
    print("APP0_TAIL_ERASED=true")
    print("APP1_TAIL_ERASED=true")
    print("OLD_APPLICATION_CODE_REMAINS=false")
    print("POSTWRITE_HARDWARE_ID_MATCH=true")
    print("PHY_INIT_UNCHANGED=true")
    print("NVS_UNCHANGED=true")
    print("AUTHORIZATION_CLAIMED=true")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--port", required=True)
    preflight.add_argument("--release-bundle", required=True)
    preflight.add_argument("--output", required=True)
    preflight.set_defaults(func=run_preflight)

    write = sub.add_parser("write")
    write.add_argument("--port", required=True)
    write.add_argument("--release-bundle", required=True)
    write.add_argument("--preflight", required=True)
    write.add_argument("--output", required=True)
    write.add_argument("--confirm", required=True)
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
