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

from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.n3w_node_application_keys import (
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SCHEMA = "gh.n3w-t1-fresh-product-state/1"

EXPECTED_MANAGER_TABLES = frozenset(
    {
        "credential_assignments",
        "node_id_leases",
        "pairing_sessions",
        "registration_events",
        "registration_node_history",
        "registrations",
        "retirement_outbox",
    }
)
BUSINESS_TABLES = tuple(sorted(EXPECTED_MANAGER_TABLES))
MANAGER_DATABASE_NAME = "manager-state.sqlite3"
REPLAY_NAME = "replay.sqlite3"
RELAY_AUTH_NAME = "relay-authorization.sqlite3"
RELAY_KEY_DIR_NAME = "relay-keys"


class FreshProductStateError(RuntimeError):
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


def _require_system_id_sha256(value: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise FreshProductStateError("system_id_sha256_invalid")


def _require_private_directory(path: Path, *, label: str) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_dir()
    ):
        raise FreshProductStateError(f"{label}_invalid")
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise FreshProductStateError(f"{label}_mode_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise FreshProductStateError(f"{label}_owner_invalid")


def _require_private_file(path: Path, *, label: str) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_file()
    ):
        raise FreshProductStateError(f"{label}_invalid")
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise FreshProductStateError(f"{label}_mode_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise FreshProductStateError(f"{label}_owner_invalid")


def _manager_report(manager_root: Path) -> dict[str, Any]:
    manager_db = manager_root / MANAGER_DATABASE_NAME
    _require_private_file(manager_db, label="manager_database")
    uri = f"{manager_db.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            raise FreshProductStateError("manager_database_integrity_invalid")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if tables != EXPECTED_MANAGER_TABLES:
            raise FreshProductStateError("manager_database_table_set_invalid")
        row_counts = {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
            for table in BUSINESS_TABLES
        }
        if any(row_counts.values()):
            raise FreshProductStateError("manager_database_not_clean")
        if "h0h1_legacy_adoption_provenance" in tables:
            raise FreshProductStateError("legacy_provenance_present")
        return {
            "manager_database_sha256": _sha256_file(manager_db),
            "manager_database_quick_check": "ok",
            "manager_table_count": len(tables),
            "manager_business_row_count": 0,
            "legacy_provenance_present": False,
        }
    finally:
        connection.close()


def _runtime_report(n3w_root: Path) -> dict[str, Any]:
    replay = n3w_root / REPLAY_NAME
    relay_auth = n3w_root / RELAY_AUTH_NAME
    relay_keys = n3w_root / RELAY_KEY_DIR_NAME
    _require_private_file(replay, label="replay_database")
    _require_private_file(relay_auth, label="relay_authorization_database")
    _require_private_directory(relay_keys, label="relay_key_directory")

    with ReplayRegistry(replay, read_only=True) as replay_registry:
        replay_report = replay_registry.audit()
    with SqliteNodeApplicationKeyProvider(relay_auth, relay_keys) as provider:
        relay_report = provider.audit()

    if replay_report.get("node_count") != 0:
        raise FreshProductStateError("replay_state_not_empty")
    if replay_report.get("replay_tuple_count") != 0:
        raise FreshProductStateError("replay_state_not_empty")
    if relay_report.get("active_node_count") != 0:
        raise FreshProductStateError("relay_authorization_not_empty")
    if any(relay_keys.iterdir()):
        raise FreshProductStateError("relay_key_directory_not_empty")

    return {
        "replay_database_sha256": _sha256_file(replay),
        "replay_node_count": 0,
        "replay_tuple_count": 0,
        "relay_authorization_database_sha256": _sha256_file(relay_auth),
        "relay_active_node_count": 0,
        "relay_key_file_count": 0,
    }


def create_fresh_state(
    manager_root: Path,
    n3w_root: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    _require_system_id_sha256(expected_system_id_sha256)
    _require_private_directory(manager_root, label="manager_root")
    _require_private_directory(n3w_root, label="n3w_root")

    if any(manager_root.iterdir()):
        raise FreshProductStateError("manager_root_not_empty")
    if any(n3w_root.iterdir()):
        raise FreshProductStateError("n3w_root_not_empty")

    manager_db = manager_root / MANAGER_DATABASE_NAME
    with RegistrationRegistry(manager_db):
        pass
    with CredentialLifecycleStore(manager_db):
        pass
    os.chmod(manager_db, 0o600)

    replay = n3w_root / REPLAY_NAME
    relay_auth = n3w_root / RELAY_AUTH_NAME
    relay_keys = n3w_root / RELAY_KEY_DIR_NAME

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

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "create",
        "system_id_sha256": expected_system_id_sha256,
        "identity_binding_mode": "external_exact_sha256",
        **_manager_report(manager_root),
        **_runtime_report(n3w_root),
        "fresh_product_state": True,
        "legacy_state_imported": False,
        "node_credential_count": 0,
        "production_service_start": False,
        "network_operation": False,
        "board_access": False,
    }


def audit_fresh_state(
    manager_root: Path,
    n3w_root: Path,
    *,
    expected_system_id_sha256: str,
) -> dict[str, Any]:
    _require_system_id_sha256(expected_system_id_sha256)
    _require_private_directory(manager_root, label="manager_root")
    _require_private_directory(n3w_root, label="n3w_root")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "audit",
        "system_id_sha256": expected_system_id_sha256,
        "identity_binding_mode": "external_exact_sha256",
        **_manager_report(manager_root),
        **_runtime_report(n3w_root),
        "fresh_product_state": True,
        "legacy_state_imported": False,
        "node_credential_count": 0,
        "production_service_start": False,
        "network_operation": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("create", "audit"), required=True)
    parser.add_argument("--manager-root", type=Path, required=True)
    parser.add_argument("--n3w-root", type=Path, required=True)
    parser.add_argument("--expected-system-id-sha256", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "create":
            report = create_fresh_state(
                args.manager_root,
                args.n3w_root,
                expected_system_id_sha256=args.expected_system_id_sha256,
            )
        else:
            report = audit_fresh_state(
                args.manager_root,
                args.n3w_root,
                expected_system_id_sha256=args.expected_system_id_sha256,
            )
    except (
        FreshProductStateError,
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
                    "production_service_start": False,
                    "network_operation": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
