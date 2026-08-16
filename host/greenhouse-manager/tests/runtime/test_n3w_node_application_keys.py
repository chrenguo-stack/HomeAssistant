import hashlib
import os
import sqlite3

import pytest

from greenhouse_manager.runtime.n3w_node_application_keys import SqliteNodeApplicationKeyProvider
from greenhouse_manager.runtime.n3w_relay_ingress import RelayIngressRejected

NODE_ID = "node_child01"
KEY = bytes(range(32))


def build_store(tmp_path):
    database = tmp_path / "relay.sqlite3"
    key_dir = tmp_path / "keys"
    key_dir.mkdir(mode=0o700)
    os.chmod(key_dir, 0o700)
    key_file = key_dir / "node_child01-1.key"
    key_file.write_bytes(KEY)
    os.chmod(key_file, 0o600)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            INSERT INTO n3w_relay_meta VALUES (2);
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL,
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                state TEXT NOT NULL,
                key_sha256 TEXT NOT NULL,
                PRIMARY KEY (node_id, key_epoch)
            );
            INSERT INTO n3w_relay_nodes VALUES ('node_child01', 1);
            """
        )
        connection.execute(
            """
            INSERT INTO n3w_relay_key_epochs
                (node_id, key_epoch, key_file, enabled, state, key_sha256)
            VALUES (?, 1, ?, 1, 'ACTIVE', ?)
            """,
            (NODE_ID, key_file.name, hashlib.sha256(KEY).hexdigest()),
        )
    os.chmod(database, 0o600)
    return database, key_dir


def test_node_key_resolves_without_gateway_grant(tmp_path) -> None:
    database, key_dir = build_store(tmp_path)
    with SqliteNodeApplicationKeyProvider(database, key_dir) as provider:
        resolved = provider.resolve_key(node_id=NODE_ID, key_epoch=1)
        audit = provider.audit()

    assert resolved == KEY
    assert audit["gateway_grant_dependency"] is False
    assert audit["read_only"] is True


def test_node_key_rejects_inactive_or_wrong_epoch(tmp_path) -> None:
    database, key_dir = build_store(tmp_path)
    with (
        SqliteNodeApplicationKeyProvider(database, key_dir) as provider,
        pytest.raises(RelayIngressRejected, match="key_epoch_rejected"),
    ):
        provider.resolve_key(node_id=NODE_ID, key_epoch=2)
