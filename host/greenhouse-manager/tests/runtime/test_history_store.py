from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from history_samples import history_record

from greenhouse_manager.runtime.history_store import (
    HistoryCapacityExceeded,
    HistoryConflict,
    HistoryStore,
)


def _payload_hash(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit(
    store: HistoryStore,
    *,
    batch_id: str = "batch-000001",
    page_index: int = 0,
    page_count: int = 2,
    records: list[dict[str, object]] | None = None,
    record: dict[str, object] | None = None,
    received_at: datetime = datetime(2026, 8, 3, 4, 5, tzinfo=UTC),
) -> object:
    page_records = records or [record or history_record()]
    document = {
        "schema": "gh.history-replay.batch/1",
        "node_id": "node-0001",
        "batch_id": batch_id,
        "page_index": page_index,
        "page_count": page_count,
        "records": page_records,
    }
    return store.commit_page(
        node_id="node-0001",
        batch_id=batch_id,
        page_index=page_index,
        page_count=page_count,
        records=page_records,
        payload_sha256=_payload_hash(document),
        received_at=received_at,
    )


def _path(tmp_path: Path) -> Path:
    return tmp_path / "manager" / "manager-state.sqlite3"


def test_commits_raw_record_and_projection_outbox_durably(tmp_path: Path) -> None:
    path = _path(tmp_path)
    with HistoryStore(path) as store:
        result = _commit(store)
        assert result.status == "accepted"
        assert result.inserted_count == 1
        assert result.next_page_index == 1
        assert store.count_records() == 1
        assert store.pending_projection_hours() == (
            ("node-0001", "2026-08-03T04:00:00.000Z"),
        )

    with HistoryStore(path) as reopened:
        duplicate = _commit(reopened)
        assert duplicate.status == "duplicate"
        assert duplicate.next_page_index == 1
        assert reopened.count_records() == 1
        assert reopened.get_record("node-0001", "boot-00000001", 1) == history_record()


def test_database_path_is_absolute_private_and_non_symlink(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        HistoryStore(Path("manager-state.sqlite3"))

    path = _path(tmp_path)
    with HistoryStore(path):
        pass
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    link = tmp_path / "linked.sqlite3"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        HistoryStore(link)


def test_rejects_record_identity_collision_without_partial_write(tmp_path: Path) -> None:
    with HistoryStore(_path(tmp_path)) as store:
        _commit(store)
        conflicting = history_record(temperature=31.0)
        with pytest.raises(HistoryConflict, match="different historical content"):
            _commit(store, batch_id="batch-000002", record=conflicting)

        assert store.count_records() == 1
        assert store.get_record("node-0001", "boot-00000001", 1) == history_record()


def test_rejects_inconsistent_page_count_for_same_batch(tmp_path: Path) -> None:
    with HistoryStore(_path(tmp_path)) as store:
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
    path = _path(tmp_path)
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
    path = _path(tmp_path)
    path.parent.mkdir(mode=0o700)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE registrations (node_id TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO registrations(node_id) VALUES ('node-legacy')")
    connection.commit()
    connection.close()

    with HistoryStore(path) as store:
        assert store.schema_version() == 2
    with HistoryStore(path) as store:
        assert store.schema_version() == 2

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT node_id FROM registrations").fetchone() == (
        "node-legacy",
    )
    connection.close()


def test_migrates_reviewed_v1_c06_records_to_v2_clock_columns(tmp_path: Path) -> None:
    path = _path(tmp_path)
    path.parent.mkdir(mode=0o700)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE c06_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO c06_schema_migrations VALUES (1, '2026-08-03T04:00:00.000Z');
        CREATE TABLE c06_history_pages (
            node_id TEXT NOT NULL, batch_id TEXT NOT NULL,
            page_index INTEGER NOT NULL, page_count INTEGER NOT NULL,
            payload_sha256 TEXT NOT NULL, record_count INTEGER NOT NULL,
            inserted_count INTEGER NOT NULL, duplicate_count INTEGER NOT NULL,
            committed_at TEXT NOT NULL,
            PRIMARY KEY (node_id, batch_id, page_index)
        );
        CREATE TABLE c06_history_records (
            node_id TEXT NOT NULL, boot_id TEXT NOT NULL, seq INTEGER NOT NULL,
            sampled_at TEXT NOT NULL, sample_hour TEXT NOT NULL,
            record_sha256 TEXT NOT NULL, record_json TEXT NOT NULL,
            batch_id TEXT NOT NULL, page_index INTEGER NOT NULL,
            received_at TEXT NOT NULL,
            PRIMARY KEY (node_id, boot_id, seq)
        );
        CREATE TABLE c06_projection_outbox (
            node_id TEXT NOT NULL, sample_hour TEXT NOT NULL,
            projection_version INTEGER NOT NULL DEFAULT 1,
            state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            completed_at TEXT,
            PRIMARY KEY (node_id, sample_hour, projection_version)
        );
        """
    )
    record = history_record()
    record_json = json.dumps(record, separators=(",", ":"), sort_keys=True)
    connection.execute(
        """
        INSERT INTO c06_history_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "node-0001",
            "boot-00000001",
            1,
            "2026-08-03T04:00:00.000Z",
            "2026-08-03T04:00:00.000Z",
            hashlib.sha256(record_json.encode()).hexdigest(),
            record_json,
            "batch-000001",
            0,
            "2026-08-03T04:05:00.000Z",
        ),
    )
    connection.commit()
    connection.close()

    with HistoryStore(path) as store:
        assert store.schema_version() == 2
        assert store.count_records() == 1

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT time_quality, time_anchor_json FROM c06_history_records"
    ).fetchone()
    assert row == ("trusted", None)
    connection.close()


def test_two_connections_serialize_conflicting_record_identity(tmp_path: Path) -> None:
    path = _path(tmp_path)
    first = HistoryStore(path)
    second = HistoryStore(path)

    def commit(store: HistoryStore, batch_id: str, temperature: float) -> str:
        try:
            _commit(
                store,
                batch_id=batch_id,
                page_count=1,
                record=history_record(temperature=temperature),
            )
            return "accepted"
        except HistoryConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: commit(*args),
                (
                    (first, "batch-conn-01", 25.0),
                    (second, "batch-conn-02", 31.0),
                ),
            )
        )

    assert sorted(results) == ["accepted", "conflict"]
    assert first.count_records() == 1
    first.close()
    second.close()


def test_prune_preserves_hour_outbox_while_valid_record_remains(tmp_path: Path) -> None:
    with HistoryStore(_path(tmp_path), retention_days=7) as store:
        records = [
            history_record(seq=1, sampled_at="2026-08-03T04:01:00Z"),
            history_record(seq=2, sampled_at="2026-08-03T04:10:00Z"),
        ]
        _commit(
            store,
            batch_id="batch-prune01",
            page_count=1,
            records=records,
            received_at=datetime(2026, 8, 3, 4, 15, tzinfo=UTC),
        )

        store.prune(now=datetime(2026, 8, 10, 4, 5, tzinfo=UTC))

        assert store.count_records() == 1
        assert store.pending_projection_hours() == (
            ("node-0001", "2026-08-03T04:00:00.000Z"),
        )


def test_relative_only_record_is_retained_by_received_time_without_projection(
    tmp_path: Path,
) -> None:
    relative = history_record(
        sampled_at=None,
        time_quality="relative_only",
        time_anchor=None,
    )
    with HistoryStore(_path(tmp_path), retention_days=7) as store:
        _commit(store, page_count=1, record=relative)
        assert store.count_records() == 1
        assert store.pending_projection_hours() == ()

        store.prune(now=datetime(2026, 8, 11, 4, 5, tzinfo=UTC))
        assert store.count_records() == 0


def test_rejects_record_capacity_before_partial_write(tmp_path: Path) -> None:
    with HistoryStore(_path(tmp_path), max_records=1_024) as store:
        connection = sqlite3.connect(store.path)
        base = history_record()
        rows = []
        for seq in range(1_024):
            record = dict(base, seq=seq, boot_id=f"boot-{seq:08d}")
            text = json.dumps(record, separators=(",", ":"), sort_keys=True)
            rows.append(
                (
                    "node-fill",
                    record["boot_id"],
                    seq,
                    "2026-08-03T04:00:00.000Z",
                    "2026-08-03T04:00:00.000Z",
                    "trusted",
                    None,
                    hashlib.sha256(text.encode()).hexdigest(),
                    text,
                    "batch-fill",
                    0,
                    "2026-08-03T04:05:00.000Z",
                )
            )
        connection.executemany(
            """
            INSERT INTO c06_history_records (
                node_id, boot_id, seq, sampled_at, sample_hour,
                time_quality, time_anchor_json, record_sha256, record_json,
                batch_id, page_index, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
        connection.close()

        with pytest.raises(HistoryCapacityExceeded, match="record capacity"):
            _commit(
                store,
                batch_id="batch-cap-001",
                page_count=1,
                record=history_record(seq=5000, boot_id="boot-cap-0001"),
            )
        assert store.count_records() == 1_024
