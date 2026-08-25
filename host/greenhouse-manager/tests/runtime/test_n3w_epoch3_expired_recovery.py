from __future__ import annotations

import base64
import os
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_node_application_keys import (
    NodeApplicationKeyStoreUnavailable,
    SqliteNodeApplicationKeyAdmin,
)
from greenhouse_manager.runtime.n3w_node_credentials import (
    ManagedApplicationKeyLifecycle,
)
from greenhouse_manager.runtime.n3w_pairing_recovery import (
    stage_pairing_epoch_key,
)
from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
)
from greenhouse_manager.runtime.registration import (
    NodeIdLeaseState,
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000f350"
NODE_ID = "node_f350"
PAIRING_1 = "11111111-1111-4111-8111-111111111111"
PAIRING_2 = "22222222-2222-4222-8222-222222222222"
PAIRING_2_ALT = "2aaaaaaa-2222-4222-8222-222222222222"
PAIRING_3 = "33333333-3333-4333-8333-333333333333"
SETUP_SECRET = bytes(range(32))
KEY_1 = bytes([0x11]) * 32
KEY_3 = bytes([0x33]) * 32


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(
        value + "=" * ((4 - len(value) % 4) % 4)
    )


def _hello(pairing_id: str, epoch: int) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": epoch,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "fc4-epoch3-recovery-test",
        "node_nonce": _b64(bytes([0x31 + epoch]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": epoch,
    }


def _prepare_expired_epoch2(
    registry: RegistrationRegistry,
) -> None:
    created = registry.observe_hello(
        _hello(PAIRING_1, 1),
        now=NOW,
    )
    assert created.status == "created"
    registry.approve(
        HARDWARE_ID,
        PAIRING_1,
        node_id=NODE_ID,
        now=NOW,
    )
    registry.authorize_repair(
        HARDWARE_ID,
        PAIRING_2,
        now=NOW + timedelta(seconds=1),
    )
    successor = registry.observe_hello(
        _hello(PAIRING_2, 2),
        now=NOW + timedelta(seconds=2),
    )
    assert successor.status == "superseded"
    assert successor.record.node_id == NODE_ID
    assert registry.expire_pending(
        now=NOW + timedelta(seconds=70)
    ) == 1
    expired = registry.get(HARDWARE_ID)
    assert expired.pairing_epoch == 2
    assert expired.state is RegistrationState.EXPIRED
    assert expired.node_id == NODE_ID


def test_expired_transaction_requires_fresh_id_not_higher_device_epoch(
    tmp_path,
) -> None:
    with RegistrationRegistry(
        tmp_path / "registration.sqlite3",
        pending_ttl_s=60,
    ) as registry:
        _prepare_expired_epoch2(registry)

        same = registry.observe_hello(
            _hello(PAIRING_2, 2),
            now=NOW + timedelta(seconds=71),
        )
        assert same.status == "rejected"
        assert same.reason == "replay_detected"

        blocked = registry.observe_hello(
            _hello(PAIRING_2_ALT, 2),
            now=NOW + timedelta(seconds=72),
        )
        assert blocked.status == "rejected"
        assert blocked.reason == "repair_intent_required"
        assert registry.get(HARDWARE_ID).pairing_id == PAIRING_2

        # Device pairing_epoch is audit metadata only. A fresh random ID
        # with the same legacy epoch is accepted after a new bound intent.
        registry.authorize_repair(
            HARDWARE_ID,
            PAIRING_2_ALT,
            now=NOW + timedelta(seconds=73),
        )
        same_epoch_new_id = registry.observe_hello(
            _hello(PAIRING_2_ALT, 2),
            now=NOW + timedelta(seconds=74),
        )

        assert same_epoch_new_id.status == "superseded"
        assert same_epoch_new_id.record.pairing_id == PAIRING_2_ALT
        assert same_epoch_new_id.record.state is RegistrationState.PENDING
        assert same_epoch_new_id.record.node_id == NODE_ID


def _build_key_admin(tmp_path) -> tuple[
    SqliteNodeApplicationKeyAdmin,
    object,
]:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    database = root / "node-keys.sqlite3"
    admin = SqliteNodeApplicationKeyAdmin(
        database,
        root / "keys",
        node_state=lambda node_id: (
            "active" if node_id == NODE_ID else None
        ),
    )
    return admin, database


def test_application_key_rotation_is_independent_of_credential_generation(
    tmp_path,
) -> None:
    admin, database = _build_key_admin(tmp_path)
    try:
        first = admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY_1,
        )
        assert first["key_epoch"] == 1
        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=1,
        )

        lifecycle = ManagedApplicationKeyLifecycle(
            admin,
            random_bytes=lambda size: (
                KEY_3 if size == 32 else b""
            ),
        )
        material = lifecycle.stage_rotation(
            node_id=NODE_ID,
        )

        assert material.key_epoch == 2

        with sqlite3.connect(database) as connection:
            rows = connection.execute(
                """
                SELECT key_epoch,state,enabled
                FROM n3w_relay_key_epochs
                WHERE node_id=?
                ORDER BY key_epoch
                """,
                (NODE_ID,),
            ).fetchall()

        assert rows == [
            (1, "ACTIVE", 1),
            (2, "STAGED", 0),
        ]

        lifecycle.rollback_staged_rotation(
            material
        )

        with sqlite3.connect(database) as connection:
            rows_after = connection.execute(
                """
                SELECT key_epoch,state,enabled
                FROM n3w_relay_key_epochs
                WHERE node_id=?
                ORDER BY key_epoch
                """,
                (NODE_ID,),
            ).fetchall()

        assert rows_after == [
            (1, "ACTIVE", 1),
            (2, "REVOKED", 0),
        ]
    finally:
        admin.close()


def test_exact_key_target_rejects_non_monotonic_reuse(
    tmp_path,
) -> None:
    admin, _database = _build_key_admin(tmp_path)
    try:
        first = admin.stage_key(
            node_id=NODE_ID,
            key_material=KEY_1,
        )
        admin.activate_key(
            node_id=NODE_ID,
            key_epoch=int(first["key_epoch"]),
        )

        with pytest.raises(
            NodeApplicationKeyStoreUnavailable,
            match="target_key_epoch_not_monotonic",
        ):
            stage_pairing_epoch_key(
                admin,
                node_id=NODE_ID,
                key_material=KEY_3,
                target_key_epoch=1,
            )
    finally:
        admin.close()


class _FailingStager:
    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ):
        assert hardware_id == HARDWARE_ID
        assert pairing_id == PAIRING_3
        assert node_id == NODE_ID
        assert credential_generation == 1
        raise RuntimeError("synthetic_epoch3_stage_failure")


class _PairingRandom:
    def __call__(self, size: int) -> bytes:
        if size == 16:
            return bytes([0x51]) * 16
        if size == 12:
            return bytes([0x61]) * 12
        raise AssertionError(size)


def test_epoch3_registered_recovery_stops_before_staging_and_preserves_identity(
    tmp_path,
) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(
        database,
        pending_ttl_s=60,
    ) as registry:
        _prepare_expired_epoch2(registry)

        registry.authorize_repair(
            HARDWARE_ID,
            PAIRING_3,
            now=NOW + timedelta(seconds=72),
        )
        epoch3 = registry.observe_hello(
            _hello(PAIRING_3, 3),
            now=NOW + timedelta(seconds=73),
        )
        assert epoch3.status == "superseded"
        assert epoch3.record.node_id == NODE_ID

        coordinator = SimplifiedPairingCoordinator(
            registry,
            _FailingStager(),
            manager_id="manager_fc4_test",
            random_bytes=_PairingRandom(),
        )
        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_3,
            setup_secret=SETUP_SECRET,
        )
        node_nonce = bytes([0x71]) * 16
        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_3,
            node_nonce=_b64(node_nonce),
            now=NOW + timedelta(seconds=73),
        )
        transcript = PairingTranscript(
            pairing_id=PAIRING_3,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=node_nonce,
            manager_nonce=_unb64(offer.manager_nonce),
        )
        proof = build_setup_proof(
            SETUP_SECRET,
            transcript,
            role="node",
        )

        with pytest.raises(
            SimplifiedPairingConflict,
            match="credential_recovery_required",
        ):
            coordinator.establish(
                offer.session_id,
                node_proof=_b64(proof),
                now=NOW + timedelta(seconds=74),
            )

        current = registry.get(HARDWARE_ID)
        assert current.pairing_epoch == 3
        assert current.state is RegistrationState.PENDING
        assert current.node_id == NODE_ID
        assert (
            registry.node_id_lease_state(NODE_ID)
            is NodeIdLeaseState.ACTIVE
        )

        events = registry.list_events(
            hardware_id=HARDWARE_ID
        )

        # C2 must stop before automatic approval/staging. Therefore no
        # rollback event should be necessary or observable.
        assert not any(
            event.event
            == "automatic_approval_rolled_back_preserved_node"
            for event in events
        )

        with sqlite3.connect(database) as connection:
            history = connection.execute(
                """
                SELECT node_id,released_at
                FROM registration_node_history
                WHERE hardware_id=?
                ORDER BY history_id
                """,
                (HARDWARE_ID,),
            ).fetchall()

        assert history == [(NODE_ID, None)]
