from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .ingest import PublishMessage
from .n3w_product_authority_time import (
    PeerAuthorizationTimeMqttAdapter,
    PeerAuthorizationTimeRejected,
)
from .n3w_product_manager_adapter import PeerAuthorizationMqttAdapter
from .n3w_product_mqtt_service import ProductManagerMqttService
from .n3w_product_peer_authorization import (
    NodeApplicationKeyProvider,
    PeerAuthorizationRejected,
    PeerAuthorizationUnavailable,
)
from .n3w_relay_ingress import RelayIngressRejected

_LOGGER = logging.getLogger(__name__)
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_AUTHORIZATION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_PAIR_BINDING_FIELDS = (
    "authorization_id",
    "system_id",
    "session_id",
    "child_node_id",
    "relay_node_id",
    "child_credential_generation",
    "relay_credential_generation",
    "child_key_epoch",
    "relay_key_epoch",
    "child_ephemeral_public_key",
    "relay_ephemeral_public_key",
    "child_nonce",
    "relay_nonce",
    "issued_at_ms",
    "expires_at_ms",
    "authorization_epoch",
)


class DynamicIngressAuthorityError(RuntimeError):
    """The finite S5 relay-ingress authorization cannot be trusted."""


@dataclass(frozen=True, slots=True)
class FinitePeerIngressGrant:
    authorization_id: str
    system_id: str
    child_node_id: str
    relay_node_id: str
    child_key_epoch: int
    issued_at_ms: int
    expires_at_ms: int

    def active_at(self, now_ms: int) -> bool:
        return self.issued_at_ms <= now_ms < self.expires_at_ms


class FinitePeerIngressAuthority:
    """RAM-only relay->child ingress grants derived only from an S4 pair grant.

    The registry intentionally has no persistence. Manager restart therefore
    clears every dynamic mapping. A durable relay-authorization row cannot make
    a pair valid in this isolated S5 service.
    """

    def __init__(self, *, system_id: str) -> None:
        if _ID.fullmatch(system_id) is None:
            raise ValueError("system_id_invalid")
        self.system_id = system_id
        self._lock = threading.RLock()
        self._grants: dict[str, FinitePeerIngressGrant] = {}

    @staticmethod
    def _require_int(value: object, *, minimum: int, code: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise DynamicIngressAuthorityError(code)
        return value

    def install_response(self, payload: bytes, *, now_ms: int) -> FinitePeerIngressGrant:
        if not isinstance(payload, bytes):
            raise DynamicIngressAuthorityError("peer_authorization_response_invalid")
        now_ms = self._require_int(now_ms, minimum=0, code="manager_time_invalid")
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DynamicIngressAuthorityError("peer_authorization_response_invalid") from error
        if (
            not isinstance(document, dict)
            or document.get("schema") != "gh.n3w-product.peer-auth-response/1"
            or set(document) != {"schema", "child_grant", "relay_grant"}
        ):
            raise DynamicIngressAuthorityError("peer_authorization_response_invalid")
        child = document["child_grant"]
        relay = document["relay_grant"]
        if not isinstance(child, dict) or not isinstance(relay, dict):
            raise DynamicIngressAuthorityError("peer_authorization_response_invalid")
        if child.get("role") != "child" or relay.get("role") != "relay":
            raise DynamicIngressAuthorityError("peer_authorization_role_invalid")
        for field in _PAIR_BINDING_FIELDS:
            if field not in child or field not in relay or child[field] != relay[field]:
                raise DynamicIngressAuthorityError("peer_authorization_pair_binding_mismatch")

        authorization_id = child["authorization_id"]
        system_id = child["system_id"]
        child_node_id = child["child_node_id"]
        relay_node_id = child["relay_node_id"]
        if not isinstance(authorization_id, str) or _AUTHORIZATION_ID.fullmatch(authorization_id) is None:
            raise DynamicIngressAuthorityError("authorization_id_invalid")
        if system_id != self.system_id:
            raise DynamicIngressAuthorityError("cross_system_rejected")
        if (
            not isinstance(child_node_id, str)
            or _ID.fullmatch(child_node_id) is None
            or not isinstance(relay_node_id, str)
            or _ID.fullmatch(relay_node_id) is None
            or child_node_id == relay_node_id
        ):
            raise DynamicIngressAuthorityError("peer_identity_invalid")
        child_key_epoch = self._require_int(
            child["child_key_epoch"],
            minimum=1,
            code="child_key_epoch_invalid",
        )
        issued_at_ms = self._require_int(
            child["issued_at_ms"],
            minimum=0,
            code="grant_time_invalid",
        )
        expires_at_ms = self._require_int(
            child["expires_at_ms"],
            minimum=1,
            code="grant_time_invalid",
        )
        if expires_at_ms <= issued_at_ms or not (issued_at_ms <= now_ms < expires_at_ms):
            raise DynamicIngressAuthorityError("grant_not_current")

        grant = FinitePeerIngressGrant(
            authorization_id=authorization_id,
            system_id=system_id,
            child_node_id=child_node_id,
            relay_node_id=relay_node_id,
            child_key_epoch=child_key_epoch,
            issued_at_ms=issued_at_ms,
            expires_at_ms=expires_at_ms,
        )
        with self._lock:
            self._purge_locked(now_ms)
            existing = self._grants.get(authorization_id)
            if existing is not None and existing != grant:
                raise DynamicIngressAuthorityError("authorization_id_conflict")
            self._grants[authorization_id] = grant
        return grant

    def revoke(self, authorization_id: str) -> bool:
        if not isinstance(authorization_id, str) or _AUTHORIZATION_ID.fullmatch(authorization_id) is None:
            return False
        with self._lock:
            return self._grants.pop(authorization_id, None) is not None

    def allows(
        self,
        *,
        relay_node_id: str,
        child_node_id: str,
        child_key_epoch: int,
        now_ms: int,
    ) -> bool:
        if (
            not isinstance(relay_node_id, str)
            or _ID.fullmatch(relay_node_id) is None
            or not isinstance(child_node_id, str)
            or _ID.fullmatch(child_node_id) is None
            or not isinstance(child_key_epoch, int)
            or isinstance(child_key_epoch, bool)
            or child_key_epoch < 1
            or not isinstance(now_ms, int)
            or isinstance(now_ms, bool)
            or now_ms < 0
        ):
            return False
        with self._lock:
            self._purge_locked(now_ms)
            return any(
                grant.relay_node_id == relay_node_id
                and grant.child_node_id == child_node_id
                and grant.child_key_epoch == child_key_epoch
                and grant.active_at(now_ms)
                for grant in self._grants.values()
            )

    def audit(self, *, now_ms: int) -> dict[str, object]:
        now_ms = self._require_int(now_ms, minimum=0, code="manager_time_invalid")
        with self._lock:
            self._purge_locked(now_ms)
            return {
                "schema": "gh.n3w-product.s5-dynamic-ingress-authority-audit/1",
                "status": "passed",
                "active_authorization_count": len(self._grants),
                "persistent_mapping_count": 0,
                "restart_restores_authorizations": False,
                "secret_values_included": False,
                "mutated": False,
            }

    def clear(self) -> None:
        with self._lock:
            self._grants.clear()

    def _purge_locked(self, now_ms: int) -> None:
        expired = [
            authorization_id
            for authorization_id, grant in self._grants.items()
            if not grant.active_at(now_ms)
        ]
        for authorization_id in expired:
            self._grants.pop(authorization_id, None)


class S5DynamicRelayAuthorizationProvider:
    """Relay ingress provider gated by the RAM-only finite S4 authorization."""

    def __init__(
        self,
        *,
        authority: FinitePeerIngressAuthority,
        application_keys: NodeApplicationKeyProvider,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.authority = authority
        self.application_keys = application_keys
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))

    def resolve_key(self, *, gateway_id: str, node_id: str, key_epoch: int) -> bytes:
        now_ms = self._now_ms()
        if not self.authority.allows(
            relay_node_id=gateway_id,
            child_node_id=node_id,
            child_key_epoch=key_epoch,
            now_ms=now_ms,
        ):
            raise RelayIngressRejected("gateway_node_unauthorized", node_id=node_id)
        try:
            key = self.application_keys.resolve_node_application_key(
                node_id=node_id,
                key_epoch=key_epoch,
            )
        except PeerAuthorizationRejected as error:
            raise RelayIngressRejected(str(error), node_id=node_id) from error
        except PeerAuthorizationUnavailable as error:
            raise RelayIngressRejected("application_key_unavailable", node_id=node_id) from error
        except Exception as error:
            raise RelayIngressRejected("application_key_unavailable", node_id=node_id) from error
        if not isinstance(key, bytes) or len(key) != 32:
            raise RelayIngressRejected("key_material_invalid", node_id=node_id)
        return key


class N3wProductIsolatedMqttService(ProductManagerMqttService):
    """Explicit opt-in live transport for an isolated S5 lab.

    Normal Manager startup does not instantiate this class. Existing S4 peer
    authorization remains the only peer authority. This subclass adds Manager
    epoch exchange and replaces only the isolated Relay-ingress authorization
    port with finite RAM-only mappings derived from freshly issued S4 grants.
    """

    def __init__(
        self,
        settings: Settings,
        peer_authorization: PeerAuthorizationMqttAdapter,
        application_keys: NodeApplicationKeyProvider | None = None,
    ) -> None:
        if not settings.n3w_runtime_enabled:
            raise ValueError("n3w_runtime_required")
        if application_keys is None:
            raise ValueError("dynamic_application_keys_required")
        self.authority_time = PeerAuthorizationTimeMqttAdapter(
            system_id=settings.system_id
        )
        self.dynamic_ingress = FinitePeerIngressAuthority(
            system_id=settings.system_id
        )
        self.dynamic_relay_authorization = S5DynamicRelayAuthorizationProvider(
            authority=self.dynamic_ingress,
            application_keys=application_keys,
        )
        super().__init__(settings, peer_authorization)
        if self.n3w_runtime is None:
            raise ValueError("n3w_runtime_required")
        # The production-shaped wiring still owns/closes its legacy provider,
        # but the isolated Relay ingress path is gated only by this finite
        # in-memory S4-derived provider. Durable gateway/node rows are ignored.
        self.n3w_runtime.relay_core.authorization = self.dynamic_relay_authorization

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        super()._on_connect(client, userdata, flags, reason_code, properties)
        if reason_code.is_failure:
            return
        result, _mid = client.subscribe(
            self.authority_time.request_subscription,
            qos=1,
        )
        if result != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "MQTT isolated Product authority-time subscribe failed topic=%s rc=%s",
                self.authority_time.request_subscription,
                result,
            )
            return
        _LOGGER.info(
            "Subscribed to %s",
            self.authority_time.request_subscription,
        )

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        if self.authority_time.is_request_topic(message.topic):
            try:
                response_topic, response_payload = self.authority_time.handle(
                    topic=message.topic,
                    payload=message.payload,
                    now_ms=int(time.time() * 1000),
                )
            except PeerAuthorizationTimeRejected as error:
                _LOGGER.warning(
                    "Rejected isolated N3-W Product authority-time request code=%s",
                    str(error),
                )
                return
            self._publish(
                PublishMessage(
                    topic=response_topic,
                    payload=response_payload,
                    qos=1,
                    retain=False,
                )
            )
            return

        if self._is_peer_authorization_topic(message.topic):
            now_ms = int(time.time() * 1000)
            try:
                response_topic, response_payload = self.peer_authorization.handle(
                    topic=message.topic,
                    payload=message.payload,
                    now_ms=now_ms,
                )
                self.dynamic_ingress.install_response(
                    response_payload,
                    now_ms=now_ms,
                )
            except PeerAuthorizationRejected as error:
                _LOGGER.warning(
                    "Rejected isolated N3-W Product peer authorization code=%s",
                    str(error),
                )
                return
            except PeerAuthorizationUnavailable as error:
                _LOGGER.error(
                    "Isolated N3-W Product peer authorization unavailable code=%s",
                    str(error),
                )
                return
            except DynamicIngressAuthorityError as error:
                _LOGGER.error(
                    "Isolated N3-W Product dynamic ingress authority unavailable code=%s",
                    str(error),
                )
                return
            self._publish(
                PublishMessage(
                    topic=response_topic,
                    payload=response_payload,
                    qos=1,
                    retain=False,
                )
            )
            return

        super()._on_message(client, userdata, message)
