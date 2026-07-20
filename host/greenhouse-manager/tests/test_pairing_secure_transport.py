from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureChannel,
    SecureEnvelope,
    SecureEnvelopeRejected,
    SecurePairingConflict,
    SecurePairingCoordinator,
    SecurePairingOffer,
    SecurePairingProofRejected,
    SecurePairingState,
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

NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
SESSION_ID = "96329311-1c64-4c88-9343-04f5de69698e"
PAIRING_ID = "416ccfd2-5a5b-46e0-84d1-44c4067dbde0"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
NODE_ID = "gh-n1-a9f2f8"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


PAIRING_SECRET = b64(bytes(range(32)))
NODE_NONCE = b64(bytes(reversed(range(32))))
MANAGER_NONCE = b64(bytes([0xA5]) * 32)


class FakePairingCore:
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
        self.proof_attempts = 0
        self.issue_calls = 0
        self.abort_calls = 0
        self.ack_calls = 0
        self.expire_calls = 0
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
            credential_generation=3,
            mqtt_password="test-only-password",
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
        self.proof_attempts += 1
        expected = build_pairing_proof(
            pairing_secret=PAIRING_SECRET,
            offer=self.offer,
            node_nonce=NODE_NONCE,
        )
        if proof != expected:
            raise RuntimeError("proof rejected")
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
        self.expire_calls += 1
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
            in (
                PairingSessionState.CREDENTIALS_ISSUED,
                PairingSessionState.CONSUMED,
            )
            else None
        )
        return PairingSessionSnapshot(
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            state=self.state,
            expires_at=self.offer.expires_at,
            proof_attempts=self.proof_attempts,
            credential_generation=generation,
        )


class NodePeer:
    def __init__(
        self,
        offer: SecurePairingOffer,
        *,
        pairing_secret: str,
        node_nonce: str,
        private_key: X25519PrivateKey,
    ) -> None:
        self.offer = offer
        self.pairing_secret = pairing_secret
        self.node_nonce = node_nonce
        self.private_key = private_key
        self.node_public_key = public_key_text(private_key)
        self.channel: SecureChannel | None = None
        self.credentials: dict[str, Any] | None = None
        self.ack: SecureEnvelope | None = None

    def proof(self) -> str:
        return build_secure_pairing_proof(
            pairing_secret=self.pairing_secret,
            offer=self.offer,
            node_nonce=self.node_nonce,
            node_public_key=self.node_public_key,
        )

    def establish_channel(self) -> None:
        transcript = secure_proof_transcript(
            offer=self.offer,
            node_nonce=self.node_nonce,
            node_public_key=self.node_public_key,
        )
        shared = self.private_key.exchange(
            load_public_key(
                self.offer.manager_public_key,
                field_name="manager_public_key",
            )
        )
        keys = derive_secure_keys(
            shared_secret=shared,
            pairing_secret=base64.urlsafe_b64decode(
                self.pairing_secret + "="
            ),
            transcript=transcript,
        )
        self.channel = SecureChannel(
            session_id=self.offer.session_id,
            send_direction=NODE_TO_MANAGER,
            send_key=keys.node_to_manager,
            receive_direction=MANAGER_TO_NODE,
            receive_key=keys.manager_to_node,
        )

    def decrypt_credentials(
        self,
        envelope: SecureEnvelope | dict[str, Any],
    ) -> dict[str, Any]:
        assert self.channel is not None
        candidate = (
            envelope
            if isinstance(envelope, SecureEnvelope)
            else SecureEnvelope.from_document(envelope)
        )
        plaintext = self.channel.decrypt(
            candidate,
            expected_content_type="gh.pair.credentials/1",
        )
        self.credentials = json.loads(plaintext)
        return self.credentials

    def build_delivery_ack(self) -> SecureEnvelope:
        if self.ack is not None:
            return self.ack
        assert self.channel is not None and self.credentials is not None
        document = {
            "credential_generation": self.credentials[
                "credential_generation"
            ],
            "node_id": self.credentials["node_id"],
            "schema": "gh.pair.delivery-ack/1",
            "stored": True,
        }
        self.ack = self.channel.encrypt(
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
            content_type="gh.pair.delivery-ack/1",
        )
        return self.ack


def fixed_private(value: int) -> X25519PrivateKey:
    return X25519PrivateKey.from_private_bytes(bytes([value]) * 32)


def established_pair() -> tuple[
    FakePairingCore,
    SecurePairingCoordinator,
    NodePeer,
]:
    core = FakePairingCore()
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: fixed_private(0x11),
    )
    offer = coordinator.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    node = NodePeer(
        offer,
        pairing_secret=PAIRING_SECRET,
        node_nonce=NODE_NONCE,
        private_key=fixed_private(0x22),
    )
    snapshot = coordinator.establish_channel(
        SESSION_ID,
        node_nonce=NODE_NONCE,
        node_public_key=node.node_public_key,
        proof=node.proof(),
        now=NOW,
    )
    node.establish_channel()
    assert snapshot.state == SecurePairingState.CHANNEL_ESTABLISHED
    return core, coordinator, node


def test_authenticated_encrypted_credential_roundtrip() -> None:
    core, coordinator, node = established_pair()
    envelope = coordinator.issue_encrypted_credentials(
        SESSION_ID,
        now=NOW,
    )
    credentials = node.decrypt_credentials(envelope)
    snapshot = coordinator.acknowledge_encrypted_delivery(
        SESSION_ID,
        node.build_delivery_ack(),
        now=NOW,
    )

    assert envelope.content_type == "gh.pair.credentials/1"
    assert "test-only-password" not in json.dumps(envelope.to_document())
    assert credentials["mqtt_password"] == "test-only-password"
    assert snapshot.state == SecurePairingState.CONSUMED
    assert snapshot.credential_generation == 3
    assert core.issue_calls == core.ack_calls == 1


def test_secure_proof_binds_both_ephemeral_public_keys() -> None:
    core = FakePairingCore()
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: fixed_private(0x11),
    )
    offer = coordinator.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    node = NodePeer(
        offer,
        pairing_secret=PAIRING_SECRET,
        node_nonce=NODE_NONCE,
        private_key=fixed_private(0x22),
    )
    attacker_key = public_key_text(fixed_private(0x33))

    with pytest.raises(SecurePairingProofRejected):
        coordinator.establish_channel(
            SESSION_ID,
            node_nonce=NODE_NONCE,
            node_public_key=attacker_key,
            proof=node.proof(),
            now=NOW,
        )

    assert core.proof_attempts == 0
    assert coordinator.status(SESSION_ID).proof_attempts == 1


def test_three_bad_proofs_lock_the_session() -> None:
    core = FakePairingCore()
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: fixed_private(0x11),
    )
    offer = coordinator.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    node = NodePeer(
        offer,
        pairing_secret=PAIRING_SECRET,
        node_nonce=NODE_NONCE,
        private_key=fixed_private(0x22),
    )
    wrong = b64(bytes([0xFF]) * 32)

    for _ in range(3):
        with pytest.raises(SecurePairingProofRejected):
            coordinator.establish_channel(
                SESSION_ID,
                node_nonce=NODE_NONCE,
                node_public_key=node.node_public_key,
                proof=wrong,
                now=NOW,
            )

    snapshot = coordinator.status(SESSION_ID)
    assert snapshot.state == SecurePairingState.FAILED
    assert snapshot.proof_attempts == 3
    assert core.abort_calls == 1


def test_tampering_does_not_advance_receive_sequence() -> None:
    _, coordinator, node = established_pair()
    envelope = coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    document = envelope.to_document()
    ciphertext = bytearray(
        base64.urlsafe_b64decode(document["ciphertext"] + "==")
    )
    ciphertext[-1] ^= 1
    document["ciphertext"] = b64(bytes(ciphertext))

    with pytest.raises(SecureEnvelopeRejected, match="authentication failed"):
        node.decrypt_credentials(document)

    assert node.decrypt_credentials(envelope)["node_id"] == NODE_ID


def test_replay_and_wrong_direction_are_rejected() -> None:
    _, coordinator, node = established_pair()
    envelope = coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    node.decrypt_credentials(envelope)

    with pytest.raises(SecureEnvelopeRejected, match="sequence rejected"):
        node.decrypt_credentials(envelope)

    wrong = envelope.to_document()
    wrong["direction"] = NODE_TO_MANAGER
    with pytest.raises(SecureEnvelopeRejected, match="direction mismatch"):
        node.decrypt_credentials(SecureEnvelope.from_document(wrong))


def test_credential_retry_returns_identical_envelope() -> None:
    core, coordinator, _node = established_pair()
    first = coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    second = coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    assert first == second
    assert core.issue_calls == 1


def test_ack_contract_is_authenticated_and_exact() -> None:
    core, coordinator, node = established_pair()
    node.decrypt_credentials(
        coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    )
    assert node.channel is not None
    invalid = node.channel.encrypt(
        json.dumps(
            {
                "credential_generation": 3,
                "node_id": NODE_ID,
                "schema": "gh.pair.delivery-ack/1",
                "stored": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
        content_type="gh.pair.delivery-ack/1",
    )

    with pytest.raises(SecureEnvelopeRejected, match="contract rejected"):
        coordinator.acknowledge_encrypted_delivery(
            SESSION_ID,
            invalid,
            now=NOW,
        )
    assert core.ack_calls == 0


def test_abort_rolls_back_and_closes_channel() -> None:
    core, coordinator, _node = established_pair()
    coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)
    assert coordinator.abort(SESSION_ID).state == SecurePairingState.FAILED
    assert core.abort_calls == 1
    with pytest.raises(SecurePairingConflict):
        coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)


def test_expiry_closes_channel_and_marks_session_expired() -> None:
    core, coordinator, _node = established_pair()
    assert coordinator.expire_sessions(
        now=NOW + timedelta(seconds=121)
    ) == 1
    assert core.expire_calls == 1
    assert coordinator.status(SESSION_ID).state == SecurePairingState.EXPIRED


def test_envelope_parser_rejects_unknown_fields() -> None:
    document: dict[str, Any] = {
        "schema": "gh.pair.envelope/1",
        "session_id": SESSION_ID,
        "direction": MANAGER_TO_NODE,
        "sequence": 0,
        "content_type": "gh.pair.credentials/1",
        "nonce": b64(b"\x00" * 12),
        "ciphertext": b64(b"ciphertext"),
        "extra": True,
    }
    with pytest.raises(SecureEnvelopeRejected, match="fields are invalid"):
        SecureEnvelope.from_document(document)
