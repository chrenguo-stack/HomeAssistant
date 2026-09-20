from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

SCHEMA = "n3w.kf096.pr437-177468e.postwrite-manager-baseline-recovery/1"

EXPECTED_PRODUCT_SOURCE = "177468e290a207f2fb7f6c554aedf60b61373b4d"
EXPECTED_APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
EXPECTED_BOARD_B_HARDWARE_ID_SHA256 = "cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0"
EXPECTED_BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"

MANAGER_CONTAINER = "greenhouse-manager"
OBSERVATION_SECONDS = 90
MIN_SEQ_DELTA = 10


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args: list[str], *, redact: set[str] | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        redactions = redact or set()
        safe = ["<REDACTED>" if item in redactions else item for item in args]
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
    fmt = "{{.State.Running}}\t{{.RestartCount}}\t{{.State.StartedAt}}"
    out = remote(
        t1_target,
        "docker inspect --format "
        + shlex.quote(fmt)
        + f" {shlex.quote(MANAGER_CONTAINER)}",
    ).strip()
    parts = out.split("\t")
    if len(parts) != 3:
        raise StopExecution("unable to parse Manager container state")
    try:
        restart_count = int(parts[1])
    except ValueError as exc:
        raise StopExecution("unable to parse Manager restart count") from exc
    return {
        "running": parts[0].strip().lower() == "true",
        "restart_count": restart_count,
        "started_at": parts[2].strip(),
    }


def canonical_snapshot(t1_target: str) -> dict[str, object]:
    remote_python = r'''
import hashlib
import json
import os
import sqlite3
import sys

expected = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
path = os.environ.get("GH_N3W_REPLAY_DB_PATH")
if not path:
    print(json.dumps({"status":"STOP","reason":"GH_N3W_REPLAY_DB_PATH missing"}))
    sys.exit(0)

con = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
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
    print(json.dumps({
        "status":"NOT_FOUND" if not matches else "AMBIGUOUS",
        "count":len(matches),
    }, separators=(",",":")))
    sys.exit(0)

print(json.dumps({"status":"FOUND","cursor":matches[0]}, separators=(",",":")))
'''
    command = (
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} "
        f"python -c {shlex.quote(remote_python)}"
    )
    raw = remote(t1_target, command).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Manager canonical snapshot returned invalid JSON") from exc


def parse_utc(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StopExecution("canonical updated_at is invalid") from exc
    if parsed.tzinfo is None:
        raise StopExecution("canonical updated_at is not timezone-aware")
    return parsed.astimezone(dt.timezone.utc)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1-target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--observation-seconds", type=int, default=OBSERVATION_SECONDS)
    args = parser.parse_args()

    if args.observation_seconds != OBSERVATION_SECONDS:
        raise SystemExit("STOP=observation-seconds must remain exactly 90")

    output = Path(args.output)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "product_source": EXPECTED_PRODUCT_SOURCE,
        "application_sha256": EXPECTED_APPLICATION_SHA256,
        "board_b_hardware_id_sha256": EXPECTED_BOARD_B_HARDWARE_ID_SHA256,
        "node_id_sha256": EXPECTED_BOARD_B_NODE_ID_SHA256,
        "observation_seconds": OBSERVATION_SECONDS,
        "board_access": False,
        "board_reset": False,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "t1_access": "SSH_READ_ONLY",
        "t1_mutation": False,
    }

    try:
        manager_before = manager_snapshot(args.t1_target)
        if not manager_before["running"]:
            raise StopExecution("Manager is not running")

        cursor_before_payload = canonical_snapshot(args.t1_target)
        if cursor_before_payload.get("status") != "FOUND":
            raise StopExecution(
                f"Board B canonical cursor unavailable: {cursor_before_payload.get('status')}"
            )
        cursor_before = cursor_before_payload["cursor"]
        if cursor_before.get("last_source") != "direct":
            raise StopExecution("Board B is not Direct at observation start")

        time.sleep(OBSERVATION_SECONDS)

        cursor_after_payload = canonical_snapshot(args.t1_target)
        manager_after = manager_snapshot(args.t1_target)
        if cursor_after_payload.get("status") != "FOUND":
            raise StopExecution(
                f"Board B canonical cursor unavailable at end: {cursor_after_payload.get('status')}"
            )
        cursor_after = cursor_after_payload["cursor"]

        if not manager_after["running"]:
            raise StopExecution("Manager is not running at observation end")
        if manager_before["restart_count"] != manager_after["restart_count"]:
            raise StopExecution("Manager restart count changed")
        if manager_before["started_at"] != manager_after["started_at"]:
            raise StopExecution("Manager StartedAt changed")

        if cursor_after.get("last_source") != "direct":
            raise StopExecution("Board B is not Direct at observation end")
        if cursor_before.get("boot_session_hex") != cursor_after.get("boot_session_hex"):
            raise StopExecution("Board B boot session changed during observation")

        seq_before = int(cursor_before["seq"])
        seq_after = int(cursor_after["seq"])
        seq_delta = seq_after - seq_before
        if seq_delta < MIN_SEQ_DELTA:
            raise StopExecution("Board B canonical seq did not advance enough")

        before_time = parse_utc(str(cursor_before["updated_at"]))
        after_time = parse_utc(str(cursor_after["updated_at"]))
        if after_time <= before_time:
            raise StopExecution("Board B canonical updated_at did not advance")

        result.update(
            {
                "status": "PASS",
                "manager_running": True,
                "manager_restart_count_before": manager_before["restart_count"],
                "manager_restart_count_after": manager_after["restart_count"],
                "manager_started_at_unchanged": True,
                "board_b_cursor_before": "FOUND",
                "board_b_cursor_after": "FOUND",
                "board_b_source_before": cursor_before["last_source"],
                "board_b_source_after": cursor_after["last_source"],
                "board_b_boot_session_sha256": sha256_text(
                    str(cursor_before["boot_session_hex"])
                ),
                "board_b_same_boot": True,
                "board_b_seq_before": seq_before,
                "board_b_seq_after": seq_after,
                "board_b_seq_delta": seq_delta,
                "board_b_updated_at_before": cursor_before["updated_at"],
                "board_b_updated_at_after": cursor_after["updated_at"],
                "board_b_canonical_advanced": True,
                "postwrite_direct_baseline": "PASS",
            }
        )
        write_json(output, result)

        print("POSTWRITE_DIRECT_BASELINE=PASS")
        print("T1_MANAGER_RUNNING=true")
        print(f"MANAGER_RESTART_COUNT_BEFORE={manager_before['restart_count']}")
        print(f"MANAGER_RESTART_COUNT_AFTER={manager_after['restart_count']}")
        print("MANAGER_STARTED_AT_UNCHANGED=true")
        print("BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND")
        print("BOARD_B_CANONICAL_CURSOR_AFTER=FOUND")
        print(f"BOARD_B_SOURCE_BEFORE={cursor_before['last_source']}")
        print(f"BOARD_B_SOURCE_AFTER={cursor_after['last_source']}")
        print(f"BOARD_B_SEQ_BEFORE={seq_before}")
        print(f"BOARD_B_SEQ_AFTER={seq_after}")
        print(f"BOARD_B_SEQ_DELTA={seq_delta}")
        print("BOARD_B_SAME_BOOT=true")
        print("BOARD_B_CANONICAL_ADVANCED=true")
        print("BOARD_ACCESS=false")
        print("BOARD_RESET=false")
        print("BOARD_FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false")
        print("T1_MUTATION=false")
        return 0

    except (StopExecution, ValueError, KeyError, TypeError) as exc:
        result["stop_reason"] = str(exc)
        write_json(output, result)
        print(f"STOP={exc}", file=sys.stderr)
        print("BOARD_ACCESS=false", file=sys.stderr)
        print("BOARD_RESET=false", file=sys.stderr)
        print("BOARD_FLASH_WRITE=false", file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false", file=sys.stderr)
        print("APPLICATION_SERIAL_OPEN=false", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
