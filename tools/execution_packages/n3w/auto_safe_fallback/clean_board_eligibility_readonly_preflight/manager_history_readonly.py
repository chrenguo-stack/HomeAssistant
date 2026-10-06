from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path, PurePosixPath

DEFAULT_REGISTRATION = "/var/lib/greenhouse-manager/registration.sqlite3"
DEFAULT_CREDENTIAL = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
DEFAULT_REPLAY = "/var/lib/greenhouse-manager/n3w/replay.sqlite3"
SCHEMA = "n3w.kf050.clean-board-manager-history-readonly/1"


class StopExecution(RuntimeError):
    pass


def run_json(args: list[str]) -> object:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise StopExecution(f"command failed rc={proc.returncode}: {' '.join(args[:3])}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise StopExecution("command returned invalid JSON") from exc


def env_map(document: dict[str, object]) -> dict[str, str]:
    config = document.get("Config")
    if not isinstance(config, dict):
        raise StopExecution("manager Config missing")
    raw = config.get("Env")
    if not isinstance(raw, list):
        raise StopExecution("manager Env missing")
    result: dict[str, str] = {}
    for item in raw:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def resolve_host_path(document: dict[str, object], container_path: str) -> Path:
    requested = PurePosixPath(container_path)
    if not requested.is_absolute():
        raise StopExecution("database path is not absolute")
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise StopExecution("manager mounts missing")
    matches: list[Path] = []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        source = mount.get("Source")
        destination = mount.get("Destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            continue
        try:
            relative = requested.relative_to(PurePosixPath(destination))
        except ValueError:
            continue
        matches.append(Path(source).joinpath(*relative.parts))
    if len(matches) != 1:
        raise StopExecution(f"database mount resolution is ambiguous for {container_path}")
    path = matches[0]
    if not path.is_file() or path.is_symlink():
        raise StopExecution(f"database file missing or unsafe for {container_path}")
    return path


def ro_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def require_tables(connection: sqlite3.Connection, names: set[str]) -> None:
    observed = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = names - observed
    if missing:
        raise StopExecution("required database tables missing: " + ",".join(sorted(missing)))


def count_where(connection: sqlite3.Connection, table: str, column: str, value: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE {column} = ?", (value,)
    ).fetchone()
    return int(row["count"])


def registration_history(path: Path, hardware_id: str) -> tuple[dict[str, int], set[str]]:
    with ro_connection(path) as connection:
        tables = {
            "registrations",
            "pairing_sessions",
            "registration_events",
            "registration_node_history",
            "node_id_leases",
            "retirement_outbox",
        }
        require_tables(connection, tables)
        counts = {
            "registrations": count_where(connection, "registrations", "hardware_id", hardware_id),
            "pairing_sessions": count_where(connection, "pairing_sessions", "hardware_id", hardware_id),
            "registration_events": count_where(connection, "registration_events", "hardware_id", hardware_id),
            "registration_node_history": count_where(connection, "registration_node_history", "hardware_id", hardware_id),
            "node_id_leases": count_where(connection, "node_id_leases", "hardware_id", hardware_id),
            "retirement_outbox": count_where(connection, "retirement_outbox", "hardware_id", hardware_id),
        }
        node_ids: set[str] = set()
        for table in ("registrations", "registration_events", "registration_node_history", "node_id_leases"):
            for row in connection.execute(
                f"SELECT node_id FROM {table} WHERE hardware_id = ? AND node_id IS NOT NULL",
                (hardware_id,),
            ).fetchall():
                if isinstance(row["node_id"], str) and row["node_id"]:
                    node_ids.add(row["node_id"])
        return counts, node_ids


def credential_history(path: Path, hardware_id: str) -> tuple[int, set[str]]:
    with ro_connection(path) as connection:
        require_tables(connection, {"credential_assignments"})
        rows = connection.execute(
            "SELECT node_id, last_node_id FROM credential_assignments WHERE hardware_id = ? ORDER BY assignment_id",
            (hardware_id,),
        ).fetchall()
        node_ids: set[str] = set()
        for row in rows:
            for key in ("node_id", "last_node_id"):
                value = row[key]
                if isinstance(value, str) and value:
                    node_ids.add(value)
        return len(rows), node_ids


def replay_history(path: Path, node_ids: set[str]) -> tuple[int, int]:
    with ro_connection(path) as connection:
        require_tables(connection, {"n3w_replay_meta", "n3w_replay_state"})
        total = int(connection.execute("SELECT COUNT(*) AS count FROM n3w_replay_state").fetchone()["count"])
        matches = 0
        for node_id in sorted(node_ids):
            matches += int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM n3w_replay_state WHERE node_id = ?", (node_id,)
                ).fetchone()["count"]
            )
        return total, matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardware-id", required=True)
    parser.add_argument("--container", default="greenhouse-manager")
    args = parser.parse_args()
    try:
        if not args.hardware_id.startswith("ghw-c6-") or len(args.hardware_id) != 19:
            raise StopExecution("hardware id format invalid")
        documents = run_json(["docker", "inspect", "--type", "container", args.container])
        if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
            raise StopExecution("manager container inspection ambiguous")
        document = documents[0]
        state = document.get("State")
        if not isinstance(state, dict) or state.get("Running") is not True:
            raise StopExecution("manager container is not running")
        env = env_map(document)
        registration_container = env.get("GH_PAIRING_DB_PATH", DEFAULT_REGISTRATION)
        credential_container = env.get("GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH", DEFAULT_CREDENTIAL)
        replay_container = env.get("GH_N3W_REPLAY_DB_PATH", DEFAULT_REPLAY)
        registration_path = resolve_host_path(document, registration_container)
        credential_path = resolve_host_path(document, credential_container)
        replay_path = resolve_host_path(document, replay_container)
        registration_counts, registration_nodes = registration_history(registration_path, args.hardware_id)
        credential_count, credential_nodes = credential_history(credential_path, args.hardware_id)
        historical_nodes = registration_nodes | credential_nodes
        replay_total, replay_matches = replay_history(replay_path, historical_nodes)
        registration_total = sum(registration_counts.values())
        clean = registration_total == 0 and credential_count == 0 and replay_matches == 0 and not historical_nodes
        payload = {
            "schema": SCHEMA,
            "status": "PASS" if clean else "FAIL",
            "manager_container_running": True,
            "registration_history_counts": registration_counts,
            "registration_history_total": registration_total,
            "credential_history_count": credential_count,
            "historical_node_id_count": len(historical_nodes),
            "replay_registry_total_rows": replay_total,
            "replay_rows_for_historical_target_nodes": replay_matches,
            "manager_old_registration_for_hardware_absent": registration_total == 0,
            "manager_old_credential_history_for_hardware_absent": credential_count == 0,
            "manager_old_replay_binding_for_target_absent": replay_matches == 0 and not historical_nodes,
            "read_only": True,
            "manager_mutation": False,
            "manager_replay_mutation": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("MANAGER_HISTORY_READONLY=" + payload["status"])
        print("MANAGER_MUTATION=false")
        print("MANAGER_REPLAY_MUTATION=false")
        return 0 if clean else 2
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
