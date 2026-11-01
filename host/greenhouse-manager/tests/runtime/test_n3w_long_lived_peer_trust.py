from __future__ import annotations

from dataclasses import replace

import pytest

from greenhouse_manager.runtime.n3w_long_lived_peer_trust import (
    PeerEndpoint,
    SystemPeerCredential,
    build_peer_proof,
    canonical_pair_binding,
    derive_pair_lmk,
    verify_peer_proof,
)

SYSTEM_ID = "gh-system-01"
KEY = bytes(range(32))
CREDENTIAL = SystemPeerCredential(system_id=SYSTEM_ID, generation=7, key=KEY)
CHILD = PeerEndpoint(node_id="gh-child-01", mac=bytes.fromhex("001122334455"))
RELAY = PeerEndpoint(node_id="gh-relay-01", mac=bytes.fromhex("aabbccddeeff"))
OTHER = PeerEndpoint(node_id="gh-relay-02", mac=bytes.fromhex("102030405060"))
BOOT_NONCE = bytes.fromhex("101112131415161718191a1b1c1d1e1f")
CHALLENGE = bytes.fromhex("202122232425262728292a2b2c2d2e2f")


def test_system_peer_credential_repr_redacts_key() -> None:
    rendered = repr(CREDENTIAL)

    assert "key=<redacted>" in rendered
    assert KEY.hex() not in rendered


@pytest.mark.parametrize(
    ("system_id", "generation", "key"),
    [
        ("x", 1, KEY),
        (SYSTEM_ID, 0, KEY),
        (SYSTEM_ID, True, KEY),
        (SYSTEM_ID, 1, b"short"),
    ],
)
def test_invalid_system_peer_credential_rejected(
    system_id: str,
    generation: int,
    key: bytes,
) -> None:
    with pytest.raises(ValueError):
        SystemPeerCredential(system_id=system_id, generation=generation, key=key)


def test_pair_binding_and_lmk_are_order_independent() -> None:
    forward_binding = canonical_pair_binding(CREDENTIAL, first=CHILD, second=RELAY)
    reverse_binding = canonical_pair_binding(CREDENTIAL, first=RELAY, second=CHILD)
    forward_lmk = derive_pair_lmk(CREDENTIAL, first=CHILD, second=RELAY)
    reverse_lmk = derive_pair_lmk(CREDENTIAL, first=RELAY, second=CHILD)

    assert forward_binding == reverse_binding
    assert forward_lmk == reverse_lmk
    assert len(forward_lmk) == 16


def test_pair_lmk_has_stable_cross_language_vector() -> None:
    assert derive_pair_lmk(CREDENTIAL, first=CHILD, second=RELAY).hex() == (
        "fbfe0c8ee9d28f9b13738efd57aed3f2"
    )


def test_different_pairs_have_different_lmk() -> None:
    assert derive_pair_lmk(CREDENTIAL, first=CHILD, second=RELAY) != derive_pair_lmk(
        CREDENTIAL,
        first=CHILD,
        second=OTHER,
    )


def test_generation_change_changes_lmk_without_changing_node_identity() -> None:
    next_generation = replace(CREDENTIAL, generation=CREDENTIAL.generation + 1)

    assert derive_pair_lmk(CREDENTIAL, first=CHILD, second=RELAY) != derive_pair_lmk(
        next_generation,
        first=CHILD,
        second=RELAY,
    )


def test_peer_proof_verifies_without_expiry_or_manager_time() -> None:
    proof = build_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
    )

    assert verify_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
        proof=proof,
    )


def test_peer_proof_has_stable_cross_language_vector() -> None:
    proof = build_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
    )

    assert proof.hex() == "c7b3b00fe36e493467ca53a84af37bb5fddb5a3d582901a2e82d0e72569fb199"


def test_changed_challenge_rejects_replayed_proof() -> None:
    proof = build_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
    )
    changed = bytes([CHALLENGE[0] ^ 0x01]) + CHALLENGE[1:]

    assert not verify_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=changed,
        proof=proof,
    )


def test_wrong_system_peer_key_rejects_proof() -> None:
    proof = build_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
    )
    wrong = replace(CREDENTIAL, key=b"x" * 32)

    assert not verify_peer_proof(
        wrong,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
        proof=proof,
    )


def test_old_generation_rejects_proof_after_rekey() -> None:
    proof = build_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
    )
    new_generation = replace(CREDENTIAL, generation=CREDENTIAL.generation + 1)

    assert not verify_peer_proof(
        new_generation,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
        proof=proof,
    )


def test_endpoint_identity_collisions_are_rejected() -> None:
    same_node = PeerEndpoint(node_id=CHILD.node_id, mac=OTHER.mac)
    same_mac = PeerEndpoint(node_id=OTHER.node_id, mac=CHILD.mac)

    with pytest.raises(ValueError, match="node_id collision"):
        derive_pair_lmk(CREDENTIAL, first=CHILD, second=same_node)
    with pytest.raises(ValueError, match="mac collision"):
        derive_pair_lmk(CREDENTIAL, first=CHILD, second=same_mac)


def test_invalid_proof_shape_fails_closed() -> None:
    assert not verify_peer_proof(
        CREDENTIAL,
        prover=CHILD,
        verifier=RELAY,
        prover_boot_nonce=BOOT_NONCE,
        challenge_nonce=CHALLENGE,
        proof=b"short",
    )
