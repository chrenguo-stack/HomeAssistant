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
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_PREFLIGHT = "n3w.auto-safe-fallback.gate-a-kf099-rollback-preflight/1"
SCHEMA_WRITE = "n3w.auto-safe-fallback.gate-a-kf099-rollback-write/1"

ARTIFACT_ID = 10959875986
ARTIFACT_NAME = "n3w-kf099-c578bcb-boardb-exact-source"
ARTIFACT_ZIP_SIZE = 731171
ARTIFACT_ZIP_SHA256 = "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb"
APPLICATION_SIZE = 1146176
APPLICATION_SHA256 = "d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
MANIFEST_SIZE = 640
MANIFEST_SHA256 = "3de057974a6ca673e064a4e58e0226b142a10412f8efa76c477697d020e3306b"

PRODUCT_SOURCE = "c578bcb2e31f50771b6b08c231704da6bf36b729"
PRODUCT_TREE = "1678c7fa571db9b8f47b7b8a03dbd332620d1e19"
TARGET_CONFIG = "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
TARGET_BLOB = "37654481747b21ca51ccecc246bf84ca437ab7a9"
PAIRING_CLIENT_BLOB = "79f050b189d89960889006c195ca5881bed7a277"
WORKFLOW_TRIGGER_SHA = "990f245a9b8a6257f7fc216820b4e196b2551ed2"
WORKFLOW_RUN_ID = 36399176674

EXPECTED_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"

WRITE_CONFIRMATION = "N3W_GATE_A_KF099_ROLLBACK_WRITE_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900
EXPECTED_MEMBERS = {"MANIFEST.txt", "firmware.bin", "ota_data_initial.bin"}

EXPECTED_MANIFEST = {
    "SOURCE_HEAD": PRODUCT_SOURCE,
    "SOURCE_TREE": PRODUCT_TREE,
    "TARGET_CONFIG": TARGET_CONFIG,
    "TARGET_BLOB_SHA": TARGET_BLOB,
    "PAIRING_CLIENT_BLOB_SHA": PAIRING_CLIENT_BLOB,
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
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)


class StopExecution(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
        raise StopExecution("private preflight is missing or unsafe")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StopExecution("private preflight is group/world accessible")


def parse_manifest(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw or "=" not in raw:
            if raw:
                raise StopExecution("rollback manifest contains invalid line")
            continue
        key, value = raw.split("=", 1)
        if not key or key in out:
            raise StopExecution("rollback manifest contains invalid or duplicate key")
        out[key] = value
    return out


def validate_artifact(archive: Path, root: Path) -> dict[str, Path]:
    if not archive.is_file():
        raise StopExecution("rollback artifact ZIP missing")
    if archive.stat().st_size != ARTIFACT_ZIP_SIZE or sha256_file(archive) != ARTIFACT_ZIP_SHA256:
        raise StopExecution("rollback artifact ZIP binding mismatch")
    with zipfile.ZipFile(archive, "r") as zf:
        members = {name for name in zf.namelist() if not name.endswith("/")}
        if members != EXPECTED_MEMBERS:
            raise StopExecution("rollback artifact member set mismatch")
        for name in sorted(EXPECTED_MEMBERS):
            target = root / name
            with zf.open(name, "r") as src, target.open("wb") as dst:
                dst.write(src.read())
    app = root / "firmware.bin"
    ota = root / "ota_data_initial.bin"
    manifest = root / "MANIFEST.txt"
    if app.stat().st_size != APPLICATION_SIZE or sha256_file(app) != APPLICATION_SHA256:
        raise StopExecution("rollback application binding mismatch")
    if ota.stat().st_size != OTADATA_SIZE or sha256_file(ota) != OTADATA_SHA256:
        raise StopExecution("rollback otadata binding mismatch")
    if manifest.stat().st_size != MANIFEST_SIZE or sha256_file(manifest) != MANIFEST_SHA256:
        raise StopExecution("rollback manifest file binding mismatch")
    if parse_manifest(manifest.read_text(encoding="utf-8")) != EXPECTED_MANIFEST:
        raise StopExecution("rollback manifest content binding mismatch")
    return {"app": app, "ota": ota, "manifest": manifest}


def run_capture(argv: list[str], *, port: str | None = None, timeout: int = 60) -> str:
    try:
        p = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s") from exc
    if p.returncode != 0:
        redacted = ["<PORT>" if port is not None and value == port else value for value in argv]
        raise StopExecution(f"command failed rc={p.returncode}: {' '.join(redacted)}")
    return (p.stdout or "") + "\n" + (p.stderr or "")


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_image(app: Path) -> None:
    out = run_capture(esptool_base() + ["--chip", "esp32c6", "image-info", str(app)])
    if "ESP32-C6" not in out.upper():
        raise StopExecution("rollback firmware is not ESP32-C6")


def hardware_id_sha256(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC")
    return sha256_bytes(("ghw-c6-" + compact).encode("utf-8"))


def verify_partition_table(port: str) -> str:
    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-rollback-partition-") as td:
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
        raise StopExecution("serial port locator invalid")
    security = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--no-stub",
            "--after", "hard-reset", "get-security-info",
        ],
        port=port,
        timeout=30,
    )
    match = MAC_RE.search(security)
    if match is None:
        raise StopExecution("Board ROM MAC unavailable")
    identity = hardware_id_sha256(match.group(1))
    if identity != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target is not frozen Board B")
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
        "partition_table_sha256": partition,
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
    }


def artifact_binding() -> dict[str, Any]:
    return {
        "artifact_id": ARTIFACT_ID,
        "artifact_name": ARTIFACT_NAME,
        "archive_sha256": ARTIFACT_ZIP_SHA256,
        "application_sha256": APPLICATION_SHA256,
        "otadata_sha256": OTADATA_SHA256,
        "source": PRODUCT_SOURCE,
        "tree": PRODUCT_TREE,
    }


def run_preflight(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-kf099-rollback-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        verify_image(files["app"])
        board = probe_board(args.port)
    payload = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "board": board,
        "artifact": artifact_binding(),
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "board_flash": False,
        "t1_mutation": False,
    }
    private_json(Path(args.output), payload)
    print("GATE_A_KF099_ROLLBACK_PREFLIGHT=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print(f"ROLLBACK_APPLICATION_SHA256={APPLICATION_SHA256}")
    print("BOARD_FLASH=false")
    print("T1_MUTATION=false")
    return 0


def load_preflight(path: Path, port: str) -> dict[str, Any]:
    require_private_file(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("rollback preflight unreadable") from exc
    if doc.get("schema") != SCHEMA_PREFLIGHT or doc.get("status") != "PASS":
        raise StopExecution("rollback preflight is not PASS")
    if doc.get("artifact") != artifact_binding():
        raise StopExecution("rollback artifact binding drifted")
    board = doc.get("board")
    if not isinstance(board, dict):
        raise StopExecution("rollback Board binding missing")
    if board.get("hardware_id_sha256") != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("rollback target identity drifted")
    if board.get("port_sha256") != sha256_bytes(port.encode("utf-8")):
        raise StopExecution("rollback serial locator changed")
    if board.get("partition_table_sha256") != PARTITION_TABLE_SHA256:
        raise StopExecution("rollback partition binding drifted")
    if doc.get("authorization_claimed") is not False or doc.get("authorization_consumed") is not False:
        raise StopExecution("rollback authorization already claimed")
    if doc.get("replay_permitted") is not False:
        raise StopExecution("rollback replay policy invalid")
    raw = doc.get("created_at")
    if not isinstance(raw, str):
        raise StopExecution("rollback preflight timestamp missing")
    try:
        created = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise StopExecution("rollback preflight timestamp invalid") from exc
    age = (utc_now() - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("rollback preflight stale")
    return doc


def claim_preflight(path: Path, port: str) -> dict[str, Any]:
    doc = load_preflight(path, port)
    claimed = path.with_name("claimed-" + path.name)
    if claimed.exists() or claimed.is_symlink():
        raise StopExecution("rollback preflight already claimed")
    try:
        inode = path.stat().st_ino
        os.link(path, claimed, follow_symlinks=False)
        path.unlink()
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        raise StopExecution("rollback preflight claim failed") from exc
    if claimed.stat().st_ino != inode:
        raise StopExecution("rollback preflight claim inode mismatch")
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
        raise StopExecution("rollback write confirmation token mismatch")
    preflight_path = Path(args.preflight)
    load_preflight(preflight_path, args.port)
    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-kf099-rollback-write-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        verify_image(files["app"])
        board = probe_board(args.port)
        if board["hardware_id_sha256"] != EXPECTED_HARDWARE_ID_SHA256:
            raise StopExecution("fresh rollback Board identity failed")
        if board["partition_table_sha256"] != PARTITION_TABLE_SHA256:
            raise StopExecution("fresh rollback partition binding failed")
        claim_preflight(preflight_path, args.port)
        run_capture(build_write_command(args.port, files["ota"], files["app"]), port=args.port, timeout=120)

    payload = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "board": board,
        "artifact": artifact_binding(),
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
        "expected_post_rollback_baseline": "KF099_PAIRING_WAIT_REPAIR_INTENT_REQUIRED",
    }
    private_json(Path(args.output), payload)
    print("GATE_A_KF099_ROLLBACK_WRITE=PASS")
    print(f"HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"APPLICATION_SHA256={APPLICATION_SHA256}")
    print(f"OTADATA_SHA256={OTADATA_SHA256}")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    print("PRODUCT_NVS_WRITE=false")
    print("PARTITION_TABLE_WRITE=false")
    print("BOOTLOADER_WRITE=false")
    print("FULL_FLASH_ERASE=false")
    print("T1_MUTATION=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--port", required=True)
    pre.add_argument("--artifact-zip", required=True)
    pre.add_argument("--output", required=True)
    pre.set_defaults(func=run_preflight)
    write = sub.add_parser("write")
    write.add_argument("--port", required=True)
    write.add_argument("--artifact-zip", required=True)
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
