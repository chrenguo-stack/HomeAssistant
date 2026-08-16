import json
from datetime import UTC, datetime

from greenhouse_manager.runtime.ingest import TelemetryProcessor
from greenhouse_manager.runtime.n3w_canonical_ingress import N3wCanonicalIngressCoordinator
from greenhouse_manager.runtime.n3w_compact_relay import (
    CompactRelayIngressCore,
    StaticNodeApplicationKeyProvider,
    encrypt_compact_telemetry,
    wrap_relay_frame,
)
from greenhouse_manager.runtime.n3w_multi_ingress_router import N3wMultiIngressRouter
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SYSTEM_ID = "gh-system-01"
NODE_ID = "node_child01"
BOOT_ID = "boot_0000000000000001"
KEY = bytes(range(32))
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def telemetry(seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": BOOT_ID,
        "seq": seq,
        "uptime_ms": 1234 + seq,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def direct_payload(seq: int) -> str:
    return json.dumps(telemetry(seq), separators=(",", ":"), sort_keys=True)


def relay_payload(seq: int) -> bytes:
    plaintext = direct_payload(seq).encode()
    return wrap_relay_frame(
        encrypt_compact_telemetry(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            key_epoch=1,
            boot_id=BOOT_ID,
            seq=seq,
            key=KEY,
            plaintext=plaintext,
        )
    )


def test_direct_and_multiple_relays_share_one_canonical_cursor(tmp_path) -> None:
    processor = TelemetryProcessor(system_id=SYSTEM_ID)
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: True,
        )
        relay = CompactRelayIngressCore(
            system_id=SYSTEM_ID,
            keys=StaticNodeApplicationKeyProvider({(NODE_ID, 1): KEY}),
        )
        router = N3wMultiIngressRouter(
            processor=processor,
            canonical=canonical,
            relay_core=relay,
        )
        direct_topic = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
        relay_a = f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay01/{NODE_ID}/frame"
        relay_b = f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay02/{NODE_ID}/frame"

        first = router.process_direct(direct_topic, direct_payload(100), received_at=NOW)
        duplicate = router.process_relay(relay_a, relay_payload(100), received_at=NOW)
        advanced = router.process_relay(relay_b, relay_payload(101), received_at=NOW)
        stale = router.process_direct(direct_topic, direct_payload(100), received_at=NOW)
        recovered = router.process_direct(direct_topic, direct_payload(102), received_at=NOW)

    assert first.status == "accepted"
    assert duplicate.status == "duplicate"
    assert advanced.status == "accepted"
    assert advanced.gateway_id == "node_relay02"
    assert stale.status == "rejected"
    assert stale.code == "stale_sequence"
    assert recovered.status == "accepted"


def test_lifecycle_gate_applies_equally_to_direct_and_relay(tmp_path) -> None:
    processor = TelemetryProcessor(system_id=SYSTEM_ID)
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: False,
        )
        router = N3wMultiIngressRouter(
            processor=processor,
            canonical=canonical,
            relay_core=CompactRelayIngressCore(
                system_id=SYSTEM_ID,
                keys=StaticNodeApplicationKeyProvider({(NODE_ID, 1): KEY}),
            ),
        )
        direct_topic = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
        relay_topic = f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay01/{NODE_ID}/frame"
        direct = router.process_direct(direct_topic, direct_payload(1), received_at=NOW)
        relayed = router.process_relay(relay_topic, relay_payload(1), received_at=NOW)

    assert direct.status == "rejected"
    assert direct.code == "node_ingress_not_allowed"
    assert relayed.status == "rejected"
    assert relayed.code == "node_ingress_not_allowed"
