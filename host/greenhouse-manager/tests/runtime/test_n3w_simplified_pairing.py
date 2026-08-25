from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
    decrypt_credential_bundle,
    derive_bootstrap_key,
    verify_setup_proof,
)
from greenhouse_manager.runtime.n3w_simplified_credentials import (
    SimplifiedProductCredentialBundle,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
    SimplifiedPairingState,
)
from greenhouse_manager.runtime.registration import (
    NodeIdLeaseState,
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SETUP_SECRET = bytes(range(32))


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))


class RoutedRandom:
    def __init__(self) -> None:
        self.node_nonce = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.manager_nonce = bytes.fromhex("102132435465768798a9babbdcddedef")
        self.node_id_material = bytes.fromhex("11111111111111111111111111111111")
        self.aead_nonce = bytes.fromhex("0102030405060708090a0b0c")
        self.calls16 = 0

    def __call__(self, size: int) -> bytes:
        if size == 16:
            self.calls16 += 1
            return self.manager_nonce if self.calls16 == 1 else self.node_id_material
        if size == 12:
            return self.aead_nonce
        raise AssertionError(size)


@dataclass
class FakeStaged:
    bundle: SimplifiedProductCredentialBundle
    committed: bool = False
    rolled_back: bool = False

    def commit(self, *, now=None) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeStager:
    def __init__(self) -> None:
        self.last: FakeStaged | None = None
        self.stage_calls = 0

    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> FakeStaged:
        self.stage_calls += 1
        assert hardware_id == HARDWARE_ID
        assert pairing_id == PAIRING_ID
        self.last = FakeStaged(
            SimplifiedProductCredentialBundle(
                system_id="gh-system-01",
                node_id=node_id,
                broker_host="mqtt.greenhouse.local",
                broker_port=8883,
                broker_tls_server_name="mqtt.greenhouse.local",
                ca_pem=(
                    "-----BEGIN CERTIFICATE-----\n"
                    "TEST\n"
                    "-----END CERTIFICATE-----\n"
                ),
                mqtt_username=f"ghn_{node_id}",
                mqtt_client_id=node_id,
                credential_generation=credential_generation,
                n3w_key_epoch=1,
                peer_trust_generation=3,
                mqtt_password="mqtt-secret",
                n3w_application_key=b64(bytes([0x55]) * 32),
                system_peer_key=bytes([0xAA]) * 32,
            )
        )
        return self.last


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": b64(bytes([0x31]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


def test_setup_secret_pairing_auto_assigns_node_and_encrypts_complete_bundle(
    tmp_path,
) -> None:
    random = RoutedRandom()
    stager = FakeStager()
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        registry.observe_hello(hello(), now=NOW)
        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_lab_01",
            random_bytes=random,
        )
        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )
        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_ID,
            node_nonce=b64(random.node_nonce),
            now=NOW,
        )
        transcript = PairingTranscript(
            pairing_id=PAIRING_ID,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=random.node_nonce,
            manager_nonce=unb64(offer.manager_nonce),
        )
        assert verify_setup_proof(
            SETUP_SECRET,
            transcript,
            role="manager",
            proof=unb64(offer.manager_proof),
        )
        node_proof = build_setup_proof(SETUP_SECRET, transcript, role="node")
        encrypted = coordinator.establish(
            offer.session_id,
            node_proof=b64(node_proof),
            now=NOW,
        )
        assert encrypted.node_id == "node_11111111111111111111111111111111"
        plaintext = decrypt_credential_bundle(
            derive_bootstrap_key(SETUP_SECRET, transcript),
            transcript,
            nonce=unb64(encrypted.nonce),
            ciphertext=unb64(encrypted.ciphertext),
        )
        assert b'"schema":"gh.pair.credentials/2"' in plaintext
        assert b'"system_peer_key":"' in plaintext
        assert encrypted.node_id.encode() in plaintext
        snapshot = coordinator.acknowledge(
            offer.session_id,
            delivery_digest=encrypted.delivery_digest,
            now=NOW,
        )
        assert snapshot.state is SimplifiedPairingState.CONSUMED
        assert stager.last is not None and stager.last.committed is True
        assert stager.last.rolled_back is False



def test_registered_pairing_requires_explicit_credential_recovery_before_staging(
    tmp_path,
) -> None:
    random = RoutedRandom()
    stager = FakeStager()
    registered_node_id = "node_22222222222222222222222222222222"
    repair_pairing_id = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"

    with RegistrationRegistry(
        tmp_path / "registration.sqlite3"
    ) as registry:
        registry.observe_hello(
            hello(),
            now=NOW,
        )
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=registered_node_id,
            now=NOW,
        )

        repair_hello = hello()
        repair_hello["pairing_id"] = repair_pairing_id
        registry.authorize_repair(
            HARDWARE_ID,
            repair_pairing_id,
            now=NOW,
        )
        observed = registry.observe_hello(
            repair_hello,
            now=NOW,
        )

        assert observed.record.node_id == registered_node_id

        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_lab_01",
            random_bytes=random,
        )

        coordinator.import_setup_secret(
            HARDWARE_ID,
            repair_pairing_id,
            setup_secret=SETUP_SECRET,
        )

        offer = coordinator.begin(
            HARDWARE_ID,
            repair_pairing_id,
            node_nonce=b64(random.node_nonce),
            now=NOW,
        )

        transcript = PairingTranscript(
            pairing_id=repair_pairing_id,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=random.node_nonce,
            manager_nonce=unb64(offer.manager_nonce),
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
                node_proof=b64(proof),
                now=NOW,
            )

        current = registry.get(HARDWARE_ID)

        assert current.node_id == registered_node_id
        assert current.pairing_id == repair_pairing_id
        assert current.state is RegistrationState.PENDING

        # Most important C2 invariant: ordinary registered pairing never
        # reaches Broker credential or application-key staging.
        assert stager.stage_calls == 0


def test_invalid_node_proof_never_allocates_node_id_or_stages_credentials(
    tmp_path,
) -> None:
    random = RoutedRandom()
    stager = FakeStager()
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        registry.observe_hello(hello(), now=NOW)
        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_lab_01",
            random_bytes=random,
        )
        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )
        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_ID,
            node_nonce=b64(random.node_nonce),
            now=NOW,
        )
        try:
            coordinator.establish(
                offer.session_id,
                node_proof=b64(bytes([0xFF]) * 32),
                now=NOW,
            )
        except RuntimeError as error:
            assert str(error) == "node_proof_rejected"
        else:
            raise AssertionError("invalid proof unexpectedly accepted")
        record = registry.get(HARDWARE_ID)
        assert record.node_id is None
        assert stager.last is None



class FailingSimplifiedStager:
    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ):
        raise RuntimeError(
            "synthetic_stage_failure"
        )


def test_stage_failure_rolls_automatic_approval_back_to_pending(
    tmp_path,
) -> None:
    random = RoutedRandom()

    with RegistrationRegistry(
        tmp_path / "registration.sqlite3"
    ) as registry:
        registry.observe_hello(
            hello(),
            now=NOW,
        )

        coordinator = SimplifiedPairingCoordinator(
            registry,
            FailingSimplifiedStager(),
            manager_id="manager_lab_01",
            random_bytes=random,
        )

        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )

        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_ID,
            node_nonce=b64(
                random.node_nonce
            ),
            now=NOW,
        )

        transcript = PairingTranscript(
            pairing_id=PAIRING_ID,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=random.node_nonce,
            manager_nonce=unb64(
                offer.manager_nonce
            ),
        )

        proof = build_setup_proof(
            SETUP_SECRET,
            transcript,
            role="node",
        )

        allocated = (
            "node_"
            "11111111111111111111111111111111"
        )

        with pytest.raises(
            RuntimeError,
            match="synthetic_stage_failure",
        ):
            coordinator.establish(
                offer.session_id,
                node_proof=b64(proof),
                now=NOW,
            )

        record = registry.get(
            HARDWARE_ID
        )

        assert (
            record.state
            is RegistrationState.PENDING
        )
        assert record.node_id is None

        assert (
            registry.node_id_lease_state(
                allocated
            )
            is NodeIdLeaseState.RETIRED
        )

        assert any(
            event.event
            == "automatic_approval_rolled_back"
            for event
            in registry.list_events(
                hardware_id=HARDWARE_ID
            )
        )


def test_abort_after_credentials_issued_rolls_registration_back(
    tmp_path,
) -> None:
    random = RoutedRandom()
    stager = FakeStager()

    with RegistrationRegistry(
        tmp_path / "registration.sqlite3"
    ) as registry:
        registry.observe_hello(
            hello(),
            now=NOW,
        )

        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_lab_01",
            random_bytes=random,
        )

        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )

        offer = coordinator.begin(
            HARDWARE_ID,
            PAIRING_ID,
            node_nonce=b64(
                random.node_nonce
            ),
            now=NOW,
        )

        transcript = PairingTranscript(
            pairing_id=PAIRING_ID,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=random.node_nonce,
            manager_nonce=unb64(
                offer.manager_nonce
            ),
        )

        proof = build_setup_proof(
            SETUP_SECRET,
            transcript,
            role="node",
        )

        issued = coordinator.establish(
            offer.session_id,
            node_proof=b64(proof),
            now=NOW,
        )

        allocated = issued.node_id

        assert (
            registry.get(
                HARDWARE_ID
            ).state
            is RegistrationState.APPROVED
        )

        snapshot = coordinator.abort(
            offer.session_id
        )

        assert (
            snapshot.state
            is SimplifiedPairingState.FAILED
        )
        assert snapshot.node_id is None

        current = registry.get(
            HARDWARE_ID
        )

        assert (
            current.state
            is RegistrationState.PENDING
        )
        assert current.node_id is None

        assert (
            registry.node_id_lease_state(
                allocated
            )
            is NodeIdLeaseState.RETIRED
        )

        assert stager.last is not None
        assert (
            stager.last.rolled_back
            is True
        )
