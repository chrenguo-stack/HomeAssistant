from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCHEMA = "n3w.kf096.pr437-177468e.direct-stall-t1-forensic/1"
PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
MANAGER_CONTAINER = "greenhouse-manager"

ACCEPTED_RE = re.compile(r"Accepted simplified N3-W telemetry source=direct node=([^ ]+)")
REJECTED_RE = re.compile(r"Rejected simplified N3-W ingress source=direct node=([^ ]+) gateway=[^ ]+ code=([^ ]+)")
LIFECYCLE_REJECT_RE = re.compile(r"Rejected simplified Direct telemetry for retired or unassigned node=([^ ]+)")


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args: list[str], *, redact: set[str] | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        redactions = redact or set()
        safe = ["<REDACTED>" if item in redactions else item for item in args]
        detail = output.strip().splitlines()
        tail = detail[-1] if detail else f"rc={proc.returncode}"
        raise StopExecution(f"command failed: {' '.join(safe)} :: {tail}")
    return output


def remote(t1_target: str, command: str) -> str:
    return run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", t1_target, command],
        redact={t1_target},
    )


def manager_state(t1_target: str) -> dict[str, object]:
    fmt = "{{.State.Running}}\\t{{.RestartCount}}\\t{{.State.StartedAt}}"
    raw = remote(
        t1_target,
        "docker inspect --format " + shlex.quote(fmt) + f" {shlex.quote(MANAGER_CONTAINER)}",
    ).strip()
    parts = raw.split("\\t")
    if len(parts) != 3:
        raise StopExecution("unable to parse Manager state")
    try:
        restart_count = int(parts[1])
    except ValueError as exc:
        raise StopExecution("unable to parse Manager restart count") from exc
    return {
        "running": parts[0].strip().lower() == "true",
        "restart_count": restart_count,
        "started_at": parts[2].strip(),
    }


def durable_snapshot(t1_target: str) -> dict[str, object]:
    remote_python = r'''
import hashlib
import json
import os
import sqlite3
import sys

expected = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
replay_path = os.environ.get("GH_N3W_REPLAY_DB_PATH")
pairing_path = os.environ.get("GH_PAIRING_DB_PATH")
if not replay_path:
    print(json.dumps({"status":"STOP","reason":"GH_N3W_REPLAY_DB_PATH missing"}))
    sys.exit(0)
if not pairing_path:
    print(json.dumps({"status":"STOP","reason":"GH_PAIRING_DB_PATH missing"}))
    sys.exit(0)

replay = sqlite3.connect("file:" + replay_path + "?mode=ro", uri=True)
replay.row_factory = sqlite3.Row

rows = replay.execute(
    "SELECT node_id, boot_session_hex, seq, last_source, updated_at "
    "FROM n3w_canonical_cursors"
).fetchall()

matches = []
for row in rows:
    node_id = row["node_id"]
    if hashlib.sha256(node_id.encode("utf-8")).hexdigest() == expected:
        matches.append(row)

if len(matches) != 1:
    print(json.dumps({
        "status":"NOT_FOUND" if not matches else "AMBIGUOUS",
        "count":len(matches),
    }, separators=(",",":")))
    sys.exit(0)

row = matches[0]
node_id = row["node_id"]

state = replay.execute(
    "SELECT highest_session_hex FROM n3w_replay_state WHERE node_id = ?",
    (node_id,),
).fetchone()

last_seen = replay.execute(
    "SELECT boot_id, seq, committed_at "
    "FROM n3w_replay_seen WHERE node_id = ? "
    "ORDER BY committed_at DESC LIMIT 1",
    (node_id,),
).fetchone()

pairing = sqlite3.connect("file:" + pairing_path + "?mode=ro", uri=True)
pairing.row_factory = sqlite3.Row

registration = pairing.execute(
    "SELECT r.hardware_id, r.current_pairing_id, r.node_id, "
    "s.state AS pairing_state, s.pairing_epoch, s.last_seen_at "
    "FROM registrations AS r "
    "JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id "
    "WHERE r.node_id = ?",
    (node_id,),
).fetchone()

lease = pairing.execute(
    "SELECT state, updated_at FROM node_id_leases WHERE node_id = ?",
    (node_id,),
).fetchone()

def rowdict(value):
    return None if value is None else dict(value)

print(json.dumps({
    "status":"FOUND",
    "node_id":node_id,
    "canonical":{
        "boot_session_hex":row["boot_session_hex"],
        "seq":row["seq"],
        "last_source":row["last_source"],
        "updated_at":row["updated_at"],
    },
    "replay_state":rowdict(state),
    "replay_last_seen":rowdict(last_seen),
    "registration":rowdict(registration),
    "lease":rowdict(lease),
}, separators=(",",":")))
'''
    raw = remote(
        t1_target,
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(remote_python)}",
    ).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("durable snapshot returned invalid JSON") from exc


def manager_logs_since(t1_target: str, since: str) -> str:
    return remote(
        t1_target,
        "docker logs --timestamps --since " + shlex.quote(since)
        + f" {shlex.quote(MANAGER_CONTAINER)} 2>&1",
    )


def sanitize_durable(payload: dict[str, object]) -> tuple[str, dict[str, object]]:
    if payload.get("status") != "FOUND":
        raise StopExecution(f"Board B durable snapshot unavailable: {payload.get('status')}")
    node_id = str(payload["node_id"])
    if sha256_text(node_id) != BOARD_B_NODE_ID_SHA256:
        raise StopExecution("resolved node_id does not match frozen Board B hash")

    canonical = dict(payload["canonical"])
    replay_state = payload.get("replay_state")
    replay_last_seen = payload.get("replay_last_seen")
    registration = payload.get("registration")
    lease = payload.get("lease")

    safe: dict[str, object] = {
        "canonical": {
            "boot_session_sha256": sha256_text(str(canonical["boot_session_hex"])),
            "seq": canonical["seq"],
            "last_source": canonical["last_source"],
            "updated_at": canonical["updated_at"],
        },
        "replay_state": None,
        "replay_last_seen": None,
        "registration": None,
        "lease": lease,
    }

    if isinstance(replay_state, dict):
        safe["replay_state"] = {
            "highest_session_sha256": sha256_text(str(replay_state["highest_session_hex"]))
        }

    if isinstance(replay_last_seen, dict):
        safe["replay_last_seen"] = {
            "boot_id_sha256": sha256_text(str(replay_last_seen["boot_id"])),
            "seq": replay_last_seen["seq"],
            "committed_at": replay_last_seen["committed_at"],
        }

    if isinstance(registration, dict):
        safe["registration"] = {
            "hardware_id_sha256": sha256_text(str(registration["hardware_id"])),
            "pairing_id_sha256": sha256_text(str(registration["current_pairing_id"])),
            "node_id_sha256": sha256_text(str(registration["node_id"])),
            "pairing_state": registration["pairing_state"],
            "pairing_epoch": registration["pairing_epoch"],
            "pairing_last_seen_at": registration["last_seen_at"],
        }

    return node_id, safe


def classify_logs(logs: str, node_id: str) -> dict[str, object]:
    accepted = 0
    rejected = 0
    lifecycle_rejected = 0
    codes: Counter[str] = Counter()
    matched_lines = 0

    for line in logs.splitlines():
        if f"node={node_id}" not in line:
            continue

        match = ACCEPTED_RE.search(line)
        if match and match.group(1) == node_id:
            accepted += 1
            matched_lines += 1
            continue

        match = REJECTED_RE.search(line)
        if match and match.group(1) == node_id:
            rejected += 1
            codes[match.group(2)] += 1
            matched_lines += 1
            continue

        match = LIFECYCLE_REJECT_RE.search(line)
        if match and match.group(1) == node_id:
            lifecycle_rejected += 1
            matched_lines += 1

    if rejected > 0:
        classification = "DIRECT_ARRIVED_MANAGER_REJECTED"
    elif lifecycle_rejected > 0:
        classification = "DIRECT_ARRIVED_LIFECYCLE_REJECTED"
    elif accepted > 0:
        classification = "DIRECT_ACCEPTED_LOG_CURSOR_INCONSISTENT"
    else:
        classification = "NO_MANAGER_DIRECT_LOG_EVIDENCE_AFTER_CURSOR"

    return {
        "accepted_direct_count": accepted,
        "rejected_direct_count": rejected,
        "lifecycle_rejected_direct_count": lifecycle_rejected,
        "rejection_codes": dict(sorted(codes.items())),
        "matched_direct_log_line_count": matched_lines,
        "classification": classification,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1-target", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "application_sha256": APPLICATION_SHA256,
        "board_b_node_id_sha256": BOARD_B_NODE_ID_SHA256,
        "board_access": False,
        "board_reset": False,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "t1_access": "SSH_READ_ONLY",
        "t1_mutation": False,
    }

    try:
        manager = manager_state(args.t1_target)
        if not manager["running"]:
            raise StopExecution("Manager is not running")

        raw_snapshot = durable_snapshot(args.t1_target)
        node_id, safe_snapshot = sanitize_durable(raw_snapshot)

        canonical = safe_snapshot["canonical"]
        assert isinstance(canonical, dict)
        since = str(canonical["updated_at"])

        logs = manager_logs_since(args.t1_target, since)
        log_result = classify_logs(logs, node_id)

        result.update({
            "status": "PASS",
            "manager": manager,
            "durable": safe_snapshot,
            "manager_logs_since_canonical_updated_at": log_result,
        })
        write_json(output, result)

        print("DIRECT_STALL_T1_FORENSIC=PASS")
        print(f"T1_MANAGER_RUNNING={str(manager['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT={manager['restart_count']}")
        print(f"CANONICAL_SEQ={canonical['seq']}")
        print(f"CANONICAL_SOURCE={canonical['last_source']}")
        print(f"CANONICAL_UPDATED_AT={canonical['updated_at']}")

        replay_last = safe_snapshot.get("replay_last_seen")
        if isinstance(replay_last, dict):
            print(f"REPLAY_LAST_SEQ={replay_last['seq']}")
            print(f"REPLAY_LAST_COMMITTED_AT={replay_last['committed_at']}")
        else:
            print("REPLAY_LAST_SEQ=NONE")
            print("REPLAY_LAST_COMMITTED_AT=NONE")

        registration = safe_snapshot.get("registration")
        if isinstance(registration, dict):
            print(f"PAIRING_STATE={registration['pairing_state']}")
            print(f"PAIRING_EPOCH={registration['pairing_epoch']}")
        else:
            print("PAIRING_STATE=NOT_FOUND")

        lease = safe_snapshot.get("lease")
        if isinstance(lease, dict):
            print(f"NODE_LEASE_STATE={lease['state']}")
        else:
            print("NODE_LEASE_STATE=NOT_FOUND")

        print(f"ACCEPTED_DIRECT_COUNT={log_result['accepted_direct_count']}")
        print(f"REJECTED_DIRECT_COUNT={log_result['rejected_direct_count']}")
        print(f"LIFECYCLE_REJECTED_DIRECT_COUNT={log_result['lifecycle_rejected_direct_count']}")
        print("REJECTION_CODES=" + json.dumps(
            log_result["rejection_codes"], sort_keys=True, separators=(",",":")
        ))
        print(f"DIRECT_STALL_CLASSIFICATION={log_result['classification']}")
        print("BOARD_ACCESS=false")
        print("BOARD_RESET=false")
        print("BOARD_FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false")
        print("T1_MUTATION=false")
        return 0

    except (StopExecution, ValueError, KeyError, TypeError, AssertionError) as exc:
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
