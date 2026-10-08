from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

PREFLIGHT_MODULE_PATH = Path(__file__).with_name("executor.py")
spec = importlib.util.spec_from_file_location("gate_f_board_b_preflight_module", PREFLIGHT_MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load Gate F preflight module")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

SCHEMA_WRITE = "n3w.auto-safe-fallback.gate-f.boardb-write/1"
WRITE_CONFIRMATION = "AUTO_SAFE_FALLBACK_B2419D1_BOARD_B_WRITE_AUTHORIZED"


class StopExecution(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def expected_artifact_payload() -> dict[str, object]:
    return {
        "artifact_id": preflight.ARTIFACT_ID,
        "artifact_name": preflight.ARTIFACT_NAME,
        "artifact_zip_sha256": preflight.ARTIFACT_ZIP_SHA256,
        "release_bundle_sha256": preflight.RELEASE_BUNDLE_SHA256,
        "application_sha256": preflight.APPLICATION_SHA256,
        "otadata_sha256": preflight.OTADATA_SHA256,
        "product_source": preflight.PRODUCT_SOURCE,
        "product_tree": preflight.PRODUCT_TREE,
        "workflow_run_id": preflight.WORKFLOW_RUN_ID,
        "workflow_trigger_sha": preflight.WORKFLOW_TRIGGER_SHA,
    }


def load_preflight(path: Path, port: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("preflight closure is unreadable") from exc

    if payload.get("schema") != preflight.SCHEMA or payload.get("status") != "PASS":
        raise StopExecution("preflight closure is not PASS")
    if payload.get("preflight_max_age_seconds") != preflight.PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("preflight age contract drifted")
    if payload.get("artifact") != expected_artifact_payload():
        raise StopExecution("preflight artifact binding drifted")
    if payload.get("persistent_mutation") is not False or payload.get("flash_write") is not False:
        raise StopExecution("preflight mutation contract is invalid")

    board = payload.get("board")
    if not isinstance(board, dict):
        raise StopExecution("preflight board binding missing")
    if board.get("hardware_id_sha256") != preflight.EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("preflight target identity mismatch")
    if board.get("port_sha256") != preflight.sha256_bytes(port.encode("utf-8")):
        raise StopExecution("serial port locator changed since preflight")
    if board.get("chip") != "ESP32-C6" or board.get("flash_size") != "8MB":
        raise StopExecution("preflight silicon or flash binding mismatch")
    if board.get("secure_boot") is not False or board.get("flash_encryption") is not False:
        raise StopExecution("preflight security state mismatch")
    if board.get("partition_table_sha256") != preflight.PARTITION_TABLE_SHA256:
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
    if age < -30 or age > preflight.PREFLIGHT_MAX_AGE_SECONDS:
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
    payload["write_authorization"] = {
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "consumed_at": utc_now().isoformat(),
    }
    write_json(claimed, payload)
    return claimed, payload


def extract_write_images(artifact_zip: Path, extract_root: Path) -> tuple[Path, Path]:
    preflight.validate_artifact(artifact_zip)
    bundle_path = extract_root / preflight.RELEASE_BUNDLE
    with zipfile.ZipFile(artifact_zip, "r") as outer:
        bundle_path.write_bytes(outer.read(preflight.RELEASE_BUNDLE))
    if bundle_path.stat().st_size != preflight.RELEASE_BUNDLE_SIZE:
        raise StopExecution("release bundle size mismatch")
    if preflight.sha256_file(bundle_path) != preflight.RELEASE_BUNDLE_SHA256:
        raise StopExecution("release bundle SHA256 mismatch")

    app = extract_root / "firmware.bin"
    ota = extract_root / "ota_data_initial.bin"
    with zipfile.ZipFile(bundle_path, "r") as inner:
        app.write_bytes(inner.read("firmware.bin"))
        ota.write_bytes(inner.read("ota_data_initial.bin"))
    if app.stat().st_size != preflight.APPLICATION_SIZE or preflight.sha256_file(app) != preflight.APPLICATION_SHA256:
        raise StopExecution("firmware.bin binding mismatch")
    if ota.stat().st_size != preflight.OTADATA_SIZE or preflight.sha256_file(ota) != preflight.OTADATA_SHA256:
        raise StopExecution("ota_data_initial.bin binding mismatch")
    return ota, app


def verify_image(application: Path) -> None:
    output = preflight.run_capture(preflight.esptool_base() + ["--chip", "esp32c6", "image-info", str(application)])
    if "ESP32-C6" not in output.upper():
        raise StopExecution("firmware.bin is not identified as ESP32-C6 image")


def build_write_command(port: str, ota: Path, app: Path) -> list[str]:
    return preflight.esptool_base() + [
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

    with tempfile.TemporaryDirectory(prefix="n3w-auto-safe-fallback-boardb-write-") as td:
        ota, app = extract_write_images(Path(args.artifact_zip), Path(td))
        esptool_version = preflight.verify_esptool()
        verify_image(app)
        board = preflight.probe_board(args.port)
        if board["port_sha256"] != preflight.sha256_bytes(args.port.encode("utf-8")):
            raise StopExecution("fresh port binding mismatch")
        if board["partition_table_sha256"] != preflight.PARTITION_TABLE_SHA256:
            raise StopExecution("fresh partition table binding mismatch")
        claimed_preflight, _ = claim_preflight(preflight_path, args.port)
        command = build_write_command(args.port, ota, app)
        preflight.run_capture(command, port=args.port)

    payload: dict[str, object] = {
        "schema": SCHEMA_WRITE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "esptool_version": esptool_version,
        "board": board,
        "artifact": expected_artifact_payload(),
        "authorization": {
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "claim_file_sha256": preflight.sha256_bytes(claimed_preflight.name.encode("utf-8")),
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
    print(f"OTADATA_SHA256={preflight.OTADATA_SHA256}")
    print(f"APPLICATION_SHA256={preflight.APPLICATION_SHA256}")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print("AUTHORIZATION_CLAIMED=true")
    print("AUTHORIZATION_CONSUMED=true")
    print("REPLAY_PERMITTED=false")
    print("BOOTLOADER_WRITE=false")
    print("PARTITION_TABLE_WRITE=false")
    print("PRODUCT_NVS_WRITE=false")
    print("FULL_FLASH_ERASE=false")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        return run_write(args)
    except (StopExecution, preflight.StopExecution) as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
