from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.ops.n3w_pairing_cli import parser
from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialLifecycleStore,
    CredentialState,
)
from greenhouse_manager.runtime.n3w_node_credentials import (
    ManagedApplicationKeyLifecycle,
    ManagedMqttCredentialLifecycle,
    ManagedProductCredentialIssuer,
)
from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    CREDENTIAL_RECOVERY_RESPONSE_SCHEMA,
    ManagerOwnedPairingSocket,
    authorize_credential_recovery_over_socket,
)
from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
)
from greenhouse_manager.runtime.n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
    SimplifiedProductCredentialBundle,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
    SimplifiedPairingState,
)
from greenhouse_manager.runtime.n3w_simplified_provisioning import (
    SimplifiedProvisioningStager,
)
from greenhouse_manager.runtime.pairing_service import PairingRollbackError
from greenhouse_manager.runtime.registration import (
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 9, 1, 2, 30, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000b"
NODE_ID = "node_22222222222222222222222222222222"
PAIRING_1 = "11111111-1111-4111-8111-111111111111"
PAIRING_2 = "22222222-2222-4222-8222-222222222222"
SETUP_SECRET = bytes(range(32))
APPLICATION_KEY = bytes([0x55]) * 32
SYSTEM_PEER_KEY = bytes([0xAA]) * 32


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(
        value + "=" * ((4 - len(value) % 4) % 4)
    )


def _hello(pairing_id: str) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": _b64(bytes([0x31]) * 32),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


class _PairingRandom:
    def __call__(self, size: int) -> bytes:
        if size == 16:
            return bytes([0x41]) * 16
        if size == 12:
            return bytes([0x51]) * 12
        raise AssertionError(size)


@dataclass
class _FakeStaged:
    bundle: SimplifiedProductCredentialBundle
    committed: bool = False
    rolled_back: bool = False

    def commit(self, *, now=None) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _RecoveryAwareStager:
    def __init__(self) -> None:
        self.first_registration_calls = 0
        self.recovery_calls: list[tuple[str, str, str]] = []
        self.last: _FakeStaged | None = None

    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> _FakeStaged:
        self.first_registration_calls += 1
        raise AssertionError("registered recovery entered first-registration staging")

    def stage_recovery(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
    ) -> _FakeStaged:
        self.recovery_calls.append((hardware_id, pairing_id, node_id))
        self.last = _FakeStaged(
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
                credential_generation=2,
                n3w_key_epoch=4,
                peer_trust_generation=3,
                mqtt_password="replacement-secret",
                n3w_application_key=_b64(APPLICATION_KEY),
                system_peer_key=SYSTEM_PEER_KEY,
            )
        )
        return self.last


def _prepare_registered(registry: RegistrationRegistry) -> None:
    registry.observe_hello(_hello(PAIRING_1), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_1,
        node_id=NODE_ID,
        now=NOW,
    )


def _open_authenticated_repair_session(
    coordinator: SimplifiedPairingCoordinator,
    registry: RegistrationRegistry,
    *,
    recovery: bool,
):
    if recovery:
        coordinator.authorize_credential_recovery(
            HARDWARE_ID,
            PAIRING_2,
            now=NOW + timedelta(seconds=1),
        )
    else:
        registry.authorize_repair(
            HARDWARE_ID,
            PAIRING_2,
            now=NOW + timedelta(seconds=1),
        )

    observed = registry.observe_hello(
        _hello(PAIRING_2),
        now=NOW + timedelta(seconds=2),
    )
    assert observed.status == "superseded"
    assert observed.record.node_id == NODE_ID

    coordinator.import_setup_secret(
        HARDWARE_ID,
        PAIRING_2,
        setup_secret=SETUP_SECRET,
    )
    node_nonce = bytes([0x61]) * 16
    offer = coordinator.begin(
        HARDWARE_ID,
        PAIRING_2,
        node_nonce=_b64(node_nonce),
        now=NOW + timedelta(seconds=3),
    )
    transcript = PairingTranscript(
        pairing_id=PAIRING_2,
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
    return offer, _b64(proof)


def test_ordinary_registered_repair_still_stops_before_credential_staging(
    tmp_path,
) -> None:
    stager = _RecoveryAwareStager()
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        _prepare_registered(registry)
        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_recovery_test",
            random_bytes=_PairingRandom(),
        )
        offer, proof = _open_authenticated_repair_session(
            coordinator,
            registry,
            recovery=False,
        )

        with pytest.raises(
            SimplifiedPairingConflict,
            match="credential_recovery_required",
        ):
            coordinator.establish(
                offer.session_id,
                node_proof=proof,
                now=NOW + timedelta(seconds=4),
            )

        assert stager.first_registration_calls == 0
        assert stager.recovery_calls == []
        assert registry.get(HARDWARE_ID).node_id == NODE_ID


def test_explicit_credential_recovery_preserves_node_and_commits_on_receipt(
    tmp_path,
) -> None:
    stager = _RecoveryAwareStager()
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        _prepare_registered(registry)
        coordinator = SimplifiedPairingCoordinator(
            registry,
            stager,
            manager_id="manager_recovery_test",
            random_bytes=_PairingRandom(),
        )
        offer, proof = _open_authenticated_repair_session(
            coordinator,
            registry,
            recovery=True,
        )

        issued = coordinator.establish(
            offer.session_id,
            node_proof=proof,
            now=NOW + timedelta(seconds=4),
        )

        assert issued.node_id == NODE_ID
        assert stager.first_registration_calls == 0
        assert stager.recovery_calls == [
            (HARDWARE_ID, PAIRING_2, NODE_ID)
        ]
        assert stager.last is not None
        assert stager.last.committed is False

        snapshot = coordinator.acknowledge(
            offer.session_id,
            delivery_digest=issued.delivery_digest,
            now=NOW + timedelta(seconds=5),
        )

        assert snapshot.state is SimplifiedPairingState.CONSUMED
        assert snapshot.node_id == NODE_ID
        assert stager.last.committed is True
        current = registry.get(HARDWARE_ID)
        assert current.node_id == NODE_ID
        assert current.state is RegistrationState.APPROVED


@dataclass(frozen=True)
class _PeerCredential:
    system_id: str
    generation: int
    key: bytes


class _PeerTrust:
    def __init__(self) -> None:
        self.calls = 0

    def get_or_create(self, system_id: str, *, now=None) -> _PeerCredential:
        self.calls += 1
        return _PeerCredential(
            system_id=system_id,
            generation=3,
            key=SYSTEM_PEER_KEY,
        )


class _IdentityProvisioner:
    def __init__(self) -> None:
        self.password_updates = []

    def set_password(self, plan, credentials) -> None:
        self.password_updates.append((plan, credentials))

    def provision(self, plan, credentials) -> None:
        raise AssertionError("recovery must not create a second Broker identity")

    def deprovision(self, plan) -> None:
        raise AssertionError("recovery must not delete the existing Broker identity")


def _build_recovery_stager(tmp_path):
    store = CredentialLifecycleStore(tmp_path / "credential-lifecycle.sqlite3")
    store.activate(
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_1,
        node_id=NODE_ID,
        generation=1,
        now=NOW,
    )
    mqtt = ManagedMqttCredentialLifecycle(store)
    application = ManagedApplicationKeyLifecycle(object())
    product = ManagedProductCredentialIssuer(application, mqtt)
    peer_trust = _PeerTrust()
    identity = _IdentityProvisioner()
    stager = SimplifiedProvisioningStager(
        identity_provisioner=identity,
        product_issuer=product,
        simplified_issuer=SimplifiedCredentialBundleIssuer(peer_trust),
        system_id="gh-system-01",
        broker_host="mqtt.greenhouse.local",
        broker_port=8883,
        broker_tls_server_name="mqtt.greenhouse.local",
        ca_pem=(
            "-----BEGIN CERTIFICATE-----\n"
            "TEST\n"
            "-----END CERTIFICATE-----\n"
        ),
    )
    stager._read_active_application_key = lambda node_id: (4, APPLICATION_KEY)
    return store, product, peer_trust, identity, stager


def test_recovery_stage_defers_broker_mutation_and_reuses_application_key(
    tmp_path,
) -> None:
    store, _product, peer_trust, identity, stager = _build_recovery_stager(
        tmp_path
    )
    try:
        staged = stager.stage_recovery(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_2,
            node_id=NODE_ID,
        )

        rotating = store.get(HARDWARE_ID)
        assert rotating.state is CredentialState.ROTATING
        assert rotating.active_generation == 1
        assert rotating.pending_generation == 2
        assert identity.password_updates == []
        assert staged.bundle.node_id == NODE_ID
        assert staged.bundle.credential_generation == 2
        assert staged.bundle.n3w_key_epoch == 4
        assert staged.bundle.n3w_application_key == _b64(APPLICATION_KEY)
        assert peer_trust.calls == 1

        staged.commit(now=NOW + timedelta(seconds=1))

        active = store.get(HARDWARE_ID)
        assert len(identity.password_updates) == 1
        assert active.state is CredentialState.ACTIVE
        assert active.active_generation == 2
        assert active.pending_generation is None
    finally:
        store.close()


def test_recovery_abort_before_receipt_preserves_old_active_generation(
    tmp_path,
) -> None:
    store, _product, _peer_trust, identity, stager = _build_recovery_stager(
        tmp_path
    )
    try:
        staged = stager.stage_recovery(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_2,
            node_id=NODE_ID,
        )
        staged.rollback()

        current = store.get(HARDWARE_ID)
        assert current.state is CredentialState.ACTIVE
        assert current.active_generation == 1
        assert current.pending_generation is None
        assert identity.password_updates == []
    finally:
        store.close()


def test_recovery_is_fail_closed_after_broker_password_applied(
    tmp_path,
) -> None:
    store, product, _peer_trust, identity, stager = _build_recovery_stager(
        tmp_path
    )
    try:
        staged = stager.stage_recovery(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_2,
            node_id=NODE_ID,
        )

        def fail_commit(*args, **kwargs):
            raise RuntimeError("synthetic_lifecycle_commit_failure")

        product.mqtt_credentials.commit_rotation = fail_commit

        with pytest.raises(
            RuntimeError,
            match="synthetic_lifecycle_commit_failure",
        ):
            staged.commit(now=NOW + timedelta(seconds=1))

        assert len(identity.password_updates) == 1
        assert staged.broker_password_applied is True
        with pytest.raises(
            PairingRollbackError,
            match="broker password already applied",
        ):
            staged.rollback()

        unresolved = store.get(HARDWARE_ID)
        assert unresolved.state is CredentialState.ROTATING
        assert unresolved.active_generation == 1
        assert unresolved.pending_generation == 2
    finally:
        store.close()


class _IpcCoordinator:
    def __init__(self, *, reject_recovery: bool = False) -> None:
        self.recovery_calls = []
        self.reject_recovery = reject_recovery

    def import_setup_secret(self, hardware_id, pairing_id, *, setup_secret):
        raise AssertionError("not used")

    def authorize_repair(self, hardware_id, pairing_id):
        raise AssertionError("not used")

    def authorize_credential_recovery(self, hardware_id, pairing_id):
        self.recovery_calls.append((hardware_id, pairing_id))
        if self.reject_recovery:
            raise RuntimeError("synthetic_recovery_rejection")


def test_credential_recovery_authorization_uses_manager_owned_ipc(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    os.chmod(runtime, 0o700)
    socket_path = runtime / "pairing.sock"
    coordinator = _IpcCoordinator()
    server = ManagerOwnedPairingSocket(coordinator, socket_path)
    server.start()
    try:
        result = authorize_credential_recovery_over_socket(
            socket_path,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_2,
        )
    finally:
        server.stop()

    assert result == {
        "accepted": True,
        "code": "credential_recovery_authorized",
        "schema": CREDENTIAL_RECOVERY_RESPONSE_SCHEMA,
    }
    assert coordinator.recovery_calls == [(HARDWARE_ID, PAIRING_2)]


def test_credential_recovery_ipc_rejection_keeps_operation_schema(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    os.chmod(runtime, 0o700)
    socket_path = runtime / "pairing.sock"
    server = ManagerOwnedPairingSocket(
        _IpcCoordinator(reject_recovery=True),
        socket_path,
    )
    server.start()
    try:
        result = authorize_credential_recovery_over_socket(
            socket_path,
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_2,
        )
    finally:
        server.stop()

    assert result["accepted"] is False
    assert result["code"] == "rejected"
    assert result["schema"] == CREDENTIAL_RECOVERY_RESPONSE_SCHEMA


def test_pairing_cli_exposes_explicit_credential_recovery_authorization() -> None:
    args = parser().parse_args(
        [
            "authorize-credential-recovery",
            "--hardware-id",
            HARDWARE_ID,
            "--pairing-id",
            PAIRING_2,
        ]
    )
    assert args.command == "authorize-credential-recovery"
    assert args.hardware_id == HARDWARE_ID
    assert args.pairing_id == PAIRING_2
