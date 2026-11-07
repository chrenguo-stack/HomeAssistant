from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.t1_ota_manager import (
    OtaRuntimeSnapshot,
    T1OtaManager,
)


def approved_manifest() -> dict:
    target_path = (
        Path(__file__).resolve().parents[4]
        / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
    )
    return {
        "schema": "gh.n3w-t1-ota-approved-manifest/1",
        "approval_status": "APPROVED",
        "signature_status": "VERIFIED",
        "validity_status": "VALID",
        "verification_status": "PASS",
        "version": "2026.10.4",
        "release_identity": "homeassistant-2026.10.4",
        "target_archive_size_bytes": 835309535,
        "target": json.loads(target_path.read_text(encoding="utf-8")),
    }


class Provider:
    def get_approved_homeassistant_manifest(self):
        return approved_manifest()


class Runtime:
    def __init__(self) -> None:
        self.phase = "DISCOVERED"
        self.usb_model: str | None = None
        self.usb_capacity: int | None = None
        self.usb_confirmation_required = False

    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        return OtaRuntimeSnapshot(
            phase=self.phase,
            usb_candidate_model=self.usb_model,
            usb_candidate_capacity_bytes=self.usb_capacity,
            usb_confirmation_required=self.usb_confirmation_required,
        )


class Sink:
    def __init__(self) -> None:
        self.intents = []

    def submit_homeassistant_ota_intent(self, intent) -> None:
        self.intents.append(intent)


def mqtt_message(
    payload: dict,
    *,
    retain: bool = False,
    qos: int = 1,
) -> Mock:
    message = Mock()
    message.topic = "gh/v1/system-001/control/t1/homeassistant/ota"
    message.payload = json.dumps(payload).encode()
    message.retain = retain
    message.qos = qos
    return message


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_ota_control_plane_reuses_existing_manager_mqtt_client(client_class) -> None:
    client = client_class.return_value
    client.subscribe.return_value = (0, 1)
    client.publish.return_value = Mock(rc=0)
    runtime = Runtime()
    sink = Sink()
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        intent_sink=sink,
        runtime_state_provider=runtime,
    )
    service = ManagerMqttService(
        Settings(system_id="system-001"),
        ota_manager=ota,
    )

    assert client_class.call_count == 1

    service._on_connect(
        client,
        None,
        Mock(),
        Mock(is_failure=False),
        None,
    )

    subscriptions = [call.args[0] for call in client.subscribe.call_args_list]
    assert "gh/v1/system-001/ingress/node/+/telemetry" in subscriptions
    assert "gh/v1/system-001/state/+/telemetry" in subscriptions
    assert "gh/v1/system-001/control/t1/homeassistant/ota" in subscriptions
    assert "gh/v1/system-001/control/t1/homeassistant/#" not in subscriptions

    published_topics = [call.args[0] for call in client.publish.call_args_list]
    assert "homeassistant/update/n3w_t1_homeassistant/config" in published_topics
    assert "homeassistant/button/n3w_t1_homeassistant_prepare/config" in published_topics
    assert "gh/v1/system-001/state/t1/homeassistant/ota" in published_topics


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_mqtt_prepare_install_status_preserve_two_step_contract(client_class) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    runtime = Runtime()
    sink = Sink()
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        intent_sink=sink,
        runtime_state_provider=runtime,
    )
    service = ManagerMqttService(
        Settings(system_id="system-001"),
        ota_manager=ota,
    )

    base = {"target_release_id": "homeassistant-2026.10.4"}
    service._on_message(
        client,
        None,
        mqtt_message({**base, "action": "PREPARE"}),
    )
    assert [intent.action for intent in sink.intents] == ["PREPARE"]

    service._on_message(
        client,
        None,
        mqtt_message({**base, "action": "INSTALL"}),
    )
    assert [intent.action for intent in sink.intents] == ["PREPARE"]

    service._on_message(
        client,
        None,
        mqtt_message({**base, "action": "STATUS"}),
    )
    assert [intent.action for intent in sink.intents] == ["PREPARE"]

    runtime.phase = "READY_TO_INSTALL"
    service._on_message(
        client,
        None,
        mqtt_message({**base, "action": "INSTALL"}),
    )
    assert [intent.action for intent in sink.intents] == ["PREPARE", "INSTALL"]


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_mqtt_control_rejects_privileged_field_injection(client_class) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    sink = Sink()
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        intent_sink=sink,
    )
    service = ManagerMqttService(
        Settings(system_id="system-001"),
        ota_manager=ota,
    )

    service._on_message(
        client,
        None,
        mqtt_message(
            {
                "action": "PREPARE",
                "target_release_id": "homeassistant-2026.10.4",
                "shell": "docker rm -f homeassistant",
            }
        ),
    )
    assert sink.intents == []


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_mqtt_control_rejects_retained_or_wrong_qos_command(client_class) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    sink = Sink()
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        intent_sink=sink,
    )
    service = ManagerMqttService(
        Settings(system_id="system-001"),
        ota_manager=ota,
    )
    command = {
        "action": "PREPARE",
        "target_release_id": "homeassistant-2026.10.4",
    }

    service._on_message(
        client,
        None,
        mqtt_message(command, retain=True),
    )
    service._on_message(
        client,
        None,
        mqtt_message(command, qos=0),
    )

    assert sink.intents == []


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_mqtt_usb_erase_confirmation_preserves_narrow_intent(client_class) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    runtime = Runtime()
    runtime.phase = "USB_REQUIRED_CONFIRMATION"
    runtime.usb_model = "Synthetic USB"
    runtime.usb_capacity = 16 * 1024**3
    runtime.usb_confirmation_required = True
    sink = Sink()
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        intent_sink=sink,
        runtime_state_provider=runtime,
    )
    service = ManagerMqttService(
        Settings(system_id="system-001"),
        ota_manager=ota,
    )
    base = {"target_release_id": "homeassistant-2026.10.4"}

    service._on_message(
        client,
        None,
        mqtt_message({**base, "action": "CONFIRM_USB_ERASE"}),
    )
    assert [intent.action for intent in sink.intents] == [
        "CONFIRM_USB_ERASE"
    ]

    service._on_message(
        client,
        None,
        mqtt_message(
            {
                **base,
                "action": "CONFIRM_USB_ERASE",
                "block_device": "/dev/sdz",
            }
        ),
    )
    assert [intent.action for intent in sink.intents] == [
        "CONFIRM_USB_ERASE"
    ]
