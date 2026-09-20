from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "n3w.kf096.pr437-177468e.postwrite-direct-baseline/1"

EXPECTED_PRODUCT_SOURCE = "177468e290a207f2fb7f6c554aedf60b61373b4d"
EXPECTED_APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
EXPECTED_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
EXPECTED_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"

MANAGER_CONTAINER = "greenhouse-manager"
CANONICAL_DB = "/var/lib/greenhouse-manager/n3w/replay.sqlite3"

DEFAULT_SETTLE_SECONDS = 30
DEFAULT_OBSERVATION_SECONDS = 90
MIN_SEQ_DELTA = 10

BASE_MAC_RE = re.compile(r"\bBASE MAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args: list[str], *, redact: set[str] | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        safe = []
        redactions = redact or set()
        for item in args:
            safe.append("<REDACTED>" if item in redactions else item)
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"rc={proc.returncode}"
        raise StopExecution(f"command failed: {' '.join(safe)} :: {tail}")
    return (proc.stdout or "") + (proc.stderr or "")


def remote(t1_target: str, command: str) -> str:
    return run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            t1_target,
            command,
        ],
        redact={t1_target},
    )


def manager_snapshot(t1_target: str) -> dict[str, object]:
    out = remote(
        t1_target,
        "docker inspect --format "
        + shlex.quote("{{.State.Running}}\t{{.RestartCount}}\t{{.State.StartedAt}}")
        + f" {shlex.quote(MANAGER_CONTAINER)}",
    ).strip()
    parts = out.split("\t")
    if len(parts) != 3:
        raise StopExecution("unable to parse Manager container state")
    running = parts[0].strip().lower() == "true"
    try:
        restart_count = int(parts[1])
    except ValueError as exc:
        raise StopExecution("unable to parse Manager restart count") from exc
    return {
        "running": running,
        "restart_count": restart_count,
        "started_at": parts[2].strip(),
    }


def canonical_snapshot(t1_target: str) -> dict[str, object]:
    remote_python = r'''
import hashlib, json, sqlite3, sys
db = "file:/var/lib/greenhouse-manager/n3w/replay.sqlite3?mode=ro"
expected = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
con = sqlite3.connect(db, uri=True)
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT node_id, boot_session_hex, seq, last_source, updated_at "
    "FROM n3w_canonical_cursors"
).fetchall()
matches = []
for row in rows:
    node_id = row["node_id"]
    if hashlib.sha256(node_id.encode("utf-8")).hexdigest() == expected:
        matches.append({
            "node_id_sha256": expected,
            "boot_session_hex": row["boot_session_hex"],
            "seq": row["seq"],
            "last_source": row["last_source"],
            "updated_at": row["updated_at"],
        })
if len(matches) != 1:
    print(json.dumps({"status":"NOT_FOUND" if not matches else "AMBIGUOUS","count":len(matches)}))
    sys.exit(0)
print(json.dumps({"status":"FOUND","cursor":matches[0]}, separators=(",",":")))
'''
    command = (
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} "
        f"python -c {shlex.quote(remote_python)}"
    )
    raw = remote(t1_target, command).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Manager canonical snapshot returned invalid JSON") from exc
    return payload


def release_board(port: str) -> str:
    if not port.startswith("/dev/cu.usbmodem") or any(ch.isspace() for ch in port):
        raise StopExecution("serial port locator is not an allowed usbmodem path")
    if not os.path.exists(port):
        raise StopExecution("serial port does not exist")

    out = run(
        [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--before",
            "no-reset",
            "--after",
            "hard-reset",
            "read-mac",
        ],
        redact={port},
    )
    match = BASE_MAC_RE.search(out)
    if match is None:
        raise StopExecution("BASE MAC was not observed while releasing Board B")
    identity_hash = sha256_text("ghw-c6-" + match.group(1).replace(":", "").lower())
    if identity_hash != EXPECTED_HARDWARE_ID_SHA256:
        raise StopExecution("connected target is not frozen Board B identity")
    return identity_hash


def parse_utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise StopExecution("canonical updated_at is not timezone-aware")
    return parsed.astimezone(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--t1-target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settle-seconds", type=int, default=DEFAULT_SETTLE_SECONDS)
    parser.add_argument("--observation-seconds", type=int, default=DEFAULT_OBSERVATION_SECONDS)
    args = parser.parse_args()

    if args.settle_seconds < 10 or args.settle_seconds > 120:
        raise SystemExit("STOP=settle-seconds outside 10..120")
    if args.observation_seconds != 90:
        raise SystemExit("STOP=observation-seconds must remain exactly 90")

    output = Path(args.output)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "product_source": EXPECTED_PRODUCT_SOURCE,
        "application_sha256": EXPECTED_APPLICATION_SHA256,
        "board_hardware_id_sha256": EXPECTED_HARDWARE_ID_SHA256,
        "node_id_sha256": EXPECTED_NODE_ID_SHA256,
        "settle_seconds": args.settle_seconds,
        "observation_seconds": args.observation_seconds,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "t1_mutation": False,
    }

    try:
        manager_pre = manager_snapshot(args.t1_target)
        if not manager_pre["running"]:
            raise StopExecution("Manager is not running before Board B release")

        observed_hardware = release_board(args.port)
        result["board_release_hardware_id_sha256"] = observed_hardware
        result["board_release_hard_reset"] = True

        time.sleep(args.settle_seconds)

        manager_start = manager_snapshot(args.t1_target)
        cursor_start = canonical_snapshot(args.t1_target)
        if cursor_start.get("status") != "FOUND":
            raise StopExecution("Board B canonical cursor not found after settle")
        start = cursor_start["cursor"]
        if start.get("last_source") != "direct":
            raise StopExecution("Board B is not Direct at observation start")

        time.sleep(args.observation_seconds)

        cursor_end = canonical_snapshot(args.t1_target)
        manager_end = manager_snapshot(args.t1_target)
        if cursor_end.get("status") != "FOUND":
            raise StopExecution("Board B canonical cursor not found at observation end")
        end = cursor_end["cursor"]

        managers = [manager_pre, manager_start, manager_end]
        if not all(item["running"] for item in managers):
            raise StopExecution("Manager was not continuously running")
        if len({item["restart_count"] for item in managers}) != 1:
            raise StopExecution("Manager restart count changed")
        if len({item["started_at"] for item in managers}) != 1:
            raise StopExecution("Manager StartedAt changed")

        if end.get("last_source") != "direct":
            raise StopExecution("Board B is not Direct at observation end")
        if start.get("boot_session_hex") != end.get("boot_session_hex"):
            raise StopExecution("Board B boot session changed during 90-second window")

        seq_start = int(start["seq"])
        seq_end = int(end["seq"])
        seq_delta = seq_end - seq_start
        if seq_delta < MIN_SEQ_DELTA:
            raise StopExecution("Board B canonical seq did not advance enough")

        if parse_utc(str(end["updated_at"])) <= parse_utc(str(start["updated_at"])):
            raise StopExecution("Board B canonical updated_at did not advance")

        result.update(
            {
                "status": "PASS",
                "manager_running": True,
                "manager_restart_count_before": manager_pre["restart_count"],
                "manager_restart_count_after": manager_end["restart_count"],
                "manager_started_at_unchanged": True,
                "board_b_cursor_before": "FOUND",
                "board_b_cursor_after": "FOUND",
                "board_b_source_before": start["last_source"],
                "board_b_source_after": end["last_source"],
                "board_b_boot_session_sha256": sha256_text(str(start["boot_session_hex"])),
                "board_b_same_boot": True,
                "board_b_seq_before": seq_start,
                "board_b_seq_after": seq_end,
                "board_b_seq_delta": seq_delta,
                "board_b_updated_at_before": start["updated_at"],
                "board_b_updated_at_after": end["updated_at"],
                "board_b_canonical_advanced": True,
                "postwrite_direct_baseline": "PASS",
            }
        )
        write_json(output, result)

        print("POSTWRITE_DIRECT_BASELINE=PASS")
        print("T1_MANAGER_RUNNING=true")
        print(f"MANAGER_RESTART_COUNT_BEFORE={manager_pre['restart_count']}")
        print(f"MANAGER_RESTART_COUNT_AFTER={manager_end['restart_count']}")
        print("MANAGER_STARTED_AT_UNCHANGED=true")
        print("BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND")
        print("BOARD_B_CANONICAL_CURSOR_AFTER=FOUND")
        print(f"BOARD_B_SOURCE_BEFORE={start['last_source']}")
        print(f"BOARD_B_SOURCE_AFTER={end['last_source']}")
        print(f"BOARD_B_SEQ_BEFORE={seq_start}")
        print(f"BOARD_B_SEQ_AFTER={seq_end}")
        print(f"BOARD_B_SEQ_DELTA={seq_delta}")
        print("BOARD_B_SAME_BOOT=true")
        print("BOARD_B_CANONICAL_ADVANCED=true")
        print("BOARD_FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false")
        print("T1_MUTATION=false")
        return 0

    except (StopExecution, ValueError, KeyError, TypeError) as exc:
        result["stop_reason"] = str(exc)
        write_json(output, result)
        print(f"STOP={exc}", file=sys.stderr)
        print("BOARD_FLASH_WRITE=false", file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false", file=sys.stderr)
        print("APPLICATION_SERIAL_OPEN=false", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
