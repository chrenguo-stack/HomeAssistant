#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_PREFLIGHT = "n3w.auto-safe-fallback.gate-a-board-b-preflight/1"
SCHEMA_WRITE = "n3w.auto-safe-fallback.gate-a-board-b-write/1"
BUNDLE_SCHEMA = "n3w.auto-safe-fallback.gate-a-private-build/1"

SOURCE_HEAD = "8210cf7b53e9ec934d145f1c15e9619579c923be"
SOURCE_TREE = "5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c"
TARGET_BLOB = "7279271d469958940c2b51aa4a80602078470891"
PATCH_BLOB = "49570a83ead08158d4d99c385740fa6d646b5e3d"
APPLICATION_SIZE = 1140352
APPLICATION_SHA256 = "77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"

EXPECTED_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"

WRITE_CONFIRMATION = "N3W_GATE_A_BOARD_B_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900

ROLLBACK_ARTIFACT_ID = 10959875986
ROLLBACK_ARTIFACT_NAME = "n3w-kf099-c578bcb-boardb-exact-source"
ROLLBACK_ARCHIVE_SHA256 = "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb"
ROLLBACK_APPLICATION_SHA256 = "d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60"
ROLLBACK_OTADATA_SHA256 = OTADATA_SHA256

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


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def require_private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StopExecution(f"private file missing or unsafe: {path.name}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StopExecution(f"private file is group/world accessible: {path.name}")


def validate_bundle(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise StopExecution("private bundle directory is missing or unsafe")
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise StopExecution("private bundle directory mode must be 0700")
    manifest_path = root / "manifest.json"
    app = root / "artifact/firmware.bin"
    ota = root / "artifact/ota_data_initial.bin"
    for path in (manifest_path, app, ota):
        require_private_file(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("private build manifest is unreadable") from exc
    if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("status") != "PASS":
        raise StopExecution("private build manifest is not PASS")
    source = manifest.get("source")
    firmware = manifest.get("firmware")
    boundary = manifest.get("execution_boundary")
    if not all(isinstance(value, dict) for value in (source, firmware, boundary)):
        raise StopExecution("private build manifest is incomplete")
    if source.get("head") != SOURCE_HEAD or source.get("tree") != SOURCE_TREE:
        raise StopExecution("private build source binding drifted")
    if source.get("target_blob") != TARGET_BLOB or source.get("patch_blob") != PATCH_BLOB:
        raise StopExecution("private build blob binding drifted")
    if firmware.get("application_size") != APPLICATION_SIZE or firmware.get("application_sha256") != APPLICATION_SHA256:
        raise StopExecution("private application manifest binding drifted")
    if firmware.get("otadata_size") != OTADATA_SIZE or firmware.get("otadata_sha256") != OTADATA_SHA256:
        raise StopExecution("private otadata manifest binding drifted")
    if any(boundary.get(name) is not False for name in (
        "board_access", "board_flash", "t1_mutation", "production_broker_mutation",
        "manager_mutation", "dynsec_mutation", "product_nvs_write",
    )):
        raise StopExecution("private build boundary drifted")
    if app.stat().st_size != APPLICATION_SIZE or sha256_file(app) != APPLICATION_SHA256:
        raise StopExecution("private application file binding mismatch")
    if ota.stat().st_size != OTADATA_SIZE or sha256_file(ota) != OTADATA_SHA256:
        raise StopExecution("private otadata file binding mismatch")
    return {"root": root, "manifest": manifest, "app": app, "ota": ota}


def run_capture(args: list[str], *, port: str | None = None, timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s") from exc
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        redacted = ["<PORT>" if port is not None and value == port else value for value in args]
        raise StopExecution(f"command failed rc={proc.returncode}: {' '.join(redacted)}")
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
        raise StopExecution("private Gate A firmware is not ESP32-C6")


def hardware_id_sha256(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC")
    return sha256_bytes(("ghw-c6-" + compact).encode("utf-8"))


def verify_partition_table(port: str) -> str:
    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-partition-") as td:
        out = Path(td) / "partition.bin"
        run_capture(
            esptool_base() + [
                "--chip", "esp32c6", "--port", port, "--no-stub",
                "read-flash", hex(PARTITION_TABLE_OFFSET), hex(PARTITION_TABLE_SIZE), str(out),
            ],
            port=port,
            timeout=45,
        )
        if not out.is_file() or out.stat().st_size != PARTITION_TABLE_SIZE:
            raise StopExecution("partition table readback size mismatch")
        digest = sha256_file(out)
    if digest != PARTITION_TABLE_SHA256:
        raise StopExecution("partition table binding mismatch")
    return digest


def probe_board(port: str) -> dict[str, Any]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is empty or contains whitespace")
    security = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--no-stub",
            "--after", "hard-reset", "get-security-info",
        ],
        port=port,
        timeout=30,
    )
    mac = MAC_RE.search(security)
    if mac is None:
        raise StopExecution("Board ROM MAC not observed")
    identity = hardware_id_sha256(mac.group(1))
    if identity != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected board is not frozen Board B")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot disabled state not proven")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption disabled state not proven")

    flash = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "--after", "hard-reset", "flash-id"],
        port=port,
        timeout=30,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash not proven")

    partition = verify_partition_table(port)
    return {
        "hardware_id_sha256": identity,
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": partition,
        "board_reset_may_occur": True,
    }


def run_preflight(args: argparse.Namespace) -> int:
    bundle = validate_bundle(Path(args.bundle))
    esptool_version = verify_esptool_version()
    verify_image(bundle["app"])
    board = probe_board(args.port)
    payload = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "application_sha256": APPLICATION_SHA256,
        "otadata_sha256": OTADATA_SHA256,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "board_flash": False,
        "product_nvs_write": False,
        "partition_table_write": False,
        "bootloader_write": False,
        "t1_mutation": False,
    }
    private_json(Path(args.output), payload)
    print("GATE_A_BOARD_B_PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
    print(f"OTADATA_SHA256={OTADATA_SHA256}")
    print("BOARD_FLASH=false")
    print("PRODUCT_NVS_WRITE=false")
    print("T1_MUTATION=false")
    return 0


def load_preflight(path: Path, port: str) -> dict[str, Any]:
    require_private_file(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("Board B Gate A preflight is unreadable") from exc
    if doc.get("schema") != SCHEMA_PREFLIGHT or doc.get("status") != "PASS":
        raise StopExecution("Board B Gate A preflight is not PASS")
    if doc.get("application_sha256") != APPLICATION_SHA256 or doc.get("otadata_sha256") != OTADATA_SHA256:
        raise StopExecution("Board B Gate A artifact binding drifted")
    board = doc.get("board")
    if not isinstance(board, dict):
        raise StopExecution("Board B binding missing")
    if board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("Board B identity drifted")
    if board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("Board B serial locator changed")
    if board.get("partition_table_sha256") != PARTITION_TABLE_SHA256:
        raise StopExecution("Board B partition binding drifted")
    if doc.get("authorization_claimed") is not False or doc.get("authorization_consumed") is not False:
        raise StopExecution("Board B write authorization already claimed")
    if doc.get("replay_permitted") is not False:
        raise StopExecution("Board B write replay policy invalid")
    raw = doc.get("created_at")
    if not isinstance(raw, str):
        raise StopExecution("Board B preflight timestamp missing")
    try:
        created = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise StopExecution("Board B preflight timestamp invalid") from exc
    age = (utc_now() - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("Board B preflight stale")
    return doc


def claim_preflight(path: Path, port: str) -> dict[str, Any]:
    doc = load_preflight(path, port)
    claimed = path.with_name("claimed-" + path.name)
    if claimed.exists() or claimed.is_symlink():
        raise StopExecution("Board B Gate A preflight already claimed")
    try:
        inode = path.stat().st_ino
        os.link(path, claimed, follow_symlinks=False)
        path.unlink()
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        raise StopExecution("Board B Gate A preflight claim failed") from exc
    if claimed.stat().st_ino != inode:
        raise StopExecution("Board B Gate A preflight claim inode mismatch")
    doc["authorization_claimed"] = True
    doc["authorization_consumed"] = True
    doc["consumed_at"] = utc_now().isoformat()
    private_json(claimed, doc)
    return doc


def build_write_command(port: str, ota: Path, app: Path) -> list[str]:
    return esptool_base() + [
        "--chip", "esp32c6", "--port", port, "--baud", "460800",
        "--before", "default-reset", "--after", "hard-reset",
        "write-flash",
        "0x9000", str(ota),
        "0x10000", str(app),
    ]


def run_write(args: argparse.Namespace) -> int:
    if args.confirm != WRITE_CONFIRMATION:
        raise StopExecution("Board B Gate A write confirmation token mismatch")
    bundle = validate_bundle(Path(args.bundle))
    preflight_path = Path(args.preflight)
    load_preflight(preflight_path, args.port)

    esptool_version = verify_esptool_version()
    verify_image(bundle["app"])
    board = probe_board(args.port)
    if board["hardware_id_sha256"] != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("fresh Board B identity binding failed")
    if board["partition_table_sha256"] != PARTITION_TABLE_SHA256:
        raise StopExecution("fresh Board B partition binding failed")

    claim_preflight(preflight_path, args.port)
    run_capture(build_write_command(args.port, bundle["ota"], bundle["app"]), port=args.port, timeout=120)

    payload = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "application_sha256": APPLICATION_SHA256,
        "otadata_sha256": OTADATA_SHA256,
        "authorization": {
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
        "write_scope": {
            "otadata_offset": "0x9000",
            "application_offset": "0x10000",
            "bootloader_write": False,
            "partition_table_write": False,
            "product_nvs_write": False,
            "full_flash_erase": False,
        },
        "rollback": {
            "artifact_id": ROLLBACK_ARTIFACT_ID,
            "artifact_name": ROLLBACK_ARTIFACT_NAME,
            "archive_sha256": ROLLBACK_ARCHIVE_SHA256,
            "application_sha256": ROLLBACK_APPLICATION_SHA256,
            "otadata_sha256": ROLLBACK_OTADATA_SHA256,
            "write_authorization_required": True,
        },
    }
    private_json(Path(args.output), payload)
    print("GATE_A_BOARD_B_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
    print(f"OTADATA_SHA256={OTADATA_SHA256}")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    print("BOOTLOADER_WRITE=false")
    print("PARTITION_TABLE_WRITE=false")
    print("PRODUCT_NVS_WRITE=false")
    print("FULL_FLASH_ERASE=false")
    print("T1_MUTATION=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--port", required=True)
    pre.add_argument("--bundle", required=True)
    pre.add_argument("--output", required=True)
    pre.set_defaults(func=run_preflight)

    write = sub.add_parser("write")
    write.add_argument("--port", required=True)
    write.add_argument("--bundle", required=True)
    write.add_argument("--preflight", required=True)
    write.add_argument("--output", required=True)
    write.add_argument("--confirm", required=True)
    write.set_defaults(func=run_write)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
