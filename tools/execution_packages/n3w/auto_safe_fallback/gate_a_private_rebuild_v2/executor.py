#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

NETWORK_SCHEMA = "n3w.auto-safe-fallback.gate-a-t1-network-preflight-v2/1"
LEGACY_SCHEMA = "n3w.auto-safe-fallback.gate-a-readonly-preflight/1"
LEGACY_EXECUTOR_BLOB = "18e5d3543c10bb1d5c35b6c8a69c57849cf79f70"
BOARD_B_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"


class StopExecution(RuntimeError):
    pass


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def require_private_json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("private preflight is missing or unsafe")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StopExecution("private preflight is group/world accessible")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("private preflight is unreadable") from exc


def validate_network_preflight(path: Path) -> dict[str, object]:
    doc = require_private_json(path)
    if doc.get("schema") != NETWORK_SCHEMA or doc.get("status") != "PASS":
        raise StopExecution("network preflight schema/status mismatch")
    if doc.get("board_access") is not False or doc.get("board_flash") is not False:
        raise StopExecution("network preflight board boundary drifted")
    if doc.get("t1_mutation") is not False:
        raise StopExecution("network preflight mutation boundary drifted")
    t1 = doc.get("t1")
    if not isinstance(t1, dict):
        raise StopExecution("network preflight T1 binding missing")
    if t1.get("wildcard_8883") is not True or t1.get("port_18883_free") is not True:
        raise StopExecution("network preflight listener boundary not PASS")
    for key in ("current_ip", "live_alias", "blackhole_ip", "interface", "broker_image_id"):
        if not isinstance(t1.get(key), str) or not t1.get(key):
            raise StopExecution(f"network preflight field missing: {key}")
    if not isinstance(t1.get("prefixlen"), int):
        raise StopExecution("network preflight prefix length missing")
    return doc


def validate_legacy_executor(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StopExecution("legacy private build executor missing")
    if git_blob_sha(path) != LEGACY_EXECUTOR_BLOB:
        raise StopExecution("legacy private build executor blob mismatch")


def write_private(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def synthesize_legacy(doc: dict[str, object]) -> dict[str, object]:
    t1 = dict(doc["t1"])
    return {
        "schema": LEGACY_SCHEMA,
        "status": "PASS",
        "t1": {
            "t1_root": True,
            "interface": t1["interface"],
            "current_ip": t1["current_ip"],
            "prefixlen": t1["prefixlen"],
            "gateway": None,
            "wildcard_8883": True,
            "broker_running": True,
            "manager_running": True,
            "manager_restart_count": int(t1.get("manager_restart_count", 0)),
            "live_alias": t1["live_alias"],
            "blackhole_ip": t1["blackhole_ip"],
        },
        "board": {
            "hardware_id_sha256": BOARD_B_HARDWARE_ID_SHA256,
            "port_sha256": "frozen-authority-not-live-read",
            "chip": "ESP32-C6",
            "flash_size": "8MB",
            "secure_boot": False,
            "flash_encryption": False,
            "partition_table_sha256": PARTITION_TABLE_SHA256,
            "board_reset_may_occur": False,
            "flash_write": False,
            "persistent_mutation": False,
        },
        "rollback_artifact": {
            "artifact_id": 10959875986,
            "artifact_name": "n3w-kf099-c578bcb-boardb-exact-source",
            "archive_sha256": "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb",
            "application_sha256": "d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60",
            "otadata_sha256": "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f",
        },
        "t1_mutation": False,
        "board_flash": False,
        "persistent_mutation": False,
    }


def run(args: argparse.Namespace) -> int:
    network = validate_network_preflight(Path(args.network_preflight))
    legacy = Path(args.legacy_executor).expanduser().resolve()
    validate_legacy_executor(legacy)
    output = Path(args.output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise StopExecution("output directory must be absent or empty")

    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-rebind-v2-") as td:
        td_path = Path(td)
        legacy_preflight = td_path / "legacy-preflight.json"
        write_private(legacy_preflight, synthesize_legacy(network))
        p = subprocess.run(
            [
                sys.executable,
                str(legacy),
                "--preflight",
                str(legacy_preflight),
                "--output-dir",
                str(output),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if p.returncode != 0:
            detail = (p.stderr or p.stdout).strip()
            raise StopExecution(f"legacy private build failed rc={p.returncode}: {detail[:800]}")

    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        raise StopExecution("private build manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rebind_v2"] = {
        "network_preflight_schema": NETWORK_SCHEMA,
        "restore_host": network["t1"]["current_ip"],
        "board_binding_source": "frozen_public_authority_not_live_board_access",
        "board_access": False,
        "prior_private_application_superseded": True,
    }
    write_private(manifest_path, manifest)

    for line in p.stdout.splitlines():
        if line.startswith((
            "GATE_A_PRIVATE_BUILD=",
            "SOURCE_HEAD=",
            "SOURCE_TREE=",
            "TARGET_BLOB=",
            "PATCH_BLOB=",
            "ESPHOME_SOURCE=",
            "APPLICATION_SIZE=",
            "APPLICATION_SHA256=",
            "OTADATA_SIZE=",
            "OTADATA_SHA256=",
            "CA_CERT_SHA256=",
            "SERVER_CERT_SHA256=",
            "SERVER_KEY_SHA256=",
            "BROKER_PORT=",
            "TLS_SERVER_NAME=",
            "PRIVATE_BUNDLE=",
        )):
            print(line)
    print("GATE_A_PRIVATE_REBUILD_V2=PASS")
    print("RESTORE_HOST_REBOUND=true")
    print("BOARD_BINDING_SOURCE=frozen_public_authority_not_live_board_access")
    print("BOARD_ACCESS=false")
    print("BOARD_FLASH=false")
    print("T1_MUTATION=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--network-preflight", required=True)
    p.add_argument("--legacy-executor", required=True)
    p.add_argument("--output-dir", required=True)
    return p


def main() -> int:
    try:
        return run(parser().parse_args())
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
