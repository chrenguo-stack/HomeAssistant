from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.ops.n3w_relay_authorization_admin import RelayAuthorizationAdmin
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore, CredentialState
from greenhouse_manager.runtime.n3w_product_pairing import ManagedProductCredentialIssuer
from greenhouse_manager.runtime.n3w_product_peer_authorization import (
    PeerAuthorizationRejected,
    ProductNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 8, 14, 7, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-node-01"
OLD_KEY = b"o" * 32
NEW_KEY = b"n" * 32


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "n3w-product-relay"],
        "sent_at_ms": 120345,
    }


def test_product_key_rotation_preserves_old_grace_then_revokes_it(tmp_path: Path) -> None:
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    credentials = CredentialLifecycleStore(tmp_path / "credentials.sqlite3")
    database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    try:
        registry.observe_hello(_hello(), now=NOW)
        registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
        credentials.activate(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            node_id=NODE_ID,
            generation=1,
            now=NOW,
        )
        with RelayAuthorizationAdmin(
            database,
            key_dir,
            node_state=lambda node_id: registry.node_id_lease_state(node_id),
        ) as admin:
            old = admin.stage_key(node_id=NODE_ID, key_material=OLD_KEY)
            admin.activate_key(node_id=NODE_ID, key_epoch=old["key_epoch"])
            issuer = ManagedProductCredentialIssuer(
                admin,
                credentials,
                random_bytes=lambda size: NEW_KEY if size == 32 else b"x" * size,
            )
            staged = issuer.stage(
                hardware_id=HARDWARE_ID,
                pairing_id="ca3e468d-fcdd-413d-b834-a8ac0cbe889e",
                node_id=NODE_ID,
                credential_generation=2,
            )
            assert staged.key_epoch == 2
            issuer.commit(staged, now=NOW)

            lifecycle = credentials.get(HARDWARE_ID)
            assert lifecycle.state is CredentialState.ACTIVE
            assert lifecycle.active_generation == 2
            audit = admin.audit()
            assert audit["active_key_epoch_count"] == 1
            assert audit["grace_key_epoch_count"] == 1
            assert audit["enabled_gateway_grant_count"] == 0

            with ProductNodeApplicationKeyProvider(database, key_dir) as provider:
                assert provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=1) == OLD_KEY
                assert provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=2) == NEW_KEY

            admin.revoke_key(node_id=NODE_ID, key_epoch=1)

        with ProductNodeApplicationKeyProvider(database, key_dir) as provider:
            with pytest.raises(PeerAuthorizationRejected, match="key_epoch_rejected"):
                provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=1)
            assert provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=2) == NEW_KEY
    finally:
        credentials.close()
        registry.close()
