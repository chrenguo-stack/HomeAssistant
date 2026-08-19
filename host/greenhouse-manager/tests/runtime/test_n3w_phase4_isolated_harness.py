import json
from datetime import UTC, datetime

from greenhouse_manager.runtime.n3w_compact_relay import (
    StaticNodeApplicationKeyProvider,
    encrypt_compact_telemetry,
    wrap_relay_frame,
)
from greenhouse_manager.runtime.n3w_phase4_isolated_harness import Phase4IsolatedManagerHarness
from greenhouse_manager.runtime.registration import RegistrationRegistry, RegistrationState
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SYSTEM_ID = "gh-system-01"
BOOT_ID = "boot_0000000000000001"
KEY = bytes(range(32))
NOW = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)


class FixedRandom:
    def __init__(self, *values: bytes) -> None:
        self.values = list(values)

    def __call__(self, size: int) -> bytes:
        assert size == 16
        return self.values.pop(0)


def hello(hardware_id: str, pairing_id: str) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": hardware_id,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-source-harness",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 1,
    }


def telemetry(node_id: str, seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": node_id,
        "boot_id": BOOT_ID,
        "seq": seq,
        "uptime_ms": 1000 + seq,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def direct_payload(node_id: str, seq: int) -> str:
    return json.dumps(telemetry(node_id, seq), separators=(",", ":"), sort_keys=True)


def relay_payload(node_id: str, seq: int) -> bytes:
    plaintext = direct_payload(node_id, seq).encode()
    return wrap_relay_frame(
        encrypt_compact_telemetry(
            system_id=SYSTEM_ID,
            node_id=node_id,
            key_epoch=1,
            boot_id=BOOT_ID,
            seq=seq,
            key=KEY,
            plaintext=plaintext,
        )
    )


def test_phase4_harness_auto_ids_and_path_independent_ingress(tmp_path) -> None:
    registration_path = tmp_path / "registration.sqlite3"
    replay_path = tmp_path / "replay.sqlite3"
    keys: dict[tuple[str, int], bytes] = {}

    with RegistrationRegistry(registration_path) as registration, ReplayRegistry(replay_path) as replay:
        hardware_a = "ghw-c6-00000000000a"
        hardware_b = "ghw-c6-00000000000b"
        pairing_a = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
        pairing_b = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
        registration.observe_hello(hello(hardware_a, pairing_a), now=NOW)
        registration.observe_hello(hello(hardware_b, pairing_b), now=NOW)

        harness = Phase4IsolatedManagerHarness(
            system_id=SYSTEM_ID,
            registration=registration,
            replay=replay,
            keys=StaticNodeApplicationKeyProvider(keys),
            random_bytes=FixedRandom(b"\x01" * 16, b"\x02" * 16),
        )
        node_a = harness.approve_registration(hardware_a, pairing_a, now=NOW)
        node_b = harness.approve_registration(hardware_b, pairing_b, now=NOW)

        assert node_a.state is RegistrationState.APPROVED
        assert node_b.state is RegistrationState.APPROVED
        assert node_a.node_id is not None
        assert node_b.node_id is not None
        assert node_a.node_id != node_b.node_id
        keys[(node_b.node_id, 1)] = KEY

        direct_topic = f"gh/v1/{SYSTEM_ID}/ingress/node/{node_b.node_id}/telemetry"
        relay_a = f"gh/v1/{SYSTEM_ID}/ingress/gateway/{node_a.node_id}/{node_b.node_id}/frame"

        first = harness.process_direct(direct_topic, direct_payload(node_b.node_id, 10), received_at=NOW)
        duplicate = harness.process_relay(relay_a, relay_payload(node_b.node_id, 10), received_at=NOW)
        advanced = harness.process_relay(relay_a, relay_payload(node_b.node_id, 11), received_at=NOW)
        stale = harness.process_direct(direct_topic, direct_payload(node_b.node_id, 10), received_at=NOW)

    assert first.status == "accepted"
    assert duplicate.status == "duplicate"
    assert advanced.status == "accepted"
    assert advanced.gateway_id == node_a.node_id
    assert stale.status == "rejected"
    assert stale.code == "stale_sequence"
