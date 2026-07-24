from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from unittest.mock import Mock, patch

from greenhouse_manager.config import Settings
from greenhouse_manager.mqtt_service import ManagerMqttService


def _telemetry_payload(node_id: str, seq: int) -> bytes:
    return json.dumps(
        {
            "schema": "gh.telemetry/1",
            "node_id": node_id,
            "boot_id": "boot_01J2A6Q9T8W4",
            "seq": seq,
            "uptime_ms": 125430 + seq,
            "sampled_at": "2026-07-10T13:05:30+08:00",
            "cap_hash": "sha256:3e19f73d5c27a84b",
            "fw_version": "F1.0-RC2-N0.2",
            "measurements": {
                "air_temperature_c": 27.4,
                "air_humidity_pct": 68.2,
                "co2_ppm": 684,
                "soil_moisture_pct": 37.6,
                "battery_v": 3.94,
                "battery_pct": 74,
            },
            "quality": {
                "air_temperature_c": "ok",
                "air_humidity_pct": "ok",
                "co2_ppm": "ok",
                "soil_moisture_pct": "ok",
                "battery_v": "ok",
                "battery_pct": "ok",
            },
            "power": {
                "source": "battery",
                "battery_v": 3.94,
                "battery_pct": 74,
                "low": False,
            },
        }
    ).encode("utf-8")


@patch("greenhouse_manager.mqtt_service.mqtt.Client")
def test_configures_bounded_mqtt_reconnect_backoff(client_class: object) -> None:
    client = client_class.return_value
    ManagerMqttService(Settings(system_id="dev"))

    client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=15)


@patch("greenhouse_manager.mqtt_service.mqtt.Client")
def test_pairing_intake_remains_disabled_by_default(client_class: object) -> None:
    service = ManagerMqttService(Settings(system_id="dev"))

    assert service.pairing_processor is None
    assert service.registration_registry is None


@patch("greenhouse_manager.mqtt_service.mqtt.Client")
def test_subscribes_to_pairing_hello_only_when_enabled(
    client_class: object, tmp_path: object
) -> None:
    client = client_class.return_value
    client.subscribe.return_value = (0, 1)
    service = ManagerMqttService(
        Settings(
            system_id="dev",
            pairing_intake_enabled=True,
            pairing_db_path=f"{tmp_path}/registration.sqlite3",
        )
    )
    reason_code = Mock(is_failure=False)

    service._on_connect(client, None, Mock(), reason_code, None)

    topics = [call.args[0] for call in client.subscribe.call_args_list]
    assert "gh/bootstrap/v1/node/+/hello" in topics
    assert "gh/bootstrap/v1/node/+/challenge" not in topics
    assert service.registration_registry is not None
    service.registration_registry.close()


@patch("greenhouse_manager.mqtt_service.mqtt.Client")
def test_mqtt_callback_and_main_thread_stale_scan_are_thread_safe(
    client_class: object,
) -> None:
    client = client_class.return_value
    client.publish.return_value.rc = 0
    service = ManagerMqttService(
        Settings(system_id="dev", ha_discovery_enabled=False, stale_after_s=180)
    )
    node_ids = tuple(f"node_{index:04d}" for index in range(64))
    start = Barrier(2)

    def network_callback_thread() -> None:
        start.wait()
        for index, node_id in enumerate(node_ids):
            service._on_message(
                client,
                None,
                Mock(
                    topic=f"gh/v1/dev/ingress/node/{node_id}/telemetry",
                    payload=_telemetry_payload(node_id, index + 1),
                ),
            )

    def main_thread_stale_loop() -> None:
        start.wait()
        for _ in range(2048):
            service.processor.stale_messages(now=datetime.now(UTC))

    with ThreadPoolExecutor(max_workers=2) as executor:
        callback = executor.submit(network_callback_thread)
        stale_loop = executor.submit(main_thread_stale_loop)
        callback.result()
        stale_loop.result()

    stale = service.processor.stale_messages(
        now=datetime(2100, 1, 1, tzinfo=UTC)
    )
    assert {message.payload["node_id"] for message in stale} == set(node_ids)
