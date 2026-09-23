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

SCHEMA_PREFLIGHT = "n3w.production.gwsel-v1.board-b-preflight/1"
BOARD_LABEL = "B"

# Exact production successor / artifact authority.
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

# Physical target binding deliberately does NOT reuse historical A/B identity
# mappings. The operator label is combined with a fresh ROM identity hash.
# The current application version is intentionally not constrained: A/B/C may
# begin this gate on different historical firmware revisions.
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = MEMBER_BINDINGS["partitions.bin"][1]
OTADATA_OFFSET = 0x9000
OTADATA_SIZE = 0x2000

TARGET_CONFIRMATION = "BOARD_B_CONNECTED_FOR_GWSEL_V1_READONLY_PREFLIGHT"
PREFLIGHT_MAX_AGE_SECONDS = 900

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


def _safe_exact_members(zf: zipfile.ZipFile, expected: set[str], label: str) -> None:
    members = {name for name in zf.namelist() if not name.endswith("/")}
    if members != expected:
        raise StopExecution(f"{label} member set mismatch")
    if any(Path(name).name != name for name in members):
        raise StopExecution(f"{label} contains non-flat member path")


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

    expected_sidecar = f"{RELEASE_BUNDLE_SHA256}  {RELEASE_BUNDLE}\n"
    if sidecar != expected_sidecar:
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
    parsed = parse_manifest(manifest.read_text(encoding="utf-8"))
    if parsed != EXPECTED_MANIFEST:
        raise StopExecution("MANIFEST.txt content binding mismatch")

    return {
        "release_bundle": release_path,
        "application": extract_root / "firmware.bin",
        "factory": extract_root / "firmware.factory.bin",
        "partition_table": extract_root / "partitions.bin",
        "manifest": manifest,
    }


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
    command = _rom_command(
        port,
        ["read-flash", hex(offset), hex(size), str(destination)],
    )
    run_capture(command, port=port)
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash readback size mismatch")
    return sha256_file(destination)


def probe_board(port: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")

    security = run_capture(
        _rom_command(port, ["get-security-info"]),
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")

    base_mac = canonical_base_mac(security)
    identity_hash = public_identity_sha256(base_mac)

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

    with tempfile.TemporaryDirectory(prefix="n3w-gwsel-v1-board-b-readback-") as td:
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
        "hardware_id_sha256": identity_hash,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(PARTITION_TABLE_OFFSET),
        "partition_table_size": PARTITION_TABLE_SIZE,
        "partition_table_sha256": partition_sha,
        "operator_board_label": BOARD_LABEL,
        "otadata_offset": hex(OTADATA_OFFSET),
        "otadata_size": OTADATA_SIZE,
        "otadata_sha256": current_otadata_sha,
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
        "firmware_bin_size": MEMBER_BINDINGS["firmware.bin"][0],
        "firmware_bin_sha256": MEMBER_BINDINGS["firmware.bin"][1],
        "factory_bin_size": MEMBER_BINDINGS["firmware.factory.bin"][0],
        "factory_bin_sha256": MEMBER_BINDINGS["firmware.factory.bin"][1],
        "partition_table_sha256": PARTITION_TABLE_SHA256,
        "product_source": PRODUCT_SOURCE,
        "product_tree": PRODUCT_TREE,
        "target_blob": TARGET_BLOB,
        "telemetry_bridge_blob": TELEMETRY_BRIDGE_BLOB,
        "transport_blob": TRANSPORT_BLOB,
        "product_core_init_blob": PRODUCT_CORE_INIT_BLOB,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "workflow_trigger_sha": WORKFLOW_TRIGGER_SHA,
        "gateway_selection_r2_link_proof": True,
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run_preflight(args: argparse.Namespace) -> int:
    if args.confirm_target != TARGET_CONFIRMATION:
        raise StopExecution("operator target confirmation token mismatch")

    with tempfile.TemporaryDirectory(prefix="n3w-gwsel-v1-board-b-preflight-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_application_image(files["application"])
        board = probe_board(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "valid_for_seconds": PREFLIGHT_MAX_AGE_SECONDS,
        "operator_board_label": BOARD_LABEL,
        "operator_target_confirmation": True,
        "historical_identity_hash_reused": False,
        "historical_identity_override_reused": False,
        "esptool_version": esptool_version,
        "board": board,
        "candidate_artifact": artifact_binding_payload(),
        "persistent_mutation": False,
        "rom_probe_may_reset_target": True,
        "application_serial_open": False,
        "flash_write": False,
        "nvs_write": False,
        "partition_table_write": False,
        "bootloader_write": False,
        "write_authorization_granted": False,
    }
    write_json(Path(args.output), payload)

    print("N3W_PRODUCTION_GWSEL_V1_BOARD_B_WRITE_TARGET_PREFLIGHT=PASS")
    print(f"BOARD_LABEL={BOARD_LABEL}")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print("CHIP=ESP32-C6")
    print("FLASH_SIZE=8MB")
    print("SECURE_BOOT=false")
    print("FLASH_ENCRYPTION=false")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"OTADATA_READBACK_SHA256={board['otadata_sha256']}")
    print(f"CANDIDATE_ARTIFACT_ID={ARTIFACT_ID}")
    print(f"CANDIDATE_RELEASE_SHA256={RELEASE_BUNDLE_SHA256}")
    print("HISTORICAL_IDENTITY_HASH_REUSED=false")
    print("HISTORICAL_IDENTITY_OVERRIDE_REUSED=false")
    print("PERSISTENT_MUTATION=false")
    print("FLASH_WRITE=false")
    print("WRITE_AUTHORIZATION_GRANTED=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm-target", required=True)
    parser.set_defaults(func=run_preflight)
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
