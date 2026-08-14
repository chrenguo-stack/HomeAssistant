from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.ops.n3w_relay_authorization_admin import RelayAuthorizationAdmin
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.n3w_product_peer_authorization import (
    EndpointHandshake,
    PeerAuthorizationRejected,
    PeerAuthorizationRequest,
    PeerAuthorizationService,
    ProductNodeApplicationKeyProvider,
    RegistrationMembershipResolver,
    RelayEligibilitySnapshot,
    RelayRuntimeHealth,
    SqlitePeerAuthorizationReplayStore,
    build_endpoint_proof,
    derive_pair_lmk,
    derive_relay_auth_key,
    verify_endpoint_grant,
)
from greenhouse_manager.runtime.n3w_relay_authorization import SqliteRelayAuthorizationProvider
from greenhouse_manager.runtime.n3w_relay_ingress import RelayIngressRejected
from greenhouse_manager.runtime.registration import RegistrationRegistry

SYSTEM_ID = "gh-system-01"
NOW = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
NOW_MS = 1_723_611_600_000
CHILD_HW = "ghw-c6-98a316a9f2f8"
RELAY_HW = "ghw-c6-aabbccddeeff"
CHILD_NODE = "gh-child-01"
RELAY_NODE = "gh-relay-01"
CHILD_PAIRING = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
RELAY_PAIRING = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
CHILD_KEY = bytes(range(32))
RELAY_KEY = bytes(range(32, 64))


def _hello(*, hardware_id: str, pairing_id: str, epoch: int) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": epoch,
        "hardware_id": hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "n3w-product-relay"],
        "sent_at_ms": 120345,
    }


class _KeyProvider:
    def __init__(self) -> None:
        self.keys = {
            (CHILD_NODE, 1): CHILD_KEY,
            (RELAY_NODE, 1): RELAY_KEY,
        }

    def resolve_node_application_key(self, *, node_id: str, key_epoch: int) -> bytes:
        return self.keys[(node_id, key_epoch)]


class _Eligibility:
    def __init__(self) -> None:
        self.snapshot = RelayEligibilitySnapshot(
            registered=True,
            same_system=True,
            wifi_up=True,
            uplink_available=True,
            direct_uplink=True,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
            retired=False,
            revoked=False,
            valid_until_ms=NOW_MS + 60_000,
        )

    def get_relay_eligibility(
        self,
        *,
        system_id: str,
        node_id: str,
        health: RelayRuntimeHealth,
        now_ms: int,
    ) -> RelayEligibilitySnapshot:
        assert system_id == SYSTEM_ID
        assert node_id == RELAY_NODE
        assert health.observed_at_ms == NOW_MS
        assert now_ms >= NOW_MS
        return self.snapshot


def _raw_private(key: X25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


def _raw_public(key: X25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


@pytest.fixture
def integrated(tmp_path: Path):
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    credentials = CredentialLifecycleStore(tmp_path / "credentials.sqlite3")
    replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-replay.sqlite3"))
    try:
        registry.observe_hello(
            _hello(hardware_id=CHILD_HW, pairing_id=CHILD_PAIRING, epoch=1),
            now=NOW,
        )
        registry.approve(CHILD_HW, CHILD_PAIRING, node_id=CHILD_NODE, now=NOW)
        credentials.activate(
            hardware_id=CHILD_HW,
            pairing_id=CHILD_PAIRING,
            node_id=CHILD_NODE,
            generation=1,
            now=NOW,
        )

        registry.observe_hello(
            _hello(hardware_id=RELAY_HW, pairing_id=RELAY_PAIRING, epoch=1),
            now=NOW,
        )
        registry.approve(RELAY_HW, RELAY_PAIRING, node_id=RELAY_NODE, now=NOW)
        credentials.activate(
            hardware_id=RELAY_HW,
            pairing_id=RELAY_PAIRING,
            node_id=RELAY_NODE,
            generation=1,
            now=NOW,
        )

        keys = _KeyProvider()
        membership = RegistrationMembershipResolver(
            registry,
            credentials,
            keys,
            system_id=SYSTEM_ID,
        )
        eligibility = _Eligibility()
        service = PeerAuthorizationService(
            membership,
            eligibility,
            replay,
            grant_ttl_ms=30_000,
            authorization_epoch=7,
            uuid_factory=lambda: UUID("12345678-1234-5678-1234-567812345678"),
        )
        yield registry, credentials, membership, eligibility, service
    finally:
        replay.close()
        credentials.close()
        registry.close()


def _unsigned_request() -> tuple[PeerAuthorizationRequest, X25519PrivateKey, X25519PrivateKey]:
    child_private = X25519PrivateKey.generate()
    relay_private = X25519PrivateKey.generate()
    request = PeerAuthorizationRequest(
        system_id=SYSTEM_ID,
        session_id="session-0001",
        requested_at_ms=NOW_MS,
        child=EndpointHandshake(
            node_id=CHILD_NODE,
            credential_generation=1,
            key_epoch=1,
            ephemeral_public_key=_raw_public(child_private),
            nonce=b"c" * 32,
        ),
        relay=EndpointHandshake(
            node_id=RELAY_NODE,
            credential_generation=1,
            key_epoch=1,
            ephemeral_public_key=_raw_public(relay_private),
            nonce=b"r" * 32,
        ),
        relay_health=RelayRuntimeHealth(
            observed_at_ms=NOW_MS,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
        ),
    )
    return request, child_private, relay_private


def _signed_request(membership: RegistrationMembershipResolver):
    request, child_private, relay_private = _unsigned_request()
    child = membership.resolve(
        system_id=SYSTEM_ID,
        node_id=CHILD_NODE,
        credential_generation=1,
        key_epoch=1,
    )
    relay = membership.resolve(
        system_id=SYSTEM_ID,
        node_id=RELAY_NODE,
        credential_generation=1,
        key_epoch=1,
    )
    child_auth = derive_relay_auth_key(child)
    relay_auth = derive_relay_auth_key(relay)
    child_proof = build_endpoint_proof(request, role="child", relay_auth_key=child_auth)
    relay_proof = build_endpoint_proof(request, role="relay", relay_auth_key=relay_auth)
    request = replace(
        request,
        child=replace(request.child, proof=child_proof),
        relay=replace(request.relay, proof=relay_proof),
    )
    return request, child_private, relay_private, child_auth, relay_auth


def test_registered_same_system_nodes_receive_bound_short_lived_grants(integrated) -> None:
    _, _, membership, _, service = integrated
    request, _, _, child_auth, relay_auth = _signed_request(membership)

    authorization = service.authorize(request, now_ms=NOW_MS)

    child = authorization.child_grant
    relay = authorization.relay_grant
    assert child.authorization_id == relay.authorization_id
    assert child.authorization_epoch == relay.authorization_epoch == 7
    assert child.system_id == relay.system_id == SYSTEM_ID
    assert child.child_node_id == relay.child_node_id == CHILD_NODE
    assert child.relay_node_id == relay.relay_node_id == RELAY_NODE
    assert child.expires_at_ms == relay.expires_at_ms == NOW_MS + 30_000
    assert verify_endpoint_grant(child, relay_auth_key=child_auth, now_ms=NOW_MS + 1)
    assert verify_endpoint_grant(relay, relay_auth_key=relay_auth, now_ms=NOW_MS + 1)
    assert not verify_endpoint_grant(child, relay_auth_key=relay_auth, now_ms=NOW_MS + 1)
    assert not verify_endpoint_grant(child, relay_auth_key=child_auth, now_ms=child.expires_at_ms)


def test_both_endpoints_derive_same_pair_specific_16_byte_lmk(integrated) -> None:
    _, _, membership, _, service = integrated
    request, child_private, relay_private, _, _ = _signed_request(membership)
    authorization = service.authorize(request, now_ms=NOW_MS)

    child_lmk = derive_pair_lmk(
        local_private_key=_raw_private(child_private),
        peer_public_key=request.relay.ephemeral_public_key,
        grant=authorization.child_grant,
    )
    relay_lmk = derive_pair_lmk(
        local_private_key=_raw_private(relay_private),
        peer_public_key=request.child.ephemeral_public_key,
        grant=authorization.relay_grant,
    )

    assert child_lmk == relay_lmk
    assert len(child_lmk) == 16
    assert child_lmk not in {CHILD_KEY[:16], RELAY_KEY[:16]}


def test_request_replay_is_rejected_persistently(integrated) -> None:
    _, _, membership, _, service = integrated
    request, *_ = _signed_request(membership)
    service.authorize(request, now_ms=NOW_MS)

    with pytest.raises(PeerAuthorizationRejected, match="request_replayed"):
        service.authorize(request, now_ms=NOW_MS + 1)


def test_replay_remains_blocked_after_short_grant_expires_while_request_is_fresh(integrated) -> None:
    _, _, membership, eligibility, service = integrated
    eligibility.snapshot = replace(eligibility.snapshot, valid_until_ms=NOW_MS + 2_000)
    request, *_ = _signed_request(membership)
    authorization = service.authorize(request, now_ms=NOW_MS)
    assert authorization.child_grant.expires_at_ms == NOW_MS + 2_000

    eligibility.snapshot = replace(eligibility.snapshot, valid_until_ms=NOW_MS + 60_000)
    with pytest.raises(PeerAuthorizationRejected, match="request_replayed"):
        service.authorize(request, now_ms=NOW_MS + 3_000)


def test_product_key_provider_needs_no_static_gateway_node_grant(tmp_path: Path) -> None:
    database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    with RelayAuthorizationAdmin(
        database,
        key_dir,
        node_state=lambda _node_id: "active",
    ) as admin:
        staged = admin.stage_key(node_id=CHILD_NODE, key_material=CHILD_KEY)
        key_epoch = staged["key_epoch"]
        assert key_epoch == 1
        admin.activate_key(node_id=CHILD_NODE, key_epoch=key_epoch)
        assert admin.audit()["enabled_gateway_grant_count"] == 0

    with ProductNodeApplicationKeyProvider(database, key_dir) as product:
        assert product.resolve_node_application_key(node_id=CHILD_NODE, key_epoch=1) == CHILD_KEY

    with SqliteRelayAuthorizationProvider(database, key_dir) as legacy:
        with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
            legacy.resolve_key(
                gateway_id=RELAY_NODE,
                node_id=CHILD_NODE,
                key_epoch=1,
            )


def test_cross_system_and_wrong_credential_generation_fail_closed(integrated) -> None:
    _, _, membership, _, _ = integrated

    with pytest.raises(PeerAuthorizationRejected, match="cross_system_rejected"):
        membership.resolve(
            system_id="gh-system-02",
            node_id=CHILD_NODE,
            credential_generation=1,
            key_epoch=1,
        )

    with pytest.raises(PeerAuthorizationRejected, match="credential_generation_rejected"):
        membership.resolve(
            system_id=SYSTEM_ID,
            node_id=CHILD_NODE,
            credential_generation=2,
            key_epoch=1,
        )


def test_retired_or_revoked_node_cannot_be_authorized(integrated) -> None:
    registry, credentials, membership, _, _ = integrated
    registry.retire(CHILD_HW, system_id=SYSTEM_ID, now=NOW)
    with pytest.raises(PeerAuthorizationRejected, match="node_not_active"):
        membership.resolve(
            system_id=SYSTEM_ID,
            node_id=CHILD_NODE,
            credential_generation=1,
            key_epoch=1,
        )

    credentials.revoke(RELAY_HW, now=NOW)
    with pytest.raises(PeerAuthorizationRejected, match="credential_generation_rejected"):
        membership.resolve(
            system_id=SYSTEM_ID,
            node_id=RELAY_NODE,
            credential_generation=1,
            key_epoch=1,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("registered", False),
        ("same_system", False),
        ("wifi_up", False),
        ("uplink_available", False),
        ("direct_uplink", False),
        ("relay_capable", False),
        ("low_battery", True),
        ("overloaded", True),
        ("retired", True),
        ("revoked", True),
    ],
)
def test_every_frozen_relay_eligibility_condition_fails_closed(integrated, field: str, value: bool) -> None:
    _, _, membership, eligibility, service = integrated
    request, *_ = _signed_request(membership)
    eligibility.snapshot = replace(eligibility.snapshot, **{field: value})

    with pytest.raises(PeerAuthorizationRejected, match="relay_not_eligible"):
        service.authorize(request, now_ms=NOW_MS)


def test_endpoint_proofs_are_role_and_pair_bound(integrated) -> None:
    _, _, membership, _, service = integrated
    request, _, _, child_auth, _ = _signed_request(membership)
    forged_relay = replace(
        request.relay,
        proof=build_endpoint_proof(request, role="relay", relay_auth_key=child_auth),
    )
    request = replace(request, relay=forged_relay)

    with pytest.raises(PeerAuthorizationRejected, match="relay_proof_rejected"):
        service.authorize(request, now_ms=NOW_MS)