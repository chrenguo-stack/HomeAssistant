from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.pairing_intake import (
    PAIRING_HELLO_SUBSCRIPTION,
    PairingHelloProcessor,
    redacted_hardware_id,
    redacted_pairing_id,
)
from greenhouse_manager.registration import RegistrationRegistry, RegistrationState

NOW = datetime(2026, 7, 11, 10, 30, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
TOPIC = f"gh/bootstrap/v1/node/{HARDWARE_ID}/hello"


def valid_hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": "c83aeb0d-8f48-4a39-a34b-ea584a588475",
        "pairing_epoch": 3,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "simulator-M2.1b",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


@pytest.fixture
def processor(tmp_path: Path) -> PairingHelloProcessor:
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3", pending_ttl_s=120)
    instance = PairingHelloProcessor(registry)
    yield instance
    registry.close()


def test_subscription_is_limited_to_hello_namespace() -> None:
    assert PAIRING_HELLO_SUBSCRIPTION == "gh/bootstrap/v1/node/+/hello"


def test_accepts_and_persists_valid_hello(processor: PairingHelloProcessor) -> None:
    result = processor.process(TOPIC, json.dumps(valid_hello()), received_at=NOW)
    record = processor.registry.get(HARDWARE_ID)

    assert result.status == "created"
    assert result.hardware_id == HARDWARE_ID
    assert result.pairing_id == valid_hello()["pairing_id"]
    assert result.state == RegistrationState.PENDING
    assert record.state == RegistrationState.PENDING


def test_deduplicates_repeated_mqtt_delivery(processor: PairingHelloProcessor) -> None:
    payload = json.dumps(valid_hello())
    first = processor.process(TOPIC, payload, received_at=NOW)
    second = processor.process(TOPIC, payload, received_at=NOW + timedelta(seconds=1))

    assert first.status == "created"
    assert second.status == "duplicate"


@pytest.mark.parametrize(
    ("topic", "payload", "reason"),
    [
        ("gh/bootstrap/v1/node/not-a-hardware-id/hello", b"{}", "invalid_topic"),
        (TOPIC, b"not-json", "invalid_json"),
        (TOPIC, b"[]", "invalid_hello"),
        (TOPIC, b"x" * 4097, "payload_too_large"),
    ],
)
def test_rejects_invalid_mqtt_input(
    processor: PairingHelloProcessor, topic: str, payload: bytes, reason: str
) -> None:
    result = processor.process(topic, payload, received_at=NOW)

    assert result.status == "rejected"
    assert result.reason == reason
    assert processor.registry.list_current() == ()


def test_rejects_topic_and_payload_hardware_mismatch(processor: PairingHelloProcessor) -> None:
    hello = valid_hello()
    hello["hardware_id"] = "ghw-c6-112233445566"

    result = processor.process(TOPIC, json.dumps(hello), received_at=NOW)

    assert result.status == "rejected"
    assert result.reason == "topic_hardware_mismatch"
    assert processor.registry.list_current() == ()


def test_pairing_pop_is_rejected_and_never_returned(processor: PairingHelloProcessor) -> None:
    hello = valid_hello()
    hello["pairing_pop"] = "secret-must-not-cross-mqtt"

    result = processor.process(TOPIC, json.dumps(hello), received_at=NOW)

    assert result.status == "rejected"
    assert result.reason == "invalid_hello"
    assert "secret" not in repr(result)


def test_expires_pending_records(processor: PairingHelloProcessor) -> None:
    processor.process(TOPIC, json.dumps(valid_hello()), received_at=NOW)

    expired = processor.expire_pending(now=NOW + timedelta(seconds=121))

    assert expired == 1
    assert processor.registry.get(HARDWARE_ID).state == RegistrationState.EXPIRED


def test_log_identifiers_are_redacted() -> None:
    assert redacted_hardware_id(HARDWARE_ID) == "a9f2f8"
    assert redacted_pairing_id("c83aeb0d-8f48-4a39-a34b-ea584a588475") == "c83aeb0d"
