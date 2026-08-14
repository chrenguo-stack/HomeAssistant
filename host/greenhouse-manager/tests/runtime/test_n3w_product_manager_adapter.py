from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.n3w_path_lease import N3wPathLeaseCoordinator, PathLeasePolicy, PathOwner
from greenhouse_manager.runtime.n3w_product_manager_adapter import (
    ManagerRelayEligibilityProvider,
    PeerAuthorizationMqttAdapter,
    ReplayRegistryPathAuthority,
    encode_peer_authorization_request,
)
from greenhouse_manager.runtime.n3w_product_peer_authorization import (
    EndpointHandshake,
    PeerAuthorizationRejected,
    PeerAuthorizationRequest,
    PeerAuthorizationService,
    RegistrationMembershipResolver,
    RelayRuntimeHealth,
    SqlitePeerAuthorizationReplayStore,
    build_endpoint_proof,
    derive_relay_auth_key,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

NOW = datetime(2026, 8, 14, 6, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)
SYSTEM_ID = "gh-system-01"
CHILD_HW = "ghw-c6-98a316a9f2f8"
RELAY_HW = "ghw-c6-aabbccddeeff"
CHILD_NODE = "gh-child-01"
RELAY_NODE = "gh-relay-01"
CHILD_PAIRING = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
RELAY_PAIRING = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
CHILD_KEY = bytes(range(32))
RELAY_KEY = bytes(range(32, 64))
BOOT = "boot_0000000000000001"


class _Keys:
    def resolve_node_application_key(self, *, node_id: str, key_epoch: int) -> bytes:
        assert key_epoch == 1
        return {CHILD_NODE: CHILD_KEY, RELAY_NODE: RELAY_KEY}[node_id]


def _hello(*, hardware_id: str, pairing_id: str) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "n3w-product-relay"],
        "sent_at_ms": 120345,
    }


def _public(private: X25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


@pytest.fixture
def manager_stack(tmp_path: Path):
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    credentials = CredentialLifecycleStore(tmp_path / "credentials.sqlite3")
    replay = ReplayRegistry(tmp_path / "replay.sqlite3")
    peer_replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-replay.sqlite3"))
    try:
        for hardware_id, pairing_id, node_id in (
            (CHILD_HW, CHILD_PAIRING, CHILD_NODE),
            (RELAY_HW, RELAY_PAIRING, RELAY_NODE),
        ):
            registry.observe_hello(_hello(hardware_id=hardware_id, pairing_id=pairing_id), now=NOW)
            registry.approve(hardware_id, pairing_id, node_id=node_id, now=NOW)
            credentials.activate(
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                node_id=node_id,
                generation=1,
                now=NOW,
            )

        path = N3wPathLeaseCoordinator(
            replay_registry=replay,
            policy=PathLeasePolicy(
                stability_window_s=0,
                minimum_distinct_frames=1,
                lease_ttl_s=30,
                old_path_grace_s=2,
            ),
            ingress_allowed=registry.is_node_id_ingress_allowed,
        )
        accepted = path.process(
            node_id=RELAY_NODE,
            boot_id=BOOT,
            seq=1,
            owner=PathOwner("direct"),
            now=NOW,
        )
        assert accepted.status == "accepted"

        membership = RegistrationMembershipResolver(
            registry,
            credentials,
            _Keys(),
            system_id=SYSTEM_ID,
        )
        eligibility = ManagerRelayEligibilityProvider(
            registry,
            ReplayRegistryPathAuthority(replay),
            system_id=SYSTEM_ID,
            max_health_age_ms=15_000,
        )
        service = PeerAuthorizationService(
            membership,
            eligibility,
            peer_replay,
            grant_ttl_ms=30_000,
            authorization_epoch=9,
            uuid_factory=lambda: UUID("12345678-1234-5678-1234-567812345678"),
        )
        adapter = PeerAuthorizationMqttAdapter(service)
        yield registry, replay, membership, eligibility, adapter
    finally:
        peer_replay.close()
        replay.close()
        credentials.close()
        registry.close()


def _signed_request(membership: RegistrationMembershipResolver, *, now_ms: int = NOW_MS):
    child_private = X25519PrivateKey.generate()
    relay_private = X25519PrivateKey.generate()
    request = PeerAuthorizationRequest(
        system_id=SYSTEM_ID,
        session_id=f"session-{now_ms}",
        requested_at_ms=now_ms,
        child=EndpointHandshake(
            node_id=CHILD_NODE,
            credential_generation=1,
            key_epoch=1,
            ephemeral_public_key=_public(child_private),
            nonce=b"c" * 32,
        ),
        relay=EndpointHandshake(
            node_id=RELAY_NODE,
            credential_generation=1,
            key_epoch=1,
            ephemeral_public_key=_public(relay_private),
            nonce=b"r" * 32,
        ),
        relay_health=RelayRuntimeHealth(
            observed_at_ms=now_ms,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
        ),
    )
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
    request = replace(
        request,
        child=replace(
            request.child,
            proof=build_endpoint_proof(
                request,
                role="child",
                relay_auth_key=derive_relay_auth_key(child),
            ),
        ),
        relay=replace(
            request.relay,
            proof=build_endpoint_proof(
                request,
                role="relay",
                relay_auth_key=derive_relay_auth_key(relay),
            ),
        ),
    )
    return request


def _resign(request: PeerAuthorizationRequest, membership: RegistrationMembershipResolver):
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
    unsigned = replace(
        request,
        child=replace(request.child, proof=b""),
        relay=replace(request.relay, proof=b""),
    )
    return replace(
        unsigned,
        child=replace(
            unsigned.child,
            proof=build_endpoint_proof(
                unsigned,
                role="child",
                relay_auth_key=derive_relay_auth_key(child),
            ),
        ),
        relay=replace(
            unsigned.relay,
            proof=build_endpoint_proof(
                unsigned,
                role="relay",
                relay_auth_key=derive_relay_auth_key(relay),
            ),
        ),
    )


def test_manager_eligibility_requires_live_canonical_direct_path(manager_stack) -> None:
    _, _, _, eligibility, _ = manager_stack
    health = RelayRuntimeHealth(
        observed_at_ms=NOW_MS,
        relay_capable=True,
        low_battery=False,
        overloaded=False,
    )
    snapshot = eligibility.get_relay_eligibility(
        system_id=SYSTEM_ID,
        node_id=RELAY_NODE,
        health=health,
        now_ms=NOW_MS,
    )
    assert snapshot.registered is True
    assert snapshot.same_system is True
    assert snapshot.wifi_up is True
    assert snapshot.uplink_available is True
    assert snapshot.direct_uplink is True
    assert snapshot.relay_capable is True
    assert snapshot.valid_until_ms == NOW_MS + 15_000

    expired = eligibility.get_relay_eligibility(
        system_id=SYSTEM_ID,
        node_id=RELAY_NODE,
        health=replace(health, observed_at_ms=NOW_MS + 31_000),
        now_ms=NOW_MS + 31_000,
    )
    assert expired.direct_uplink is False
    assert expired.eligible_at(NOW_MS + 31_000) is False


def test_mqtt_adapter_uses_existing_relay_node_acl_subtrees_and_returns_bound_grants(manager_stack) -> None:
    _, _, membership, _, adapter = manager_stack
    request = _signed_request(membership)
    request_topic = adapter.request_topic(system_id=SYSTEM_ID, relay_node_id=RELAY_NODE)

    response_topic, response_payload = adapter.handle(
        topic=request_topic,
        payload=encode_peer_authorization_request(request),
        now_ms=NOW_MS,
    )
    response = json.loads(response_payload)

    assert response_topic == (
        f"gh/v1/{SYSTEM_ID}/out/node/{RELAY_NODE}/relay-peer-auth/{request.session_id}"
    )
    assert response["schema"] == "gh.n3w-product.peer-auth-response/1"
    assert response["child_grant"]["child_node_id"] == CHILD_NODE
    assert response["relay_grant"]["relay_node_id"] == RELAY_NODE
    assert response["child_grant"]["authorization_id"] == response["relay_grant"]["authorization_id"]
    assert response["child_grant"]["expires_at_ms"] == NOW_MS + 15_000
    assert "application_key" not in response_payload.decode()
    assert "lmk" not in response_payload.decode().lower()


def test_mqtt_topic_identity_mismatch_fails_closed(manager_stack) -> None:
    _, _, membership, _, adapter = manager_stack
    request = _signed_request(membership)
    wrong_topic = adapter.request_topic(system_id=SYSTEM_ID, relay_node_id="gh-other-relay")
    with pytest.raises(PeerAuthorizationRejected, match="mqtt_topic_identity_mismatch"):
        adapter.handle(
            topic=wrong_topic,
            payload=encode_peer_authorization_request(request),
            now_ms=NOW_MS,
        )


def test_stale_signed_relay_health_fails_closed(manager_stack) -> None:
    _, _, membership, _, adapter = manager_stack
    request = _signed_request(membership)
    request = replace(
        request,
        relay_health=replace(request.relay_health, observed_at_ms=NOW_MS - 16_000),
    )
    request = _resign(request, membership)

    with pytest.raises(PeerAuthorizationRejected, match="relay_not_eligible"):
        adapter.handle(
            topic=adapter.request_topic(system_id=SYSTEM_ID, relay_node_id=RELAY_NODE),
            payload=encode_peer_authorization_request(request),
            now_ms=NOW_MS,
        )


def test_expired_direct_path_cannot_authorize_relay_even_with_fresh_signed_health(manager_stack) -> None:
    _, _, membership, _, adapter = manager_stack
    later = int((NOW + timedelta(seconds=31)).timestamp() * 1000)
    request = _signed_request(membership, now_ms=later)

    with pytest.raises(PeerAuthorizationRejected, match="relay_not_eligible"):
        adapter.handle(
            topic=adapter.request_topic(system_id=SYSTEM_ID, relay_node_id=RELAY_NODE),
            payload=encode_peer_authorization_request(request),
            now_ms=later,
        )
