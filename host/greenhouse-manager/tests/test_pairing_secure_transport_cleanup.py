from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.pairing_secure_transport import (
    CIPHER_SUITE,
    SecurePairingConflict,
    SecurePairingCoordinator,
    SecurePairingOffer,
    SecurePairingState,
    _SecureSession,
    build_secure_pairing_proof,
    public_key_text,
)
from greenhouse_manager.pairing_service import (
    CredentialBundle,
    PairingOffer,
    PairingSessionSnapshot,
    PairingSessionState,
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


class CleanupCore:
    def __init__(self) -> None:
        self.abort_calls = 0
        self.verify_fails = False
        self.offer = PairingOffer(
            schema="gh.pair.offer/1",
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            manager_nonce=MANAGER_NONCE,
            expires_at=NOW + timedelta(seconds=120),
            max_proof_attempts=3,
        )
        self.bundle = CredentialBundle(
            schema="gh.pair.credentials/1",
            system_id="greenhouse",
            node_id=NODE_ID,
            broker_host="mqtt.greenhouse.local",
            broker_port=8883,
            broker_tls_server_name="mqtt.greenhouse.local",
            ca_pem="TEST-CA",
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
        return self.offer

    def verify_proof(
        self,
        session_id: str,
        *,
        proof: str,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        if self.verify_fails:
            raise RuntimeError("injected core proof failure")
        return self.snapshot(PairingSessionState.PROOF_VERIFIED)

    def issue_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> CredentialBundle:
        return self.bundle

    def acknowledge_delivery(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        return self.snapshot(PairingSessionState.CONSUMED)

    def abort(self, session_id: str) -> PairingSessionSnapshot:
        self.abort_calls += 1
        return self.snapshot(PairingSessionState.FAILED)

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        return 0

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        return self.snapshot(PairingSessionState.OPEN)

    def snapshot(
        self,
        state: PairingSessionState,
    ) -> PairingSessionSnapshot:
        return PairingSessionSnapshot(
            session_id=SESSION_ID,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            state=state,
            expires_at=self.offer.expires_at,
            proof_attempts=1,
            credential_generation=None,
        )


class FailingChannel:
    def __init__(self) -> None:
        self.closed = False

    def encrypt(self, plaintext: bytes, *, content_type: str) -> None:
        raise RuntimeError("injected encryption failure")

    def close(self) -> None:
        self.closed = True


def test_core_proof_failure_aborts_and_clears_secure_session() -> None:
    core = CleanupCore()
    core.verify_fails = True
    coordinator = SecurePairingCoordinator(
        core,
        private_key_factory=lambda: X25519PrivateKey.from_private_bytes(
            bytes([0x11]) * 32
        ),
    )
    offer = coordinator.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    node_private = X25519PrivateKey.from_private_bytes(bytes([0x22]) * 32)
    node_public = public_key_text(node_private)
    proof = build_secure_pairing_proof(
        pairing_secret=PAIRING_SECRET,
        offer=offer,
        node_nonce=NODE_NONCE,
        node_public_key=node_public,
    )

    with pytest.raises(
        SecurePairingConflict,
        match="core proof verification failed",
    ):
        coordinator.establish_channel(
            SESSION_ID,
            node_nonce=NODE_NONCE,
            node_public_key=node_public,
            proof=proof,
            now=NOW,
        )

    assert core.abort_calls == 1
    assert coordinator.status(SESSION_ID).state == SecurePairingState.FAILED


def test_encryption_failure_rolls_back_issued_identity() -> None:
    core = CleanupCore()
    coordinator = SecurePairingCoordinator(core)
    secure_offer = SecurePairingOffer(
        schema="gh.pair.secure-offer/1",
        session_id=SESSION_ID,
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_ID,
        manager_nonce=MANAGER_NONCE,
        manager_public_key=b64(bytes([0x33]) * 32),
        cipher_suite=CIPHER_SUITE,
        expires_at=core.offer.expires_at,
        max_proof_attempts=3,
    )
    channel = FailingChannel()
    coordinator._sessions[SESSION_ID] = _SecureSession(
        core_offer=core.offer,
        offer=secure_offer,
        secret=bytearray(),
        private_key=None,
        state=SecurePairingState.CHANNEL_ESTABLISHED,
        channel=channel,
    )

    with pytest.raises(
        SecurePairingConflict,
        match="credential encryption failed",
    ):
        coordinator.issue_encrypted_credentials(SESSION_ID, now=NOW)

    assert core.abort_calls == 1
    assert channel.closed is True
    assert coordinator.status(SESSION_ID).state == SecurePairingState.FAILED
