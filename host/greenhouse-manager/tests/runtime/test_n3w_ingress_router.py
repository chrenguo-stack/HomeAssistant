from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from greenhouse_manager.runtime.ingest import PrepareResult, TelemetryProcessor
from greenhouse_manager.runtime.n3w_ingress_router import N3wManagerIngressRouter
from greenhouse_manager.runtime.n3w_path_lease import N3wPathLeaseCoordinator, PathLeasePolicy
from greenhouse_manager.runtime.n3w_relay_ingress import (
    N3wRelayIngressCore,
    RelayEnvelope,
    StaticRelayAuthorizationProvider,
    build_aad,
    derive_nonce,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SYSTEM_ID = "system_001"
GATEWAY_ID = "gateway_001"
NODE_ID = "node_0001"
BOOT_1 = "boot_0000000000000001"
BOOT_2 = "boot_0000000000000002"
KEY_EPOCH = 1
KEY = bytes(range(32))
DIRECT_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
RELAY_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/gateway/{GATEWAY_ID}/{NODE_ID}/frame"
NOW = datetime(2026, 8, 7, 6, 30, tzinfo=UTC)
PATH_POLICY = PathLeasePolicy(
    stability_window_s=5,
    minimum_distinct_frames=2,
    lease_ttl_s=10,
    old_path_grace_s=3,
)


def telemetry(*, boot_id: str = BOOT_1, seq: int = 1) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": boot_id,
        "seq": seq,
        "uptime_ms": 1234,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def authorization() -> StaticRelayAuthorizationProvider:
    return StaticRelayAuthorizationProvider(
        active_nodes=frozenset({NODE_ID}),
        gateway_nodes={GATEWAY_ID: frozenset({NODE_ID})},
        keys={(NODE_ID, KEY_EPOCH): KEY},
    )


def relay_payload(document: dict[str, object]) -> bytes:
    boot_id = str(document["boot_id"])
    seq = int(document["seq"])
    nonce = derive_nonce(boot_id, seq)
    envelope = RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=GATEWAY_ID,
        node_id=NODE_ID,
        hop_count=1,
        key_epoch=KEY_EPOCH,
        boot_id=boot_id,
        seq=seq,
        nonce=nonce,
        ciphertext=b"placeholder",
        tag=b"0" * 16,
    )
    sealed = AESGCM(KEY).encrypt(
        nonce,
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
        build_aad(envelope),
    )
    outer = {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": GATEWAY_ID,
        "node_id": NODE_ID,
        "hop_count": 1,
        "key_epoch": KEY_EPOCH,
        "boot_id": boot_id,
        "seq": seq,
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(sealed[:-16]).decode(),
        "tag_b64": base64.b64encode(sealed[-16:]).decode(),
    }
    return json.dumps(outer, separators=(",", ":")).encode()


def make_path(replay: ReplayRegistry, *, ingress_allowed: bool = True) -> N3wPathLeaseCoordinator:
    return N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=PATH_POLICY,
        ingress_allowed=lambda _node_id: ingress_allowed,
    )


def make_router(database: Path, *, ingress_allowed: bool = True) -> N3wManagerIngressRouter:
    replay = ReplayRegistry(database)
    processor = TelemetryProcessor(system_id=SYSTEM_ID)
    relay = N3wRelayIngressCore(
        system_id=SYSTEM_ID,
        authorization=authorization(),
        replay_registry=replay,
    )
    return N3wManagerIngressRouter(
        processor=processor,
        replay_registry=replay,
        relay_core=relay,
        path_lease=make_path(replay, ingress_allowed=ingress_allowed),
    )


def test_requires_one_shared_replay_registry_and_system_identity(tmp_path: Path) -> None:
    first = ReplayRegistry(tmp_path / "first.sqlite3")
    second = ReplayRegistry(tmp_path / "second.sqlite3")
    try:
        relay = N3wRelayIngressCore(
            system_id=SYSTEM_ID,
            authorization=authorization(),
            replay_registry=first,
        )
        try:
            N3wManagerIngressRouter(
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                replay_registry=second,
                relay_core=relay,
                path_lease=make_path(second),
            )
        except ValueError as exc:
            assert str(exc) == "replay_registry_must_be_shared"
        else:
            raise AssertionError("split replay registries must be rejected")

        try:
            N3wManagerIngressRouter(
                processor=TelemetryProcessor(system_id="system_999"),
                replay_registry=first,
                relay_core=relay,
                path_lease=make_path(first),
            )
        except ValueError as exc:
            assert str(exc) == "system_id_mismatch"
        else:
            raise AssertionError("split system identity must be rejected")

        split_path = make_path(second)
        try:
            N3wManagerIngressRouter(
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                replay_registry=first,
                relay_core=relay,
                path_lease=split_path,
            )
        except ValueError as exc:
            assert str(exc) == "path_lease_replay_registry_must_be_shared"
        else:
            raise AssertionError("split path/replay registries must be rejected")
    finally:
        first.close()
        second.close()


def test_direct_validation_then_path_replay_then_canonical_commit(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3")
    payload = json.dumps(telemetry())
    try:
        accepted = router.process_direct(DIRECT_TOPIC, payload, received_at=NOW)
        duplicate = router.process_direct(DIRECT_TOPIC, payload, received_at=NOW)

        assert accepted.status == "accepted"
        assert accepted.source == "direct"
        assert len(accepted.messages) == 2
        assert accepted.messages[0].payload["received_at"] == "2026-08-07T06:30:00.000Z"
        assert duplicate.status == "duplicate"
        assert duplicate.code in {
            "canonical_duplicate",
            "canonical_duplicate_reconciled",
            "duplicate_node_boot_seq",
        }
    finally:
        router.replay_registry.close()


def test_invalid_direct_payload_does_not_consume_replay_tuple(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3")
    invalid = telemetry()
    invalid.pop("power")
    try:
        rejected = router.process_direct(DIRECT_TOPIC, json.dumps(invalid), received_at=NOW)
        corrected = router.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        )

        assert rejected.status == "rejected"
        assert rejected.code == "canonical_validation_rejected"
        assert corrected.status == "accepted"
    finally:
        router.replay_registry.close()


def test_direct_path_enforces_n3w_persistent_boot_session_contract(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3")
    legacy = telemetry(boot_id="boot_legacy_01")
    try:
        rejected = router.process_direct(DIRECT_TOPIC, json.dumps(legacy), received_at=NOW)
        corrected = router.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        )

        assert rejected.status == "rejected"
        assert rejected.code == "boot_session_invalid"
        assert corrected.status == "accepted"
    finally:
        router.replay_registry.close()


def test_relay_handoff_produces_existing_canonical_pipeline_messages(tmp_path: Path) -> None:
    direct_router = make_router(tmp_path / "direct.sqlite3")
    relay_router = make_router(tmp_path / "relay.sqlite3")
    document = telemetry()
    try:
        direct = direct_router.process_direct(
            DIRECT_TOPIC,
            json.dumps(document),
            received_at=NOW,
        )
        relay = relay_router.process_relay(
            RELAY_TOPIC,
            relay_payload(document),
            received_at=NOW,
        )

        assert direct.status == relay.status == "accepted"
        assert direct.messages == relay.messages
        assert relay.source == "relay"
    finally:
        direct_router.replay_registry.close()
        relay_router.replay_registry.close()


def test_direct_then_relay_and_relay_then_direct_are_cross_path_duplicates(tmp_path: Path) -> None:
    first = make_router(tmp_path / "first.sqlite3")
    second = make_router(tmp_path / "second.sqlite3")
    try:
        direct = first.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        )
        relay_duplicate = first.process_relay(
            RELAY_TOPIC,
            relay_payload(telemetry()),
            received_at=NOW,
        )
        assert direct.status == "accepted"
        assert relay_duplicate.status == "duplicate"
        assert relay_duplicate.code == "duplicate_node_boot_seq"

        relay = second.process_relay(
            RELAY_TOPIC,
            relay_payload(telemetry()),
            received_at=NOW,
        )
        direct_duplicate = second.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        )
        assert relay.status == "accepted"
        assert direct_duplicate.status == "duplicate"
    finally:
        first.replay_registry.close()
        second.replay_registry.close()


def test_cross_path_duplicate_survives_router_restart(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    first = make_router(database)
    assert (
        first.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        ).status
        == "accepted"
    )
    first.replay_registry.close()

    reopened = make_router(database)
    try:
        duplicate = reopened.process_relay(
            RELAY_TOPIC,
            relay_payload(telemetry()),
            received_at=NOW,
        )
        assert duplicate.status == "duplicate"
        assert duplicate.code == "duplicate_node_boot_seq"
    finally:
        reopened.replay_registry.close()


def test_higher_session_blocks_lower_session_across_paths(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3")
    try:
        higher = router.process_relay(
            RELAY_TOPIC,
            relay_payload(telemetry(boot_id=BOOT_2, seq=0)),
            received_at=NOW,
        )
        stale = router.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry(boot_id=BOOT_1, seq=99)),
            received_at=NOW,
        )

        assert higher.status == "accepted"
        assert stale.status == "rejected"
        assert stale.code == "stale_boot_session"
    finally:
        router.replay_registry.close()


def test_relay_canonical_validation_failure_happens_before_path_replay_commit(tmp_path: Path) -> None:
    class RejectingProcessor(TelemetryProcessor):
        def prepare(self, *args: object, **kwargs: object) -> PrepareResult:
            return PrepareResult(
                status="rejected",
                node_id=NODE_ID,
                reason="forced canonical rejection",
            )

    database = tmp_path / "replay.sqlite3"
    replay = ReplayRegistry(database)
    relay_core = N3wRelayIngressCore(
        system_id=SYSTEM_ID,
        authorization=authorization(),
        replay_registry=replay,
    )
    router = N3wManagerIngressRouter(
        processor=RejectingProcessor(system_id=SYSTEM_ID),
        replay_registry=replay,
        relay_core=relay_core,
        path_lease=make_path(replay),
    )
    try:
        rejected = router.process_relay(RELAY_TOPIC, relay_payload(telemetry()), received_at=NOW)
        inspection = replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=1)

        assert rejected.status == "rejected"
        assert rejected.code == "canonical_validation_rejected"
        assert inspection.status == "ready"
        assert router.path_lease.audit()["node_count"] == 0
    finally:
        replay.close()


def test_unavailable_replay_registry_fails_direct_path_before_canonical_commit(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3")
    router.replay_registry.close()

    result = router.process_direct(
        DIRECT_TOPIC,
        json.dumps(telemetry()),
        received_at=NOW,
    )

    assert result.status == "rejected"
    assert result.code == "replay_registry_unavailable"
    assert router.processor.stale_messages(now=NOW) == ()


def test_registration_lifecycle_denial_blocks_router_before_replay_or_canonical(tmp_path: Path) -> None:
    router = make_router(tmp_path / "replay.sqlite3", ingress_allowed=False)
    try:
        result = router.process_direct(
            DIRECT_TOPIC,
            json.dumps(telemetry()),
            received_at=NOW,
        )
        assert result.status == "rejected"
        assert result.code == "node_ingress_not_allowed"
        assert router.replay_registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=1).status == "ready"
        assert router.processor.stale_messages(now=NOW) == ()
    finally:
        router.replay_registry.close()
