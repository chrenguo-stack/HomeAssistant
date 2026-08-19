from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "greenhouse-manager" / "src"))

from greenhouse_manager.runtime.config import Settings  # noqa: E402
from greenhouse_manager.runtime.ingest import TelemetryProcessor  # noqa: E402
from greenhouse_manager.runtime.n3w_ingress_router import N3wManagerIngressRouter  # noqa: E402
from greenhouse_manager.runtime.n3w_path_lease import (  # noqa: E402
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
)
from greenhouse_manager.runtime.n3w_product_authority_time import (  # noqa: E402
    PeerAuthorizationTimeMqttAdapter,
    PeerAuthorizationTimeRejected,
)
from greenhouse_manager.runtime.n3w_product_isolated_mqtt_service import (  # noqa: E402
    DynamicIngressAuthorityError,
    FinitePeerIngressAuthority,
    N3wProductIsolatedMqttService,
    S5DynamicRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.n3w_product_manager_adapter import (  # noqa: E402
    ManagerRelayEligibilityProvider,
    ReplayRegistryPathAuthority,
    encode_peer_authorization_response,
)
from greenhouse_manager.runtime.n3w_product_peer_authorization import (  # noqa: E402
    EndpointGrant,
    PairAuthorization,
    RelayRuntimeHealth,
)
from greenhouse_manager.runtime.n3w_relay_ingress import (  # noqa: E402
    N3wRelayIngressCore,
    RelayIngressRejected,
    StaticRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry  # noqa: E402
from greenhouse_manager.runtime.replay_registry import ReplayRegistry  # noqa: E402

SYSTEM_ID = "system001"
NOW_MS = 1_786_689_000_100
NOW = datetime.fromtimestamp(NOW_MS / 1000, UTC)
RELAY_NODE = "node_relay01"
CHILD_NODE = "node_child01"
RELAY_HW = "ghw-c6-aabbccddeeff"
RELAY_PAIRING = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
AUTHORIZATION_ID = "11111111-2222-3333-4444-555555555555"
CHILD_KEY = bytes(range(32))


class _NodeKeys:
    def resolve_node_application_key(self, *, node_id: str, key_epoch: int) -> bytes:
        if node_id != CHILD_NODE or key_epoch != 1:
            raise KeyError((node_id, key_epoch))
        return CHILD_KEY


def _grant(*, role: str) -> EndpointGrant:
    return EndpointGrant(
        role=role,
        authorization_id=AUTHORIZATION_ID,
        system_id=SYSTEM_ID,
        session_id="s5-session-0001",
        child_node_id=CHILD_NODE,
        relay_node_id=RELAY_NODE,
        child_credential_generation=1,
        relay_credential_generation=2,
        child_key_epoch=1,
        relay_key_epoch=3,
        child_ephemeral_public_key=b"c" * 32,
        relay_ephemeral_public_key=b"r" * 32,
        child_nonce=b"C" * 32,
        relay_nonce=b"R" * 32,
        issued_at_ms=NOW_MS,
        expires_at_ms=NOW_MS + 30_000,
        authorization_epoch=7,
        grant_mac=(b"1" if role == "child" else b"2") * 32,
    )


def _authorization_payload() -> bytes:
    return encode_peer_authorization_response(
        PairAuthorization(
            child_grant=_grant(role="child"),
            relay_grant=_grant(role="relay"),
        )
    )


def _relay_hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": RELAY_PAIRING,
        "pairing_epoch": 1,
        "hardware_id": RELAY_HW,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "n3w-product-relay"],
        "sent_at_ms": 120345,
    }


def _direct_telemetry(*, seq: int = 1) -> bytes:
    return json.dumps(
        {
            "schema": "gh.telemetry/1",
            "node_id": RELAY_NODE,
            "boot_id": "boot_0000000000000001",
            "seq": seq,
            "uptime_ms": 1234 + seq,
            "cap_hash": "relay-cap-001",
            "measurements": {},
            "quality": {},
            "power": {"source": "main", "low": False},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_authority_time_transport_is_strict_and_manager_epoch_only() -> None:
    adapter = PeerAuthorizationTimeMqttAdapter(system_id=SYSTEM_ID)
    assert adapter.request_subscription == (
        "gh/v1/system001/ingress/node/+/relay-peer-auth/time-request"
    )
    topic = (
        "gh/v1/system001/ingress/node/node_relay01/"
        "relay-peer-auth/time-request"
    )
    response_topic, payload = adapter.handle(
        topic=topic,
        payload=(
            b'{"nonce":"s5t-1-1000",'
            b'"schema":"gh.n3w-product.peer-auth-time-request/1"}'
        ),
        now_ms=NOW_MS,
    )
    assert response_topic == (
        "gh/v1/system001/out/node/node_relay01/relay-peer-auth/time"
    )
    assert json.loads(payload) == {
        "authority_now_ms": NOW_MS,
        "nonce": "s5t-1-1000",
        "schema": "gh.n3w-product.peer-auth-time-response/1",
    }
    assert b"lmk" not in payload.lower()
    assert b"application_key" not in payload.lower()

    with pytest.raises(
        PeerAuthorizationTimeRejected,
        match="cross_system_rejected",
    ):
        adapter.handle(
            topic=(
                "gh/v1/system999/ingress/node/node_relay01/"
                "relay-peer-auth/time-request"
            ),
            payload=(
                b'{"nonce":"s5t-2-1000",'
                b'"schema":"gh.n3w-product.peer-auth-time-request/1"}'
            ),
            now_ms=NOW_MS,
        )

    for payload in (
        b'{"schema":"gh.n3w-product.peer-auth-time-request/1"}',
        b'{"nonce":"bad nonce","schema":"gh.n3w-product.peer-auth-time-request/1"}',
        b'{"nonce":"s5t-3-1000","schema":"wrong"}',
    ):
        with pytest.raises(PeerAuthorizationTimeRejected):
            adapter.handle(topic=topic, payload=payload, now_ms=NOW_MS)


def test_isolated_manager_service_is_explicit_opt_in() -> None:
    settings = Settings(system_id=SYSTEM_ID, n3w_runtime_enabled=False)
    with pytest.raises(ValueError, match="n3w_runtime_required"):
        N3wProductIsolatedMqttService(settings, None)  # type: ignore[arg-type]

    normal_app = (
        ROOT
        / "host"
        / "greenhouse-manager"
        / "src"
        / "greenhouse_manager"
        / "runtime"
        / "app.py"
    ).read_text(encoding="utf-8")
    product_service = (
        ROOT
        / "host"
        / "greenhouse-manager"
        / "src"
        / "greenhouse_manager"
        / "runtime"
        / "n3w_product_mqtt_service.py"
    ).read_text(encoding="utf-8")
    launcher = (
        ROOT
        / "host"
        / "greenhouse-manager"
        / "src"
        / "greenhouse_manager"
        / "runtime"
        / "n3w_product_isolated_launcher.py"
    ).read_text(encoding="utf-8")
    isolated = (
        ROOT
        / "host"
        / "greenhouse-manager"
        / "src"
        / "greenhouse_manager"
        / "runtime"
        / "n3w_product_isolated_mqtt_service.py"
    ).read_text(encoding="utf-8")
    assert "N3wProductIsolatedMqttService" not in normal_app
    assert "n3w_product_isolated_mqtt_service" not in normal_app
    assert "PeerAuthorizationTimeMqttAdapter" not in product_service
    assert "authority.application_keys" in launcher
    assert "relay_core.authorization = self.dynamic_relay_authorization" in isolated


def test_canonical_direct_ingress_is_the_relay_eligibility_authority(tmp_path: Path) -> None:
    registry = RegistrationRegistry(tmp_path / "registration.sqlite3")
    replay = ReplayRegistry(tmp_path / "replay.sqlite3")
    try:
        registry.observe_hello(_relay_hello(), now=NOW)
        registry.approve(RELAY_HW, RELAY_PAIRING, node_id=RELAY_NODE, now=NOW)
        processor = TelemetryProcessor(system_id=SYSTEM_ID)
        path = N3wPathLeaseCoordinator(
            replay_registry=replay,
            policy=PathLeasePolicy(
                stability_window_s=0,
                minimum_distinct_frames=1,
                lease_ttl_s=30,
                old_path_grace_s=2,
            ),
            ingress_allowed=registry.is_node_id_ingress_allowed,
        )
        relay_core = N3wRelayIngressCore(
            system_id=SYSTEM_ID,
            authorization=StaticRelayAuthorizationProvider(
                active_nodes=frozenset(),
                gateway_nodes={},
                keys={},
            ),
            replay_registry=replay,
        )
        router = N3wManagerIngressRouter(
            processor=processor,
            replay_registry=replay,
            relay_core=relay_core,
            path_lease=path,
        )
        eligibility = ManagerRelayEligibilityProvider(
            registry,
            ReplayRegistryPathAuthority(replay),
            system_id=SYSTEM_ID,
        )
        health = RelayRuntimeHealth(
            observed_at_ms=NOW_MS,
            relay_capable=True,
            low_battery=False,
            overloaded=False,
        )

        before = eligibility.get_relay_eligibility(
            system_id=SYSTEM_ID,
            node_id=RELAY_NODE,
            health=health,
            now_ms=NOW_MS,
        )
        assert before.direct_uplink is False
        assert before.eligible_at(NOW_MS) is False

        accepted = router.process_direct(
            f"gh/v1/{SYSTEM_ID}/ingress/node/{RELAY_NODE}/telemetry",
            _direct_telemetry(),
            received_at=NOW,
        )
        assert accepted.status == "accepted"
        assert accepted.source == "direct"

        after = eligibility.get_relay_eligibility(
            system_id=SYSTEM_ID,
            node_id=RELAY_NODE,
            health=health,
            now_ms=NOW_MS,
        )
        assert after.direct_uplink is True
        assert after.wifi_up is True
        assert after.uplink_available is True
        assert after.eligible_at(NOW_MS) is True
    finally:
        replay.close()
        registry.close()


def test_dynamic_ingress_authority_is_finite_exact_revoke_and_restart_empty() -> None:
    now = [NOW_MS + 1]
    authority = FinitePeerIngressAuthority(system_id=SYSTEM_ID)
    provider = S5DynamicRelayAuthorizationProvider(
        authority=authority,
        application_keys=_NodeKeys(),
        now_ms=lambda: now[0],
    )

    authority.install_response(_authorization_payload(), now_ms=NOW_MS)
    assert provider.resolve_key(
        gateway_id=RELAY_NODE,
        node_id=CHILD_NODE,
        key_epoch=1,
    ) == CHILD_KEY

    for gateway_id, node_id, key_epoch in (
        ("node_other01", CHILD_NODE, 1),
        (RELAY_NODE, "node_other01", 1),
        (RELAY_NODE, CHILD_NODE, 2),
    ):
        with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
            provider.resolve_key(
                gateway_id=gateway_id,
                node_id=node_id,
                key_epoch=key_epoch,
            )

    assert authority.revoke("22222222-2222-3333-4444-555555555555") is False
    assert provider.resolve_key(
        gateway_id=RELAY_NODE,
        node_id=CHILD_NODE,
        key_epoch=1,
    ) == CHILD_KEY

    assert authority.revoke(AUTHORIZATION_ID) is True
    with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
        provider.resolve_key(
            gateway_id=RELAY_NODE,
            node_id=CHILD_NODE,
            key_epoch=1,
        )

    authority.install_response(_authorization_payload(), now_ms=NOW_MS)
    now[0] = NOW_MS + 30_000
    with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
        provider.resolve_key(
            gateway_id=RELAY_NODE,
            node_id=CHILD_NODE,
            key_epoch=1,
        )
    assert authority.audit(now_ms=now[0])["active_authorization_count"] == 0

    restarted = FinitePeerIngressAuthority(system_id=SYSTEM_ID)
    restarted_provider = S5DynamicRelayAuthorizationProvider(
        authority=restarted,
        application_keys=_NodeKeys(),
        now_ms=lambda: NOW_MS + 1,
    )
    with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
        restarted_provider.resolve_key(
            gateway_id=RELAY_NODE,
            node_id=CHILD_NODE,
            key_epoch=1,
        )
    assert restarted.audit(now_ms=NOW_MS + 1)["restart_restores_authorizations"] is False


def test_dynamic_ingress_rejects_tampered_pair_binding() -> None:
    payload = json.loads(_authorization_payload())
    payload["relay_grant"]["child_node_id"] = "node_other01"
    authority = FinitePeerIngressAuthority(system_id=SYSTEM_ID)
    with pytest.raises(
        DynamicIngressAuthorityError,
        match="peer_authorization_pair_binding_mismatch",
    ):
        authority.install_response(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
            now_ms=NOW_MS,
        )
