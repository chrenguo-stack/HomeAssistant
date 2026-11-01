from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from .history_projection_store_models import (
    MAX_PROJECTION_PAYLOAD_BYTES,
    SHA256_RE,
    ProjectionStoreError,
    ProjectionTask,
    utc,
)
from .history_store import _timestamp


class ProjectionStoreSettlementMixin:
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
        current_text = _timestamp(utc(now))
        next_text = (
            _timestamp(utc(next_attempt_at))
            if next_attempt_at is not None
            else None
        )
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
                      AND lease_until > ?
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
                        current_text,
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
        current = utc(now or datetime.now(UTC))
        retry_at = utc(next_attempt_at)
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
            now=utc(now or datetime.now(UTC)),
            next_attempt_at=None,
        )

    def requeue_blocked(
        self,
        *,
        node_id: str,
        sample_hour: str,
        expected_revision: int,
        operator_reason: str,
        projection_version: int = 1,
        now: datetime | None = None,
    ) -> bool:
        reason = operator_reason.strip()
        if not reason or len(reason) > 512:
            raise ValueError("operator_reason must contain 1 to 512 characters")
        if expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        if projection_version < 1:
            raise ValueError("projection_version must be positive")
        current_text = _timestamp(utc(now or datetime.now(UTC)))
        with self._lock:
            self._transaction()
            try:
                cursor = self._connection.execute(
                    """
                    UPDATE c06_projection_jobs
                    SET state = 'pending',
                        attempts = 0,
                        claimed_by = NULL,
                        lease_until = NULL,
                        next_attempt_at = ?,
                        last_error_code = NULL,
                        last_error = NULL,
                        updated_at = ?,
                        requeue_count = requeue_count + 1,
                        last_requeued_at = ?,
                        last_requeue_reason = ?
                    WHERE node_id = ?
                      AND sample_hour = ?
                      AND projection_version = ?
                      AND revision = ?
                      AND state = 'blocked'
                      AND EXISTS (
                        SELECT 1 FROM c06_projection_outbox AS outbox
                        WHERE outbox.node_id = c06_projection_jobs.node_id
                          AND outbox.sample_hour = c06_projection_jobs.sample_hour
                          AND outbox.projection_version =
                              c06_projection_jobs.projection_version
                          AND outbox.state = 'pending'
                      )
                    """,
                    (
                        current_text,
                        current_text,
                        current_text,
                        reason,
                        node_id,
                        sample_hour,
                        projection_version,
                        expected_revision,
                    ),
                )
                self._commit()
                return cursor.rowcount == 1
            except Exception:
                self._rollback()
                raise

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
        if SHA256_RE.fullmatch(projection_hash) is None:
            raise ValueError("projection_hash must be a lowercase SHA-256 hex digest")
        payload_bytes = payload_json.encode("utf-8")
        if hashlib.sha256(payload_bytes).hexdigest() != projection_hash:
            raise ValueError("projection_hash does not match payload_json")
        if len(payload_bytes) > MAX_PROJECTION_PAYLOAD_BYTES:
            raise ValueError("projection payload exceeds the 1048576-byte limit")
        if not adapter_kind or len(adapter_kind) > 128:
            raise ValueError("adapter_kind must contain 1 to 128 characters")
        if not adapter_version or len(adapter_version) > 128:
            raise ValueError("adapter_version must contain 1 to 128 characters")
        current = utc(now or datetime.now(UTC))
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
                      AND lease_until > ?
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
                        current_text,
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
