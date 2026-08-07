from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

_NODE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_BOOT_ID = re.compile(r"^boot_([0-9a-f]{16})$")
_MAX_SEQ = 2**32 - 1
_SCHEMA_VERSION = 1
_EXPECTED_TABLES = {
    "n3w_replay_meta",
    "n3w_replay_state",
    "n3w_replay_seen",
}

InspectionStatus = Literal["ready", "duplicate", "stale_boot_session"]
CommitStatus = Literal["accepted", "duplicate", "stale_boot_session"]


class ReplayRegistryError(RuntimeError):
    """Base error for persistent replay state failures."""


class ReplayRegistryUnavailable(ReplayRegistryError):
    """Persistent replay state cannot be trusted, so ingress must fail closed."""


@dataclass(frozen=True, slots=True)
class ReplayTuple:
    node_id: str
    boot_id: str
    boot_session: int
    seq: int


@dataclass(frozen=True, slots=True)
class ReplayInspection:
    status: InspectionStatus
    key: ReplayTuple
    highest_session: int | None


@dataclass(frozen=True, slots=True)
class ReplayCommit:
    status: CommitStatus
    key: ReplayTuple
    highest_session: int


def _utc_text() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_replay_tuple(node_id: str, boot_id: str, seq: int) -> ReplayTuple:
    if not isinstance(node_id, str) or _NODE_ID.fullmatch(node_id) is None:
        raise ValueError("node_id_invalid")
    if not isinstance(boot_id, str):
        raise ValueError("boot_session_invalid")
    match = _BOOT_ID.fullmatch(boot_id)
    if match is None:
        raise ValueError("boot_session_invalid")
    boot_session = int(match.group(1), 16)
    if boot_session == 0:
        raise ValueError("boot_session_invalid")
    if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq <= _MAX_SEQ:
        raise ValueError("sequence_out_of_range")
    return ReplayTuple(
        node_id=node_id,
        boot_id=boot_id,
        boot_session=boot_session,
        seq=seq,
    )


class ReplayRegistry:
    """SQLite-backed N3-W replay and boot-session high-water registry.

    Inspection is read-only. ``commit`` re-checks the tuple inside one
    ``BEGIN IMMEDIATE`` transaction so a successful telemetry validator can
    atomically advance the high-water and consume the replay tuple immediately
    before canonical acceptance.
    """

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        self._lock = threading.RLock()
        self._closed = False
        try:
            database = str(self.path)
            if self.read_only:
                database = f"{self.path.resolve().as_uri()}?mode=ro"
            self._connection = sqlite3.connect(
                database,
                isolation_level=None,
                check_same_thread=False,
                timeout=5.0,
                uri=self.read_only,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            if self.read_only:
                self._require_schema()
            else:
                self._initialize()
            self._require_integrity()
        except (OSError, sqlite3.Error, ReplayRegistryUnavailable) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            if isinstance(exc, ReplayRegistryUnavailable):
                raise
            raise ReplayRegistryUnavailable("replay_registry_unavailable") from exc

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS n3w_replay_meta (
                    schema_version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS n3w_replay_state (
                    node_id TEXT PRIMARY KEY,
                    highest_session_hex TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS n3w_replay_seen (
                    node_id TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    committed_at TEXT NOT NULL,
                    PRIMARY KEY (node_id, boot_id, seq),
                    FOREIGN KEY (node_id)
                        REFERENCES n3w_replay_state(node_id)
                        ON DELETE RESTRICT
                );
                """
            )
            rows = self._connection.execute("SELECT schema_version FROM n3w_replay_meta").fetchall()
            if not rows:
                self._connection.execute(
                    "INSERT INTO n3w_replay_meta (schema_version) VALUES (?)",
                    (_SCHEMA_VERSION,),
                )
        self._require_schema()

    def _require_schema(self) -> None:
        rows = self._connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name LIKE 'n3w_replay_%'
            """
        ).fetchall()
        names = {row["name"] for row in rows}
        if names != _EXPECTED_TABLES:
            raise ReplayRegistryUnavailable("replay_registry_schema_mismatch")
        versions = self._connection.execute("SELECT schema_version FROM n3w_replay_meta").fetchall()
        if len(versions) != 1 or versions[0]["schema_version"] != _SCHEMA_VERSION:
            raise ReplayRegistryUnavailable("replay_registry_schema_mismatch")

    def _require_integrity(self) -> None:
        row = self._connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            raise ReplayRegistryUnavailable("replay_registry_corrupt")

    def _require_open(self) -> None:
        if self._closed:
            raise ReplayRegistryUnavailable("replay_registry_unavailable")

    @staticmethod
    def _session_hex(session: int) -> str:
        return f"{session:016x}"

    @staticmethod
    def _parse_session_hex(value: object) -> int:
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{16}", value) is None:
            raise ReplayRegistryUnavailable("replay_registry_corrupt")
        session = int(value, 16)
        if session == 0:
            raise ReplayRegistryUnavailable("replay_registry_corrupt")
        return session

    def _highest_session(self, node_id: str) -> int | None:
        row = self._connection.execute(
            "SELECT highest_session_hex FROM n3w_replay_state WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return self._parse_session_hex(row["highest_session_hex"])

    def _is_seen(self, key: ReplayTuple) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM n3w_replay_seen
            WHERE node_id = ? AND boot_id = ? AND seq = ?
            """,
            (key.node_id, key.boot_id, key.seq),
        ).fetchone()
        return row is not None

    def inspect(self, *, node_id: str, boot_id: str, seq: int) -> ReplayInspection:
        key = validate_replay_tuple(node_id, boot_id, seq)
        with self._lock:
            self._require_open()
            try:
                highest = self._highest_session(key.node_id)
                if highest is not None and key.boot_session < highest:
                    return ReplayInspection("stale_boot_session", key, highest)
                if self._is_seen(key):
                    return ReplayInspection("duplicate", key, highest)
                return ReplayInspection("ready", key, highest)
            except sqlite3.Error as exc:
                raise ReplayRegistryUnavailable("replay_registry_unavailable") from exc

    def commit(self, *, node_id: str, boot_id: str, seq: int) -> ReplayCommit:
        key = validate_replay_tuple(node_id, boot_id, seq)
        with self._lock:
            self._require_open()
            if self.read_only:
                raise ReplayRegistryUnavailable("replay_registry_read_only")
            transaction_open = False
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                transaction_open = True
                highest = self._highest_session(key.node_id)
                if highest is not None and key.boot_session < highest:
                    self._connection.execute("COMMIT")
                    transaction_open = False
                    return ReplayCommit("stale_boot_session", key, highest)
                if self._is_seen(key):
                    self._connection.execute("COMMIT")
                    transaction_open = False
                    return ReplayCommit("duplicate", key, highest or key.boot_session)

                new_highest = max(highest or 0, key.boot_session)
                if highest is None:
                    self._connection.execute(
                        """
                        INSERT INTO n3w_replay_state (node_id, highest_session_hex)
                        VALUES (?, ?)
                        """,
                        (key.node_id, self._session_hex(new_highest)),
                    )
                elif new_highest != highest:
                    self._connection.execute(
                        """
                        UPDATE n3w_replay_state
                        SET highest_session_hex = ?
                        WHERE node_id = ?
                        """,
                        (self._session_hex(new_highest), key.node_id),
                    )
                    self._connection.execute(
                        """
                        DELETE FROM n3w_replay_seen
                        WHERE node_id = ? AND boot_id <> ?
                        """,
                        (key.node_id, key.boot_id),
                    )
                self._connection.execute(
                    """
                    INSERT INTO n3w_replay_seen (
                        node_id, boot_id, seq, committed_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (key.node_id, key.boot_id, key.seq, _utc_text()),
                )
                self._connection.execute("COMMIT")
                transaction_open = False
                return ReplayCommit("accepted", key, new_highest)
            except (sqlite3.Error, ReplayRegistryUnavailable) as exc:
                if transaction_open:
                    with suppress(sqlite3.Error):
                        self._connection.execute("ROLLBACK")
                if isinstance(exc, ReplayRegistryUnavailable):
                    raise
                raise ReplayRegistryUnavailable("replay_registry_unavailable") from exc

    def audit(self) -> dict[str, int | str]:
        with self._lock:
            self._require_open()
            try:
                self._require_integrity()
                node_count_row = self._connection.execute(
                    "SELECT COUNT(*) FROM n3w_replay_state"
                ).fetchone()
                replay_count_row = self._connection.execute(
                    "SELECT COUNT(*) FROM n3w_replay_seen"
                ).fetchone()
                node_count = int(node_count_row[0])
                replay_count = int(replay_count_row[0])
                rows = self._connection.execute(
                    "SELECT node_id, highest_session_hex FROM n3w_replay_state"
                ).fetchall()
                highest_by_node: dict[str, int] = {}
                for row in rows:
                    node_id = row["node_id"]
                    if not isinstance(node_id, str) or _NODE_ID.fullmatch(node_id) is None:
                        raise ReplayRegistryUnavailable("replay_registry_corrupt")
                    highest_by_node[node_id] = self._parse_session_hex(row["highest_session_hex"])
                seen_rows = self._connection.execute(
                    "SELECT node_id, boot_id, seq FROM n3w_replay_seen"
                ).fetchall()
                for row in seen_rows:
                    try:
                        key = validate_replay_tuple(
                            row["node_id"],
                            row["boot_id"],
                            row["seq"],
                        )
                    except (TypeError, ValueError) as exc:
                        raise ReplayRegistryUnavailable("replay_registry_corrupt") from exc
                    highest = highest_by_node.get(key.node_id)
                    if highest is None or key.boot_session != highest:
                        raise ReplayRegistryUnavailable("replay_registry_corrupt")
                return {
                    "schema": "gh.n3w-replay-registry-audit/1",
                    "status": "passed",
                    "schema_version": _SCHEMA_VERSION,
                    "node_count": node_count,
                    "replay_tuple_count": replay_count,
                }
            except sqlite3.Error as exc:
                raise ReplayRegistryUnavailable("replay_registry_unavailable") from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> ReplayRegistry:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
