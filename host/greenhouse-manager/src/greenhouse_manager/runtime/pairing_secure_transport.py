from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .pairing_service import (
    CredentialBundle,
    PairingOffer,
    PairingSessionSnapshot,
    PairingSessionState,
    build_pairing_proof,
)

BASE64URL_32_PATTERN = re.compile("^[A-Za-z0-9_-]{43}$")
CIPHER_SUITE = "X25519-HKDF-SHA256-CHACHA20-POLY1305"
MANAGER_TO_NODE = "manager_to_node"
NODE_TO_MANAGER = "node_to_manager"
MAX_SEQUENCE = (1 << 64) - 1


class SecurePairingError(RuntimeError):
    """Base error for the Stage 2B authenticated encrypted transport."""


class SecurePairingConflict(SecurePairingError):
    pass


class SecurePairingProofRejected(SecurePairingError):
    pass


class SecurePairingKeyRejected(SecurePairingError):
    pass


class SecureEnvelopeRejected(SecurePairingError):
    pass


class SecurePairingRollbackError(SecurePairingError):
    pass


class SecurePairingState(StrEnum):
    OFFERED = "offered"
    CHANNEL_ESTABLISHED = "channel_established"
    CREDENTIALS_ENCRYPTED = "credentials_encrypted"
    CONSUMED = "consumed"
    FAILED = "failed"
    EXPIRED = "expired"


class PairingCore(Protocol):
    def open_session(
        self, hardware_id: str, pairing_id: str, *, pairing_secret: str, now: datetime | None = None
    ) -> PairingOffer: ...

    def verify_proof(
        self, session_id: str, *, proof: str, now: datetime | None = None
    ) -> PairingSessionSnapshot: ...

    def issue_credentials(self, session_id: str, *, now: datetime | None = None) -> CredentialBundle: ...

    def acknowledge_delivery(
        self, session_id: str, *, now: datetime | None = None
    ) -> PairingSessionSnapshot: ...

    def abort(self, session_id: str) -> PairingSessionSnapshot: ...

    def expire_sessions(self, *, now: datetime | None = None) -> int: ...

    def status(self, session_id: str, *, now: datetime | None = None) -> PairingSessionSnapshot: ...


@dataclass(frozen=True, slots=True)
class SecurePairingOffer:
    schema: str
    session_id: str
    hardware_id: str
    pairing_id: str
    manager_nonce: str
    manager_public_key: str
    cipher_suite: str
    expires_at: datetime
    max_proof_attempts: int


@dataclass(frozen=True, slots=True)
class SecureEnvelope:
    schema: str
    session_id: str
    direction: str
    sequence: int
    content_type: str
    nonce: str
    ciphertext: str

    def to_document(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> SecureEnvelope:
        required = {"schema", "session_id", "direction", "sequence", "content_type", "nonce", "ciphertext"}
        if set(document) != required:
            raise SecureEnvelopeRejected("encrypted envelope fields are invalid")
        if document["schema"] != "gh.pair.envelope/1":
            raise SecureEnvelopeRejected("encrypted envelope schema is invalid")
        if not isinstance(document["session_id"], str) or not document["session_id"]:
            raise SecureEnvelopeRejected("encrypted envelope session_id is invalid")
        if document["direction"] not in (MANAGER_TO_NODE, NODE_TO_MANAGER):
            raise SecureEnvelopeRejected("encrypted envelope direction is invalid")
        sequence = document["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool) or (not 0 <= sequence <= MAX_SEQUENCE):
            raise SecureEnvelopeRejected("encrypted envelope sequence is invalid")
        if not isinstance(document["content_type"], str) or not document["content_type"]:
            raise SecureEnvelopeRejected("encrypted envelope content_type is invalid")
        if not isinstance(document["nonce"], str) or not isinstance(document["ciphertext"], str):
            raise SecureEnvelopeRejected("encrypted envelope encoding is invalid")
        return cls(
            schema="gh.pair.envelope/1",
            session_id=document["session_id"],
            direction=document["direction"],
            sequence=sequence,
            content_type=document["content_type"],
            nonce=document["nonce"],
            ciphertext=document["ciphertext"],
        )


@dataclass(frozen=True, slots=True)
class SecureKeyPair:
    manager_to_node: bytes
    node_to_manager: bytes


@dataclass(frozen=True, slots=True)
class SecurePairingSnapshot:
    session_id: str
    state: SecurePairingState
    expires_at: datetime
    proof_attempts: int
    credential_generation: int | None


@dataclass(slots=True)
class _SecureSession:
    core_offer: PairingOffer
    offer: SecurePairingOffer
    secret: bytearray
    private_key: X25519PrivateKey | None
    state: SecurePairingState = SecurePairingState.OFFERED
    proof_attempts: int = 0
    channel: SecureChannel | None = None
    bundle: CredentialBundle | None = None
    envelope: SecureEnvelope | None = None
    credential_generation: int | None = None


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_base64url(value: str, *, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be non-empty base64url")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if any(character not in alphabet for character in value):
        raise ValueError(f"{field_name} must be unpadded base64url")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except ValueError as error:
        raise ValueError(f"{field_name} must be unpadded base64url") from error


def decode_base64url_32(value: str, *, field_name: str) -> bytes:
    if BASE64URL_32_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be 32-byte unpadded base64url")
    decoded = decode_base64url(value, field_name=field_name)
    if len(decoded) != 32:
        raise ValueError(f"{field_name} must decode to exactly 32 bytes")
    return decoded


def public_key_text(private_key: X25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return encode_base64url(raw)


def load_public_key(value: str, *, field_name: str) -> X25519PublicKey:
    try:
        return X25519PublicKey.from_public_bytes(decode_base64url_32(value, field_name=field_name))
    except ValueError as error:
        raise SecurePairingKeyRejected("ephemeral public key rejected") from error


def secure_proof_transcript(*, offer: SecurePairingOffer, node_nonce: str, node_public_key: str) -> bytes:
    decode_base64url_32(node_nonce, field_name="node_nonce")
    decode_base64url_32(node_public_key, field_name="node_public_key")
    return "\n".join(
        (
            "gh.pair.secure-proof/1",
            offer.session_id,
            offer.hardware_id,
            offer.pairing_id,
            node_nonce,
            offer.manager_nonce,
            offer.manager_public_key,
            node_public_key,
            offer.cipher_suite,
        )
    ).encode("ascii")


def build_secure_pairing_proof(
    *, pairing_secret: str, offer: SecurePairingOffer, node_nonce: str, node_public_key: str
) -> str:
    secret = decode_base64url_32(pairing_secret, field_name="pairing_secret")
    transcript = secure_proof_transcript(offer=offer, node_nonce=node_nonce, node_public_key=node_public_key)
    return encode_base64url(hmac.new(secret, transcript, hashlib.sha256).digest())


def derive_secure_keys(*, shared_secret: bytes, pairing_secret: bytes, transcript: bytes) -> SecureKeyPair:
    digest = hashlib.sha256(transcript).digest()
    salt = hmac.new(pairing_secret, b"gh.pair.secure-salt/1\x00" + digest, hashlib.sha256).digest()
    material = HKDF(
        algorithm=hashes.SHA256(), length=64, salt=salt, info=b"gh.pair.secure-keys/1\x00" + digest
    ).derive(shared_secret)
    return SecureKeyPair(manager_to_node=material[:32], node_to_manager=material[32:])


def envelope_nonce(direction: str, sequence: int) -> bytes:
    if direction == MANAGER_TO_NODE:
        prefix = b"\x00\x00\x00\x01"
    elif direction == NODE_TO_MANAGER:
        prefix = b"\x00\x00\x00\x02"
    else:
        raise SecureEnvelopeRejected("encrypted envelope direction is invalid")
    if not 0 <= sequence <= MAX_SEQUENCE:
        raise SecureEnvelopeRejected("encrypted envelope sequence exhausted")
    return prefix + sequence.to_bytes(8, "big")


def envelope_aad(*, session_id: str, direction: str, sequence: int, content_type: str) -> bytes:
    return json.dumps(
        {
            "content_type": content_type,
            "direction": direction,
            "schema": "gh.pair.envelope/1",
            "sequence": sequence,
            "session_id": session_id,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


class SecureChannel:
    def __init__(
        self,
        *,
        session_id: str,
        send_direction: str,
        send_key: bytes,
        receive_direction: str,
        receive_key: bytes,
    ) -> None:
        if not session_id:
            raise ValueError("session_id must not be empty")
        if {send_direction, receive_direction} != {MANAGER_TO_NODE, NODE_TO_MANAGER}:
            raise ValueError("secure channel directions must be complementary")
        if len(send_key) != 32 or len(receive_key) != 32:
            raise ValueError("secure channel keys must be exactly 32 bytes")
        self.session_id = session_id
        self.send_direction = send_direction
        self.receive_direction = receive_direction
        self._send_key = bytearray(send_key)
        self._receive_key = bytearray(receive_key)
        self._send_sequence = 0
        self._receive_sequence = 0
        self._closed = False
        self._lock = threading.RLock()

    def encrypt(self, plaintext: bytes, *, content_type: str) -> SecureEnvelope:
        with self._lock:
            self._require_open()
            if not content_type:
                raise ValueError("content_type must not be empty")
            sequence = self._send_sequence
            nonce = envelope_nonce(self.send_direction, sequence)
            aad = envelope_aad(
                session_id=self.session_id,
                direction=self.send_direction,
                sequence=sequence,
                content_type=content_type,
            )
            ciphertext = ChaCha20Poly1305(bytes(self._send_key)).encrypt(nonce, plaintext, aad)
            self._send_sequence += 1
            return SecureEnvelope(
                schema="gh.pair.envelope/1",
                session_id=self.session_id,
                direction=self.send_direction,
                sequence=sequence,
                content_type=content_type,
                nonce=encode_base64url(nonce),
                ciphertext=encode_base64url(ciphertext),
            )

    def decrypt(self, envelope: SecureEnvelope, *, expected_content_type: str) -> bytes:
        with self._lock:
            self._require_open()
            if envelope.session_id != self.session_id:
                raise SecureEnvelopeRejected("encrypted envelope session mismatch")
            if envelope.direction != self.receive_direction:
                raise SecureEnvelopeRejected("encrypted envelope direction mismatch")
            if envelope.content_type != expected_content_type:
                raise SecureEnvelopeRejected("encrypted envelope content_type mismatch")
            if envelope.sequence != self._receive_sequence:
                raise SecureEnvelopeRejected("encrypted envelope sequence rejected")
            expected_nonce = envelope_nonce(envelope.direction, envelope.sequence)
            supplied_nonce = decode_base64url(envelope.nonce, field_name="nonce")
            if not hmac.compare_digest(supplied_nonce, expected_nonce):
                raise SecureEnvelopeRejected("encrypted envelope nonce rejected")
            aad = envelope_aad(
                session_id=envelope.session_id,
                direction=envelope.direction,
                sequence=envelope.sequence,
                content_type=envelope.content_type,
            )
            try:
                plaintext = ChaCha20Poly1305(bytes(self._receive_key)).decrypt(
                    expected_nonce, decode_base64url(envelope.ciphertext, field_name="ciphertext"), aad
                )
            except InvalidTag as error:
                raise SecureEnvelopeRejected("encrypted envelope authentication failed") from error
            self._receive_sequence += 1
            return plaintext

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            for key in (self._send_key, self._receive_key):
                for index in range(len(key)):
                    key[index] = 0
                key.clear()
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise SecurePairingConflict("secure channel is closed")


class SecurePairingCoordinator:
    """Wrap the Stage 2A core without exposing plaintext credentials."""

    def __init__(
        self,
        core: PairingCore,
        *,
        private_key_factory: Callable[[], X25519PrivateKey] = X25519PrivateKey.generate,
    ) -> None:
        self.core = core
        self.private_key_factory = private_key_factory
        self._lock = threading.RLock()
        self._sessions: dict[str, _SecureSession] = {}

    def open_session(
        self, hardware_id: str, pairing_id: str, *, pairing_secret: str, now: datetime | None = None
    ) -> SecurePairingOffer:
        secret = decode_base64url_32(pairing_secret, field_name="pairing_secret")
        core_offer = self.core.open_session(hardware_id, pairing_id, pairing_secret=pairing_secret, now=now)
        try:
            private_key = self.private_key_factory()
            manager_public_key = public_key_text(private_key)
        except Exception as creation_error:
            try:
                self.core.abort(core_offer.session_id)
            except Exception:
                raise SecurePairingRollbackError("ephemeral key creation cleanup failed") from creation_error
            raise
        offer = SecurePairingOffer(
            schema="gh.pair.secure-offer/1",
            session_id=core_offer.session_id,
            hardware_id=core_offer.hardware_id,
            pairing_id=core_offer.pairing_id,
            manager_nonce=core_offer.manager_nonce,
            manager_public_key=manager_public_key,
            cipher_suite=CIPHER_SUITE,
            expires_at=core_offer.expires_at,
            max_proof_attempts=core_offer.max_proof_attempts,
        )
        with self._lock:
            if offer.session_id in self._sessions:
                self.core.abort(offer.session_id)
                raise SecurePairingConflict("duplicate secure session_id")
            self._sessions[offer.session_id] = _SecureSession(
                core_offer=core_offer, offer=offer, secret=bytearray(secret), private_key=private_key
            )
        return offer

    def establish_channel(
        self,
        session_id: str,
        *,
        node_nonce: str,
        node_public_key: str,
        proof: str,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot:
        supplied = decode_base64url_32(proof, field_name="proof")
        with self._lock:
            session = self._require_session(session_id)
            if session.state != SecurePairingState.OFFERED:
                raise SecurePairingConflict(f"cannot establish channel in {session.state} state")
            transcript = secure_proof_transcript(
                offer=session.offer, node_nonce=node_nonce, node_public_key=node_public_key
            )
            expected = hmac.new(bytes(session.secret), transcript, hashlib.sha256).digest()
            session.proof_attempts += 1
            if not hmac.compare_digest(supplied, expected):
                self._reject_proof(session)
                raise SecurePairingProofRejected("secure pairing proof rejected")
            legacy_proof = build_pairing_proof(
                pairing_secret=encode_base64url(bytes(session.secret)),
                offer=session.core_offer,
                node_nonce=node_nonce,
            )
            try:
                self.core.verify_proof(
                    session_id,
                    proof=legacy_proof,
                    now=now,
                )
            except Exception as error:
                try:
                    self.core.abort(session_id)
                except Exception:
                    session.state = SecurePairingState.FAILED
                    self._clear_sensitive(session)
                    raise SecurePairingRollbackError("pairing core proof cleanup failed") from error
                session.state = SecurePairingState.FAILED
                self._clear_sensitive(session)
                raise SecurePairingConflict("pairing core proof verification failed") from error
            if session.private_key is None:
                raise SecurePairingConflict("manager ephemeral key unavailable")
            try:
                shared = session.private_key.exchange(
                    load_public_key(node_public_key, field_name="node_public_key")
                )
                keys = derive_secure_keys(
                    shared_secret=shared, pairing_secret=bytes(session.secret), transcript=transcript
                )
            except ValueError as error:
                self._abort_after_key_rejection(session, error)
                raise AssertionError("unreachable") from error
            session.channel = SecureChannel(
                session_id=session_id,
                send_direction=MANAGER_TO_NODE,
                send_key=keys.manager_to_node,
                receive_direction=NODE_TO_MANAGER,
                receive_key=keys.node_to_manager,
            )
            session.private_key = None
            self._clear_secret(session)
            session.state = SecurePairingState.CHANNEL_ESTABLISHED
            return self._snapshot(session)

    def issue_encrypted_credentials(self, session_id: str, *, now: datetime | None = None) -> SecureEnvelope:
        with self._lock:
            session = self._require_session(session_id)
            if session.state == SecurePairingState.CREDENTIALS_ENCRYPTED and session.envelope is not None:
                return session.envelope
            if session.state != SecurePairingState.CHANNEL_ESTABLISHED or session.channel is None:
                raise SecurePairingConflict("credentials require an established secure channel")
            bundle = self.core.issue_credentials(session_id, now=now)
            try:
                document = {
                    "broker_host": bundle.broker_host,
                    "broker_port": bundle.broker_port,
                    "broker_tls_server_name": bundle.broker_tls_server_name,
                    "ca_pem": bundle.ca_pem,
                    "credential_generation": bundle.credential_generation,
                    "mqtt_client_id": bundle.mqtt_client_id,
                    "mqtt_password": bundle.mqtt_password,
                    "mqtt_username": bundle.mqtt_username,
                    "node_id": bundle.node_id,
                    "schema": bundle.schema,
                    "system_id": bundle.system_id,
                }
                plaintext = json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
                envelope = session.channel.encrypt(
                    plaintext,
                    content_type="gh.pair.credentials/1",
                )
            except Exception as encryption_error:
                try:
                    self.core.abort(session_id)
                except Exception:
                    session.state = SecurePairingState.FAILED
                    self._clear_sensitive(session)
                    raise SecurePairingRollbackError(
                        "credential encryption cleanup failed"
                    ) from encryption_error
                session.state = SecurePairingState.FAILED
                self._clear_sensitive(session)
                raise SecurePairingConflict("credential encryption failed") from encryption_error
            session.envelope = envelope
            session.bundle = bundle
            session.credential_generation = bundle.credential_generation
            session.state = SecurePairingState.CREDENTIALS_ENCRYPTED
            return session.envelope

    def acknowledge_encrypted_delivery(
        self, session_id: str, envelope: SecureEnvelope | Mapping[str, Any], *, now: datetime | None = None
    ) -> SecurePairingSnapshot:
        candidate = (
            envelope if isinstance(envelope, SecureEnvelope) else SecureEnvelope.from_document(envelope)
        )
        with self._lock:
            session = self._require_session(session_id)
            if (
                session.state != SecurePairingState.CREDENTIALS_ENCRYPTED
                or session.channel is None
                or session.bundle is None
            ):
                raise SecurePairingConflict("acknowledgement requires encrypted credentials")
            plaintext = session.channel.decrypt(candidate, expected_content_type="gh.pair.delivery-ack/1")
            try:
                document = json.loads(plaintext.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SecureEnvelopeRejected("delivery acknowledgement is invalid JSON") from error
            expected = {
                "credential_generation": session.bundle.credential_generation,
                "node_id": session.bundle.node_id,
                "schema": "gh.pair.delivery-ack/1",
                "stored": True,
            }
            if document != expected:
                raise SecureEnvelopeRejected("delivery acknowledgement contract rejected")
            try:
                snapshot = self.core.acknowledge_delivery(session_id, now=now)
            except Exception:
                self._clear_if_core_terminal(session, now=now)
                raise
            if snapshot.state != PairingSessionState.CONSUMED:
                raise SecurePairingConflict("pairing core did not consume acknowledgement")
            session.state = SecurePairingState.CONSUMED
            self._clear_sensitive(session)
            return self._snapshot(session)

    def abort(self, session_id: str) -> SecurePairingSnapshot:
        with self._lock:
            session = self._require_session(session_id)
            if session.state == SecurePairingState.CONSUMED:
                raise SecurePairingConflict("consumed secure pairing cannot abort")
            try:
                snapshot = self.core.abort(session_id)
            except Exception as error:
                session.state = SecurePairingState.FAILED
                self._clear_sensitive(session)
                raise SecurePairingRollbackError("secure pairing rollback failed") from error
            session.state = (
                SecurePairingState.EXPIRED
                if snapshot.state == PairingSessionState.EXPIRED
                else SecurePairingState.FAILED
            )
            self._clear_sensitive(session)
            return self._snapshot(session)

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        observed_at = utc(now or datetime.now(UTC))
        with self._lock:
            candidates = [
                session
                for session in self._sessions.values()
                if session.state
                not in (
                    SecurePairingState.CONSUMED,
                    SecurePairingState.FAILED,
                    SecurePairingState.EXPIRED,
                )
                and observed_at > session.offer.expires_at
            ]
            if not candidates:
                return 0
            try:
                self.core.expire_sessions(now=observed_at)
            except Exception as error:
                for session in candidates:
                    session.state = SecurePairingState.FAILED
                    self._clear_sensitive(session)
                raise SecurePairingRollbackError("secure pairing expiry rollback failed") from error
            for session in candidates:
                snapshot = self.core.status(
                    session.offer.session_id,
                    now=observed_at,
                )
                if snapshot.state != PairingSessionState.EXPIRED:
                    session.state = SecurePairingState.FAILED
                    self._clear_sensitive(session)
                    raise SecurePairingConflict("pairing core did not expire overdue session")
                session.state = SecurePairingState.EXPIRED
                self._clear_sensitive(session)
            return len(candidates)

    def status(self, session_id: str, *, now: datetime | None = None) -> SecurePairingSnapshot:
        with self._lock:
            session = self._require_session(session_id)
            try:
                snapshot = self.core.status(session_id, now=now)
            except Exception:
                self._clear_if_core_terminal(session, now=now)
                raise
            if snapshot.state == PairingSessionState.EXPIRED:
                session.state = SecurePairingState.EXPIRED
                self._clear_sensitive(session)
            elif snapshot.state == PairingSessionState.FAILED:
                session.state = SecurePairingState.FAILED
                self._clear_sensitive(session)
            return self._snapshot(session)

    def _reject_proof(self, session: _SecureSession) -> None:
        if session.proof_attempts < session.offer.max_proof_attempts:
            return
        try:
            self.core.abort(session.offer.session_id)
        except Exception as error:
            session.state = SecurePairingState.FAILED
            self._clear_sensitive(session)
            raise SecurePairingRollbackError("proof-lockout cleanup failed") from error
        session.state = SecurePairingState.FAILED
        self._clear_sensitive(session)

    def _abort_after_key_rejection(self, session: _SecureSession, error: ValueError) -> None:
        try:
            self.core.abort(session.offer.session_id)
        except Exception as rollback_error:
            session.state = SecurePairingState.FAILED
            self._clear_sensitive(session)
            raise SecurePairingRollbackError("rejected key cleanup failed") from rollback_error
        session.state = SecurePairingState.FAILED
        self._clear_sensitive(session)
        raise SecurePairingKeyRejected("node ephemeral public key rejected") from error

    def _clear_if_core_terminal(self, session: _SecureSession, *, now: datetime | None) -> None:
        try:
            snapshot = self.core.status(session.offer.session_id, now=now)
        except Exception:
            return
        if snapshot.state == PairingSessionState.FAILED:
            session.state = SecurePairingState.FAILED
            self._clear_sensitive(session)
        elif snapshot.state == PairingSessionState.EXPIRED:
            session.state = SecurePairingState.EXPIRED
            self._clear_sensitive(session)

    def _require_session(self, session_id: str) -> _SecureSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise SecurePairingConflict("unknown secure pairing session") from error

    @staticmethod
    def _clear_secret(session: _SecureSession) -> None:
        for index in range(len(session.secret)):
            session.secret[index] = 0
        session.secret.clear()

    def _clear_sensitive(self, session: _SecureSession) -> None:
        self._clear_secret(session)
        session.private_key = None
        if session.channel is not None:
            session.channel.close()
        session.channel = None
        session.bundle = None
        session.envelope = None

    @staticmethod
    def _snapshot(session: _SecureSession) -> SecurePairingSnapshot:
        return SecurePairingSnapshot(
            session_id=session.offer.session_id,
            state=session.state,
            expires_at=session.offer.expires_at,
            proof_attempts=session.proof_attempts,
            credential_generation=session.credential_generation,
        )
