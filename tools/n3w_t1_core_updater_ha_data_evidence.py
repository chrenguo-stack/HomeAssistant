from __future__ import annotations

import math
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error, canonical, sha256_bytes


MANAGER_PAIRING_DB = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
_HISTORY_QUERY = """
    SELECT m.entity_id, s.last_updated_ts, s.state
    FROM states AS s JOIN states_meta AS m ON m.metadata_id = s.metadata_id
"""
_PAIRING_QUERY = """
    SELECT r.node_id, r.current_pairing_id, r.pairing_epoch
    FROM registrations AS r JOIN pairing_sessions AS p ON p.pairing_id = r.current_pairing_id
    WHERE r.retired_at IS NULL AND r.node_id IS NOT NULL AND p.state = 'approved'
"""


def _valid_selector(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 255 and value.isprintable()


def _valid_timestamp(value: Any) -> bool:
    return type(value) in {int, float} and 0 < value < 10**11 and math.isfinite(value)


def valid_data_sample(sample: Any) -> bool:
    if not isinstance(sample, dict) or set(sample) != {"history", "pairing"}:
        return False
    history, pairing = sample["history"], sample["pairing"]
    return (
        (history is None or (
            isinstance(history, dict) and set(history) == {"entity", "at", "sha256"}
            and _valid_selector(history["entity"]) and _valid_timestamp(history["at"])
            and isinstance(history["sha256"], str) and SHA256.fullmatch(history["sha256"])
        ))
        and (pairing is None or (
            isinstance(pairing, dict) and set(pairing) == {"node", "sha256"}
            and _valid_selector(pairing["node"])
            and isinstance(pairing["sha256"], str) and SHA256.fullmatch(pairing["sha256"])
        ))
    )


@contextmanager
def read_local_database(path: Path) -> Iterator[sqlite3.Connection]:
    if any(parent.is_symlink() for parent in path.parents) or not stat.S_ISREG(path.lstat().st_mode):
        raise UpdaterV2Error("ha_usb_data_evidence_database_invalid")
    with path.open("rb") as stream:
        header = stream.read(20)
    if (
        len(header) != 20 or not header.startswith(b"SQLite format 3\0")
        or header[18:20] not in (b"\1\1", b"\2\2")
    ):
        raise UpdaterV2Error("ha_usb_data_evidence_database_invalid")
    wal = header[18:20] == b"\2\2"
    for suffix in ("-wal", "-shm", "-journal"):
        sibling = path.with_name(path.name + suffix)
        required = wal and suffix != "-journal"
        if sibling.is_symlink() or (
            (sibling.exists() or required) and not stat.S_ISREG(sibling.lstat().st_mode)
        ):
            raise UpdaterV2Error("ha_usb_data_evidence_sidecar_invalid")
    # Read the active database and its WAL. Immutable mode can hide recent commits.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
        connection.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + 2
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1_000)
        yield connection


class HaProtectedDataEvidence:
    """Read representative history and active pairing from the bound local databases."""

    def __init__(self, history: Path, pairing: Path = MANAGER_PAIRING_DB) -> None:
        self.history = history
        self.pairing = pairing

    def capture(self) -> dict[str, Any]:
        with read_local_database(self.history) as connection:
            history = connection.execute(
                _HISTORY_QUERY + " WHERE s.last_updated_ts > 0 ORDER BY s.state_id DESC LIMIT 1"
            ).fetchone()
            if history is None and connection.execute(
                "SELECT 1 FROM states WHERE last_updated_ts > 0 LIMIT 1"
            ).fetchone() is not None:
                raise UpdaterV2Error("ha_usb_data_evidence_history_identity_unavailable")
        with read_local_database(self.pairing) as connection:
            pairing = connection.execute(_PAIRING_QUERY + " ORDER BY r.node_id LIMIT 1").fetchone()
        sample = {
            "history": None if history is None else {
                "entity": history[0], "at": history[1], "sha256": sha256_bytes(canonical(history)),
            },
            "pairing": None if pairing is None else {
                "node": pairing[0], "sha256": sha256_bytes(canonical(pairing)),
            },
        }
        if not valid_data_sample(sample):
            raise UpdaterV2Error("ha_usb_data_evidence_sample_invalid")
        return sample

    def compare(self, sample: dict[str, Any]) -> str:
        if not valid_data_sample(sample):
            raise UpdaterV2Error("ha_usb_data_evidence_sample_invalid")
        history, pairing = sample["history"], sample["pairing"]
        try:
            with read_local_database(self.history) as connection:
                if history is None:
                    connection.execute(_HISTORY_QUERY + " LIMIT 1").fetchone()
                    history_matches = True
                else:
                    rows = connection.execute(
                        _HISTORY_QUERY + " WHERE m.entity_id = ? AND s.last_updated_ts = ? LIMIT 16",
                        (history["entity"], history["at"]),
                    ).fetchall()
                    history_matches = any(sha256_bytes(canonical(row)) == history["sha256"] for row in rows)
            with read_local_database(self.pairing) as connection:
                if pairing is None:
                    connection.execute(_PAIRING_QUERY + " LIMIT 1").fetchone()
                else:
                    row = connection.execute(_PAIRING_QUERY + " AND r.node_id = ?", (pairing["node"],)).fetchone()
                    if row is None or sha256_bytes(canonical(row)) != pairing["sha256"]:
                        return "PROVEN_FAIL"
        except (OSError, sqlite3.Error, UpdaterV2Error):
            return "EVIDENCE_UNAVAILABLE"
        # Retention or a changed history layout can remove the reference row without proving data loss.
        return "PASS" if history_matches else "EVIDENCE_UNAVAILABLE"
