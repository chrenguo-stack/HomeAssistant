from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .replay_registry import ReplayRegistry, ReplayRegistryUnavailable, ReplayTuple, validate_replay_tuple

_SCHEMA_VERSION = 1
_SESSION_HEX = re.compile(r"^[0-9a-f]{16}$")
IngressSource = Literal["direct", "relay"]
CanonicalStatus = Literal["accepted", "duplicate", "rejected"]


@dataclass(frozen=True, slots=True)
class CanonicalCursorSnapshot:
    node_id: str
    boot_id: str
    boot_session: int
    seq: int
    last_source: IngressSource | None
    last_gateway_id: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalIngressDecision:
    status: CanonicalStatus
    node_id: str
    source: IngressSource
    code: str | None = None
    gateway_id: str | None = None
    boot_id: str | None = None
    seq: int | None = None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("canonical clock must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReplayRegistryUnavailable("canonical_cursor_corrupt") from error
    if parsed.tzinfo is None:
        raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
    return parsed.astimezone(UTC)


def _session_hex(value: int) -> str:
    return f"{value:016x}"


def _parse_session_hex(value: object) -> int:
    if not isinstance(value, str) or _SESSION_HEX.fullmatch(value) is None:
        raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
    parsed = int(value, 16)
    if parsed == 0:
        raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
    return parsed


class N3wCanonicalIngressCoordinator:
    """Durable transport-independent `(BOOT_ID, SEQ)` canonical high-water.

    The coordinator shares the ReplayRegistry transaction but owns no path lease,
    candidate path, TTL, switch window or grace period. Direct and Relay sources
    may both submit; only the highest valid telemetry tuple advances canonical
    state. Existing replay/path high-water is imported during initialization.
    """

    def __init__(
        self,
        *,
        replay_registry: ReplayRegistry,
        ingress_allowed: Callable[[str], bool],
    ) -> None:
        self.replay_registry = replay_registry
        self.ingress_allowed = ingress_allowed
        self._initialize()

    def _initialize(self) -> None:
        try:
            with self.replay_registry.transaction() as transaction:
                connection = transaction.connection
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS n3w_canonical_meta (
                        schema_version INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS n3w_canonical_cursors (
                        node_id TEXT PRIMARY KEY,
                        boot_session_hex TEXT NOT NULL,
                        seq INTEGER NOT NULL CHECK (seq >= 0),
                        last_source TEXT CHECK (
                            last_source IS NULL OR last_source IN ('direct', 'relay')
                        ),
                        last_gateway_id TEXT,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                versions = connection.execute(
                    "SELECT schema_version FROM n3w_canonical_meta"
                ).fetchall()
                if not versions:
                    connection.execute(
                        "INSERT INTO n3w_canonical_meta (schema_version) VALUES (?)",
                        (_SCHEMA_VERSION,),
                    )
                elif len(versions) != 1 or versions[0]["schema_version"] != _SCHEMA_VERSION:
                    raise ReplayRegistryUnavailable("canonical_cursor_schema_mismatch")
                self._migrate_replay_high_water(connection)
                self._migrate_legacy_path_high_water(connection)
        except ReplayRegistryUnavailable:
            raise
        except sqlite3.Error as error:
            raise ReplayRegistryUnavailable("canonical_cursor_unavailable") from error

    def _migrate_replay_high_water(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT s.node_id, s.highest_session_hex, MAX(v.seq) AS max_seq
            FROM n3w_replay_state AS s
            LEFT JOIN n3w_replay_seen AS v
              ON v.node_id = s.node_id
             AND substr(v.boot_id, 6, 16) = s.highest_session_hex
            GROUP BY s.node_id, s.highest_session_hex
            """
        ).fetchall()
        for row in rows:
            if row["max_seq"] is None:
                continue
            self._merge_cursor(
                connection,
                node_id=row["node_id"],
                boot_session=_parse_session_hex(row["highest_session_hex"]),
                seq=row["max_seq"],
                source=None,
                gateway_id=None,
                updated_at=datetime.now(UTC),
            )

    def _migrate_legacy_path_high_water(self, connection: sqlite3.Connection) -> None:
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'n3w_path_leases'
            """
        ).fetchone()
        if table is None:
            return
        rows = connection.execute(
            """
            SELECT node_id, canonical_boot_session_hex, canonical_seq, updated_at
            FROM n3w_path_leases
            """
        ).fetchall()
        for row in rows:
            self._merge_cursor(
                connection,
                node_id=row["node_id"],
                boot_session=_parse_session_hex(row["canonical_boot_session_hex"]),
                seq=row["canonical_seq"],
                source=None,
                gateway_id=None,
                updated_at=_parse_timestamp(row["updated_at"]),
            )

    def _merge_cursor(
        self,
        connection: sqlite3.Connection,
        *,
        node_id: str,
        boot_session: int,
        seq: int,
        source: IngressSource | None,
        gateway_id: str | None,
        updated_at: datetime,
    ) -> None:
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
        row = connection.execute(
            "SELECT boot_session_hex, seq FROM n3w_canonical_cursors WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        should_write = row is None
        if row is not None:
            current_boot = _parse_session_hex(row["boot_session_hex"])
            current_seq = row["seq"]
            if not isinstance(current_seq, int) or isinstance(current_seq, bool) or current_seq < 0:
                raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
            should_write = boot_session > current_boot or (
                boot_session == current_boot and seq > current_seq
            )
        if not should_write:
            return
        connection.execute(
            """
            INSERT INTO n3w_canonical_cursors (
                node_id, boot_session_hex, seq, last_source, last_gateway_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                boot_session_hex = excluded.boot_session_hex,
                seq = excluded.seq,
                last_source = excluded.last_source,
                last_gateway_id = excluded.last_gateway_id,
                updated_at = excluded.updated_at
            """,
            (
                node_id,
                _session_hex(boot_session),
                seq,
                source,
                gateway_id,
                _timestamp(updated_at),
            ),
        )

    @staticmethod
    def _cursor_reject(row: sqlite3.Row, key: ReplayTuple) -> str | None:
        current_boot = _parse_session_hex(row["boot_session_hex"])
        current_seq = row["seq"]
        if not isinstance(current_seq, int) or isinstance(current_seq, bool) or current_seq < 0:
            raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
        if key.boot_session < current_boot:
            return "stale_boot_session"
        if key.boot_session == current_boot and key.seq < current_seq:
            return "stale_sequence"
        if key.boot_session == current_boot and key.seq == current_seq:
            return "duplicate_node_boot_seq"
        return None

    def process(
        self,
        *,
        node_id: str,
        boot_id: str,
        seq: int,
        source: IngressSource,
        gateway_id: str | None = None,
        now: datetime | None = None,
    ) -> CanonicalIngressDecision:
        if source not in {"direct", "relay"}:
            raise ValueError("canonical ingress source is invalid")
        if source == "direct" and gateway_id is not None:
            raise ValueError("direct ingress cannot carry gateway_id")
        observed_at = now or datetime.now(UTC)
        _timestamp(observed_at)
        try:
            key = validate_replay_tuple(node_id, boot_id, seq)
        except ValueError as error:
            return CanonicalIngressDecision(
                "rejected", node_id, source, str(error), gateway_id, boot_id, seq
            )
        try:
            allowed = self.ingress_allowed(node_id)
        except Exception:
            return CanonicalIngressDecision(
                "rejected", node_id, source, "lifecycle_unavailable", gateway_id, boot_id, seq
            )
        if allowed is not True:
            return CanonicalIngressDecision(
                "rejected", node_id, source, "node_ingress_not_allowed", gateway_id, boot_id, seq
            )

        try:
            with self.replay_registry.transaction() as transaction:
                connection = transaction.connection
                row = connection.execute(
                    "SELECT * FROM n3w_canonical_cursors WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if row is not None:
                    reject = self._cursor_reject(row, key)
                    if reject == "duplicate_node_boot_seq":
                        return CanonicalIngressDecision(
                            "duplicate", node_id, source, reject, gateway_id, boot_id, seq
                        )
                    if reject is not None:
                        return CanonicalIngressDecision(
                            "rejected", node_id, source, reject, gateway_id, boot_id, seq
                        )

                inspection = transaction.inspect(node_id=node_id, boot_id=boot_id, seq=seq)
                if inspection.status == "stale_boot_session":
                    return CanonicalIngressDecision(
                        "rejected", node_id, source, "stale_boot_session", gateway_id, boot_id, seq
                    )
                if inspection.status == "duplicate":
                    self._merge_cursor(
                        connection,
                        node_id=node_id,
                        boot_session=key.boot_session,
                        seq=key.seq,
                        source=source,
                        gateway_id=gateway_id,
                        updated_at=observed_at,
                    )
                    return CanonicalIngressDecision(
                        "duplicate", node_id, source, "duplicate_node_boot_seq", gateway_id, boot_id, seq
                    )

                committed = transaction.commit(node_id=node_id, boot_id=boot_id, seq=seq)
                if committed.status != "accepted":
                    status: CanonicalStatus = (
                        "duplicate" if committed.status == "duplicate" else "rejected"
                    )
                    return CanonicalIngressDecision(
                        status, node_id, source, committed.status, gateway_id, boot_id, seq
                    )
                self._merge_cursor(
                    connection,
                    node_id=node_id,
                    boot_session=key.boot_session,
                    seq=key.seq,
                    source=source,
                    gateway_id=gateway_id,
                    updated_at=observed_at,
                )
                return CanonicalIngressDecision(
                    "accepted", node_id, source, None, gateway_id, boot_id, seq
                )
        except ReplayRegistryUnavailable:
            return CanonicalIngressDecision(
                "rejected", node_id, source, "canonical_cursor_unavailable", gateway_id, boot_id, seq
            )

    def snapshot(self, node_id: str) -> CanonicalCursorSnapshot:
        with self.replay_registry._lock:  # noqa: SLF001 - shared durable state boundary
            self.replay_registry._require_open()  # noqa: SLF001
            row = self.replay_registry._connection.execute(  # noqa: SLF001
                "SELECT * FROM n3w_canonical_cursors WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if row is None:
                raise KeyError(node_id)
            boot_session = _parse_session_hex(row["boot_session_hex"])
            source = row["last_source"]
            if source not in {None, "direct", "relay"}:
                raise ReplayRegistryUnavailable("canonical_cursor_corrupt")
            return CanonicalCursorSnapshot(
                node_id=node_id,
                boot_id=f"boot_{boot_session:016x}",
                boot_session=boot_session,
                seq=row["seq"],
                last_source=source,
                last_gateway_id=row["last_gateway_id"],
                updated_at=_parse_timestamp(row["updated_at"]),
            )

    def audit(self) -> dict[str, int | str | bool]:
        with self.replay_registry._lock:  # noqa: SLF001 - shared durable state boundary
            self.replay_registry._require_open()  # noqa: SLF001
            try:
                connection = self.replay_registry._connection  # noqa: SLF001
                versions = connection.execute(
                    "SELECT schema_version FROM n3w_canonical_meta"
                ).fetchall()
                if len(versions) != 1 or versions[0]["schema_version"] != _SCHEMA_VERSION:
                    raise ReplayRegistryUnavailable("canonical_cursor_schema_mismatch")
                count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM n3w_canonical_cursors"
                    ).fetchone()[0]
                )
                return {
                    "schema": "gh.n3w-canonical-ingress-audit/1",
                    "status": "passed",
                    "cursor_count": count,
                    "path_lease_dependency": False,
                    "candidate_path_state": False,
                }
            except sqlite3.Error as error:
                raise ReplayRegistryUnavailable("canonical_cursor_unavailable") from error
