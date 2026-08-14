from __future__ import annotations

import logging
import time
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

_LOGGER = logging.getLogger(__name__)


class N3wProductIsolatedMqttService(ProductManagerMqttService):
    """Explicit opt-in live transport for an isolated S5 lab.

    Normal Manager startup does not instantiate this class. Existing S4 peer
    authorization and normal N3-W relay ingress remain owned by the parent
    service; this subclass adds only the Manager-epoch transport exchange.
    """

    def __init__(
        self,
        settings: Settings,
        peer_authorization: PeerAuthorizationMqttAdapter,
    ) -> None:
        if not settings.n3w_runtime_enabled:
            raise ValueError("n3w_runtime_required")
        self.authority_time = PeerAuthorizationTimeMqttAdapter(
            system_id=settings.system_id
        )
        super().__init__(settings, peer_authorization)

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
        if not self.authority_time.is_request_topic(message.topic):
            super()._on_message(client, userdata, message)
            return
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
