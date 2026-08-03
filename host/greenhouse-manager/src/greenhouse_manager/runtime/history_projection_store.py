from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from .history_store import _parse_timestamp, _private_path, _timestamp

ProjectionJobState = Literal["pending", "leased", "retry", "blocked", "completed"]


class ProjectionStoreError(RuntimeError):
    """Base class for C06-B1 projection storage failures."""


@dataclass(frozen=True, slots=True)
class ProjectionTask:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    attempts: int
    claimed_by: str
    lease_until: datetime


@dataclass(frozen=True, slots=True)
class ProjectionJobSnapshot:
    node_id: str
    sample_hour: str
    projection_version: int
    revision: int
    state: ProjectionJobState
    attempts: int
    claimed_by: str | None
    lease_until: datetime | None
    next_attempt_at: datetime | None
    last_error_code: str | None
    last_error: str | None
    projection_hash: str | None
    payload_json: str | None
    adapter_kind: str | None
    adapter_version: str | None
    verified_at: datetime | None
    completed_at: datetime | None


def _optional_timestamp(value: object) -> datetime | None:
    return _parse_timestamp(str(value)) if value is not None else None


class ProjectionStore:
    """Durable C06-B1 job state layered on the C06-A projection outbox."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        _private_path(self.path)
        if not self.path.is_file():
            raise ProjectionStoreError("C06-A manager state database must already exist")
        os.chmod(self.path, 0o600)
        if stat.S_IMODE(self.path.stat().st_mode) & 0o077:
            raise ProjectionStoreError(
                "projection database must not be group- or world-accessible"
            )
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path), isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._initialize()

    def _transaction(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")

    def _commit(self) -> None:
        self._connection.execute("COMMIT")

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")

    def _require_c06a_tables(self) -> None:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        names = {str(row["name"]) for row in rows}
        required = {"c06_history_records", "c06_projection_outbox"}
        missing = sorted(required - names)
        if missing:
            raise ProjectionStoreError(
                "C06-A projection prerequisites are missing: " + ",".join(missing)
            )

    def _initialize(self) -> None:
        with self._lock:
            self._require_c06a_tables()
            try:
                self._connection.executescript(
                    """
                    BEGIN IMMEDIATE;

                    CREATE TABLE IF NOT EXISTS c06b1_schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS c06_projection_jobs (
                        node_id TEXT NOT NULL,
                        sample_hour TEXT NOT NULL,
                        projection_version INTEGER NOT NULL,
                        revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                        state TEXT NOT NULL DEFAULT 'pending'
                            CHECK (state IN (
                                'pending', 'leased', 'retry', 'blocked', 'completed'
                            )),
                        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                        claimed_by TEXT,
                        lease_until TEXT,
                        next_attempt_at TEXT,
                        last_error_code TEXT,
                        last_error TEXT,
                        projection_hash TEXT,
                        payload_json TEXT,
                        adapter_kind TEXT,
                        adapter_version TEXT,
                        last_dispatched_at TEXT,
                        verified_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        completed_at TEXT,
                        PRIMARY KEY (node_id, sample_hour, projection_version),
                        FOREIGN KEY (node_id, sample_hour, projection_version)
                            REFERENCES c06_projection_outbox(
                                node_id, sample_hour, projection_version
                            ) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS c06_projection_jobs_due
                        ON c06_projection_jobs(
                            state, next_attempt_at, lease_until, sample_hour, node_id
                        );

                    INSERT OR IGNORE INTO c06_projection_jobs (
                        node_id, sample_hour, projection_version, revision, state,
                        attempts, claimed_by, lease_until, next_attempt_at,
                        last_error_code, last_error, projection_hash, payload_json,
                        adapter_kind, adapter_version, last_dispatched_at, verified_at,
                        created_at, updated_at, completed_at
                    )
                    SELECT
                        node_id, sample_hour, projection_version, 1,
                        CASE WHEN state = 'completed' THEN 'completed' ELSE 'pending' END,
                        attempts, NULL, NULL,
                        CASE WHEN state = 'pending' THEN updated_at ELSE NULL END,
                        NULL, last_error, NULL, NULL, NULL, NULL, NULL, NULL,
                        created_at, updated_at, completed_at
                    FROM c06_projection_outbox;

                    CREATE TRIGGER IF NOT EXISTS c06b1_projection_outbox_insert
                    AFTER INSERT ON c06_projection_outbox
                    WHEN NEW.state = 'pending'
                    BEGIN
                        INSERT INTO c06_projection_jobs (
                            node_id, sample_hour, projection_version, revision, state,
                            attempts, claimed_by, lease_until, next_attempt_at,
                            last_error_code, last_error, projection_hash, payload_json,
                            adapter_kind, adapter_version, last_dispatched_at, verified_at,
                            created_at, updated_at, completed_at
                        ) VALUES (
                            NEW.node_id, NEW.sample_hour, NEW.projection_version,
                            1, 'pending', 0, NULL, NULL, NEW.updated_at,
                            NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                            NEW.created_at, NEW.updated_at, NULL
                        )
                        ON CONFLICT(node_id, sample_hour, projection_version) DO UPDATE SET
                            revision = c06_projection_jobs.revision + 1,
                            state = 'pending',
                            claimed_by = NULL,
                            lease_until = NULL,
                            next_attempt_at = excluded.next_attempt_at,
                            last_error_code = NULL,
                            last_error = NULL,
                            projection_hash = NULL,
                            payload_json = NULL,
                            adapter_kind = NULL,
                            adapter_version = NULL,
                            last_dispatched_at = NULL,
                            verified_at = NULL,
                            updated_at = excluded.updated_at,
                            completed_at = NULL;
                    END;

                    CREATE TRIGGER IF NOT EXISTS c06b1_projection_outbox_reopen
                    AFTER UPDATE OF state, updated_at ON c06_projection_outbox
                    WHEN NEW.state = 'pending'
                    BEGIN
                        INSERT INTO c06_projection_jobs (
                            node_id, sample_hour, projection_version, revision, state,
                            attempts, claimed_by, lease_until, next_attempt_at,
                            last_error_code, last_error, projection_hash, payload_json,
                            adapter_kind, adapter_version, last_dispatched_at, verified_at,
                            created_at, updated_at, completed_at
                        ) VALUES (
                            NEW.node_id, NEW.sample_hour, NEW.projection_version,
                            1, 'pending', 0, NULL, NULL, NEW.updated_at,
                            NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                            NEW.created_at, NEW.updated_at, NULL
                        )
                        ON CONFLICT(node_id, sample_hour, projection_version) DO UPDATE SET
                            revision = c06_projection_jobs.revision + 1,
                            state = 'pending',
                            claimed_by = NULL,
                            lease_until = NULL,
                            next_attempt_at = excluded.next_attempt_at,
                            last_error_code = NULL,
                            last_error = NULL,
                            projection_hash = NULL,
                            payload_json = NULL,
                            adapter_kind = NULL,
                            adapter_version = NULL,
                            last_dispatched_at = NULL,
                            verified_at = NULL,
                            updated_at = excluded.updated_at,
                            completed_at = NULL;
                    END;
                    """
                )
                applied = {
                    int(row["version"])
                    for row in self._connection.execute(
                        "SELECT version FROM c06b1_schema_migrations"
                    ).fetchall()
                }
                unsupported = sorted(
                    version for version in applied if version > self.SCHEMA_VERSION
                )
                if unsupported:
                    raise ProjectionStoreError(
                        f"unsupported C06-B1 schema migration set: {unsupported}"
                    )
                if 1 not in applied:
                    self._connection.execute(
                        "INSERT INTO c06b1_schema_migrations(version, applied_at) "
                        "VALUES (1, ?)",
                        (_timestamp(datetime.now(UTC)),),
                    )
                self._commit()
            except Exception:
                self._rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> ProjectionStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def claim_next(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> ProjectionTask | None:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id must contain 1 to 128 characters")
        if not 5 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 5 and 3600")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        current_text = _timestamp(current)
        lease_until = current + timedelta(seconds=lease_seconds)
        lease_text = _timestamp(lease_until)
        with self._lock:
            self._transaction()
            try:
                row = self._connection.execute(
                    """
                    SELECT jobs.*
                    FROM c06_projection_jobs AS jobs
                    JOIN c06_projection_outbox AS outbox
                      ON outbox.node_id = jobs.node_id
                     AND outbox.sample_hour = jobs.sample_hour
                     AND outbox.projection_version = jobs.projection_version
                    WHERE outbox.state = 'pending'
                      AND (
                        jobs.state = 'pending'
                        OR (
                            jobs.state = 'retry'
                            AND (
                                jobs.next_attempt_at IS NULL
                                OR jobs.next_attempt_at <= ?
                            )
                        )
                        OR (
                            jobs.state = 'leased'
                            AND jobs.lease_until IS NOT NULL
                            AND jobs.lease_until <= ?
                        )
                      )
                    ORDER BY jobs.sample_hour, jobs.node_id, jobs.projection_version
                    LIMIT 1
                    """,
                    (current_text, current_text),
                ).fetchone()
                if row is None:
                    self._commit()
                    return None
                revision = int(row["revision"])
                cursor = self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET state = 'leased',
                        attempts = attempts + 1,
                        claimed_by = ?,
                        lease_until = ?,
                        next_attempt_at = NULL,
                        updated_at = ?
                    WHERE node_id = ? AND sample_hour = ?
                      AND projection_version = ? AND revision = ?
                    """,
                    (
                        worker_id,
                        lease_text,
                        current_text,
                        str(row["node_id"]),
                        str(row["sample_hour"]),
                        int(row["projection_version"]),
                        revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ProjectionStoreError("projection claim lost atomic ownership")
                attempts = int(row["attempts"]) + 1
                self._commit()
                return ProjectionTask(
                    node_id=str(row["node_id"]),
                    sample_hour=str(row["sample_hour"]),
                    projection_version=int(row["projection_version"]),
                    revision=revision,
                    attempts=attempts,
                    claimed_by=worker_id,
                    lease_until=lease_until,
                )
            except Exception:
                self._rollback()
                raise

    def load_records(self, task: ProjectionTask) -> tuple[dict[str, Any], ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT record_json
                FROM c06_history_records
                WHERE node_id = ? AND sample_hour = ?
                ORDER BY sampled_at, boot_id, seq
                """,
                (task.node_id, task.sample_hour),
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            value = json.loads(str(row["record_json"]))
            if not isinstance(value, dict):
                raise ProjectionStoreError("stored historical record is not an object")
            records.append(value)
        return tuple(records)

    def _mark_failure(
        self,
        task: ProjectionTask,
        *,
        state: Literal["retry", "blocked"],
        error_code: str,
        error: str,
        now: datetime,
        next_attempt_at: datetime | None,
    ) -> bool:
        if not error_code or len(error_code) > 128:
            raise ValueError("error_code must contain 1 to 128 characters")
        error_text = error[:2048]
        current_text = _timestamp(now)
        next_text = _timestamp(next_attempt_at) if next_attempt_at is not None else None
        with self._lock:
            self._transaction()
            try:
                cursor = self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET state = ?,
                        claimed_by = NULL,
                        lease_until = NULL,
                        next_attempt_at = ?,
                        last_error_code = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE node_id = ? AND sample_hour = ?
                      AND projection_version = ? AND revision = ?
                      AND state = 'leased' AND claimed_by = ?
                    """,
                    (
                        state,
                        next_text,
                        error_code,
                        error_text,
                        current_text,
                        task.node_id,
                        task.sample_hour,
                        task.projection_version,
                        task.revision,
                        task.claimed_by,
                    ),
                )
                self._commit()
                return cursor.rowcount == 1
            except Exception:
                self._rollback()
                raise

    def mark_retry(
        self,
        task: ProjectionTask,
        *,
        error_code: str,
        error: str,
        next_attempt_at: datetime,
        now: datetime | None = None,
    ) -> bool:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        retry_at = next_attempt_at.astimezone(UTC)
        if retry_at < current:
            raise ValueError("next_attempt_at must not be earlier than now")
        return self._mark_failure(
            task,
            state="retry",
            error_code=error_code,
            error=error,
            now=current,
            next_attempt_at=retry_at,
        )

    def mark_blocked(
        self,
        task: ProjectionTask,
        *,
        error_code: str,
        error: str,
        now: datetime | None = None,
    ) -> bool:
        return self._mark_failure(
            task,
            state="blocked",
            error_code=error_code,
            error=error,
            now=(now or datetime.now(UTC)).astimezone(UTC),
            next_attempt_at=None,
        )

    def mark_completed(
        self,
        task: ProjectionTask,
        *,
        projection_hash: str,
        payload_json: str,
        adapter_kind: str,
        adapter_version: str,
        now: datetime | None = None,
    ) -> bool:
        if len(projection_hash) != 64:
            raise ValueError("projection_hash must be a SHA-256 hex digest")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        current_text = _timestamp(current)
        with self._lock:
            self._transaction()
            try:
                cursor = self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET state = 'completed',
                        claimed_by = NULL,
                        lease_until = NULL,
                        next_attempt_at = NULL,
                        last_error_code = NULL,
                        last_error = NULL,
                        projection_hash = ?,
                        payload_json = ?,
                        adapter_kind = ?,
                        adapter_version = ?,
                        last_dispatched_at = ?,
                        verified_at = ?,
                        updated_at = ?,
                        completed_at = ?
                    WHERE node_id = ? AND sample_hour = ?
                      AND projection_version = ? AND revision = ?
                      AND state = 'leased' AND claimed_by = ?
                    """,
                    (
                        projection_hash,
                        payload_json,
                        adapter_kind,
                        adapter_version,
                        current_text,
                        current_text,
                        current_text,
                        current_text,
                        task.node_id,
                        task.sample_hour,
                        task.projection_version,
                        task.revision,
                        task.claimed_by,
                    ),
                )
                if cursor.rowcount != 1:
                    self._commit()
                    return False
                outbox = self._connection.execute(
                    """
                    UPDATE c06_projection_outbox
                    SET state = 'completed',
                        attempts = ?,
                        last_error = NULL,
                        updated_at = ?,
                        completed_at = ?
                    WHERE node_id = ? AND sample_hour = ?
                      AND projection_version = ? AND state = 'pending'
                    """,
                    (
                        task.attempts,
                        current_text,
                        current_text,
                        task.node_id,
                        task.sample_hour,
                        task.projection_version,
                    ),
                )
                if outbox.rowcount != 1:
                    raise ProjectionStoreError(
                        "projection completion lost the C06-A outbox row"
                    )
                self._commit()
                return True
            except Exception:
                self._rollback()
                raise

    def get_job(
        self, node_id: str, sample_hour: str, projection_version: int = 1
    ) -> ProjectionJobSnapshot | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM c06_projection_jobs
                WHERE node_id = ? AND sample_hour = ? AND projection_version = ?
                """,
                (node_id, sample_hour, projection_version),
            ).fetchone()
        if row is None:
            return None
        return ProjectionJobSnapshot(
            node_id=str(row["node_id"]),
            sample_hour=str(row["sample_hour"]),
            projection_version=int(row["projection_version"]),
            revision=int(row["revision"]),
            state=str(row["state"]),  # type: ignore[arg-type]
            attempts=int(row["attempts"]),
            claimed_by=str(row["claimed_by"]) if row["claimed_by"] is not None else None,
            lease_until=_optional_timestamp(row["lease_until"]),
            next_attempt_at=_optional_timestamp(row["next_attempt_at"]),
            last_error_code=(
                str(row["last_error_code"])
                if row["last_error_code"] is not None
                else None
            ),
            last_error=str(row["last_error"]) if row["last_error"] is not None else None,
            projection_hash=(
                str(row["projection_hash"])
                if row["projection_hash"] is not None
                else None
            ),
            payload_json=(
                str(row["payload_json"]) if row["payload_json"] is not None else None
            ),
            adapter_kind=(
                str(row["adapter_kind"]) if row["adapter_kind"] is not None else None
            ),
            adapter_version=(
                str(row["adapter_version"])
                if row["adapter_version"] is not None
                else None
            ),
            verified_at=_optional_timestamp(row["verified_at"]),
            completed_at=_optional_timestamp(row["completed_at"]),
        )

    def count_jobs(self) -> int:
        with self._lock:
            return int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM c06_projection_jobs"
                ).fetchone()[0]
            )

    def schema_version(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT MAX(version) FROM c06b1_schema_migrations"
            ).fetchone()
            return int(row[0]) if row is not None and row[0] is not None else 0
