from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from history_samples import history_record

from greenhouse_manager.runtime.history_store import HistoryConflict, HistoryStore


def _payload_hash(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit(
    store: HistoryStore,
    *,
    batch_id: str = "batch-000001",
    page_index: int = 0,
    page_count: int = 2,
    record: dict[str, object] | None = None,
) -> object:
    records = [record or history_record()]
    document = {
        "schema": "gh.history-replay.batch/1",
        "node_id": "node-0001",
        "batch_id": batch_id,
        "page_index": page_index,
        "page_count": page_count,
        "records": records,
    }
    return store.commit_page(
        node_id="node-0001",
        batch_id=batch_id,
        page_index=page_index,
        page_count=page_count,
        records=records,
        payload_sha256=_payload_hash(document),
        received_at=datetime(2026, 8, 3, 4, 5, tzinfo=UTC),
    )


def test_commits_raw_record_and_projection_outbox_durably(tmp_path: Path) -> None:
    path = tmp_path / "manager-state.sqlite3"
    with HistoryStore(path) as store:
        result = _commit(store)
        assert result.status == "accepted"
        assert result.inserted_count == 1
        assert store.count_records() == 1
        assert store.pending_projection_hours() == (
            ("node-0001", "2026-08-03T04:00:00.000Z"),
        )

    with HistoryStore(path) as reopened:
        duplicate = _commit(reopened)
        assert duplicate.status == "duplicate"
        assert reopened.count_records() == 1
        assert reopened.get_record("node-0001", "boot-00000001", 1) == history_record()


def test_rejects_record_identity_collision_without_partial_write(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        _commit(store)
        conflicting = history_record(temperature=31.0)
        with pytest.raises(HistoryConflict, match="different historical content"):
            _commit(store, batch_id="batch-000002", record=conflicting)

        assert store.count_records() == 1
        assert store.get_record("node-0001", "boot-00000001", 1) == history_record()


def test_rejects_inconsistent_page_count_for_same_batch(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        _commit(store, batch_id="batch-000003", page_index=0, page_count=2)
        second_record = history_record(
            seq=2,
            sampled_at="2026-08-03T04:01:00Z",
        )

        with pytest.raises(HistoryConflict, match="different page_count"):
            _commit(
                store,
                batch_id="batch-000003",
                page_index=1,
                page_count=3,
                record=second_record,
            )

        assert store.count_records() == 1


def test_duplicate_record_in_new_page_does_not_reopen_completed_projection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manager-state.sqlite3"
    with HistoryStore(path) as store:
        _commit(store)

    connection = sqlite3.connect(path)
    connection.execute(
        """
        UPDATE c06_projection_outbox
        SET state = 'completed', completed_at = '2026-08-03T04:10:00.000Z'
        """
    )
    connection.commit()
    connection.close()

    with HistoryStore(path) as reopened:
        duplicate_record = _commit(
            reopened,
            batch_id="batch-000004",
            page_index=1,
            record=history_record(),
        )

        assert duplicate_record.status == "accepted"
        assert duplicate_record.inserted_count == 0
        assert duplicate_record.duplicate_count == 1
        assert reopened.pending_projection_hours() == ()


def test_idempotent_migration_preserves_existing_manager_tables(tmp_path: Path) -> None:
    path = tmp_path / "manager-state.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE registrations (node_id TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO registrations(node_id) VALUES ('node-legacy')")
    connection.commit()
    connection.close()

    with HistoryStore(path) as store:
        assert store.schema_version() == 1
    with HistoryStore(path) as store:
        assert store.schema_version() == 1

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT node_id FROM registrations").fetchone() == (
        "node-legacy",
    )
    connection.close()


def test_concurrent_duplicate_page_has_single_durable_insert(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: _commit(store), range(2)))

        assert sorted(result.status for result in results) == ["accepted", "duplicate"]
        assert store.count_records() == 1


def test_prunes_raw_records_older_than_retention_window(tmp_path: Path) -> None:
    old_record = history_record(sampled_at="2026-07-20T04:00:00Z")
    with HistoryStore(tmp_path / "manager-state.sqlite3", retention_days=7) as store:
        _commit(store, record=old_record)
        assert store.count_records() == 0
        assert store.pending_projection_hours() == ()
