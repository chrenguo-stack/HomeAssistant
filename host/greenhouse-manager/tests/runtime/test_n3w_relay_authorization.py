from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from greenhouse_manager.runtime.n3w_relay_authorization import (
    RelayAuthorizationStoreUnavailable,
    SqliteRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.n3w_relay_ingress import RelayIngressRejected

NODE_ID = "node_01hzx7aq5fj3"
GATEWAY_ID = "gateway_01hzx7aq5fj3"
OTHER_GATEWAY_ID = "gateway_01hzx7aq5fj4"
KEY_FILE = "node_01hzx7aq5fj3-epoch-1.key"
KEY = bytes(range(32))


def create_store(tmp_path: Path) -> tuple[Path, Path]:
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    os.chmod(key_dir, 0o700)
    key_path = key_dir / KEY_FILE
    key_path.write_bytes(KEY)
    os.chmod(key_path, 0o600)

    database = tmp_path / "relay-authorization.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (
                schema_version INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (gateway_id, node_id)
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL,
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (node_id, key_epoch)
            );
            """
        )
        connection.execute("INSERT INTO n3w_relay_meta VALUES (1)")
        connection.execute(
            "INSERT INTO n3w_relay_nodes VALUES (?, 1)",
            (NODE_ID,),
        )
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes VALUES (?, ?, 1)",
            (GATEWAY_ID, NODE_ID),
        )
        connection.execute(
            "INSERT INTO n3w_relay_key_epochs VALUES (?, 1, ?, 1)",
            (NODE_ID, KEY_FILE),
        )
    os.chmod(database, 0o600)
    return database, key_dir


def test_resolve_key_and_audit_are_secret_free(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)

    with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
        key = provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )
        audit = provider.audit()

    assert key == KEY
    assert audit == {
        "schema": "gh.n3w-relay-authorization-audit/1",
        "status": "passed",
        "schema_version": 1,
        "node_count": 1,
        "active_node_count": 1,
        "enabled_gateway_grant_count": 1,
        "enabled_key_epoch_count": 1,
        "secret_values_included": False,
        "mutated": False,
    }
    assert KEY.hex() not in json.dumps(audit)
    assert KEY_FILE not in json.dumps(audit)


def test_inactive_node_is_rejected(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE n3w_relay_nodes SET active = 0 WHERE node_id = ?",
            (NODE_ID,),
        )

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="node_not_active"),
    ):
        provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )


def test_unauthorized_gateway_is_rejected(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"),
    ):
        provider.resolve_key(
            gateway_id=OTHER_GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )


def test_unknown_or_disabled_epoch_is_rejected(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="key_epoch_rejected"),
    ):
        provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=2,
        )


def test_key_material_must_be_private_regular_and_32_bytes(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)
    key_path = key_dir / KEY_FILE
    key_path.write_bytes(b"too-short")

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="key_material_invalid"),
    ):
        provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )

    key_path.write_bytes(KEY)
    os.chmod(key_path, 0o644)
    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="key_file_permissions_invalid"),
    ):
        provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )


def test_key_file_reference_cannot_escape_private_directory(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE n3w_relay_key_epochs SET key_file = '../outside.key'")

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="key_file_reference_invalid"),
    ):
        provider.resolve_key(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            key_epoch=1,
        )


def test_store_and_key_directory_permissions_fail_closed(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)
    os.chmod(database, 0o644)
    with pytest.raises(
        RelayAuthorizationStoreUnavailable,
        match="authorization_store_permissions_invalid",
    ):
        SqliteRelayAuthorizationProvider(database, key_dir)

    os.chmod(database, 0o600)
    os.chmod(key_dir, 0o755)
    with pytest.raises(
        RelayAuthorizationStoreUnavailable,
        match="key_directory_permissions_invalid",
    ):
        SqliteRelayAuthorizationProvider(database, key_dir)


def test_read_only_provider_cannot_mutate_database(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(sqlite3.OperationalError),
    ):
        provider._connection.execute(  # noqa: SLF001 - prove read-only boundary
            "UPDATE n3w_relay_nodes SET active = 0"
        )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT active FROM n3w_relay_nodes WHERE node_id = ?",
            (NODE_ID,),
        ).fetchone()
    assert row == (1,)


def test_missing_or_wrong_schema_fails_without_creating_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    os.chmod(key_dir, 0o700)

    with pytest.raises(RelayAuthorizationStoreUnavailable):
        SqliteRelayAuthorizationProvider(missing, key_dir)
    assert not missing.exists()

    wrong = tmp_path / "wrong.sqlite3"
    with sqlite3.connect(wrong) as connection:
        connection.execute("CREATE TABLE unrelated (value INTEGER)")
    os.chmod(wrong, 0o600)
    with pytest.raises(
        RelayAuthorizationStoreUnavailable,
        match="authorization_store_schema_mismatch",
    ):
        SqliteRelayAuthorizationProvider(wrong, key_dir)


def test_audit_detects_invalid_metadata_without_returning_secret(tmp_path: Path) -> None:
    database, key_dir = create_store(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE n3w_relay_gateway_nodes SET node_id = 'INVALID NODE'")

    with (
        SqliteRelayAuthorizationProvider(database, key_dir) as provider,
        pytest.raises(
            RelayAuthorizationStoreUnavailable,
            match="authorization_store_corrupt",
        ),
    ):
        provider.audit()
