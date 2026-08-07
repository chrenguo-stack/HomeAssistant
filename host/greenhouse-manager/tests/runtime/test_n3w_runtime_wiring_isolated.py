from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.n3w_relay_ingress import (
    RelayEnvelope,
    build_aad,
    derive_nonce,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

HOST = os.getenv("GH_N3W_TEST_MQTT_HOST")
PORT_RAW = os.getenv("GH_N3W_TEST_MQTT_PORT")
pytestmark = pytest.mark.skipif(
    not HOST or not PORT_RAW,
    reason="isolated temporary Mosquitto endpoint not configured",
)

SYSTEM_ID = "n3w_iso_001"
NODE_ID = "node_0001"
GATEWAY_ID = "gateway_001"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
BOOT_ID = "boot_0000000000000001"
KEY = bytes(range(32))
KEY_FILE = f"{NODE_ID}-epoch-1.key"
DIRECT_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
RELAY_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/gateway/{GATEWAY_ID}/{NODE_ID}/frame"
CANONICAL_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
NOW = datetime(2026, 8, 7, 12, 30, tzinfo=UTC)


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials"],
        "sent_at_ms": 120345,
    }


def telemetry(seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": BOOT_ID,
        "seq": seq,
        "uptime_ms": 10_000 + seq,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5 + seq / 100},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def relay_payload(seq: int) -> bytes:
    document = telemetry(seq)
    nonce = derive_nonce(BOOT_ID, seq)
    envelope = RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=GATEWAY_ID,
        node_id=NODE_ID,
        hop_count=1,
        key_epoch=1,
        boot_id=BOOT_ID,
        seq=seq,
        nonce=nonce,
        ciphertext=b"placeholder",
        tag=b"0" * 16,
    )
    sealed = AESGCM(KEY).encrypt(
        nonce,
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
        build_aad(envelope),
    )
    outer = {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": GATEWAY_ID,
        "node_id": NODE_ID,
        "hop_count": 1,
        "key_epoch": 1,
        "boot_id": BOOT_ID,
        "seq": seq,
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(sealed[:-16]).decode(),
        "tag_b64": base64.b64encode(sealed[-16:]).decode(),
    }
    return json.dumps(outer, separators=(",", ":")).encode()


def create_runtime_state(tmp_path: Path) -> Settings:
    registration = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(registration) as registry:
        registry.observe_hello(hello(), now=NOW)
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            now=NOW,
        )

    replay = tmp_path / "replay.sqlite3"
    fd = os.open(replay, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with ReplayRegistry(replay):
        pass
    os.chmod(replay, 0o600)

    key_dir = tmp_path / "relay-keys"
    key_dir.mkdir(mode=0o700)
    key_path = key_dir / KEY_FILE
    key_path.write_bytes(KEY)
    os.chmod(key_path, 0o600)

    authorization = tmp_path / "relay-authorization.sqlite3"
    with sqlite3.connect(authorization) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL CHECK (active IN (0,1))
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
                PRIMARY KEY (gateway_id,node_id)
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL CHECK (key_epoch >= 1),
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
                state TEXT NOT NULL CHECK (state IN ('STAGED','ACTIVE','GRACE','REVOKED')),
                key_sha256 TEXT,
                PRIMARY KEY (node_id,key_epoch)
            );
            CREATE TABLE n3w_relay_operations (
                operation_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                node_id TEXT NOT NULL,
                gateway_id TEXT,
                key_epoch INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute("INSERT INTO n3w_relay_meta VALUES (2)")
        connection.execute(
            "INSERT INTO n3w_relay_nodes VALUES (?,1)",
            (NODE_ID,),
        )
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes VALUES (?,?,1)",
            (GATEWAY_ID, NODE_ID),
        )
        connection.execute(
            """
            INSERT INTO n3w_relay_key_epochs
                (node_id,key_epoch,key_file,enabled,state,key_sha256)
            VALUES (?,1,?,1,'ACTIVE',?)
            """,
            (NODE_ID, KEY_FILE, hashlib.sha256(KEY).hexdigest()),
        )
    os.chmod(authorization, 0o600)

    return Settings(
        system_id=SYSTEM_ID,
        mqtt_host=str(HOST),
        mqtt_port=int(str(PORT_RAW)),
        mqtt_client_id="n3w-manager-isolated-1",
        ha_discovery_enabled=False,
        pairing_db_path=str(registration),
        n3w_runtime_enabled=True,
        n3w_replay_db_path=str(replay),
        n3w_relay_authorization_db_path=str(authorization),
        n3w_relay_key_dir=str(key_dir),
        n3w_path_stability_window_s=0,
        n3w_path_minimum_distinct_frames=1,
        n3w_path_lease_ttl_s=1,
        n3w_path_old_grace_s=0,
    )


class SubscriptionBarrier:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self.count = 0

    def callback(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, mid, reason_codes, properties
        with self._condition:
            self.count += 1
            self._condition.notify_all()

    def wait_for(self, target: int, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self.count < target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        f"subscription barrier timed out at {self.count}/{target}"
                    )
                self._condition.wait(remaining)


class CanonicalCapture:
    def __init__(self, host: str, port: int) -> None:
        self._condition = threading.Condition()
        self.documents: list[dict[str, Any]] = []
        self.subscribed = threading.Event()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="n3w-isolated-observer",
            protocol=mqtt.MQTTv5,
        )
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()
        self.client.subscribe(CANONICAL_TOPIC, qos=1)
        if not self.subscribed.wait(5):
            raise AssertionError("observer subscription timed out")

    def _on_subscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, mid, reason_codes, properties
        self.subscribed.set()

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        del client, userdata
        document = json.loads(message.payload.decode("utf-8"))
        with self._condition:
            self.documents.append(document)
            self._condition.notify_all()

    def wait_for_seq(self, seq: int, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                for document in reversed(self.documents):
                    if document.get("seq") == seq:
                        return document
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f"canonical seq {seq} not observed")
                self._condition.wait(remaining)

    def assert_no_new(self, previous_count: int, timeout: float = 0.35) -> None:
        deadline = time.monotonic() + timeout
        with self._condition:
            while len(self.documents) == previous_count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self._condition.wait(remaining)
            raise AssertionError(
                f"unexpected canonical publication count={len(self.documents)} "
                f"previous={previous_count}"
            )

    def close(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


def start_manager(settings: Settings) -> tuple[ManagerMqttService, SubscriptionBarrier]:
    service = ManagerMqttService(settings)
    barrier = SubscriptionBarrier()
    service.client.on_subscribe = barrier.callback
    service.client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    service.client.loop_start()
    barrier.wait_for(3)
    return service, barrier


def stop_manager(service: ManagerMqttService) -> None:
    service.client.disconnect()
    service.client.loop_stop()
    if service.n3w_runtime is not None:
        service.n3w_runtime.close()
    if service.registration_registry is not None:
        service.registration_registry.close()


def publisher(host: str, port: int) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="n3w-isolated-publisher",
        protocol=mqtt.MQTTv5,
    )
    client.connect(host, port, keepalive=30)
    client.loop_start()
    deadline = time.monotonic() + 5
    while not client.is_connected():
        if time.monotonic() >= deadline:
            raise AssertionError("publisher connection timed out")
        time.sleep(0.01)
    return client


def publish(client: mqtt.Client, topic: str, payload: bytes | str) -> None:
    info = client.publish(topic, payload=payload, qos=1, retain=False)
    info.wait_for_publish(timeout=5)
    assert info.rc == mqtt.MQTT_ERR_SUCCESS


def test_isolated_runtime_restart_reconnect_path_and_revoke_matrix(
    tmp_path: Path,
) -> None:
    settings = create_runtime_state(tmp_path)
    capture = CanonicalCapture(settings.mqtt_host, settings.mqtt_port)
    sender = publisher(settings.mqtt_host, settings.mqtt_port)
    first: ManagerMqttService | None = None
    second: ManagerMqttService | None = None
    try:
        first, _barrier = start_manager(settings)

        publish(sender, RELAY_TOPIC, relay_payload(1))
        assert capture.wait_for_seq(1)["node_id"] == NODE_ID

        count = len(capture.documents)
        publish(sender, RELAY_TOPIC, relay_payload(1))
        capture.assert_no_new(count)

        stop_manager(first)
        first = None

        second_settings = replace(settings, mqtt_client_id="n3w-manager-isolated-2")
        second, barrier = start_manager(second_settings)
        count = len(capture.documents)
        publish(sender, RELAY_TOPIC, relay_payload(1))
        capture.assert_no_new(count)

        publish(sender, RELAY_TOPIC, relay_payload(2))
        capture.wait_for_seq(2)

        prior_subscriptions = barrier.count
        second.client.disconnect()
        deadline = time.monotonic() + 5
        while second.client.is_connected():
            if time.monotonic() >= deadline:
                raise AssertionError("manager disconnect timed out")
            time.sleep(0.01)
        second.client.reconnect()
        barrier.wait_for(prior_subscriptions + 3)

        publish(sender, RELAY_TOPIC, relay_payload(3))
        capture.wait_for_seq(3)

        publish(sender, DIRECT_TOPIC, json.dumps(telemetry(4)))
        capture.wait_for_seq(4)

        count = len(capture.documents)
        publish(sender, RELAY_TOPIC, relay_payload(5))
        capture.assert_no_new(count)

        time.sleep(1.1)
        publish(sender, RELAY_TOPIC, relay_payload(6))
        capture.wait_for_seq(6)

        count = len(capture.documents)
        publish(sender, DIRECT_TOPIC, json.dumps(telemetry(6)))
        capture.assert_no_new(count)

        publish(sender, DIRECT_TOPIC, json.dumps(telemetry(5)))
        capture.assert_no_new(count)

        with sqlite3.connect(settings.n3w_relay_authorization_db_path) as connection:
            connection.execute(
                """
                UPDATE n3w_relay_gateway_nodes
                SET enabled=0
                WHERE gateway_id=? AND node_id=?
                """,
                (GATEWAY_ID, NODE_ID),
            )
        time.sleep(0.05)
        publish(sender, RELAY_TOPIC, relay_payload(7))
        capture.assert_no_new(count)
    finally:
        if first is not None:
            stop_manager(first)
        if second is not None:
            stop_manager(second)
        sender.disconnect()
        sender.loop_stop()
        capture.close()
