from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "n3w.kf096.pr437-177468e.disconnect-context-t1-forensic/1"

PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"

CANONICAL_ANCHOR = "2026-09-20T14:35:06.070Z"
EXACT_CLIENT_DISCONNECT = "2026-09-20T14:35:30.732623821Z"

MANAGER_CONTAINER = "greenhouse-manager"
BROKER_COMPOSE_SERVICE = "broker"
BROKER_COMPOSE_PROJECT = "n3wfc4"

WINDOW_BEFORE_SECONDS = 90
WINDOW_AFTER_SECONDS = 180

ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
NEW_CLIENT_RE = re.compile(r"New client connected from .* as ([^ ]+) ")
DISCONNECT_RE = re.compile(r"Client ([^ ]+) disconnected(?:\.| |$)", re.I)


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
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=1",
            t1_target,
            command,
        ],
        redact={t1_target},
    )


def parse_iso(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StopExecution(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise StopExecution("timestamp is not timezone-aware")
    return parsed.astimezone(dt.timezone.utc)


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


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


def manager_private_runtime(t1_target: str) -> dict[str, str]:
    remote_python = r'''
import hashlib
import json
import os
import sqlite3
import sys

expected = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
replay_path = os.environ.get("GH_N3W_REPLAY_DB_PATH")
system_id = os.environ.get("GH_SYSTEM_ID")
manager_client_id = os.environ.get("GH_MQTT_CLIENT_ID")
mqtt_port = os.environ.get("GH_MQTT_PORT")
if not replay_path or not system_id or not manager_client_id or not mqtt_port:
    print(json.dumps({"status":"STOP","reason":"required Manager runtime environment missing"}))
    sys.exit(0)

db = sqlite3.connect("file:" + replay_path + "?mode=ro", uri=True)
db.row_factory = sqlite3.Row
rows = db.execute(
    "SELECT node_id, boot_session_hex, seq, last_source, updated_at "
    "FROM n3w_canonical_cursors"
).fetchall()
matches = []
for row in rows:
    node_id = row["node_id"]
    if hashlib.sha256(node_id.encode("utf-8")).hexdigest() == expected:
        matches.append(dict(row))

if len(matches) != 1:
    print(json.dumps({
        "status":"NOT_FOUND" if not matches else "AMBIGUOUS",
        "count":len(matches),
    }, separators=(",",":")))
    sys.exit(0)

print(json.dumps({
    "status":"FOUND",
    "system_id":system_id,
    "node_id":matches[0]["node_id"],
    "seq":matches[0]["seq"],
    "last_source":matches[0]["last_source"],
    "updated_at":matches[0]["updated_at"],
    "manager_client_id":manager_client_id,
    "mqtt_port":mqtt_port,
}, separators=(",",":")))
'''
    raw = remote(
        t1_target,
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(remote_python)}",
    ).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Manager private runtime returned invalid JSON") from exc
    if payload.get("status") != "FOUND":
        raise StopExecution(f"Manager private runtime status={payload.get('status')}")
    node_id = str(payload["node_id"])
    if sha256_text(node_id) != BOARD_B_NODE_ID_SHA256:
        raise StopExecution("resolved node_id does not match frozen Board B hash")
    return {
        "system_id": str(payload["system_id"]),
        "node_id": node_id,
        "seq": str(payload["seq"]),
        "last_source": str(payload["last_source"]),
        "updated_at": str(payload["updated_at"]),
        "manager_client_id": str(payload["manager_client_id"]),
        "mqtt_port": str(payload["mqtt_port"]),
    }


def manager_socket_samples(t1_target: str) -> dict[str, object]:
    remote_python = r'''
import json
import os
import re
import time

port_text = os.environ.get("GH_MQTT_PORT")
if not port_text:
    print(json.dumps({"status":"STOP","reason":"GH_MQTT_PORT missing"}))
    raise SystemExit(0)
port = int(port_text)

socket_re = re.compile(r"^socket:\[(\d+)\]$")

def owned_inodes():
    out = set()
    try:
        names = os.listdir("/proc/1/fd")
    except OSError:
        return out
    for name in names:
        try:
            target = os.readlink("/proc/1/fd/" + name)
        except OSError:
            continue
        match = socket_re.match(target)
        if match:
            out.add(match.group(1))
    return out

def established_mqtt_inodes():
    owned = owned_inodes()
    matched = set()
    for table in ("/proc/1/net/tcp", "/proc/1/net/tcp6"):
        try:
            lines = open(table, "r", encoding="ascii").read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "01":
                continue
            try:
                remote_port = int(fields[2].rsplit(":", 1)[1], 16)
            except ValueError:
                continue
            inode = fields[9]
            if remote_port == port and inode in owned:
                matched.add(inode)
    return matched

samples = []
for index in range(3):
    current = established_mqtt_inodes()
    samples.append(sorted(current))
    if index != 2:
        time.sleep(1.0)

sets = [set(item) for item in samples]
stable = bool(sets[0] and sets[0] & sets[1] & sets[2])
print(json.dumps({
    "status":"PASS",
    "sample_counts":[len(item) for item in samples],
    "stable_same_inode_all_samples":stable,
}, separators=(",",":")))
'''
    raw = remote(
        t1_target,
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(remote_python)}",
    ).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Manager socket sampler returned invalid JSON") from exc
    if payload.get("status") != "PASS":
        raise StopExecution(f"Manager socket sampler status={payload.get('status')}")
    return payload


def container_inventory(t1_target: str) -> list[dict[str, Any]]:
    ids = [line.strip() for line in remote(t1_target, "docker ps -aq --no-trunc").splitlines() if line.strip()]
    if not ids:
        raise StopExecution("Docker container inventory is empty")
    raw = remote(
        t1_target,
        "docker inspect " + " ".join(shlex.quote(value) for value in ids),
    )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Docker inspect inventory returned invalid JSON") from exc
    if not isinstance(value, list):
        raise StopExecution("Docker inspect inventory is not a list")
    return [item for item in value if isinstance(item, dict)]


def select_broker(items: list[dict[str, Any]]) -> tuple[str, dict[str, object]]:
    matches: list[dict[str, Any]] = []
    for item in items:
        config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
        state = item.get("State") if isinstance(item.get("State"), dict) else {}
        if (
            labels.get("com.docker.compose.service") == BROKER_COMPOSE_SERVICE
            and labels.get("com.docker.compose.project") == BROKER_COMPOSE_PROJECT
            and state.get("Running") is True
        ):
            matches.append(item)
    if len(matches) != 1:
        raise StopExecution(f"running authoritative Broker count={len(matches)}, expected 1")
    broker = matches[0]
    broker_id = str(broker.get("Id") or "")
    if not broker_id:
        raise StopExecution("Broker container ID missing")
    state = broker.get("State") if isinstance(broker.get("State"), dict) else {}
    return broker_id, {
        "running": state.get("Running") is True,
        "restart_count": int(broker.get("RestartCount") or 0),
        "started_at": str(state.get("StartedAt") or ""),
    }


def broker_log_window(t1_target: str, broker_id: str) -> tuple[str, str, str]:
    center = parse_iso(EXACT_CLIENT_DISCONNECT)
    start = center - dt.timedelta(seconds=WINDOW_BEFORE_SECONDS)
    end = center + dt.timedelta(seconds=WINDOW_AFTER_SECONDS)
    start_text = iso_z(start)
    end_text = iso_z(end)
    logs = remote(
        t1_target,
        "docker logs --timestamps --since "
        + shlex.quote(start_text)
        + " --until "
        + shlex.quote(end_text)
        + " "
        + shlex.quote(broker_id)
        + " 2>&1",
    )
    return start_text, end_text, logs


def line_time(line: str) -> dt.datetime | None:
    match = ISO_RE.search(line)
    if match is None:
        return None
    try:
        return parse_iso(match.group(0))
    except StopExecution:
        return None


def generic_error_category(line: str) -> str | None:
    folded = line.casefold()
    if not any(marker in folded for marker in ("error", "failed", "failure", "denied", "authoris", "authentic")):
        return None
    if any(marker in folded for marker in ("ssl", "tls", "openssl", "certificate", "handshake")):
        return "TLS_SSL"
    if any(marker in folded for marker in ("not authorised", "not authorized", "acl", "authentication", "bad user name", "password", "denied")):
        return "AUTH_ACL"
    if any(marker in folded for marker in ("protocol", "malformed", "packet")):
        return "PROTOCOL"
    if any(marker in folded for marker in ("socket", "network", "connection", "broken pipe", "reset by peer", "timed out", "timeout")):
        return "SOCKET_NETWORK"
    if any(marker in folded for marker in ("memory", "resource", "too many", "file descriptor")):
        return "RESOURCE"
    if any(marker in folded for marker in ("config", "listener", "bind", "address already in use", "persistence")):
        return "BROKER_RUNTIME"
    return "OTHER_ERROR"


def analyze_window(logs: str, *, board_id: str, manager_id: str) -> dict[str, object]:
    center = parse_iso(EXACT_CLIENT_DISCONNECT)
    exact_board_disconnects: list[str] = []
    exact_board_connects_after: list[str] = []
    exact_board_connects_before: list[str] = []
    manager_disconnects: list[str] = []
    manager_connects: list[str] = []
    other_disconnect_ids: set[str] = set()
    other_connect_ids: set[str] = set()
    error_categories: Counter[str] = Counter()
    error_timestamps: list[str] = []
    near_5_other_disconnects = 0
    near_30_other_disconnects = 0
    near_5_errors = 0
    near_30_errors = 0

    for line in logs.splitlines():
        stamp = line_time(line)
        folded = line.casefold()

        connection = NEW_CLIENT_RE.search(line)
        if connection is not None:
            cid = connection.group(1)
            if cid == board_id:
                if stamp is not None and stamp > center:
                    exact_board_connects_after.append(iso_z(stamp))
                else:
                    exact_board_connects_before.append(iso_z(stamp) if stamp else "UNKNOWN")
            elif cid == manager_id:
                manager_connects.append(iso_z(stamp) if stamp else "UNKNOWN")
            else:
                other_connect_ids.add(cid)

        disconnect = DISCONNECT_RE.search(line)
        if disconnect is not None:
            cid = disconnect.group(1)
            if cid == board_id:
                exact_board_disconnects.append(iso_z(stamp) if stamp else "UNKNOWN")
            elif cid == manager_id:
                manager_disconnects.append(iso_z(stamp) if stamp else "UNKNOWN")
            else:
                other_disconnect_ids.add(cid)
                if stamp is not None:
                    delta = abs((stamp - center).total_seconds())
                    if delta <= 5:
                        near_5_other_disconnects += 1
                    if delta <= 30:
                        near_30_other_disconnects += 1

        category = generic_error_category(line)
        if category is not None:
            error_categories[category] += 1
            if stamp is not None:
                error_timestamps.append(iso_z(stamp))
                delta = abs((stamp - center).total_seconds())
                if delta <= 5:
                    near_5_errors += 1
                if delta <= 30:
                    near_30_errors += 1

    mass_disconnect_near_event = near_5_other_disconnects >= 2 or near_30_other_disconnects >= 3
    broker_error_cluster_near_event = near_5_errors >= 1 or near_30_errors >= 2

    if exact_board_connects_after:
        board_reconnect_class = "RECONNECT_OBSERVED"
    else:
        board_reconnect_class = "NO_RECONNECT_LOG_OBSERVED"

    if manager_disconnects:
        manager_window_class = "MANAGER_DISCONNECT_OBSERVED"
    else:
        manager_window_class = "NO_MANAGER_DISCONNECT_LOG_OBSERVED"

    return {
        "board_disconnect_count": len(exact_board_disconnects),
        "board_disconnect_timestamps": exact_board_disconnects,
        "board_connection_before_count": len(exact_board_connects_before),
        "board_connection_after_count": len(exact_board_connects_after),
        "board_connection_after_timestamps": exact_board_connects_after,
        "board_reconnect_classification": board_reconnect_class,
        "manager_disconnect_count": len(manager_disconnects),
        "manager_connection_count": len(manager_connects),
        "manager_window_classification": manager_window_class,
        "other_unique_disconnect_client_count": len(other_disconnect_ids),
        "other_unique_connect_client_count": len(other_connect_ids),
        "other_disconnect_count_within_5s": near_5_other_disconnects,
        "other_disconnect_count_within_30s": near_30_other_disconnects,
        "mass_disconnect_near_event": mass_disconnect_near_event,
        "generic_error_categories": dict(sorted(error_categories.items())),
        "generic_error_timestamps": error_timestamps,
        "generic_error_count_within_5s": near_5_errors,
        "generic_error_count_within_30s": near_30_errors,
        "broker_error_cluster_near_event": broker_error_cluster_near_event,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "canonical_anchor": CANONICAL_ANCHOR,
        "exact_client_disconnect": EXACT_CLIENT_DISCONNECT,
        "board_access": False,
        "board_reset": False,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "mqtt_test_publish": False,
        "mqtt_extra_subscriber": False,
        "t1_access": "SSH_READ_ONLY",
        "t1_mutation": False,
    }

    try:
        manager = manager_state(args.t1_target)
        if not manager["running"]:
            raise StopExecution("Manager is not running")

        private = manager_private_runtime(args.t1_target)
        if private["updated_at"] != CANONICAL_ANCHOR:
            raise StopExecution("Board B canonical anchor changed; rebind before context forensic")
        if private["seq"] != "49" or private["last_source"] != "direct":
            raise StopExecution("Board B canonical anchor tuple changed")

        socket_samples = manager_socket_samples(args.t1_target)

        broker_id, broker = select_broker(container_inventory(args.t1_target))
        if not broker["running"]:
            raise StopExecution("Broker is not running")
        if parse_iso(str(broker["started_at"])) > parse_iso(CANONICAL_ANCHOR):
            raise StopExecution("Broker started after canonical anchor")

        start, end, logs = broker_log_window(args.t1_target, broker_id)
        analysis = analyze_window(
            logs,
            board_id=private["node_id"],
            manager_id=private["manager_client_id"],
        )

        if analysis["board_disconnect_count"] < 1:
            raise StopExecution("exact Board B disconnect missing from bounded log window")

        if analysis["mass_disconnect_near_event"]:
            context_classification = "BROKER_WIDE_CLIENT_CHURN_NEAR_BOARD_B_DISCONNECT"
        elif analysis["broker_error_cluster_near_event"]:
            context_classification = "BROKER_ERROR_CLUSTER_NEAR_BOARD_B_DISCONNECT"
        elif analysis["manager_disconnect_count"] > 0:
            context_classification = "MANAGER_AND_BOARD_B_SESSION_LOSS_IN_WINDOW"
        elif analysis["board_connection_after_count"] > 0:
            context_classification = "BOARD_B_RECONNECT_OBSERVED_AFTER_DISCONNECT"
        else:
            context_classification = "BOARD_B_ISOLATED_DISCONNECT_NO_RECONNECT_LOG_OBSERVED"

        public_private = {
            "system_id_sha256": sha256_text(private["system_id"]),
            "node_id_sha256": BOARD_B_NODE_ID_SHA256,
            "manager_client_id_sha256": sha256_text(private["manager_client_id"]),
            "mqtt_port": int(private["mqtt_port"]),
        }

        result.update(
            {
                "status": "PASS",
                "manager": manager,
                "manager_runtime_public": public_private,
                "manager_socket_samples": socket_samples,
                "broker": broker,
                "window_start": start,
                "window_end": end,
                "analysis": analysis,
                "context_classification": context_classification,
                "broker_publish_visibility": "NOT_AVAILABLE_AT_NOTICE_WARNING_ERROR_LOG_LEVEL",
            }
        )
        write_json(output, result)

        print("DISCONNECT_CONTEXT_T1_FORENSIC=PASS")
        print(f"T1_MANAGER_RUNNING={str(manager['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT={manager['restart_count']}")
        print(
            "MANAGER_MQTT_SOCKET_SAMPLE_COUNTS="
            + json.dumps(socket_samples["sample_counts"], separators=(",",":"))
        )
        print(
            "MANAGER_MQTT_SOCKET_STABLE_NOW="
            + str(socket_samples["stable_same_inode_all_samples"]).lower()
        )
        print(f"BROKER_RUNNING={str(broker['running']).lower()}")
        print(f"BROKER_RESTART_COUNT={broker['restart_count']}")
        print(f"FORENSIC_WINDOW_START={start}")
        print(f"FORENSIC_WINDOW_END={end}")

        print(f"BOARD_B_DISCONNECT_COUNT={analysis['board_disconnect_count']}")
        print(
            "BOARD_B_CONNECTION_BEFORE_DISCONNECT_COUNT="
            f"{analysis['board_connection_before_count']}"
        )
        print(
            "BOARD_B_CONNECTION_AFTER_DISCONNECT_COUNT="
            f"{analysis['board_connection_after_count']}"
        )
        print(
            "BOARD_B_RECONNECT_CLASSIFICATION="
            f"{analysis['board_reconnect_classification']}"
        )

        print(f"MANAGER_DISCONNECT_COUNT_IN_WINDOW={analysis['manager_disconnect_count']}")
        print(f"MANAGER_CONNECTION_COUNT_IN_WINDOW={analysis['manager_connection_count']}")
        print(
            "MANAGER_WINDOW_CLASSIFICATION="
            f"{analysis['manager_window_classification']}"
        )

        print(
            "OTHER_UNIQUE_DISCONNECT_CLIENT_COUNT="
            f"{analysis['other_unique_disconnect_client_count']}"
        )
        print(
            "OTHER_DISCONNECT_COUNT_WITHIN_5S="
            f"{analysis['other_disconnect_count_within_5s']}"
        )
        print(
            "OTHER_DISCONNECT_COUNT_WITHIN_30S="
            f"{analysis['other_disconnect_count_within_30s']}"
        )
        print(
            "MASS_DISCONNECT_NEAR_EVENT="
            + str(analysis["mass_disconnect_near_event"]).lower()
        )

        print(
            "GENERIC_ERROR_CATEGORIES="
            + json.dumps(analysis["generic_error_categories"], sort_keys=True, separators=(",",":"))
        )
        print(
            "GENERIC_ERROR_COUNT_WITHIN_5S="
            f"{analysis['generic_error_count_within_5s']}"
        )
        print(
            "GENERIC_ERROR_COUNT_WITHIN_30S="
            f"{analysis['generic_error_count_within_30s']}"
        )
        print(
            "BROKER_ERROR_CLUSTER_NEAR_EVENT="
            + str(analysis["broker_error_cluster_near_event"]).lower()
        )
        print(f"DISCONNECT_CONTEXT_CLASSIFICATION={context_classification}")
        print("BROKER_PUBLISH_VISIBILITY=NOT_AVAILABLE_AT_NOTICE_WARNING_ERROR_LOG_LEVEL")

        print("BOARD_ACCESS=false")
        print("BOARD_RESET=false")
        print("BOARD_FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false")
        print("MQTT_TEST_PUBLISH=false")
        print("MQTT_EXTRA_SUBSCRIBER=false")
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
        print("MQTT_TEST_PUBLISH=false", file=sys.stderr)
        print("MQTT_EXTRA_SUBSCRIBER=false", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
