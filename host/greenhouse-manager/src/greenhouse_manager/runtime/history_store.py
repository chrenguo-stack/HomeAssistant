from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class HistoryStoreError(RuntimeError):
    """Base class for durable C-06 history storage failures."""


class HistoryConflict(HistoryStoreError):
    """Raised when a stable page or record identity is reused with different content."""


@dataclass(frozen=True, slots=True)
class PageCommitResult:
    status: str
    record_count: int
    inserted_count: int
    duplicate_count: int
    committed_at: datetime


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized_timestamp(value: str) -> str:
    return _timestamp(_parse_timestamp(value))


def _sample_hour(sampled_at: str) -> str:
    value = _parse_timestamp(sampled_at)
    return _timestamp(value.replace(minute=0, second=0, microsecond=0))


class HistoryStore:
    """Thread-safe, durable C-06 raw history and projection-outbox storage.

    All C-06 objects use a dedicated ``c06_`` table prefix so the store can share
    PR #260's portable ``manager-state.sqlite3`` file without taking ownership of
    registration, credential, or retirement tables.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path, *, retention_days: int = 7) -> None:
        if not 1 <= retention_days <= 30:
            raise ValueError("retention_days must be between 1 and 30")
        self.path = Path(path)
        self.retention = timedelta(days=retention_days)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path),
            isolation_level="IMMEDIATE",
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._initialize()

    def _initialize(self) -> None:
        applied_at = _timestamp(datetime.now(UTC))
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS c06_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS c06_history_pages (
                    node_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    page_index INTEGER NOT NULL CHECK (page_index >= 0),
                    page_count INTEGER NOT NULL CHECK (page_count >= 1),
                    payload_sha256 TEXT NOT NULL,
                    record_count INTEGER NOT NULL CHECK (record_count >= 1),
                    inserted_count INTEGER NOT NULL CHECK (inserted_count >= 0),
                    duplicate_count INTEGER NOT NULL CHECK (duplicate_count >= 0),
                    committed_at TEXT NOT NULL,
                    PRIMARY KEY (node_id, batch_id, page_index)
                );

                CREATE INDEX IF NOT EXISTS c06_history_pages_committed_at
                    ON c06_history_pages(committed_at);

                CREATE TABLE IF NOT EXISTS c06_history_records (
                    node_id TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    seq INTEGER NOT NULL CHECK (seq >= 0),
                    sampled_at TEXT NOT NULL,
                    sample_hour TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    page_index INTEGER NOT NULL CHECK (page_index >= 0),
                    received_at TEXT NOT NULL,
                    PRIMARY KEY (node_id, boot_id, seq)
                );

                CREATE INDEX IF NOT EXISTS c06_history_records_sample_time
                    ON c06_history_records(node_id, sampled_at);

                CREATE INDEX IF NOT EXISTS c06_history_records_hour
                    ON c06_history_records(node_id, sample_hour);

                CREATE TABLE IF NOT EXISTS c06_projection_outbox (
                    node_id TEXT NOT NULL,
                    sample_hour TEXT NOT NULL,
                    projection_version INTEGER NOT NULL DEFAULT 1,
                    state TEXT NOT NULL DEFAULT 'pending'
                        CHECK (state IN ('pending', 'completed')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    PRIMARY KEY (node_id, sample_hour, projection_version)
                );

                CREATE INDEX IF NOT EXISTS c06_projection_outbox_pending
                    ON c06_projection_outbox(state, sample_hour, node_id);
                """
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO c06_schema_migrations(version, applied_at)
                VALUES (?, ?)
                """,
                (self.SCHEMA_VERSION, applied_at),
            )
            versions = [
                int(row["version"])
                for row in self._connection.execute(
                    "SELECT version FROM c06_schema_migrations ORDER BY version"
                ).fetchall()
            ]
            if versions != [self.SCHEMA_VERSION]:
                raise HistoryStoreError(
                    f"unsupported C-06 schema migration set: {versions}"
                )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def commit_page(
        self,
        *,
        node_id: str,
        batch_id: str,
        page_index: int,
        page_count: int,
        records: list[dict[str, Any]],
        payload_sha256: str,
        received_at: datetime,
    ) -> PageCommitResult:
        if not records:
            raise ValueError("history page must contain at least one record")
        committed_at = _utc(received_at)
        committed_text = _timestamp(committed_at)

        prepared: list[tuple[dict[str, Any], str, str, str, str]] = []
        in_page_keys: set[tuple[str, int]] = set()
        for record in records:
            key = (str(record["boot_id"]), int(record["seq"]))
            if key in in_page_keys:
                raise HistoryConflict("duplicate record identity inside one page")
            in_page_keys.add(key)
            record_json = _canonical_json(record)
            prepared.append(
                (
                    record,
                    record_json,
                    _sha256_text(record_json),
                    _normalized_timestamp(str(record["sampled_at"])),
                    _sample_hour(str(record["sampled_at"])),
                )
            )

        with self._lock, self._connection:
            existing_page = self._connection.execute(
                """
                SELECT * FROM c06_history_pages
                WHERE node_id = ? AND batch_id = ? AND page_index = ?
                """,
                (node_id, batch_id, page_index),
            ).fetchone()
            if existing_page is not None:
                if existing_page["payload_sha256"] != payload_sha256:
                    raise HistoryConflict("page identity reused with different payload")
                if int(existing_page["page_count"]) != page_count:
                    raise HistoryConflict("page identity reused with different page_count")
                return PageCommitResult(
                    status="duplicate",
                    record_count=int(existing_page["record_count"]),
                    inserted_count=int(existing_page["inserted_count"]),
                    duplicate_count=int(existing_page["duplicate_count"]),
                    committed_at=_parse_timestamp(str(existing_page["committed_at"])),
                )

            inserted_count = 0
            duplicate_count = 0
            for record, _record_json, record_sha256, _sampled_at, _hour in prepared:
                existing_record = self._connection.execute(
                    """
                    SELECT record_sha256 FROM c06_history_records
                    WHERE node_id = ? AND boot_id = ? AND seq = ?
                    """,
                    (node_id, str(record["boot_id"]), int(record["seq"])),
                ).fetchone()
                if existing_record is None:
                    inserted_count += 1
                    continue
                if existing_record["record_sha256"] != record_sha256:
                    raise HistoryConflict(
                        "record identity reused with different historical content"
                    )
                duplicate_count += 1

            for record, record_json, record_sha256, sampled_at, hour in prepared:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO c06_history_records (
                        node_id, boot_id, seq, sampled_at, sample_hour,
                        record_sha256, record_json, batch_id, page_index, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        str(record["boot_id"]),
                        int(record["seq"]),
                        sampled_at,
                        hour,
                        record_sha256,
                        record_json,
                        batch_id,
                        page_index,
                        committed_text,
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO c06_projection_outbox (
                        node_id, sample_hour, projection_version, state,
                        attempts, last_error, created_at, updated_at, completed_at
                    ) VALUES (?, ?, 1, 'pending', 0, NULL, ?, ?, NULL)
                    ON CONFLICT(node_id, sample_hour, projection_version) DO UPDATE SET
                        state = 'pending',
                        last_error = NULL,
                        updated_at = excluded.updated_at,
                        completed_at = NULL
                    """,
                    (node_id, hour, committed_text, committed_text),
                )

            self._connection.execute(
                """
                INSERT INTO c06_history_pages (
                    node_id, batch_id, page_index, page_count, payload_sha256,
                    record_count, inserted_count, duplicate_count, committed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    batch_id,
                    page_index,
                    page_count,
                    payload_sha256,
                    len(records),
                    inserted_count,
                    duplicate_count,
                    committed_text,
                ),
            )
            self._prune_locked(committed_at)

        return PageCommitResult(
            status="accepted",
            record_count=len(records),
            inserted_count=inserted_count,
            duplicate_count=duplicate_count,
            committed_at=committed_at,
        )

    def _prune_locked(self, now: datetime) -> int:
        cutoff = _timestamp(_utc(now) - self.retention)
        cursor = self._connection.execute(
            "DELETE FROM c06_history_records WHERE sampled_at < ?",
            (cutoff,),
        )
        self._connection.execute(
            "DELETE FROM c06_projection_outbox WHERE sample_hour < ?",
            (cutoff,),
        )
        self._connection.execute(
            "DELETE FROM c06_history_pages WHERE committed_at < ?",
            (cutoff,),
        )
        return max(cursor.rowcount, 0)

    def prune(self, *, now: datetime | None = None) -> int:
        with self._lock, self._connection:
            return self._prune_locked(now or datetime.now(UTC))

    def count_records(self, *, node_id: str | None = None) -> int:
        with self._lock:
            if node_id is None:
                row = self._connection.execute(
                    "SELECT COUNT(*) AS count FROM c06_history_records"
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT COUNT(*) AS count FROM c06_history_records WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
            assert row is not None
            return int(row["count"])

    def get_record(self, node_id: str, boot_id: str, seq: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT record_json FROM c06_history_records
                WHERE node_id = ? AND boot_id = ? AND seq = ?
                """,
                (node_id, boot_id, seq),
            ).fetchone()
            if row is None:
                return None
            value = json.loads(str(row["record_json"]))
            assert isinstance(value, dict)
            return value

    def pending_projection_hours(self) -> tuple[tuple[str, str], ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT node_id, sample_hour
                FROM c06_projection_outbox
                WHERE state = 'pending'
                ORDER BY sample_hour, node_id
                """
            ).fetchall()
            return tuple((str(row["node_id"]), str(row["sample_hour"])) for row in rows)

    def schema_version(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT MAX(version) AS version FROM c06_schema_migrations"
            ).fetchone()
            assert row is not None
            return int(row["version"])
