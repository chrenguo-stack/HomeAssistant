"""Executable host-only model for the N3-W single-hop ingress contract."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_MAX_ENVELOPE_BYTES = 4096
_MAX_CIPHERTEXT_BYTES = 1024


class ContractRejected(ValueError):
    """Raised internally when an envelope fails closed."""


@dataclass(frozen=True)
class IngressResult:
    status: str
    code: str | None = None
    node_id: str | None = None
    ingress_topic: str | None = None
    telemetry: dict[str, Any] | None = None


def derive_nonce(node_id: str, boot_id: str, seq: int) -> bytes:
    if not 0 <= seq < 2**32:
        raise ContractRejected("sequence_out_of_range")
    prefix = hashlib.sha256(f"{node_id}\0{boot_id}".encode()).digest()[:8]
    return prefix + seq.to_bytes(4, "big")


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
    """Validates relay binding before an injected AEAD implementation is called."""

    def __init__(
        self,
        *,
        system_id: str,
        active_nodes: set[str],
        gateway_nodes: dict[str, set[str]],
        key_epochs: dict[str, set[int]],
    ) -> None:
        self.system_id = system_id
        self.active_nodes = set(active_nodes)
        self.gateway_nodes = {key: set(value) for key, value in gateway_nodes.items()}
        self.key_epochs = {key: set(value) for key, value in key_epochs.items()}
        self._seen: set[tuple[str, str, int]] = set()

    def observe_direct(self, *, node_id: str, boot_id: str, seq: int) -> None:
        """Models the existing direct-ingress dedup set shared with relay ingress."""
        self._seen.add((node_id, boot_id, seq))

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
        if not isinstance(seq, int) or isinstance(seq, bool):
            raise ContractRejected("sequence_out_of_range")
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
        dedup = (node_id, boot_id, seq)
        if dedup in self._seen:
            return IngressResult(
                status="duplicate", code="duplicate_node_boot_seq", node_id=node_id
            )
        self._seen.add(dedup)
        return IngressResult(
            status="accepted",
            node_id=node_id,
            ingress_topic=f"gh/v1/{self.system_id}/ingress/node/{node_id}/telemetry",
            telemetry=telemetry,
        )
