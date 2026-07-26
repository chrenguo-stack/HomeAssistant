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
    node_id: str
    active_generation: int
    pending_generation: int | None
    state: CredentialState
    reason: str | None
    updated_at: datetime


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class CredentialLifecycleStore:
    """Secret-free credential lifecycle metadata stored beside registration state."""

    def __init__(self, path: str | Path) -> None:
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(path), isolation_level="IMMEDIATE", check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS credential_lifecycle (
                    hardware_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL UNIQUE,
                    active_generation INTEGER NOT NULL CHECK (active_generation >= 1),
                    pending_generation INTEGER,
                    state TEXT NOT NULL CHECK (
                        state IN ('active', 'rotating', 'revoked', 'recovery_required')
                    ),
                    reason TEXT,
                    updated_at TEXT NOT NULL,
                    CHECK (
                        pending_generation IS NULL
                        OR pending_generation > active_generation
                    )
                );
                """
            )

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
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        if generation < 1:
            raise ValueError("generation must be positive")
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self._row(hardware_id)
            if current is not None:
                raise CredentialLifecycleConflict("credential lifecycle already exists")
            try:
                self._connection.execute(
                    """
                    INSERT INTO credential_lifecycle (
                        hardware_id, node_id, active_generation, pending_generation,
                        state, reason, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, NULL, ?)
                    """,
                    (
                        hardware_id,
                        node_id,
                        generation,
                        CredentialState.ACTIVE,
                        _timestamp(updated_at),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise CredentialLifecycleConflict("node_id is already assigned") from error
            return self.get(hardware_id)

    def begin_rotation(
        self,
        hardware_id: str,
        *,
        generation: int,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self.get(hardware_id)
            if current.state is not CredentialState.ACTIVE:
                raise CredentialLifecycleConflict(
                    f"cannot rotate credentials in {current.state} state"
                )
            if generation <= current.active_generation:
                raise CredentialLifecycleConflict("generation must increase")
            self._connection.execute(
                """
                UPDATE credential_lifecycle
                SET pending_generation = ?, state = ?, reason = NULL, updated_at = ?
                WHERE hardware_id = ?
                """,
                (
                    generation,
                    CredentialState.ROTATING,
                    _timestamp(updated_at),
                    hardware_id,
                ),
            )
            return self.get(hardware_id)

    def commit_rotation(
        self, hardware_id: str, *, now: datetime | None = None
    ) -> CredentialLifecycle:
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self.get(hardware_id)
            if (
                current.state is not CredentialState.ROTATING
                or current.pending_generation is None
            ):
                raise CredentialLifecycleConflict("no credential rotation is pending")
            self._connection.execute(
                """
                UPDATE credential_lifecycle
                SET active_generation = pending_generation, pending_generation = NULL,
                    state = ?, reason = NULL, updated_at = ?
                WHERE hardware_id = ?
                """,
                (CredentialState.ACTIVE, _timestamp(updated_at), hardware_id),
            )
            return self.get(hardware_id)

    def roll_back_rotation(
        self,
        hardware_id: str,
        *,
        reason: str = "candidate_verification_failed",
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            current = self.get(hardware_id)
            if current.state is not CredentialState.ROTATING:
                raise CredentialLifecycleConflict("no credential rotation is pending")
            self._connection.execute(
                """
                UPDATE credential_lifecycle
                SET pending_generation = NULL, state = ?, reason = ?, updated_at = ?
                WHERE hardware_id = ?
                """,
                (
                    CredentialState.ACTIVE,
                    reason,
                    _timestamp(updated_at),
                    hardware_id,
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
        return self._terminal_transition(
            hardware_id,
            state=CredentialState.REVOKED,
            reason=reason,
            now=now,
        )

    def require_recovery(
        self,
        hardware_id: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        return self._terminal_transition(
            hardware_id,
            state=CredentialState.RECOVERY_REQUIRED,
            reason=reason,
            now=now,
        )

    def _terminal_transition(
        self,
        hardware_id: str,
        *,
        state: CredentialState,
        reason: str,
        now: datetime | None,
    ) -> CredentialLifecycle:
        if not reason:
            raise ValueError("reason must not be empty")
        updated_at = now or datetime.now(UTC)
        with self._lock, self._connection:
            self.get(hardware_id)
            self._connection.execute(
                """
                UPDATE credential_lifecycle
                SET pending_generation = NULL, state = ?, reason = ?, updated_at = ?
                WHERE hardware_id = ?
                """,
                (state, reason, _timestamp(updated_at), hardware_id),
            )
            return self.get(hardware_id)

    def get(self, hardware_id: str) -> CredentialLifecycle:
        with self._lock:
            row = self._row(hardware_id)
            if row is None:
                raise KeyError(hardware_id)
            return CredentialLifecycle(
                hardware_id=row["hardware_id"],
                node_id=row["node_id"],
                active_generation=row["active_generation"],
                pending_generation=row["pending_generation"],
                state=CredentialState(row["state"]),
                reason=row["reason"],
                updated_at=_parse_timestamp(row["updated_at"]),
            )

    def _row(self, hardware_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM credential_lifecycle WHERE hardware_id = ?",
            (hardware_id,),
        ).fetchone()
