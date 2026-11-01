from __future__ import annotations

from dataclasses import replace

import pytest
from cryptography.exceptions import InvalidTag

from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
    decrypt_credential_bundle,
    derive_bootstrap_key,
    encrypt_credential_bundle,
    verify_setup_proof,
)

SETUP_SECRET = bytes(range(32))
TRANSCRIPT = PairingTranscript(
    pairing_id="pairing-0001",
    hardware_id="ghw-c6-98a316a9f2f8",
    manager_id="manager-01",
    node_nonce=bytes.fromhex("000102030405060708090a0b0c0d0e0f"),
    manager_nonce=bytes.fromhex("101112131415161718191a1b1c1d1e1f"),
)
AEAD_NONCE = bytes.fromhex("202122232425262728292a2b")
PLAINTEXT = b'{"mqtt":"credential","peer_trust_generation":7}'


def test_bootstrap_key_has_stable_cross_language_vector() -> None:
    assert derive_bootstrap_key(SETUP_SECRET, TRANSCRIPT).hex() == (
        "245cd6779140823149f1f338418155b6159515074f44c847cbefa779148b6442"
    )


def test_node_and_manager_proofs_have_stable_cross_language_vectors() -> None:
    assert build_setup_proof(SETUP_SECRET, TRANSCRIPT, role="node").hex() == (
        "5ee6550d20a489b5d60901158f63728a37a8faaf81c927d100dd2a20e0ea39fa"
    )
    assert build_setup_proof(SETUP_SECRET, TRANSCRIPT, role="manager").hex() == (
        "8d070768337a1f279fc667c8b8e7f1dac2a917a002d99931ed78b72af30c89b4"
    )


def test_setup_proof_verifies_and_wrong_secret_fails() -> None:
    proof = build_setup_proof(SETUP_SECRET, TRANSCRIPT, role="node")

    assert verify_setup_proof(
        SETUP_SECRET,
        TRANSCRIPT,
        role="node",
        proof=proof,
    )
    assert not verify_setup_proof(
        b"x" * 32,
        TRANSCRIPT,
        role="node",
        proof=proof,
    )


def test_changed_transcript_rejects_old_setup_proof() -> None:
    proof = build_setup_proof(SETUP_SECRET, TRANSCRIPT, role="manager")
    changed = replace(
        TRANSCRIPT,
        manager_nonce=b"z" * 16,
    )

    assert not verify_setup_proof(
        SETUP_SECRET,
        changed,
        role="manager",
        proof=proof,
    )


def test_credential_bundle_round_trip_and_stable_vector() -> None:
    key = derive_bootstrap_key(SETUP_SECRET, TRANSCRIPT)
    ciphertext = encrypt_credential_bundle(
        key,
        TRANSCRIPT,
        nonce=AEAD_NONCE,
        plaintext=PLAINTEXT,
    )

    assert ciphertext.hex() == (
        "ce6b1a415414bc949bb884cc78231ecd6ed87b83cb3e8d6a52ad4fe3d1708dc"
        "3d576fbe76e645fe0f1ebb5b05b4b9c83369cac871d430d709a3f46e297a370"
    )
    assert decrypt_credential_bundle(
        key,
        TRANSCRIPT,
        nonce=AEAD_NONCE,
        ciphertext=ciphertext,
    ) == PLAINTEXT


def test_bundle_tamper_fails_closed() -> None:
    key = derive_bootstrap_key(SETUP_SECRET, TRANSCRIPT)
    ciphertext = encrypt_credential_bundle(
        key,
        TRANSCRIPT,
        nonce=AEAD_NONCE,
        plaintext=PLAINTEXT,
    )
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0x01])

    with pytest.raises(InvalidTag):
        decrypt_credential_bundle(
            key,
            TRANSCRIPT,
            nonce=AEAD_NONCE,
            ciphertext=tampered,
        )


def test_transcript_change_changes_key_and_breaks_decryption() -> None:
    key = derive_bootstrap_key(SETUP_SECRET, TRANSCRIPT)
    ciphertext = encrypt_credential_bundle(
        key,
        TRANSCRIPT,
        nonce=AEAD_NONCE,
        plaintext=PLAINTEXT,
    )
    changed = replace(
        TRANSCRIPT,
        node_nonce=b"y" * 16,
    )
    changed_key = derive_bootstrap_key(SETUP_SECRET, changed)

    assert changed_key != key
    with pytest.raises(InvalidTag):
        decrypt_credential_bundle(
            changed_key,
            changed,
            nonce=AEAD_NONCE,
            ciphertext=ciphertext,
        )


@pytest.mark.parametrize(
    "secret",
    [b"", b"x" * 16, b"x" * 31, b"x" * 33],
)
def test_setup_secret_must_be_32_bytes(secret: bytes) -> None:
    with pytest.raises(ValueError, match="setup secret"):
        derive_bootstrap_key(secret, TRANSCRIPT)


def test_invalid_pairing_role_fails_closed() -> None:
    with pytest.raises(ValueError, match="role"):
        build_setup_proof(SETUP_SECRET, TRANSCRIPT, role="relay")

    assert not verify_setup_proof(
        SETUP_SECRET,
        TRANSCRIPT,
        role="relay",
        proof=b"x" * 32,
    )
