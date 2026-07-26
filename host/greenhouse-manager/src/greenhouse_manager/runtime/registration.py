from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

HARDWARE_ID_PATTERN = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
LOGICAL_LOCATION_ID_PATTERN = NODE_ID_PATTERN


class RegistrationState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RETIRED = "retired"


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
    logical_location_id: str | None
    retired_at: datetime | None
    reason: str | None


@dataclass(frozen=True)
class ObserveResult:
    status: str
    record: RegistrationRecord
    reason: str | None = None


@dataclass(frozen=True)
class RegistrationEvent:
    event_id: int
    hardware_id: str
    pairing_id: str
    node_id: str | None
    logical_location_id: str | None
    event: str
    reason: str | None
    occurred_at: datetime


class NodeIdLeaseState(StrEnum):
    ACTIVE = "active"
    RETIRING = "retiring"
    REUSABLE = "reusable"


class RetirementState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True)
class RetirementJob:
    retirement_id: int
    hardware_id: str
    pairing_id: str
    node_id: str
    logical_location_id: str | None
    system_id: str
    reason: str
    credentials_revoked: bool
    credential_evidence: str | None
    runtime_cleanup_complete: bool
    state: RetirementState
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


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
        self._connection = sqlite3.connect(str(path), isolation_level="IMMEDIATE", check_same_thread=False)
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
                    logical_location_id TEXT,
                    repair_authorized INTEGER NOT NULL DEFAULT 0 CHECK (repair_authorized IN (0, 1)),
                    retired_at TEXT,
                    retirement_reason TEXT,
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

                CREATE TABLE IF NOT EXISTS registration_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hardware_id TEXT NOT NULL,
                    pairing_id TEXT NOT NULL,
                    node_id TEXT,
                    logical_location_id TEXT,
                    event TEXT NOT NULL,
                    reason TEXT,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS registration_events_hardware_time
                    ON registration_events(hardware_id, occurred_at);

                CREATE TABLE IF NOT EXISTS registration_node_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hardware_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    logical_location_id TEXT,
                    assigned_at TEXT NOT NULL,
                    released_at TEXT,
                    retirement_event_id INTEGER
                );

                CREATE UNIQUE INDEX IF NOT EXISTS registration_node_history_open_hardware
                    ON registration_node_history(hardware_id)
                    WHERE released_at IS NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS registration_node_history_open_node
                    ON registration_node_history(node_id)
                    WHERE released_at IS NULL;

                CREATE TABLE IF NOT EXISTS node_id_leases (
                    node_id TEXT PRIMARY KEY,
                    hardware_id TEXT NOT NULL,
                    logical_location_id TEXT,
                    state TEXT NOT NULL CHECK (state IN ('active', 'retiring', 'reusable')),
                    retirement_id INTEGER,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS retirement_outbox (
                    retirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hardware_id TEXT NOT NULL,
                    pairing_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    logical_location_id TEXT,
                    system_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    credentials_revoked INTEGER NOT NULL DEFAULT 0
                        CHECK (credentials_revoked IN (0, 1)),
                    credential_evidence TEXT,
                    runtime_cleanup_complete INTEGER NOT NULL DEFAULT 0
                        CHECK (runtime_cleanup_complete IN (0, 1)),
                    state TEXT NOT NULL DEFAULT 'pending'
                        CHECK (state IN ('pending', 'completed')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE (hardware_id, pairing_id, node_id)
                );

                CREATE INDEX IF NOT EXISTS retirement_outbox_runtime_pending
                    ON retirement_outbox(runtime_cleanup_complete, retirement_id);
                """
            )
            self._ensure_column("registrations", "logical_location_id", "TEXT")
            self._ensure_column("registrations", "retired_at", "TEXT")
            self._ensure_column("registrations", "retirement_reason", "TEXT")
            self._ensure_column("registration_events", "node_id", "TEXT")
            self._ensure_column("registration_events", "logical_location_id", "TEXT")
            self._ensure_column("registration_node_history", "logical_location_id", "TEXT")
            self._ensure_column("node_id_leases", "logical_location_id", "TEXT")
            self._ensure_column("retirement_outbox", "logical_location_id", "TEXT")
            self._bootstrap_node_assignments()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _bootstrap_node_assignments(self) -> None:
        rows = self._connection.execute(
            """
            SELECT r.hardware_id, r.node_id, r.logical_location_id, s.first_seen_at
            FROM registrations AS r
            JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id
            WHERE r.node_id IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO node_id_leases (
                    node_id, hardware_id, logical_location_id, state,
                    retirement_id, updated_at
                ) VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (
                    row["node_id"],
                    row["hardware_id"],
                    row["logical_location_id"],
                    NodeIdLeaseState.ACTIVE,
                    row["first_seen_at"],
                ),
            )
            open_history = self._connection.execute(
                """
                SELECT 1
                FROM registration_node_history
                WHERE hardware_id = ? AND released_at IS NULL
                """,
                (row["hardware_id"],),
            ).fetchone()
            if open_history is None:
                self._connection.execute(
                    """
                    INSERT INTO registration_node_history (
                        hardware_id, node_id, logical_location_id, assigned_at,
                        released_at, retirement_event_id
                    ) VALUES (?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        row["hardware_id"],
                        row["node_id"],
                        row["logical_location_id"],
                        row["first_seen_at"],
                    ),
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

            if current is not None and current["retired_at"] is not None:
                return ObserveResult("rejected", self.get(hardware_id), "hardware_retired")

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
            self._record_event(
                hardware_id,
                pairing_id,
                "hello_created" if status == "created" else "hello_superseded",
                None,
                observed_at,
            )
            return ObserveResult(status, self.get(hardware_id))

    def authorize_repair(self, hardware_id: str, *, now: datetime | None = None) -> RegistrationRecord:
        """Open one re-pair window after an authenticated or explicit user action."""
        with self._lock, self._connection:
            record = self.get(hardware_id)
            if record.state != RegistrationState.APPROVED:
                raise RegistrationConflict("only an approved registration can enter re-pair mode")
            self._connection.execute(
                "UPDATE registrations SET repair_authorized = 1 WHERE hardware_id = ?",
                (hardware_id,),
            )
            self._record_event(
                hardware_id,
                record.pairing_id,
                "repair_authorized",
                None,
                _utc(now or datetime.now(UTC)),
            )
            return record

    def approve(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        node_id: str | None = None,
        logical_location_id: str | None = None,
        reuse_retired_node_id: bool = False,
        private_identity_bound: bool = False,
        anonymous_compatibility_enabled: bool = True,
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
            if record.node_id is not None and node_id is not None and node_id != record.node_id:
                raise RegistrationConflict("node_id change requires retiring the existing hardware")
            if assigned_node_id is None:
                raise RegistrationConflict("node_id is required for first approval")
            if NODE_ID_PATTERN.fullmatch(assigned_node_id) is None:
                raise RegistrationConflict("node_id does not match gh-mqtt-v1")
            assigned_logical_location_id = logical_location_id or record.logical_location_id
            if (
                assigned_logical_location_id is not None
                and LOGICAL_LOCATION_ID_PATTERN.fullmatch(assigned_logical_location_id) is None
            ):
                raise RegistrationConflict("logical_location_id does not match gh-mqtt-v1")
            if (
                record.logical_location_id is not None
                and logical_location_id is not None
                and logical_location_id != record.logical_location_id
            ):
                raise RegistrationConflict(
                    "logical_location_id change requires retiring the existing hardware"
                )
            reused_from_hardware_id = self._validate_node_id_claim(
                hardware_id,
                assigned_node_id,
                logical_location_id=assigned_logical_location_id,
                reuse_retired_node_id=reuse_retired_node_id,
                private_identity_bound=private_identity_bound,
                anonymous_compatibility_enabled=anonymous_compatibility_enabled,
            )
            try:
                self._connection.execute(
                    """
                    UPDATE registrations
                    SET node_id = ?, logical_location_id = ?
                    WHERE hardware_id = ?
                    """,
                    (
                        assigned_node_id,
                        assigned_logical_location_id,
                        hardware_id,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise RegistrationConflict("node_id is already assigned") from error
            self._activate_node_id_lease(
                hardware_id,
                assigned_node_id,
                assigned_logical_location_id,
                observed_at,
            )
            self._set_session_state(pairing_id, RegistrationState.APPROVED, "operator_approved")
            self._record_event(
                hardware_id,
                pairing_id,
                "operator_approved",
                None,
                observed_at,
                node_id=assigned_node_id,
                logical_location_id=assigned_logical_location_id,
            )
            if reused_from_hardware_id is not None:
                self._record_event(
                    hardware_id,
                    pairing_id,
                    "node_id_reuse_approved",
                    f"replaced_hardware_id={reused_from_hardware_id}",
                    observed_at,
                    node_id=assigned_node_id,
                    logical_location_id=assigned_logical_location_id,
                )
            self._open_assignment_history(
                hardware_id,
                assigned_node_id,
                assigned_logical_location_id,
                observed_at,
            )
            return self.get(hardware_id)

    def reject(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        reason: str = "user_rejected",
        now: datetime | None = None,
    ) -> RegistrationRecord:
        with self._lock, self._connection:
            record = self._require_current(hardware_id, pairing_id)
            if record.state != RegistrationState.PENDING:
                raise RegistrationConflict(f"cannot reject registration in {record.state} state")
            self._set_session_state(pairing_id, RegistrationState.REJECTED, reason)
            self._record_event(
                hardware_id,
                pairing_id,
                "operator_rejected",
                reason,
                _utc(now or datetime.now(UTC)),
            )
            return self.get(hardware_id)

    def expire_pending(self, *, now: datetime | None = None) -> int:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            expiring = self._connection.execute(
                """
                SELECT hardware_id, pairing_id
                FROM pairing_sessions
                WHERE state = ? AND expires_at < ?
                """,
                (RegistrationState.PENDING, _timestamp(observed_at)),
            ).fetchall()
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
            for row in expiring:
                self._record_event(
                    row["hardware_id"],
                    row["pairing_id"],
                    "expired",
                    "expired",
                    observed_at,
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
                SELECT s.*, r.node_id, r.logical_location_id, r.retired_at,
                       r.retirement_reason, r.repair_authorized
                FROM registrations AS r
                JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id
                ORDER BY s.first_seen_at, s.hardware_id
                """
            ).fetchall()
            return tuple(self._row_to_record(row, row["node_id"]) for row in rows)

    def list_events(
        self, *, hardware_id: str | None = None, limit: int = 100
    ) -> tuple[RegistrationEvent, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            if hardware_id is None:
                rows = self._connection.execute(
                    """
                    SELECT * FROM registration_events
                    ORDER BY event_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT * FROM registration_events
                    WHERE hardware_id = ?
                    ORDER BY event_id DESC
                    LIMIT ?
                    """,
                    (hardware_id, limit),
                ).fetchall()
            return tuple(
                RegistrationEvent(
                    event_id=row["event_id"],
                    hardware_id=row["hardware_id"],
                    pairing_id=row["pairing_id"],
                    node_id=row["node_id"],
                    logical_location_id=row["logical_location_id"],
                    event=row["event"],
                    reason=row["reason"],
                    occurred_at=_parse_timestamp(row["occurred_at"]),
                )
                for row in rows
            )

    def retire(
        self,
        hardware_id: str,
        *,
        system_id: str,
        reason: str = "operator_retired",
        now: datetime | None = None,
    ) -> RetirementJob:
        if NODE_ID_PATTERN.fullmatch(system_id) is None:
            raise ValueError("system_id does not match gh-mqtt-v1")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("retirement reason must not be empty")
        occurred_at = _utc(now or datetime.now(UTC))

        with self._lock, self._connection:
            record = self.get(hardware_id)
            if record.state is RegistrationState.RETIRED:
                row = self._connection.execute(
                    """
                    SELECT *
                    FROM retirement_outbox
                    WHERE hardware_id = ?
                    ORDER BY retirement_id DESC
                    LIMIT 1
                    """,
                    (hardware_id,),
                ).fetchone()
                if row is None:
                    raise RegistrationConflict("retired registration is missing its retirement outbox record")
                return self._row_to_retirement(row)
            if record.state is not RegistrationState.APPROVED:
                raise RegistrationConflict("only an approved registration can be retired")
            if record.node_id is None:
                raise RegistrationConflict("approved registration has no node_id")

            node_id = record.node_id
            retirement_event_id = self._record_event(
                hardware_id,
                record.pairing_id,
                "operator_retired",
                normalized_reason,
                occurred_at,
                node_id=node_id,
                logical_location_id=record.logical_location_id,
            )
            self._close_assignment_history(
                record,
                released_at=occurred_at,
                retirement_event_id=retirement_event_id,
            )
            self._connection.execute(
                """
                UPDATE registrations
                SET node_id = NULL, repair_authorized = 0,
                    retired_at = ?, retirement_reason = ?
                WHERE hardware_id = ?
                """,
                (_timestamp(occurred_at), normalized_reason, hardware_id),
            )
            cursor = self._connection.execute(
                """
                INSERT INTO retirement_outbox (
                    hardware_id, pairing_id, node_id, logical_location_id,
                    system_id, reason,
                    credentials_revoked, credential_evidence,
                    runtime_cleanup_complete, state, attempts, last_error,
                    created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 0, ?, 0, NULL, ?, ?, NULL)
                """,
                (
                    hardware_id,
                    record.pairing_id,
                    node_id,
                    record.logical_location_id,
                    system_id,
                    normalized_reason,
                    RetirementState.PENDING,
                    _timestamp(occurred_at),
                    _timestamp(occurred_at),
                ),
            )
            retirement_id = int(cursor.lastrowid)
            self._connection.execute(
                """
                INSERT INTO node_id_leases (
                    node_id, hardware_id, logical_location_id, state,
                    retirement_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    hardware_id = excluded.hardware_id,
                    logical_location_id = excluded.logical_location_id,
                    state = excluded.state,
                    retirement_id = excluded.retirement_id,
                    updated_at = excluded.updated_at
                """,
                (
                    node_id,
                    hardware_id,
                    record.logical_location_id,
                    NodeIdLeaseState.RETIRING,
                    retirement_id,
                    _timestamp(occurred_at),
                ),
            )
            return self.get_retirement_job(retirement_id)

    def list_retirement_jobs(
        self, *, ready_for_runtime_cleanup_only: bool = False
    ) -> tuple[RetirementJob, ...]:
        with self._lock:
            query = "SELECT * FROM retirement_outbox"
            if ready_for_runtime_cleanup_only:
                query += " WHERE credentials_revoked = 1 AND runtime_cleanup_complete = 0"
            query += " ORDER BY retirement_id"
            rows = self._connection.execute(query).fetchall()
            return tuple(self._row_to_retirement(row) for row in rows)

    def get_retirement_job(self, retirement_id: int) -> RetirementJob:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM retirement_outbox WHERE retirement_id = ?",
                (retirement_id,),
            ).fetchone()
            if row is None:
                raise KeyError(retirement_id)
            return self._row_to_retirement(row)

    def mark_credentials_revoked(
        self,
        retirement_id: int,
        *,
        evidence: str,
        now: datetime | None = None,
    ) -> RetirementJob:
        normalized_evidence = evidence.strip()
        if not normalized_evidence:
            raise ValueError("credential revocation evidence must not be empty")
        occurred_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            job = self.get_retirement_job(retirement_id)
            if not job.credentials_revoked:
                self._connection.execute(
                    """
                    UPDATE retirement_outbox
                    SET credentials_revoked = 1, credential_evidence = ?,
                        updated_at = ?, last_error = NULL
                    WHERE retirement_id = ?
                    """,
                    (normalized_evidence[:512], _timestamp(occurred_at), retirement_id),
                )
                self._record_event(
                    job.hardware_id,
                    job.pairing_id,
                    "retirement_credentials_revoked",
                    normalized_evidence[:512],
                    occurred_at,
                    node_id=job.node_id,
                )
            return self._reconcile_retirement(retirement_id, occurred_at)

    def mark_runtime_cleanup_complete(
        self,
        retirement_id: int,
        *,
        now: datetime | None = None,
    ) -> RetirementJob:
        occurred_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            job = self.get_retirement_job(retirement_id)
            if not job.credentials_revoked:
                raise RegistrationConflict("credentials must be revoked before runtime cleanup")
            if not job.runtime_cleanup_complete:
                self._connection.execute(
                    """
                    UPDATE retirement_outbox
                    SET runtime_cleanup_complete = 1, updated_at = ?, last_error = NULL
                    WHERE retirement_id = ?
                    """,
                    (_timestamp(occurred_at), retirement_id),
                )
                self._record_event(
                    job.hardware_id,
                    job.pairing_id,
                    "retirement_runtime_cleanup_complete",
                    None,
                    occurred_at,
                    node_id=job.node_id,
                )
            return self._reconcile_retirement(retirement_id, occurred_at)

    def record_retirement_failure(
        self,
        retirement_id: int,
        error: str,
        *,
        now: datetime | None = None,
    ) -> RetirementJob:
        normalized_error = error.strip() or "retirement_cleanup_failed"
        occurred_at = _utc(now or datetime.now(UTC))
        with self._lock, self._connection:
            self.get_retirement_job(retirement_id)
            self._connection.execute(
                """
                UPDATE retirement_outbox
                SET attempts = attempts + 1, last_error = ?, updated_at = ?
                WHERE retirement_id = ?
                """,
                (normalized_error[:512], _timestamp(occurred_at), retirement_id),
            )
            return self.get_retirement_job(retirement_id)

    def node_id_lease_state(self, node_id: str) -> NodeIdLeaseState | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT state FROM node_id_leases WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if row is None:
                return None
            return NodeIdLeaseState(row["state"])

    def is_node_id_ingress_allowed(self, node_id: str) -> bool:
        state = self.node_id_lease_state(node_id)
        return state is None or state is NodeIdLeaseState.ACTIVE

    def _reconcile_retirement(self, retirement_id: int, occurred_at: datetime) -> RetirementJob:
        row = self._connection.execute(
            "SELECT * FROM retirement_outbox WHERE retirement_id = ?",
            (retirement_id,),
        ).fetchone()
        if row is None:
            raise KeyError(retirement_id)
        if (
            row["credentials_revoked"]
            and row["runtime_cleanup_complete"]
            and row["state"] != RetirementState.COMPLETED
        ):
            self._connection.execute(
                """
                UPDATE retirement_outbox
                SET state = ?, completed_at = ?, updated_at = ?, last_error = NULL
                WHERE retirement_id = ?
                """,
                (
                    RetirementState.COMPLETED,
                    _timestamp(occurred_at),
                    _timestamp(occurred_at),
                    retirement_id,
                ),
            )
            self._connection.execute(
                """
                UPDATE node_id_leases
                SET state = ?, updated_at = ?
                WHERE retirement_id = ?
                """,
                (NodeIdLeaseState.REUSABLE, _timestamp(occurred_at), retirement_id),
            )
            self._record_event(
                row["hardware_id"],
                row["pairing_id"],
                "retirement_completed",
                None,
                occurred_at,
                node_id=row["node_id"],
            )
        return self.get_retirement_job(retirement_id)

    def _validate_node_id_claim(
        self,
        hardware_id: str,
        node_id: str,
        *,
        logical_location_id: str | None,
        reuse_retired_node_id: bool,
        private_identity_bound: bool,
        anonymous_compatibility_enabled: bool,
    ) -> str | None:
        lease = self._connection.execute(
            "SELECT * FROM node_id_leases WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if lease is None:
            return None
        state = NodeIdLeaseState(lease["state"])
        owner = str(lease["hardware_id"])
        lease_logical_location_id = lease["logical_location_id"]
        if state is NodeIdLeaseState.ACTIVE:
            if owner != hardware_id:
                raise RegistrationConflict("node_id is already assigned")
            if (
                lease_logical_location_id is not None
                and logical_location_id is not None
                and lease_logical_location_id != logical_location_id
            ):
                raise RegistrationConflict(
                    "logical_location_id change requires retiring the existing hardware"
                )
            return None
        if state is NodeIdLeaseState.RETIRING:
            raise RegistrationConflict("node_id retirement cleanup is incomplete")
        if owner != hardware_id and not reuse_retired_node_id:
            raise RegistrationConflict("explicit retired node_id reuse approval is required")
        if owner != hardware_id and lease_logical_location_id is None:
            raise RegistrationConflict(
                "retired node_id has no logical location evidence and cannot be reused"
            )
        if owner != hardware_id and logical_location_id is None:
            raise RegistrationConflict("logical_location_id is required to reuse a retired node_id")
        if owner != hardware_id and lease_logical_location_id != logical_location_id:
            raise RegistrationConflict("retired node_id may only be reused for the same logical location")
        if owner != hardware_id and anonymous_compatibility_enabled:
            raise RegistrationConflict(
                "anonymous compatibility must be disabled before reusing a retired node_id"
            )
        if owner != hardware_id and not private_identity_bound:
            raise RegistrationConflict("private identity binding is required to reuse a retired node_id")
        return owner if owner != hardware_id else None

    def _activate_node_id_lease(
        self,
        hardware_id: str,
        node_id: str,
        logical_location_id: str | None,
        occurred_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO node_id_leases (
                node_id, hardware_id, logical_location_id, state,
                retirement_id, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                hardware_id = excluded.hardware_id,
                logical_location_id = excluded.logical_location_id,
                state = excluded.state,
                retirement_id = NULL,
                updated_at = excluded.updated_at
            """,
            (
                node_id,
                hardware_id,
                logical_location_id,
                NodeIdLeaseState.ACTIVE,
                _timestamp(occurred_at),
            ),
        )

    def _open_assignment_history(
        self,
        hardware_id: str,
        node_id: str,
        logical_location_id: str | None,
        assigned_at: datetime,
    ) -> None:
        row = self._connection.execute(
            """
            SELECT 1
            FROM registration_node_history
            WHERE hardware_id = ? AND released_at IS NULL
            """,
            (hardware_id,),
        ).fetchone()
        if row is None:
            self._connection.execute(
                """
                INSERT INTO registration_node_history (
                    hardware_id, node_id, logical_location_id, assigned_at,
                    released_at, retirement_event_id
                ) VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (
                    hardware_id,
                    node_id,
                    logical_location_id,
                    _timestamp(assigned_at),
                ),
            )

    def _close_assignment_history(
        self,
        record: RegistrationRecord,
        *,
        released_at: datetime,
        retirement_event_id: int,
    ) -> None:
        cursor = self._connection.execute(
            """
            UPDATE registration_node_history
            SET released_at = ?, retirement_event_id = ?
            WHERE hardware_id = ? AND node_id = ? AND released_at IS NULL
            """,
            (
                _timestamp(released_at),
                retirement_event_id,
                record.hardware_id,
                record.node_id,
            ),
        )
        if cursor.rowcount == 0:
            self._connection.execute(
                """
                INSERT INTO registration_node_history (
                    hardware_id, node_id, logical_location_id, assigned_at,
                    released_at, retirement_event_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.hardware_id,
                    record.node_id,
                    record.logical_location_id,
                    _timestamp(record.first_seen_at),
                    _timestamp(released_at),
                    retirement_event_id,
                ),
            )

    @staticmethod
    def _row_to_retirement(row: sqlite3.Row) -> RetirementJob:
        return RetirementJob(
            retirement_id=row["retirement_id"],
            hardware_id=row["hardware_id"],
            pairing_id=row["pairing_id"],
            node_id=row["node_id"],
            logical_location_id=row["logical_location_id"],
            system_id=row["system_id"],
            reason=row["reason"],
            credentials_revoked=bool(row["credentials_revoked"]),
            credential_evidence=row["credential_evidence"],
            runtime_cleanup_complete=bool(row["runtime_cleanup_complete"]),
            state=RetirementState(row["state"]),
            attempts=row["attempts"],
            last_error=row["last_error"],
            created_at=_parse_timestamp(row["created_at"]),
            updated_at=_parse_timestamp(row["updated_at"]),
            completed_at=(_parse_timestamp(row["completed_at"]) if row["completed_at"] is not None else None),
        )

    def _require_current(self, hardware_id: str, pairing_id: str) -> RegistrationRecord:
        record = self.get(hardware_id)
        if record.pairing_id != pairing_id:
            raise RegistrationConflict("pairing_id is not the current session")
        return record

    def _current_row(self, hardware_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT s.*, r.current_pairing_id, r.node_id, r.logical_location_id,
                   r.repair_authorized, r.retired_at, r.retirement_reason
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

    def _set_session_state(self, pairing_id: str, state: RegistrationState, reason: str | None) -> None:
        self._connection.execute(
            "UPDATE pairing_sessions SET state = ?, reason = ? WHERE pairing_id = ?",
            (state, reason, pairing_id),
        )

    def _record_event(
        self,
        hardware_id: str,
        pairing_id: str,
        event: str,
        reason: str | None,
        occurred_at: datetime,
        *,
        node_id: str | None = None,
        logical_location_id: str | None = None,
    ) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO registration_events (
                hardware_id, pairing_id, node_id, logical_location_id,
                event, reason, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hardware_id,
                pairing_id,
                node_id,
                logical_location_id,
                event,
                reason,
                _timestamp(occurred_at),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _row_to_record(row: sqlite3.Row, node_id: str | None) -> RegistrationRecord:
        columns = set(row.keys())
        retired_at_text = row["retired_at"] if "retired_at" in columns else None
        retirement_reason = row["retirement_reason"] if "retirement_reason" in columns else None
        logical_location_id = row["logical_location_id"] if "logical_location_id" in columns else None
        retired_at = _parse_timestamp(retired_at_text) if retired_at_text is not None else None
        return RegistrationRecord(
            hardware_id=row["hardware_id"],
            pairing_id=row["pairing_id"],
            pairing_epoch=row["pairing_epoch"],
            model=row["model"],
            fw_version=row["fw_version"],
            node_nonce=row["node_nonce"],
            capabilities=tuple(json.loads(row["capabilities_json"])),
            state=(RegistrationState.RETIRED if retired_at is not None else RegistrationState(row["state"])),
            first_seen_at=_parse_timestamp(row["first_seen_at"]),
            last_seen_at=_parse_timestamp(row["last_seen_at"]),
            expires_at=_parse_timestamp(row["expires_at"]),
            node_id=node_id,
            logical_location_id=logical_location_id,
            retired_at=retired_at,
            reason=retirement_reason if retired_at is not None else row["reason"],
        )
