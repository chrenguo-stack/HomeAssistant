import hashlib
import os
import sqlite3

import pytest

from greenhouse_manager.runtime.n3w_node_application_keys import (
    NodeApplicationKeyStoreUnavailable,
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
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


def _active_node_state(node_id: str) -> str:
    assert node_id == NODE_ID
    return "active"


def build_fresh_admin(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)

    database = root / "node-keys.sqlite3"
    key_dir = root / "keys"

    admin = SqliteNodeApplicationKeyAdmin(
        database,
        key_dir,
        node_state=_active_node_state,
    )

    return admin, database, key_dir


def test_node_key_admin_creates_grant_free_fresh_store(tmp_path) -> None:
    admin, database, key_dir = build_fresh_admin(tmp_path)

    try:
        staged = admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY,
        )

        assert staged["key_epoch"] == 1

        with SqliteNodeApplicationKeyProvider(
            database,
            key_dir,
        ) as provider, pytest.raises(
            RelayIngressRejected,
            match="key_epoch_rejected",
        ):
            provider.resolve_key(
                node_id=NODE_ID,
                key_epoch=1,
            )

        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=1,
        )

        with SqliteNodeApplicationKeyProvider(
            database,
            key_dir,
        ) as provider:
            assert (
                provider.resolve_key(
                    node_id=NODE_ID,
                    key_epoch=1,
                )
                == KEY
            )

        with sqlite3.connect(database) as connection:
            names = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type='table'
                    """
                ).fetchall()
            }

        assert "n3w_relay_gateway_nodes" not in names

        audit = admin.audit()

        assert audit["gateway_grant_dependency"] is False
        assert audit["active_key_epoch_count"] == 1
        assert audit["pending_operation_count"] == 0
    finally:
        admin.close()


def test_node_key_admin_revoke_removes_key_material(tmp_path) -> None:
    admin, database, key_dir = build_fresh_admin(tmp_path)

    try:
        staged = admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY,
        )
        epoch = staged["key_epoch"]

        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=epoch,
        )

        admin.revoke_key(
            node_id=NODE_ID,
            key_epoch=epoch,
        )

        assert list(key_dir.glob("*.key")) == []

        with SqliteNodeApplicationKeyProvider(
            database,
            key_dir,
        ) as provider, pytest.raises(
            RelayIngressRejected,
            match="key_epoch_rejected",
        ):
            provider.resolve_key(
                node_id=NODE_ID,
                key_epoch=epoch,
            )
    finally:
        admin.close()


def test_node_key_admin_rotation_rollback_restores_old_key(tmp_path) -> None:
    admin, database, key_dir = build_fresh_admin(tmp_path)
    replacement = bytes(reversed(range(32)))

    try:
        first = admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY,
        )
        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=first["key_epoch"],
        )

        second = admin.stage_key(
            node_id=NODE_ID,
            key_material=replacement,
        )
        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=second["key_epoch"],
        )

        with SqliteNodeApplicationKeyProvider(
            database,
            key_dir,
        ) as provider:
            assert (
                provider.resolve_key(
                    node_id=NODE_ID,
                    key_epoch=second["key_epoch"],
                )
                == replacement
            )
            assert (
                provider.resolve_key(
                    node_id=NODE_ID,
                    key_epoch=first["key_epoch"],
                )
                == KEY
            )

        admin.rollback_rotation(
            node_id=NODE_ID,
            key_epoch=second["key_epoch"],
        )

        with SqliteNodeApplicationKeyProvider(
            database,
            key_dir,
        ) as provider:
            assert (
                provider.resolve_key(
                    node_id=NODE_ID,
                    key_epoch=first["key_epoch"],
                )
                == KEY
            )
            with pytest.raises(
                RelayIngressRejected,
                match="key_epoch_rejected",
            ):
                provider.resolve_key(
                    node_id=NODE_ID,
                    key_epoch=second["key_epoch"],
                )
    finally:
        admin.close()


def test_node_key_admin_rejects_non_active_registration(tmp_path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)

    with SqliteNodeApplicationKeyAdmin(
        root / "node-keys.sqlite3",
        root / "keys",
        node_state=lambda _node_id: "pending",
    ) as admin, pytest.raises(
        NodeApplicationKeyStoreUnavailable,
        match="node_id_not_active",
    ):
        admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY,
        )


def test_node_key_admin_exposes_required_product_issuer_contract() -> None:
    required = {
        "stage_key",
        "activate_key",
        "revoke_key",
        "rollback_rotation",
    }

    assert required <= set(dir(SqliteNodeApplicationKeyAdmin))
