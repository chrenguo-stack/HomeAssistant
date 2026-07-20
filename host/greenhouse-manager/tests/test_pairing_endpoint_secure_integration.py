from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.pairing_endpoint import (
    PairingEndpointApp,
    PendingOfferRegistry,
    build_claim_proof,
)
from greenhouse_manager.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureChannel,
    SecureEnvelope,
    SecurePairingCoordinator,
    SecurePairingOffer,
    build_secure_pairing_proof,
    derive_secure_keys,
    load_public_key,
    public_key_text,
    secure_proof_transcript,
)
from greenhouse_manager.pairing_service import (
    CredentialBundle,
    PairingOffer,
    PairingSessionSnapshot,
    PairingSessionState,
    build_pairing_proof,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
SESSION_ID = "96329311-1c64-4c88-9343-04f5de69698e"
PAIRING_ID = "416ccfd2-5a5b-46e0-84d1-44c4067dbde0"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
NODE_ID = "gh-n1-a9f2f8"
CLIENT_IP = "127.0.0.2"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


PAIRING_SECRET = b64(bytes(range(32)))
NODE_NONCE = b64(bytes(reversed(range(32))))
MANAGER_NONCE = b64(bytes([0xA5]) * 32)


class IntegrationPairingCore:
    def __init__(self) -> None:
        self.offer = PairingOffer(
            schema="gh.pair.offer/1",
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            manager_nonce=MANAGER_NONCE,
            expires_at=NOW + timedelta(seconds=120),
            max_proof_attempts=3,
        )
        self.state = PairingSessionState.OPEN
        self.issue_calls = 0
        self.ack_calls = 0
        self.abort_calls = 0
        self.bundle = CredentialBundle(
            schema="gh.pair.credentials/1",
            system_id="greenhouse",
            node_id=NODE_ID,
            broker_host="mqtt.greenhouse.local",
            broker_port=8883,
            broker_tls_server_name="mqtt.greenhouse.local",
            ca_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
            mqtt_username=f"ghn_{NODE_ID}",
            mqtt_client_id=NODE_ID,
            credential_generation=7,
            mqtt_password="integration-only-password",
        )

    def open_session(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> PairingOffer:
        assert (hardware_id, pairing_id, pairing_secret, now) == (
            HARDWARE_ID,
            PAIRING_ID,
            PAIRING_SECRET,
            NOW,
        )
        return self.offer

    def verify_proof(
        self,
        session_id: str,
        *,
        proof: str,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        assert proof == build_pairing_proof(
            pairing_secret=PAIRING_SECRET,
            offer=self.offer,
            node_nonce=NODE_NONCE,
        )
        self.state = PairingSessionState.PROOF_VERIFIED
        return self.snapshot()

    def issue_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> CredentialBundle:
        assert session_id == SESSION_ID
        self.issue_calls += 1
        self.state = PairingSessionState.CREDENTIALS_ISSUED
        return self.bundle

    def acknowledge_delivery(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        self.ack_calls += 1
        self.state = PairingSessionState.CONSUMED
        return self.snapshot()

    def abort(self, session_id: str) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        self.abort_calls += 1
        self.state = PairingSessionState.FAILED
        return self.snapshot()

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        if now is not None and now > self.offer.expires_at:
            self.state = PairingSessionState.EXPIRED
            return 1
        return 0

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        assert session_id == SESSION_ID
        return self.snapshot()

    def snapshot(self) -> PairingSessionSnapshot:
        generation = (
            self.bundle.credential_generation
            if self.state
            in {
                PairingSessionState.CREDENTIALS_ISSUED,
                PairingSessionState.CONSUMED,
            }
            else None
        )
        return PairingSessionSnapshot(
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            state=self.state,
            expires_at=self.offer.expires_at,
            proof_attempts=0,
            credential_generation=generation,
        )


class IntegrationNodePeer:
    def __init__(
        self,
        offer: SecurePairingOffer,
        *,
        private_key: X25519PrivateKey,
    ) -> None:
        self.offer = offer
        self.private_key = private_key
        self.public_key = public_key_text(private_key)
        self.channel: SecureChannel | None = None

    def secure_proof(self) -> str:
        return build_secure_pairing_proof(
            pairing_secret=PAIRING_SECRET,
            offer=self.offer,
            node_nonce=NODE_NONCE,
            node_public_key=self.public_key,
        )

    def establish_channel(self) -> None:
        transcript = secure_proof_transcript(
            offer=self.offer,
            node_nonce=NODE_NONCE,
            node_public_key=self.public_key,
        )
        shared = self.private_key.exchange(
            load_public_key(
                self.offer.manager_public_key,
                field_name="manager_public_key",
            )
        )
        keys = derive_secure_keys(
            shared_secret=shared,
            pairing_secret=base64.urlsafe_b64decode(PAIRING_SECRET + "="),
            transcript=transcript,
        )
        self.channel = SecureChannel(
            session_id=SESSION_ID,
            send_direction=NODE_TO_MANAGER,
            send_key=keys.node_to_manager,
            receive_direction=MANAGER_TO_NODE,
            receive_key=keys.manager_to_node,
        )

    def decrypt_credentials(self, document: dict[str, Any]) -> dict[str, Any]:
        assert self.channel is not None
        plaintext = self.channel.decrypt(
            SecureEnvelope.from_document(document),
            expected_content_type="gh.pair.credentials/1",
        )
        decoded = json.loads(plaintext.decode("utf-8"))
        assert isinstance(decoded, dict)
        return decoded

    def delivery_ack(self, credentials: dict[str, Any]) -> SecureEnvelope:
        assert self.channel is not None
        payload = json.dumps(
            {
                "credential_generation": credentials["credential_generation"],
                "node_id": credentials["node_id"],
                "schema": "gh.pair.delivery-ack/1",
                "stored": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.channel.encrypt(
            payload,
            content_type="gh.pair.delivery-ack/1",
        )


def post(
    app: PairingEndpointApp,
    path: str,
    document: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    response = app.handle(
        method="POST",
        path=path,
        headers={"Content-Type": "application/json"},
        body=json.dumps(document, separators=(",", ":")).encode("utf-8"),
        client_ip=CLIENT_IP,
    )
    decoded = json.loads(response.body.decode("utf-8"))
    assert isinstance(decoded, dict)
    return response.status, decoded


def test_endpoint_and_secure_transport_complete_real_crypto_roundtrip() -> None:
    core = IntegrationPairingCore()
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: X25519PrivateKey.from_private_bytes(
            bytes([0x11]) * 32
        ),
    )
    registry = PendingOfferRegistry(coordinator)
    registry.import_scanned_pairing(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    app = PairingEndpointApp(registry, clock=lambda: NOW)

    claim_proof = build_claim_proof(
        pairing_secret=PAIRING_SECRET,
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_ID,
    )
    status, offer_document = post(
        app,
        "/v1/pairing/claim",
        {
            "schema": "gh.pair.claim/1",
            "hardware_id": HARDWARE_ID,
            "pairing_id": PAIRING_ID,
            "claim_proof": claim_proof,
        },
    )
    assert status == 200
    assert "pairing_secret" not in offer_document

    offer = SecurePairingOffer(
        schema=offer_document["schema"],
        session_id=offer_document["session_id"],
        hardware_id=offer_document["hardware_id"],
        pairing_id=offer_document["pairing_id"],
        manager_nonce=offer_document["manager_nonce"],
        manager_public_key=offer_document["manager_public_key"],
        cipher_suite=offer_document["cipher_suite"],
        expires_at=core.offer.expires_at,
        max_proof_attempts=offer_document["max_proof_attempts"],
    )
    node = IntegrationNodePeer(
        offer,
        private_key=X25519PrivateKey.from_private_bytes(bytes([0x22]) * 32),
    )

    status, establish_document = post(
        app,
        f"/v1/pairing/sessions/{SESSION_ID}/establish",
        {
            "schema": "gh.pair.establish/1",
            "node_nonce": NODE_NONCE,
            "node_public_key": node.public_key,
            "proof": node.secure_proof(),
        },
    )
    assert status == 200
    assert establish_document["state"] == "channel_established"
    node.establish_channel()

    status, encrypted_credentials = post(
        app,
        f"/v1/pairing/sessions/{SESSION_ID}/credentials",
        {"schema": "gh.pair.credentials-request/1"},
    )
    assert status == 200
    assert "integration-only-password" not in json.dumps(encrypted_credentials)
    credentials = node.decrypt_credentials(encrypted_credentials)
    assert credentials["node_id"] == NODE_ID
    assert credentials["mqtt_password"] == "integration-only-password"

    status, consumed = post(
        app,
        f"/v1/pairing/sessions/{SESSION_ID}/ack",
        node.delivery_ack(credentials).to_document(),
    )
    assert status == 200
    assert consumed["state"] == "consumed"
    assert consumed["credential_generation"] == 7
    assert core.issue_calls == 1
    assert core.ack_calls == 1

    status_response = app.handle(
        method="GET",
        path=f"/v1/pairing/sessions/{SESSION_ID}/status",
        headers={},
        body=b"",
        client_ip=CLIENT_IP,
    )
    assert status_response.status == 404
