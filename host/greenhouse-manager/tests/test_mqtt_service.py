from __future__ import annotations

from unittest.mock import patch

from greenhouse_manager.config import Settings
from greenhouse_manager.mqtt_service import ManagerMqttService


@patch("greenhouse_manager.mqtt_service.mqtt.Client")
def test_configures_bounded_mqtt_reconnect_backoff(client_class: object) -> None:
    client = client_class.return_value
    ManagerMqttService(Settings(system_id="dev"))

    client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=15)
