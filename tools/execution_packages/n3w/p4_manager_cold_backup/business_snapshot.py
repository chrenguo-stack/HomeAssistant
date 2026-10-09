from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import cold_snapshot as snapshot

EXPECTED = {
    "registration": (
        "registrations",
        "pairing_sessions",
        "registration_node_history",
        "registration_events",
        "node_id_leases",
        "retirement_outbox",
    ),
    "n3w/credential-lifecycle": ("credential_assignments",),
    "n3w/replay": (
        "n3w_replay_meta",
        "n3w_replay_state",
        "n3w_replay_seen",
    ),
}


def _rows_and_fingerprint(connection: sqlite3.Connection, table: str) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute('SELECT * FROM "' + table + '"'):
        values = [None if item is None else str(item) for item in row]
        digest.update(json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode())
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def _db_summary(path: Path, required: tuple[str, ...]) -> dict[str, Any]:
    snapshot.require(path.is_file() and not path.is_symlink(), "BUSINESS_DB_MISSING")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2.0)
    try:
        connection.execute("PRAGMA query_only=ON")
        snapshot.require(
            connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
            "BUSINESS_DB_INTEGRITY_FAIL",
        )
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        snapshot.require(
            set(required).issubset(names),
            "BUSINESS_DB_SCHEMA_MISSING",
        )
        result = {}
        for table in required:
            count, digest = _rows_and_fingerprint(connection, table)
            result[table] = {"count": count, "fingerprint": digest}
        if "registrations" in required:
            result["registration_distinct_hardware"] = connection.execute(
                "SELECT COUNT(DISTINCT hardware_id) FROM registrations"
            ).fetchone()[0]
            result["history_distinct_hardware"] = connection.execute(
                "SELECT COUNT(DISTINCT hardware_id) FROM registration_node_history"
            ).fetchone()[0]
            result["all_known_hardware"] = connection.execute(
                "SELECT COUNT(*) FROM ("
                " SELECT hardware_id FROM registrations"
                " UNION SELECT hardware_id FROM registration_node_history"
                " UNION SELECT hardware_id FROM registration_events"
                ")"
            ).fetchone()[0]
        if "credential_assignments" in required:
            result["credential_current"] = connection.execute(
                "SELECT COUNT(*) FROM credential_assignments WHERE state != 'revoked'"
            ).fetchone()[0]
            result["credential_historical"] = connection.execute(
                "SELECT COUNT(DISTINCT hardware_id) FROM credential_assignments"
            ).fetchone()[0]
            result["credential_max_generation"] = connection.execute(
                "SELECT COALESCE(MAX(active_generation), 0) FROM credential_assignments"
            ).fetchone()[0]
        if "n3w_replay_state" in required:
            result["replay_max_boot_session_hex"] = connection.execute(
                "SELECT COALESCE(MAX(highest_session_hex), '') FROM n3w_replay_state"
            ).fetchone()[0]
            result["replay_max_seq"] = connection.execute(
                "SELECT COALESCE(MAX(seq), -1) FROM n3w_replay_seen"
            ).fetchone()[0]
        return result
    finally:
        connection.close()


def read_frozen_semantics(directory: Path) -> dict[str, Any]:
    result = {
        "registration": _db_summary(
            directory / "registration/registration.sqlite3",
            EXPECTED["registration"],
        ),
        "credential": _db_summary(
            directory / "n3w/credential-lifecycle.sqlite3",
            EXPECTED["n3w/credential-lifecycle"],
        ),
        "replay": _db_summary(
            directory / "n3w/replay.sqlite3",
            EXPECTED["n3w/replay"],
        ),
    }
    snapshot.require(
        result["registration"]["all_known_hardware"] >= 5,
        "HISTORICAL_FIVE_IDENTITIES_NOT_ESTABLISHED",
    )
    snapshot.require(
        result["credential"]["credential_historical"] >= 1,
        "CREDENTIAL_HISTORY_EMPTY",
    )
    snapshot.require(
        result["replay"]["n3w_replay_state"]["count"] > 0,
        "REPLAY_STATE_EMPTY",
    )
    return result


def validate_cold_and_isolated(private: Path) -> None:
    cold = private / "cold-snapshot"
    clone = private / "isolated-restoration"
    snapshot.require(cold.is_dir() and clone.is_dir(), "FROZEN_COPIES_MISSING")
    cold_before = snapshot.inventory(cold)
    clone_before = snapshot.inventory(clone)
    snapshot.require(cold_before == clone_before, "FROZEN_CLONE_MISMATCH")
    one = read_frozen_semantics(cold)
    two = read_frozen_semantics(clone)
    snapshot.require(one == two, "FROZEN_BUSINESS_SEMANTICS_MISMATCH")
    snapshot.require(
        snapshot.inventory(cold) == cold_before,
        "FROZEN_ORIGINAL_CHANGED_BY_SEMANTIC_CHECK",
    )
    snapshot.require(
        snapshot.inventory(clone) == clone_before,
        "FROZEN_CLONE_CHANGED_BY_SEMANTIC_CHECK",
    )
    target = private / "p4-business-restore-evidence-private.json"
    snapshot.require(not target.exists() and not target.is_symlink(), "BUSINESS_EVIDENCE_EXISTS")
    target.write_text(
        json.dumps({"schema": "gh.n3w.p4.cold-business-evidence/1", "values": one}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    target.chmod(0o600)
    print("HISTORICAL_IDENTITY_COUNT_MINIMUM_FIVE=PASS")
    print("CREDENTIAL_GENERATIONS_AND_REPLAY_HIGH_WATER_PRESERVED=PASS")
    print("COLD_AND_RESTORED_BUSINESS_STATE=PASS")
