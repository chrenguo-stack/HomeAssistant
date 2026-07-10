from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from greenhouse_manager.ingest import TelemetryProcessor

NODE_ID = "node_01HZX7AQ5FJ3"
TOPIC = f"gh/v1/dev/ingress/node/{NODE_ID}/telemetry"
NOW = datetime(2026, 7, 10, 5, 40, tzinfo=UTC)


def valid_payload() -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_01J2A6Q9T8W4",
        "seq": 42,
        "uptime_ms": 125430,
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


def test_accepts_and_canonicalizes_valid_telemetry() -> None:
    processor = TelemetryProcessor(system_id="dev")

    result = processor.process(TOPIC, json.dumps(valid_payload()), received_at=NOW)

    assert result.status == "accepted"
    assert result.node_id == NODE_ID
    assert result.dedup_key == (NODE_ID, "boot_01J2A6Q9T8W4", 42)
    assert len(result.messages) == 2
    assert result.messages[0].topic == f"gh/v1/dev/state/{NODE_ID}/telemetry"
    assert result.messages[0].payload["received_at"] == "2026-07-10T05:40:00.000Z"
    assert result.messages[1].payload["state"] == "online"


def test_rejects_duplicate_without_republishing() -> None:
    processor = TelemetryProcessor(system_id="dev")
    payload = json.dumps(valid_payload())

    first = processor.process(TOPIC, payload, received_at=NOW)
    second = processor.process(TOPIC, payload, received_at=NOW + timedelta(seconds=1))

    assert first.status == "accepted"
    assert second.status == "duplicate"
    assert second.messages == ()


def test_rejects_topic_and_payload_node_mismatch() -> None:
    processor = TelemetryProcessor(system_id="dev")
    payload = valid_payload()
    payload["node_id"] = "node_01DIFFERENT"

    result = processor.process(TOPIC, json.dumps(payload), received_at=NOW)

    assert result.status == "rejected"
    assert result.reason == "payload node_id does not match topic node_id"


def test_rejects_schema_violation() -> None:
    processor = TelemetryProcessor(system_id="dev")
    payload = valid_payload()
    measurements = payload["measurements"]
    assert isinstance(measurements, dict)
    measurements["air_humidity_pct"] = 140

    result = processor.process(TOPIC, json.dumps(payload), received_at=NOW)

    assert result.status == "rejected"
    assert result.reason is not None
    assert "schema validation failed" in result.reason


def test_rejects_manager_owned_received_at_on_ingress() -> None:
    processor = TelemetryProcessor(system_id="dev")
    payload = valid_payload()
    payload["received_at"] = "2026-07-10T05:40:00Z"

    result = processor.process(TOPIC, json.dumps(payload), received_at=NOW)

    assert result.status == "rejected"
    assert "manager-owned received_at" in (result.reason or "")


def test_marks_node_unavailable_after_stale_timeout() -> None:
    processor = TelemetryProcessor(system_id="dev", stale_after_s=180)
    processor.process(TOPIC, json.dumps(valid_payload()), received_at=NOW)

    before = processor.stale_messages(now=NOW + timedelta(seconds=180))
    after = processor.stale_messages(now=NOW + timedelta(seconds=181))
    repeated = processor.stale_messages(now=NOW + timedelta(seconds=240))

    assert before == ()
    assert len(after) == 1
    assert after[0].payload["state"] == "unavailable"
    assert repeated == ()
