from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_HISTORY_DB_ROLE_PARTS = ("manager", "manager-state.sqlite3")


class HistoryStoreError(RuntimeError):
    """Base class for durable C-06 history storage failures."""


class HistoryConflict(HistoryStoreError):
    """Raised when a stable page or record identity is reused with different content."""


class HistoryCapacityExceeded(HistoryStoreError):
    """Raised when configured durable capacity would be exceeded."""


@dataclass(frozen=True, slots=True)
class PageCommitResult:
    status: str
    record_count: int
    inserted_count: int
    duplicate_count: int
    committed_at: datetime
    next_page_index: int | None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    parsed = datetime.fromisoformat(normalized)
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


def _private_path(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("history database path must be absolute")
    if path.is_symlink():
        raise ValueError("history database path must not be a symlink")
    if path.parts[-2:] != _HISTORY_DB_ROLE_PARTS:
        raise ValueError(
            "history database path must target manager/manager-state.sqlite3"
        )
    parent = path.parent
    current = parent
    while True:
        if current.is_symlink():
            raise ValueError("history database path ancestors must not be symlinks")
        if current == current.parent:
            break
        current = current.parent
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("history database parent must be a directory")
    os.chmod(parent, 0o700)


class HistoryStore:
    """Thread-safe, durable C-06 raw history and projection-outbox storage."""

    SCHEMA_VERSION = 2

    def __init__(
        self,
        path: str | Path,
        *,
        retention_days: int = 7,
        max_records: int = 250_000,
        max_db_bytes: int = 268_435_456,
    ) -> None:
        if not 1 <= retention_days <= 30:
            raise ValueError("retention_days must be between 1 and 30")
        if not 1_024 <= max_records <= 2_000_000:
            raise ValueError("max_records must be between 1024 and 2000000")
        if not 1_048_576 <= max_db_bytes <= 2_147_483_648:
            raise ValueError("max_db_bytes must be between 1048576 and 2147483648")
        self.path = Path(path)
        _private_path(self.path)
        self.retention = timedelta(days=retention_days)
        self.max_records = max_records
        self.max_db_bytes = max_db_bytes
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path),
            isolation_level=None,
            check_same_thread=False,
        )
        os.chmod(self.path, 0o600)
        if stat.S_IMODE(self.path.stat().st_mode) & 0o077:
            raise HistoryStoreError("history database must not be group- or world-accessible")
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

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS c06_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                int(row["version"])
                for row in self._connection.execute(
                    "SELECT version FROM c06_schema_migrations"
                ).fetchall()
            }
            unsupported = sorted(
                version for version in applied if version > self.SCHEMA_VERSION
            )
            if unsupported:
                raise HistoryStoreError(
                    f"unsupported C-06 schema migration set: {unsupported}"
                )
            if 1 not in applied:
                self._apply_v1()
                applied.add(1)
            if 2 not in applied:
                self._apply_v2()
                applied.add(2)
            if applied != {1, 2}:
                raise HistoryStoreError(
                    f"unsupported C-06 schema migration set: {sorted(applied)}"
                )

    def _record_migration(self, version: int) -> None:
        self._connection.execute(
            "INSERT INTO c06_schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, _timestamp(datetime.now(UTC))),
        )

    def _apply_v1(self) -> None:
        try:
            self._connection.executescript(
                """
                BEGIN IMMEDIATE;

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
            self._record_migration(1)
            self._commit()
        except Exception:
            self._rollback()
            raise

    def _apply_v2(self) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(
                "PRAGMA table_info(c06_history_records)"
            ).fetchall()
        }
        try:
            if "time_quality" in columns:
                self._transaction()
            else:
                self._connection.executescript(
                    """
                    BEGIN IMMEDIATE;

                    ALTER TABLE c06_history_records RENAME TO c06_history_records_v1;

                    CREATE TABLE c06_history_records (
                        node_id TEXT NOT NULL,
                        boot_id TEXT NOT NULL,
                        seq INTEGER NOT NULL CHECK (seq >= 0),
                        sampled_at TEXT,
                        sample_hour TEXT,
                        time_quality TEXT NOT NULL
                            CHECK (time_quality IN ('trusted', 'estimated', 'relative_only')),
                        time_anchor_json TEXT,
                        record_sha256 TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        batch_id TEXT NOT NULL,
                        page_index INTEGER NOT NULL CHECK (page_index >= 0),
                        received_at TEXT NOT NULL,
                        PRIMARY KEY (node_id, boot_id, seq),
                        CHECK (
                            (time_quality = 'relative_only'
                                AND sampled_at IS NULL AND sample_hour IS NULL)
                            OR
                            (time_quality != 'relative_only'
                                AND sampled_at IS NOT NULL AND sample_hour IS NOT NULL)
                        )
                    );

                    INSERT INTO c06_history_records (
                        node_id, boot_id, seq, sampled_at, sample_hour,
                        time_quality, time_anchor_json, record_sha256, record_json,
                        batch_id, page_index, received_at
                    )
                    SELECT node_id, boot_id, seq, sampled_at, sample_hour,
                           'trusted', NULL, record_sha256, record_json,
                           batch_id, page_index, received_at
                    FROM c06_history_records_v1;

                    DROP TABLE c06_history_records_v1;

                    CREATE INDEX c06_history_records_sample_time
                        ON c06_history_records(node_id, sampled_at);

                    CREATE INDEX c06_history_records_hour
                        ON c06_history_records(node_id, sample_hour);

                    CREATE INDEX c06_history_records_received_at
                        ON c06_history_records(received_at);
                    """
                )
            self._record_migration(2)
            self._commit()
        except Exception:
            self._rollback()
            raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _db_size_locked(self) -> int:
        page_count = int(self._connection.execute("PRAGMA page_count").fetchone()[0])
        free_count = int(self._connection.execute("PRAGMA freelist_count").fetchone()[0])
        page_size = int(self._connection.execute("PRAGMA page_size").fetchone()[0])
        return max(page_count - free_count, 0) * page_size

    def _next_page_index_locked(
        self, node_id: str, batch_id: str, page_count: int
    ) -> int | None:
        present = {
            int(row["page_index"])
            for row in self._connection.execute(
                """
                SELECT page_index FROM c06_history_pages
                WHERE node_id = ? AND batch_id = ?
                """,
                (node_id, batch_id),
            ).fetchall()
        }
        for candidate in range(page_count):
            if candidate not in present:
                return candidate
        return None

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

        prepared: list[
            tuple[dict[str, Any], str, str, str | None, str | None, str, str | None]
        ] = []
        in_page_keys: set[tuple[str, int]] = set()
        for record in records:
            key = (str(record["boot_id"]), int(record["seq"]))
            if key in in_page_keys:
                raise HistoryConflict("duplicate record identity inside one page")
            in_page_keys.add(key)
            record_json = _canonical_json(record)
            time_quality = str(record["time_quality"])
            raw_sampled_at = record.get("sampled_at")
            sampled_at = (
                _normalized_timestamp(str(raw_sampled_at))
                if raw_sampled_at is not None
                else None
            )
            hour = _sample_hour(sampled_at) if sampled_at is not None else None
            raw_anchor = record.get("time_anchor")
            anchor_json = _canonical_json(raw_anchor) if raw_anchor is not None else None
            prepared.append(
                (
                    record,
                    record_json,
                    _sha256_text(record_json),
                    sampled_at,
                    hour,
                    time_quality,
                    anchor_json,
                )
            )

        with self._lock:
            self._transaction()
            try:
                self._prune_locked(committed_at)
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
                    next_page_index = self._next_page_index_locked(
                        node_id, batch_id, page_count
                    )
                    result = PageCommitResult(
                        status="duplicate",
                        record_count=int(existing_page["record_count"]),
                        inserted_count=int(existing_page["inserted_count"]),
                        duplicate_count=int(existing_page["duplicate_count"]),
                        committed_at=_parse_timestamp(str(existing_page["committed_at"])),
                        next_page_index=next_page_index,
                    )
                    self._commit()
                    return result

                existing_batch = self._connection.execute(
                    """
                    SELECT page_count FROM c06_history_pages
                    WHERE node_id = ? AND batch_id = ?
                    ORDER BY page_index
                    LIMIT 1
                    """,
                    (node_id, batch_id),
                ).fetchone()
                if (
                    existing_batch is not None
                    and int(existing_batch["page_count"]) != page_count
                ):
                    raise HistoryConflict("batch_id reused with different page_count")

                inserted_count = 0
                duplicate_count = 0
                new_record_keys: set[tuple[str, int]] = set()
                for record, _record_json, record_sha256, *_rest in prepared:
                    existing_record = self._connection.execute(
                        """
                        SELECT record_sha256 FROM c06_history_records
                        WHERE node_id = ? AND boot_id = ? AND seq = ?
                        """,
                        (node_id, str(record["boot_id"]), int(record["seq"])),
                    ).fetchone()
                    if existing_record is None:
                        inserted_count += 1
                        new_record_keys.add(
                            (str(record["boot_id"]), int(record["seq"]))
                        )
                        continue
                    if existing_record["record_sha256"] != record_sha256:
                        raise HistoryConflict(
                            "record identity reused with different historical content"
                        )
                    duplicate_count += 1

                current_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM c06_history_records"
                    ).fetchone()[0]
                )
                if current_count + inserted_count > self.max_records:
                    raise HistoryCapacityExceeded("history record capacity exceeded")
                estimated_growth = sum(
                    len(record_json.encode("utf-8")) + 1_024
                    for record, record_json, *_rest in prepared
                    if (str(record["boot_id"]), int(record["seq"]))
                    in new_record_keys
                )
                if self._db_size_locked() + estimated_growth > self.max_db_bytes:
                    raise HistoryCapacityExceeded("history database byte capacity exceeded")

                for (
                    record,
                    record_json,
                    record_sha256,
                    sampled_at,
                    hour,
                    time_quality,
                    anchor_json,
                ) in prepared:
                    insert = self._connection.execute(
                        """
                        INSERT OR IGNORE INTO c06_history_records (
                            node_id, boot_id, seq, sampled_at, sample_hour,
                            time_quality, time_anchor_json, record_sha256, record_json,
                            batch_id, page_index, received_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            node_id,
                            str(record["boot_id"]),
                            int(record["seq"]),
                            sampled_at,
                            hour,
                            time_quality,
                            anchor_json,
                            record_sha256,
                            record_json,
                            batch_id,
                            page_index,
                            committed_text,
                        ),
                    )
                    if insert.rowcount == 0:
                        persisted = self._connection.execute(
                            """
                            SELECT record_sha256 FROM c06_history_records
                            WHERE node_id = ? AND boot_id = ? AND seq = ?
                            """,
                            (node_id, str(record["boot_id"]), int(record["seq"])),
                        ).fetchone()
                        if persisted is None or persisted["record_sha256"] != record_sha256:
                            raise HistoryConflict(
                                "record identity reused with different historical content"
                            )
                        continue
                    if hour is None:
                        continue
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
                next_page_index = self._next_page_index_locked(
                    node_id, batch_id, page_count
                )
                self._commit()
            except Exception:
                self._rollback()
                raise

        return PageCommitResult(
            status="accepted",
            record_count=len(records),
            inserted_count=inserted_count,
            duplicate_count=duplicate_count,
            committed_at=committed_at,
            next_page_index=next_page_index,
        )

    def _prune_locked(self, now: datetime) -> int:
        cutoff = _timestamp(_utc(now) - self.retention)
        cursor = self._connection.execute(
            """
            DELETE FROM c06_history_records
            WHERE (sampled_at IS NOT NULL AND sampled_at < ?)
               OR (sampled_at IS NULL AND received_at < ?)
            """,
            (cutoff, cutoff),
        )
        self._connection.execute(
            """
            DELETE FROM c06_projection_outbox
            WHERE NOT EXISTS (
                SELECT 1 FROM c06_history_records AS records
                WHERE records.node_id = c06_projection_outbox.node_id
                  AND records.sample_hour = c06_projection_outbox.sample_hour
            )
            """
        )
        self._connection.execute(
            "DELETE FROM c06_history_pages WHERE committed_at < ?",
            (cutoff,),
        )
        return max(cursor.rowcount, 0)

    def prune(self, *, now: datetime | None = None) -> int:
        with self._lock:
            self._transaction()
            try:
                count = self._prune_locked(now or datetime.now(UTC))
                self._commit()
                return count
            except Exception:
                self._rollback()
                raise

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
