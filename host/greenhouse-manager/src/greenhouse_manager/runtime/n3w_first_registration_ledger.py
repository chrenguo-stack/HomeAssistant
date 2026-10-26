from __future__ import annotations

import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NODE_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


class FirstRegistrationLedgerConflict(RuntimeError):
    pass


class FirstRegistrationAttemptState(StrEnum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    EXPIRED = "EXPIRED"
    RESTART_INVALIDATED = "RESTART_INVALIDATED"


class FirstRegistrationPhase(StrEnum):
    BOOTSTRAP_ACCEPTED = "BOOTSTRAP_ACCEPTED"
    HELLO_OBSERVED = "HELLO_OBSERVED"
    BUNDLE_STAGED = "BUNDLE_STAGED"
    COMMITTING = "COMMITTING"
    TERMINAL = "TERMINAL"


class FirstRegistrationCleanupState(StrEnum):
    NONE = "NONE"
    REQUIRED = "REQUIRED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class FirstRegistrationAttempt:
    pairing_id: str
    hardware_id_sha256: str
    opened_at: datetime
    expires_at: datetime
    state: FirstRegistrationAttemptState
    phase: FirstRegistrationPhase
    cleanup_state: FirstRegistrationCleanupState
    node_id: str | None
    dynsec_prestate_absent: bool | None
    application_key_prestate_absent: bool | None
    application_key_epoch: int | None
    delivery_digest_sha256: str | None
    terminal_at: datetime | None
    terminal_reason: str | None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _require_pairing_id(value: str) -> None:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValueError("pairing_id is invalid") from error
    if str(parsed) != value:
        raise ValueError("pairing_id is invalid")


def _require_sha256(value: str, *, label: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")


def initialize_first_registration_ledger(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS first_registration_attempts (
            pairing_id TEXT PRIMARY KEY,
            hardware_id_sha256 TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            state TEXT NOT NULL CHECK (
                state IN ('ACTIVE', 'COMMITTED', 'EXPIRED', 'RESTART_INVALIDATED')
            ),
            phase TEXT NOT NULL CHECK (
                phase IN (
                    'BOOTSTRAP_ACCEPTED',
                    'HELLO_OBSERVED',
                    'BUNDLE_STAGED',
                    'COMMITTING',
                    'TERMINAL'
                )
            ),
            cleanup_state TEXT NOT NULL CHECK (
                cleanup_state IN ('NONE', 'REQUIRED', 'COMPLETE', 'FAILED')
            ),
            node_id TEXT,
            dynsec_prestate_absent INTEGER CHECK (
                dynsec_prestate_absent IS NULL
                OR dynsec_prestate_absent IN (0, 1)
            ),
            application_key_prestate_absent INTEGER CHECK (
                application_key_prestate_absent IS NULL
                OR application_key_prestate_absent IN (0, 1)
            ),
            application_key_epoch INTEGER CHECK (
                application_key_epoch IS NULL OR application_key_epoch >= 1
            ),
            delivery_digest_sha256 TEXT,
            terminal_at TEXT,
            terminal_reason TEXT
        );

        CREATE INDEX IF NOT EXISTS first_registration_attempts_reconciliation
            ON first_registration_attempts(state, cleanup_state, expires_at);
        """
    )


class FirstRegistrationLedger:
    def __init__(
        self,
        connection: sqlite3.Connection,
        lock: threading.RLock,
    ) -> None:
        self._connection = connection
        self._lock = lock

    def create_active(
        self,
        *,
        pairing_id: str,
        hardware_id_sha256: str,
        opened_at: datetime,
        expires_at: datetime,
    ) -> FirstRegistrationAttempt:
        _require_pairing_id(pairing_id)
        _require_sha256(hardware_id_sha256, label="hardware_id_sha256")
        opened = opened_at.astimezone(UTC) if opened_at.tzinfo is not None else None
        expires = expires_at.astimezone(UTC) if expires_at.tzinfo is not None else None
        if opened is None or expires is None:
            raise ValueError("attempt timestamps must be timezone-aware")
        if expires <= opened:
            raise ValueError("attempt deadline must be after opened_at")
        with self._lock, self._connection:
            try:
                self._connection.execute(
                    """
                    INSERT INTO first_registration_attempts (
                        pairing_id,
                        hardware_id_sha256,
                        opened_at,
                        expires_at,
                        state,
                        phase,
                        cleanup_state,
                        node_id,
                        dynsec_prestate_absent,
                        application_key_prestate_absent,
                        application_key_epoch,
                        delivery_digest_sha256,
                        terminal_at,
                        terminal_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
                    """,
                    (
                        pairing_id,
                        hardware_id_sha256,
                        _timestamp(opened),
                        _timestamp(expires),
                        FirstRegistrationAttemptState.ACTIVE,
                        FirstRegistrationPhase.BOOTSTRAP_ACCEPTED,
                        FirstRegistrationCleanupState.NONE,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise FirstRegistrationLedgerConflict(
                    "first registration pairing_id already exists"
                ) from error
            return self.get(pairing_id)

    def get(self, pairing_id: str) -> FirstRegistrationAttempt:
        _require_pairing_id(pairing_id)
        with self._lock:
            row = self._row(pairing_id)
            if row is None:
                raise KeyError(pairing_id)
            return self._attempt(row)

    def list_reconcilable(self) -> tuple[FirstRegistrationAttempt, ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM first_registration_attempts
                WHERE state = 'ACTIVE'
                   OR (
                        state IN ('EXPIRED', 'RESTART_INVALIDATED')
                        AND cleanup_state != 'COMPLETE'
                   )
                ORDER BY opened_at, pairing_id
                """
            ).fetchall()
            return tuple(self._attempt(row) for row in rows)

    def mark_hello_observed(self, pairing_id: str) -> FirstRegistrationAttempt:
        with self._lock, self._connection:
            current = self._require_active(pairing_id)
            if current.phase is FirstRegistrationPhase.HELLO_OBSERVED:
                return current
            if current.phase is not FirstRegistrationPhase.BOOTSTRAP_ACCEPTED:
                raise FirstRegistrationLedgerConflict(
                    "first registration hello phase transition invalid"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET phase = ?
                WHERE pairing_id = ?
                """,
                (FirstRegistrationPhase.HELLO_OBSERVED, pairing_id),
            )
            return self.get(pairing_id)

    def record_dynsec_prestate(
        self,
        pairing_id: str,
        *,
        node_id: str,
        absent: bool,
    ) -> FirstRegistrationAttempt:
        self._require_node_id(node_id)
        with self._lock, self._connection:
            current = self._require_mutable_staging(pairing_id)
            if current.node_id is not None and current.node_id != node_id:
                raise FirstRegistrationLedgerConflict(
                    "first registration node binding conflict"
                )
            if (
                current.dynsec_prestate_absent is not None
                and current.dynsec_prestate_absent is not absent
            ):
                raise FirstRegistrationLedgerConflict(
                    "first registration dynsec prestate conflict"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET node_id = ?, dynsec_prestate_absent = ?
                WHERE pairing_id = ?
                """,
                (node_id, int(absent), pairing_id),
            )
            return self.get(pairing_id)

    def record_application_key_prestate(
        self,
        pairing_id: str,
        *,
        node_id: str,
        absent: bool,
    ) -> FirstRegistrationAttempt:
        self._require_node_id(node_id)
        with self._lock, self._connection:
            current = self._require_mutable_staging(pairing_id)
            if current.node_id is not None and current.node_id != node_id:
                raise FirstRegistrationLedgerConflict(
                    "first registration node binding conflict"
                )
            if (
                current.application_key_prestate_absent is not None
                and current.application_key_prestate_absent is not absent
            ):
                raise FirstRegistrationLedgerConflict(
                    "first registration application-key prestate conflict"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET node_id = ?, application_key_prestate_absent = ?
                WHERE pairing_id = ?
                """,
                (node_id, int(absent), pairing_id),
            )
            return self.get(pairing_id)

    def mark_bundle_staged(
        self,
        pairing_id: str,
        *,
        node_id: str,
        application_key_epoch: int,
        delivery_digest_sha256: str,
    ) -> FirstRegistrationAttempt:
        self._require_node_id(node_id)
        if (
            not isinstance(application_key_epoch, int)
            or isinstance(application_key_epoch, bool)
            or application_key_epoch < 1
        ):
            raise ValueError("application_key_epoch is invalid")
        _require_sha256(
            delivery_digest_sha256,
            label="delivery_digest_sha256",
        )
        with self._lock, self._connection:
            current = self._require_active(pairing_id)
            if current.phase is FirstRegistrationPhase.BUNDLE_STAGED:
                if (
                    current.node_id == node_id
                    and current.application_key_epoch == application_key_epoch
                    and current.delivery_digest_sha256 == delivery_digest_sha256
                ):
                    return current
                raise FirstRegistrationLedgerConflict(
                    "first registration bundle binding conflict"
                )
            if current.phase is not FirstRegistrationPhase.HELLO_OBSERVED:
                raise FirstRegistrationLedgerConflict(
                    "first registration bundle phase transition invalid"
                )
            if (
                current.node_id != node_id
                or current.dynsec_prestate_absent is not True
                or current.application_key_prestate_absent is not True
            ):
                raise FirstRegistrationLedgerConflict(
                    "first registration ownership proof incomplete"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET phase = ?,
                    application_key_epoch = ?,
                    delivery_digest_sha256 = ?
                WHERE pairing_id = ?
                """,
                (
                    FirstRegistrationPhase.BUNDLE_STAGED,
                    application_key_epoch,
                    delivery_digest_sha256,
                    pairing_id,
                ),
            )
            return self.get(pairing_id)

    def claim_committing(self, pairing_id: str) -> FirstRegistrationAttempt:
        with self._lock, self._connection:
            current = self._require_active(pairing_id)
            if current.phase is FirstRegistrationPhase.COMMITTING:
                return current
            if current.phase is not FirstRegistrationPhase.BUNDLE_STAGED:
                raise FirstRegistrationLedgerConflict(
                    "first registration committing transition invalid"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET phase = ?
                WHERE pairing_id = ?
                """,
                (FirstRegistrationPhase.COMMITTING, pairing_id),
            )
            return self.get(pairing_id)

    def mark_committed(
        self,
        pairing_id: str,
        *,
        terminal_at: datetime,
    ) -> FirstRegistrationAttempt:
        with self._lock, self._connection:
            current = self._require_active(pairing_id)
            if current.phase is not FirstRegistrationPhase.COMMITTING:
                raise FirstRegistrationLedgerConflict(
                    "first registration commit claim missing"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET state = ?,
                    phase = ?,
                    cleanup_state = ?,
                    terminal_at = ?,
                    terminal_reason = NULL
                WHERE pairing_id = ?
                """,
                (
                    FirstRegistrationAttemptState.COMMITTED,
                    FirstRegistrationPhase.TERMINAL,
                    FirstRegistrationCleanupState.COMPLETE,
                    _timestamp(terminal_at),
                    pairing_id,
                ),
            )
            return self.get(pairing_id)

    def terminalize_not_committed(
        self,
        pairing_id: str,
        *,
        state: FirstRegistrationAttemptState,
        cleanup_state: FirstRegistrationCleanupState,
        terminal_at: datetime,
        terminal_reason: str,
    ) -> FirstRegistrationAttempt:
        if state not in {
            FirstRegistrationAttemptState.EXPIRED,
            FirstRegistrationAttemptState.RESTART_INVALIDATED,
        }:
            raise ValueError("terminal state is invalid")
        if cleanup_state not in {
            FirstRegistrationCleanupState.REQUIRED,
            FirstRegistrationCleanupState.FAILED,
        }:
            raise ValueError("terminal cleanup state is invalid")
        if terminal_reason not in {"expired", "replay_detected"}:
            raise ValueError("terminal_reason is invalid")
        with self._lock, self._connection:
            self._require_active(pairing_id)
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET state = ?,
                    phase = ?,
                    cleanup_state = ?,
                    terminal_at = ?,
                    terminal_reason = ?
                WHERE pairing_id = ?
                """,
                (
                    state,
                    FirstRegistrationPhase.TERMINAL,
                    cleanup_state,
                    _timestamp(terminal_at),
                    terminal_reason,
                    pairing_id,
                ),
            )
            return self.get(pairing_id)

    def mark_cleanup_complete(self, pairing_id: str) -> FirstRegistrationAttempt:
        with self._lock, self._connection:
            current = self.get(pairing_id)
            if current.state not in {
                FirstRegistrationAttemptState.EXPIRED,
                FirstRegistrationAttemptState.RESTART_INVALIDATED,
            }:
                raise FirstRegistrationLedgerConflict(
                    "first registration cleanup target is not terminal"
                )
            if current.cleanup_state is FirstRegistrationCleanupState.COMPLETE:
                return current
            if current.cleanup_state not in {
                FirstRegistrationCleanupState.REQUIRED,
                FirstRegistrationCleanupState.FAILED,
            }:
                raise FirstRegistrationLedgerConflict(
                    "first registration cleanup transition invalid"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET cleanup_state = ?
                WHERE pairing_id = ?
                """,
                (FirstRegistrationCleanupState.COMPLETE, pairing_id),
            )
            return self.get(pairing_id)

    def mark_cleanup_failed(self, pairing_id: str) -> FirstRegistrationAttempt:
        with self._lock, self._connection:
            current = self.get(pairing_id)
            if current.state not in {
                FirstRegistrationAttemptState.EXPIRED,
                FirstRegistrationAttemptState.RESTART_INVALIDATED,
            }:
                raise FirstRegistrationLedgerConflict(
                    "first registration cleanup target is not terminal"
                )
            if current.cleanup_state is FirstRegistrationCleanupState.COMPLETE:
                raise FirstRegistrationLedgerConflict(
                    "first registration completed cleanup cannot regress"
                )
            self._connection.execute(
                """
                UPDATE first_registration_attempts
                SET cleanup_state = ?
                WHERE pairing_id = ?
                """,
                (FirstRegistrationCleanupState.FAILED, pairing_id),
            )
            return self.get(pairing_id)

    def _require_active(self, pairing_id: str) -> FirstRegistrationAttempt:
        current = self.get(pairing_id)
        if current.state is not FirstRegistrationAttemptState.ACTIVE:
            raise FirstRegistrationLedgerConflict(
                "first registration attempt is not active"
            )
        return current

    def _require_mutable_staging(
        self,
        pairing_id: str,
    ) -> FirstRegistrationAttempt:
        current = self._require_active(pairing_id)
        if current.phase not in {
            FirstRegistrationPhase.HELLO_OBSERVED,
            FirstRegistrationPhase.BOOTSTRAP_ACCEPTED,
        }:
            raise FirstRegistrationLedgerConflict(
                "first registration ownership proof phase invalid"
            )
        return current

    def _row(self, pairing_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT *
            FROM first_registration_attempts
            WHERE pairing_id = ?
            """,
            (pairing_id,),
        ).fetchone()

    @staticmethod
    def _require_node_id(node_id: str) -> None:
        if not isinstance(node_id, str) or _NODE_ID.fullmatch(node_id) is None:
            raise ValueError("node_id is invalid")

    @staticmethod
    def _attempt(row: sqlite3.Row) -> FirstRegistrationAttempt:
        try:
            hardware_hash = row["hardware_id_sha256"]
            delivery_hash = row["delivery_digest_sha256"]
            _require_sha256(hardware_hash, label="hardware_id_sha256")
            if delivery_hash is not None:
                _require_sha256(
                    delivery_hash,
                    label="delivery_digest_sha256",
                )
            dynsec_prestate = row["dynsec_prestate_absent"]
            application_prestate = row["application_key_prestate_absent"]
            return FirstRegistrationAttempt(
                pairing_id=row["pairing_id"],
                hardware_id_sha256=hardware_hash,
                opened_at=_parse_timestamp(row["opened_at"]),
                expires_at=_parse_timestamp(row["expires_at"]),
                state=FirstRegistrationAttemptState(row["state"]),
                phase=FirstRegistrationPhase(row["phase"]),
                cleanup_state=FirstRegistrationCleanupState(
                    row["cleanup_state"]
                ),
                node_id=row["node_id"],
                dynsec_prestate_absent=(
                    None
                    if dynsec_prestate is None
                    else bool(dynsec_prestate)
                ),
                application_key_prestate_absent=(
                    None
                    if application_prestate is None
                    else bool(application_prestate)
                ),
                application_key_epoch=row["application_key_epoch"],
                delivery_digest_sha256=delivery_hash,
                terminal_at=(
                    None
                    if row["terminal_at"] is None
                    else _parse_timestamp(row["terminal_at"])
                ),
                terminal_reason=row["terminal_reason"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise FirstRegistrationLedgerConflict(
                "first registration ledger record is corrupt"
            ) from error
