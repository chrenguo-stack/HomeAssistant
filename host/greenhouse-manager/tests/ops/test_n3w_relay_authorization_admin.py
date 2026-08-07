from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.ops.n3w_relay_authorization_admin import (
    RelayAuthorizationAdmin,
    RelayAuthorizationAdminError,
    ReplayPathLeaseInvalidator,
)
from greenhouse_manager.runtime.n3w_path_lease import N3wPathLeaseCoordinator, PathLeasePolicy, PathOwner
from greenhouse_manager.runtime.n3w_relay_authorization import (
    REVOKED_GATEWAY_SENTINEL,
    SqliteRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.n3w_relay_ingress import RelayIngressRejected
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

NODE_ID = "node_01hzx7aq5fj3"
GATEWAY_A = "gateway_01hzx7aq5fj3"
KEY_A = bytes(range(32))
KEY_B = bytes(reversed(range(32)))
BOOT_ID = "boot_0000000000000001"
NOW = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)


def admin_paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "relay-auth.sqlite3", tmp_path / "keys"


def active(_node_id: str) -> str:
    return "active"


def make_v1_store(tmp_path: Path) -> tuple[Path, Path]:
    database, key_dir = admin_paths(tmp_path)
    key_dir.mkdir(mode=0o700)
    key_file = key_dir / f"{NODE_ID}-epoch-1.key"
    key_file.write_bytes(KEY_A)
    os.chmod(key_file, 0o600)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            CREATE TABLE n3w_relay_nodes (node_id TEXT PRIMARY KEY, active INTEGER NOT NULL);
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (gateway_id,node_id)
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL,
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (node_id,key_epoch)
            );
            """
        )
        connection.execute("INSERT INTO n3w_relay_meta VALUES (1)")
        connection.execute("INSERT INTO n3w_relay_nodes VALUES (?,1)", (NODE_ID,))
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes VALUES (?,?,1)",
            (GATEWAY_A, NODE_ID),
        )
        connection.execute(
            "INSERT INTO n3w_relay_key_epochs VALUES (?,1,?,1)",
            (NODE_ID, key_file.name),
        )
    os.chmod(database, 0o600)
    return database, key_dir


def test_blank_store_initializes_v2_and_audit_is_secret_free(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        audit = admin.audit()
    assert audit == {
        "schema": "gh.n3w-relay-authorization-admin-audit/1",
        "status": "passed",
        "schema_version": 2,
        "enabled_gateway_grant_count": 0,
        "staged_key_epoch_count": 0,
        "active_key_epoch_count": 0,
        "grace_key_epoch_count": 0,
        "revoked_key_epoch_count": 0,
        "pending_operation_count": 0,
        "secret_values_included": False,
        "mutated": False,
    }
    assert database.stat().st_mode & 0o077 == 0
    assert key_dir.stat().st_mode & 0o077 == 0


def test_v1_store_migrates_without_breaking_existing_active_key(tmp_path: Path) -> None:
    database, key_dir = make_v1_store(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        assert admin.audit()["active_key_epoch_count"] == 1
    with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
        assert provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1) == KEY_A
        assert provider.audit()["schema_version"] == 2


@pytest.mark.parametrize("state", [None, "retiring", "retired"])
def test_new_authorization_and_key_stage_require_explicit_active_node(
    tmp_path: Path, state: str | None
) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=lambda _node: state) as admin:
        with pytest.raises(RelayAuthorizationAdminError, match="node_id_not_active"):
            admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
        with pytest.raises(RelayAuthorizationAdminError, match="node_id_not_active"):
            admin.stage_key(node_id=NODE_ID, key_material=KEY_A)


def test_staged_active_grace_rollback_and_epoch_non_reuse(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
        first = admin.stage_key(node_id=NODE_ID, key_material=KEY_A)
        assert first["key_epoch"] == 1
        with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
            with pytest.raises(RelayIngressRejected, match="key_epoch_rejected"):
                provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1)

        admin.activate_key(node_id=NODE_ID, key_epoch=1)
        second = admin.stage_key(node_id=NODE_ID, key_material=KEY_B)
        assert second["key_epoch"] == 2
        admin.activate_key(node_id=NODE_ID, key_epoch=2)
        with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
            assert provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1) == KEY_A
            assert provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=2) == KEY_B

        admin.rollback_rotation(node_id=NODE_ID, key_epoch=2)
        with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
            assert provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1) == KEY_A
            with pytest.raises(RelayIngressRejected, match="key_epoch_rejected"):
                provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=2)

        third = admin.stage_key(node_id=NODE_ID, key_material=KEY_B)
        assert third["key_epoch"] == 3
        admin.activate_key(node_id=NODE_ID, key_epoch=3)
        admin.revoke_key(node_id=NODE_ID, key_epoch=1)
        audit = admin.audit()
        assert audit["active_key_epoch_count"] == 1
        assert audit["grace_key_epoch_count"] == 0
        assert audit["revoked_key_epoch_count"] == 2

    assert not (key_dir / f"{NODE_ID}-epoch-1.key").exists()
    assert not (key_dir / f"{NODE_ID}-epoch-2.key").exists()


def test_interrupted_stage_recovers_fail_closed_and_never_reuses_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        with monkeypatch.context() as patch:
            patch.setattr(admin, "_write_key", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
            with pytest.raises(RelayAuthorizationAdminError, match="key_file_write_failed"):
                admin.stage_key(node_id=NODE_ID, key_material=KEY_A)
        assert admin.audit()["pending_operation_count"] == 1
        recovery = admin.recover()
        assert recovery["recovered_operation_count"] == 1
        assert admin.audit()["revoked_key_epoch_count"] == 1
        assert admin.stage_key(node_id=NODE_ID, key_material=KEY_B)["key_epoch"] == 2


def test_revoke_disables_authorization_before_retryable_path_cleanup(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=admin.stage_key(node_id=NODE_ID, key_material=KEY_A)["key_epoch"],
        )
        result = admin.revoke_grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
        assert result["recovery_pending"] is True
        with pytest.raises(RelayAuthorizationAdminError, match="grant_recovery_pending"):
            admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)

    with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
        with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
            provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1)


def test_revoke_invalidates_active_relay_owner_preserves_cursor_and_requires_fresh_stability(
    tmp_path: Path,
) -> None:
    auth_db, key_dir = admin_paths(tmp_path)
    replay_db = tmp_path / "replay.sqlite3"
    replay = ReplayRegistry(replay_db)
    policy = PathLeasePolicy(
        stability_window_s=0,
        minimum_distinct_frames=2,
        lease_ttl_s=10,
        old_path_grace_s=1,
    )
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=policy,
        ingress_allowed=lambda _node_id: True,
    )
    owner = PathOwner("relay", GATEWAY_A)
    try:
        accepted = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=1,
            owner=owner,
            now=NOW,
        )
        assert accepted.status == "accepted"
        with sqlite3.connect(replay_db) as connection:
            before = connection.execute(
                """
                SELECT canonical_boot_session_hex,canonical_seq
                FROM n3w_path_leases WHERE node_id=?
                """,
                (NODE_ID,),
            ).fetchone()

        with RelayAuthorizationAdmin(
            auth_db,
            key_dir,
            node_state=active,
            path_invalidator=ReplayPathLeaseInvalidator(replay),
        ) as admin:
            admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
            epoch = admin.stage_key(node_id=NODE_ID, key_material=KEY_A)["key_epoch"]
            admin.activate_key(node_id=NODE_ID, key_epoch=epoch)
            revoked = admin.revoke_grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
            assert revoked["recovery_pending"] is False

            with SqliteRelayAuthorizationProvider(auth_db, key_dir) as provider:
                with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
                    provider.resolve_key(gateway_id=GATEWAY_A, node_id=NODE_ID, key_epoch=1)

            with sqlite3.connect(replay_db) as connection:
                row = connection.execute(
                    """
                    SELECT active_gateway_id,lease_expires_at,canonical_boot_session_hex,
                           canonical_seq,candidate_gateway_id
                    FROM n3w_path_leases WHERE node_id=?
                    """,
                    (NODE_ID,),
                ).fetchone()
            assert row[:2] == (REVOKED_GATEWAY_SENTINEL, "1970-01-01T00:00:00.000Z")
            assert row[2:4] == before
            assert row[4] is None
            assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=1).status == "duplicate"

            admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
            first = path.process(
                node_id=NODE_ID,
                boot_id=BOOT_ID,
                seq=2,
                owner=owner,
                now=NOW + timedelta(seconds=1),
            )
            assert first.code == "path_candidate_pending"
            second = path.process(
                node_id=NODE_ID,
                boot_id=BOOT_ID,
                seq=3,
                owner=owner,
                now=NOW + timedelta(seconds=2),
            )
            assert second.status == "accepted"
            assert second.switched is True
            assert second.active_owner == owner
    finally:
        replay.close()


def test_pending_path_cleanup_can_recover_then_regrant(tmp_path: Path) -> None:
    auth_db, key_dir = admin_paths(tmp_path)
    replay_db = tmp_path / "replay.sqlite3"
    replay = ReplayRegistry(replay_db)
    N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=PathLeasePolicy(
            stability_window_s=0,
            minimum_distinct_frames=1,
            lease_ttl_s=10,
            old_path_grace_s=0,
        ),
        ingress_allowed=lambda _node_id: True,
    )
    try:
        with RelayAuthorizationAdmin(auth_db, key_dir, node_state=active) as admin:
            admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
            assert admin.revoke_grant(gateway_id=GATEWAY_A, node_id=NODE_ID)["recovery_pending"]

        with RelayAuthorizationAdmin(
            auth_db,
            key_dir,
            node_state=active,
            path_invalidator=ReplayPathLeaseInvalidator(replay),
        ) as recovered:
            assert recovered.recover()["recovered_operation_count"] == 1
            assert recovered.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)["status"] == "passed"
    finally:
        replay.close()


def test_two_admins_serialize_key_epoch_allocation(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    first = RelayAuthorizationAdmin(database, key_dir, node_state=active)
    second = RelayAuthorizationAdmin(database, key_dir, node_state=active)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            epochs = sorted(
                future.result()["key_epoch"]
                for future in (
                    executor.submit(first.stage_key, node_id=NODE_ID, key_material=KEY_A),
                    executor.submit(second.stage_key, node_id=NODE_ID, key_material=KEY_B),
                )
            )
        assert epochs == [1, 2]
    finally:
        first.close()
        second.close()


def test_audits_never_expose_key_material_filename_or_fingerprint(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        admin.grant(gateway_id=GATEWAY_A, node_id=NODE_ID)
        epoch = admin.stage_key(node_id=NODE_ID, key_material=KEY_A)["key_epoch"]
        admin.activate_key(node_id=NODE_ID, key_epoch=epoch)
        admin_doc = json.dumps(admin.audit())
    with SqliteRelayAuthorizationProvider(database, key_dir) as provider:
        runtime_doc = json.dumps(provider.audit())
    for document in (admin_doc, runtime_doc):
        assert KEY_A.hex() not in document
        assert f"{NODE_ID}-epoch-1.key" not in document
        assert hashlib.sha256(KEY_A).hexdigest() not in document


def test_reserved_gateway_sentinel_cannot_be_granted(tmp_path: Path) -> None:
    database, key_dir = admin_paths(tmp_path)
    with RelayAuthorizationAdmin(database, key_dir, node_state=active) as admin:
        with pytest.raises(RelayAuthorizationAdminError, match="gateway_id_reserved"):
            admin.grant(gateway_id=REVOKED_GATEWAY_SENTINEL, node_id=NODE_ID)
