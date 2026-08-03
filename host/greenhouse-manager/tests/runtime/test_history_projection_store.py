from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from history_samples import history_record

from greenhouse_manager.runtime.history_projection_store import (
    ProjectionStore,
    ProjectionStoreError,
)
from greenhouse_manager.runtime.history_store import HistoryStore

HOUR = "2026-08-03T04:00:00.000Z"
NOW = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)


def db_path(root: Path) -> Path:
    return root / "manager" / "manager-state.sqlite3"


def commit_records(
    store: HistoryStore,
    records: list[dict],
    *,
    batch_id: str,
    received_at: datetime = NOW,
) -> None:
    store.commit_page(
        node_id="node-0001",
        batch_id=batch_id,
        page_index=0,
        page_count=1,
        records=records,
        payload_sha256=hashlib.sha256(batch_id.encode()).hexdigest(),
        received_at=received_at,
    )


def test_projection_store_requires_existing_c06a_database(tmp_path: Path) -> None:
    with pytest.raises(ProjectionStoreError, match="must already exist"):
        ProjectionStore(db_path(tmp_path))


def test_existing_pending_outbox_is_migrated_and_claimed_once(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-000001")

    with ProjectionStore(path) as first, ProjectionStore(path) as second:
        assert first.schema_version() == 1
        task = first.claim_next(worker_id="worker-a", now=NOW)
        assert task is not None
        assert task.revision == 1
        assert task.attempts == 1
        assert second.claim_next(worker_id="worker-b", now=NOW) is None


def test_expired_lease_is_reclaimed(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-lease")
    with ProjectionStore(path) as store:
        first = store.claim_next(worker_id="worker-a", now=NOW, lease_seconds=5)
        assert first is not None
        reclaimed = store.claim_next(
            worker_id="worker-b", now=NOW + timedelta(seconds=6), lease_seconds=5
        )
        assert reclaimed is not None
        assert reclaimed.revision == first.revision
        assert reclaimed.attempts == 2
        assert reclaimed.claimed_by == "worker-b"


def test_late_record_reopens_with_new_revision_and_stales_old_claim(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record(seq=1)], batch_id="batch-first")
        with ProjectionStore(path) as projections:
            old = projections.claim_next(worker_id="worker-a", now=NOW)
            assert old is not None
            commit_records(
                history,
                [
                    history_record(
                        seq=2,
                        sampled_at="2026-08-03T04:05:00Z",
                        temperature=27.0,
                    )
                ],
                batch_id="batch-late",
                received_at=NOW,
            )
            snapshot = projections.get_job("node-0001", HOUR)
            assert snapshot is not None
            assert snapshot.revision == old.revision + 1
            assert snapshot.state == "pending"
            assert not projections.mark_completed(
                old,
                projection_hash="a" * 64,
                payload_json="{}",
                adapter_kind="fake-host-only",
                adapter_version="1",
                now=NOW,
            )
            new = projections.claim_next(worker_id="worker-b", now=NOW)
            assert new is not None
            assert new.revision == old.revision + 1


def test_duplicate_page_does_not_reopen_completed_projection(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        record = history_record()
        commit_records(history, [record], batch_id="batch-duplicate")
        with ProjectionStore(path) as projections:
            task = projections.claim_next(worker_id="worker-a", now=NOW)
            assert task is not None
            assert projections.mark_completed(
                task,
                projection_hash="b" * 64,
                payload_json="{}",
                adapter_kind="fake-host-only",
                adapter_version="1",
                now=NOW,
            )
            commit_records(history, [record], batch_id="batch-duplicate")
            snapshot = projections.get_job("node-0001", HOUR)
            assert snapshot is not None
            assert snapshot.state == "completed"
            assert snapshot.revision == task.revision
            assert projections.claim_next(worker_id="worker-b", now=NOW) is None


def test_retry_and_blocked_states_remain_durable(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-retry")
    with ProjectionStore(path) as store:
        task = store.claim_next(worker_id="worker-a", now=NOW)
        assert task is not None
        retry_at = NOW + timedelta(seconds=10)
        assert store.mark_retry(
            task,
            error_code="temporary",
            error="temporary failure",
            next_attempt_at=retry_at,
            now=NOW,
        )
        assert store.claim_next(worker_id="worker-b", now=NOW) is None
        retry_task = store.claim_next(worker_id="worker-b", now=retry_at)
        assert retry_task is not None
        assert store.mark_blocked(
            retry_task,
            error_code="contract",
            error="requires repair",
            now=retry_at,
        )
        blocked = store.get_job("node-0001", HOUR)
        assert blocked is not None
        assert blocked.state == "blocked"
        assert blocked.last_error_code == "contract"
        assert store.claim_next(worker_id="worker-c", now=retry_at) is None


def test_raw_retention_deletion_cascades_projection_job(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    old = datetime(2026, 8, 1, 4, 5, tzinfo=UTC)
    with HistoryStore(path, retention_days=1) as history:
        commit_records(
            history,
            [history_record(sampled_at="2026-08-01T04:00:00Z")],
            batch_id="batch-old",
            received_at=old,
        )
        with ProjectionStore(path) as projections:
            assert projections.count_jobs() == 1
            history.prune(now=datetime(2026, 8, 3, 5, 0, tzinfo=UTC))
            assert projections.count_jobs() == 0


def test_projection_tables_do_not_create_a_second_database(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-role")
    with ProjectionStore(path):
        pass
    sqlite_files = list(tmp_path.rglob("*.sqlite3"))
    assert sqlite_files == [path]
    with sqlite3.connect(path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "c06_projection_jobs" in names
