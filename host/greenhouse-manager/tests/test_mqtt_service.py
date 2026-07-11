from __future__ import annotations

from unittest.mock import Mock, patch

from greenhouse_manager.config import Settings
from greenhouse_manager.mqtt_service import ManagerMqttService


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
