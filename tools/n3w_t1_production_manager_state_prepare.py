#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import Any

from greenhouse_manager.runtime.n3w_node_application_keys import (
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SCHEMA = "gh.n3w-t1-production-manager-state-prepare/1"

EXPECTED_MANAGER_TABLES = frozenset(
    {
        "credential_assignments",
        "h0h1_legacy_adoption_provenance",
        "node_id_leases",
        "pairing_sessions",
        "registration_events",
        "registration_node_history",
        "registrations",
        "retirement_outbox",
    }
)

BUSINESS_TABLES = (
    "credential_assignments",
    "node_id_leases",
    "pairing_sessions",
    "registration_events",
    "registration_node_history",
    "registrations",
    "retirement_outbox",
)

PROVENANCE_SCHEMA = "gh.h0h1.legacy-adoption-provenance/1"
SYSTEM_ID_FINGERPRINT_LENGTH = 24
REPLAY_NAME = "replay.sqlite3"
RELAY_AUTH_NAME = "relay-authorization.sqlite3"
RELAY_KEY_DIR_NAME = "relay-keys"


class ManagerStatePrepareError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _require_private_directory(path: Path, *, label: str) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_dir()
    ):
        raise ManagerStatePrepareError(f"{label}_invalid")
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise ManagerStatePrepareError(f"{label}_mode_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ManagerStatePrepareError(f"{label}_owner_invalid")


def _require_private_file(path: Path, *, label: str) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_file()
    ):
        raise ManagerStatePrepareError(f"{label}_invalid")
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise ManagerStatePrepareError(f"{label}_mode_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ManagerStatePrepareError(f"{label}_owner_invalid")


def _expected_provenance_fingerprint(
    expected_system_id_sha256: str,
) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_system_id_sha256):
        raise ManagerStatePrepareError("expected_system_id_sha256_invalid")
    return expected_system_id_sha256[:SYSTEM_ID_FINGERPRINT_LENGTH]


def _manager_db_report(
    path: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    _require_private_file(path, label="manager_database")
    uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            raise ManagerStatePrepareError("manager_database_integrity_invalid")

        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }
        if tables != EXPECTED_MANAGER_TABLES:
            raise ManagerStatePrepareError("manager_database_table_set_invalid")

        business_counts = {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
            for table in BUSINESS_TABLES
        }
        if any(business_counts.values()):
            raise ManagerStatePrepareError("manager_database_not_clean")

        provenance = connection.execute(
            """
            SELECT
                schema,
                system_id_fingerprint,
                structured_legacy_manager_state_imported,
                anonymous_nodes_reconstructed
            FROM h0h1_legacy_adoption_provenance
            """
        ).fetchall()
        if len(provenance) != 1:
            raise ManagerStatePrepareError(
                "manager_database_provenance_count_invalid"
            )
        row = provenance[0]
        if row[0] != PROVENANCE_SCHEMA:
            raise ManagerStatePrepareError(
                "manager_database_provenance_schema_invalid"
            )
        expected_fingerprint = _expected_provenance_fingerprint(
            expected_system_id_sha256
        )
        if row[1] != expected_fingerprint:
            raise ManagerStatePrepareError(
                "manager_database_system_identity_binding_invalid"
            )
        if row[2] != 0 or row[3] != 0:
            raise ManagerStatePrepareError(
                "manager_database_legacy_import_flags_invalid"
            )

        return {
            "manager_database_sha256": _sha256_file(path),
            "manager_database_quick_check": "ok",
            "manager_database_table_count": len(tables),
            "manager_database_business_row_count": sum(
                business_counts.values()
            ),
            "manager_database_provenance_count": 1,
            "manager_database_system_identity_bound": True,
            "manager_database_system_id_fingerprint": expected_fingerprint,
        }
    finally:
        connection.close()


def _unexpected_collision(manager_db: Path) -> Path:
    return manager_db.parent / "registration.sqlite3"


def _require_collision_absent(manager_db: Path) -> None:
    collision = _unexpected_collision(manager_db)
    if collision.exists() or collision.is_symlink():
        raise ManagerStatePrepareError(
            "legacy_registration_collision_present"
        )


def _n3w_paths(root: Path) -> tuple[Path, Path, Path]:
    return (
        root / REPLAY_NAME,
        root / RELAY_AUTH_NAME,
        root / RELAY_KEY_DIR_NAME,
    )


def _audit_runtime_state(root: Path) -> dict[str, Any]:
    _require_private_directory(root, label="n3w_state_root")
    replay, relay_auth, relay_keys = _n3w_paths(root)
    _require_private_file(replay, label="replay_database")
    _require_private_file(relay_auth, label="relay_authorization_database")
    _require_private_directory(relay_keys, label="relay_key_directory")

    with ReplayRegistry(replay, read_only=True) as replay_registry:
        replay_report = replay_registry.audit()

    with SqliteNodeApplicationKeyProvider(
        relay_auth,
        relay_keys,
    ) as provider:
        relay_report = provider.audit()

    if replay_report.get("node_count") != 0:
        raise ManagerStatePrepareError("replay_state_not_empty")
    if replay_report.get("replay_tuple_count") != 0:
        raise ManagerStatePrepareError("replay_state_not_empty")
    if relay_report.get("active_node_count") != 0:
        raise ManagerStatePrepareError("relay_authorization_not_empty")

    if any(relay_keys.iterdir()):
        raise ManagerStatePrepareError("relay_key_directory_not_empty")

    return {
        "replay_database_sha256": _sha256_file(replay),
        "replay_node_count": 0,
        "replay_tuple_count": 0,
        "relay_authorization_database_sha256": _sha256_file(relay_auth),
        "relay_active_node_count": 0,
        "relay_key_file_count": 0,
    }


def preflight(
    manager_db: Path,
    n3w_root: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    manager = _manager_db_report(
        manager_db,
        expected_system_id_sha256=expected_system_id_sha256,
    )
    _require_collision_absent(manager_db)
    _require_private_directory(n3w_root, label="n3w_state_root")
    children = sorted(item.name for item in n3w_root.iterdir())
    return {
        **manager,
        "legacy_registration_collision_absent": True,
        "n3w_state_root_empty": not children,
        "n3w_state_existing_children": children,
    }


def prepare(
    manager_db: Path,
    n3w_root: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    before = preflight(
        manager_db,
        n3w_root,
        expected_system_id_sha256=expected_system_id_sha256,
    )
    if not before["n3w_state_root_empty"]:
        raise ManagerStatePrepareError("n3w_state_root_not_empty")

    manager_sha_before = str(before["manager_database_sha256"])
    replay, relay_auth, relay_keys = _n3w_paths(n3w_root)

    previous_umask = os.umask(0o077)
    try:
        with ReplayRegistry(replay):
            pass
        os.chmod(replay, 0o600)

        admin = SqliteNodeApplicationKeyAdmin(
            relay_auth,
            relay_keys,
            node_state=lambda _node_id: None,
        )
        admin.close()
        os.chmod(relay_auth, 0o600)
        os.chmod(relay_keys, 0o700)
    finally:
        os.umask(previous_umask)

    manager_after = _manager_db_report(
        manager_db,
        expected_system_id_sha256=expected_system_id_sha256,
    )
    if manager_after["manager_database_sha256"] != manager_sha_before:
        raise ManagerStatePrepareError("manager_database_mutated")

    runtime = _audit_runtime_state(n3w_root)
    return {
        **manager_after,
        **runtime,
        "legacy_registration_collision_absent": True,
        "n3w_state_prepared": True,
        "manager_database_mutated": False,
    }


def audit(
    manager_db: Path,
    n3w_root: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    manager = _manager_db_report(
        manager_db,
        expected_system_id_sha256=expected_system_id_sha256,
    )
    _require_collision_absent(manager_db)
    runtime = _audit_runtime_state(n3w_root)
    return {
        **manager,
        **runtime,
        "legacy_registration_collision_absent": True,
        "n3w_state_prepared": True,
        "manager_database_mutated": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("preflight", "prepare", "audit"),
        required=True,
    )
    parser.add_argument("--manager-db", type=Path, required=True)
    parser.add_argument("--n3w-root", type=Path, required=True)
    parser.add_argument(
        "--expected-system-id-sha256",
        required=True,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "preflight":
            report = preflight(
                args.manager_db,
                args.n3w_root,
                expected_system_id_sha256=(
                    args.expected_system_id_sha256
                ),
            )
        elif args.phase == "prepare":
            report = prepare(
                args.manager_db,
                args.n3w_root,
                expected_system_id_sha256=(
                    args.expected_system_id_sha256
                ),
            )
        else:
            report = audit(
                args.manager_db,
                args.n3w_root,
                expected_system_id_sha256=(
                    args.expected_system_id_sha256
                ),
            )
    except (
        ManagerStatePrepareError,
        OSError,
        sqlite3.Error,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "phase": args.phase,
                    "status": "STOP",
                    "reason": str(error),
                    "live_service_start": False,
                    "network_operation": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "phase": args.phase,
                "status": "PASS",
                **report,
                "live_service_start": False,
                "network_operation": False,
                "board_access": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
