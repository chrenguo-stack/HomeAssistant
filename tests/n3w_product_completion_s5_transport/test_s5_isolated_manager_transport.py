from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host" / "greenhouse-manager" / "src"))

from greenhouse_manager.runtime.config import Settings  # noqa: E402
from greenhouse_manager.runtime.n3w_product_authority_time import (  # noqa: E402
    PeerAuthorizationTimeMqttAdapter,
    PeerAuthorizationTimeRejected,
)
from greenhouse_manager.runtime.n3w_product_isolated_mqtt_service import (  # noqa: E402
    N3wProductIsolatedMqttService,
)

SYSTEM_ID = "system001"
NOW_MS = 1_786_689_000_100


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
    assert "N3wProductIsolatedMqttService" not in normal_app
    assert "n3w_product_isolated_mqtt_service" not in normal_app
    assert "PeerAuthorizationTimeMqttAdapter" not in product_service
