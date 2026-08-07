from __future__ import annotations

from datetime import UTC, datetime

from .history_projection_store_models import ProjectionStoreError
from .history_store import _timestamp


class ProjectionStoreSchemaMixin:
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

    def _create_base_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS c06b1_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
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
                requeue_count INTEGER NOT NULL DEFAULT 0
                    CHECK (requeue_count >= 0),
                last_requeued_at TEXT,
                last_requeue_reason TEXT,
                PRIMARY KEY (node_id, sample_hour, projection_version),
                FOREIGN KEY (node_id, sample_hour, projection_version)
                    REFERENCES c06_projection_outbox(
                        node_id, sample_hour, projection_version
                    ) ON DELETE CASCADE
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS c06_projection_jobs_due
            ON c06_projection_jobs(
                state, next_attempt_at, lease_until, sample_hour, node_id
            )
            """
        )

    def _ensure_v2_columns(self) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(
                "PRAGMA table_info(c06_projection_jobs)"
            ).fetchall()
        }
        additions = (
            (
                "requeue_count",
                "ALTER TABLE c06_projection_jobs "
                "ADD COLUMN requeue_count INTEGER NOT NULL DEFAULT 0",
            ),
            (
                "last_requeued_at",
                "ALTER TABLE c06_projection_jobs ADD COLUMN last_requeued_at TEXT",
            ),
            (
                "last_requeue_reason",
                "ALTER TABLE c06_projection_jobs ADD COLUMN last_requeue_reason TEXT",
            ),
        )
        for name, statement in additions:
            if name not in columns:
                self._connection.execute(statement)

    def _drop_triggers(self) -> None:
        self._connection.execute(
            "DROP TRIGGER IF EXISTS c06b1_projection_outbox_insert"
        )
        self._connection.execute(
            "DROP TRIGGER IF EXISTS c06b1_projection_outbox_reopen"
        )

    def _create_triggers(self) -> None:
        # Pending jobs have no active worker and can absorb more source records
        # without revision churn. Any non-pending state is a frozen execution
        # generation, so new source data increments revision and resets attempts.
        self._connection.execute(
            """
            CREATE TRIGGER c06b1_projection_outbox_insert
            AFTER INSERT ON c06_projection_outbox
            WHEN NEW.state = 'pending'
            BEGIN
                INSERT INTO c06_projection_jobs (
                    node_id, sample_hour, projection_version, revision, state,
                    attempts, claimed_by, lease_until, next_attempt_at,
                    last_error_code, last_error, projection_hash, payload_json,
                    adapter_kind, adapter_version, last_dispatched_at, verified_at,
                    created_at, updated_at, completed_at, requeue_count,
                    last_requeued_at, last_requeue_reason
                ) VALUES (
                    NEW.node_id, NEW.sample_hour, NEW.projection_version,
                    1, 'pending', 0, NULL, NULL, NEW.updated_at,
                    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    NEW.created_at, NEW.updated_at, NULL, 0, NULL, NULL
                )
                ON CONFLICT(node_id, sample_hour, projection_version) DO UPDATE SET
                    revision = CASE
                        WHEN c06_projection_jobs.state = 'pending'
                            THEN c06_projection_jobs.revision
                        ELSE c06_projection_jobs.revision + 1
                    END,
                    state = 'pending',
                    attempts = CASE
                        WHEN c06_projection_jobs.state = 'pending'
                            THEN c06_projection_jobs.attempts
                        ELSE 0
                    END,
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
            END
            """
        )
        self._connection.execute(
            """
            CREATE TRIGGER c06b1_projection_outbox_reopen
            AFTER UPDATE OF state, updated_at ON c06_projection_outbox
            WHEN NEW.state = 'pending'
            BEGIN
                INSERT INTO c06_projection_jobs (
                    node_id, sample_hour, projection_version, revision, state,
                    attempts, claimed_by, lease_until, next_attempt_at,
                    last_error_code, last_error, projection_hash, payload_json,
                    adapter_kind, adapter_version, last_dispatched_at, verified_at,
                    created_at, updated_at, completed_at, requeue_count,
                    last_requeued_at, last_requeue_reason
                ) VALUES (
                    NEW.node_id, NEW.sample_hour, NEW.projection_version,
                    1, 'pending', 0, NULL, NULL, NEW.updated_at,
                    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    NEW.created_at, NEW.updated_at, NULL, 0, NULL, NULL
                )
                ON CONFLICT(node_id, sample_hour, projection_version) DO UPDATE SET
                    revision = CASE
                        WHEN c06_projection_jobs.state = 'pending'
                            THEN c06_projection_jobs.revision
                        ELSE c06_projection_jobs.revision + 1
                    END,
                    state = 'pending',
                    attempts = CASE
                        WHEN c06_projection_jobs.state = 'pending'
                            THEN c06_projection_jobs.attempts
                        ELSE 0
                    END,
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
            END
            """
        )

    def _initialize(self) -> None:
        with self._lock:
            self._require_c06a_tables()
            try:
                self._transaction()
                self._create_base_schema()
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

                self._ensure_v2_columns()
                self._drop_triggers()

                # Missing companion jobs are always pending. A legacy C06-A
                # completed outbox has no C06-B1 hash/readback proof and must be
                # re-projected rather than trusted.
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO c06_projection_jobs (
                        node_id, sample_hour, projection_version, revision, state,
                        attempts, claimed_by, lease_until, next_attempt_at,
                        last_error_code, last_error, projection_hash, payload_json,
                        adapter_kind, adapter_version, last_dispatched_at, verified_at,
                        created_at, updated_at, completed_at, requeue_count,
                        last_requeued_at, last_requeue_reason
                    )
                    SELECT
                        node_id, sample_hour, projection_version, 1, 'pending',
                        0, NULL, NULL, updated_at,
                        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                        created_at, updated_at, NULL, 0, NULL, NULL
                    FROM c06_projection_outbox
                    """
                )

                # Fail closed on any completed companion row lacking the complete
                # C06-B1 evidence tuple.
                self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET state = 'pending',
                        attempts = 0,
                        claimed_by = NULL,
                        lease_until = NULL,
                        next_attempt_at = updated_at,
                        last_error_code = NULL,
                        last_error = NULL,
                        projection_hash = NULL,
                        payload_json = NULL,
                        adapter_kind = NULL,
                        adapter_version = NULL,
                        last_dispatched_at = NULL,
                        verified_at = NULL,
                        completed_at = NULL
                    WHERE state = 'completed'
                      AND (
                        projection_hash IS NULL
                        OR payload_json IS NULL
                        OR adapter_kind IS NULL
                        OR adapter_version IS NULL
                        OR verified_at IS NULL
                        OR completed_at IS NULL
                      )
                    """
                )
                # If the C06-A outbox is pending, it is authoritative: a
                # previously completed companion generation must reopen.
                self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET revision = revision + 1,
                        state = 'pending',
                        attempts = 0,
                        claimed_by = NULL,
                        lease_until = NULL,
                        next_attempt_at = updated_at,
                        last_error_code = NULL,
                        last_error = NULL,
                        projection_hash = NULL,
                        payload_json = NULL,
                        adapter_kind = NULL,
                        adapter_version = NULL,
                        last_dispatched_at = NULL,
                        verified_at = NULL,
                        completed_at = NULL
                    WHERE state = 'completed'
                      AND EXISTS (
                        SELECT 1 FROM c06_projection_outbox AS outbox
                        WHERE outbox.node_id = c06_projection_jobs.node_id
                          AND outbox.sample_hour = c06_projection_jobs.sample_hour
                          AND outbox.projection_version =
                              c06_projection_jobs.projection_version
                          AND outbox.state = 'pending'
                      )
                    """
                )
                # Conversely, any non-completed companion means a legacy
                # completed outbox lacks complete C06-B1 proof and must reopen.
                self._connection.execute(
                    """
                    UPDATE c06_projection_outbox
                    SET state = 'pending',
                        attempts = 0,
                        last_error = NULL,
                        completed_at = NULL
                    WHERE state = 'completed'
                      AND EXISTS (
                        SELECT 1 FROM c06_projection_jobs AS jobs
                        WHERE jobs.node_id = c06_projection_outbox.node_id
                          AND jobs.sample_hour = c06_projection_outbox.sample_hour
                          AND jobs.projection_version =
                              c06_projection_outbox.projection_version
                          AND jobs.state != 'completed'
                      )
                    """
                )

                now_text = _timestamp(datetime.now(UTC))
                if 1 not in applied:
                    self._connection.execute(
                        "INSERT INTO c06b1_schema_migrations(version, applied_at) "
                        "VALUES (1, ?)",
                        (now_text,),
                    )
                    applied.add(1)
                if 2 not in applied:
                    self._connection.execute(
                        "INSERT INTO c06b1_schema_migrations(version, applied_at) "
                        "VALUES (2, ?)",
                        (now_text,),
                    )
                    applied.add(2)
                if applied != {1, 2}:
                    raise ProjectionStoreError(
                        f"unsupported C06-B1 schema migration set: {sorted(applied)}"
                    )
                self._create_triggers()
                self._commit()
            except Exception:
                self._rollback()
                raise
