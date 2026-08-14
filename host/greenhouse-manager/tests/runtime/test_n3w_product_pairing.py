from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.ops.n3w_relay_authorization_admin import RelayAuthorizationAdmin
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore, CredentialState
from greenhouse_manager.runtime.n3w_product_pairing import (
    ManagedProductCredentialIssuer,
    ProductPairingCore,
    ProductSecurePairingCoordinator,
)
from greenhouse_manager.runtime.n3w_product_peer_authorization import (
    PeerAuthorizationRejected,
    ProductNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureChannel,
    build_secure_pairing_proof,
    decode_base64url,
    derive_secure_keys,
    load_public_key,
    public_key_text,
    secure_proof_transcript,
)
from greenhouse_manager.runtime.pairing_service import PairingSessionManager, build_pairing_proof
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 8, 14, 5, 0, tzinfo=UTC)
SYSTEM_ID = "gh-system-01"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-node-01"
PAIRING_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
NODE_NONCE = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY"
PRODUCT_KEY = bytes(range(32))


class _Provisioner:
    def __init__(self) -> None:
        self.provisioned = []
        self.deprovisioned = []

    def provision(self, plan, credentials) -> None:
        self.provisioned.append((plan, credentials))

    def deprovision(self, plan) -> None:
        self.deprovisioned.append(plan)


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": NODE_NONCE,
        "capabilities": ["mqtt-runtime-credentials", "n3w-product-relay"],
        "sent_at_ms": 120345,
    }


@pytest.fixture
def product_pairing(tmp_path: Path):
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    credential_store = CredentialLifecycleStore(tmp_path / "credentials.sqlite3")
    registry.observe_hello(_hello(), now=NOW)
    provisioner = _Provisioner()
    base = PairingSessionManager(
        registry,
        provisioner,
        system_id=SYSTEM_ID,
        broker_host="broker.local",
        broker_port=8883,
        broker_tls_server_name="broker.local",
        ca_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
        random_bytes=lambda size: b"m" * size,
        uuid_factory=lambda: UUID("12345678-1234-5678-1234-567812345678"),
    )
    database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    admin = RelayAuthorizationAdmin(
        database,
        key_dir,
        node_state=lambda node_id: registry.node_id_lease_state(node_id),
    )
    issuer = ManagedProductCredentialIssuer(
        admin,
        credential_store,
        random_bytes=lambda size: PRODUCT_KEY if size == 32 else b"x" * size,
    )
    product = ProductPairingCore(base, issuer)
    try:
        yield registry, credential_store, provisioner, admin, database, key_dir, product
    finally:
        admin.close()
        credential_store.close()
        registry.close()


def _verify_base_proof(product: ProductPairingCore):
    offer = product.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    proof = build_pairing_proof(
        pairing_secret=PAIRING_SECRET,
        offer=offer,
        node_nonce=NODE_NONCE,
    )
    product.verify_proof(offer.session_id, proof=proof, now=NOW)
    return offer


def test_product_key_is_staged_after_approval_and_activated_only_after_ack(product_pairing) -> None:
    registry, credential_store, provisioner, admin, database, key_dir, product = product_pairing
    offer = _verify_base_proof(product)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    bundle = product.issue_credentials(offer.session_id, now=NOW)

    assert bundle.node_id == NODE_ID
    assert bundle.credential_generation == 1
    assert bundle.n3w_key_epoch == 1
    assert decode_base64url(bundle.n3w_application_key, field_name="n3w_application_key") == PRODUCT_KEY
    assert admin.audit()["enabled_gateway_grant_count"] == 0
    assert admin.audit()["staged_key_epoch_count"] == 1
    assert len(provisioner.provisioned) == 1
    with pytest.raises(KeyError):
        credential_store.get(HARDWARE_ID)
    with (
        ProductNodeApplicationKeyProvider(database, key_dir) as provider,
        pytest.raises(PeerAuthorizationRejected, match="key_epoch_rejected"),
    ):
        provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=1)

    consumed = product.acknowledge_delivery(offer.session_id, now=NOW)

    assert consumed.state.value == "consumed"
    lifecycle = credential_store.get(HARDWARE_ID)
    assert lifecycle.state is CredentialState.ACTIVE
    assert lifecycle.node_id == NODE_ID
    assert lifecycle.active_generation == 1
    assert admin.audit()["active_key_epoch_count"] == 1
    assert admin.audit()["enabled_gateway_grant_count"] == 0
    with ProductNodeApplicationKeyProvider(database, key_dir) as provider:
        assert provider.resolve_node_application_key(node_id=NODE_ID, key_epoch=1) == PRODUCT_KEY


def test_aborted_product_pairing_revokes_staged_key_and_rolls_back_broker(product_pairing) -> None:
    registry, credential_store, provisioner, admin, _, _, product = product_pairing
    offer = _verify_base_proof(product)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
    product.issue_credentials(offer.session_id, now=NOW)

    failed = product.abort(offer.session_id)

    assert failed.state.value == "failed"
    assert len(provisioner.deprovisioned) == 1
    audit = admin.audit()
    assert audit["active_key_epoch_count"] == 0
    assert audit["staged_key_epoch_count"] == 0
    assert audit["revoked_key_epoch_count"] == 1
    with pytest.raises(KeyError):
        credential_store.get(HARDWARE_ID)


def test_product_application_key_is_only_delivered_inside_secure_pairing_envelope(product_pairing) -> None:
    registry, credential_store, _, admin, _, _, product = product_pairing
    coordinator = ProductSecurePairingCoordinator(
        product,
        private_key_factory=lambda: X25519PrivateKey.from_private_bytes(b"M" * 32),
    )
    offer = coordinator.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    node_private = X25519PrivateKey.from_private_bytes(b"N" * 32)
    node_public_key = public_key_text(node_private)
    proof = build_secure_pairing_proof(
        pairing_secret=PAIRING_SECRET,
        offer=offer,
        node_nonce=NODE_NONCE,
        node_public_key=node_public_key,
    )
    coordinator.establish_channel(
        offer.session_id,
        node_nonce=NODE_NONCE,
        node_public_key=node_public_key,
        proof=proof,
        now=NOW,
    )
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    envelope = coordinator.issue_encrypted_credentials(offer.session_id, now=NOW)
    transcript = secure_proof_transcript(
        offer=offer,
        node_nonce=NODE_NONCE,
        node_public_key=node_public_key,
    )
    shared = node_private.exchange(load_public_key(offer.manager_public_key, field_name="manager_public_key"))
    keys = derive_secure_keys(
        shared_secret=shared,
        pairing_secret=decode_base64url(PAIRING_SECRET, field_name="pairing_secret"),
        transcript=transcript,
    )
    node_channel = SecureChannel(
        session_id=offer.session_id,
        send_direction=NODE_TO_MANAGER,
        send_key=keys.node_to_manager,
        receive_direction=MANAGER_TO_NODE,
        receive_key=keys.manager_to_node,
    )
    plaintext = node_channel.decrypt(envelope, expected_content_type="gh.pair.credentials/1")
    document = json.loads(plaintext)

    assert document["node_id"] == NODE_ID
    assert document["n3w_key_epoch"] == 1
    assert decode_base64url(document["n3w_application_key"], field_name="n3w_application_key") == PRODUCT_KEY
    assert "peer_mac" not in document
    assert "gateway_id" not in document
    assert "lmk" not in document
    assert admin.audit()["staged_key_epoch_count"] == 1

    ack = node_channel.encrypt(
        json.dumps(
            {
                "credential_generation": 1,
                "node_id": NODE_ID,
                "schema": "gh.pair.delivery-ack/1",
                "stored": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
        content_type="gh.pair.delivery-ack/1",
    )
    consumed = coordinator.acknowledge_encrypted_delivery(offer.session_id, ack, now=NOW)
    assert consumed.state.value == "consumed"
    assert credential_store.get(HARDWARE_ID).state is CredentialState.ACTIVE
    assert admin.audit()["active_key_epoch_count"] == 1
