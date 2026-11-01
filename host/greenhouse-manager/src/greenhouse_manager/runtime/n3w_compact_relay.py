from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .n3w_relay_ingress import PackagedTelemetryValidator, RelayIngressRejected, parse_relay_topic

ESPNOW_V2_PAYLOAD_LIMIT = 1470
SINGLE_FRAME_HEADER_BYTES = 48
MAX_CIPHERTEXT_BYTES = 1024
_FRAME_MAGIC = b"N3W2"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_MAX_SEQ = 2**32 - 1
_BOOT_ID = re.compile(r"^boot_([0-9a-f]{16})$")
_SCHEMA = "gh.relay/2"


class NodeApplicationKeyProvider(Protocol):
    def resolve_key(self, *, node_id: str, key_epoch: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StaticNodeApplicationKeyProvider:
    keys: dict[tuple[str, int], bytes]

    def resolve_key(self, *, node_id: str, key_epoch: int) -> bytes:
        key = self.keys.get((node_id, key_epoch))
        if key is None:
            raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
        if not isinstance(key, bytes) or len(key) != 32:
            raise RelayIngressRejected("key_material_invalid", node_id=node_id)
        return key


@dataclass(frozen=True, slots=True)
class CompactTelemetryFrame:
    boot_session: int
    seq: int
    key_epoch: int
    nonce: bytes
    tag: bytes
    ciphertext: bytes

    @property
    def boot_id(self) -> str:
        return f"boot_{self.boot_session:016x}"


@dataclass(frozen=True, slots=True)
class CompactRelayPreparation:
    status: str
    code: str | None = None
    system_id: str | None = None
    gateway_id: str | None = None
    node_id: str | None = None
    ingress_topic: str | None = None
    telemetry: dict[str, Any] | None = None
    boot_id: str | None = None
    seq: int | None = None


def single_frame_wire_bytes(ciphertext_bytes: int) -> int:
    if not isinstance(ciphertext_bytes, int) or isinstance(ciphertext_bytes, bool):
        raise ValueError("ciphertext size is invalid")
    if not 1 <= ciphertext_bytes <= MAX_CIPHERTEXT_BYTES:
        raise ValueError("ciphertext size is invalid")
    return SINGLE_FRAME_HEADER_BYTES + ciphertext_bytes


def _validate_frame(frame: CompactTelemetryFrame) -> None:
    if not isinstance(frame.boot_session, int) or isinstance(frame.boot_session, bool):
        raise ValueError("boot_session is invalid")
    if not 1 <= frame.boot_session <= 2**64 - 1:
        raise ValueError("boot_session is invalid")
    if not isinstance(frame.seq, int) or isinstance(frame.seq, bool) or not 0 <= frame.seq <= _MAX_SEQ:
        raise ValueError("sequence is invalid")
    if not isinstance(frame.key_epoch, int) or isinstance(frame.key_epoch, bool) or frame.key_epoch < 1:
        raise ValueError("key_epoch is invalid")
    if not isinstance(frame.nonce, bytes) or len(frame.nonce) != _NONCE_BYTES:
        raise ValueError("nonce is invalid")
    if not isinstance(frame.tag, bytes) or len(frame.tag) != _TAG_BYTES:
        raise ValueError("tag is invalid")
    if not isinstance(frame.ciphertext, bytes):
        raise ValueError("ciphertext is invalid")
    if single_frame_wire_bytes(len(frame.ciphertext)) > ESPNOW_V2_PAYLOAD_LIMIT:
        raise ValueError("single frame exceeds ESP-NOW v2 payload budget")


def encode_single_frame(frame: CompactTelemetryFrame) -> bytes:
    _validate_frame(frame)
    return b"".join(
        (
            _FRAME_MAGIC,
            frame.boot_session.to_bytes(8, "big"),
            frame.seq.to_bytes(4, "big"),
            frame.key_epoch.to_bytes(4, "big"),
            frame.nonce,
            frame.tag,
            frame.ciphertext,
        )
    )


def decode_single_frame(payload: bytes) -> CompactTelemetryFrame:
    if not isinstance(payload, bytes) or len(payload) <= SINGLE_FRAME_HEADER_BYTES:
        raise RelayIngressRejected("single_frame_invalid")
    if len(payload) > ESPNOW_V2_PAYLOAD_LIMIT or payload[:4] != _FRAME_MAGIC:
        raise RelayIngressRejected("single_frame_invalid")
    frame = CompactTelemetryFrame(
        boot_session=int.from_bytes(payload[4:12], "big"),
        seq=int.from_bytes(payload[12:16], "big"),
        key_epoch=int.from_bytes(payload[16:20], "big"),
        nonce=payload[20:32],
        tag=payload[32:48],
        ciphertext=payload[48:],
    )
    try:
        _validate_frame(frame)
    except ValueError as error:
        raise RelayIngressRejected("single_frame_invalid") from error
    return frame


def _boot_session(boot_id: str) -> int:
    if not isinstance(boot_id, str):
        raise ValueError("boot_id is invalid")
    match = _BOOT_ID.fullmatch(boot_id)
    if match is None:
        raise ValueError("boot_id is invalid")
    session = int(match.group(1), 16)
    if session == 0:
        raise ValueError("boot_id is invalid")
    return session


def derive_nonce(boot_id: str, seq: int) -> bytes:
    session = _boot_session(boot_id)
    if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq <= _MAX_SEQ:
        raise ValueError("sequence is invalid")
    return session.to_bytes(8, "big") + seq.to_bytes(4, "big")


def build_aad(
    *,
    system_id: str,
    node_id: str,
    key_epoch: int,
    boot_id: str,
    seq: int,
) -> bytes:
    document = {
        "boot_id": boot_id,
        "key_epoch": key_epoch,
        "node_id": node_id,
        "schema": _SCHEMA,
        "seq": seq,
        "system_id": system_id,
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encrypt_compact_telemetry(
    *,
    system_id: str,
    node_id: str,
    key_epoch: int,
    boot_id: str,
    seq: int,
    key: bytes,
    plaintext: bytes,
) -> bytes:
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("application key must be 32 bytes")
    if not isinstance(plaintext, bytes) or not plaintext:
        raise ValueError("telemetry plaintext is invalid")
    nonce = derive_nonce(boot_id, seq)
    aad = build_aad(
        system_id=system_id,
        node_id=node_id,
        key_epoch=key_epoch,
        boot_id=boot_id,
        seq=seq,
    )
    encrypted = AESGCM(key).encrypt(nonce, plaintext, aad)
    ciphertext, tag = encrypted[:-_TAG_BYTES], encrypted[-_TAG_BYTES:]
    frame = CompactTelemetryFrame(
        boot_session=_boot_session(boot_id),
        seq=seq,
        key_epoch=key_epoch,
        nonce=nonce,
        tag=tag,
        ciphertext=ciphertext,
    )
    return encode_single_frame(frame)


def wrap_relay_frame(frame: bytes) -> bytes:
    decode_single_frame(frame)
    document = {
        "frame_b64": base64.b64encode(frame).decode("ascii"),
        "schema": _SCHEMA,
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _unwrap_relay_frame(payload: bytes | str) -> bytes:
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        document = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise RelayIngressRejected("payload_invalid") from error
    if not isinstance(document, dict) or set(document) != {"schema", "frame_b64"}:
        raise RelayIngressRejected("payload_invalid")
    if document["schema"] != _SCHEMA or not isinstance(document["frame_b64"], str):
        raise RelayIngressRejected("schema_or_transport_invalid")
    try:
        return base64.b64decode(document["frame_b64"], validate=True)
    except (ValueError, TypeError) as error:
        raise RelayIngressRejected("payload_invalid") from error


class CompactRelayIngressCore:
    """Authenticate one path-independent single-frame Relay telemetry payload."""

    def __init__(
        self,
        *,
        system_id: str,
        keys: NodeApplicationKeyProvider,
        telemetry_validator: PackagedTelemetryValidator | None = None,
    ) -> None:
        self.system_id = system_id
        self.keys = keys
        self.telemetry_validator = telemetry_validator or PackagedTelemetryValidator()

    def prepare(self, topic: str, payload: bytes | str) -> CompactRelayPreparation:
        try:
            return self._prepare(topic, payload)
        except RelayIngressRejected as error:
            return CompactRelayPreparation(status="rejected", code=error.code, node_id=error.node_id)

    def _prepare(self, topic: str, payload: bytes | str) -> CompactRelayPreparation:
        parsed_topic = parse_relay_topic(topic)
        if parsed_topic.system_id != self.system_id:
            raise RelayIngressRejected("system_binding_mismatch", node_id=parsed_topic.node_id)
        frame = decode_single_frame(_unwrap_relay_frame(payload))
        key = self.keys.resolve_key(node_id=parsed_topic.node_id, key_epoch=frame.key_epoch)
        expected_nonce = derive_nonce(frame.boot_id, frame.seq)
        if frame.nonce != expected_nonce:
            raise RelayIngressRejected("nonce_mismatch", node_id=parsed_topic.node_id)
        aad = build_aad(
            system_id=self.system_id,
            node_id=parsed_topic.node_id,
            key_epoch=frame.key_epoch,
            boot_id=frame.boot_id,
            seq=frame.seq,
        )
        try:
            plaintext = AESGCM(key).decrypt(frame.nonce, frame.ciphertext + frame.tag, aad)
        except InvalidTag as error:
            raise RelayIngressRejected("aead_or_plaintext_rejected", node_id=parsed_topic.node_id) from error
        try:
            telemetry = json.loads(plaintext)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            raise RelayIngressRejected("aead_or_plaintext_rejected", node_id=parsed_topic.node_id) from error
        if not isinstance(telemetry, dict) or telemetry.get("schema") != "gh.telemetry/1":
            raise RelayIngressRejected("inner_schema_invalid", node_id=parsed_topic.node_id)
        if (
            telemetry.get("node_id"),
            telemetry.get("boot_id"),
            telemetry.get("seq"),
        ) != (parsed_topic.node_id, frame.boot_id, frame.seq):
            raise RelayIngressRejected("inner_binding_mismatch", node_id=parsed_topic.node_id)
        self.telemetry_validator.validate(telemetry)
        return CompactRelayPreparation(
            status="ready",
            system_id=self.system_id,
            gateway_id=parsed_topic.gateway_id,
            node_id=parsed_topic.node_id,
            ingress_topic=(
                f"gh/v1/{self.system_id}/ingress/node/{parsed_topic.node_id}/telemetry"
            ),
            telemetry=dict(telemetry),
            boot_id=frame.boot_id,
            seq=frame.seq,
        )
