from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from .replay_registry import ReplayRegistry, ReplayRegistryUnavailable, ReplayTuple, validate_replay_tuple

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_SESSION_HEX = re.compile(r"^[0-9a-f]{16}$")
_SCHEMA_VERSION = 1
_EXPECTED_TABLES = {"n3w_path_meta", "n3w_path_leases"}

PathTransport = Literal["direct", "relay"]
PathDecisionStatus = Literal["accepted", "duplicate", "rejected"]


@dataclass(frozen=True, slots=True)
class PathOwner:
    transport: PathTransport
    gateway_id: str | None = None

    def __post_init__(self) -> None:
        if self.transport == "direct":
            if self.gateway_id is not None:
                raise ValueError("direct_gateway_must_be_null")
            return
        if self.transport != "relay":
            raise ValueError("path_transport_invalid")
        if not isinstance(self.gateway_id, str) or _ID.fullmatch(self.gateway_id) is None:
            raise ValueError("gateway_id_invalid")


@dataclass(frozen=True, slots=True)
class PathLeasePolicy:
    stability_window_s: float
    minimum_distinct_frames: int
    lease_ttl_s: float
    old_path_grace_s: float

    def __post_init__(self) -> None:
        if self.stability_window_s < 0:
            raise ValueError("stability_window_s must be non-negative")
        if self.minimum_distinct_frames < 1:
            raise ValueError("minimum_distinct_frames must be positive")
        if self.lease_ttl_s <= 0:
            raise ValueError("lease_ttl_s must be positive")
        if self.old_path_grace_s < 0:
            raise ValueError("old_path_grace_s must be non-negative")


@dataclass(frozen=True, slots=True)
class PathLeaseDecision:
    status: PathDecisionStatus
    node_id: str
    owner: PathOwner
    code: str | None = None
    active_owner: PathOwner | None = None
    switched: bool = False
    candidate_distinct_count: int = 0
    revision: int | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("path_clock_timezone_required")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ReplayRegistryUnavailable("path_state_corrupt")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplayRegistryUnavailable("path_state_corrupt") from exc
    if parsed.tzinfo is None:
        raise ReplayRegistryUnavailable("path_state_corrupt")
    return parsed.astimezone(UTC)


def _session_hex(session: int) -> str:
    return f"{session:016x}"


def _parse_session_hex(value: object) -> int:
    if not isinstance(value, str) or _SESSION_HEX.fullmatch(value) is None:
        raise ReplayRegistryUnavailable("path_state_corrupt")
    session = int(value, 16)
    if session == 0:
        raise ReplayRegistryUnavailable("path_state_corrupt")
    return session


def _row_owner(row: sqlite3.Row, prefix: str) -> PathOwner | None:
    transport = row[f"{prefix}_transport"]
    gateway_id = row[f"{prefix}_gateway_id"]
    if transport is None:
        if gateway_id is not None:
            raise ReplayRegistryUnavailable("path_state_corrupt")
        return None
    try:
        return PathOwner(str(transport), gateway_id)
    except ValueError as exc:
        raise ReplayRegistryUnavailable("path_state_corrupt") from exc


def _tuple_advances(*, boot_session: int, seq: int, prior_boot_id: object, prior_seq: object) -> bool:
    if prior_boot_id is None and prior_seq is None:
        return True
    if not isinstance(prior_boot_id, str) or not isinstance(prior_seq, int):
        raise ReplayRegistryUnavailable("path_state_corrupt")
    prior = validate_replay_tuple("node_tmp", prior_boot_id, prior_seq)
    return boot_session > prior.boot_session or (boot_session == prior.boot_session and seq > prior.seq)


class N3wPathLeaseCoordinator:
    """Persistent host-only Direct/Relay path lease and canonical cursor coordinator.

    Path lease rows live in the same SQLite database and use the same
    ``BEGIN IMMEDIATE`` transaction as ``ReplayRegistry``. Candidate evidence is
    durable but deliberately does not consume replay tuples. Only an already-active
    owner or the frame that atomically completes a path switch can advance replay,
    the canonical sequence cursor, and path ownership.

    The lifecycle eligibility callback is an injected read-only authority, normally
    ``RegistrationRegistry.is_node_id_ingress_allowed``. It is evaluated before the
    replay/path transaction and cannot be replaced by a path lease.
    """

    def __init__(
        self,
        *,
        replay_registry: ReplayRegistry,
        policy: PathLeasePolicy,
        ingress_allowed: Callable[[str], bool],
    ) -> None:
        self.replay_registry = replay_registry
        self.policy = policy
        self.ingress_allowed = ingress_allowed
        self._initialize()

    def _initialize(self) -> None:
        try:
            with self.replay_registry.transaction() as transaction:
                connection = transaction.connection
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS n3w_path_meta (
                        schema_version INTEGER NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS n3w_path_leases (
                        node_id TEXT PRIMARY KEY,
                        active_transport TEXT NOT NULL
                            CHECK (active_transport IN ('direct', 'relay')),
                        active_gateway_id TEXT,
                        lease_expires_at TEXT NOT NULL,
                        candidate_transport TEXT
                            CHECK (candidate_transport IS NULL OR candidate_transport IN ('direct', 'relay')),
                        candidate_gateway_id TEXT,
                        candidate_since TEXT,
                        candidate_last_boot_id TEXT,
                        candidate_last_seq INTEGER,
                        candidate_distinct_count INTEGER NOT NULL DEFAULT 0
                            CHECK (candidate_distinct_count >= 0),
                        previous_transport TEXT
                            CHECK (previous_transport IS NULL OR previous_transport IN ('direct', 'relay')),
                        previous_gateway_id TEXT,
                        old_grace_until TEXT,
                        canonical_boot_session_hex TEXT NOT NULL,
                        canonical_seq INTEGER NOT NULL CHECK (canonical_seq >= 0),
                        last_clock TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision >= 1),
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                versions = connection.execute(
                    "SELECT schema_version FROM n3w_path_meta"
                ).fetchall()
                if not versions:
                    connection.execute(
                        "INSERT INTO n3w_path_meta (schema_version) VALUES (?)",
                        (_SCHEMA_VERSION,),
                    )
            self._require_schema()
            self._require_integrity()
        except ReplayRegistryUnavailable:
            raise
        except sqlite3.Error as exc:
            raise ReplayRegistryUnavailable("path_state_unavailable") from exc

    def _require_schema(self) -> None:
        with self.replay_registry._lock:  # noqa: SLF001 - same-store integrity boundary
            self.replay_registry._require_open()  # noqa: SLF001
            try:
                connection = self.replay_registry._connection  # noqa: SLF001
                rows = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name LIKE 'n3w_path_%'
                    """
                ).fetchall()
                if {row["name"] for row in rows} != _EXPECTED_TABLES:
                    raise ReplayRegistryUnavailable("path_state_schema_mismatch")
                versions = connection.execute(
                    "SELECT schema_version FROM n3w_path_meta"
                ).fetchall()
                if len(versions) != 1 or versions[0]["schema_version"] != _SCHEMA_VERSION:
                    raise ReplayRegistryUnavailable("path_state_schema_mismatch")
            except sqlite3.Error as exc:
                raise ReplayRegistryUnavailable("path_state_unavailable") from exc

    def _require_integrity(self) -> None:
        with self.replay_registry._lock:  # noqa: SLF001 - same-store integrity boundary
            self.replay_registry._require_open()  # noqa: SLF001
            try:
                connection = self.replay_registry._connection  # noqa: SLF001
                row = connection.execute("PRAGMA quick_check").fetchone()
                if row is None or row[0] != "ok":
                    raise ReplayRegistryUnavailable("path_state_corrupt")
            except sqlite3.Error as exc:
                raise ReplayRegistryUnavailable("path_state_unavailable") from exc

    @staticmethod
    def _active_row(connection: sqlite3.Connection, node_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM n3w_path_leases WHERE node_id = ?",
            (node_id,),
        ).fetchone()

    @staticmethod
    def _clear_candidate_values() -> tuple[None, None, None, None, None, int]:
        return (None, None, None, None, None, 0)

    @staticmethod
    def _cursor_reject_code(row: sqlite3.Row, key: ReplayTuple) -> str | None:
        canonical_session = _parse_session_hex(row["canonical_boot_session_hex"])
        canonical_seq = row["canonical_seq"]
        if not isinstance(canonical_seq, int) or isinstance(canonical_seq, bool) or canonical_seq < 0:
            raise ReplayRegistryUnavailable("path_state_corrupt")
        if key.boot_session < canonical_session:
            return "stale_boot_session"
        if key.boot_session == canonical_session and key.seq <= canonical_seq:
            return "stale_sequence"
        return None

    @staticmethod
    def _owner_matches(row: sqlite3.Row, prefix: str, owner: PathOwner) -> bool:
        persisted = _row_owner(row, prefix)
        return persisted == owner

    def _switch_candidate_allowed(
        self,
        *,
        active_owner: PathOwner,
        lease_expires_at: datetime,
        candidate_owner: PathOwner,
        now: datetime,
    ) -> bool:
        if active_owner.transport == "relay" and candidate_owner.transport == "direct":
            return True
        return now > lease_expires_at

    def _candidate_ready(
        self,
        *,
        candidate_since: datetime,
        candidate_distinct_count: int,
        now: datetime,
    ) -> bool:
        return (
            candidate_distinct_count >= self.policy.minimum_distinct_frames
            and now - candidate_since >= timedelta(seconds=self.policy.stability_window_s)
        )

    @staticmethod
    def _decision(
        status: PathDecisionStatus,
        *,
        node_id: str,
        owner: PathOwner,
        code: str | None = None,
        active_owner: PathOwner | None = None,
        switched: bool = False,
        candidate_distinct_count: int = 0,
        revision: int | None = None,
    ) -> PathLeaseDecision:
        return PathLeaseDecision(
            status=status,
            node_id=node_id,
            owner=owner,
            code=code,
            active_owner=active_owner,
            switched=switched,
            candidate_distinct_count=candidate_distinct_count,
            revision=revision,
        )

    def process(
        self,
        *,
        node_id: str,
        boot_id: str,
        seq: int,
        owner: PathOwner,
        now: datetime,
    ) -> PathLeaseDecision:
        try:
            key = validate_replay_tuple(node_id, boot_id, seq)
            observed_at = _utc(now)
        except ValueError as exc:
            return self._decision(
                "rejected",
                node_id=node_id,
                owner=owner,
                code=str(exc),
            )

        try:
            allowed = self.ingress_allowed(node_id)
        except Exception:
            return self._decision(
                "rejected",
                node_id=node_id,
                owner=owner,
                code="lifecycle_unavailable",
            )
        if allowed is not True:
            return self._decision(
                "rejected",
                node_id=node_id,
                owner=owner,
                code="node_ingress_not_allowed",
            )

        try:
            with self.replay_registry.transaction() as transaction:
                connection = transaction.connection
                row = self._active_row(connection, node_id)
                if row is not None:
                    last_clock = _parse_timestamp(row["last_clock"])
                    if observed_at < last_clock:
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code="clock_rollback",
                            active_owner=_row_owner(row, "active"),
                            revision=row["revision"],
                        )

                replay = transaction.inspect(node_id=node_id, boot_id=boot_id, seq=seq)
                if replay.status == "stale_boot_session":
                    return self._decision(
                        "rejected",
                        node_id=node_id,
                        owner=owner,
                        code="stale_boot_session",
                        active_owner=_row_owner(row, "active") if row is not None else None,
                        revision=row["revision"] if row is not None else None,
                    )
                if replay.status == "duplicate":
                    return self._decision(
                        "duplicate",
                        node_id=node_id,
                        owner=owner,
                        code="duplicate_node_boot_seq",
                        active_owner=_row_owner(row, "active") if row is not None else None,
                        revision=row["revision"] if row is not None else None,
                    )

                if row is None:
                    committed = transaction.commit(node_id=node_id, boot_id=boot_id, seq=seq)
                    if committed.status != "accepted":
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code=committed.status,
                        )
                    lease_expires_at = observed_at + timedelta(seconds=self.policy.lease_ttl_s)
                    connection.execute(
                        """
                        INSERT INTO n3w_path_leases (
                            node_id, active_transport, active_gateway_id, lease_expires_at,
                            candidate_transport, candidate_gateway_id, candidate_since,
                            candidate_last_boot_id, candidate_last_seq, candidate_distinct_count,
                            previous_transport, previous_gateway_id, old_grace_until,
                            canonical_boot_session_hex, canonical_seq,
                            last_clock, revision, updated_at
                        ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, 0,
                                  NULL, NULL, NULL, ?, ?, ?, 1, ?)
                        """,
                        (
                            node_id,
                            owner.transport,
                            owner.gateway_id,
                            _timestamp(lease_expires_at),
                            _session_hex(key.boot_session),
                            key.seq,
                            _timestamp(observed_at),
                            _timestamp(observed_at),
                        ),
                    )
                    return self._decision(
                        "accepted",
                        node_id=node_id,
                        owner=owner,
                        active_owner=owner,
                        revision=1,
                    )

                active_owner = _row_owner(row, "active")
                assert active_owner is not None
                revision = row["revision"]
                if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                    raise ReplayRegistryUnavailable("path_state_corrupt")

                cursor_reject = self._cursor_reject_code(row, key)
                if cursor_reject is not None:
                    return self._decision(
                        "rejected",
                        node_id=node_id,
                        owner=owner,
                        code=cursor_reject,
                        active_owner=active_owner,
                        revision=revision,
                    )

                previous_owner = _row_owner(row, "previous")
                if previous_owner == owner and row["old_grace_until"] is not None:
                    grace_until = _parse_timestamp(row["old_grace_until"])
                    if observed_at <= grace_until:
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code="old_path_grace",
                            active_owner=active_owner,
                            revision=revision,
                        )

                if active_owner == owner:
                    committed = transaction.commit(node_id=node_id, boot_id=boot_id, seq=seq)
                    if committed.status == "duplicate":
                        return self._decision(
                            "duplicate",
                            node_id=node_id,
                            owner=owner,
                            code="duplicate_node_boot_seq",
                            active_owner=active_owner,
                            revision=revision,
                        )
                    if committed.status != "accepted":
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code=committed.status,
                            active_owner=active_owner,
                            revision=revision,
                        )

                    candidate_owner = _row_owner(row, "candidate")
                    preserve_direct_candidate = (
                        active_owner.transport == "relay"
                        and candidate_owner is not None
                        and candidate_owner.transport == "direct"
                    )
                    if preserve_direct_candidate:
                        candidate_values = (
                            row["candidate_transport"],
                            row["candidate_gateway_id"],
                            row["candidate_since"],
                            row["candidate_last_boot_id"],
                            row["candidate_last_seq"],
                            row["candidate_distinct_count"],
                        )
                    else:
                        candidate_values = self._clear_candidate_values()
                    new_revision = revision + 1
                    connection.execute(
                        """
                        UPDATE n3w_path_leases
                        SET lease_expires_at = ?,
                            candidate_transport = ?, candidate_gateway_id = ?,
                            candidate_since = ?, candidate_last_boot_id = ?,
                            candidate_last_seq = ?, candidate_distinct_count = ?,
                            canonical_boot_session_hex = ?, canonical_seq = ?,
                            last_clock = ?, revision = ?, updated_at = ?
                        WHERE node_id = ?
                        """,
                        (
                            _timestamp(observed_at + timedelta(seconds=self.policy.lease_ttl_s)),
                            *candidate_values,
                            _session_hex(key.boot_session),
                            key.seq,
                            _timestamp(observed_at),
                            new_revision,
                            _timestamp(observed_at),
                            node_id,
                        ),
                    )
                    return self._decision(
                        "accepted",
                        node_id=node_id,
                        owner=owner,
                        active_owner=owner,
                        revision=new_revision,
                    )

                lease_expires_at = _parse_timestamp(row["lease_expires_at"])
                if not self._switch_candidate_allowed(
                    active_owner=active_owner,
                    lease_expires_at=lease_expires_at,
                    candidate_owner=owner,
                    now=observed_at,
                ):
                    return self._decision(
                        "rejected",
                        node_id=node_id,
                        owner=owner,
                        code="active_path_healthy",
                        active_owner=active_owner,
                        revision=revision,
                    )

                candidate_owner = _row_owner(row, "candidate")
                if candidate_owner != owner:
                    candidate_since = observed_at
                    candidate_count = 1
                else:
                    candidate_since = _parse_timestamp(row["candidate_since"])
                    if not _tuple_advances(
                        boot_session=key.boot_session,
                        seq=key.seq,
                        prior_boot_id=row["candidate_last_boot_id"],
                        prior_seq=row["candidate_last_seq"],
                    ):
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code="candidate_sequence_not_advancing",
                            active_owner=active_owner,
                            candidate_distinct_count=row["candidate_distinct_count"],
                            revision=revision,
                        )
                    candidate_count = row["candidate_distinct_count"] + 1

                if self._candidate_ready(
                    candidate_since=candidate_since,
                    candidate_distinct_count=candidate_count,
                    now=observed_at,
                ):
                    committed = transaction.commit(node_id=node_id, boot_id=boot_id, seq=seq)
                    if committed.status == "duplicate":
                        return self._decision(
                            "duplicate",
                            node_id=node_id,
                            owner=owner,
                            code="duplicate_node_boot_seq",
                            active_owner=active_owner,
                            candidate_distinct_count=candidate_count,
                            revision=revision,
                        )
                    if committed.status != "accepted":
                        return self._decision(
                            "rejected",
                            node_id=node_id,
                            owner=owner,
                            code=committed.status,
                            active_owner=active_owner,
                            candidate_distinct_count=candidate_count,
                            revision=revision,
                        )
                    new_revision = revision + 1
                    connection.execute(
                        """
                        UPDATE n3w_path_leases
                        SET active_transport = ?, active_gateway_id = ?, lease_expires_at = ?,
                            candidate_transport = NULL, candidate_gateway_id = NULL,
                            candidate_since = NULL, candidate_last_boot_id = NULL,
                            candidate_last_seq = NULL, candidate_distinct_count = 0,
                            previous_transport = ?, previous_gateway_id = ?, old_grace_until = ?,
                            canonical_boot_session_hex = ?, canonical_seq = ?,
                            last_clock = ?, revision = ?, updated_at = ?
                        WHERE node_id = ?
                        """,
                        (
                            owner.transport,
                            owner.gateway_id,
                            _timestamp(observed_at + timedelta(seconds=self.policy.lease_ttl_s)),
                            active_owner.transport,
                            active_owner.gateway_id,
                            _timestamp(observed_at + timedelta(seconds=self.policy.old_path_grace_s)),
                            _session_hex(key.boot_session),
                            key.seq,
                            _timestamp(observed_at),
                            new_revision,
                            _timestamp(observed_at),
                            node_id,
                        ),
                    )
                    return self._decision(
                        "accepted",
                        node_id=node_id,
                        owner=owner,
                        active_owner=owner,
                        switched=True,
                        revision=new_revision,
                    )

                new_revision = revision + 1
                connection.execute(
                    """
                    UPDATE n3w_path_leases
                    SET candidate_transport = ?, candidate_gateway_id = ?,
                        candidate_since = ?, candidate_last_boot_id = ?,
                        candidate_last_seq = ?, candidate_distinct_count = ?,
                        last_clock = ?, revision = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        owner.transport,
                        owner.gateway_id,
                        _timestamp(candidate_since),
                        boot_id,
                        seq,
                        candidate_count,
                        _timestamp(observed_at),
                        new_revision,
                        _timestamp(observed_at),
                        node_id,
                    ),
                )
                return self._decision(
                    "rejected",
                    node_id=node_id,
                    owner=owner,
                    code="path_candidate_pending",
                    active_owner=active_owner,
                    candidate_distinct_count=candidate_count,
                    revision=new_revision,
                )
        except ReplayRegistryUnavailable as exc:
            return self._decision(
                "rejected",
                node_id=node_id,
                owner=owner,
                code=(
                    str(exc)
                    if str(exc).startswith("path_state_")
                    else "replay_registry_unavailable"
                ),
            )
        except sqlite3.Error:
            return self._decision(
                "rejected",
                node_id=node_id,
                owner=owner,
                code="path_state_unavailable",
            )

    def audit(self) -> dict[str, int | str | bool]:
        self._require_schema()
        self._require_integrity()
        with self.replay_registry._lock:  # noqa: SLF001 - same-store read-only audit
            self.replay_registry._require_open()  # noqa: SLF001
            try:
                rows = self.replay_registry._connection.execute(  # noqa: SLF001
                    "SELECT * FROM n3w_path_leases"
                ).fetchall()
                candidate_count = 0
                for row in rows:
                    node_id = row["node_id"]
                    if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
                        raise ReplayRegistryUnavailable("path_state_corrupt")
                    active = _row_owner(row, "active")
                    if active is None:
                        raise ReplayRegistryUnavailable("path_state_corrupt")
                    candidate = _row_owner(row, "candidate")
                    previous = _row_owner(row, "previous")
                    if candidate is not None:
                        candidate_count += 1
                        _parse_timestamp(row["candidate_since"])
                        validate_replay_tuple(
                            node_id,
                            row["candidate_last_boot_id"],
                            row["candidate_last_seq"],
                        )
                    if previous is not None and row["old_grace_until"] is None:
                        raise ReplayRegistryUnavailable("path_state_corrupt")
                    _parse_timestamp(row["lease_expires_at"])
                    _parse_timestamp(row["last_clock"])
                    _parse_timestamp(row["updated_at"])
                    _parse_session_hex(row["canonical_boot_session_hex"])
                    if not isinstance(row["canonical_seq"], int) or row["canonical_seq"] < 0:
                        raise ReplayRegistryUnavailable("path_state_corrupt")
                return {
                    "schema": "gh.n3w-path-lease-audit/1",
                    "status": "passed",
                    "schema_version": _SCHEMA_VERSION,
                    "node_count": len(rows),
                    "candidate_node_count": candidate_count,
                    "mutated": False,
                }
            except (sqlite3.Error, TypeError, ValueError) as exc:
                raise ReplayRegistryUnavailable("path_state_unavailable") from exc
