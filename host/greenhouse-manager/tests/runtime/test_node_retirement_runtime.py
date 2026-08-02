from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService
from greenhouse_manager.runtime.registration import (
    NodeIdLeaseState,
    RegistrationRegistry,
    RetirementState,
)

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"
LOGICAL_LOCATION_ID = "greenhouse-bed-01"
NOW = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials"],
        "sent_at_ms": 1,
    }


def telemetry() -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_01J2A6Q9T8W4",
        "seq": 1,
        "uptime_ms": 1000,
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


def retired_database(tmp_path: Path) -> tuple[Path, int]:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as registry:
        registry.observe_hello(hello(), now=NOW)
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            logical_location_id=LOGICAL_LOCATION_ID,
            now=NOW,
        )
        job = registry.retire(HARDWARE_ID, system_id="greenhouse", now=NOW)
    return database, job.retirement_id


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_manager_retries_durable_cleanup_after_credential_revocation(
    client_class: object,
    tmp_path: Path,
) -> None:
    database, retirement_id = retired_database(tmp_path)
    service = ManagerMqttService(
        Settings(
            system_id="greenhouse",
            pairing_intake_enabled=False,
            pairing_db_path=str(database),
        )
    )
    assert service.registration_registry is not None
    client = client_class.return_value
    publish_info = Mock(rc=0)
    publish_info.is_published.return_value = True
    client.publish.return_value = publish_info

    service._process_retirement_jobs()
    client.publish.assert_not_called()

    service.registration_registry.mark_credentials_revoked(
        retirement_id,
        evidence="test_revocation",
        now=NOW,
    )
    service._process_retirement_jobs()

    topics = [call.args[0] for call in client.publish.call_args_list]
    assert topics == [
        f"homeassistant/device/{NODE_ID}/config",
        f"homeassistant/binary_sensor/{NODE_ID}_connectivity/config",
        f"gh/v1/greenhouse/state/{NODE_ID}/telemetry",
        f"gh/v1/greenhouse/state/{NODE_ID}/availability",
        f"gh/v1/greenhouse/state/{NODE_ID}/diagnostic",
    ]
    assert all(call.kwargs["payload"] == b"" for call in client.publish.call_args_list)
    assert all(call.kwargs["retain"] is True for call in client.publish.call_args_list)

    completed = service.registration_registry.get_retirement_job(retirement_id)
    assert completed.state is RetirementState.COMPLETED
    assert service.registration_registry.node_id_lease_state(NODE_ID) is NodeIdLeaseState.RETIRED
    assert service.processor.stale_messages(now=NOW) == ()
    service.registration_registry.close()


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_retained_canonical_state_cannot_resurrect_retired_node(
    client_class: object,
    tmp_path: Path,
) -> None:
    database, _retirement_id = retired_database(tmp_path)
    service = ManagerMqttService(Settings(system_id="greenhouse", pairing_db_path=str(database)))
    canonical = telemetry()
    canonical["received_at"] = "2026-07-26T08:00:00.000Z"
    message = Mock(
        topic=f"gh/v1/greenhouse/state/{NODE_ID}/telemetry",
        payload=json.dumps(canonical).encode("utf-8"),
    )

    service._on_message(client_class.return_value, None, message)

    client_class.return_value.publish.assert_not_called()
    assert service.processor.stale_messages(now=NOW) == ()
    service.registration_registry.close()
