from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .mqtt_service import ManagerMqttService
from .n3w_compact_relay import NodeApplicationKeyProvider
from .n3w_multi_ingress_router import MultiIngressResult
from .n3w_phase4_isolated_harness import Phase4IsolatedManagerHarness
from .registration import RegistrationRegistry
from .replay_registry import ReplayRegistry
from .topics import parse_node_telemetry_topic

_LOGGER = logging.getLogger(__name__)


class N3wSimplifiedIsolatedMqttService(ManagerMqttService):
    """Simplified N3-W MQTT entrypoint with no legacy PATH/finite-grant authority.

    Phase 4 originally kept this entrypoint isolated-only. Phase 5-A promotes the
    same validated Direct/Relay router behind the normal Manager service selector.
    The base service is deliberately constructed with both legacy N3-W runtime and
    legacy pairing intake disabled; Direct and Relay ingress are routed only through
    `N3wMultiIngressRouter` and one shared canonical freshness cursor.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        registration: RegistrationRegistry,
        replay: ReplayRegistry,
        keys: NodeApplicationKeyProvider,
    ) -> None:
        # Keep the original one-line replacement as a Phase 4 source-contract
        # compatibility marker, then independently disable the superseded MQTT
        # pairing intake for the promoted Phase 5-A path.
        source_settings = replace(settings, n3w_runtime_enabled=False)
        source_settings = replace(source_settings, pairing_intake_enabled=False)
        super().__init__(source_settings)
        if (
            self.registration_registry is not None
            and self.registration_registry is not registration
        ):
            self.registration_registry.close()
        self.registration_registry = registration
        self.phase4 = Phase4IsolatedManagerHarness(
            system_id=settings.system_id,
            registration=registration,
            replay=replay,
            keys=keys,
            ingress_allowed=registration.is_node_id_ingress_allowed,
            processor=self.processor,
        )

    @property
    def simplified_relay_subscription(self) -> str:
        return f"gh/v1/{self.settings.system_id}/ingress/gateway/+/+/frame"

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
        result, _mid = client.subscribe(self.simplified_relay_subscription, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "MQTT simplified Relay subscribe failed topic=%s rc=%s",
                self.simplified_relay_subscription,
                result,
            )
            return
        _LOGGER.info("Subscribed to %s", self.simplified_relay_subscription)

    def _is_simplified_relay_topic(self, topic: str) -> bool:
        prefix = f"gh/v1/{self.settings.system_id}/ingress/gateway/"
        if not topic.startswith(prefix) or not topic.endswith("/frame"):
            return False
        remainder = topic[len(prefix) : -len("/frame")]
        parts = remainder.split("/")
        return len(parts) == 2 and all(parts)

    def _handle_simplified_result(self, result: MultiIngressResult) -> None:
        if result.status == "accepted":
            canonical_document: dict[str, Any] | None = None
            for outgoing in result.messages:
                self._publish(outgoing)
                if outgoing.topic.endswith("/telemetry") and isinstance(
                    outgoing.payload, dict
                ):
                    canonical_document = outgoing.payload
            if canonical_document is not None:
                self._publish_discovery(canonical_document)
            _LOGGER.info(
                "Accepted simplified N3-W telemetry source=%s node=%s gateway=%s key=%s",
                result.source,
                result.node_id,
                result.gateway_id,
                result.dedup_key,
            )
            return
        if result.status == "duplicate":
            _LOGGER.debug(
                "Ignored simplified N3-W duplicate source=%s node=%s key=%s code=%s",
                result.source,
                result.node_id,
                result.dedup_key,
                result.code,
            )
            return
        _LOGGER.warning(
            "Rejected simplified N3-W ingress source=%s node=%s gateway=%s code=%s",
            result.source,
            result.node_id,
            result.gateway_id,
            result.code,
        )
        if (
            result.source == "direct"
            and result.node_id
            and result.code == "canonical_validation_rejected"
        ):
            self._publish_diagnostic(
                result.node_id,
                result.detail or "unknown validation error",
            )

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        if self._is_simplified_relay_topic(message.topic):
            with self._lifecycle_lock:
                result = self.phase4.process_relay(
                    message.topic,
                    message.payload,
                    received_at=datetime.now(UTC),
                )
            self._handle_simplified_result(result)
            return

        try:
            direct = parse_node_telemetry_topic(message.topic)
        except ValueError:
            direct = None
        if direct is not None:
            if not self.registration_registry.is_node_id_ingress_allowed(direct.node_id):
                _LOGGER.warning(
                    "Rejected simplified Direct telemetry for retired or unassigned node=%s",
                    direct.node_id,
                )
                return
            with self._lifecycle_lock:
                result = self.phase4.process_direct(
                    message.topic,
                    message.payload,
                    received_at=datetime.now(UTC),
                )
            self._handle_simplified_result(result)
            return

        super()._on_message(client, userdata, message)
