from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

BASELINE_SCHEMA = "n3w.kf050.runtime-identity-snapshot/1"
QR_PATTERN = re.compile(
    r"GHN3W2:(ghw-c6-[0-9a-f]{12}):"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}):"
    r"([A-Za-z0-9_-]{43})"
)
HEX_64 = re.compile(r"[0-9a-f]{64}")
REGISTRATION_TABLES = (
    "registrations",
    "pairing_sessions",
    "registration_events",
    "registration_node_history",
    "node_id_leases",
    "retirement_outbox",
)
REQUIRED_COLUMNS = {
    "registrations": {"hardware_id", "current_pairing_id", "pairing_epoch", "node_id", "retired_at"},
    "pairing_sessions": {"pairing_id", "hardware_id", "pairing_epoch", "state", "expires_at"},
    "registration_events": {"hardware_id", "pairing_id", "node_id", "event"},
    "registration_node_history": {"hardware_id", "node_id"},
    "node_id_leases": {"hardware_id", "node_id"},
    "retirement_outbox": {"hardware_id", "pairing_id", "node_id"},
    "credential_assignments": {"hardware_id", "pairing_id", "node_id", "last_node_id", "state"},
    "n3w_replay_state": {"node_id"},
}


class BinderInvalid(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _reject(code: str) -> None:
    raise BinderInvalid(code)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_baseline_document(document: object, count: int = 5) -> frozenset[str]:
    if not isinstance(document, dict) or set(document) != {
        "schema", "hardware_id_sha256", "hardware_id_count", "read_only", "manager_mutation", "manager_replay_mutation"
    }:
        _reject("INVALID_SNAPSHOT_SCHEMA")
    hashes = document["hardware_id_sha256"]
    if (
        document["schema"] != BASELINE_SCHEMA
        or document["hardware_id_count"] != count
        or document["read_only"] is not True
        or document["manager_mutation"] is not False
        or document["manager_replay_mutation"] is not False
        or not isinstance(hashes, list)
        or len(hashes) != count
        or not all(isinstance(h, str) and HEX_64.fullmatch(h) for h in hashes)
        or hashes != sorted(set(hashes))
    ):
        _reject("INVALID_SNAPSHOT_SCHEMA")
    return frozenset(hashes)


def read_private_baseline(path: Path, expected_sha256: str, count: int = 5) -> frozenset[str]:
    try:
        parent = path.parent
        if not path.is_absolute() or path.is_symlink() or parent.is_symlink():
            _reject("INVALID_PRIVATE_SNAPSHOT")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            _reject("INVALID_PRIVATE_SNAPSHOT")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            _reject("INVALID_PRIVATE_SNAPSHOT")
        if not isinstance(expected_sha256, str) or not HEX_64.fullmatch(expected_sha256):
            _reject("INVALID_PRIVATE_SNAPSHOT")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            _reject("INVALID_SNAPSHOT_DRIFT")
        document = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        _reject("INVALID_PRIVATE_SNAPSHOT")
    return validate_baseline_document(document, count=count)


def parse_optical_qr(payload: str) -> tuple[str, str]:
    if not isinstance(payload, str) or len(payload) > 512 or len(payload) < 80:
        _reject("INVALID_QR_FORMAT")
    match = QR_PATTERN.fullmatch(payload)
    if match is None:
        _reject("INVALID_QR_FORMAT")
    secret = match.group(3)
    try:
        decoded = base64.b64decode(secret + "=", altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        _reject("INVALID_QR_FORMAT")
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != secret:
        _reject("INVALID_QR_FORMAT")
    return match.group(1), match.group(2)


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        _reject("INVALID_RUNTIME_AUTHORITY")
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            _reject("INVALID_RUNTIME_AUTHORITY")
        return connection
    except sqlite3.Error:
        _reject("INVALID_RUNTIME_AUTHORITY")


def _check_schema(connection: sqlite3.Connection, tables: tuple[str, ...]) -> None:
    try:
        for table in tables:
            cols = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not REQUIRED_COLUMNS[table].issubset(cols):
                _reject("INVALID_RUNTIME_AUTHORITY")
    except sqlite3.Error:
        _reject("INVALID_RUNTIME_AUTHORITY")


def _fetch(connection: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    try:
        return connection.execute(query, params).fetchall()
    except sqlite3.Error:
        _reject("INVALID_RUNTIME_AUTHORITY")


def _hardware_union(reg: sqlite3.Connection, cred: sqlite3.Connection) -> frozenset[str]:
    values: set[str] = set()
    for connection, tables in ((reg, REGISTRATION_TABLES), (cred, ("credential_assignments",))):
        for table in tables:
            for row in _fetch(connection, f"SELECT DISTINCT hardware_id FROM {table} WHERE hardware_id IS NOT NULL"):
                value = row[0]
                if not isinstance(value, str) or not value:
                    _reject("INVALID_RUNTIME_AUTHORITY")
                values.add(value)
    return frozenset(digest(value) for value in values)


def _binding_state(reg: sqlite3.Connection, cred: sqlite3.Connection, hardware_id: str) -> tuple:
    selections = (
        (reg, "registrations", "hardware_id,current_pairing_id,pairing_epoch,node_id,retired_at"),
        (reg, "pairing_sessions", "hardware_id,pairing_id,pairing_epoch,state,expires_at"),
        (reg, "registration_events", "hardware_id,pairing_id,node_id,event"),
        (reg, "registration_node_history", "hardware_id,node_id"),
        (reg, "node_id_leases", "hardware_id,node_id"),
        (reg, "retirement_outbox", "hardware_id,pairing_id,node_id"),
        (cred, "credential_assignments", "hardware_id,pairing_id,node_id,last_node_id,state"),
    )
    result = []
    for connection, table, columns in selections:
        rows = _fetch(connection, f"SELECT {columns} FROM {table} WHERE hardware_id=?", (hardware_id,))
        result.append((table, tuple(sorted((tuple(row) for row in rows), key=repr))))
    return tuple(result)


def verify_sqlite_pairing(
    registration_path: Path,
    credential_path: Path,
    replay_path: Path,
    baseline: frozenset[str],
    optical_payload: str,
    *,
    now: datetime,
    minimum_remaining_seconds: int = 60,
    runtime_authority_pass: bool = False,
) -> dict[str, object]:
    if runtime_authority_pass is not True:
        _reject("INVALID_RUNTIME_AUTHORITY")
    if now.tzinfo is None or minimum_remaining_seconds < 1:
        _reject("INVALID_RUNTIME_AUTHORITY")
    hardware_id, pairing_id = parse_optical_qr(optical_payload)
    if not isinstance(baseline, frozenset) or not all(HEX_64.fullmatch(x) for x in baseline):
        _reject("INVALID_SNAPSHOT_SCHEMA")
    reg = _connect_ro(registration_path)
    try:
        cred = _connect_ro(credential_path)
        try:
            replay = _connect_ro(replay_path)
            try:
                _check_schema(reg, REGISTRATION_TABLES)
                _check_schema(cred, ("credential_assignments",))
                _check_schema(replay, ("n3w_replay_state",))
                binding_start = _binding_state(reg, cred, hardware_id)
                postboot = _hardware_union(reg, cred)
                if not baseline.issubset(postboot):
                    _reject("INVALID_SNAPSHOT_DRIFT")
                additions = postboot - baseline
                if len(additions) != 1:
                    _reject("INVALID_UNIQUE_IDENTITY")
                if digest(hardware_id) not in additions:
                    _reject("INVALID_QR_PENDING_BINDING")
                registration = _fetch(reg, "SELECT hardware_id, current_pairing_id, node_id, pairing_epoch, retired_at FROM registrations WHERE hardware_id=?", (hardware_id,))
                sessions = _fetch(reg, "SELECT hardware_id, pairing_id, state, expires_at, pairing_epoch FROM pairing_sessions WHERE hardware_id=?", (hardware_id,))
                if len(registration) != 1 or len(sessions) != 1:
                    _reject("INVALID_PRIOR_HISTORY")
                record, session = registration[0], sessions[0]
                if record["node_id"] is not None or record["retired_at"] is not None or record["pairing_epoch"] != 1:
                    _reject("INVALID_PRIOR_HISTORY")
                if (
                    record["current_pairing_id"] != pairing_id
                    or session["pairing_id"] != pairing_id
                    or session["hardware_id"] != hardware_id
                ):
                    _reject("INVALID_QR_PENDING_BINDING")
                if session["state"] != "pending" or session["pairing_epoch"] != 1:
                    _reject("INVALID_PENDING_LIFECYCLE")
                try:
                    expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
                except (ValueError, TypeError, AttributeError):
                    _reject("INVALID_PENDING_LIFECYCLE")
                if expires.tzinfo is None or (expires - now.astimezone(UTC)).total_seconds() < minimum_remaining_seconds:
                    _reject("INVALID_PENDING_LIFECYCLE")
                events = _fetch(reg, "SELECT pairing_id, node_id, event FROM registration_events WHERE hardware_id=?", (hardware_id,))
                if len(events) != 1 or events[0]["pairing_id"] != pairing_id or events[0]["node_id"] is not None or events[0]["event"] != "hello_created":
                    _reject("INVALID_PRIOR_HISTORY")
                for table in ("registration_node_history", "node_id_leases", "retirement_outbox"):
                    if _fetch(reg, f"SELECT 1 FROM {table} WHERE hardware_id=? LIMIT 1", (hardware_id,)):
                        _reject("INVALID_PRIOR_HISTORY")
                if _fetch(cred, "SELECT 1 FROM credential_assignments WHERE hardware_id=? LIMIT 1", (hardware_id,)):
                    _reject("INVALID_PRIOR_HISTORY")
                if _hardware_union(reg, cred) != postboot:
                    _reject("INVALID_SNAPSHOT_DRIFT")
                if _binding_state(reg, cred, hardware_id) != binding_start:
                    _reject("INVALID_BINDING_STATE_DRIFT")
                return {
                    "status": "BINDER_PASS_NO_IMPORT",
                    "product_hardware_id_sha256": digest(hardware_id),
                    "pairing_id_sha256": digest(pairing_id),
                    "historical_identity_count": len(baseline),
                    "new_identity_count": 1,
                    "remaining_time_policy_pass": True,
                    "manager_mutation": False,
                    "setup_secret_imported": False,
                    "stop": True,
                }
            finally:
                replay.close()
        finally:
            cred.close()
    finally:
        reg.close()
