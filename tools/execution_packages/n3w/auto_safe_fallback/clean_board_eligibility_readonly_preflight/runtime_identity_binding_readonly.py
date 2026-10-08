from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path, PurePosixPath

DEFAULT_REGISTRATION = "/var/lib/greenhouse-manager/registration.sqlite3"
DEFAULT_CREDENTIAL = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
DEFAULT_REPLAY = "/var/lib/greenhouse-manager/n3w/replay.sqlite3"
SNAPSHOT_SCHEMA = "n3w.kf050.runtime-identity-snapshot/1"
VERIFY_SCHEMA = "n3w.kf050.runtime-identity-binding/1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def manager_database_paths(container: str) -> tuple[Path, Path, Path]:
    documents = run_json(["docker", "inspect", "--type", "container", container])
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise StopExecution("manager container inspection ambiguous")
    document = documents[0]
    state = document.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise StopExecution("manager container is not running")
    env = env_map(document)
    registration = resolve_host_path(
        document,
        env.get("GH_PAIRING_DB_PATH", DEFAULT_REGISTRATION),
    )
    credential = resolve_host_path(
        document,
        env.get("GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH", DEFAULT_CREDENTIAL),
    )
    replay = resolve_host_path(
        document,
        env.get("GH_N3W_REPLAY_DB_PATH", DEFAULT_REPLAY),
    )
    return registration, credential, replay


def ro_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def require_tables(connection: sqlite3.Connection, names: set[str]) -> None:
    present = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = names - present
    if missing:
        raise StopExecution("required database tables missing: " + ",".join(sorted(missing)))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def table_hardware_ids(connection: sqlite3.Connection, table: str) -> set[str]:
    result: set[str] = set()
    for row in connection.execute(
        f"SELECT DISTINCT hardware_id FROM {table} WHERE hardware_id IS NOT NULL"
    ).fetchall():
        value = row["hardware_id"]
        if isinstance(value, str) and value:
            result.add(value)
    return result


def all_manager_hardware_ids(registration: Path, credential: Path) -> set[str]:
    registration_tables = {
        "registrations",
        "pairing_sessions",
        "registration_events",
        "registration_node_history",
        "node_id_leases",
        "retirement_outbox",
    }
    result: set[str] = set()
    with ro_connection(registration) as connection:
        require_tables(connection, registration_tables)
        for table in sorted(registration_tables):
            result.update(table_hardware_ids(connection, table))
    with ro_connection(credential) as connection:
        require_tables(connection, {"credential_assignments"})
        result.update(table_hardware_ids(connection, "credential_assignments"))
    return result


def build_snapshot(registration: Path, credential: Path) -> dict[str, object]:
    hashes = sorted(sha256_text(value) for value in all_manager_hardware_ids(registration, credential))
    return {
        "schema": SNAPSHOT_SCHEMA,
        "hardware_id_sha256": hashes,
        "hardware_id_count": len(hashes),
        "read_only": True,
        "manager_mutation": False,
        "manager_replay_mutation": False,
    }


def write_snapshot(path: Path, payload: dict[str, object]) -> None:
    if not path.is_absolute():
        raise StopExecution("snapshot output path must be absolute")
    if path.exists() or path.is_symlink():
        raise StopExecution("snapshot output already exists")
    parent = path.parent.resolve(strict=True)
    path = parent / path.name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def read_snapshot(path: Path) -> set[str]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise StopExecution("snapshot input missing or unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution("snapshot input invalid") from exc
    if (
        not isinstance(document, dict)
        or document.get("schema") != SNAPSHOT_SCHEMA
        or document.get("read_only") is not True
        or document.get("manager_mutation") is not False
        or document.get("manager_replay_mutation") is not False
    ):
        raise StopExecution("snapshot contract invalid")
    raw = document.get("hardware_id_sha256")
    if not isinstance(raw, list) or document.get("hardware_id_count") != len(raw):
        raise StopExecution("snapshot identity set invalid")
    hashes: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
            raise StopExecution("snapshot identity hash invalid")
        hashes.add(value)
    if len(hashes) != len(raw):
        raise StopExecution("snapshot identity hashes are not unique")
    return hashes


def current_fresh_pending(registration: Path) -> dict[str, str]:
    with ro_connection(registration) as connection:
        require_tables(connection, {"registrations", "pairing_sessions"})
        rows = connection.execute(
            """
            SELECT r.hardware_id, r.current_pairing_id
            FROM registrations AS r
            JOIN pairing_sessions AS s
              ON s.pairing_id = r.current_pairing_id
             AND s.hardware_id = r.hardware_id
            WHERE s.state = 'pending'
              AND r.node_id IS NULL
              AND r.retired_at IS NULL
            """
        ).fetchall()
    result: dict[str, str] = {}
    for row in rows:
        hardware_id = row["hardware_id"]
        pairing_id = row["current_pairing_id"]
        if not isinstance(hardware_id, str) or not isinstance(pairing_id, str):
            raise StopExecution("pending identity shape invalid")
        if hardware_id in result and result[hardware_id] != pairing_id:
            raise StopExecution("pending identity is not unique")
        result[hardware_id] = pairing_id
    return result


def target_registration_clean(registration: Path, hardware_id: str, pairing_id: str) -> bool:
    with ro_connection(registration) as connection:
        require_tables(
            connection,
            {
                "registrations",
                "pairing_sessions",
                "registration_node_history",
                "node_id_leases",
                "retirement_outbox",
            },
        )
        row = connection.execute(
            """
            SELECT r.node_id, r.repair_authorized, r.retired_at,
                   r.retirement_reason, s.state
            FROM registrations AS r
            JOIN pairing_sessions AS s
              ON s.pairing_id = r.current_pairing_id
             AND s.hardware_id = r.hardware_id
            WHERE r.hardware_id = ? AND r.current_pairing_id = ?
            """,
            (hardware_id, pairing_id),
        ).fetchone()
        if row is None:
            return False
        if (
            row["node_id"] is not None
            or int(row["repair_authorized"]) != 0
            or row["retired_at"] is not None
            or row["retirement_reason"] is not None
            or row["state"] != "pending"
        ):
            return False
        for table in ("registration_node_history", "node_id_leases", "retirement_outbox"):
            count = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE hardware_id = ?",
                    (hardware_id,),
                ).fetchone()["count"]
            )
            if count != 0:
                return False
    return True


def target_credential_history(credential: Path, hardware_id: str) -> tuple[int, set[str]]:
    with ro_connection(credential) as connection:
        require_tables(connection, {"credential_assignments"})
        rows = connection.execute(
            """
            SELECT node_id, last_node_id
            FROM credential_assignments
            WHERE hardware_id = ?
            """,
            (hardware_id,),
        ).fetchall()
    nodes: set[str] = set()
    for row in rows:
        for key in ("node_id", "last_node_id"):
            value = row[key]
            if isinstance(value, str) and value:
                nodes.add(value)
    return len(rows), nodes


def replay_rows_for_nodes(replay: Path, node_ids: set[str]) -> int:
    with ro_connection(replay) as connection:
        require_tables(connection, {"n3w_replay_state"})
        total = 0
        for node_id in sorted(node_ids):
            total += int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM n3w_replay_state WHERE node_id = ?",
                    (node_id,),
                ).fetchone()["count"]
            )
    return total


def verify_binding(
    registration: Path,
    credential: Path,
    replay: Path,
    *,
    snapshot_hashes: set[str],
    product_hardware_id_sha256: str,
    pairing_id_sha256: str,
) -> dict[str, object]:
    pending = current_fresh_pending(registration)
    new_pending = [
        (hardware_id, pairing_id)
        for hardware_id, pairing_id in pending.items()
        if sha256_text(hardware_id) not in snapshot_hashes
    ]
    if len(new_pending) != 1:
        raise StopExecution("new pending product identity is not unique")
    hardware_id, pairing_id = new_pending[0]
    if sha256_text(hardware_id) != product_hardware_id_sha256:
        raise StopExecution("LCD product identity does not match new pending identity")
    if sha256_text(pairing_id) != pairing_id_sha256:
        raise StopExecution("LCD pairing identity does not match new pending transaction")
    if product_hardware_id_sha256 in snapshot_hashes:
        raise StopExecution("product identity existed before first boot")
    if not target_registration_clean(registration, hardware_id, pairing_id):
        raise StopExecution("new pending registration has pre-existing ownership state")
    credential_count, historical_nodes = target_credential_history(credential, hardware_id)
    replay_count = replay_rows_for_nodes(replay, historical_nodes)
    if credential_count != 0 or historical_nodes or replay_count != 0:
        raise StopExecution("product identity has credential or replay history")
    return {
        "schema": VERIFY_SCHEMA,
        "status": "PASS",
        "product_hardware_id_sha256": product_hardware_id_sha256,
        "pairing_id_sha256": pairing_id_sha256,
        "new_pending_identity_count": 1,
        "preboot_identity_absent": True,
        "lcd_matches_manager_pending": True,
        "credential_history_count": 0,
        "historical_node_id_count": 0,
        "replay_rows_for_target": 0,
        "read_only": True,
        "manager_mutation": False,
        "manager_replay_mutation": False,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    root.add_argument("--container", default="greenhouse-manager")
    commands = root.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--output", required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--snapshot", required=True)
    verify.add_argument("--product-hardware-id-sha256", required=True)
    verify.add_argument("--pairing-id-sha256", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        registration, credential, replay = manager_database_paths(args.container)
        if args.command == "snapshot":
            payload = build_snapshot(registration, credential)
            output = Path(args.output).expanduser()
            write_snapshot(output, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("RUNTIME_IDENTITY_SNAPSHOT=PASS")
            return 0

        hardware_hash = args.product_hardware_id_sha256.lower()
        pairing_hash = args.pairing_id_sha256.lower()
        if SHA256_RE.fullmatch(hardware_hash) is None or SHA256_RE.fullmatch(pairing_hash) is None:
            raise StopExecution("identity SHA256 format invalid")
        snapshot_hashes = read_snapshot(Path(args.snapshot).expanduser())
        payload = verify_binding(
            registration,
            credential,
            replay,
            snapshot_hashes=snapshot_hashes,
            product_hardware_id_sha256=hardware_hash,
            pairing_id_sha256=pairing_hash,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("RUNTIME_IDENTITY_BINDING=PASS")
        return 0
    except (StopExecution, OSError, sqlite3.Error) as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
