from __future__ import annotations

import os
import sqlite3
import stat
import threading
from pathlib import Path

from .history_projection_store_models import (
    ProjectionJobSnapshot,
    ProjectionJobState,
    ProjectionStoreError,
    ProjectionTask,
    optional_timestamp,
)
from .history_projection_store_queue import ProjectionStoreQueueMixin
from .history_projection_store_schema import ProjectionStoreSchemaMixin
from .history_projection_store_settlement import ProjectionStoreSettlementMixin
from .history_store import _private_path


class ProjectionStore(
    ProjectionStoreSchemaMixin,
    ProjectionStoreQueueMixin,
    ProjectionStoreSettlementMixin,
):
    """Durable C06-B1 job state layered on the C06-A projection outbox."""

    SCHEMA_VERSION = 2

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

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> ProjectionStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

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
            claimed_by=(
                str(row["claimed_by"]) if row["claimed_by"] is not None else None
            ),
            lease_until=optional_timestamp(row["lease_until"]),
            next_attempt_at=optional_timestamp(row["next_attempt_at"]),
            last_error_code=(
                str(row["last_error_code"])
                if row["last_error_code"] is not None
                else None
            ),
            last_error=(
                str(row["last_error"]) if row["last_error"] is not None else None
            ),
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
            verified_at=optional_timestamp(row["verified_at"]),
            completed_at=optional_timestamp(row["completed_at"]),
            requeue_count=int(row["requeue_count"]),
            last_requeued_at=optional_timestamp(row["last_requeued_at"]),
            last_requeue_reason=(
                str(row["last_requeue_reason"])
                if row["last_requeue_reason"] is not None
                else None
            ),
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


__all__ = [
    "ProjectionJobSnapshot",
    "ProjectionJobState",
    "ProjectionStore",
    "ProjectionStoreError",
    "ProjectionTask",
]
