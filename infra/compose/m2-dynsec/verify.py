from __future__ import annotations

import json
import os
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Sequence

import paho.mqtt.client as mqtt

from greenhouse_manager.dynsec_api import (
    DynsecError,
    DynsecProvisioner,
    PahoDynsecTransport,
    RESPONSE_TOPIC,
)
from greenhouse_manager.dynsec_plan import build_node_provisioning_plan, generate_node_credentials
from greenhouse_manager.service_identity_plan import (
    ServiceCredentials,
    ServiceIdentityPlan,
    build_service_identity_plan,
    generate_service_credentials,
)

BROKER = "broker"
PORT = 1883


@dataclass
class SubscriptionResult:
    event: threading.Event
    allowed: bool | None = None


class Session:
    def __init__(
        self,
        *,
        client_id: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
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
        if username is not None:
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


class FailAfterCreateClientTransport:
    """Inject a post-create failure so rollback executes against a real isolated Broker."""

    def __init__(self, delegate: PahoDynsecTransport) -> None:
        self.delegate = delegate
        self.command_names: list[str] = []
        self.failed = False

    def execute(self, commands: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        self.command_names.extend(command["command"] for command in commands)
        responses = self.delegate.execute(commands)
        if not self.failed and any(command["command"] == "createClient" for command in commands):
            self.failed = True
            raise DynsecError("injected post-create failure")
        return responses


def session_for(credentials: Any) -> Session:
    return Session(
        client_id=credentials.client_id,
        username=credentials.username,
        password=credentials.password,
    )


def assert_wrong_client_id_rejected(credentials: Any) -> None:
    wrong = Session(
        client_id=f"{credentials.client_id}-wrong",
        username=credentials.username,
        password=credentials.password,
    )
    wrong.start(expect_allowed=False)
    wrong.close()


def assert_publish_allowed(observer: Session, publisher: Session, topic: str) -> None:
    observer.drain()
    publisher.publish(topic)
    assert observer.wait_for(topic), topic


def assert_publish_denied(observer: Session, publisher: Session, topic: str) -> None:
    observer.drain()
    publisher.publish(topic)
    assert not observer.wait_for(topic, timeout=1.0), topic


def assert_dynsec_object_missing(
    transport: PahoDynsecTransport,
    *,
    command: str,
    key: str,
    value: str,
) -> None:
    try:
        transport.execute(({"command": command, key: value},))
    except DynsecError:
        return
    raise AssertionError(f"{command} unexpectedly found rolled-back object")


def assert_control_publish_denied(
    transport: PahoDynsecTransport,
    publisher: Session,
    *,
    canary_username: str,
) -> None:
    forbidden_command = json.dumps(
        {
            "commands": [
                {
                    "command": "createClient",
                    "username": canary_username,
                    "password": secrets.token_urlsafe(32),
                    "clientid": canary_username,
                }
            ]
        },
        separators=(",", ":"),
    ).encode()
    publisher.publish("$CONTROL/dynamic-security/v1", forbidden_command)
    time.sleep(0.5)
    assert_dynsec_object_missing(
        transport,
        command="getClient",
        key="username",
        value=canary_username,
    )


def build_service_plans() -> dict[str, ServiceIdentityPlan]:
    return {
        service: build_service_identity_plan(
            system_id="greenhouse",
            service=service,  # type: ignore[arg-type]
            generation=1,
        )
        for service in ("provisioning", "manager", "homeassistant")
    }


def main() -> None:
    admin_password = os.environ["GH_DYNSEC_ADMIN_PASSWORD"]
    admin = Session(client_id="gh-dynsec-test-admin", username="admin", password=admin_password)
    admin.start()
    transport = PahoDynsecTransport(admin.client)
    admin.message_hook = transport.on_message
    provisioner = DynsecProvisioner(transport)

    node_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-n1-a9f2f8", generation=1
    )
    second_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-test-node-002", generation=1
    )
    service_plans = build_service_plans()

    node_credentials = generate_node_credentials(node_plan)
    second_credentials = generate_node_credentials(second_plan)
    service_credentials: dict[str, ServiceCredentials] = {
        service: generate_service_credentials(plan)
        for service, plan in service_plans.items()
    }

    identities = [node_credentials, *service_credentials.values()]
    assert len({identity.username for identity in identities}) == len(identities)
    assert len({identity.client_id for identity in identities}) == len(identities)
    assert service_plans["provisioning"].client_id == "gh-provisioning-greenhouse"
    assert service_plans["manager"].client_id == "gh-manager-greenhouse"
    assert service_plans["homeassistant"].client_id == "gh-homeassistant-greenhouse"
    assert node_plan.client_id == "gh-n1-a9f2f8"

    provisioner.apply_baseline(node_plan)
    provisioner.apply_legacy_anonymous_shadow()
    provisioner.provision(node_plan, node_credentials)
    provisioner.provision(second_plan, second_credentials)
    for service, plan in service_plans.items():
        provisioner.provision(plan, service_credentials[service])

    assert admin.subscribe("#")

    legacy = Session(client_id="gh-legacy-anonymous-test")
    legacy.start()
    assert legacy.subscribe("gh/#")
    assert legacy.subscribe("homeassistant/#")
    assert legacy.subscribe("$SYS/#")
    assert not legacy.subscribe("$CONTROL/#")

    legacy_topic = "gh/v1/greenhouse/ingress/node/legacy-node/telemetry"
    assert_publish_allowed(admin, legacy, legacy_topic)
    assert_control_publish_denied(
        transport,
        legacy,
        canary_username="gh-dynsec-legacy-forbidden-canary",
    )

    node = session_for(node_credentials)
    second = session_for(second_credentials)
    provisioning = session_for(service_credentials["provisioning"])
    manager = session_for(service_credentials["manager"])
    homeassistant = session_for(service_credentials["homeassistant"])
    for session in (node, second, provisioning, manager, homeassistant):
        session.start()

    for credentials in identities:
        assert_wrong_client_id_rejected(credentials)

    own_out = "gh/v1/greenhouse/out/node/gh-n1-a9f2f8/#"
    other_out = "gh/v1/greenhouse/out/node/gh-test-node-002/#"
    assert node.subscribe(own_out)
    assert not node.subscribe(other_out)
    assert not node.subscribe("#")

    manager_ingress = "gh/v1/greenhouse/ingress/node/+/telemetry"
    assert manager.subscribe(manager_ingress)
    node_ingress = "gh/v1/greenhouse/ingress/node/gh-n1-a9f2f8/telemetry"
    manager.drain()
    node.publish(node_ingress)
    assert manager.wait_for(node_ingress)

    denied_node_topics = (
        "gh/v1/greenhouse/ingress/node/gh-test-node-002/telemetry",
        "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry",
        "homeassistant/device/gh-n1-a9f2f8/config",
    )
    for topic in denied_node_topics:
        assert_publish_denied(admin, node, topic)
    assert_control_publish_denied(
        transport,
        node,
        canary_username="gh-dynsec-node-forbidden-canary",
    )

    assert homeassistant.subscribe("gh/v1/greenhouse/state/#")
    assert homeassistant.subscribe("homeassistant/#")
    canonical_topic = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
    homeassistant.drain()
    manager.publish(canonical_topic)
    assert homeassistant.wait_for(canonical_topic)

    discovery_topics = (
        "homeassistant/device/gh-n1-a9f2f8/config",
        "homeassistant/binary_sensor/gh-n1-a9f2f8_connectivity/config",
    )
    for topic in discovery_topics:
        homeassistant.drain()
        manager.publish(topic)
        assert homeassistant.wait_for(topic)

    assert_publish_denied(admin, manager, "homeassistant/status")
    assert_publish_denied(admin, manager, "homeassistant/sensor/rogue/config")
    assert_publish_denied(admin, manager, node_ingress)
    assert not manager.subscribe("$CONTROL/#")
    assert_control_publish_denied(
        transport,
        manager,
        canary_username="gh-dynsec-manager-forbidden-canary",
    )

    assert_publish_allowed(admin, homeassistant, "homeassistant/status")
    assert_publish_denied(admin, homeassistant, canonical_topic)
    assert_publish_denied(admin, homeassistant, node_ingress)
    assert not homeassistant.subscribe("$CONTROL/#")
    assert_control_publish_denied(
        transport,
        homeassistant,
        canary_username="gh-dynsec-ha-forbidden-canary",
    )

    assert not provisioning.subscribe("gh/#")
    assert not provisioning.subscribe("homeassistant/#")
    assert_publish_denied(admin, provisioning, node_ingress)
    assert_publish_denied(admin, provisioning, "homeassistant/status")
    provisioning_transport = PahoDynsecTransport(provisioning.client)
    provisioning.message_hook = provisioning_transport.on_message
    responses = provisioning_transport.execute(({"command": "listClients"},))
    assert responses and responses[0].get("command") == "listClients"

    rollback_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-rollback-probe", generation=1
    )
    rollback_credentials = generate_node_credentials(rollback_plan)
    failing_transport = FailAfterCreateClientTransport(transport)
    try:
        DynsecProvisioner(failing_transport).provision(
            rollback_plan,
            rollback_credentials,
        )
    except DynsecError as error:
        assert str(error) == "injected post-create failure"
    else:
        raise AssertionError("injected provisioning failure was not propagated")
    assert failing_transport.command_names == [
        "createRole",
        "createClient",
        "deleteClient",
        "deleteRole",
    ]
    assert_dynsec_object_missing(
        transport,
        command="getClient",
        key="username",
        value=rollback_plan.username,
    )
    assert_dynsec_object_missing(
        transport,
        command="getRole",
        key="rolename",
        value=rollback_plan.role_name,
    )
    legacy_receive_topic = "gh/v1/greenhouse/out/node/legacy-node/rollback-probe"
    legacy.drain()
    admin.publish(legacy_receive_topic)
    assert legacy.wait_for(legacy_receive_topic)

    node.close()
    second.close()

    replacement_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-n1-a9f2f8", generation=2
    )
    replacement_credentials = generate_node_credentials(replacement_plan)

    def verify_replacement(credentials: Any) -> None:
        probe = session_for(credentials)
        probe.start()
        assert_publish_allowed(admin, probe, node_ingress)
        probe.close()

    provisioner.rotate_password(
        node_plan,
        node_credentials,
        replacement_credentials,
        verify_replacement,
    )

    old_password = session_for(node_credentials)
    old_password.start(expect_allowed=False)
    old_password.close()

    rollback_generation_plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-n1-a9f2f8", generation=3
    )
    rollback_candidate = generate_node_credentials(rollback_generation_plan)

    def reject_candidate(_credentials: Any) -> None:
        raise RuntimeError("injected candidate verification failure")

    try:
        provisioner.rotate_password(
            node_plan,
            replacement_credentials,
            rollback_candidate,
            reject_candidate,
        )
    except RuntimeError as error:
        assert str(error) == "injected candidate verification failure"
    else:
        raise AssertionError("failed rotation verification was not propagated")

    restored = session_for(replacement_credentials)
    restored.start()
    restored.close()

    rejected_candidate = session_for(rollback_candidate)
    rejected_candidate.start(expect_allowed=False)
    rejected_candidate.close()

    provisioning.close()
    manager.close()
    homeassistant.close()
    legacy.close()

    for plan in service_plans.values():
        provisioner.deprovision(plan)
    provisioner.deprovision(node_plan)
    provisioner.deprovision(second_plan)

    revoked = session_for(replacement_credentials)
    revoked.start(expect_allowed=False)
    revoked.close()
    admin.close()


if __name__ == "__main__":
    main()
