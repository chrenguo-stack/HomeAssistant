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


def completion_payload(value: str = "{}") -> tuple[str, str]:
    return hashlib.sha256(value.encode()).hexdigest(), value


def complete_task(
    store: ProjectionStore,
    *,
    worker_id: str = "worker-a",
    now: datetime = NOW,
) -> None:
    task = store.claim_next(worker_id=worker_id, now=now)
    assert task is not None
    digest, payload = completion_payload()
    assert store.mark_completed(
        task,
        projection_hash=digest,
        payload_json=payload,
        adapter_kind="fake-host-only",
        adapter_version="2",
        now=now,
    )


def install_legacy_v1_completed_job(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE c06_projection_outbox
            SET state='completed', completed_at=updated_at
            WHERE node_id='node-0001' AND sample_hour=?
            """,
            (HOUR,),
        )
        connection.executescript(
            """
            CREATE TABLE c06b1_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            INSERT INTO c06b1_schema_migrations(version, applied_at)
            VALUES (1, '2026-08-03T04:10:00.000Z');

            CREATE TABLE c06_projection_jobs (
                node_id TEXT NOT NULL,
                sample_hour TEXT NOT NULL,
                projection_version INTEGER NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                state TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
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
            """
        )
        row = connection.execute(
            """
            SELECT created_at, updated_at, completed_at
            FROM c06_projection_outbox
            WHERE node_id='node-0001' AND sample_hour=?
            """,
            (HOUR,),
        ).fetchone()
        assert row is not None
        connection.execute(
            """
            INSERT INTO c06_projection_jobs (
                node_id, sample_hour, projection_version, revision, state,
                attempts, created_at, updated_at, completed_at
            ) VALUES ('node-0001', ?, 1, 1, 'completed', 4, ?, ?, ?)
            """,
            (HOUR, row[0], row[1], row[2]),
        )


def test_projection_store_requires_existing_c06a_database(tmp_path: Path) -> None:
    with pytest.raises(ProjectionStoreError, match="must already exist"):
        ProjectionStore(db_path(tmp_path))


def test_existing_pending_outbox_is_migrated_and_claimed_once(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-000001")

    with ProjectionStore(path) as first, ProjectionStore(path) as second:
        assert first.schema_version() == 2
        task = first.claim_next(worker_id="worker-a", now=NOW)
        assert task is not None
        assert task.revision == 1
        assert task.attempts == 1
        assert second.claim_next(worker_id="worker-b", now=NOW) is None


def test_legacy_completed_without_c06b1_evidence_reopens_fail_closed(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-legacy")
    install_legacy_v1_completed_job(path)

    with ProjectionStore(path) as store:
        assert store.schema_version() == 2
        job = store.get_job("node-0001", HOUR)
        assert job is not None
        assert job.state == "pending"
        assert job.attempts == 0
        assert job.projection_hash is None
        assert job.requeue_count == 0
        assert store.claim_next(worker_id="worker-a", now=NOW) is not None
    with sqlite3.connect(path) as connection:
        state = connection.execute(
            """
            SELECT state FROM c06_projection_outbox
            WHERE node_id='node-0001' AND sample_hour=?
            """,
            (HOUR,),
        ).fetchone()
    assert state == ("pending",)


def test_valid_completed_job_remains_completed_after_store_restart(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-valid-complete")
    with ProjectionStore(path) as store:
        complete_task(store)
    with ProjectionStore(path) as reopened:
        job = reopened.get_job("node-0001", HOUR)
        assert job is not None
        assert job.state == "completed"
        assert job.projection_hash is not None
        assert reopened.claim_next(worker_id="worker-b", now=NOW) is None


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


def test_expired_lease_cannot_settle_without_reclaim(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-expired-settle")
    with ProjectionStore(path) as store:
        task = store.claim_next(worker_id="worker-a", now=NOW, lease_seconds=5)
        assert task is not None
        digest, payload = completion_payload()
        assert not store.mark_completed(
            task,
            projection_hash=digest,
            payload_json=payload,
            adapter_kind="fake-host-only",
            adapter_version="2",
            now=NOW + timedelta(seconds=5),
        )
        assert not store.mark_blocked(
            task,
            error_code="too_late",
            error="lease expired",
            now=NOW + timedelta(seconds=5),
        )


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
            assert snapshot.attempts == 0
            digest, payload = completion_payload()
            assert not projections.mark_completed(
                old,
                projection_hash=digest,
                payload_json=payload,
                adapter_kind="fake-host-only",
                adapter_version="2",
                now=NOW,
            )
            new = projections.claim_next(worker_id="worker-b", now=NOW)
            assert new is not None
            assert new.revision == old.revision + 1
            assert new.attempts == 1


def test_multiple_late_records_in_one_page_create_one_new_revision(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record(seq=1)], batch_id="batch-initial")
        with ProjectionStore(path) as projections:
            complete_task(projections)
            before = projections.get_job("node-0001", HOUR)
            assert before is not None
            commit_records(
                history,
                [
                    history_record(
                        seq=2,
                        sampled_at="2026-08-03T04:05:00Z",
                        temperature=26.0,
                    ),
                    history_record(
                        seq=3,
                        sampled_at="2026-08-03T04:06:00Z",
                        temperature=27.0,
                    ),
                ],
                batch_id="batch-two-late",
            )
            after = projections.get_job("node-0001", HOUR)
            assert after is not None
            assert after.revision == before.revision + 1
            assert after.state == "pending"
            assert after.attempts == 0


def test_new_revision_resets_previous_retry_attempts(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record(seq=1)], batch_id="batch-attempts")
        with ProjectionStore(path) as store:
            first = store.claim_next(worker_id="worker-a", now=NOW)
            assert first is not None
            first_due = NOW + timedelta(seconds=1)
            assert store.mark_retry(
                first,
                error_code="temporary",
                error="first",
                next_attempt_at=first_due,
                now=NOW,
            )
            second = store.claim_next(worker_id="worker-b", now=first_due)
            assert second is not None
            assert second.attempts == 2
            second_due = NOW + timedelta(seconds=2)
            assert store.mark_retry(
                second,
                error_code="temporary",
                error="second",
                next_attempt_at=second_due,
                now=first_due,
            )
            commit_records(
                history,
                [
                    history_record(
                        seq=2,
                        sampled_at="2026-08-03T04:05:00Z",
                        temperature=28.0,
                    )
                ],
                batch_id="batch-new-generation",
            )
            reopened = store.get_job("node-0001", HOUR)
            assert reopened is not None
            assert reopened.revision == first.revision + 1
            assert reopened.attempts == 0
            claimed = store.claim_next(worker_id="worker-c", now=NOW)
            assert claimed is not None
            assert claimed.attempts == 1


def test_duplicate_page_does_not_reopen_completed_projection(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        record = history_record()
        commit_records(history, [record], batch_id="batch-duplicate")
        with ProjectionStore(path) as projections:
            complete_task(projections)
            before = projections.get_job("node-0001", HOUR)
            assert before is not None
            commit_records(history, [record], batch_id="batch-duplicate")
            after = projections.get_job("node-0001", HOUR)
            assert after is not None
            assert after.state == "completed"
            assert after.revision == before.revision
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


def test_operator_requeue_is_revision_safe_and_audited(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-requeue")
    with ProjectionStore(path) as store:
        task = store.claim_next(worker_id="worker-a", now=NOW)
        assert task is not None
        assert store.mark_blocked(
            task,
            error_code="entity_missing",
            error="not yet created",
            now=NOW,
        )
        assert not store.requeue_blocked(
            node_id="node-0001",
            sample_hour=HOUR,
            expected_revision=task.revision + 1,
            operator_reason="wrong expected revision",
            now=NOW + timedelta(seconds=1),
        )
        assert store.requeue_blocked(
            node_id="node-0001",
            sample_hour=HOUR,
            expected_revision=task.revision,
            operator_reason="entity registry repaired",
            now=NOW + timedelta(seconds=1),
        )
        snapshot = store.get_job("node-0001", HOUR)
        assert snapshot is not None
        assert snapshot.state == "pending"
        assert snapshot.attempts == 0
        assert snapshot.requeue_count == 1
        assert snapshot.last_requeued_at == NOW + timedelta(seconds=1)
        assert snapshot.last_requeue_reason == "entity registry repaired"


def test_completion_rejects_hash_mismatch_and_oversized_payload(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-payload-bound")
    with ProjectionStore(path) as store:
        task = store.claim_next(worker_id="worker-a", now=NOW)
        assert task is not None
        with pytest.raises(ValueError, match="does not match"):
            store.mark_completed(
                task,
                projection_hash="0" * 64,
                payload_json="{}",
                adapter_kind="fake-host-only",
                adapter_version="2",
                now=NOW,
            )
        huge = '"' + ("x" * 1_048_576) + '"'
        digest = hashlib.sha256(huge.encode()).hexdigest()
        with pytest.raises(ValueError, match="1048576-byte"):
            store.mark_completed(
                task,
                projection_hash=digest,
                payload_json=huge,
                adapter_kind="fake-host-only",
                adapter_version="2",
                now=NOW,
            )


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
