from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

HARDWARE_ID_PATTERN = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


class RegistrationState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class HelloValidationError(ValueError):
    """Raised when an untrusted hello payload is not gh.pair.hello/1."""


class RegistrationConflict(RuntimeError):
    """Raised when a requested state transition is not safe."""


@dataclass(frozen=True)
class RegistrationRecord:
    hardware_id: str
    pairing_id: str
    pairing_epoch: int
    model: str
    fw_version: str
    node_nonce: str
    capabilities: tuple[str, ...]
    state: RegistrationState
    first_seen_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    node_id: str | None
    reason: str | None


@dataclass(frozen=True)
class ObserveResult:
    status: str
    record: RegistrationRecord
    reason: str | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class RegistrationRegistry:
    """Persistent, thread-safe M2 pairing intake state.

    This slice deliberately stops before PoP verification and credential issuance.
    Approving a pending record is an operator decision only; it never creates a
    broker account or grants MQTT access.
    """

    def __init__(self, path: str | Path, *, pending_ttl_s: int = 120) -> None:
        if pending_ttl_s < 1:
            raise ValueError("pending_ttl_s must be positive")
        self.pending_ttl = timedelta(seconds=pending_ttl_s)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(path), isolation_level="IMMEDIATE", check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._validator = self._load_validator()
        self._initialize()

    @staticmethod
    def _load_validator() -> Draft202012Validator:
        schema_path = files("greenhouse_manager").joinpath("schemas/gh.pair.hello-1.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS registrations (
                    hardware_id TEXT PRIMARY KEY,
                    current_pairing_id TEXT NOT NULL UNIQUE,
                    pairing_epoch INTEGER NOT NULL CHECK (pairing_epoch >= 1),
                    node_id TEXT UNIQUE,
                    repair_authorized INTEGER NOT NULL DEFAULT 0 CHECK (repair_authorized IN (0, 1)),
                    FOREIGN KEY (current_pairing_id) REFERENCES pairing_sessions(pairing_id)
                );

                CREATE TABLE IF NOT EXISTS pairing_sessions (
                    pairing_id TEXT PRIMARY KEY,
                    hardware_id TEXT NOT NULL,
                    pairing_epoch INTEGER NOT NULL CHECK (pairing_epoch >= 1),
                    model TEXT NOT NULL,
                    fw_version TEXT NOT NULL,
                    node_nonce TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('pending', 'approved', 'rejected', 'expired')),
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    reason TEXT
                );

                CREATE INDEX IF NOT EXISTS pairing_sessions_hardware_epoch
                    ON pairing_sessions(hardware_id, pairing_epoch);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> RegistrationRegistry:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def validate_hello(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        candidate = dict(payload)
        errors = sorted(self._validator.iter_errors(candidate), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.path) or "$"
            raise HelloValidationError(f"{location}: {error.message}")
        return candidate

    def observe_hello(
        self,
        payload: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> ObserveResult:
        hello = self.validate_hello(payload)
        observed_at = _utc(now or datetime.now(UTC))
        pairing_id = hello["pairing_id"]
        hardware_id = hello["hardware_id"]
        epoch = hello["pairing_epoch"]

        with self._lock, self._connection:
            replay = self._session_row(pairing_id)
            current = self._current_row(hardware_id)

            if replay is not None:
                if replay["hardware_id"] != hardware_id or replay["pairing_epoch"] != epoch:
                    record = self._row_to_record(replay, current["node_id"] if current else None)
                    return ObserveResult("rejected", record, "replay_detected")
                if current is None or current["current_pairing_id"] != pairing_id:
                    return ObserveResult(
                        "rejected",
                        self._row_to_record(replay, current["node_id"] if current else None),
                        "replay_detected",
                    )
                if replay["state"] != RegistrationState.PENDING:
                    return ObserveResult(
                        "rejected",
                        self._row_to_record(replay, current["node_id"]),
                        "replay_detected",
                    )
                if observed_at > _parse_timestamp(replay["expires_at"]):
                    self._set_session_state(pairing_id, RegistrationState.EXPIRED, "expired")
                    return ObserveResult("rejected", self.get(hardware_id), "expired")
                self._connection.execute(
                    "UPDATE pairing_sessions SET last_seen_at = ? WHERE pairing_id = ?",
                    (_timestamp(observed_at), pairing_id),
                )
                return ObserveResult("duplicate", self.get(hardware_id))

            if current is not None and epoch <= current["pairing_epoch"]:
                return ObserveResult("rejected", self.get(hardware_id), "generation_rollback")

            if (
                current is not None
                and current["state"] == RegistrationState.APPROVED
                and not current["repair_authorized"]
            ):
                return ObserveResult("rejected", self.get(hardware_id), "repair_not_authorized")

            expires_at = observed_at + self.pending_ttl
            self._connection.execute(
                """
                INSERT INTO pairing_sessions (
                    pairing_id, hardware_id, pairing_epoch, model, fw_version, node_nonce,
                    capabilities_json, state, first_seen_at, last_seen_at, expires_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    pairing_id,
                    hardware_id,
                    epoch,
                    hello["model"],
                    hello["fw_version"],
                    hello["node_nonce"],
                    json.dumps(hello["capabilities"], separators=(",", ":")),
                    RegistrationState.PENDING,
                    _timestamp(observed_at),
                    _timestamp(observed_at),
                    _timestamp(expires_at),
                ),
            )

            status = "created"
            node_id = None
            if current is not None:
                status = "superseded"
                node_id = current["node_id"]
                previous = self._session_row(current["current_pairing_id"])
                if previous is not None and previous["state"] == RegistrationState.PENDING:
                    self._set_session_state(
                        current["current_pairing_id"], RegistrationState.REJECTED, "superseded"
                    )
                self._connection.execute(
                    """
                    UPDATE registrations
                    SET current_pairing_id = ?, pairing_epoch = ?, repair_authorized = 0
                    WHERE hardware_id = ?
                    """,
                    (pairing_id, epoch, hardware_id),
                )
            else:
                self._connection.execute(
                    """
                    INSERT INTO registrations (hardware_id, current_pairing_id, pairing_epoch, node_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (hardware_id, pairing_id, epoch, node_id),
                )
            return ObserveResult(status, self.get(hardware_id))

    def authorize_repair(self, hardware_id: str) -> RegistrationRecord:
        """Open one re-pair window after an authenticated or explicit user action."""
        with self._lock, self._connection:
            record = self.get(hardware_id)
            if record.state != RegistrationState.APPROVED:
                raise RegistrationConflict("only an approved registration can enter re-pair mode")
            self._connection.execute(
                "UPDATE registrations SET repair_authorized = 1 WHERE hardware_id = ?",
                (hardware_id,),
            )
            return record

    def approve(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        node_id: str | None = None,
        now: datetime | None = None,
    ) -> RegistrationRecord:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            record = self._require_current(hardware_id, pairing_id)
            if record.state != RegistrationState.PENDING:
                raise RegistrationConflict(f"cannot approve registration in {record.state} state")
            if observed_at > record.expires_at:
                self._set_session_state(pairing_id, RegistrationState.EXPIRED, "expired")
                raise RegistrationConflict("cannot approve expired registration")
            assigned_node_id = node_id or record.node_id
            if assigned_node_id is None:
                raise RegistrationConflict("node_id is required for first approval")
            if NODE_ID_PATTERN.fullmatch(assigned_node_id) is None:
                raise RegistrationConflict("node_id does not match gh-mqtt-v1")
            try:
                self._connection.execute(
                    "UPDATE registrations SET node_id = ? WHERE hardware_id = ?",
                    (assigned_node_id, hardware_id),
                )
            except sqlite3.IntegrityError as error:
                raise RegistrationConflict("node_id is already assigned") from error
            self._set_session_state(pairing_id, RegistrationState.APPROVED, "operator_approved")
            return self.get(hardware_id)

    def reject(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        reason: str = "user_rejected",
    ) -> RegistrationRecord:
        with self._lock, self._connection:
            record = self._require_current(hardware_id, pairing_id)
            if record.state != RegistrationState.PENDING:
                raise RegistrationConflict(f"cannot reject registration in {record.state} state")
            self._set_session_state(pairing_id, RegistrationState.REJECTED, reason)
            return self.get(hardware_id)

    def expire_pending(self, *, now: datetime | None = None) -> int:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE pairing_sessions
                SET state = ?, reason = ?
                WHERE state = ? AND expires_at < ?
                """,
                (
                    RegistrationState.EXPIRED,
                    "expired",
                    RegistrationState.PENDING,
                    _timestamp(observed_at),
                ),
            )
            return cursor.rowcount

    def get(self, hardware_id: str) -> RegistrationRecord:
        with self._lock:
            row = self._current_row(hardware_id)
            if row is None:
                raise KeyError(hardware_id)
            return self._row_to_record(row, row["node_id"])

    def list_current(self) -> tuple[RegistrationRecord, ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT s.*, r.node_id
                FROM registrations AS r
                JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id
                ORDER BY s.first_seen_at, s.hardware_id
                """
            ).fetchall()
            return tuple(self._row_to_record(row, row["node_id"]) for row in rows)

    def _require_current(self, hardware_id: str, pairing_id: str) -> RegistrationRecord:
        record = self.get(hardware_id)
        if record.pairing_id != pairing_id:
            raise RegistrationConflict("pairing_id is not the current session")
        return record

    def _current_row(self, hardware_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT s.*, r.current_pairing_id, r.node_id, r.repair_authorized
            FROM registrations AS r
            JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id
            WHERE r.hardware_id = ?
            """,
            (hardware_id,),
        ).fetchone()

    def _session_row(self, pairing_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM pairing_sessions WHERE pairing_id = ?", (pairing_id,)
        ).fetchone()

    def _set_session_state(
        self, pairing_id: str, state: RegistrationState, reason: str | None
    ) -> None:
        self._connection.execute(
            "UPDATE pairing_sessions SET state = ?, reason = ? WHERE pairing_id = ?",
            (state, reason, pairing_id),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row, node_id: str | None) -> RegistrationRecord:
        return RegistrationRecord(
            hardware_id=row["hardware_id"],
            pairing_id=row["pairing_id"],
            pairing_epoch=row["pairing_epoch"],
            model=row["model"],
            fw_version=row["fw_version"],
            node_nonce=row["node_nonce"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            state=RegistrationState(row["state"]),
            first_seen_at=_parse_timestamp(row["first_seen_at"]),
            last_seen_at=_parse_timestamp(row["last_seen_at"]),
            expires_at=_parse_timestamp(row["expires_at"]),
            node_id=node_id,
            reason=row["reason"],
        )
