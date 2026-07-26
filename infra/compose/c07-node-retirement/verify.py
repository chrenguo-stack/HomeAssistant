from __future__ import annotations

import io
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from greenhouse_manager.ops.node_retirement_cli import (
    PahoCredentialRevoker,
)
from greenhouse_manager.ops.node_retirement_cli import (
    main as retirement_main,
)
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.dynsec_api import (
    DynsecProvisioner,
    PahoDynsecTransport,
)
from greenhouse_manager.runtime.dynsec_plan import (
    NodeCredentials,
    build_node_provisioning_plan,
    generate_node_credentials,
)
from greenhouse_manager.runtime.registration import (
    RegistrationConflict,
    RegistrationRegistry,
    RetirementState,
)

BROKER = "broker"
PORT = 1883
SYSTEM_ID = "greenhouse"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
REPLACEMENT_HARDWARE_ID = "ghw-c6-112233445566"
REPLACEMENT_PAIRING_ID = "d5bcf708-88a0-4974-8ca9-597482974e94"
NODE_ID = "gh-n1-a9f2f8"
LOGICAL_LOCATION_ID = "greenhouse-bed-01"
HA_PROBE_PATH = Path("/ha-config/c07-probe-state.json")
MANAGER_LOG_PATH = Path("/tmp/c07-manager.log")
DATABASE = Path("/tmp/c07-registration.sqlite3")

DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
CONNECTIVITY_DISCOVERY_TOPIC = (
    f"homeassistant/binary_sensor/{NODE_ID}_connectivity/config"
)
TELEMETRY_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
AVAILABILITY_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability"
DIAGNOSTIC_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/diagnostic"
INGRESS_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
RETAINED_TOPICS = (
    DISCOVERY_TOPIC,
    CONNECTIVITY_DISCOVERY_TOPIC,
    TELEMETRY_TOPIC,
    AVAILABILITY_TOPIC,
    DIAGNOSTIC_TOPIC,
)


class Session:
    def __init__(
        self,
        client_id: str,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.connected = threading.Event()
        self.connection_allowed: bool | None = None
        self.subscribed = threading.Event()
        self.subscription_allowed: bool | None = None
        self.messages: queue.Queue[tuple[str, bytes]] = queue.Queue()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        if username is not None:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message

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

    def _on_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _mid: int,
        reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        self.subscription_allowed = bool(reason_codes) and all(
            not reason_code.is_failure for reason_code in reason_codes
        )
        self.subscribed.set()

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        self.messages.put((message.topic, bytes(message.payload)))

    def start(self, *, expect_allowed: bool = True) -> None:
        self.client.connect(BROKER, PORT, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(10):
            raise AssertionError("MQTT connection result timed out")
        if self.connection_allowed is not expect_allowed:
            raise AssertionError("MQTT connection result did not match expectation")

    def subscribe(self, topic: str) -> None:
        self.subscribed.clear()
        result, _mid = self.client.subscribe(topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError(f"MQTT subscribe call failed for {topic}")
        if not self.subscribed.wait(5) or self.subscription_allowed is not True:
            raise AssertionError(f"MQTT subscription was not allowed for {topic}")

    def publish(self, topic: str, payload: bytes, *, retain: bool = False) -> None:
        info = self.client.publish(
            topic,
            payload=payload,
            qos=1,
            retain=retain,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError(f"MQTT publish call failed for {topic}")
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise AssertionError(f"MQTT publish acknowledgement timed out for {topic}")

    def close(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float,
    description: str,
    interval_s: float = 0.5,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval_s)
    raise AssertionError(f"timed out waiting for {description}")


def retained_payload(topic: str, *, timeout_s: float = 1.5) -> bytes | None:
    session = Session(f"c07-retained-{time.monotonic_ns()}")
    try:
        session.start()
        session.subscribe(topic)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                received_topic, payload = session.messages.get(
                    timeout=deadline - time.monotonic()
                )
            except queue.Empty:
                return None
            if received_topic == topic:
                return payload
        return None
    finally:
        session.close()


def hello(
    *,
    hardware_id: str = HARDWARE_ID,
    pairing_id: str = PAIRING_ID,
) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials"],
        "sent_at_ms": 1,
    }


def telemetry(seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_01J2A6Q9T8W4",
        "seq": seq,
        "uptime_ms": seq * 1000,
        "sampled_at": "2026-07-26T08:00:00Z",
        "cap_hash": "sha256:3e19f73d5c27a84b",
        "fw_version": "F1.0-RC2-N2.0",
        "measurements": {"air_temperature_c": 25.0},
        "quality": {"air_temperature_c": "ok"},
        "power": {
            "source": "main",
            "battery_v": None,
            "battery_pct": None,
            "low": False,
        },
    }


def canonical_telemetry(seq: int) -> dict[str, object]:
    document = telemetry(seq)
    document["received_at"] = "2026-07-26T08:00:01.000Z"
    return document


def read_ha_probe() -> dict[str, Any]:
    try:
        document = json.loads(HA_PROBE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def connected_admin(password: str) -> tuple[mqtt.Client, PahoDynsecTransport]:
    connected = threading.Event()
    allowed: list[bool] = []
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="c07-admin",
        protocol=mqtt.MQTTv5,
    )
    client.username_pw_set("admin", password)
    transport = PahoDynsecTransport(client)

    def on_connect(
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        allowed.append(not reason_code.is_failure)
        connected.set()

    client.on_connect = on_connect
    client.on_message = transport.on_message
    client.connect(BROKER, PORT, keepalive=30)
    client.loop_start()
    if not connected.wait(10) or allowed != [True]:
        raise AssertionError("Dynamic Security admin connection failed")
    return client, transport


def start_manager() -> tuple[subprocess.Popen[str], Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "GH_SYSTEM_ID": SYSTEM_ID,
            "GH_MQTT_HOST": BROKER,
            "GH_MQTT_PORT": str(PORT),
            "GH_MQTT_CLIENT_ID": "c07-manager",
            "GH_PAIRING_INTAKE_ENABLED": "false",
            "GH_PAIRING_DB_PATH": str(DATABASE),
            "GH_STALE_AFTER_S": "180",
            "GH_LOG_LEVEL": "INFO",
        }
    )
    log_stream = MANAGER_LOG_PATH.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "greenhouse_manager"],
        env=environment,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(2)
    if process.poll() is not None:
        log_stream.close()
        raise AssertionError("greenhouse-manager exited during startup")
    return process, log_stream


def stop_manager(process: subprocess.Popen[str] | None, log_stream: Any) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
    if log_stream is not None:
        log_stream.close()


def initialize_registration_database() -> None:
    now = datetime.now(UTC)
    with RegistrationRegistry(DATABASE) as registry:
        registry.observe_hello(hello(), now=now)
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            logical_location_id=LOGICAL_LOCATION_ID,
            now=now,
        )
    with CredentialLifecycleStore(DATABASE) as lifecycle:
        lifecycle.activate(
            hardware_id=HARDWARE_ID,
            node_id=NODE_ID,
            generation=1,
            now=now,
        )


def publish_until_discovery(node: Session) -> None:
    for seq in range(1, 11):
        node.publish(
            INGRESS_TOPIC,
            json.dumps(
                telemetry(seq),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        if retained_payload(DISCOVERY_TOPIC) not in (None, b""):
            return
        time.sleep(1)
    raise AssertionError("manager did not publish retained Home Assistant discovery")


def assert_anonymous_reuse_is_blocked() -> None:
    with RegistrationRegistry(DATABASE) as registry:
        registry.observe_hello(
            hello(
                hardware_id=REPLACEMENT_HARDWARE_ID,
                pairing_id=REPLACEMENT_PAIRING_ID,
            ),
            now=datetime.now(UTC),
        )
        try:
            registry.approve(
                REPLACEMENT_HARDWARE_ID,
                REPLACEMENT_PAIRING_ID,
                node_id=NODE_ID,
                logical_location_id=LOGICAL_LOCATION_ID,
                reuse_retired_node_id=True,
                private_identity_bound=True,
                now=datetime.now(UTC),
            )
        except RegistrationConflict as error:
            if "anonymous compatibility must be disabled" not in str(error):
                raise
        else:
            raise AssertionError("anonymous compatibility did not block NODE_ID reuse")


def retirement_completed(retirement_id: int) -> bool:
    with RegistrationRegistry(DATABASE) as registry:
        return (
            registry.get_retirement_job(retirement_id).state
            is RetirementState.COMPLETED
        )


def main() -> None:
    admin_password = os.environ["GH_DYNSEC_ADMIN_PASSWORD"]
    admin_client: mqtt.Client | None = None
    manager_process: subprocess.Popen[str] | None = None
    manager_log: Any = None
    node: Session | None = None
    anonymous: Session | None = None
    created_entities: set[str] = set()

    try:
        admin_client, transport = connected_admin(admin_password)
        provisioner = DynsecProvisioner(transport)
        plan = build_node_provisioning_plan(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            generation=1,
        )
        credentials: NodeCredentials = generate_node_credentials(plan)
        provisioner.apply_baseline(plan)
        provisioner.apply_legacy_anonymous_shadow()
        provisioner.provision(plan, credentials)

        initialize_registration_database()
        manager_process, manager_log = start_manager()
        node = Session(
            credentials.client_id,
            username=credentials.username,
            password=credentials.password,
        )
        node.start()
        publish_until_discovery(node)

        wait_until(
            lambda: bool(read_ha_probe().get("current_entities")),
            timeout_s=90,
            description="Home Assistant MQTT Discovery entities",
        )
        created_entities = set(read_ha_probe()["current_entities"])
        if not created_entities:
            raise AssertionError("Home Assistant did not create any C-07 entities")

        node.close()
        node = None
        stdout = io.StringIO()
        stderr = io.StringIO()
        revoker = PahoCredentialRevoker(
            host=BROKER,
            port=PORT,
            username="admin",
            password=admin_password,
            client_id="c07-revoker",
            tls=False,
            ca_file=None,
        )
        code = retirement_main(
            [
                "--db",
                str(DATABASE),
                "retire",
                HARDWARE_ID,
                "--system-id",
                SYSTEM_ID,
            ],
            stdout=stdout,
            stderr=stderr,
            credential_revoker=revoker,
        )
        if code != 0:
            raise AssertionError("node retirement command failed in isolated lab")
        retirement = json.loads(stdout.getvalue())
        if retirement.get("credentials_revoked") is not True:
            raise AssertionError(
                "Dynamic Security credential revocation was not recorded"
            )

        revoked = Session(
            credentials.client_id,
            username=credentials.username,
            password=credentials.password,
        )
        revoked.start(expect_allowed=False)
        revoked.close()

        wait_until(
            lambda: retirement_completed(int(retirement["retirement_id"])),
            timeout_s=30,
            description="durable retirement outbox completion",
        )
        wait_until(
            lambda: (
                not read_ha_probe().get("current_entities")
                and created_entities.issubset(
                    set(read_ha_probe().get("removed_entities", []))
                )
            ),
            timeout_s=90,
            description="Home Assistant entity removal",
        )
        for topic in RETAINED_TOPICS:
            if retained_payload(topic) is not None:
                raise AssertionError(f"retained tombstone did not clear {topic}")

        assert_anonymous_reuse_is_blocked()

        stop_manager(manager_process, manager_log)
        manager_process = None
        manager_log = None

        anonymous = Session("c07-anonymous-resurrection")
        anonymous.start()
        anonymous.publish(
            TELEMETRY_TOPIC,
            json.dumps(
                canonical_telemetry(99),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            retain=True,
        )
        if retained_payload(TELEMETRY_TOPIC) in (None, b""):
            raise AssertionError("failed to stage stale retained canonical telemetry")

        manager_process, manager_log = start_manager()
        time.sleep(8)
        if retained_payload(DISCOVERY_TOPIC) is not None:
            raise AssertionError(
                "retired node discovery resurrected after manager restart"
            )
        if read_ha_probe().get("current_entities"):
            raise AssertionError(
                "Home Assistant entities resurrected after manager restart"
            )

        anonymous.publish(TELEMETRY_TOPIC, b"", retain=True)
        for topic in RETAINED_TOPICS:
            if retained_payload(topic) is not None:
                raise AssertionError(f"final retained state was not empty for {topic}")

        final_probe = read_ha_probe()
        result = {
            "schema": "gh.c07.isolated-retirement-closure/1",
            "real_mosquitto_dynamic_security": True,
            "real_homeassistant_mqtt_discovery": True,
            "credentials_invalidated": True,
            "retained_topics_cleared": len(RETAINED_TOPICS),
            "homeassistant_entities_created": len(created_entities),
            "homeassistant_entities_removed": len(
                final_probe.get("removed_entities", [])
            ),
            "anonymous_reuse_blocked": True,
            "manager_restart_resurrection_blocked": True,
            "production_services_modified": False,
            "secret_values_included": False,
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    except Exception:
        if MANAGER_LOG_PATH.exists():
            print("C07_MANAGER_LOG_TAIL_BEGIN", file=sys.stderr)
            lines = MANAGER_LOG_PATH.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
            print("\n".join(lines[-80:]), file=sys.stderr)
            print("C07_MANAGER_LOG_TAIL_END", file=sys.stderr)
        raise
    finally:
        if node is not None:
            node.close()
        if anonymous is not None:
            anonymous.close()
        stop_manager(manager_process, manager_log)
        if admin_client is not None:
            admin_client.disconnect()
            admin_client.loop_stop()


if __name__ == "__main__":
    main()
