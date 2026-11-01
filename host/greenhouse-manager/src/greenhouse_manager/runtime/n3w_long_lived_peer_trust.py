from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_SYSTEM_PEER_KEY_BYTES = 32
_MAC_BYTES = 6
_NONCE_BYTES = 16
_PROOF_BYTES = 32

_PAIR_DOMAIN = b"gh.n3w.peer-pair/1"
_PROOF_DOMAIN = b"gh.n3w.long-lived-peer-proof/1"
_LMK_DOMAIN = b"gh.n3w.long-lived-peer-lmk/1"


@dataclass(frozen=True, slots=True)
class PeerEndpoint:
    """One registered N3-W endpoint participating in local peer authentication."""

    node_id: str
    mac: bytes

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.node_id) is None:
            raise ValueError("peer node_id is invalid")
        if not isinstance(self.mac, bytes) or len(self.mac) != _MAC_BYTES:
            raise ValueError("peer mac must be 6 bytes")


@dataclass(frozen=True, slots=True, repr=False)
class SystemPeerCredential:
    """Long-lived same-system credential delivered only after Manager registration."""

    system_id: str
    generation: int
    key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.system_id) is None:
            raise ValueError("system_id is invalid")
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise ValueError("peer trust generation is invalid")
        if self.generation < 1:
            raise ValueError("peer trust generation is invalid")
        if not isinstance(self.key, bytes) or len(self.key) != _SYSTEM_PEER_KEY_BYTES:
            raise ValueError("system peer key must be 32 bytes")

    def __repr__(self) -> str:
        return (
            "SystemPeerCredential("
            f"system_id={self.system_id!r}, generation={self.generation!r}, "
            "key=<redacted>)"
        )


def build_peer_proof(
    credential: SystemPeerCredential,
    *,
    prover: PeerEndpoint,
    verifier: PeerEndpoint,
    prover_boot_nonce: bytes,
    challenge_nonce: bytes,
) -> bytes:
    """Authenticate one registered peer to another without a Manager round trip."""

    _require_distinct_endpoints(prover, verifier)
    _require_nonce(prover_boot_nonce, "prover_boot_nonce")
    _require_nonce(challenge_nonce, "challenge_nonce")
    message = _proof_message(
        credential,
        prover=prover,
        verifier=verifier,
        prover_boot_nonce=prover_boot_nonce,
        challenge_nonce=challenge_nonce,
    )
    return hmac.new(credential.key, message, hashlib.sha256).digest()


def verify_peer_proof(
    credential: SystemPeerCredential,
    *,
    prover: PeerEndpoint,
    verifier: PeerEndpoint,
    prover_boot_nonce: bytes,
    challenge_nonce: bytes,
    proof: bytes,
) -> bool:
    """Verify a peer proof for the current system peer-trust generation."""

    if not isinstance(proof, bytes) or len(proof) != _PROOF_BYTES:
        return False
    try:
        expected = build_peer_proof(
            credential,
            prover=prover,
            verifier=verifier,
            prover_boot_nonce=prover_boot_nonce,
            challenge_nonce=challenge_nonce,
        )
    except ValueError:
        return False
    return hmac.compare_digest(proof, expected)


def derive_pair_lmk(
    credential: SystemPeerCredential,
    *,
    first: PeerEndpoint,
    second: PeerEndpoint,
) -> bytes:
    """Derive the stable 16-byte ESP-NOW LMK for one unordered peer pair."""

    binding = canonical_pair_binding(
        credential,
        first=first,
        second=second,
    )
    salt = hashlib.sha256(_LMK_DOMAIN + b"\x00salt\x00" + binding).digest()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=salt,
        info=_LMK_DOMAIN + b"\x00derive\x00" + binding,
    ).derive(credential.key)


def canonical_pair_binding(
    credential: SystemPeerCredential,
    *,
    first: PeerEndpoint,
    second: PeerEndpoint,
) -> bytes:
    """Return an order-independent identity binding for deterministic LMK derivation."""

    _require_distinct_endpoints(first, second)
    ordered = sorted((first, second), key=lambda endpoint: (endpoint.node_id, endpoint.mac))
    fields = (
        _PAIR_DOMAIN,
        credential.system_id.encode("ascii"),
        str(credential.generation).encode("ascii"),
        ordered[0].node_id.encode("ascii"),
        ordered[0].mac.hex().encode("ascii"),
        ordered[1].node_id.encode("ascii"),
        ordered[1].mac.hex().encode("ascii"),
    )
    return b"\x00".join(fields)


def _proof_message(
    credential: SystemPeerCredential,
    *,
    prover: PeerEndpoint,
    verifier: PeerEndpoint,
    prover_boot_nonce: bytes,
    challenge_nonce: bytes,
) -> bytes:
    fields = (
        _PROOF_DOMAIN,
        credential.system_id.encode("ascii"),
        str(credential.generation).encode("ascii"),
        prover.node_id.encode("ascii"),
        prover.mac.hex().encode("ascii"),
        verifier.node_id.encode("ascii"),
        verifier.mac.hex().encode("ascii"),
        prover_boot_nonce.hex().encode("ascii"),
        challenge_nonce.hex().encode("ascii"),
    )
    return b"\x00".join(fields)


def _require_distinct_endpoints(first: PeerEndpoint, second: PeerEndpoint) -> None:
    if first.node_id == second.node_id:
        raise ValueError("peer node_id collision")
    if first.mac == second.mac:
        raise ValueError("peer mac collision")


def _require_nonce(value: bytes, label: str) -> None:
    if not isinstance(value, bytes) or len(value) != _NONCE_BYTES:
        raise ValueError(f"{label} must be 16 bytes")
