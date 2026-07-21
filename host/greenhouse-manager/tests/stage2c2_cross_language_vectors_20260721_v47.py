from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from greenhouse_manager.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureChannel,
    SecurePairingOffer,
    build_secure_pairing_proof,
    derive_secure_keys,
    envelope_aad,
    envelope_nonce,
    secure_proof_transcript,
)

ROOT = Path(__file__).resolve().parents[3]
VECTOR_PATH = ROOT / "protocols/pairing/gh-h3-stage2c2-cross-language-vectors-v1.json"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def canonical(document: dict[str, object]) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def vector() -> dict[str, object]:
    pairing_secret = bytes([1] * 32)
    pairing_secret_text = b64(pairing_secret)
    manager_private_raw = bytearray(range(0x20, 0x40))
    manager_private_raw[0] &= 248
    manager_private_raw[31] &= 127
    manager_private_raw[31] |= 64
    node_private_raw = bytearray(range(1, 33))
    node_private_raw[0] &= 248
    node_private_raw[31] &= 127
    node_private_raw[31] |= 64
    manager_private = X25519PrivateKey.from_private_bytes(bytes(manager_private_raw))
    node_private = X25519PrivateKey.from_private_bytes(bytes(node_private_raw))
    manager_public = manager_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    node_public = node_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    shared = node_private.exchange(manager_private.public_key())

    session_id = "11111111-2222-4333-8444-555555555555"
    hardware_id = "ghw-c6-stage2c2-vector"
    pairing_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    manager_nonce_raw = bytes(range(0x40, 0x60))
    node_nonce_raw = bytes(range(0x80, 0xA0))
    manager_nonce = b64(manager_nonce_raw)
    node_nonce = b64(node_nonce_raw)
    manager_public_text = b64(manager_public)
    node_public_text = b64(node_public)
    cipher_suite = "X25519-HKDF-SHA256-CHACHA20-POLY1305"
    offer = SecurePairingOffer(
        schema="gh.pair.secure-offer/1",
        session_id=session_id,
        hardware_id=hardware_id,
        pairing_id=pairing_id,
        manager_nonce=manager_nonce,
        manager_public_key=manager_public_text,
        cipher_suite=cipher_suite,
        expires_at=datetime(2026, 7, 21, 9, 0, tzinfo=UTC),
        max_proof_attempts=3,
    )
    transcript = secure_proof_transcript(
        offer=offer,
        node_nonce=node_nonce,
        node_public_key=node_public_text,
    )
    proof_text = build_secure_pairing_proof(
        pairing_secret=pairing_secret_text,
        offer=offer,
        node_nonce=node_nonce,
        node_public_key=node_public_text,
    )
    proof = base64.urlsafe_b64decode(proof_text + "=")
    digest = hashlib.sha256(transcript).digest()
    salt = hmac.new(
        pairing_secret, b"gh.pair.secure-salt/1\x00" + digest, hashlib.sha256
    ).digest()
    keys = derive_secure_keys(
        shared_secret=shared,
        pairing_secret=pairing_secret,
        transcript=transcript,
    )

    credentials = {
        "broker_host": "broker.stage2c2.local",
        "broker_port": 8883,
        "broker_tls_server_name": "broker.stage2c2.local",
        "ca_pem": "-----BEGIN CERTIFICATE-----\nSTAGE2C2-LAB\n-----END CERTIFICATE-----\n",
        "credential_generation": 1,
        "mqtt_client_id": "gh-n1-stage2c2-vector",
        "mqtt_password": "stage2c2-ram-only-password",
        "mqtt_username": "gh-n1-stage2c2-vector",
        "node_id": "gh-n1-stage2c2-vector",
        "schema": "gh.pair.credentials/1",
        "system_id": "greenhouse",
    }
    credentials_plaintext = canonical(credentials)
    manager_channel = SecureChannel(
        session_id=session_id,
        send_direction=MANAGER_TO_NODE,
        send_key=keys.manager_to_node,
        receive_direction=NODE_TO_MANAGER,
        receive_key=keys.node_to_manager,
    )
    credentials_envelope = manager_channel.encrypt(
        credentials_plaintext, content_type="gh.pair.credentials/1"
    )

    ack = {
        "credential_generation": 1,
        "node_id": "gh-n1-stage2c2-vector",
        "schema": "gh.pair.delivery-ack/1",
        "stored": True,
    }
    ack_plaintext = canonical(ack)
    node_channel = SecureChannel(
        session_id=session_id,
        send_direction=NODE_TO_MANAGER,
        send_key=keys.node_to_manager,
        receive_direction=MANAGER_TO_NODE,
        receive_key=keys.manager_to_node,
    )
    ack_envelope = node_channel.encrypt(
        ack_plaintext, content_type="gh.pair.delivery-ack/1"
    )

    credentials_nonce_raw = envelope_nonce(MANAGER_TO_NODE, 0)
    ack_nonce_raw = envelope_nonce(NODE_TO_MANAGER, 0)
    credentials_aad = envelope_aad(
        session_id=session_id,
        direction=MANAGER_TO_NODE,
        sequence=0,
        content_type="gh.pair.credentials/1",
    )
    ack_aad = envelope_aad(
        session_id=session_id,
        direction=NODE_TO_MANAGER,
        sequence=0,
        content_type="gh.pair.delivery-ack/1",
    )

    assert credentials_envelope.nonce == b64(credentials_nonce_raw)
    assert ack_envelope.nonce == b64(ack_nonce_raw)

    return {
        "schema": "gh.h3-n2.stage2c2-vectors/1",
        "pairing_secret": pairing_secret_text,
        "manager_private_key_hex": bytes(manager_private_raw).hex(),
        "manager_public_key": manager_public_text,
        "node_private_key_hex": bytes(node_private_raw).hex(),
        "node_public_key": node_public_text,
        "x25519_shared_secret_hex": shared.hex(),
        "session_id": session_id,
        "hardware_id": hardware_id,
        "pairing_id": pairing_id,
        "manager_nonce": manager_nonce,
        "node_nonce": node_nonce,
        "cipher_suite": cipher_suite,
        "secure_proof": b64(proof),
        "transcript_sha256_hex": digest.hex(),
        "hkdf_salt_hex": salt.hex(),
        "manager_to_node_key_hex": keys.manager_to_node.hex(),
        "node_to_manager_key_hex": keys.node_to_manager.hex(),
        "credentials_plaintext": credentials_plaintext.decode("ascii"),
        "credentials_nonce": credentials_envelope.nonce,
        "credentials_aad": credentials_aad.decode("ascii"),
        "credentials_ciphertext": credentials_envelope.ciphertext,
        "ack_plaintext": ack_plaintext.decode("ascii"),
        "ack_nonce": ack_envelope.nonce,
        "ack_aad": ack_aad.decode("ascii"),
        "ack_ciphertext": ack_envelope.ciphertext,
    }


def cxx(value: str) -> str:
    return json.dumps(value)


def write_header(values: dict[str, object], path: Path) -> None:
    names = [
        "pairing_secret",
        "manager_public_key",
        "node_private_key_hex",
        "node_public_key",
        "session_id",
        "hardware_id",
        "pairing_id",
        "manager_nonce",
        "node_nonce",
        "cipher_suite",
        "secure_proof",
        "credentials_plaintext",
        "credentials_nonce",
        "credentials_aad",
        "credentials_ciphertext",
        "ack_plaintext",
        "ack_nonce",
        "ack_aad",
        "ack_ciphertext",
    ]
    lines = ["#pragma once", "namespace stage2c2_vectors {"]
    for name in names:
        lines.append(
            f"inline constexpr const char *{name} = {cxx(str(values[name]))};"
        )
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--header", type=Path)
    args = parser.parse_args()
    values = vector()
    encoded = json.dumps(values, indent=2, sort_keys=True) + "\n"
    if args.write:
        VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        VECTOR_PATH.write_text(encoded, encoding="utf-8")
    else:
        current = VECTOR_PATH.read_text(encoding="utf-8")
        if current != encoded:
            raise SystemExit(
                "Stage 2C-2 vectors drifted from Manager implementation"
            )
    if args.header is not None:
        write_header(values, args.header)


if __name__ == "__main__":
    main()
