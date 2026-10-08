from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import termios
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

HARDWARE_ID = re.compile(r"ghw-c6-[0-9a-f]{12}\Z")
PAIRING_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
SCHEMA = "n3w.p4.pending-identity-projection/1"
RESULT_SCHEMA = "gh.pair.setup-secret-import-result/1"
TABLES = ("registrations", "pairing_sessions", "registration_events", "registration_node_history", "node_id_leases", "retirement_outbox")


class GateStop(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def reject(code: str) -> None:
    raise GateStop(code)


def parse_qr(payload: str) -> tuple[str, str]:
    if not isinstance(payload, str) or len(payload) > 512:
        reject("INVALID_QR")
    parts = payload.split(":")
    if len(parts) != 4 or parts[0] != "GHN3W2" or not HARDWARE_ID.fullmatch(parts[1]) or not PAIRING_ID.fullmatch(parts[2]):
        reject("INVALID_QR")
    secret = parts[3]
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
        reject("INVALID_QR")
    try:
        decoded = base64.b64decode(secret + "=", altchars=b"-_", validate=True)
    except Exception:
        reject("INVALID_QR")
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != secret:
        reject("INVALID_QR")
    return parts[1], parts[2]


def capture_private_qr(reader: Callable[[], str] | None = None) -> str:
    if reader is not None:
        payload = reader()
    else:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
        try:
            if not os.isatty(fd):
                reject("PRIVATE_TTY_REQUIRED")
            original = termios.tcgetattr(fd)
            changed = list(original)
            changed[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(fd, termios.TCSADRAIN, changed)
            try:
                os.write(fd, b"Scan pairing QR into private terminal, then Enter: ")
                data = bytearray()
                while True:
                    chunk = os.read(fd, 1)
                    if not chunk or chunk in (b"\r", b"\n"):
                        break
                    if len(data) >= 512:
                        reject("INVALID_QR")
                    data.extend(chunk)
                os.write(fd, b"\n")
                payload = data.decode("ascii")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, original)
        except (UnicodeDecodeError, OSError, termios.error):
            reject("PRIVATE_CAPTURE_FAILED")
        finally:
            os.close(fd)
    parse_qr(payload)
    return payload


def _ro(path: Path) -> sqlite3.Connection:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        reject("DB_AUTHORITY_INVALID")
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error:
        reject("DB_AUTHORITY_INVALID")


def _query(connection: sqlite3.Connection, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    try:
        return connection.execute(sql, args).fetchall()
    except sqlite3.Error:
        reject("DB_SCHEMA_INVALID")


def _project_once(reg: sqlite3.Connection, cred: sqlite3.Connection, preboot: frozenset[str]) -> dict[str, object]:
    values: set[str] = set()
    for conn, tables in ((reg, TABLES), (cred, ("credential_assignments",))):
        for table in tables:
            for row in _query(conn, f"SELECT DISTINCT hardware_id FROM {table} WHERE hardware_id IS NOT NULL"):
                if not isinstance(row[0], str) or not row[0]:
                    reject("DB_SCHEMA_INVALID")
                values.add(row[0])
    hashes = frozenset(map(sha, values))
    if not preboot.issubset(hashes):
        reject("PREBOOT_IDENTITY_DRIFT")
    new = [value for value in values if sha(value) not in preboot]
    if len(new) != 1:
        reject("NEW_IDENTITY_NOT_UNIQUE")
    hardware_id = new[0]
    records = _query(reg, "SELECT current_pairing_id,pairing_epoch,node_id,retired_at FROM registrations WHERE hardware_id=?", (hardware_id,))
    sessions = _query(reg, "SELECT pairing_id,pairing_epoch,state,expires_at FROM pairing_sessions WHERE hardware_id=?", (hardware_id,))
    events = _query(reg, "SELECT pairing_id,node_id,event FROM registration_events WHERE hardware_id=?", (hardware_id,))
    if len(records) != 1 or len(sessions) != 1 or len(events) != 1:
        reject("PRIOR_IDENTITY_HISTORY")
    a,b,c = records[0],sessions[0],events[0]
    if a[1] != 1 or a[2] is not None or a[3] is not None or b[1] != 1:
        reject("PRIOR_IDENTITY_HISTORY")
    if a[0] != b[0] or b[2] != "pending" or c[0] != b[0] or c[1] is not None or c[2] != "hello_created":
        reject("PENDING_BINDING_INVALID")
    for table in ("registration_node_history", "node_id_leases", "retirement_outbox"):
        if _query(reg, f"SELECT 1 FROM {table} WHERE hardware_id=? LIMIT 1", (hardware_id,)):
            reject("PRIOR_IDENTITY_HISTORY")
    if _query(cred, "SELECT 1 FROM credential_assignments WHERE hardware_id=? LIMIT 1", (hardware_id,)):
        reject("PRIOR_IDENTITY_HISTORY")
    try:
        expires = datetime.fromisoformat(b[3].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        reject("PENDING_EXPIRES_INVALID")
    if expires.tzinfo is None:
        reject("PENDING_EXPIRES_INVALID")
    return {"schema":SCHEMA, "hardware_sha256":sha(hardware_id), "pairing_sha256":sha(b[0]),
            "expires_at":expires.astimezone(UTC).isoformat(), "preboot_count":len(preboot),
            "preboot_hashes":sorted(preboot), "new_count":1}


def project_readonly(registration: Path, credentials: Path, preboot: frozenset[str]) -> dict[str, object]:
    with contextlib.closing(_ro(registration)) as reg, contextlib.closing(_ro(credentials)) as cred:
        first = _project_once(reg, cred, preboot)
        second = _project_once(reg, cred, preboot)
        if first != second:
            reject("PENDING_STATE_DRIFT")
        return second


@dataclass(frozen=True)
class Binding:
    hardware_sha256: str
    pairing_sha256: str
    expires_at: datetime
    live_attested: bool = False


def bind_qr(payload: str, projection: dict[str, object], preboot: frozenset[str], now: datetime, *, min_remaining: int = 60) -> Binding:
    hardware, pairing = parse_qr(payload)
    if now.tzinfo is None or min_remaining < 1:
        reject("CLOCK_UNTRUSTED")
    try:
        if projection["schema"] != SCHEMA or projection["new_count"] != 1 or projection["preboot_count"] != len(preboot) or projection["preboot_hashes"] != sorted(preboot):
            reject("PROJECTION_INVALID")
        if projection["hardware_sha256"] != sha(hardware) or projection["pairing_sha256"] != sha(pairing):
            reject("OPTICAL_MANAGER_MISMATCH")
        expires = datetime.fromisoformat(projection["expires_at"])
    except (KeyError, TypeError, ValueError):
        reject("PROJECTION_INVALID")
    if expires.tzinfo is None or (expires - now.astimezone(UTC)).total_seconds() < min_remaining:
        reject("PENDING_EXPIRED_OR_SHORT")
    verified = (
        projection.get("container_continuity_pass") is True
        and projection.get("manager_socket_pass") is True
        and projection.get("tls_live_reprobe_pass") is True
    )
    if verified:
        try:
            observed = datetime.fromisoformat(projection["read_at"])
        except (KeyError, TypeError, ValueError):
            reject("LIVE_PROJECTION_STALE")
        if observed.tzinfo is None or not 0 <= (now.astimezone(UTC) - observed.astimezone(UTC)).total_seconds() <= 10:
            reject("LIVE_PROJECTION_STALE")
    return Binding(sha(hardware),sha(pairing),expires,verified)


@dataclass(frozen=True)
class ImportPermission:
    exact_hardware_sha256: str
    exact_pairing_sha256: str
    separately_authorized: bool
    operator_continue: bool


class OneShotImporter:
    def __init__(self):
        self._consumed = False

    def import_once(
        self,
        payload: str,
        binding: Binding,
        permission: ImportPermission,
        transport: Callable[[bytes], bytes],
        now: datetime,
    ) -> dict[str, object]:
        if self._consumed:
            reject("IMPORT_ALREADY_CONSUMED")
        self._consumed = True
        reject("IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR")


def ssh_manager_stdin_transport(target: str, data: bytes, *, expected_target_sha256: str, timeout: int = 12) -> bytes:
    reject("IMPORT_DISABLED_PENDING_VERIFIED_FIELD_ORCHESTRATOR")
    if sha(target) != expected_target_sha256 or not re.fullmatch(r"root@(?:[0-9]{1,3}\.){3}[0-9]{1,3}", target):
        reject("IMPORT_TARGET_MISMATCH")
    cmd = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5", target,
           "docker", "exec", "-i", "greenhouse-manager", "greenhouse-manager-pairing", "import-payload", "--payload-stdin"]
    try:
        result = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        reject("IMPORT_TRANSPORT_UNAVAILABLE")
    if result.returncode != 0:
        reject("IMPORT_TRANSPORT_REJECTED")
    return result.stdout
