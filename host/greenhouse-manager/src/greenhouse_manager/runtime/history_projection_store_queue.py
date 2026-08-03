from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .history_projection_store_models import ProjectionStoreError, ProjectionTask, utc
from .history_store import _timestamp


class ProjectionStoreQueueMixin:
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
        current = utc(now or datetime.now(UTC))
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
                      AND state = ?
                    """,
                    (
                        worker_id,
                        lease_text,
                        current_text,
                        str(row["node_id"]),
                        str(row["sample_hour"]),
                        int(row["projection_version"]),
                        revision,
                        str(row["state"]),
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

    def claim_is_current(
        self,
        task: ProjectionTask,
        *,
        now: datetime | None = None,
    ) -> bool:
        current_text = _timestamp(utc(now or datetime.now(UTC)))
        with self._lock:
            row = self._connection.execute(
                """
                SELECT 1
                FROM c06_projection_jobs AS jobs
                JOIN c06_projection_outbox AS outbox
                  ON outbox.node_id = jobs.node_id
                 AND outbox.sample_hour = jobs.sample_hour
                 AND outbox.projection_version = jobs.projection_version
                WHERE jobs.node_id = ?
                  AND jobs.sample_hour = ?
                  AND jobs.projection_version = ?
                  AND jobs.revision = ?
                  AND jobs.state = 'leased'
                  AND jobs.claimed_by = ?
                  AND jobs.lease_until > ?
                  AND outbox.state = 'pending'
                """,
                (
                    task.node_id,
                    task.sample_hour,
                    task.projection_version,
                    task.revision,
                    task.claimed_by,
                    current_text,
                ),
            ).fetchone()
            return row is not None

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
            try:
                value = json.loads(str(row["record_json"]))
            except (TypeError, ValueError) as exc:
                raise ProjectionStoreError(
                    f"stored historical record is invalid JSON: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ProjectionStoreError("stored historical record is not an object")
            records.append(value)
        return tuple(records)
