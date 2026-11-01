from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_PAIRING_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_SETUP_SECRET_BYTES = 32
_HANDSHAKE_NONCE_BYTES = 16
_AEAD_NONCE_BYTES = 12
_PROOF_BYTES = 32
_ALLOWED_ROLES = {"node", "manager"}

_BOOTSTRAP_DOMAIN = b"gh.pair.simple-bootstrap/1"


@dataclass(frozen=True, slots=True)
class PairingTranscript:
    """Public pairing fields bound to one one-time Setup Secret."""

    pairing_id: str
    hardware_id: str
    manager_id: str
    node_nonce: bytes
    manager_nonce: bytes

    def __post_init__(self) -> None:
        if _PAIRING_ID.fullmatch(self.pairing_id) is None:
            raise ValueError("pairing_id is invalid")
        if _ID.fullmatch(self.hardware_id) is None:
            raise ValueError("hardware_id is invalid")
        if _ID.fullmatch(self.manager_id) is None:
            raise ValueError("manager_id is invalid")
        _require_nonce(self.node_nonce, "node_nonce")
        _require_nonce(self.manager_nonce, "manager_nonce")
        if self.node_nonce == self.manager_nonce:
            raise ValueError("pairing nonces must be distinct")

    def encode(self) -> bytes:
        fields = (
            _BOOTSTRAP_DOMAIN,
            self.pairing_id.encode("ascii"),
            self.hardware_id.encode("ascii"),
            self.manager_id.encode("ascii"),
            self.node_nonce.hex().encode("ascii"),
            self.manager_nonce.hex().encode("ascii"),
        )
        return b"\x00".join(fields)


def build_setup_proof(
    setup_secret: bytes,
    transcript: PairingTranscript,
    *,
    role: str,
) -> bytes:
    """Prove possession of the scanned one-time Setup Secret."""

    _require_setup_secret(setup_secret)
    if role not in _ALLOWED_ROLES:
        raise ValueError("pairing proof role is invalid")
    message = (
        _BOOTSTRAP_DOMAIN
        + b"\x00proof\x00"
        + role.encode("ascii")
        + b"\x00"
        + transcript.encode()
    )
    return hmac.new(setup_secret, message, hashlib.sha256).digest()


def verify_setup_proof(
    setup_secret: bytes,
    transcript: PairingTranscript,
    *,
    role: str,
    proof: bytes,
) -> bool:
    """Verify proof of Setup Secret possession without logging the secret."""

    if not isinstance(proof, bytes) or len(proof) != _PROOF_BYTES:
        return False
    try:
        expected = build_setup_proof(setup_secret, transcript, role=role)
    except ValueError:
        return False
    return hmac.compare_digest(proof, expected)


def derive_bootstrap_key(
    setup_secret: bytes,
    transcript: PairingTranscript,
) -> bytes:
    """Derive the one-time AES-256-GCM key for the credential bundle."""

    _require_setup_secret(setup_secret)
    encoded = transcript.encode()
    salt = hashlib.sha256(
        _BOOTSTRAP_DOMAIN + b"\x00salt\x00" + encoded
    ).digest()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_BOOTSTRAP_DOMAIN + b"\x00key\x00" + encoded,
    ).derive(setup_secret)


def encrypt_credential_bundle(
    bootstrap_key: bytes,
    transcript: PairingTranscript,
    *,
    nonce: bytes,
    plaintext: bytes,
) -> bytes:
    """Encrypt one credential bundle with transcript-bound authenticated data."""

    _require_bootstrap_key(bootstrap_key)
    _require_aead_nonce(nonce)
    if not isinstance(plaintext, bytes) or not plaintext:
        raise ValueError("credential bundle plaintext is invalid")
    return AESGCM(bootstrap_key).encrypt(
        nonce,
        plaintext,
        transcript.encode(),
    )


def decrypt_credential_bundle(
    bootstrap_key: bytes,
    transcript: PairingTranscript,
    *,
    nonce: bytes,
    ciphertext: bytes,
) -> bytes:
    """Decrypt and authenticate one transcript-bound credential bundle."""

    _require_bootstrap_key(bootstrap_key)
    _require_aead_nonce(nonce)
    if not isinstance(ciphertext, bytes) or len(ciphertext) < 16:
        raise ValueError("credential bundle ciphertext is invalid")
    return AESGCM(bootstrap_key).decrypt(
        nonce,
        ciphertext,
        transcript.encode(),
    )


def _require_setup_secret(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) != _SETUP_SECRET_BYTES:
        raise ValueError("setup secret must be 32 bytes")


def _require_bootstrap_key(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValueError("bootstrap key must be 32 bytes")


def _require_nonce(value: bytes, label: str) -> None:
    if not isinstance(value, bytes) or len(value) != _HANDSHAKE_NONCE_BYTES:
        raise ValueError(f"{label} must be 16 bytes")


def _require_aead_nonce(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) != _AEAD_NONCE_BYTES:
        raise ValueError("AES-GCM nonce must be 12 bytes")
