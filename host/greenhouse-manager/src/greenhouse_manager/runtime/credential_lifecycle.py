from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class CredentialState(StrEnum):
    ACTIVE = "active"
    ROTATING = "rotating"
    REVOKED = "revoked"
    RECOVERY_REQUIRED = "recovery_required"


class CredentialLifecycleConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CredentialLifecycle:
    hardware_id: str
    node_id: str | None
    last_node_id: str
    active_generation: int
    pending_generation: int | None
    state: CredentialState
    reason: str | None
    updated_at: datetime
    assignment_id: int
    pairing_id: str | None
    created_at: datetime
    revoked_at: datetime | None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class CredentialLifecycleStore:
    """Secret-free, multi-assignment credential lifecycle history."""

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self._lock = threading.RLock()
        self._read_only = read_only
        database = Path(path)
        if read_only:
            if not database.is_file() or database.is_symlink():
                raise CredentialLifecycleConflict("credential lifecycle database is missing or unsafe")
            self._connection = sqlite3.connect(
                f"{database.resolve().as_uri()}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
        else:
            self._connection = sqlite3.connect(
                str(database),
                isolation_level="IMMEDIATE",
                check_same_thread=False,
            )
        self._connection.row_factory = sqlite3.Row
        if read_only:
            try:
                self._validate_read_only_schema()
            except Exception:
                self._connection.close()
                raise
        else:
            self._initialize()

    def _validate_read_only_schema(self) -> None:
        required = {
            "assignment_id",
            "hardware_id",
            "pairing_id",
            "node_id",
            "last_node_id",
            "active_generation",
            "pending_generation",
            "state",
            "reason",
            "created_at",
            "updated_at",
            "revoked_at",
        }
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(credential_assignments)").fetchall()
        }
        if columns != required:
            raise CredentialLifecycleConflict("credential lifecycle read-only schema is invalid")

    def _require_writable(self) -> None:
        if self._read_only:
            raise CredentialLifecycleConflict("credential lifecycle store is read-only")

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS credential_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hardware_id TEXT NOT NULL,
                    pairing_id TEXT,
                    node_id TEXT UNIQUE,
                    last_node_id TEXT NOT NULL UNIQUE,
                    active_generation INTEGER NOT NULL CHECK (active_generation >= 1),
                    pending_generation INTEGER,
                    state TEXT NOT NULL CHECK (
                        state IN ('active', 'rotating', 'revoked', 'recovery_required')
                    ),
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revoked_at TEXT,
                    CHECK (
                        pending_generation IS NULL
                        OR pending_generation > active_generation
                    ),
                    CHECK (state = 'revoked' OR node_id IS NOT NULL)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS credential_assignments_current_hardware
                    ON credential_assignments(hardware_id)
                    WHERE state != 'revoked';

                CREATE INDEX IF NOT EXISTS credential_assignments_hardware_history
                    ON credential_assignments(hardware_id, assignment_id);
                """
            )
            self._migrate_v06_table()

    def _migrate_v06_table(self) -> None:
        legacy = self._connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'credential_lifecycle'
            """
        ).fetchone()
        if legacy is None:
            return
        rows = self._connection.execute(
            """
            SELECT hardware_id, node_id, last_node_id, active_generation,
                   pending_generation, state, reason, updated_at
            FROM credential_lifecycle
            ORDER BY hardware_id
            """
        ).fetchall()
        existing = self._connection.execute(
            "SELECT COUNT(*) AS count FROM credential_assignments"
        ).fetchone()["count"]
        if existing and rows:
            raise CredentialLifecycleConflict(
                "cannot merge legacy credential lifecycle into non-empty assignment history"
            )
        for row in rows:
            revoked_at = row["updated_at"] if row["state"] == CredentialState.REVOKED else None
            self._connection.execute(
                """
                INSERT INTO credential_assignments (
                    hardware_id, pairing_id, node_id, last_node_id,
                    active_generation, pending_generation, state, reason,
                    created_at, updated_at, revoked_at
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["hardware_id"],
                    row["node_id"],
                    row["last_node_id"],
                    row["active_generation"],
                    row["pending_generation"],
                    row["state"],
                    row["reason"],
                    row["updated_at"],
                    row["updated_at"],
                    revoked_at,
                ),
            )
        self._connection.execute("DROP TABLE credential_lifecycle")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> CredentialLifecycleStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def activate(
        self,
        *,
        hardware_id: str,
        node_id: str,
        generation: int,
        pairing_id: str | None = None,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        self._require_writable()
        if generation < 1:
            raise ValueError("generation must be positive")
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._current_row(hardware_id)
            if current is not None:
                raise CredentialLifecycleConflict("credential lifecycle already exists")
            maximum = self._connection.execute(
                """
                SELECT MAX(active_generation) AS maximum
                FROM credential_assignments
                WHERE hardware_id = ?
                """,
                (hardware_id,),
            ).fetchone()["maximum"]
            if maximum is not None and generation <= int(maximum):
                raise CredentialLifecycleConflict("generation must increase across assignments")
            try:
                self._connection.execute(
                    """
                    INSERT INTO credential_assignments (
                        hardware_id, pairing_id, node_id, last_node_id,
                        active_generation, pending_generation, state, reason,
                        created_at, updated_at, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?, NULL)
                    """,
                    (
                        hardware_id,
                        pairing_id,
                        node_id,
                        node_id,
                        generation,
                        CredentialState.ACTIVE,
                        _timestamp(updated_at),
                        _timestamp(updated_at),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise CredentialLifecycleConflict(
                    "node_id has already been used and is permanently reserved"
                ) from error
            return self.get(hardware_id)

    def begin_rotation(
        self,
        hardware_id: str,
        *,
        generation: int,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        self._require_writable()
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._require_current(hardware_id)
            if current.state is not CredentialState.ACTIVE:
                raise CredentialLifecycleConflict(
                    f"cannot rotate credentials in {current.state} state"
                )
            if generation <= current.active_generation:
                raise CredentialLifecycleConflict("generation must increase")
            self._connection.execute(
                """
                UPDATE credential_assignments
                SET pending_generation = ?, state = ?, reason = NULL, updated_at = ?
                WHERE assignment_id = ?
                """,
                (
                    generation,
                    CredentialState.ROTATING,
                    _timestamp(updated_at),
                    current.assignment_id,
                ),
            )
            return self.get(hardware_id)

    def commit_rotation(
        self, hardware_id: str, *, now: datetime | None = None
    ) -> CredentialLifecycle:
        self._require_writable()
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._require_current(hardware_id)
            if (
                current.state is not CredentialState.ROTATING
                or current.pending_generation is None
            ):
                raise CredentialLifecycleConflict("no credential rotation is pending")
            self._connection.execute(
                """
                UPDATE credential_assignments
                SET active_generation = pending_generation, pending_generation = NULL,
                    state = ?, reason = NULL, updated_at = ?
                WHERE assignment_id = ?
                """,
                (
                    CredentialState.ACTIVE,
                    _timestamp(updated_at),
                    current.assignment_id,
                ),
            )
            return self.get(hardware_id)

    def roll_back_rotation(
        self,
        hardware_id: str,
        *,
        reason: str = "candidate_verification_failed",
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        self._require_writable()
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._require_current(hardware_id)
            if current.state is not CredentialState.ROTATING:
                raise CredentialLifecycleConflict("no credential rotation is pending")
            self._connection.execute(
                """
                UPDATE credential_assignments
                SET pending_generation = NULL, state = ?, reason = ?, updated_at = ?
                WHERE assignment_id = ?
                """,
                (
                    CredentialState.ACTIVE,
                    reason,
                    _timestamp(updated_at),
                    current.assignment_id,
                ),
            )
            return self.get(hardware_id)

    def revoke(
        self,
        hardware_id: str,
        *,
        reason: str = "operator_revoked",
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        self._require_writable()
        if not reason:
            raise ValueError("reason must not be empty")
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._current_row(hardware_id)
            if current is None:
                latest = self.get(hardware_id)
                if latest.state is CredentialState.REVOKED:
                    return latest
                raise CredentialLifecycleConflict("no revocable credential assignment exists")
            self._connection.execute(
                """
                UPDATE credential_assignments
                SET node_id = NULL, pending_generation = NULL, state = ?,
                    reason = ?, updated_at = ?, revoked_at = ?
                WHERE assignment_id = ?
                """,
                (
                    CredentialState.REVOKED,
                    reason,
                    _timestamp(updated_at),
                    _timestamp(updated_at),
                    current["assignment_id"],
                ),
            )
            return self.get(hardware_id)

    def require_recovery(
        self,
        hardware_id: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        self._require_writable()
        if not reason:
            raise ValueError("reason must not be empty")
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._require_current(hardware_id)
            self._connection.execute(
                """
                UPDATE credential_assignments
                SET pending_generation = NULL, state = ?, reason = ?, updated_at = ?
                WHERE assignment_id = ?
                """,
                (
                    CredentialState.RECOVERY_REQUIRED,
                    reason,
                    _timestamp(updated_at),
                    current.assignment_id,
                ),
            )
            return self.get(hardware_id)

    def get(self, hardware_id: str) -> CredentialLifecycle:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM credential_assignments
                WHERE hardware_id = ?
                ORDER BY assignment_id DESC
                LIMIT 1
                """,
                (hardware_id,),
            ).fetchone()
            if row is None:
                raise KeyError(hardware_id)
            return self._row_to_record(row)

    def list_for_hardware(self, hardware_id: str) -> tuple[CredentialLifecycle, ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM credential_assignments
                WHERE hardware_id = ?
                ORDER BY assignment_id
                """,
                (hardware_id,),
            ).fetchall()
            return tuple(self._row_to_record(row) for row in rows)

    def _require_current(self, hardware_id: str) -> CredentialLifecycle:
        row = self._current_row(hardware_id)
        if row is None:
            raise CredentialLifecycleConflict("no active credential assignment exists")
        return self._row_to_record(row)

    def _current_row(self, hardware_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT * FROM credential_assignments
            WHERE hardware_id = ? AND state != ?
            ORDER BY assignment_id DESC
            LIMIT 1
            """,
            (hardware_id, CredentialState.REVOKED),
        ).fetchone()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> CredentialLifecycle:
        return CredentialLifecycle(
            hardware_id=row["hardware_id"],
            node_id=row["node_id"],
            last_node_id=row["last_node_id"],
            active_generation=row["active_generation"],
            pending_generation=row["pending_generation"],
            state=CredentialState(row["state"]),
            reason=row["reason"],
            updated_at=_parse_timestamp(row["updated_at"]),
            assignment_id=row["assignment_id"],
            pairing_id=row["pairing_id"],
            created_at=_parse_timestamp(row["created_at"]),
            revoked_at=(
                _parse_timestamp(row["revoked_at"])
                if row["revoked_at"] is not None
                else None
            ),
        )
