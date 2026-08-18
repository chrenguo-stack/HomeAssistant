from __future__ import annotations

import base64
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .n3w_product_peer_authorization import (
    EndpointGrant,
    EndpointHandshake,
    PairAuthorization,
    PeerAuthorizationRejected,
    PeerAuthorizationRequest,
    PeerAuthorizationService,
    PeerAuthorizationUnavailable,
    RelayEligibilitySnapshot,
    RelayRuntimeHealth,
)
from .registration import RegistrationRegistry, RegistrationState
from .replay_registry import ReplayRegistry, ReplayRegistryUnavailable

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_REQUEST_SCHEMA = "gh.n3w-product.peer-auth-request/1"
_RESPONSE_SCHEMA = "gh.n3w-product.peer-auth-response/1"
_RELAY_CAPABILITY = "n3w-product-relay"


@dataclass(frozen=True, slots=True)
class ActivePathSnapshot:
    transport: str
    gateway_id: str | None
    valid_until_ms: int
    revision: int


class ReplayRegistryPathAuthority:
    """Read the Manager's canonical path lease without accepting a relay self-claim as uplink proof."""

    def __init__(self, replay_registry: ReplayRegistry) -> None:
        self.replay_registry = replay_registry

    def get_active_path(self, *, node_id: str) -> ActivePathSnapshot | None:
        if _ID.fullmatch(node_id) is None:
            raise PeerAuthorizationRejected("relay_identity_invalid")
        try:
            with self.replay_registry._lock:  # noqa: SLF001 - same-store read-only authority
                self.replay_registry._require_open()  # noqa: SLF001
                row = self.replay_registry._connection.execute(  # noqa: SLF001
                    """
                    SELECT active_transport, active_gateway_id, lease_expires_at, revision
                    FROM n3w_path_leases
                    WHERE node_id = ?
                    """,
                    (node_id,),
                ).fetchone()
        except (sqlite3.Error, ReplayRegistryUnavailable) as error:
            raise PeerAuthorizationUnavailable("path_authority_unavailable") from error
        if row is None:
            return None
        transport = row["active_transport"]
        gateway_id = row["active_gateway_id"]
        revision = row["revision"]
        if transport not in {"direct", "relay"}:
            raise PeerAuthorizationUnavailable("path_authority_corrupt")
        if transport == "direct" and gateway_id is not None:
            raise PeerAuthorizationUnavailable("path_authority_corrupt")
        if transport == "relay" and (not isinstance(gateway_id, str) or _ID.fullmatch(gateway_id) is None):
            raise PeerAuthorizationUnavailable("path_authority_corrupt")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise PeerAuthorizationUnavailable("path_authority_corrupt")
        try:
            expires_at = datetime.fromisoformat(str(row["lease_expires_at"]).replace("Z", "+00:00"))
        except ValueError as error:
            raise PeerAuthorizationUnavailable("path_authority_corrupt") from error
        if expires_at.tzinfo is None:
            raise PeerAuthorizationUnavailable("path_authority_corrupt")
        return ActivePathSnapshot(
            transport=transport,
            gateway_id=gateway_id,
            valid_until_ms=int(expires_at.timestamp() * 1000),
            revision=revision,
        )


class ManagerRelayEligibilityProvider:
    """Combine Manager registration + canonical Direct path + signed relay health."""

    def __init__(
        self,
        registry: RegistrationRegistry,
        path_authority: ReplayRegistryPathAuthority,
        *,
        system_id: str,
        max_health_age_ms: int = 15_000,
        max_future_skew_ms: int = 2_000,
    ) -> None:
        if _ID.fullmatch(system_id) is None:
            raise ValueError("system_id is invalid")
        if max_health_age_ms < 1 or max_future_skew_ms < 0:
            raise ValueError("relay health policy is invalid")
        self.registry = registry
        self.path_authority = path_authority
        self.system_id = system_id
        self.max_health_age_ms = max_health_age_ms
        self.max_future_skew_ms = max_future_skew_ms

    def get_relay_eligibility(
        self,
        *,
        system_id: str,
        node_id: str,
        health: RelayRuntimeHealth,
        now_ms: int,
    ) -> RelayEligibilitySnapshot:
        if system_id != self.system_id:
            raise PeerAuthorizationRejected("cross_system_rejected")
        if not health.valid_shape():
            raise PeerAuthorizationRejected("relay_health_invalid")

        matches = [record for record in self.registry.list_current() if record.node_id == node_id]
        record = matches[0] if len(matches) == 1 else None
        registered = (
            record is not None
            and record.state is RegistrationState.APPROVED
            and record.retired_at is None
        )
        relay_capability_registered = registered and _RELAY_CAPABILITY in record.capabilities
        path = self.path_authority.get_active_path(node_id=node_id) if registered else None
        direct_live = path is not None and path.transport == "direct" and now_ms < path.valid_until_ms

        health_valid_until = health.observed_at_ms + self.max_health_age_ms
        health_fresh = (
            health.observed_at_ms <= now_ms + self.max_future_skew_ms
            and now_ms < health_valid_until
        )
        valid_until_ms = min(
            path.valid_until_ms if path is not None else now_ms,
            health_valid_until,
        )
        return RelayEligibilitySnapshot(
            registered=registered,
            same_system=registered,
            wifi_up=direct_live,
            uplink_available=direct_live,
            direct_uplink=direct_live,
            relay_capable=bool(relay_capability_registered and health.relay_capable and health_fresh),
            low_battery=health.low_battery,
            overloaded=health.overloaded,
            retired=record is not None and record.retired_at is not None,
            revoked=False,
            valid_until_ms=valid_until_ms,
        )


class PeerAuthorizationMqttAdapter:
    """Pure Manager MQTT request/response adapter under the relay node's existing ACL subtree."""

    def __init__(self, service: PeerAuthorizationService) -> None:
        self.service = service

    @staticmethod
    def request_topic(*, system_id: str, relay_node_id: str) -> str:
        return f"gh/v1/{system_id}/ingress/node/{relay_node_id}/relay-peer-auth/request"

    @staticmethod
    def response_topic(*, system_id: str, relay_node_id: str, session_id: str) -> str:
        return f"gh/v1/{system_id}/out/node/{relay_node_id}/relay-peer-auth/{session_id}"

    def handle(self, *, topic: str, payload: bytes, now_ms: int) -> tuple[str, bytes]:
        system_id, relay_node_id = self._parse_request_topic(topic)
        request = decode_peer_authorization_request(payload)
        if request.system_id != system_id or request.relay.node_id != relay_node_id:
            raise PeerAuthorizationRejected("mqtt_topic_identity_mismatch")
        authorization = self.service.authorize(request, now_ms=now_ms)
        response = encode_peer_authorization_response(authorization)
        return (
            self.response_topic(
                system_id=system_id,
                relay_node_id=relay_node_id,
                session_id=request.session_id,
            ),
            response,
        )

    @staticmethod
    def _parse_request_topic(topic: str) -> tuple[str, str]:
        parts = topic.split("/")
        if (
            len(parts) != 8
            or parts[0:2] != ["gh", "v1"]
            or parts[3:5] != ["ingress", "node"]
            or parts[6:8] != ["relay-peer-auth", "request"]
            or _ID.fullmatch(parts[2]) is None
            or _ID.fullmatch(parts[5]) is None
        ):
            raise PeerAuthorizationRejected("mqtt_topic_rejected")
        return parts[2], parts[5]


def decode_peer_authorization_request(payload: bytes) -> PeerAuthorizationRequest:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PeerAuthorizationRejected("peer_request_json_invalid") from error
    if not isinstance(document, dict) or set(document) != {
        "schema",
        "system_id",
        "session_id",
        "requested_at_ms",
        "child",
        "relay",
        "relay_health",
    }:
        raise PeerAuthorizationRejected("peer_request_fields_invalid")
    if document["schema"] != _REQUEST_SCHEMA:
        raise PeerAuthorizationRejected("peer_request_schema_invalid")
    child = _decode_endpoint(document["child"])
    relay = _decode_endpoint(document["relay"])
    health_document = document["relay_health"]
    if not isinstance(health_document, dict) or set(health_document) != {
        "observed_at_ms",
        "relay_capable",
        "low_battery",
        "overloaded",
    }:
        raise PeerAuthorizationRejected("relay_health_fields_invalid")
    health = RelayRuntimeHealth(
        observed_at_ms=health_document["observed_at_ms"],
        relay_capable=health_document["relay_capable"],
        low_battery=health_document["low_battery"],
        overloaded=health_document["overloaded"],
    )
    request = PeerAuthorizationRequest(
        system_id=document["system_id"],
        session_id=document["session_id"],
        requested_at_ms=document["requested_at_ms"],
        child=child,
        relay=relay,
        relay_health=health,
    )
    if not request.valid_shape() or len(child.proof) != 32 or len(relay.proof) != 32:
        raise PeerAuthorizationRejected("peer_request_shape_invalid")
    return request


def encode_peer_authorization_request(request: PeerAuthorizationRequest) -> bytes:
    document = {
        "schema": _REQUEST_SCHEMA,
        "system_id": request.system_id,
        "session_id": request.session_id,
        "requested_at_ms": request.requested_at_ms,
        "child": _endpoint_document(request.child),
        "relay": _endpoint_document(request.relay),
        "relay_health": {
            "observed_at_ms": request.relay_health.observed_at_ms,
            "relay_capable": request.relay_health.relay_capable,
            "low_battery": request.relay_health.low_battery,
            "overloaded": request.relay_health.overloaded,
        },
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_peer_authorization_response(authorization: PairAuthorization) -> bytes:
    document = {
        "schema": _RESPONSE_SCHEMA,
        "child_grant": _grant_document(authorization.child_grant),
        "relay_grant": _grant_document(authorization.relay_grant),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_endpoint(value: Any) -> EndpointHandshake:
    if not isinstance(value, dict) or set(value) != {
        "node_id",
        "credential_generation",
        "key_epoch",
        "ephemeral_public_key",
        "nonce",
        "proof",
    }:
        raise PeerAuthorizationRejected("peer_endpoint_fields_invalid")
    try:
        return EndpointHandshake(
            node_id=value["node_id"],
            credential_generation=value["credential_generation"],
            key_epoch=value["key_epoch"],
            ephemeral_public_key=_decode_b64_32(value["ephemeral_public_key"]),
            nonce=_decode_b64_32(value["nonce"]),
            proof=_decode_b64_32(value["proof"]),
        )
    except (TypeError, ValueError) as error:
        raise PeerAuthorizationRejected("peer_endpoint_encoding_invalid") from error


def _endpoint_document(endpoint: EndpointHandshake) -> dict[str, object]:
    return {
        "node_id": endpoint.node_id,
        "credential_generation": endpoint.credential_generation,
        "key_epoch": endpoint.key_epoch,
        "ephemeral_public_key": _b64(endpoint.ephemeral_public_key),
        "nonce": _b64(endpoint.nonce),
        "proof": _b64(endpoint.proof),
    }


def _grant_document(grant: EndpointGrant) -> dict[str, object]:
    return {
        "role": grant.role,
        "authorization_id": grant.authorization_id,
        "system_id": grant.system_id,
        "session_id": grant.session_id,
        "child_node_id": grant.child_node_id,
        "relay_node_id": grant.relay_node_id,
        "child_credential_generation": grant.child_credential_generation,
        "relay_credential_generation": grant.relay_credential_generation,
        "child_key_epoch": grant.child_key_epoch,
        "relay_key_epoch": grant.relay_key_epoch,
        "child_ephemeral_public_key": _b64(grant.child_ephemeral_public_key),
        "relay_ephemeral_public_key": _b64(grant.relay_ephemeral_public_key),
        "child_nonce": _b64(grant.child_nonce),
        "relay_nonce": _b64(grant.relay_nonce),
        "issued_at_ms": grant.issued_at_ms,
        "expires_at_ms": grant.expires_at_ms,
        "authorization_epoch": grant.authorization_epoch,
        "grant_mac": _b64(grant.grant_mac),
    }


def _decode_b64_32(value: object) -> bytes:
    if not isinstance(value, str) or "=" in value:
        raise ValueError("base64url value invalid")
    padding = "=" * ((4 - len(value) % 4) % 4)
    decoded = base64.urlsafe_b64decode(value + padding)
    if len(decoded) != 32:
        raise ValueError("base64url value must decode to 32 bytes")
    return decoded


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
