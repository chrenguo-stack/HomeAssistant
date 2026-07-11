from __future__ import annotations

import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from greenhouse_manager.dynsec_api import (
    DynsecError,
    DynsecProvisioner,
    PahoDynsecTransport,
    RESPONSE_TOPIC,
)
from greenhouse_manager.dynsec_plan import build_node_provisioning_plan, generate_node_credentials

BROKER = "broker"
PORT = 1883


@dataclass
class SubscriptionResult:
    event: threading.Event
    allowed: bool | None = None


class Session:
    def __init__(self, *, client_id: str, username: str, password: str) -> None:
        self.connected = threading.Event()
        self.connection_allowed: bool | None = None
        self.messages: queue.Queue[tuple[str, bytes]] = queue.Queue()
        self.subscriptions: dict[int, SubscriptionResult] = {}
        self.message_hook: Any = None
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        self.connection_allowed = not reason_code.is_failure
        self.connected.set()

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        if self.message_hook is not None:
            self.message_hook(client, userdata, message)
        if message.topic != RESPONSE_TOPIC:
            self.messages.put((message.topic, bytes(message.payload)))

    def _on_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        mid: int,
        reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        result = self.subscriptions.get(mid)
        if result is not None:
            result.allowed = bool(reason_codes) and all(not code.is_failure for code in reason_codes)
            result.event.set()

    def start(self, *, expect_allowed: bool = True) -> None:
        self.client.connect(BROKER, PORT, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(10):
            raise AssertionError("MQTT connection result timed out")
        assert self.connection_allowed is expect_allowed

    def subscribe(self, topic: str) -> bool:
        result_code, mid = self.client.subscribe(topic, qos=1)
        assert result_code == mqtt.MQTT_ERR_SUCCESS
        result = SubscriptionResult(threading.Event())
        self.subscriptions[mid] = result
        if not result.event.wait(5):
            raise AssertionError(f"SUBACK timed out for {topic}")
        return bool(result.allowed)

    def publish(self, topic: str, payload: bytes = b"test") -> None:
        info = self.client.publish(topic, payload=payload, qos=1, retain=False)
        try:
            info.wait_for_publish(timeout=5)
        except RuntimeError:
            pass

    def wait_for(self, topic: str, *, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                received_topic, _payload = self.messages.get(timeout=deadline - time.monotonic())
            except queue.Empty:
                return False
            if received_topic == topic:
                return True
        return False

    def drain(self) -> None:
        while True:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                return

    def close(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


def main() -> None:
    admin_password = os.environ["GH_DYNSEC_ADMIN_PASSWORD"]
    admin = Session(client_id="gh-dynsec-test-admin", username="admin", password=admin_password)
    admin.start()
    transport = PahoDynsecTransport(admin.client)
    admin.message_hook = transport.on_message
    provisioner = DynsecProvisioner(transport)

    first_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-test-node-001", generation=1
    )
    second_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-test-node-002", generation=1
    )
    first_credentials = generate_node_credentials(first_plan)
    second_credentials = generate_node_credentials(second_plan)

    provisioner.apply_baseline(first_plan)
    provisioner.provision(first_plan, first_credentials)
    provisioner.provision(second_plan, second_credentials)

    assert admin.subscribe("#")

    first = Session(
        client_id=first_credentials.client_id,
        username=first_credentials.username,
        password=first_credentials.password,
    )
    second = Session(
        client_id=second_credentials.client_id,
        username=second_credentials.username,
        password=second_credentials.password,
    )
    first.start()
    second.start()

    own_out = "gh/v1/greenhouse/out/node/gh-test-node-001/#"
    other_out = "gh/v1/greenhouse/out/node/gh-test-node-002/#"
    assert first.subscribe(own_out)
    assert not first.subscribe(other_out)
    assert not first.subscribe("#")

    wrong_id = Session(
        client_id="wrong-client-id",
        username=first_credentials.username,
        password=first_credentials.password,
    )
    wrong_id.start(expect_allowed=False)
    wrong_id.close()

    allowed = "gh/v1/greenhouse/ingress/node/gh-test-node-001/telemetry"
    admin.drain()
    first.publish(allowed)
    assert admin.wait_for(allowed)

    denied_topics = (
        "gh/v1/greenhouse/ingress/node/gh-test-node-002/telemetry",
        "gh/v1/greenhouse/state/gh-test-node-001/telemetry",
        "homeassistant/device/gh-test-node-001/config",
    )
    for topic in denied_topics:
        admin.drain()
        first.publish(topic)
        assert not admin.wait_for(topic, timeout=1.0), topic

    canary_username = "gh-dynsec-forbidden-canary"
    forbidden_command = json.dumps(
        {
            "commands": [
                {
                    "command": "createClient",
                    "username": canary_username,
                    "password": "not-a-real-secret",
                    "clientid": "gh-dynsec-forbidden-canary",
                }
            ]
        },
        separators=(",", ":"),
    ).encode()
    first.publish("$CONTROL/dynamic-security/v1", forbidden_command)
    time.sleep(0.5)
    try:
        transport.execute(({"command": "getClient", "username": canary_username},))
    except DynsecError:
        pass
    else:
        raise AssertionError("unauthorized Dynamic Security command created a client")

    first.close()
    second.close()

    replacement_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-test-node-001", generation=2
    )
    replacement_credentials = generate_node_credentials(replacement_plan)

    def verify_replacement(credentials: Any) -> None:
        probe = Session(
            client_id=credentials.client_id,
            username=credentials.username,
            password=credentials.password,
        )
        probe.start()
        admin.drain()
        probe.publish(allowed, b"rotation-probe")
        assert admin.wait_for(allowed)
        probe.close()

    provisioner.rotate_password(
        first_plan,
        first_credentials,
        replacement_credentials,
        verify_replacement,
    )

    old_password = Session(
        client_id=first_credentials.client_id,
        username=first_credentials.username,
        password=first_credentials.password,
    )
    old_password.start(expect_allowed=False)
    old_password.close()

    rollback_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-test-node-001", generation=3
    )
    rollback_candidate = generate_node_credentials(rollback_plan)

    def reject_candidate(_credentials: Any) -> None:
        raise RuntimeError("injected candidate verification failure")

    try:
        provisioner.rotate_password(
            first_plan,
            replacement_credentials,
            rollback_candidate,
            reject_candidate,
        )
    except RuntimeError as error:
        assert str(error) == "injected candidate verification failure"
    else:
        raise AssertionError("failed rotation verification was not propagated")

    restored = Session(
        client_id=replacement_credentials.client_id,
        username=replacement_credentials.username,
        password=replacement_credentials.password,
    )
    restored.start()
    restored.close()

    rejected_candidate = Session(
        client_id=rollback_candidate.client_id,
        username=rollback_candidate.username,
        password=rollback_candidate.password,
    )
    rejected_candidate.start(expect_allowed=False)
    rejected_candidate.close()

    provisioner.deprovision(first_plan)
    provisioner.deprovision(second_plan)

    revoked = Session(
        client_id=first_credentials.client_id,
        username=first_credentials.username,
        password=first_credentials.password,
    )
    revoked.start(expect_allowed=False)
    revoked.close()
    admin.close()


if __name__ == "__main__":
    main()
