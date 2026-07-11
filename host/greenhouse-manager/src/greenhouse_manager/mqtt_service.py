from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .ingest import PublishMessage, TelemetryProcessor
from .topics import (
    canonical_telemetry_subscription,
    diagnostic_topic,
    ingress_subscription,
)

_LOGGER = logging.getLogger(__name__)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ManagerMqttService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.processor = TelemetryProcessor(
            system_id=settings.system_id,
            dedup_capacity=settings.dedup_capacity,
            stale_after_s=settings.stale_after_s,
        )
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv5,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.enable_logger(_LOGGER)

        if settings.mqtt_username and settings.mqtt_password:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self.client.tls_set(ca_certs=settings.mqtt_ca_file)

    def _publish(self, message: PublishMessage) -> bool:
        info = self.client.publish(
            message.topic,
            payload=_json_bytes(message.payload),
            qos=message.qos,
            retain=message.retain,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error("MQTT publish failed topic=%s rc=%s", message.topic, info.rc)
            return False
        return True

    def _publish_diagnostic(self, node_id: str, reason: str) -> None:
        self._publish(
            PublishMessage(
                topic=diagnostic_topic(self.settings.system_id, node_id),
                payload={
                    "schema": "gh.diagnostic/1",
                    "node_id": node_id,
                    "state": "invalid_telemetry",
                    "message": reason[:512],
                    "updated_at": _now_text(),
                },
            )
        )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            _LOGGER.error("MQTT connection rejected: %s", reason_code)
            return

        topics = (
            ingress_subscription(self.settings.system_id),
            canonical_telemetry_subscription(self.settings.system_id),
        )
        for topic in topics:
            result, _mid = client.subscribe(topic, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.error("MQTT subscribe failed topic=%s rc=%s", topic, result)
                continue
            _LOGGER.info("Subscribed to %s", topic)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            _LOGGER.warning("Unexpected MQTT disconnect: %s", reason_code)
        else:
            _LOGGER.info("MQTT disconnected")

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        canonical_prefix = f"gh/v1/{self.settings.system_id}/state/"
        if message.topic.startswith(canonical_prefix) and message.topic.endswith("/telemetry"):
            restored = self.processor.restore_canonical(message.topic, message.payload)
            if restored.status == "restored":
                _LOGGER.debug(
                    "Restored canonical telemetry node=%s key=%s last_seen=%s",
                    restored.node_id,
                    restored.dedup_key,
                    restored.last_seen,
                )
            else:
                _LOGGER.warning(
                    "Rejected canonical telemetry recovery node=%s reason=%s",
                    restored.node_id,
                    restored.reason,
                )
            return

        result = self.processor.process(message.topic, message.payload)

        if result.status == "accepted":
            for outgoing in result.messages:
                self._publish(outgoing)
            _LOGGER.info("Accepted telemetry node=%s key=%s", result.node_id, result.dedup_key)
            return

        if result.status == "duplicate":
            _LOGGER.debug("Ignored duplicate telemetry node=%s key=%s", result.node_id, result.dedup_key)
            return

        _LOGGER.warning("Rejected telemetry node=%s reason=%s", result.node_id, result.reason)
        if result.node_id:
            self._publish_diagnostic(result.node_id, result.reason or "unknown validation error")

    def run(self) -> None:
        _LOGGER.info(
            "Starting greenhouse-manager system_id=%s broker=%s:%d",
            self.settings.system_id,
            self.settings.mqtt_host,
            self.settings.mqtt_port,
        )
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
        self.client.loop_start()

        try:
            while True:
                time.sleep(5)
                for message in self.processor.stale_messages():
                    if self._publish(message):
                        _LOGGER.info("Published unavailable state topic=%s", message.topic)
                        continue

                    node_id = message.payload.get("node_id")
                    if isinstance(node_id, str):
                        self.processor.mark_unavailable_publish_failed(node_id)
                    _LOGGER.warning("Deferred unavailable state topic=%s; will retry", message.topic)
        except KeyboardInterrupt:
            _LOGGER.info("Stopping greenhouse-manager")
        finally:
            self.client.disconnect()
            self.client.loop_stop()
