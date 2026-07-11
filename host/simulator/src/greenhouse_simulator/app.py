from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .pairing import build_pairing_hello
from .payload import build_telemetry

_LOGGER = logging.getLogger(__name__)


def _topic(system_id: str, node_id: str) -> str:
    return f"gh/v1/{system_id}/ingress/node/{node_id}/telemetry"


def _pairing_topic(hardware_id: str) -> str:
    return f"gh/bootstrap/v1/node/{hardware_id}/hello"


def _payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


class Simulator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connected = threading.Event()
        self.boot_id = f"boot_{uuid.uuid4().hex}"
        self.started_monotonic = time.monotonic()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{settings.node_id}",
            protocol=mqtt.MQTTv5,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.enable_logger(_LOGGER)

        if settings.mqtt_username and settings.mqtt_password:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

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
        self.connected.set()
        _LOGGER.info("Connected to MQTT broker")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        self.connected.clear()
        if reason_code.is_failure:
            _LOGGER.warning("Unexpected MQTT disconnect: %s", reason_code)

    def _publish_pairing_hello(self) -> None:
        payload = build_pairing_hello(
            hardware_id=self.settings.hardware_id,
            pairing_epoch=self.settings.pairing_epoch,
            sent_at_ms=int((time.monotonic() - self.started_monotonic) * 1000),
        )
        topic = _pairing_topic(self.settings.hardware_id)
        info = self.client.publish(topic, _payload_bytes(payload), qos=1, retain=False)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise RuntimeError("MQTT publish timed out for pairing hello")
        _LOGGER.info(
            "Published pairing hello hardware_suffix=%s pairing_prefix=%s epoch=%s",
            self.settings.hardware_id[-6:],
            str(payload["pairing_id"])[:8],
            self.settings.pairing_epoch,
        )

    def _publish(self, payload: dict[str, Any], *, label: str) -> None:
        topic = _topic(self.settings.system_id, self.settings.node_id)
        info = self.client.publish(topic, _payload_bytes(payload), qos=1, retain=False)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise RuntimeError(f"MQTT publish timed out for {label}")
        _LOGGER.info(
            "Published %s telemetry node=%s boot=%s seq=%s",
            label,
            self.settings.node_id,
            payload["boot_id"],
            payload["seq"],
        )

    def run(self) -> None:
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
        self.client.loop_start()

        try:
            if not self.connected.wait(timeout=20):
                raise RuntimeError("MQTT connection timed out")
            if self.settings.initial_delay_s:
                time.sleep(self.settings.initial_delay_s)
            if self.settings.pairing_hello_enabled:
                self._publish_pairing_hello()

            seq = 0
            published = 0
            while self.settings.publish_count == 0 or published < self.settings.publish_count:
                invalid = self.settings.invalid_every > 0 and (seq + 1) % self.settings.invalid_every == 0
                payload = build_telemetry(
                    node_id=self.settings.node_id,
                    boot_id=self.boot_id,
                    seq=seq,
                    uptime_ms=int((time.monotonic() - self.started_monotonic) * 1000),
                    now=datetime.now(UTC),
                    invalid=invalid,
                )
                self._publish(payload, label="invalid" if invalid else "valid")

                if (
                    not invalid
                    and self.settings.duplicate_every > 0
                    and (seq + 1) % self.settings.duplicate_every == 0
                ):
                    self._publish(payload, label="duplicate")

                seq += 1
                published += 1
                if self.settings.publish_count == 0 or published < self.settings.publish_count:
                    time.sleep(self.settings.publish_interval_s)
        finally:
            self.client.disconnect()
            self.client.loop_stop()


def main() -> int:
    try:
        settings = Settings.from_env()
    except (TypeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        Simulator(settings).run()
    except (OSError, RuntimeError) as exc:
        _LOGGER.error("Simulator stopped: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
