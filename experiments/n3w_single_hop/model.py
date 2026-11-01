"""Executable host-only model for the N3-W single-hop ingress contract."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_BOOT_ID = re.compile(r"^boot_([0-9a-f]{16})$")
_MAX_ENVELOPE_BYTES = 4096
_MAX_CIPHERTEXT_BYTES = 1024

TelemetryValidator = Callable[[dict[str, Any]], bool | None]


class ContractRejected(ValueError):
    """Raised internally when an envelope fails closed."""


@dataclass(frozen=True)
class IngressResult:
    status: str
    code: str | None = None
    node_id: str | None = None
    ingress_topic: str | None = None
    telemetry: dict[str, Any] | None = None


@dataclass
class ReplayRegistry:
    """Host-only port model for Manager-owned persistent replay state."""

    available: bool = True
    highest_session: dict[str, int] = field(default_factory=dict)
    seen: set[tuple[str, str, int]] = field(default_factory=set)

    def require_available(self) -> None:
        if not self.available:
            raise ContractRejected("replay_registry_unavailable")

    def validate_before_decrypt(self, *, node_id: str, boot_id: str, seq: int) -> None:
        """Fail closed before decryption when persistent state or session is invalid."""
        self.require_available()
        session = _validate_boot_seq(boot_id, seq)
        highest = self.highest_session.get(node_id)
        if highest is not None and session < highest:
            raise ContractRejected("stale_boot_session")

    def commit(self, *, node_id: str, boot_id: str, seq: int) -> str:
        """Model one atomic cross-path highest-session and replay-set transaction."""
        self.require_available()
        session = _validate_boot_seq(boot_id, seq)
        highest = self.highest_session.get(node_id)
        if highest is not None and session < highest:
            return "stale_boot_session"
        dedup = (node_id, boot_id, seq)
        if dedup in self.seen:
            return "duplicate_node_boot_seq"
        if highest is None or session > highest:
            self.highest_session[node_id] = session
        self.seen.add(dedup)
        return "accepted"


def _boot_session(boot_id: str) -> int:
    match = _BOOT_ID.fullmatch(boot_id)
    if match is None:
        raise ContractRejected("boot_session_invalid")
    session = int(match.group(1), 16)
    if session == 0:
        raise ContractRejected("boot_session_invalid")
    return session


def _validate_boot_seq(boot_id: Any, seq: Any) -> int:
    if not isinstance(boot_id, str):
        raise ContractRejected("boot_session_invalid")
    session = _boot_session(boot_id)
    if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq < 2**32:
        raise ContractRejected("sequence_out_of_range")
    return session


def derive_nonce(node_id: str, boot_id: str, seq: int) -> bytes:
    session = _validate_boot_seq(boot_id, seq)
    del node_id  # The per-node key and AAD provide the node binding.
    return session.to_bytes(8, "big") + seq.to_bytes(4, "big")


def _decode_b64(value: Any, *, field: str, length: int | None = None) -> bytes:
    if not isinstance(value, str):
        raise ContractRejected(f"{field}_invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ContractRejected(f"{field}_invalid") from exc
    if length is not None and len(decoded) != length:
        raise ContractRejected(f"{field}_invalid")
    return decoded


class N3wIngressModel:
    """Validate relay binding and canonical ingress ordering.

    This host-only model is not wired to production entry points.
    """

    def __init__(
        self,
        *,
        system_id: str,
        active_nodes: set[str],
        gateway_nodes: dict[str, set[str]],
        key_epochs: dict[str, set[int]],
        replay_registry: ReplayRegistry,
        telemetry_validator: TelemetryValidator,
    ) -> None:
        self.system_id = system_id
        self.active_nodes = set(active_nodes)
        self.gateway_nodes = {key: set(value) for key, value in gateway_nodes.items()}
        self.key_epochs = {key: set(value) for key, value in key_epochs.items()}
        self.replay_registry = replay_registry
        self.telemetry_validator = telemetry_validator

    def observe_direct(self, *, node_id: str, boot_id: str, seq: int) -> IngressResult:
        """Commit a validated direct tuple before canonical acceptance."""
        try:
            replay_status = self.replay_registry.commit(
                node_id=node_id, boot_id=boot_id, seq=seq
            )
        except ContractRejected as exc:
            return IngressResult(status="rejected", code=str(exc), node_id=node_id)
        if replay_status == "accepted":
            return IngressResult(status="accepted", node_id=node_id)
        return IngressResult(
            status="duplicate"
            if replay_status == "duplicate_node_boot_seq"
            else "rejected",
            code=replay_status,
            node_id=node_id,
        )

    def process(
        self,
        topic: str,
        payload: bytes | str,
        *,
        decrypt: Callable[[bytes, bytes, bytes, bytes], bytes],
    ) -> IngressResult:
        try:
            return self._process(topic, payload, decrypt=decrypt)
        except ContractRejected as exc:
            return IngressResult(status="rejected", code=str(exc))

    def _process(
        self,
        topic: str,
        payload: bytes | str,
        *,
        decrypt: Callable[[bytes, bytes, bytes, bytes], bytes],
    ) -> IngressResult:
        encoded_payload = payload.encode() if isinstance(payload, str) else payload
        if (
            not isinstance(encoded_payload, bytes)
            or len(encoded_payload) > _MAX_ENVELOPE_BYTES
        ):
            raise ContractRejected("payload_size_rejected")
        parts = topic.split("/")
        if (
            len(parts) != 8
            or parts[:2] != ["gh", "v1"]
            or parts[3:5] != ["ingress", "gateway"]
            or parts[7] != "frame"
        ):
            raise ContractRejected("topic_invalid")
        system_id, gateway_id, topic_node_id = parts[2], parts[5], parts[6]
        if system_id != self.system_id:
            raise ContractRejected("system_binding_mismatch")
        if not all(_ID.fullmatch(value) for value in (gateway_id, topic_node_id)):
            raise ContractRejected("topic_identity_invalid")
        try:
            document = json.loads(encoded_payload)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise ContractRejected("payload_invalid") from exc
        if not isinstance(document, dict):
            raise ContractRejected("payload_invalid")
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
            raise ContractRejected("required_field_missing")
        if document["schema"] != "gh.relay/1" or document["transport"] != "esp_now":
            raise ContractRejected("schema_or_transport_invalid")
        node_id = document["node_id"]
        boot_id = document["boot_id"]
        if document["gateway_id"] != gateway_id or node_id != topic_node_id:
            raise ContractRejected("outer_binding_mismatch")
        if (
            not isinstance(node_id, str)
            or not isinstance(boot_id, str)
            or not _ID.fullmatch(boot_id)
        ):
            raise ContractRejected("outer_identity_invalid")
        if document["hop_count"] != 1:
            raise ContractRejected("not_single_hop")
        if node_id not in self.active_nodes:
            raise ContractRejected("node_not_active")
        if node_id not in self.gateway_nodes.get(gateway_id, set()):
            raise ContractRejected("gateway_node_unauthorized")
        epoch, seq = document["key_epoch"], document["seq"]
        if (
            not isinstance(epoch, int)
            or isinstance(epoch, bool)
            or epoch not in self.key_epochs.get(node_id, set())
        ):
            raise ContractRejected("key_epoch_rejected")
        self.replay_registry.validate_before_decrypt(
            node_id=node_id, boot_id=boot_id, seq=seq
        )
        nonce = _decode_b64(document["nonce_b64"], field="nonce", length=12)
        if nonce != derive_nonce(node_id, boot_id, seq):
            raise ContractRejected("nonce_mismatch")
        ciphertext = _decode_b64(document["ciphertext_b64"], field="ciphertext")
        tag = _decode_b64(document["tag_b64"], field="tag", length=16)
        if not ciphertext or len(ciphertext) > _MAX_CIPHERTEXT_BYTES:
            raise ContractRejected("ciphertext_size_rejected")
        aad_document = {
            key: document[key]
            for key in (
                "schema",
                "transport",
                "gateway_id",
                "node_id",
                "hop_count",
                "key_epoch",
                "boot_id",
                "seq",
            )
        }
        aad = json.dumps(aad_document, separators=(",", ":"), sort_keys=True).encode()
        try:
            plaintext = decrypt(nonce, ciphertext, tag, aad)
            telemetry = json.loads(plaintext)
        except Exception as exc:
            raise ContractRejected("aead_or_plaintext_rejected") from exc
        if (
            not isinstance(telemetry, dict)
            or telemetry.get("schema") != "gh.telemetry/1"
        ):
            raise ContractRejected("inner_schema_invalid")
        if "received_at" in telemetry:
            raise ContractRejected("manager_owned_field_present")
        if (
            telemetry.get("node_id"),
            telemetry.get("boot_id"),
            telemetry.get("seq"),
        ) != (node_id, boot_id, seq):
            raise ContractRejected("inner_binding_mismatch")
        try:
            validation_result = self.telemetry_validator(telemetry)
        except Exception as exc:
            raise ContractRejected("telemetry_validation_rejected") from exc
        if validation_result is not None and validation_result is not True:
            raise ContractRejected("telemetry_validation_rejected")
        replay_status = self.replay_registry.commit(
            node_id=node_id, boot_id=boot_id, seq=seq
        )
        if replay_status != "accepted":
            return IngressResult(
                status="duplicate"
                if replay_status == "duplicate_node_boot_seq"
                else "rejected",
                code=replay_status,
                node_id=node_id,
            )
        return IngressResult(
            status="accepted",
            node_id=node_id,
            ingress_topic=f"gh/v1/{self.system_id}/ingress/node/{node_id}/telemetry",
            telemetry=telemetry,
        )
