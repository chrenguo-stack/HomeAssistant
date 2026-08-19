from __future__ import annotations

import re
import secrets
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .n3w_long_lived_peer_trust import SystemPeerCredential

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_SYSTEM_PEER_KEY_BYTES = 32


class PeerTrustStoreConflict(RuntimeError):
    """Raised when persistent system peer-trust state is invalid or unavailable."""


@dataclass(frozen=True, slots=True)
class PeerTrustSnapshot:
    """Secret-free status for one system peer-trust credential."""

    system_id: str
    generation: int
    created_at: datetime
    updated_at: datetime


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class SystemPeerTrustStore:
    """Canonical persistent SYSTEM_PEER_KEY store for ADR-0007.

    Normal registration reads one stable per-system credential. Rotation is an
    explicit security operation; ordinary reboot, Wi-Fi loss, Relay switching or
    adding a node never changes the key or generation.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self.random_bytes = random_bytes
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                str(path), isolation_level="IMMEDIATE", check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._initialize()
        except sqlite3.Error as error:
            raise PeerTrustStoreConflict("system peer trust store unavailable") from error

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS n3w_system_peer_trust (
                    system_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL CHECK (generation >= 1),
                    key_material BLOB NOT NULL CHECK (length(key_material) = 32),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SystemPeerTrustStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_or_create(
        self,
        system_id: str,
        *,
        now: datetime | None = None,
    ) -> SystemPeerCredential:
        self._validate_system_id(system_id)
        observed_at = now or datetime.now(UTC)
        stamp = _timestamp(observed_at)
        with self._lock, self._connection:
            row = self._row(system_id)
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO n3w_system_peer_trust (
                        system_id, generation, key_material, created_at, updated_at
                    ) VALUES (?, 1, ?, ?, ?)
                    """,
                    (system_id, self._new_key(), stamp, stamp),
                )
                row = self._row(system_id)
            assert row is not None
            return self._credential(row)

    def get(self, system_id: str) -> SystemPeerCredential:
        self._validate_system_id(system_id)
        with self._lock:
            row = self._row(system_id)
            if row is None:
                raise KeyError(system_id)
            return self._credential(row)

    def snapshot(self, system_id: str) -> PeerTrustSnapshot:
        self._validate_system_id(system_id)
        with self._lock:
            row = self._row(system_id)
            if row is None:
                raise KeyError(system_id)
            return self._snapshot(row)

    def rotate(
        self,
        system_id: str,
        *,
        now: datetime | None = None,
    ) -> SystemPeerCredential:
        """Rotate only for an explicit compromise/revocation security event."""

        self._validate_system_id(system_id)
        stamp = _timestamp(now or datetime.now(UTC))
        with self._lock, self._connection:
            row = self._row(system_id)
            if row is None:
                raise PeerTrustStoreConflict("system peer trust is not initialized")
            generation = row["generation"]
            if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
                raise PeerTrustStoreConflict("system peer trust generation is corrupt")
            self._connection.execute(
                """
                UPDATE n3w_system_peer_trust
                SET generation = ?, key_material = ?, updated_at = ?
                WHERE system_id = ?
                """,
                (generation + 1, self._new_key(), stamp, system_id),
            )
            updated = self._row(system_id)
            assert updated is not None
            return self._credential(updated)

    def audit(self) -> dict[str, int | str | bool]:
        """Return secret-free store health metadata."""

        with self._lock:
            try:
                check = self._connection.execute("PRAGMA quick_check").fetchone()
                if check is None or check[0] != "ok":
                    raise PeerTrustStoreConflict("system peer trust store corrupt")
                count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM n3w_system_peer_trust"
                    ).fetchone()[0]
                )
                return {
                    "schema": "gh.n3w-system-peer-trust-audit/1",
                    "status": "passed",
                    "system_count": count,
                    "secret_values_included": False,
                    "normal_get_rotates": False,
                }
            except sqlite3.Error as error:
                raise PeerTrustStoreConflict("system peer trust store unavailable") from error

    def _row(self, system_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT system_id, generation, key_material, created_at, updated_at
            FROM n3w_system_peer_trust
            WHERE system_id = ?
            """,
            (system_id,),
        ).fetchone()

    def _credential(self, row: sqlite3.Row) -> SystemPeerCredential:
        key_material = row["key_material"]
        if not isinstance(key_material, bytes) or len(key_material) != _SYSTEM_PEER_KEY_BYTES:
            raise PeerTrustStoreConflict("system peer key is corrupt")
        try:
            return SystemPeerCredential(
                system_id=row["system_id"],
                generation=row["generation"],
                key=key_material,
            )
        except (TypeError, ValueError) as error:
            raise PeerTrustStoreConflict("system peer trust record is corrupt") from error

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> PeerTrustSnapshot:
        try:
            return PeerTrustSnapshot(
                system_id=row["system_id"],
                generation=row["generation"],
                created_at=_parse_timestamp(row["created_at"]),
                updated_at=_parse_timestamp(row["updated_at"]),
            )
        except (TypeError, ValueError) as error:
            raise PeerTrustStoreConflict("system peer trust metadata is corrupt") from error

    def _new_key(self) -> bytes:
        value = self.random_bytes(_SYSTEM_PEER_KEY_BYTES)
        if not isinstance(value, bytes) or len(value) != _SYSTEM_PEER_KEY_BYTES:
            raise PeerTrustStoreConflict("system peer key generator returned invalid length")
        if not any(value):
            raise PeerTrustStoreConflict("system peer key generator returned all-zero key")
        return value

    @staticmethod
    def _validate_system_id(system_id: str) -> None:
        if not isinstance(system_id, str) or _ID.fullmatch(system_id) is None:
            raise ValueError("system_id is invalid")
