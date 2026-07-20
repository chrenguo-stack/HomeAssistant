from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from greenhouse_manager.pairing_service import (
    PairingConflict,
    PairingExpired,
    PairingProofRejected,
    PairingSessionManager,
    PairingSessionState,
    build_pairing_proof,
)
from greenhouse_manager.registration import RegistrationState

NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"
NODE_NONCE = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
PAIRING_SECRET = base64.urlsafe_b64encode(bytes(reversed(range(32)))).rstrip(b"=").decode()


class Registry:
    def __init__(self) -> None:
        self.record = SimpleNamespace(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            pairing_epoch=3,
            node_nonce=NODE_NONCE,
            state=RegistrationState.PENDING,
            node_id=None,
            expires_at=NOW + timedelta(seconds=120),
        )

    def get(self, hardware_id: str) -> SimpleNamespace:
        if hardware_id != HARDWARE_ID:
            raise KeyError(hardware_id)
        return self.record

    def approve(self) -> None:
        self.record.state = RegistrationState.APPROVED
        self.record.node_id = NODE_ID


class Provisioner:
    def __init__(self) -> None:
        self.provisioned = []
        self.deprovisioned = []
        self.fail_provision = False
        self.fail_deprovision = False

    def provision(self, plan, credentials) -> None:
        if self.fail_provision:
            raise RuntimeError("secret broker details")
        self.provisioned.append((plan, credentials))

    def deprovision(self, plan) -> None:
        if self.fail_deprovision:
            raise RuntimeError("secret rollback details")
        self.deprovisioned.append(plan)


@pytest.fixture
def context():
    registry = Registry()
    provisioner = Provisioner()
    manager = PairingSessionManager(
        registry,
        provisioner,
        system_id="greenhouse",
        broker_host="mqtt.greenhouse.local",
        broker_port=8883,
        broker_tls_server_name="mqtt.greenhouse.local",
        ca_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
        session_ttl_s=120,
        max_proof_attempts=3,
        random_bytes=lambda size: b"M" * size,
        uuid_factory=lambda: UUID("5449b33c-3e77-47ad-96ee-df7274cabfd1"),
    )
    return registry, provisioner, manager


def open_and_prove(manager: PairingSessionManager):
    offer = manager.open_session(
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
    snapshot = manager.verify_proof(
        offer.session_id,
        proof=proof,
        now=NOW + timedelta(seconds=1),
    )
    return offer, snapshot


def test_opens_single_use_session_without_exposing_secret(context) -> None:
    _registry, _provisioner, manager = context

    offer = manager.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )

    assert offer.schema == "gh.pair.offer/1"
    assert offer.manager_nonce == base64.urlsafe_b64encode(b"M" * 32).rstrip(b"=").decode()
    assert PAIRING_SECRET not in repr(offer)
    with pytest.raises(PairingConflict, match="one-time session"):
        manager.open_session(
            HARDWARE_ID,
            PAIRING_ID,
            pairing_secret=PAIRING_SECRET,
            now=NOW,
        )


def test_verifies_proof_once_and_rejects_replay(context) -> None:
    _registry, _provisioner, manager = context

    offer, snapshot = open_and_prove(manager)

    assert snapshot.state == PairingSessionState.PROOF_VERIFIED
    assert snapshot.proof_attempts == 1
    proof = build_pairing_proof(
        pairing_secret=PAIRING_SECRET,
        offer=offer,
        node_nonce=NODE_NONCE,
    )
    with pytest.raises(PairingConflict, match="proof cannot be verified"):
        manager.verify_proof(offer.session_id, proof=proof, now=NOW)


def test_wrong_proof_locks_session_after_three_attempts(context) -> None:
    _registry, _provisioner, manager = context
    offer = manager.open_session(
        HARDWARE_ID,
        PAIRING_ID,
        pairing_secret=PAIRING_SECRET,
        now=NOW,
    )
    wrong = base64.urlsafe_b64encode(b"X" * 32).rstrip(b"=").decode()

    for _ in range(3):
        with pytest.raises(PairingProofRejected):
            manager.verify_proof(
                offer.session_id,
                proof=wrong,
                now=NOW,
            )

    assert manager.status(offer.session_id, now=NOW).state == PairingSessionState.FAILED


def test_credentials_require_explicit_approval_and_are_idempotent(context) -> None:
    registry, provisioner, manager = context
    offer, _snapshot = open_and_prove(manager)

    with pytest.raises(PairingConflict, match="explicit operator approval"):
        manager.issue_credentials(offer.session_id, now=NOW)

    registry.approve()
    first = manager.issue_credentials(offer.session_id, now=NOW)
    second = manager.issue_credentials(offer.session_id, now=NOW)

    assert first is second
    assert first.node_id == NODE_ID
    assert first.credential_generation == 3
    assert first.mqtt_client_id == NODE_ID
    assert first.mqtt_password not in repr(first)
    assert len(provisioner.provisioned) == 1

    consumed = manager.acknowledge_delivery(offer.session_id, now=NOW)
    assert consumed.state == PairingSessionState.CONSUMED
    assert consumed.credential_generation == 3
    with pytest.raises(PairingConflict, match="verified proof"):
        manager.issue_credentials(offer.session_id, now=NOW)


def test_abort_rolls_back_issued_identity(context) -> None:
    registry, provisioner, manager = context
    offer, _snapshot = open_and_prove(manager)
    registry.approve()
    manager.issue_credentials(offer.session_id, now=NOW)

    result = manager.abort(offer.session_id)

    assert result.state == PairingSessionState.FAILED
    assert len(provisioner.deprovisioned) == 1


def test_expiration_rejects_proof_and_clears_session(context) -> None:
    _registry, _provisioner, manager = context
    offer = manager.open_session(
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

    with pytest.raises(PairingExpired):
        manager.verify_proof(
            offer.session_id,
            proof=proof,
            now=NOW + timedelta(seconds=121),
        )
    assert manager.status(
        offer.session_id,
        now=NOW + timedelta(seconds=121),
    ).state == PairingSessionState.EXPIRED


def test_provisioning_failure_is_sanitized(context) -> None:
    registry, provisioner, manager = context
    offer, _snapshot = open_and_prove(manager)
    registry.approve()
    provisioner.fail_provision = True

    with pytest.raises(RuntimeError) as captured:
        manager.issue_credentials(offer.session_id, now=NOW)

    assert "secret broker details" not in str(captured.value)
    assert PAIRING_SECRET not in str(captured.value)
