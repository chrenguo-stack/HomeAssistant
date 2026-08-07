from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.registration import RegistrationRegistry


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_configures_bounded_mqtt_reconnect_backoff(client_class: object) -> None:
    client = client_class.return_value
    ManagerMqttService(Settings(system_id="dev"))

    client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=15)


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_pairing_intake_remains_disabled_by_default(client_class: object) -> None:
    service = ManagerMqttService(Settings(system_id="dev"))

    assert service.pairing_processor is None
    assert service.registration_registry is None
    assert service.n3w_runtime is None


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
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
    assert "gh/v1/dev/ingress/gateway/+/+/frame" not in topics
    assert service.registration_registry is not None
    service.registration_registry.close()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_n3w_runtime_adds_relay_subscription_only_when_explicitly_enabled(
    client_class: object, tmp_path: object
) -> None:
    registration_path = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(registration_path):
        pass

    router = SimpleNamespace(process_relay=Mock(), process_direct=Mock())
    runtime = SimpleNamespace(
        relay_subscription="gh/v1/dev/ingress/gateway/+/+/frame",
        is_relay_topic=lambda topic: topic.startswith("gh/v1/dev/ingress/gateway/"),
        router=router,
        close=Mock(),
    )
    settings = Settings(
        system_id="dev",
        pairing_db_path=str(registration_path),
        n3w_runtime_enabled=True,
        n3w_replay_db_path=str(tmp_path / "replay.sqlite3"),
        n3w_relay_authorization_db_path=str(tmp_path / "authorization.sqlite3"),
        n3w_relay_key_dir=str(tmp_path / "keys"),
    )
    client = client_class.return_value
    client.subscribe.return_value = (0, 1)

    with patch(
        "greenhouse_manager.runtime.mqtt_service.build_n3w_runtime_wiring",
        return_value=runtime,
    ) as builder:
        service = ManagerMqttService(settings)

    service._on_connect(client, None, Mock(), Mock(is_failure=False), None)

    topics = [call.args[0] for call in client.subscribe.call_args_list]
    assert "gh/v1/dev/ingress/gateway/+/+/frame" in topics
    builder.assert_called_once()
    assert service.n3w_runtime is runtime
    assert service.registration_registry is not None
    service.registration_registry.close()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_rejected_relay_frame_never_publishes_canonical_diagnostic(
    client_class: object, tmp_path: object
) -> None:
    registration_path = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(registration_path):
        pass

    relay_result = SimpleNamespace(
        status="rejected",
        source="relay",
        node_id="node_0001",
        messages=(),
        code="gateway_node_unauthorized",
        detail=None,
        dedup_key=None,
    )
    router = SimpleNamespace(
        process_relay=Mock(return_value=relay_result),
        process_direct=Mock(),
    )
    runtime = SimpleNamespace(
        relay_subscription="gh/v1/dev/ingress/gateway/+/+/frame",
        is_relay_topic=lambda topic: topic.startswith("gh/v1/dev/ingress/gateway/"),
        router=router,
        close=Mock(),
    )
    settings = Settings(
        system_id="dev",
        pairing_db_path=str(registration_path),
        n3w_runtime_enabled=True,
        n3w_replay_db_path=str(tmp_path / "replay.sqlite3"),
        n3w_relay_authorization_db_path=str(tmp_path / "authorization.sqlite3"),
        n3w_relay_key_dir=str(tmp_path / "keys"),
    )

    with patch(
        "greenhouse_manager.runtime.mqtt_service.build_n3w_runtime_wiring",
        return_value=runtime,
    ):
        service = ManagerMqttService(settings)

    service._publish_diagnostic = Mock()
    service._on_message(
        client_class.return_value,
        None,
        SimpleNamespace(
            topic="gh/v1/dev/ingress/gateway/gateway_001/node_0001/frame",
            payload=b"{}",
            retain=False,
        ),
    )

    router.process_relay.assert_called_once()
    service._publish_diagnostic.assert_not_called()
    assert service.registration_registry is not None
    service.registration_registry.close()
