from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

BROKER = "broker"
PORT = 1883
SYSTEM_ID = "greenhouse"
REQUEST_TOPIC = f"gh/v1/{SYSTEM_ID}/out/homeassistant/history/projection"
RESULT_TOPIC = (
    f"gh/v1/{SYSTEM_ID}/ingress/homeassistant/history/projection/result"
)
EVIDENCE = Path("/evidence")


def write_json(name: str, document: dict[str, Any]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    target = EVIDENCE / name
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(target)


def summary(message: mqtt.MQTTMessage) -> dict[str, Any]:
    document = json.loads(bytes(message.payload).decode("utf-8"))
    if not isinstance(document, dict):
        raise TypeError("captured MQTT payload is not an object")
    projection = document.get("projection")
    if projection is not None and not isinstance(projection, dict):
        raise TypeError("captured projection is not an object")
    return {
        "topic": message.topic,
        "qos": message.qos,
        "retain": bool(message.retain),
        "payload_bytes": len(message.payload),
        "schema": document.get("schema"),
        "request_id": document.get("request_id"),
        "status": document.get("status"),
        "code": document.get("code"),
        "detail": document.get("detail"),
        "idempotency_key": (
            document.get("idempotency_key")
            if projection is None
            else projection.get("idempotency_key")
        ),
        "revision": (
            document.get("revision")
            if projection is None
            else projection.get("revision")
        ),
        "projection_hash": document.get("projection_hash"),
    }


def main() -> None:
    connected = threading.Event()
    subscribed = threading.Event()
    subscription_allowed = False
    messages: queue.Queue[mqtt.MQTTMessage] = queue.Queue()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="c06b2c-observer",
        protocol=mqtt.MQTTv5,
    )
    client.username_pw_set("tester", os.environ["GH_C06B2C_MQTT_PASSWORD"])

    def on_connect(
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            raise AssertionError(f"MQTT connection rejected: {reason_code}")
        connected.set()

    def on_subscribe(
        _client: mqtt.Client,
        _userdata: Any,
        _mid: int,
        reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        nonlocal subscription_allowed
        subscription_allowed = bool(reason_codes) and all(
            not reason_code.is_failure for reason_code in reason_codes
        )
        subscribed.set()

    def on_message(
        _client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        messages.put(message)

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.connect(BROKER, PORT, keepalive=30)
    client.loop_start()
    try:
        if not connected.wait(10):
            raise AssertionError("MQTT observer connection timed out")
        result, _mid = client.subscribe(
            [(REQUEST_TOPIC, 1), (RESULT_TOPIC, 1)]
        )
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError("MQTT observer subscribe call failed")
        if not subscribed.wait(10) or not subscription_allowed:
            raise AssertionError("MQTT observer SUBACK failed")
        write_json(
            "observer-ready.json",
            {
                "schema": "gh.c06b2c.observer-ready/1",
                "subscribed": True,
                "topics": [REQUEST_TOPIC, RESULT_TOPIC],
                "secret_values_included": False,
            },
        )

        request: dict[str, Any] | None = None
        result_document: dict[str, Any] | None = None
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                message = messages.get(
                    timeout=max(0.1, deadline - time.monotonic())
                )
            except queue.Empty:
                break
            if message.topic == REQUEST_TOPIC and request is None:
                request = summary(message)
                continue
            if message.topic != RESULT_TOPIC or request is None:
                continue
            candidate = summary(message)
            if candidate.get("request_id") == request.get("request_id"):
                result_document = candidate
                break
        if request is None or result_document is None:
            raise AssertionError("matching request and result were not captured")
        write_json(
            "mqtt-capture.json",
            {
                "schema": "gh.c06b2c.mqtt-capture/2",
                "request": request,
                "result": result_document,
                "secret_values_included": False,
                "production_broker_accessed": False,
            },
        )
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
