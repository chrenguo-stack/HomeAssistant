from __future__ import annotations

import sqlite3
import stat
from pathlib import Path
from typing import Any

from cutover_contract import (
    RW_TARGETS,
    CutoverStop,
    plan_isolated_bindings,
    require,
)

REGISTRATION_TABLES = (
    "registrations",
    "pairing_sessions",
    "registration_events",
    "registration_node_history",
    "node_id_leases",
    "retirement_outbox",
)
CREDENTIAL_TABLES = ("credential_assignments",)
REPLAY_TABLES = ("n3w_replay_state", "n3w_replay_seen")
REGISTRATION_DB = "registration.sqlite3"
CREDENTIAL_DB = "credential-lifecycle.sqlite3"
REPLAY_DB = "replay.sqlite3"


def _safe_directory(path: Path) -> None:
    require(path.is_absolute() and path.is_dir() and not path.is_symlink(),
            "FRESH_DIRECTORY_UNSAFE")
    require(stat.S_IMODE(path.stat().st_mode) == 0o700,
            "FRESH_DIRECTORY_MODE_UNSAFE")
    for ancestor in path.parents:
        require(not ancestor.is_symlink(), "FRESH_DIRECTORY_ANCESTOR_SYMLINK")


def validate_fresh_sources(
    old_manager: dict[str, Any],
    sources: dict[str, str],
) -> dict[str, dict[str, Any]]:
    mounts = plan_isolated_bindings(old_manager, sources)
    for dest in RW_TARGETS:
        root = Path(sources[dest])
        _safe_directory(root)
        require(not any(root.iterdir()), "FRESH_ROOT_NOT_EMPTY")
    return mounts


def _zero_table_rows(path: Path, tables: tuple[str, ...]) -> None:
    require(path.is_file() and not path.is_symlink(),
            "FRESH_DB_NOT_INITIALIZED")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only=ON")
        require(connection.execute("PRAGMA quick_check").fetchall() == [("ok",)],
                "FRESH_DB_QUICK_CHECK_FAILED")
        names = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        require(set(tables).issubset(names), "FRESH_DB_SCHEMA_INCOMPLETE")
        for table in tables:
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            require(count == 0, "FRESH_DB_CONTAINS_LEGACY_ROWS")
    finally:
        connection.close()


def validate_initialized_fresh_state(sources: dict[str, str]) -> None:
    require(set(sources) == RW_TARGETS, "FRESH_ROOT_SET_INCOMPLETE")
    roots = {key: Path(val) for key, val in sources.items()}
    for root in roots.values():
        _safe_directory(root)
    _zero_table_rows(
        roots["/var/lib/greenhouse-manager-registration"] / REGISTRATION_DB,
        REGISTRATION_TABLES,
    )
    n3w = roots["/var/lib/greenhouse-manager/n3w"]
    _zero_table_rows(n3w / CREDENTIAL_DB, CREDENTIAL_TABLES)
    _zero_table_rows(n3w / REPLAY_DB, REPLAY_TABLES)
    require(
        not any(roots["/var/lib/greenhouse-manager/n3w/relay-keys"].iterdir()),
        "FRESH_RELAY_KEYS_NOT_EMPTY",
    )


def accept_fresh_identity_baseline(
    observed_registration_rows: int,
    observed_credential_rows: int,
    observed_replay_rows: int,
) -> dict[str, int]:
    require(
        (observed_registration_rows, observed_credential_rows,
         observed_replay_rows) == (0, 0, 0),
        "FRESH_PREBOOT_IDENTITY_BASELINE_MUST_BE_ZERO",
    )
    return {
        "registrations": 0,
        "credential_assignments": 0,
        "replay_seen": 0,
    }
