from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "n3w.kf096.pr437-177468e.broker-path-readonly-forensic/1"

PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
CANONICAL_ANCHOR = "2026-09-20T14:35:06.070Z"

MANAGER_CONTAINER = "greenhouse-manager"
BROKER_COMPOSE_SERVICE = "broker"
BROKER_COMPOSE_PROJECT = "n3wfc4"

ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")


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


def resolve_board_b_runtime(t1_target: str) -> dict[str, str]:
    remote_python = r'''
import hashlib
import json
import os
import sqlite3
import sys

expected = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
replay_path = os.environ.get("GH_N3W_REPLAY_DB_PATH")
system_id = os.environ.get("GH_SYSTEM_ID")
if not replay_path:
    print(json.dumps({"status":"STOP","reason":"GH_N3W_REPLAY_DB_PATH missing"}))
    sys.exit(0)
if not system_id:
    print(json.dumps({"status":"STOP","reason":"GH_SYSTEM_ID missing"}))
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
    "boot_session_hex":matches[0]["boot_session_hex"],
    "seq":matches[0]["seq"],
    "last_source":matches[0]["last_source"],
    "updated_at":matches[0]["updated_at"],
}, separators=(",",":")))
'''
    raw = remote(
        t1_target,
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(remote_python)}",
    ).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Board B runtime resolver returned invalid JSON") from exc
    if payload.get("status") != "FOUND":
        raise StopExecution(f"Board B runtime resolver status={payload.get('status')}")
    node_id = str(payload["node_id"])
    if sha256_text(node_id) != BOARD_B_NODE_ID_SHA256:
        raise StopExecution("resolved node_id does not match frozen Board B hash")
    return {
        "system_id": str(payload["system_id"]),
        "node_id": node_id,
        "boot_session_hex": str(payload["boot_session_hex"]),
        "seq": str(payload["seq"]),
        "last_source": str(payload["last_source"]),
        "updated_at": str(payload["updated_at"]),
    }


def container_inventory(t1_target: str) -> list[dict[str, Any]]:
    ids = remote(t1_target, "docker ps -aq --no-trunc").splitlines()
    ids = [value.strip() for value in ids if value.strip()]
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


def select_broker(items: list[dict[str, Any]]) -> dict[str, Any]:
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
    return matches[0]


def broker_public_state(broker: dict[str, Any]) -> tuple[str, dict[str, object]]:
    broker_id = str(broker.get("Id") or "")
    if not broker_id:
        raise StopExecution("Broker container ID missing")
    state = broker.get("State") if isinstance(broker.get("State"), dict) else {}
    host = broker.get("HostConfig") if isinstance(broker.get("HostConfig"), dict) else {}
    config = broker.get("Config") if isinstance(broker.get("Config"), dict) else {}
    log_config = host.get("LogConfig") if isinstance(host.get("LogConfig"), dict) else {}
    return broker_id, {
        "running": state.get("Running") is True,
        "restart_count": int(broker.get("RestartCount") or 0),
        "started_at": str(state.get("StartedAt") or ""),
        "network_mode": str(host.get("NetworkMode") or ""),
        "image_sha256": sha256_text(str(config.get("Image") or "")),
        "log_driver": str(log_config.get("Type") or ""),
    }


def broker_config(t1_target: str, broker_id: str) -> str:
    return remote(
        t1_target,
        f"docker exec {shlex.quote(broker_id)} cat /mosquitto/config/mosquitto.conf",
    )


def parse_broker_config(text: str) -> dict[str, object]:
    dynsec_paths: list[str] = []
    dynamic_plugin = False
    connection_messages: str | None = None
    log_types: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        key = parts[0]
        value = parts[1].strip() if len(parts) == 2 else ""
        if key in {"plugin", "global_plugin"} and "dynamic_security" in value:
            dynamic_plugin = True
        elif key == "plugin_opt_config_file":
            dynsec_paths.append(value)
        elif key == "connection_messages":
            connection_messages = value.lower()
        elif key == "log_type":
            log_types.append(value.lower())
    unique = sorted(set(dynsec_paths))
    if not dynamic_plugin or len(unique) != 1 or not unique[0].startswith("/"):
        raise StopExecution(
            f"cannot derive active DynSec path: plugin={dynamic_plugin} paths={unique}"
        )
    return {
        "dynsec_path": unique[0],
        "connection_messages": connection_messages or "UNSPECIFIED",
        "log_types": sorted(set(log_types)),
    }


def role_names(client: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for role in client.get("roles") or []:
        if isinstance(role, str):
            names.append(role)
        elif isinstance(role, dict) and isinstance(role.get("rolename"), str):
            names.append(str(role["rolename"]))
    return names


def dynsec_analysis(
    raw: str, *, system_id: str, node_id: str
) -> dict[str, object]:
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopExecution("Dynamic Security JSON is invalid") from exc
    if not isinstance(state, dict):
        raise StopExecution("Dynamic Security root is not an object")

    clients = [item for item in state.get("clients") or [] if isinstance(item, dict)]
    roles = {
        str(item["rolename"]): item
        for item in state.get("roles") or []
        if isinstance(item, dict) and isinstance(item.get("rolename"), str)
    }

    expected_username = "ghn_" + node_id
    expected_role = f"gh-node-{system_id}-{node_id}"
    expected_ingress = f"gh/v1/{system_id}/ingress/node/{node_id}/#"

    exact = [
        item
        for item in clients
        if item.get("clientid") == node_id and item.get("username") == expected_username
    ]
    if len(exact) != 1:
        raise StopExecution(f"exact Board B DynSec client count={len(exact)}, expected 1")

    client = exact[0]
    assigned_roles = role_names(client)
    role = roles.get(expected_role)
    role_present = isinstance(role, dict)
    role_assigned = expected_role in assigned_roles

    direct_publish_allow = False
    if isinstance(role, dict):
        for acl in role.get("acls") or []:
            if not isinstance(acl, dict):
                continue
            if (
                acl.get("acltype") == "publishClientSend"
                and acl.get("topic") == expected_ingress
                and acl.get("allow") is True
            ):
                direct_publish_allow = True
                break

    disabled = client.get("disabled")
    return {
        "exact_client_count": 1,
        "client_disabled": disabled if isinstance(disabled, bool) else "UNSPECIFIED",
        "expected_role_present": role_present,
        "expected_role_assigned": role_assigned,
        "direct_publish_allow": direct_publish_allow,
        "assigned_role_count": len(assigned_roles),
    }


def exact_log_analysis(
    text: str, *, node_id: str, username: str
) -> dict[str, object]:
    exact_lines: list[str] = []
    connection_count = 0
    disconnect_count = 0
    received_publish_count = 0
    puback_count = 0
    auth_or_acl_failure_count = 0
    protocol_or_socket_error_count = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None

    node_marker = node_id.casefold()
    user_marker = username.casefold()

    for line in text.splitlines():
        folded = line.casefold()
        if node_marker not in folded and user_marker not in folded:
            continue
        exact_lines.append(line)
        stamp = ISO_RE.search(line)
        if stamp:
            if first_timestamp is None:
                first_timestamp = stamp.group(0)
            last_timestamp = stamp.group(0)

        if "new client connected" in folded and node_marker in folded:
            connection_count += 1
        if "client " + node_marker in folded and "disconnected" in folded:
            disconnect_count += 1
        if "received publish from " + node_marker in folded:
            received_publish_count += 1
        if "sending puback to " + node_marker in folded:
            puback_count += 1

        if any(
            marker in folded
            for marker in (
                "not authorised",
                "not authorized",
                "authentication",
                "bad user name or password",
                "acl denied",
                "permission denied",
                "access denied",
            )
        ):
            auth_or_acl_failure_count += 1

        if any(
            marker in folded
            for marker in (
                "protocol error",
                "socket error",
                "connection lost",
                "keepalive timeout",
                "out of memory",
            )
        ):
            protocol_or_socket_error_count += 1

    if received_publish_count > 0:
        classification = "BROKER_RECEIVED_DIRECT_PUBLISH_AFTER_ANCHOR"
    elif auth_or_acl_failure_count > 0:
        classification = "EXACT_CLIENT_AUTH_OR_ACL_FAILURE_OBSERVED"
    elif connection_count > 0 or disconnect_count > 0 or protocol_or_socket_error_count > 0:
        classification = "EXACT_CLIENT_BROKER_SESSION_ACTIVITY_OBSERVED"
    else:
        classification = "NO_EXACT_CLIENT_BROKER_LOG_EVIDENCE"

    return {
        "exact_client_log_line_count": len(exact_lines),
        "connection_count": connection_count,
        "disconnect_count": disconnect_count,
        "received_publish_count": received_publish_count,
        "puback_count": puback_count,
        "auth_or_acl_failure_count": auth_or_acl_failure_count,
        "protocol_or_socket_error_count": protocol_or_socket_error_count,
        "first_exact_client_log_timestamp": first_timestamp,
        "last_exact_client_log_timestamp": last_timestamp,
        "classification": classification,
    }


def generic_log_analysis(text: str) -> dict[str, int]:
    lines = text.splitlines()
    auth = 0
    errors = 0
    received_publish = 0
    for line in lines:
        folded = line.casefold()
        if any(
            marker in folded
            for marker in (
                "not authorised",
                "not authorized",
                "authentication",
                "bad user name or password",
                "acl denied",
                "permission denied",
                "access denied",
            )
        ):
            auth += 1
        if any(marker in folded for marker in ("error", "failed", "failure")):
            errors += 1
        if "received publish from " in folded:
            received_publish += 1
    return {
        "total_log_line_count": len(lines),
        "generic_auth_or_acl_failure_line_count": auth,
        "generic_error_line_count": errors,
        "generic_received_publish_line_count": received_publish,
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
        "board_access": False,
        "board_reset": False,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "t1_access": "SSH_READ_ONLY",
        "t1_mutation": False,
        "mqtt_test_publish": False,
        "mqtt_extra_subscriber": False,
    }

    try:
        manager = manager_state(args.t1_target)
        if not manager["running"]:
            raise StopExecution("Manager is not running")

        runtime = resolve_board_b_runtime(args.t1_target)
        if runtime["updated_at"] != CANONICAL_ANCHOR:
            raise StopExecution(
                "Board B canonical anchor changed; rebind before Broker forensic"
            )
        if runtime["seq"] != "49" or runtime["last_source"] != "direct":
            raise StopExecution("Board B canonical anchor tuple changed")

        broker = select_broker(container_inventory(args.t1_target))
        broker_id, broker_state = broker_public_state(broker)
        if broker_state["running"] is not True:
            raise StopExecution("Broker is not running")

        config = parse_broker_config(broker_config(args.t1_target, broker_id))
        dynsec_raw = remote(
            args.t1_target,
            f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(str(config['dynsec_path']))}",
        )
        dynsec = dynsec_analysis(
            dynsec_raw,
            system_id=runtime["system_id"],
            node_id=runtime["node_id"],
        )

        logs = remote(
            args.t1_target,
            "docker logs --timestamps --since "
            + shlex.quote(CANONICAL_ANCHOR)
            + " "
            + shlex.quote(broker_id)
            + " 2>&1",
        )
        exact = exact_log_analysis(
            logs,
            node_id=runtime["node_id"],
            username="ghn_" + runtime["node_id"],
        )
        generic = generic_log_analysis(logs)

        anchor_time = parse_iso(CANONICAL_ANCHOR)
        broker_started_raw = str(broker_state["started_at"])
        broker_started = parse_iso(broker_started_raw) if broker_started_raw else None
        broker_started_before_anchor = (
            broker_started is not None and broker_started <= anchor_time
        )

        public_runtime = {
            "system_id_sha256": sha256_text(runtime["system_id"]),
            "node_id_sha256": BOARD_B_NODE_ID_SHA256,
            "boot_session_sha256": sha256_text(runtime["boot_session_hex"]),
            "seq": int(runtime["seq"]),
            "last_source": runtime["last_source"],
            "updated_at": runtime["updated_at"],
        }

        result.update(
            {
                "status": "PASS",
                "manager": manager,
                "board_b_runtime_anchor": public_runtime,
                "broker": broker_state,
                "broker_started_before_anchor": broker_started_before_anchor,
                "broker_config": {
                    "connection_messages": config["connection_messages"],
                    "log_types": config["log_types"],
                    "dynamic_security_enabled": True,
                },
                "board_b_dynsec": dynsec,
                "exact_client_log_evidence": exact,
                "generic_broker_log_evidence": generic,
            }
        )
        write_json(output, result)

        print("BROKER_PATH_READONLY_FORENSIC=PASS")
        print(f"T1_MANAGER_RUNNING={str(manager['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT={manager['restart_count']}")
        print(f"BROKER_RUNNING={str(broker_state['running']).lower()}")
        print(f"BROKER_RESTART_COUNT={broker_state['restart_count']}")
        print(
            "BROKER_STARTED_BEFORE_CANONICAL_ANCHOR="
            + str(broker_started_before_anchor).lower()
        )
        print(f"BROKER_CONNECTION_MESSAGES={config['connection_messages']}")
        print("BROKER_LOG_TYPES=" + json.dumps(config["log_types"], separators=(",",":")))

        print(f"DYNSEC_EXACT_CLIENT_COUNT={dynsec['exact_client_count']}")
        print(f"DYNSEC_CLIENT_DISABLED={dynsec['client_disabled']}")
        print(f"DYNSEC_EXPECTED_ROLE_PRESENT={str(dynsec['expected_role_present']).lower()}")
        print(f"DYNSEC_EXPECTED_ROLE_ASSIGNED={str(dynsec['expected_role_assigned']).lower()}")
        print(f"DYNSEC_DIRECT_PUBLISH_ALLOW={str(dynsec['direct_publish_allow']).lower()}")

        print(f"EXACT_CLIENT_LOG_LINE_COUNT={exact['exact_client_log_line_count']}")
        print(f"EXACT_CLIENT_CONNECTION_COUNT={exact['connection_count']}")
        print(f"EXACT_CLIENT_DISCONNECT_COUNT={exact['disconnect_count']}")
        print(f"EXACT_CLIENT_RECEIVED_PUBLISH_COUNT={exact['received_publish_count']}")
        print(f"EXACT_CLIENT_PUBACK_COUNT={exact['puback_count']}")
        print(
            "EXACT_CLIENT_AUTH_OR_ACL_FAILURE_COUNT="
            f"{exact['auth_or_acl_failure_count']}"
        )
        print(
            "EXACT_CLIENT_PROTOCOL_OR_SOCKET_ERROR_COUNT="
            f"{exact['protocol_or_socket_error_count']}"
        )
        print(
            "EXACT_CLIENT_FIRST_LOG_TIMESTAMP="
            f"{exact['first_exact_client_log_timestamp'] or 'NONE'}"
        )
        print(
            "EXACT_CLIENT_LAST_LOG_TIMESTAMP="
            f"{exact['last_exact_client_log_timestamp'] or 'NONE'}"
        )
        print(f"BROKER_PATH_CLASSIFICATION={exact['classification']}")

        print(
            "GENERIC_BROKER_AUTH_OR_ACL_FAILURE_LINE_COUNT="
            f"{generic['generic_auth_or_acl_failure_line_count']}"
        )
        print(f"GENERIC_BROKER_ERROR_LINE_COUNT={generic['generic_error_line_count']}")

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
