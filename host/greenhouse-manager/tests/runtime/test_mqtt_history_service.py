from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.registration import NodeIdLeaseState


def _history_page() -> bytes:
    document = {
        "schema": "gh.history-replay.batch/1",
        "node_id": "node-0001",
        "batch_id": "batch-000001",
        "page_index": 0,
        "page_count": 1,
        "records": [
            {
                "boot_id": "boot-00000001",
                "seq": 1,
                "uptime_ms": 1000,
                "sampled_at": "2026-08-03T04:00:00Z",
                "cap_hash": "cap-hash-0001",
                "measurements": {"air_temperature_c": 25.0},
                "quality": {"air_temperature_c": "ok"},
                "power": {"source": "battery", "low": False},
            }
        ],
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_history_subscription_is_opt_in_and_separate(
    client_class: object, tmp_path: Path
) -> None:
    client = client_class.return_value
    client.subscribe.return_value = (0, 1)
    service = ManagerMqttService(
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(tmp_path / "manager-state.sqlite3"),
        )
    )

    service._on_connect(client, None, Mock(), Mock(is_failure=False), None)

    topics = [call.args[0] for call in client.subscribe.call_args_list]
    assert "gh/v1/system-001/ingress/node/+/history" in topics
    assert "gh/v1/system-001/state/+/history" not in topics
    assert service.history_store is not None
    service.history_store.close()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_history_message_only_publishes_nonretained_ack(
    client_class: object, tmp_path: Path
) -> None:
    client = client_class.return_value
    publish_info = Mock(rc=0)
    client.publish.return_value = publish_info
    service = ManagerMqttService(
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(tmp_path / "manager-state.sqlite3"),
        )
    )
    service._publish_discovery = Mock()
    service.processor.process = Mock()
    message = Mock(
        topic="gh/v1/system-001/ingress/node/node-0001/history",
        payload=_history_page(),
        retain=False,
    )

    service._on_message(client, None, message)

    service.processor.process.assert_not_called()
    service._publish_discovery.assert_not_called()
    assert client.publish.call_count == 1
    call = client.publish.call_args
    assert call.args[0] == "gh/v1/system-001/command/node/node-0001/history/ack"
    assert call.kwargs["retain"] is False
    assert b'"committed":true' in call.kwargs["payload"]
    assert service.history_store is not None
    assert service.history_store.count_records() == 1
    service.history_store.close()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_loaded_registry_rejects_inactive_history_node_without_storage(
    client_class: object, tmp_path: Path
) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    service = ManagerMqttService(
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(tmp_path / "manager-state.sqlite3"),
        )
    )
    service.registration_registry = Mock()
    service.registration_registry.node_id_lease_state.return_value = (
        NodeIdLeaseState.RETIRED
    )
    message = Mock(
        topic="gh/v1/system-001/ingress/node/node-0001/history",
        payload=_history_page(),
        retain=False,
    )

    service._on_message(client, None, message)

    assert client.publish.call_count == 1
    payload = client.publish.call_args.kwargs["payload"]
    assert b'"committed":false' in payload
    assert b'"next_page_index":0' in payload
    assert service.history_store is not None
    assert service.history_store.count_records() == 0
    service.history_store.close()
