from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
from contextlib import ExitStack, closing
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "n3w.p4.terminal-pending-readonly/1"
HARDWARE = re.compile(r"ghw-c6-[0-9a-f]{12}\Z")
PAIRING = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
TABLES = {
    "registrations": {"hardware_id", "current_pairing_id", "pairing_epoch", "node_id", "retired_at"},
    "pairing_sessions": {"hardware_id", "pairing_id", "pairing_epoch", "state", "expires_at"},
    "registration_events": {"hardware_id", "pairing_id", "node_id", "event"},
    "registration_node_history": {"hardware_id", "node_id"},
    "node_id_leases": {"hardware_id", "node_id"},
    "retirement_outbox": {"hardware_id", "pairing_id", "node_id"},
    "credential_assignments": {"hardware_id", "pairing_id", "node_id", "last_node_id"},
    "n3w_replay_meta": {"schema_version"},
    "n3w_replay_state": {"node_id"},
    "n3w_replay_seen": {"node_id"},
}
REG_TABLES = tuple(TABLES)[:6]
REPLAY_TABLES = ("n3w_replay_meta", "n3w_replay_state", "n3w_replay_seen")


class PendingReadonlyError(ValueError):
    pass


def _stop() -> None:
    raise PendingReadonlyError("P4_PENDING_READONLY_INVALID")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _file_state(path: Path) -> tuple:
    states = []
    for suffix in ("", "-wal", "-shm"):
        item = Path(str(path) + suffix)
        try:
            info = item.lstat()
        except FileNotFoundError:
            states.append(None)
            continue
        except OSError as error:
            raise PendingReadonlyError("P4_PENDING_READONLY_INVALID") from error
        if not stat.S_ISREG(info.st_mode) or item.is_symlink():
            _stop()
        states.append((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns))
    if states[0] is None or (states[1] is None) != (states[2] is None):
        _stop()
    return tuple(states)


def _open_ro(path: Path) -> sqlite3.Connection:
    if not path.is_absolute() or path.is_symlink():
        _stop()
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            _stop()
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            conn.close()
            _stop()
        return conn
    except (OSError, sqlite3.Error, ValueError) as error:
        raise PendingReadonlyError("P4_PENDING_READONLY_INVALID") from error


def _tables(connection: sqlite3.Connection, expected: tuple[str, ...]) -> dict[str, list[dict]]:
    result = {}
    for table in expected:
        found = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if not TABLES[table].issubset(found):
            _stop()
        result[table] = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    return result


def _id_set(tables: dict[str, list[dict]], names: tuple[str, ...]) -> set[str]:
    values = set()
    for name in names:
        for row in tables[name]:
            value = row.get("hardware_id")
            if not isinstance(value, str) or not value:
                _stop()
            values.add(value)
    return values


def _projection(reg: sqlite3.Connection, cred: sqlite3.Connection, replay: sqlite3.Connection) -> dict:
    registrations = _tables(reg, REG_TABLES)
    credentials = _tables(cred, ("credential_assignments",))
    replays = _tables(replay, REPLAY_TABLES)
    if replays["n3w_replay_meta"] != [{"schema_version": 1}]:
        _stop()
    ids = _id_set(registrations, REG_TABLES) | _id_set(credentials, ("credential_assignments",))
    if len(ids) != 6:
        _stop()
    pending = [s for s in registrations["pairing_sessions"] if s["state"] == "pending"]
    if len(pending) != 1:
        _stop()
    session = pending[0]
    hardware = session["hardware_id"]
    pairing = session["pairing_id"]
    if (
        not isinstance(hardware, str)
        or not HARDWARE.fullmatch(hardware)
        or not isinstance(pairing, str)
        or not PAIRING.fullmatch(pairing)
        or hardware not in ids
    ):
        _stop()
    current = [s for s in registrations["registrations"] if s["hardware_id"] == hardware]
    sessions = [s for s in registrations["pairing_sessions"] if s["hardware_id"] == hardware]
    events = [s for s in registrations["registration_events"] if s["hardware_id"] == hardware]
    if len(current) != 1 or len(sessions) != 1 or len(events) != 1:
        _stop()
    record = current[0]
    event = events[0]
    if (
        record["current_pairing_id"] != pairing
        or record["pairing_epoch"] != 1
        or record["node_id"] is not None
        or record["retired_at"] is not None
        or session["pairing_epoch"] != 1
        or event["pairing_id"] != pairing
        or event["node_id"] is not None
        or event["event"] != "hello_created"
    ):
        _stop()
    if any(
        row["hardware_id"] == hardware
        for name in (*REG_TABLES[3:], "credential_assignments")
        for row in (registrations if name in registrations else credentials)[name]
    ):
        _stop()
    try:
        expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None:
            _stop()
    except (AttributeError, ValueError, TypeError):
        _stop()
    old = ids - {hardware}
    if len(old) != 5:
        _stop()

    mapping: dict[str, str] = {}
    for name in ("registrations", "registration_node_history", "node_id_leases", "retirement_outbox"):
        for row in registrations[name]:
            node = row.get("node_id")
            if node is None:
                continue
            if not isinstance(node, str) or not node:
                _stop()
            previous = mapping.setdefault(node, row["hardware_id"])
            if previous != row["hardware_id"]:
                _stop()
    for row in credentials["credential_assignments"]:
        for field in ("node_id", "last_node_id"):
            node = row.get(field)
            if node is None:
                continue
            if not isinstance(node, str) or not node:
                _stop()
            previous = mapping.setdefault(node, row["hardware_id"])
            if previous != row["hardware_id"]:
                _stop()
    referenced_nodes = {
        row["node_id"]
        for table in ("n3w_replay_state", "n3w_replay_seen")
        for row in replays[table]
    }
    if any(node not in mapping or mapping[node] not in old for node in referenced_nodes):
        _stop()
    historical = sorted(_hash(value) for value in old)
    if len(set(historical)) != 5:
        _stop()
    return {
        "schema": SCHEMA,
        "historical_count": 5,
        "historical_hardware_hashes": historical,
        "new_count": 1,
        "hardware_sha256": _hash(hardware),
        "pairing_sha256": _hash(pairing),
        "expires_at": expires.astimezone(UTC).isoformat(),
        "pending_state": "pending",
        "first_registration_no_history": True,
        "credential_history_clear": True,
        "replay_linkage_clear": True,
        "read_only": True,
    }


def read_pending(
    registration_path: Path,
    credential_path: Path,
    replay_path: Path,
    *,
    now: datetime | None = None,
) -> dict:
    paths = (registration_path, credential_path, replay_path)
    if len({str(path.resolve()) for path in paths}) != 3:
        _stop()
    before = tuple(_file_state(path) for path in paths)
    with ExitStack() as stack:
        connections = [
            stack.enter_context(closing(_open_ro(path)))
            for path in paths
        ]
        try:
            first = _projection(*connections)
            middle = tuple(_file_state(path) for path in paths)
            second = _projection(*connections)
        except (sqlite3.Error, KeyError, IndexError, TypeError, UnicodeError) as error:
            raise PendingReadonlyError("P4_PENDING_READONLY_INVALID") from error
        if first != second or before != middle:
            _stop()
    if tuple(_file_state(path) for path in paths) != before:
        _stop()
    observed = now if now is not None else datetime.now(UTC)
    if observed.tzinfo is None:
        _stop()
    expiry = datetime.fromisoformat(second["expires_at"])
    if expiry <= observed.astimezone(UTC):
        _stop()
    second["read_at"] = observed.astimezone(UTC).isoformat()
    return second


def encode_result(result: dict) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":"))
