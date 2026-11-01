from __future__ import annotations

import sys
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "greenhouse-manager" / "src"))

from greenhouse_manager.runtime.n3w_product_peer_authorization import (  # noqa: E402
    EndpointHandshake,
    NodeMembership,
    PeerAuthorizationRejected,
    PeerAuthorizationRequest,
    PeerAuthorizationService,
    RelayEligibilitySnapshot,
    RelayRuntimeHealth,
    SqlitePeerAuthorizationReplayStore,
    build_endpoint_proof,
    derive_pair_lmk,
    derive_relay_auth_key,
    verify_endpoint_grant,
)


NOW_MS = 1_786_689_000_100
REQUESTED_AT_MS = 1_786_689_000_000
AUTHORIZATION_ID = "11111111-2222-3333-4444-555555555555"


def _bytes(hex_value: str) -> bytes:
    return bytes.fromhex(hex_value)


def _public(private_key: bytes) -> bytes:
    return (
        X25519PrivateKey.from_private_bytes(private_key)
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )


CHILD_PRIVATE = _bytes(
    "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
)
RELAY_PRIVATE = _bytes(
    "2122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f40"
)
CHILD_NONCE = _bytes(
    "4142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60"
)
RELAY_NONCE = _bytes(
    "6162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f80"
)
CHILD_MEMBERSHIP = NodeMembership(
    system_id="system001",
    hardware_id="hardware_child01",
    node_id="node_child01",
    credential_generation=1,
    key_epoch=1,
    application_key=_bytes(
        "8182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9fa0"
    ),
)
RELAY_MEMBERSHIP = NodeMembership(
    system_id="system001",
    hardware_id="hardware_relay01",
    node_id="node_relay01",
    credential_generation=2,
    key_epoch=3,
    application_key=_bytes(
        "a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebfc0"
    ),
)


class StaticMembershipResolver:
    def resolve(
        self,
        *,
        system_id: str,
        node_id: str,
        credential_generation: int,
        key_epoch: int,
    ) -> NodeMembership:
        if system_id != "system001":
            raise PeerAuthorizationRejected("cross_system_rejected")
        matches = [
            membership
            for membership in (CHILD_MEMBERSHIP, RELAY_MEMBERSHIP)
            if membership.node_id == node_id
            and membership.credential_generation == credential_generation
            and membership.key_epoch == key_epoch
        ]
        if len(matches) != 1:
            raise PeerAuthorizationRejected("credential_generation_rejected")
        return matches[0]


class StaticEligibilityProvider:
    def get_relay_eligibility(
        self,
        *,
        system_id: str,
        node_id: str,
        health: RelayRuntimeHealth,
        now_ms: int,
    ) -> RelayEligibilitySnapshot:
        if system_id != "system001":
            raise PeerAuthorizationRejected("cross_system_rejected")
        if node_id != RELAY_MEMBERSHIP.node_id:
            raise PeerAuthorizationRejected("relay_not_eligible")
        assert health.relay_capable is True
        assert health.low_battery is False
        assert health.overloaded is False
        return RelayEligibilitySnapshot(
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
            valid_until_ms=1_786_689_030_000,
        )


class RevokedEligibilityProvider(StaticEligibilityProvider):
    def get_relay_eligibility(
        self,
        *,
        system_id: str,
        node_id: str,
        health: RelayRuntimeHealth,
        now_ms: int,
    ) -> RelayEligibilitySnapshot:
        current = super().get_relay_eligibility(
            system_id=system_id,
            node_id=node_id,
            health=health,
            now_ms=now_ms,
        )
        return replace(current, revoked=True)


def _request() -> PeerAuthorizationRequest:
    child_auth = derive_relay_auth_key(CHILD_MEMBERSHIP)
    relay_auth = derive_relay_auth_key(RELAY_MEMBERSHIP)
    unsigned = PeerAuthorizationRequest(
        system_id="system001",
        session_id="s5-session-0001",
        requested_at_ms=REQUESTED_AT_MS,
        child=EndpointHandshake(
            node_id=CHILD_MEMBERSHIP.node_id,
            credential_generation=CHILD_MEMBERSHIP.credential_generation,
            key_epoch=CHILD_MEMBERSHIP.key_epoch,
            ephemeral_public_key=_public(CHILD_PRIVATE),
            nonce=CHILD_NONCE,
        ),
        relay=EndpointHandshake(
            node_id=RELAY_MEMBERSHIP.node_id,
            credential_generation=RELAY_MEMBERSHIP.credential_generation,
            key_epoch=RELAY_MEMBERSHIP.key_epoch,
            ephemeral_public_key=_public(RELAY_PRIVATE),
            nonce=RELAY_NONCE,
        ),
        relay_health=RelayRuntimeHealth(
            observed_at_ms=1_786_688_999_000,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
        ),
    )
    return replace(
        unsigned,
        child=replace(
            unsigned.child,
            proof=build_endpoint_proof(unsigned, role="child", relay_auth_key=child_auth),
        ),
        relay=replace(
            unsigned.relay,
            proof=build_endpoint_proof(unsigned, role="relay", relay_auth_key=relay_auth),
        ),
    )


def _service(
    replay: SqlitePeerAuthorizationReplayStore,
    *,
    eligibility: StaticEligibilityProvider | None = None,
) -> PeerAuthorizationService:
    return PeerAuthorizationService(
        StaticMembershipResolver(),
        eligibility or StaticEligibilityProvider(),
        replay,
        grant_ttl_ms=29_900,
        max_request_skew_ms=10_000,
        authorization_epoch=7,
        uuid_factory=lambda: uuid.UUID(AUTHORIZATION_ID),
    )


def test_actual_manager_service_grants_match_endpoint_crypto_and_replay_contract(tmp_path: Path) -> None:
    replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-replay.sqlite3"))
    service = _service(replay)
    request = _request()
    authorization = service.authorize(request, now_ms=NOW_MS)

    child_auth = derive_relay_auth_key(CHILD_MEMBERSHIP)
    relay_auth = derive_relay_auth_key(RELAY_MEMBERSHIP)
    assert authorization.child_grant.authorization_id == AUTHORIZATION_ID
    assert authorization.relay_grant.authorization_id == AUTHORIZATION_ID
    assert authorization.child_grant.expires_at_ms == 1_786_689_030_000
    assert authorization.relay_grant.expires_at_ms == 1_786_689_030_000
    assert authorization.child_grant.grant_mac.hex() == (
        "49263fe315de3a170592be8b56cb0183c62d6a721ee12f961bc30f8faf280cc8"
    )
    assert authorization.relay_grant.grant_mac.hex() == (
        "d4172a3446782ffd863155900224f14fb48a9741eed2cc286a027d711c055f04"
    )
    assert verify_endpoint_grant(
        authorization.child_grant, relay_auth_key=child_auth, now_ms=NOW_MS + 100
    )
    assert verify_endpoint_grant(
        authorization.relay_grant, relay_auth_key=relay_auth, now_ms=NOW_MS + 100
    )

    child_lmk = derive_pair_lmk(
        local_private_key=CHILD_PRIVATE,
        peer_public_key=request.relay.ephemeral_public_key,
        grant=authorization.child_grant,
    )
    relay_lmk = derive_pair_lmk(
        local_private_key=RELAY_PRIVATE,
        peer_public_key=request.child.ephemeral_public_key,
        grant=authorization.relay_grant,
    )
    assert child_lmk == relay_lmk
    assert child_lmk.hex() == "aaebd482e2dec5346c9d11b00ad9c3fb"
    assert child_lmk != bytes(16)

    tampered_epoch = replace(authorization.child_grant, authorization_epoch=8)
    assert not verify_endpoint_grant(
        tampered_epoch, relay_auth_key=child_auth, now_ms=NOW_MS + 100
    )
    tampered_generation = replace(
        authorization.child_grant,
        relay_credential_generation=authorization.child_grant.relay_credential_generation + 1,
    )
    assert not verify_endpoint_grant(
        tampered_generation, relay_auth_key=child_auth, now_ms=NOW_MS + 100
    )
    tampered_key_epoch = replace(
        authorization.child_grant,
        relay_key_epoch=authorization.child_grant.relay_key_epoch + 1,
    )
    assert not verify_endpoint_grant(
        tampered_key_epoch, relay_auth_key=child_auth, now_ms=NOW_MS + 100
    )
    assert not verify_endpoint_grant(
        authorization.child_grant,
        relay_auth_key=child_auth,
        now_ms=authorization.child_grant.expires_at_ms,
    )

    with pytest.raises(PeerAuthorizationRejected, match="request_replayed"):
        service.authorize(request, now_ms=NOW_MS + 200)

    stale = replace(
        request,
        session_id="s5-session-stale",
        requested_at_ms=NOW_MS - 10_001,
    )
    with pytest.raises(PeerAuthorizationRejected, match="request_stale"):
        service.authorize(stale, now_ms=NOW_MS)

    cross_system = replace(
        request,
        system_id="system999",
        session_id="s5-session-cross",
    )
    with pytest.raises(PeerAuthorizationRejected, match="cross_system_rejected"):
        service.authorize(cross_system, now_ms=NOW_MS)

    wrong_child_generation = replace(
        request,
        session_id="s5-session-child-generation",
        child=replace(
            request.child,
            credential_generation=request.child.credential_generation + 1,
        ),
    )
    with pytest.raises(PeerAuthorizationRejected, match="credential_generation_rejected"):
        service.authorize(wrong_child_generation, now_ms=NOW_MS)

    wrong_relay_generation = replace(
        request,
        session_id="s5-session-relay-generation",
        relay=replace(
            request.relay,
            credential_generation=request.relay.credential_generation + 1,
        ),
    )
    with pytest.raises(PeerAuthorizationRejected, match="credential_generation_rejected"):
        service.authorize(wrong_relay_generation, now_ms=NOW_MS)

    wrong_key_epoch = replace(
        request,
        session_id="s5-session-key-epoch",
        relay=replace(request.relay, key_epoch=request.relay.key_epoch + 1),
    )
    with pytest.raises(PeerAuthorizationRejected, match="credential_generation_rejected"):
        service.authorize(wrong_key_epoch, now_ms=NOW_MS)

    replay.close()


def test_request_replay_survives_manager_replay_store_restart(tmp_path: Path) -> None:
    database = tmp_path / "peer-replay.sqlite3"
    request = _request()

    first_replay = SqlitePeerAuthorizationReplayStore(str(database))
    first = _service(first_replay)
    first.authorize(request, now_ms=NOW_MS)
    first_replay.close()

    reopened_replay = SqlitePeerAuthorizationReplayStore(str(database))
    reopened = _service(reopened_replay)
    try:
        with pytest.raises(PeerAuthorizationRejected, match="request_replayed"):
            reopened.authorize(request, now_ms=NOW_MS + 200)
    finally:
        reopened_replay.close()


def test_revoked_relay_eligibility_fails_closed_before_grant_issue(tmp_path: Path) -> None:
    replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-replay.sqlite3"))
    service = _service(replay, eligibility=RevokedEligibilityProvider())
    try:
        with pytest.raises(PeerAuthorizationRejected, match="relay_not_eligible"):
            service.authorize(_request(), now_ms=NOW_MS)
    finally:
        replay.close()
