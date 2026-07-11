from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.registration import (
    HelloValidationError,
    RegistrationConflict,
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"


def valid_hello(*, pairing_id: str = PAIRING_ID, epoch: int = 3) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": epoch,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


@pytest.fixture
def registry(tmp_path: Path) -> RegistrationRegistry:
    instance = RegistrationRegistry(tmp_path / "registration.sqlite3", pending_ttl_s=120)
    yield instance
    instance.close()


def test_strictly_validates_untrusted_hello(registry: RegistrationRegistry) -> None:
    invalid = valid_hello()
    invalid["pairing_pop"] = "must-never-cross-mqtt"

    with pytest.raises(HelloValidationError, match="Additional properties"):
        registry.observe_hello(invalid, now=NOW)

    invalid = valid_hello()
    invalid["node_nonce"] = "too-short"
    with pytest.raises(HelloValidationError, match="node_nonce"):
        registry.observe_hello(invalid, now=NOW)


def test_creates_pending_and_deduplicates_same_session(registry: RegistrationRegistry) -> None:
    created = registry.observe_hello(valid_hello(), now=NOW)
    duplicate = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=10))

    assert created.status == "created"
    assert created.record.state == RegistrationState.PENDING
    assert created.record.expires_at == NOW + timedelta(seconds=120)
    assert duplicate.status == "duplicate"
    assert duplicate.record.first_seen_at == NOW
    assert duplicate.record.last_seen_at == NOW + timedelta(seconds=10)


def test_approved_device_requires_repair_authorization_and_preserves_node_id(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    approved = registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    next_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    blocked = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=19),
    )
    registry.authorize_repair(HARDWARE_ID)
    superseded = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=20),
    )
    reapproved = registry.approve(
        HARDWARE_ID,
        next_pairing_id,
        now=NOW + timedelta(seconds=21),
    )

    assert approved.node_id == NODE_ID
    assert blocked.status == "rejected"
    assert blocked.reason == "repair_not_authorized"
    assert blocked.record.state == RegistrationState.APPROVED
    assert superseded.status == "superseded"
    assert superseded.record.node_id == NODE_ID
    assert reapproved.node_id == NODE_ID
    assert reapproved.state == RegistrationState.APPROVED


def test_first_approval_requires_explicit_node_id(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    with pytest.raises(RegistrationConflict, match="node_id is required"):
        registry.approve(HARDWARE_ID, PAIRING_ID, now=NOW)


def test_rejects_pairing_replay_and_epoch_rollback(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.reject(HARDWARE_ID, PAIRING_ID)

    replay = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=1))
    rollback = registry.observe_hello(
        valid_hello(
            pairing_id="3de01176-a1bb-4f5a-b1f8-cdeaf42e54c0",
            epoch=2,
        ),
        now=NOW + timedelta(seconds=2),
    )

    assert replay.status == "rejected"
    assert replay.reason == "replay_detected"
    assert rollback.status == "rejected"
    assert rollback.reason == "generation_rollback"


def test_new_epoch_supersedes_pending_session(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    next_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"

    result = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=1),
    )
    old_replay = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=2))

    assert result.status == "superseded"
    assert result.record.pairing_id == next_pairing_id
    assert old_replay.status == "rejected"
    assert old_replay.reason == "replay_detected"


def test_expires_pending_and_refuses_late_approval(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    assert registry.expire_pending(now=NOW + timedelta(seconds=120)) == 0
    assert registry.expire_pending(now=NOW + timedelta(seconds=121)) == 1
    assert registry.get(HARDWARE_ID).state == RegistrationState.EXPIRED
    with pytest.raises(RegistrationConflict, match="expired state"):
        registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)


def test_node_id_cannot_be_assigned_to_two_hardware_ids(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    second = valid_hello(pairing_id="d5bcf708-88a0-4974-8ca9-597482974e94")
    second["hardware_id"] = "ghw-c6-112233445566"
    registry.observe_hello(second, now=NOW)
    with pytest.raises(RegistrationConflict, match="already assigned"):
        registry.approve(
            "ghw-c6-112233445566",
            "d5bcf708-88a0-4974-8ca9-597482974e94",
            node_id=NODE_ID,
            now=NOW,
        )


def test_registry_survives_process_restart(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as first:
        first.observe_hello(valid_hello(), now=NOW)
        first.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    with RegistrationRegistry(database) as restored:
        record = restored.get(HARDWARE_ID)

    assert record.state == RegistrationState.APPROVED
    assert record.node_id == NODE_ID
    assert json.loads(json.dumps(record.capabilities)) == [
        "mqtt-runtime-credentials",
        "lcd-pairing-qr",
    ]
