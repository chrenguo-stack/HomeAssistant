from __future__ import annotations

import logging
from unittest.mock import Mock, patch

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService


def _canonical_telemetry() -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": "node-0001",
        "boot_id": "boot-00000001",
        "seq": 1,
        "uptime_ms": 1000,
        "received_at": "2026-11-04T10:00:00.000Z",
        "cap_hash": "cap-hash-0001",
        "fw_version": "F1.0",
        "measurements": {"air_temperature_c": 25.0},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "battery", "low": False},
    }


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_discovery_publish_failure_retries_unchanged_telemetry(
    client_class: object,
    caplog: object,
) -> None:
    service = ManagerMqttService(Settings(system_id="system-001"))
    service._publish = Mock(side_effect=[False, True, True, True])
    document = _canonical_telemetry()
    caplog.set_level(
        logging.INFO,
        logger="greenhouse_manager.runtime.mqtt_service",
    )

    service._publish_discovery(document)

    first_topics = [
        call.args[0].topic for call in service._publish.call_args_list
    ]
    assert len(first_topics) == 2
    failed_topic = first_topics[0]
    assert any(
        record.levelno == logging.WARNING
        and failed_topic in record.getMessage()
        and "will retry" in record.getMessage()
        for record in caplog.records
    )
    assert not any(
        record.levelno == logging.INFO
        and failed_topic in record.getMessage()
        and "Published Home Assistant discovery" in record.getMessage()
        for record in caplog.records
    )

    service._publish_discovery(document)

    assert service._publish.call_count == 4
    assert [
        call.args[0].topic for call in service._publish.call_args_list[2:]
    ] == first_topics

    service._publish_discovery(document)

    assert service._publish.call_count == 4
