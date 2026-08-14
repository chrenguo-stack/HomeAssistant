from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.n3w_product_mqtt_service import ProductManagerMqttService
from greenhouse_manager.runtime.n3w_product_peer_authorization import (
    PeerAuthorizationRejected,
    PeerAuthorizationUnavailable,
)


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_opt_in_product_service_subscribes_existing_relay_node_ingress_subtree(client_class: object) -> None:
    client = client_class.return_value
    client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
    adapter = Mock()
    service = ProductManagerMqttService(Settings(system_id="dev"), adapter)

    service._on_connect(client, None, Mock(), Mock(is_failure=False), None)

    topics = [call.args[0] for call in client.subscribe.call_args_list]
    assert "gh/v1/dev/ingress/node/+/relay-peer-auth/request" in topics


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_product_peer_auth_request_publishes_nonretained_response(client_class: object) -> None:
    client = client_class.return_value
    client.publish.return_value = SimpleNamespace(rc=mqtt.MQTT_ERR_SUCCESS)
    adapter = Mock()
    adapter.handle.return_value = (
        "gh/v1/dev/out/node/relay-01/relay-peer-auth/session-0001",
        b'{"schema":"gh.n3w-product.peer-auth-response/1"}',
    )
    service = ProductManagerMqttService(Settings(system_id="dev"), adapter)
    message = SimpleNamespace(
        topic="gh/v1/dev/ingress/node/relay-01/relay-peer-auth/request",
        payload=b'{"request":true}',
    )

    with patch("greenhouse_manager.runtime.n3w_product_mqtt_service.time.time", return_value=1234.5):
        service._on_message(client, None, message)

    adapter.handle.assert_called_once_with(
        topic=message.topic,
        payload=message.payload,
        now_ms=1_234_500,
    )
    client.publish.assert_called_once_with(
        "gh/v1/dev/out/node/relay-01/relay-peer-auth/session-0001",
        payload=b'{"schema":"gh.n3w-product.peer-auth-response/1"}',
        qos=1,
        retain=False,
    )


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_product_peer_auth_rejection_and_unavailability_fail_closed(client_class: object) -> None:
    client = client_class.return_value
    adapter = Mock()
    service = ProductManagerMqttService(Settings(system_id="dev"), adapter)
    message = SimpleNamespace(
        topic="gh/v1/dev/ingress/node/relay-01/relay-peer-auth/request",
        payload=b"{}",
    )

    adapter.handle.side_effect = PeerAuthorizationRejected("relay_not_eligible")
    service._on_message(client, None, message)
    client.publish.assert_not_called()

    adapter.handle.side_effect = PeerAuthorizationUnavailable("path_authority_unavailable")
    service._on_message(client, None, message)
    client.publish.assert_not_called()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_non_product_message_delegates_to_legacy_manager_router(client_class: object) -> None:
    client = client_class.return_value
    adapter = Mock()
    service = ProductManagerMqttService(Settings(system_id="dev"), adapter)
    message = SimpleNamespace(topic="gh/v1/dev/ingress/node/node-01/telemetry", payload=b"{}")

    with patch.object(ManagerMqttService, "_on_message") as legacy:
        service._on_message(client, None, message)

    legacy.assert_called_once_with(client, None, message)
    adapter.handle.assert_not_called()
