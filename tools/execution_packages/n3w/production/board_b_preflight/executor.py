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

SCHEMA_PREFLIGHT = "n3w.production.boardb-preflight/1"

# Exact production successor / artifact authority.
PRODUCT_SOURCE = "c1b3d9d016d06c21c9ff7070c0043163739565ca"
PRODUCT_TREE = "0c857fb0f830239717a2e937d176903a6acae8ac"
TARGET_CONFIG = "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
TARGET_BLOB = "32a2b3cb29be4e1bce46807d8825b6a4c37999ec"
TELEMETRY_BRIDGE_BLOB = "ce16f2389d146f9b25e95cbb628547e11ce36bd6"
TRANSPORT_BLOB = "aa39d4b083f2db1b30a76efb1afef156db355a35"
PRODUCT_CORE_INIT_BLOB = "7e86aa2f3fb1bff6f5813e431da501970263e33a"
WORKFLOW_TRIGGER_SHA = "433b91c19bf436a832021d821bda53261b7e3532"
WORKFLOW_RUN_ID = 35612622035

ARTIFACT_ID = 10644667734
ARTIFACT_NAME = "n3w-production-f1rc2-c1b3d9d-exact-source"
ARTIFACT_ZIP_SIZE = 4269260
ARTIFACT_ZIP_SHA256 = "02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72"

RELEASE_BUNDLE = "n3w-production-f1rc2-c1b3d9d-exact-source.zip"
RELEASE_BUNDLE_SIZE = 4268748
RELEASE_BUNDLE_SHA256 = "93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065"
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
    "MANIFEST.txt": (1555, "b0483fe6990a50bbb0715c55a24dc01eb1ce6ddd13ae2d22bc7283f78301a744"),
    "bootloader.bin": (22576, "07865c91e04285282a43188ef326af650b9ecb28c7de74b50006c4917cdea445"),
    "firmware.bin": (1388928, "8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa"),
    "firmware.factory.bin": (1454464, "434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774"),
    "firmware.ota.bin": (1388928, "8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56c876732fd3782c62f"),
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

# Fresh target binding deliberately does NOT reuse the stale historical
# EXPECTED_HARDWARE_ID_SHA256 that failed on the actual Board B in 2026-09-19.
# Instead, operator confirmation is combined with a fresh ROM identity hash and
# an exact readback of the currently deployed PR #437 application.
CURRENT_DEPLOYED_SOURCE = "4270f24a92a87dd5239d781ebba624c2f34b7fc2"
CURRENT_DEPLOYED_ARTIFACT_ID = 10619047221
CURRENT_DEPLOYED_APPLICATION_OFFSET = 0x10000
CURRENT_DEPLOYED_APPLICATION_SIZE = 1145984
CURRENT_DEPLOYED_APPLICATION_SHA256 = "b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843"

PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = MEMBER_BINDINGS["partitions.bin"][1]

TARGET_CONFIRMATION = "BOARD_B_CONNECTED_FOR_READONLY_PREFLIGHT"
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

    mac_match = MAC_RE.search(security)
    if mac_match is None:
        raise StopExecution("ROM MAC was not observed")
    identity_hash = public_identity_sha256(mac_match.group(1))

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

    with tempfile.TemporaryDirectory(prefix="n3w-production-boardb-readback-") as td:
        root = Path(td)
        partition = root / "partition-table.bin"
        current_app = root / "current-pr437-firmware.bin"

        partition_sha = read_flash_region(
            port,
            PARTITION_TABLE_OFFSET,
            PARTITION_TABLE_SIZE,
            partition,
        )
        if partition_sha != PARTITION_TABLE_SHA256:
            raise StopExecution("partition table binding mismatch")

        current_app_sha = read_flash_region(
            port,
            CURRENT_DEPLOYED_APPLICATION_OFFSET,
            CURRENT_DEPLOYED_APPLICATION_SIZE,
            current_app,
        )
        if current_app_sha != CURRENT_DEPLOYED_APPLICATION_SHA256:
            raise StopExecution(
                "current deployed PR437 application readback does not match Board B authority"
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
        "current_deployed_source": CURRENT_DEPLOYED_SOURCE,
        "current_deployed_artifact_id": CURRENT_DEPLOYED_ARTIFACT_ID,
        "current_application_offset": hex(CURRENT_DEPLOYED_APPLICATION_OFFSET),
        "current_application_size": CURRENT_DEPLOYED_APPLICATION_SIZE,
        "current_application_sha256": current_app_sha,
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

    with tempfile.TemporaryDirectory(prefix="n3w-production-boardb-preflight-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_application_image(files["application"])
        board = probe_board(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "valid_for_seconds": PREFLIGHT_MAX_AGE_SECONDS,
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

    print("N3W_PRODUCTION_BOARD_B_WRITE_TARGET_PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print("CHIP=ESP32-C6")
    print("FLASH_SIZE=8MB")
    print("SECURE_BOOT=false")
    print("FLASH_ENCRYPTION=false")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"CURRENT_APPLICATION_SHA256={board['current_application_sha256']}")
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
