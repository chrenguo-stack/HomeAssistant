from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Literal, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from .replay_registry import ReplayRegistry, ReplayRegistryUnavailable

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_BOOT_ID = re.compile(r"^boot_([0-9a-f]{16})$")
_MAX_ENVELOPE_BYTES = 4096
_MAX_CIPHERTEXT_BYTES = 1024
_MAX_SEQ = 2**32 - 1

IngressStatus = Literal["accepted", "duplicate", "rejected"]


class RelayIngressRejected(ValueError):
    """Fail-closed N3-W relay ingress rejection with a stable diagnostic code."""

    def __init__(self, code: str, *, node_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.node_id = node_id


@dataclass(frozen=True, slots=True)
class RelayTopic:
    system_id: str
    gateway_id: str
    node_id: str


@dataclass(frozen=True, slots=True)
class RelayEnvelope:
    schema: str
    transport: str
    gateway_id: str
    node_id: str
    hop_count: int
    key_epoch: int
    boot_id: str
    seq: int
    nonce: bytes
    ciphertext: bytes
    tag: bytes


@dataclass(frozen=True, slots=True)
class RelayIngressResult:
    status: IngressStatus
    code: str | None = None
    node_id: str | None = None
    ingress_topic: str | None = None
    telemetry: dict[str, Any] | None = None


class RelayAuthorizationProvider(Protocol):
    """Non-live port for node/gateway authorization and per-epoch application keys."""

    def resolve_key(self, *, gateway_id: str, node_id: str, key_epoch: int) -> bytes:
        """Return one 32-byte application key or raise ``RelayIngressRejected``."""


@dataclass(frozen=True, slots=True)
class StaticRelayAuthorizationProvider:
    """Test/non-live authorization provider; not a production key store."""

    active_nodes: frozenset[str]
    gateway_nodes: dict[str, frozenset[str]]
    keys: dict[tuple[str, int], bytes]

    def resolve_key(self, *, gateway_id: str, node_id: str, key_epoch: int) -> bytes:
        if node_id not in self.active_nodes:
            raise RelayIngressRejected("node_not_active", node_id=node_id)
        if node_id not in self.gateway_nodes.get(gateway_id, frozenset()):
            raise RelayIngressRejected("gateway_node_unauthorized", node_id=node_id)
        key = self.keys.get((node_id, key_epoch))
        if key is None:
            raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
        if not isinstance(key, bytes) or len(key) != 32:
            raise RelayIngressRejected("key_material_invalid", node_id=node_id)
        return key


class PackagedTelemetryValidator:
    """Complete schema/Manager-owned-field validator reused by non-live relay ingress."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        self.validator = Draft202012Validator(
            schema or self._load_packaged_schema(),
            format_checker=FormatChecker(),
        )

    @staticmethod
    def _load_packaged_schema() -> dict[str, Any]:
        schema_path = files("greenhouse_manager").joinpath("schemas/gh.telemetry-1.schema.json")
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def validate(self, telemetry: dict[str, Any]) -> None:
        if "received_at" in telemetry:
            raise RelayIngressRejected("manager_owned_field_present")
        errors = sorted(
            self.validator.iter_errors(telemetry),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            raise RelayIngressRejected("telemetry_validation_rejected")


def parse_relay_topic(topic: str) -> RelayTopic:
    if not isinstance(topic, str):
        raise RelayIngressRejected("topic_invalid")
    parts = topic.split("/")
    if (
        len(parts) != 8
        or parts[:2] != ["gh", "v1"]
        or parts[3:5] != ["ingress", "gateway"]
        or parts[7] != "frame"
    ):
        raise RelayIngressRejected("topic_invalid")
    system_id, gateway_id, node_id = parts[2], parts[5], parts[6]
    if not all(_ID.fullmatch(value) for value in (system_id, gateway_id, node_id)):
        raise RelayIngressRejected("topic_identity_invalid")
    return RelayTopic(system_id=system_id, gateway_id=gateway_id, node_id=node_id)


def derive_nonce(boot_id: str, seq: int) -> bytes:
    if not isinstance(boot_id, str):
        raise RelayIngressRejected("boot_session_invalid")
    match = _BOOT_ID.fullmatch(boot_id)
    if match is None:
        raise RelayIngressRejected("boot_session_invalid")
    session = int(match.group(1), 16)
    if session == 0:
        raise RelayIngressRejected("boot_session_invalid")
    if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq <= _MAX_SEQ:
        raise RelayIngressRejected("sequence_out_of_range")
    return session.to_bytes(8, "big") + seq.to_bytes(4, "big")


def build_aad(envelope: RelayEnvelope) -> bytes:
    document = {
        "schema": envelope.schema,
        "transport": envelope.transport,
        "gateway_id": envelope.gateway_id,
        "node_id": envelope.node_id,
        "hop_count": envelope.hop_count,
        "key_epoch": envelope.key_epoch,
        "boot_id": envelope.boot_id,
        "seq": envelope.seq,
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode_b64(value: object, *, field: str, length: int | None = None) -> bytes:
    if not isinstance(value, str):
        raise RelayIngressRejected(f"{field}_invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise RelayIngressRejected(f"{field}_invalid") from exc
    if length is not None and len(decoded) != length:
        raise RelayIngressRejected(f"{field}_invalid")
    return decoded


def parse_relay_envelope(payload: bytes | str) -> RelayEnvelope:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise RelayIngressRejected("payload_invalid")
    if len(encoded) > _MAX_ENVELOPE_BYTES:
        raise RelayIngressRejected("payload_size_rejected")
    try:
        document = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RelayIngressRejected("payload_invalid") from exc
    if not isinstance(document, dict):
        raise RelayIngressRejected("payload_invalid")

    required = {
        "schema",
        "transport",
        "gateway_id",
        "node_id",
        "hop_count",
        "key_epoch",
        "boot_id",
        "seq",
        "nonce_b64",
        "ciphertext_b64",
        "tag_b64",
    }
    if not required.issubset(document):
        raise RelayIngressRejected("required_field_missing")
    if document["schema"] != "gh.relay/1" or document["transport"] != "esp_now":
        raise RelayIngressRejected("schema_or_transport_invalid")
    gateway_id = document["gateway_id"]
    node_id = document["node_id"]
    boot_id = document["boot_id"]
    if not isinstance(gateway_id, str) or _ID.fullmatch(gateway_id) is None:
        raise RelayIngressRejected("outer_identity_invalid")
    if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
        raise RelayIngressRejected("outer_identity_invalid")
    if document["hop_count"] != 1:
        raise RelayIngressRejected("not_single_hop", node_id=node_id)
    key_epoch = document["key_epoch"]
    if not isinstance(key_epoch, int) or isinstance(key_epoch, bool) or key_epoch < 1:
        raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
    seq = document["seq"]
    derive_nonce(boot_id, seq)

    nonce = _decode_b64(document["nonce_b64"], field="nonce", length=12)
    ciphertext = _decode_b64(document["ciphertext_b64"], field="ciphertext")
    tag = _decode_b64(document["tag_b64"], field="tag", length=16)
    if not ciphertext or len(ciphertext) > _MAX_CIPHERTEXT_BYTES:
        raise RelayIngressRejected("ciphertext_size_rejected", node_id=node_id)

    return RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=gateway_id,
        node_id=node_id,
        hop_count=1,
        key_epoch=key_epoch,
        boot_id=boot_id,
        seq=seq,
        nonce=nonce,
        ciphertext=ciphertext,
        tag=tag,
    )


def aes256gcm_decrypt(
    *,
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    tag: bytes,
    aad: bytes,
) -> bytes:
    if len(key) != 32:
        raise RelayIngressRejected("key_material_invalid")
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RelayIngressRejected("aead_backend_unavailable") from exc
    try:
        return AESGCM(key).decrypt(nonce, ciphertext + tag, aad)
    except InvalidTag as exc:
        raise RelayIngressRejected("aead_or_plaintext_rejected") from exc


class N3wRelayIngressCore:
    """Non-live Manager relay ingress core with persistent cross-path replay state.

    This class deliberately does not subscribe to MQTT or publish canonical state.
    Accepted relay plaintext is handed back on the existing direct-ingress topic so
    a later production wiring gate can reuse the canonical Manager pipeline.
    """

    def __init__(
        self,
        *,
        system_id: str,
        authorization: RelayAuthorizationProvider,
        replay_registry: ReplayRegistry,
        telemetry_validator: PackagedTelemetryValidator | None = None,
    ) -> None:
        if _ID.fullmatch(system_id) is None:
            raise ValueError("system_id_invalid")
        self.system_id = system_id
        self.authorization = authorization
        self.replay_registry = replay_registry
        self.telemetry_validator = telemetry_validator or PackagedTelemetryValidator()

    def process(self, topic: str, payload: bytes | str) -> RelayIngressResult:
        try:
            return self._process(topic, payload)
        except RelayIngressRejected as exc:
            return RelayIngressResult(status="rejected", code=exc.code, node_id=exc.node_id)
        except ReplayRegistryUnavailable:
            return RelayIngressResult(status="rejected", code="replay_registry_unavailable")

    def _process(self, topic: str, payload: bytes | str) -> RelayIngressResult:
        parsed_topic = parse_relay_topic(topic)
        if parsed_topic.system_id != self.system_id:
            raise RelayIngressRejected("system_binding_mismatch", node_id=parsed_topic.node_id)
        envelope = parse_relay_envelope(payload)
        if (
            envelope.gateway_id != parsed_topic.gateway_id
            or envelope.node_id != parsed_topic.node_id
        ):
            raise RelayIngressRejected("outer_binding_mismatch", node_id=parsed_topic.node_id)

        key = self.authorization.resolve_key(
            gateway_id=envelope.gateway_id,
            node_id=envelope.node_id,
            key_epoch=envelope.key_epoch,
        )

        inspection = self.replay_registry.inspect(
            node_id=envelope.node_id,
            boot_id=envelope.boot_id,
            seq=envelope.seq,
        )
        if inspection.status == "stale_boot_session":
            raise RelayIngressRejected("stale_boot_session", node_id=envelope.node_id)

        expected_nonce = derive_nonce(envelope.boot_id, envelope.seq)
        if envelope.nonce != expected_nonce:
            raise RelayIngressRejected("nonce_mismatch", node_id=envelope.node_id)

        plaintext = aes256gcm_decrypt(
            key=key,
            nonce=envelope.nonce,
            ciphertext=envelope.ciphertext,
            tag=envelope.tag,
            aad=build_aad(envelope),
        )
        try:
            telemetry = json.loads(plaintext)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise RelayIngressRejected("aead_or_plaintext_rejected", node_id=envelope.node_id) from exc
        if not isinstance(telemetry, dict) or telemetry.get("schema") != "gh.telemetry/1":
            raise RelayIngressRejected("inner_schema_invalid", node_id=envelope.node_id)
        if (
            telemetry.get("node_id"),
            telemetry.get("boot_id"),
            telemetry.get("seq"),
        ) != (envelope.node_id, envelope.boot_id, envelope.seq):
            raise RelayIngressRejected("inner_binding_mismatch", node_id=envelope.node_id)

        try:
            self.telemetry_validator.validate(telemetry)
        except RelayIngressRejected as exc:
            raise RelayIngressRejected(exc.code, node_id=envelope.node_id) from exc
        except Exception as exc:
            raise RelayIngressRejected(
                "telemetry_validation_rejected", node_id=envelope.node_id
            ) from exc

        committed = self.replay_registry.commit(
            node_id=envelope.node_id,
            boot_id=envelope.boot_id,
            seq=envelope.seq,
        )
        if committed.status == "duplicate":
            return RelayIngressResult(
                status="duplicate",
                code="duplicate_node_boot_seq",
                node_id=envelope.node_id,
            )
        if committed.status == "stale_boot_session":
            return RelayIngressResult(
                status="rejected",
                code="stale_boot_session",
                node_id=envelope.node_id,
            )
        return RelayIngressResult(
            status="accepted",
            node_id=envelope.node_id,
            ingress_topic=(
                f"gh/v1/{self.system_id}/ingress/node/{envelope.node_id}/telemetry"
            ),
            telemetry=telemetry,
        )

    def commit_validated_direct_tuple(
        self, *, node_id: str, boot_id: str, seq: int
    ) -> RelayIngressResult:
        """Model the future direct-path shared replay commit without wiring production."""
        try:
            committed = self.replay_registry.commit(
                node_id=node_id,
                boot_id=boot_id,
                seq=seq,
            )
        except (ReplayRegistryUnavailable, ValueError):
            return RelayIngressResult(
                status="rejected",
                code="replay_registry_unavailable",
                node_id=node_id,
            )
        if committed.status == "accepted":
            return RelayIngressResult(status="accepted", node_id=node_id)
        if committed.status == "duplicate":
            return RelayIngressResult(
                status="duplicate",
                code="duplicate_node_boot_seq",
                node_id=node_id,
            )
        return RelayIngressResult(
            status="rejected",
            code="stale_boot_session",
            node_id=node_id,
        )
