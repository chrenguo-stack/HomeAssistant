from __future__ import annotations

import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "greenhouse-manager" / "src"))

from greenhouse_manager.runtime.ingest import TelemetryProcessor  # noqa: E402
from greenhouse_manager.runtime.n3w_ingress_router import N3wManagerIngressRouter  # noqa: E402
from greenhouse_manager.runtime.n3w_path_lease import (  # noqa: E402
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
)
from greenhouse_manager.runtime.n3w_product_isolated_manager import (  # noqa: E402
    N3wProductIsolatedManager,
)
from greenhouse_manager.runtime.n3w_product_peer_authorization import (  # noqa: E402
    PeerAuthorizationService,
    SqlitePeerAuthorizationReplayStore,
)
from greenhouse_manager.runtime.n3w_relay_ingress import (  # noqa: E402
    N3wRelayIngressCore,
    RelayEnvelope,
    StaticRelayAuthorizationProvider,
    build_aad,
    derive_nonce,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry  # noqa: E402

SYSTEM_ID = "system001"
GATEWAY_ID = "node_relay01"
NODE_ID = "node_child01"
BOOT_ID = "boot_0000000000000001"
KEY_EPOCH = 3
KEY = bytes(range(32))
NOW = datetime(2026, 8, 14, 10, 30, tzinfo=UTC)


class UnusedEligibility:
    def get_relay_eligibility(self, **_: object) -> object:
        raise AssertionError("authorization is covered by the S5-A/B authority test")


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


def make_router(database: Path) -> N3wManagerIngressRouter:
    replay = ReplayRegistry(database)
    processor = TelemetryProcessor(system_id=SYSTEM_ID)
    authorization = StaticRelayAuthorizationProvider(
        active_nodes=frozenset({NODE_ID}),
        gateway_nodes={GATEWAY_ID: frozenset({NODE_ID})},
        keys={(NODE_ID, KEY_EPOCH): KEY},
    )
    relay = N3wRelayIngressCore(
        system_id=SYSTEM_ID,
        authorization=authorization,
        replay_registry=replay,
    )
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=PathLeasePolicy(
            stability_window_s=5,
            minimum_distinct_frames=2,
            lease_ttl_s=10,
            old_path_grace_s=3,
        ),
        ingress_allowed=lambda _node_id: True,
    )
    return N3wManagerIngressRouter(
        processor=processor,
        replay_registry=replay,
        relay_core=relay,
        path_lease=path,
    )


def make_isolated_manager(tmp_path: Path, router: N3wManagerIngressRouter) -> N3wProductIsolatedManager:
    replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-auth.sqlite3"))
    membership = SimpleNamespace(system_id=SYSTEM_ID)
    service = PeerAuthorizationService(
        membership,  # type: ignore[arg-type]
        UnusedEligibility(),  # type: ignore[arg-type]
        replay,
    )
    return N3wProductIsolatedManager(service, router)


def test_isolated_manager_reuses_canonical_relay_pipeline_and_preserves_identity(tmp_path: Path) -> None:
    direct_router = make_router(tmp_path / "direct.sqlite3")
    relay_router = make_router(tmp_path / "relay.sqlite3")
    manager = make_isolated_manager(tmp_path, relay_router)
    document = telemetry(42)
    direct_topic = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
    try:
        direct = direct_router.process_direct(
            direct_topic,
            json.dumps(document),
            received_at=NOW,
        )
        relay = manager.ingest_relay_frame(
            gateway_id=GATEWAY_ID,
            node_id=NODE_ID,
            payload=relay_payload(document),
            received_at=NOW,
        )

        assert direct.status == relay.status == "accepted"
        assert relay.source == "relay"
        assert relay.node_id == NODE_ID
        assert relay.dedup_key == (NODE_ID, BOOT_ID, 42)
        assert direct.messages == relay.messages
        assert relay.messages[0].payload["node_id"] == NODE_ID
        assert relay.messages[0].payload["seq"] == 42
        assert NODE_ID in relay.messages[0].topic
        assert NODE_ID in relay.messages[1].topic
    finally:
        direct_router.replay_registry.close()
        relay_router.replay_registry.close()
        manager.peer_authorization.replay_store.close()


def test_isolated_manager_rejects_split_system_composition(tmp_path: Path) -> None:
    router = make_router(tmp_path / "relay.sqlite3")
    replay = SqlitePeerAuthorizationReplayStore(str(tmp_path / "peer-auth.sqlite3"))
    service = PeerAuthorizationService(
        SimpleNamespace(system_id="system999"),  # type: ignore[arg-type]
        UnusedEligibility(),  # type: ignore[arg-type]
        replay,
    )
    try:
        try:
            N3wProductIsolatedManager(service, router)
        except ValueError as exc:
            assert str(exc) == "system_id_mismatch"
        else:
            raise AssertionError("split system composition must fail closed")
    finally:
        router.replay_registry.close()
        replay.close()
