from __future__ import annotations

import logging
import time
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .ingest import PublishMessage
from .mqtt_service import ManagerMqttService
from .n3w_product_manager_adapter import PeerAuthorizationMqttAdapter
from .n3w_product_peer_authorization import (
    PeerAuthorizationRejected,
    PeerAuthorizationUnavailable,
)

_LOGGER = logging.getLogger(__name__)


class ProductManagerMqttService(ManagerMqttService):
    """Opt-in Manager service that adds Product peer authorization without changing legacy routing."""

    def __init__(
        self,
        settings: Settings,
        peer_authorization: PeerAuthorizationMqttAdapter,
    ) -> None:
        self.peer_authorization = peer_authorization
        super().__init__(settings)

    @property
    def peer_authorization_subscription(self) -> str:
        return f"gh/v1/{self.settings.system_id}/ingress/node/+/relay-peer-auth/request"

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
        result, _mid = client.subscribe(self.peer_authorization_subscription, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "MQTT product peer authorization subscribe failed topic=%s rc=%s",
                self.peer_authorization_subscription,
                result,
            )
            return
        _LOGGER.info("Subscribed to %s", self.peer_authorization_subscription)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        if not self._is_peer_authorization_topic(message.topic):
            super()._on_message(client, userdata, message)
            return
        try:
            response_topic, response_payload = self.peer_authorization.handle(
                topic=message.topic,
                payload=message.payload,
                now_ms=int(time.time() * 1000),
            )
        except PeerAuthorizationRejected as error:
            _LOGGER.warning("Rejected N3-W Product peer authorization code=%s", str(error))
            return
        except PeerAuthorizationUnavailable as error:
            _LOGGER.error("N3-W Product peer authorization unavailable code=%s", str(error))
            return
        self._publish(
            PublishMessage(
                topic=response_topic,
                payload=response_payload,
                qos=1,
                retain=False,
            )
        )

    def _is_peer_authorization_topic(self, topic: str) -> bool:
        prefix = f"gh/v1/{self.settings.system_id}/ingress/node/"
        return topic.startswith(prefix) and topic.endswith("/relay-peer-auth/request")
