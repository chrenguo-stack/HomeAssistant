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

SCHEMA_PREFLIGHT = "n3w.kf096.pr437.boardb-preflight/1"
SCHEMA_WRITE = "n3w.kf096.pr437.boardb-write/1"

PRODUCT_SOURCE = "cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c"
PRODUCT_TREE = "b459fae0a054d45b0d09e60bffae9769e060a5c0"
TARGET_CONFIG = "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
TARGET_BLOB = "3d13e2197520c375b56d682b37773ef28e194421"
WORKFLOW_TRIGGER_SHA = "f5dfdad292a1a9263a7f433b759a6def4d3d1153"
WORKFLOW_RUN_ID = 35414060819

ARTIFACT_ID = 10575077512
ARTIFACT_NAME = "n3w-pr437-boardb-exact-source"
ARTIFACT_ZIP_SIZE = 727532
ARTIFACT_ZIP_SHA256 = "b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814"
APPLICATION_SIZE = 1139600
APPLICATION_SHA256 = "407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
MANIFEST_SIZE = 575
MANIFEST_SHA256 = "98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"

EXPECTED_HARDWARE_ID_SHA256 = "cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0"
EXPECTED_MEMBERS = {"MANIFEST.txt", "firmware.bin", "ota_data_initial.bin"}
WRITE_CONFIRMATION = "PR437_BOARD_B_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900

EXPECTED_MANIFEST = {
    "SOURCE_HEAD": PRODUCT_SOURCE,
    "SOURCE_TREE": PRODUCT_TREE,
    "TARGET_CONFIG": TARGET_CONFIG,
    "TARGET_BLOB_SHA": TARGET_BLOB,
    "PYTHON_VERSION": "3.11",
    "ESPHOME_VERSION": "2026.4.3",
    "ESP_IDF_VERSION": "5.5.4",
    "WORKFLOW_TRIGGER_SHA": WORKFLOW_TRIGGER_SHA,
    "APPLICATION_SIZE": str(APPLICATION_SIZE),
    "OTADATA_SIZE": str(OTADATA_SIZE),
    "APPLICATION_SHA256": APPLICATION_SHA256,
    "OTADATA_SHA256": OTADATA_SHA256,
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


def validate_artifact(archive: Path, extract_root: Path) -> dict[str, Path]:
    if not archive.is_file():
        raise StopExecution("artifact ZIP is missing")
    if archive.stat().st_size != ARTIFACT_ZIP_SIZE:
        raise StopExecution("artifact ZIP size mismatch")
    if sha256_file(archive) != ARTIFACT_ZIP_SHA256:
        raise StopExecution("artifact ZIP SHA256 mismatch")

    with zipfile.ZipFile(archive, "r") as zf:
        members = {name for name in zf.namelist() if not name.endswith("/")}
        if members != EXPECTED_MEMBERS:
            raise StopExecution("artifact member set mismatch")
        for name in sorted(EXPECTED_MEMBERS):
            target = extract_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name, "r") as source, target.open("wb") as dest:
                dest.write(source.read())

    app = extract_root / "firmware.bin"
    ota = extract_root / "ota_data_initial.bin"
    manifest = extract_root / "MANIFEST.txt"

    if app.stat().st_size != APPLICATION_SIZE or sha256_file(app) != APPLICATION_SHA256:
        raise StopExecution("firmware.bin binding mismatch")
    if ota.stat().st_size != OTADATA_SIZE or sha256_file(ota) != OTADATA_SHA256:
        raise StopExecution("ota_data_initial.bin binding mismatch")
    if manifest.stat().st_size != MANIFEST_SIZE or sha256_file(manifest) != MANIFEST_SHA256:
        raise StopExecution("MANIFEST.txt hash binding mismatch")

    parsed = parse_manifest(manifest.read_text(encoding="utf-8"))
    if parsed != EXPECTED_MANIFEST:
        raise StopExecution("MANIFEST.txt content binding mismatch")

    return {"application": app, "otadata": ota, "manifest": manifest}


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


def verify_image(application: Path) -> None:
    output = run_capture(esptool_base() + ["--chip", "esp32c6", "image-info", str(application)])
    if "ESP32-C6" not in output.upper():
        raise StopExecution("firmware.bin is not identified as ESP32-C6 image")


def verify_partition_table(port: str) -> str:
    with tempfile.TemporaryDirectory(prefix="n3w-pr437-partition-") as td:
        destination = Path(td) / "partition-table.bin"
        command = esptool_base() + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--no-stub",
            "read-flash",
            hex(PARTITION_TABLE_OFFSET),
            hex(PARTITION_TABLE_SIZE),
            str(destination),
        ]
        run_capture(command, port=port)
        if not destination.is_file() or destination.stat().st_size != PARTITION_TABLE_SIZE:
            raise StopExecution("partition table readback size mismatch")
        digest = sha256_file(destination)
        if digest != PARTITION_TABLE_SHA256:
            raise StopExecution("partition table binding mismatch")
        return digest


def probe_board(port: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")

    security_cmd = esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
        "get-security-info",
    ]
    security = run_capture(security_cmd, port=port)
    if "ESP32-C6" not in security.upper():
        raise StopExecution("connected target is not reported as ESP32-C6")
    mac_match = MAC_RE.search(security)
    if mac_match is None:
        raise StopExecution("ROM MAC was not observed")
    identity_hash = public_identity_sha256(mac_match.group(1))
    if identity_hash != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target does not match frozen Board B identity")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot is not proven disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption is not proven disabled")

    flash_cmd = esptool_base() + [
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
        "flash-id",
    ]
    flash = run_capture(flash_cmd, port=port)
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash is not proven")

    partition_table_sha256 = verify_partition_table(port)

    return {
        "hardware_id_sha256": identity_hash,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(PARTITION_TABLE_OFFSET),
        "partition_table_size": PARTITION_TABLE_SIZE,
        "partition_table_sha256": partition_table_sha256,
    }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def artifact_binding_payload() -> dict[str, object]:
    return {
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "archive_sha256": ARTIFACT_ZIP_SHA256,
        "application_size": APPLICATION_SIZE,
        "application_sha256": APPLICATION_SHA256,
        "manifest_size": MANIFEST_SIZE,
        "manifest_sha256": MANIFEST_SHA256,
        "otadata_size": OTADATA_SIZE,
        "otadata_sha256": OTADATA_SHA256,
        "product_source": PRODUCT_SOURCE,
        "product_tree": PRODUCT_TREE,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "workflow_trigger_sha": WORKFLOW_TRIGGER_SHA,
    }


def run_preflight(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="n3w-pr437-boardb-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_image(files["application"])
        board = probe_board(args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "persistent_mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
    }
    write_json(Path(args.output), payload)
    print("PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print("CHIP=ESP32-C6")
    print("FLASH_SIZE=8MB")
    print("SECURE_BOOT=false")
    print("FLASH_ENCRYPTION=false")
    print(f"PARTITION_TABLE_SHA256={board[\'partition_table_sha256\']}")
    print("FLASH_WRITE=false")
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
    if payload.get("authorization_claimed") is not False:
        raise StopExecution("preflight authorization is already claimed")
    if payload.get("authorization_consumed") is not False:
        raise StopExecution("preflight authorization is already consumed")
    if payload.get("replay_permitted") is not False:
        raise StopExecution("preflight replay policy is invalid")

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


def claim_preflight(path: Path, port: str) -> tuple[Path, dict[str, object]]:
    payload = load_preflight(path, port)
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


def build_write_command(port: str, ota: Path, app: Path) -> list[str]:
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
        "0x9000",
        str(ota),
        "0x10000",
        str(app),
    ]


def run_write(args: argparse.Namespace) -> int:
    if args.confirm != WRITE_CONFIRMATION:
        raise StopExecution("write confirmation token mismatch")

    preflight_path = Path(args.preflight)
    load_preflight(preflight_path, args.port)

    with tempfile.TemporaryDirectory(prefix="n3w-pr437-boardb-write-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool_version()
        verify_image(files["application"])
        board = probe_board(args.port)
        if board["port_sha256"] != sha256_bytes(args.port.encode("utf-8")):
            raise StopExecution("fresh port binding mismatch")
        if board["partition_table_sha256"] != PARTITION_TABLE_SHA256:
            raise StopExecution("fresh partition table binding mismatch")
        claimed_preflight, _ = claim_preflight(preflight_path, args.port)
        command = build_write_command(args.port, files["otadata"], files["application"])
        run_capture(command, port=args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": artifact_binding_payload(),
        "authorization": {
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "claim_file_sha256": sha256_bytes(claimed_preflight.name.encode("utf-8")),
        },
        "write_scope": {
            "otadata_offset": "0x9000",
            "application_offset": "0x10000",
            "bootloader_write": False,
            "partition_table_write": False,
            "product_nvs_write": False,
            "full_flash_erase": False,
        },
    }
    write_json(Path(args.output), payload)
    print("BOARD_B_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"OTADATA_SHA256={OTADATA_SHA256}")
    print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
    print(f"PARTITION_TABLE_SHA256={board[\'partition_table_sha256\']}")
    print("AUTHORIZATION_CLAIMED=true")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    print("BOOTLOADER_WRITE=false")
    print("PARTITION_TABLE_WRITE=false")
    print("PRODUCT_NVS_WRITE=false")
    print("FULL_FLASH_ERASE=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--port", required=True)
    preflight.add_argument("--artifact-zip", required=True)
    preflight.add_argument("--output", required=True)
    preflight.set_defaults(func=run_preflight)

    write = sub.add_parser("write")
    write.add_argument("--port", required=True)
    write.add_argument("--artifact-zip", required=True)
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
