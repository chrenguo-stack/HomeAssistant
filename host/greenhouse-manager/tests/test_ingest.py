from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from greenhouse_manager.ingest import TelemetryProcessor

NODE_ID = "node_01HZX7AQ5FJ3"
TOPIC = f"gh/v1/dev/ingress/node/{NODE_ID}/telemetry"
CANONICAL_TOPIC = f"gh/v1/dev/state/{NODE_ID}/telemetry"
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


def canonical_payload(*, received_at: datetime = NOW) -> dict[str, object]:
    payload = valid_payload()
    payload["received_at"] = received_at.isoformat().replace("+00:00", "Z")
    return payload


def test_accepts_and_canonicalizes_valid_telemetry() -> None:
    processor = TelemetryProcessor(system_id="dev")

    result = processor.process(TOPIC, json.dumps(valid_payload()), received_at=NOW)

    assert result.status == "accepted"
    assert result.node_id == NODE_ID
    assert result.dedup_key == (NODE_ID, "boot_01J2A6Q9T8W4", 42)
    assert len(result.messages) == 2
    assert result.messages[0].topic == CANONICAL_TOPIC
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


def test_restores_stale_tracking_from_retained_canonical_telemetry() -> None:
    processor = TelemetryProcessor(system_id="dev", stale_after_s=180)

    restored = processor.restore_canonical(CANONICAL_TOPIC, json.dumps(canonical_payload()))
    stale = processor.stale_messages(now=NOW + timedelta(seconds=181))

    assert restored.status == "restored"
    assert restored.last_seen == NOW
    assert len(stale) == 1
    assert stale[0].payload["state"] == "unavailable"
    assert stale[0].payload["last_seen"] == "2026-07-10T05:40:00.000Z"


def test_restore_seeds_deduplication_after_manager_restart() -> None:
    processor = TelemetryProcessor(system_id="dev")

    restored = processor.restore_canonical(CANONICAL_TOPIC, json.dumps(canonical_payload()))
    repeated_ingress = processor.process(
        TOPIC,
        json.dumps(valid_payload()),
        received_at=NOW + timedelta(seconds=1),
    )

    assert restored.status == "restored"
    assert repeated_ingress.status == "duplicate"


def test_restore_does_not_overwrite_newer_in_memory_last_seen() -> None:
    processor = TelemetryProcessor(system_id="dev", stale_after_s=180)
    newer = NOW + timedelta(seconds=120)
    processor.process(TOPIC, json.dumps(valid_payload()), received_at=newer)

    restored = processor.restore_canonical(CANONICAL_TOPIC, json.dumps(canonical_payload()))
    before_timeout = processor.stale_messages(now=newer + timedelta(seconds=180))

    assert restored.status == "restored"
    assert before_timeout == ()


def test_rejects_canonical_telemetry_without_received_at() -> None:
    processor = TelemetryProcessor(system_id="dev")

    restored = processor.restore_canonical(CANONICAL_TOPIC, json.dumps(valid_payload()))

    assert restored.status == "rejected"
    assert "missing manager-owned received_at" in (restored.reason or "")


def test_retries_unavailable_after_publish_failure() -> None:
    processor = TelemetryProcessor(system_id="dev", stale_after_s=180)
    processor.process(TOPIC, json.dumps(valid_payload()), received_at=NOW)

    first = processor.stale_messages(now=NOW + timedelta(seconds=181))
    assert len(first) == 1

    processor.mark_unavailable_publish_failed(NODE_ID)
    retry = processor.stale_messages(now=NOW + timedelta(seconds=186))

    assert len(retry) == 1
    assert retry[0].topic == first[0].topic
    assert retry[0].payload["state"] == "unavailable"


def test_process_and_stale_scans_are_thread_safe_and_keep_latest_last_seen() -> None:
    processor = TelemetryProcessor(system_id="dev", stale_after_s=180)
    node_ids = tuple(f"node_{index:04d}" for index in range(32))
    rounds = 32
    start = Barrier(2)

    def write_telemetry() -> None:
        start.wait()
        for sequence in range(rounds):
            observed_at = NOW + timedelta(seconds=sequence)
            for node_id in node_ids:
                payload = valid_payload()
                payload["node_id"] = node_id
                payload["seq"] = 1000 + sequence
                topic = f"gh/v1/dev/ingress/node/{node_id}/telemetry"
                result = processor.process(topic, json.dumps(payload), received_at=observed_at)
                assert result.status == "accepted"

    def scan_for_stale_nodes() -> None:
        start.wait()
        for offset in range(rounds * len(node_ids) * 2):
            current = NOW + timedelta(seconds=offset % rounds)
            assert processor.stale_messages(now=current) == ()

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(write_telemetry)
        scanner = executor.submit(scan_for_stale_nodes)
        writer.result()
        scanner.result()

    latest = NOW + timedelta(seconds=rounds - 1)
    assert processor.stale_messages(now=latest + timedelta(seconds=180)) == ()

    stale = processor.stale_messages(now=latest + timedelta(seconds=181))
    assert {message.payload["node_id"] for message in stale} == set(node_ids)
    assert {message.payload["last_seen"] for message in stale} == {
        latest.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    }


def test_accepts_strictly_increasing_sequence_for_same_boot() -> None:
    processor = TelemetryProcessor(system_id="dev")
    first_payload = valid_payload()
    first_payload["seq"] = 42
    next_payload = valid_payload()
    next_payload["seq"] = 43

    first = processor.process(TOPIC, json.dumps(first_payload), received_at=NOW)
    second = processor.process(
        TOPIC,
        json.dumps(next_payload),
        received_at=NOW + timedelta(seconds=1),
    )

    assert first.status == "accepted"
    assert second.status == "accepted"


def test_rejects_out_of_order_or_replayed_sequence() -> None:
    processor = TelemetryProcessor(system_id="dev")
    current_payload = valid_payload()
    current_payload["seq"] = 42
    older_payload = valid_payload()
    older_payload["seq"] = 41

    accepted = processor.process(TOPIC, json.dumps(current_payload), received_at=NOW)
    rejected = processor.process(
        TOPIC,
        json.dumps(older_payload),
        received_at=NOW + timedelta(seconds=1),
    )

    assert accepted.status == "accepted"
    assert rejected.status == "rejected"
    assert rejected.reason == "out-of-order or replayed seq for node_id + boot_id"
    assert rejected.messages == ()
    assert rejected.dedup_key == (NODE_ID, "boot_01J2A6Q9T8W4", 41)


def test_accepts_sequence_reset_after_boot_id_changes() -> None:
    processor = TelemetryProcessor(system_id="dev")
    previous_boot = valid_payload()
    previous_boot["seq"] = 42
    new_boot = valid_payload()
    new_boot["boot_id"] = "boot_01J2A6Q9T8W5"
    new_boot["seq"] = 1

    first = processor.process(TOPIC, json.dumps(previous_boot), received_at=NOW)
    restarted = processor.process(
        TOPIC,
        json.dumps(new_boot),
        received_at=NOW + timedelta(seconds=1),
    )

    assert first.status == "accepted"
    assert restarted.status == "accepted"
    assert restarted.dedup_key == (NODE_ID, "boot_01J2A6Q9T8W5", 1)


def test_restore_seeds_max_sequence_and_rejects_older_ingress() -> None:
    processor = TelemetryProcessor(system_id="dev")
    retained = canonical_payload()
    retained["seq"] = 42
    older_payload = valid_payload()
    older_payload["seq"] = 41
    newer_payload = valid_payload()
    newer_payload["seq"] = 43

    restored = processor.restore_canonical(CANONICAL_TOPIC, json.dumps(retained))
    rejected = processor.process(
        TOPIC,
        json.dumps(older_payload),
        received_at=NOW + timedelta(seconds=1),
    )
    accepted = processor.process(
        TOPIC,
        json.dumps(newer_payload),
        received_at=NOW + timedelta(seconds=2),
    )

    assert restored.status == "restored"
    assert rejected.status == "rejected"
    assert rejected.reason == "out-of-order or replayed seq for node_id + boot_id"
    assert accepted.status == "accepted"
