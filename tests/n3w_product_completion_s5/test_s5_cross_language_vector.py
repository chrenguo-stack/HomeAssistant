from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "greenhouse-manager" / "src"))

from greenhouse_manager.runtime.n3w_product_peer_authorization import (  # noqa: E402
    EndpointGrant,
    EndpointHandshake,
    NodeMembership,
    PeerAuthorizationRequest,
    RelayRuntimeHealth,
    build_endpoint_proof,
    derive_pair_lmk,
    derive_relay_auth_key,
    verify_endpoint_grant,
)


def _bytes(hex_value: str) -> bytes:
    return bytes.fromhex(hex_value)


def test_s5_cross_language_peer_security_vector() -> None:
    child_private = _bytes(
        "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
    )
    relay_private = _bytes(
        "2122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f40"
    )
    child_public = _bytes(
        "07a37cbc142093c8b755dc1b10e86cb426374ad16aa853ed0bdfc0b2b86d1c7c"
    )
    relay_public = _bytes(
        "5869aff450549732cbaaed5e5df9b30a6da31cb0e5742bad5ad4a1a768f1a67b"
    )
    child_nonce = _bytes(
        "4142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60"
    )
    relay_nonce = _bytes(
        "6162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f80"
    )
    child_membership = NodeMembership(
        system_id="system001",
        hardware_id="hardware_child01",
        node_id="node_child01",
        credential_generation=1,
        key_epoch=1,
        application_key=_bytes(
            "8182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9fa0"
        ),
    )
    relay_membership = NodeMembership(
        system_id="system001",
        hardware_id="hardware_relay01",
        node_id="node_relay01",
        credential_generation=2,
        key_epoch=3,
        application_key=_bytes(
            "a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebfc0"
        ),
    )
    child_auth = derive_relay_auth_key(child_membership)
    relay_auth = derive_relay_auth_key(relay_membership)
    assert child_auth.hex() == (
        "ae5c57299e4915e934e7a84d19158b033542fa0418751e5262036c088aea5bd0"
    )
    assert relay_auth.hex() == (
        "af1c7d570a32112cf2221b366fa8eebd4290de97958c0637c188f7c20c2b8bf0"
    )

    request = PeerAuthorizationRequest(
        system_id="system001",
        session_id="s5-session-0001",
        requested_at_ms=1786689000000,
        child=EndpointHandshake(
            node_id="node_child01",
            credential_generation=1,
            key_epoch=1,
            ephemeral_public_key=child_public,
            nonce=child_nonce,
        ),
        relay=EndpointHandshake(
            node_id="node_relay01",
            credential_generation=2,
            key_epoch=3,
            ephemeral_public_key=relay_public,
            nonce=relay_nonce,
        ),
        relay_health=RelayRuntimeHealth(
            observed_at_ms=1786688999000,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
        ),
    )
    assert build_endpoint_proof(request, role="child", relay_auth_key=child_auth).hex() == (
        "01d10498afbfe1c88a50992e614ec1b4c43ef6d715fdb6b1dc7fc1784f653db8"
    )
    assert build_endpoint_proof(request, role="relay", relay_auth_key=relay_auth).hex() == (
        "7cd74be1126de0087da8dad7e2dce68510913c324dd93f0d07d0892a97706801"
    )

    common = dict(
        authorization_id="11111111-2222-3333-4444-555555555555",
        system_id="system001",
        session_id="s5-session-0001",
        child_node_id="node_child01",
        relay_node_id="node_relay01",
        child_credential_generation=1,
        relay_credential_generation=2,
        child_key_epoch=1,
        relay_key_epoch=3,
        child_ephemeral_public_key=child_public,
        relay_ephemeral_public_key=relay_public,
        child_nonce=child_nonce,
        relay_nonce=relay_nonce,
        issued_at_ms=1786689000100,
        expires_at_ms=1786689030000,
        authorization_epoch=7,
    )
    child_grant = EndpointGrant(
        role="child",
        grant_mac=_bytes(
            "49263fe315de3a170592be8b56cb0183c62d6a721ee12f961bc30f8faf280cc8"
        ),
        **common,
    )
    relay_grant = EndpointGrant(
        role="relay",
        grant_mac=_bytes(
            "d4172a3446782ffd863155900224f14fb48a9741eed2cc286a027d711c055f04"
        ),
        **common,
    )
    assert verify_endpoint_grant(
        child_grant, relay_auth_key=child_auth, now_ms=1786689000200
    )
    assert verify_endpoint_grant(
        relay_grant, relay_auth_key=relay_auth, now_ms=1786689000200
    )
    assert not verify_endpoint_grant(
        child_grant, relay_auth_key=relay_auth, now_ms=1786689000200
    )

    child_lmk = derive_pair_lmk(
        local_private_key=child_private,
        peer_public_key=relay_public,
        grant=child_grant,
    )
    relay_lmk = derive_pair_lmk(
        local_private_key=relay_private,
        peer_public_key=child_public,
        grant=relay_grant,
    )
    assert child_lmk == relay_lmk
    assert child_lmk.hex() == "aaebd482e2dec5346c9d11b00ad9c3fb"
