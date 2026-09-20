from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "n3w.kf096.pr437-177468e.postwrite-manager-cursor-forensic/1"
EXPECTED_PRODUCT_SOURCE = "177468e290a207f2fb7f6c554aedf60b61373b4d"
EXPECTED_APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
EXPECTED_BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
MANAGER_CONTAINER = "greenhouse-manager"
OBSERVATION_SECONDS = 30


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def cursor_public(cursor: dict[str, object], observed_at: dt.datetime) -> dict[str, object]:
    updated = parse_utc(str(cursor["updated_at"]))
    return {
        "boot_session_sha256": sha256_text(str(cursor["boot_session_hex"])),
        "seq": int(cursor["seq"]),
        "last_source": cursor["last_source"],
        "updated_at": cursor["updated_at"],
        "age_seconds": round((observed_at - updated).total_seconds(), 3),
    }


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
        raise SystemExit("STOP=observation-seconds must remain exactly 30")

    output = Path(args.output)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "product_source": EXPECTED_PRODUCT_SOURCE,
        "application_sha256": EXPECTED_APPLICATION_SHA256,
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

        observed_before = utc_now()
        before_payload = canonical_snapshot(args.t1_target)
        if before_payload.get("status") != "FOUND":
            raise StopExecution(
                f"Board B canonical cursor unavailable: {before_payload.get('status')}"
            )
        before = before_payload["cursor"]
        before_public = cursor_public(before, observed_before)

        time.sleep(OBSERVATION_SECONDS)

        observed_after = utc_now()
        after_payload = canonical_snapshot(args.t1_target)
        manager_after = manager_snapshot(args.t1_target)
        if after_payload.get("status") != "FOUND":
            raise StopExecution(
                f"Board B canonical cursor unavailable at end: {after_payload.get('status')}"
            )
        after = after_payload["cursor"]
        after_public = cursor_public(after, observed_after)

        manager_continuity = (
            manager_after["running"]
            and manager_before["restart_count"] == manager_after["restart_count"]
            and manager_before["started_at"] == manager_after["started_at"]
        )
        same_boot = before["boot_session_hex"] == after["boot_session_hex"]
        seq_delta = int(after["seq"]) - int(before["seq"])
        updated_advanced = parse_utc(str(after["updated_at"])) > parse_utc(str(before["updated_at"]))
        source_before = before["last_source"]
        source_after = after["last_source"]

        if seq_delta > 0 and updated_advanced:
            activity = "ADVANCING"
        elif seq_delta == 0 and not updated_advanced:
            activity = "STALE"
        else:
            activity = "INCONSISTENT"

        result.update(
            {
                "status": "PASS",
                "manager_before": manager_before,
                "manager_after": manager_after,
                "manager_continuity": manager_continuity,
                "observed_at_before": iso_utc(observed_before),
                "observed_at_after": iso_utc(observed_after),
                "cursor_before": before_public,
                "cursor_after": after_public,
                "same_boot": same_boot,
                "seq_delta": seq_delta,
                "updated_at_advanced": updated_advanced,
                "source_before": source_before,
                "source_after": source_after,
                "cursor_activity": activity,
            }
        )
        write_json(output, result)

        print("FORENSIC_OBSERVATION=PASS")
        print(f"T1_MANAGER_RUNNING_BEFORE={str(manager_before['running']).lower()}")
        print(f"T1_MANAGER_RUNNING_AFTER={str(manager_after['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT_BEFORE={manager_before['restart_count']}")
        print(f"MANAGER_RESTART_COUNT_AFTER={manager_after['restart_count']}")
        print(f"MANAGER_CONTINUITY={str(manager_continuity).lower()}")
        print(f"BOARD_B_SOURCE_BEFORE={source_before}")
        print(f"BOARD_B_SOURCE_AFTER={source_after}")
        print(f"BOARD_B_SEQ_BEFORE={before_public['seq']}")
        print(f"BOARD_B_SEQ_AFTER={after_public['seq']}")
        print(f"BOARD_B_SEQ_DELTA={seq_delta}")
        print(f"BOARD_B_UPDATED_AT_BEFORE={before_public['updated_at']}")
        print(f"BOARD_B_UPDATED_AT_AFTER={after_public['updated_at']}")
        print(f"BOARD_B_CURSOR_AGE_SECONDS_BEFORE={before_public['age_seconds']}")
        print(f"BOARD_B_CURSOR_AGE_SECONDS_AFTER={after_public['age_seconds']}")
        print(f"BOARD_B_SAME_BOOT={str(same_boot).lower()}")
        print(f"BOARD_B_UPDATED_AT_ADVANCED={str(updated_advanced).lower()}")
        print(f"BOARD_B_CURSOR_ACTIVITY={activity}")
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
