from __future__ import annotations

from datetime import UTC, datetime

import pytest

from greenhouse_manager.runtime.n3w_node_credentials import ProductCredentialBundle
from greenhouse_manager.runtime.n3w_peer_trust_store import SystemPeerTrustStore
from greenhouse_manager.runtime.n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
)

NOW = datetime(2026, 9, 1, 3, 30, tzinfo=UTC)
SYSTEM_ID = "gh-system-01"
NODE_ID = "node_22222222222222222222222222222222"


def _bundle(generation: int) -> ProductCredentialBundle:
    return ProductCredentialBundle(
        schema="gh.pair.credentials/1",
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        broker_host="mqtt.greenhouse.local",
        broker_port=8883,
        broker_tls_server_name="mqtt.greenhouse.local",
        ca_pem="TEST-CA",
        mqtt_username=f"ghn_{NODE_ID}",
        mqtt_client_id=NODE_ID,
        credential_generation=generation,
        n3w_key_epoch=4,
        mqtt_password="replacement-secret",
        n3w_application_key="A" * 43,
    )


def test_recovery_does_not_initialize_missing_peer_trust(tmp_path) -> None:
    with SystemPeerTrustStore(tmp_path / "peer-trust.sqlite3") as store:
        issuer = SimplifiedCredentialBundleIssuer(store)

        with pytest.raises(KeyError):
            issuer.issue(_bundle(2), now=NOW)

        assert store.audit()["system_count"] == 0


def test_first_registration_may_initialize_peer_trust(tmp_path) -> None:
    with SystemPeerTrustStore(tmp_path / "peer-trust.sqlite3") as store:
        issuer = SimplifiedCredentialBundleIssuer(store)
        issued = issuer.issue(_bundle(1), now=NOW)

        assert issued.peer_trust_generation == 1
        assert store.audit()["system_count"] == 1


def test_recovery_reuses_existing_peer_trust_without_rotation(tmp_path) -> None:
    with SystemPeerTrustStore(tmp_path / "peer-trust.sqlite3") as store:
        issuer = SimplifiedCredentialBundleIssuer(store)
        first = issuer.issue(_bundle(1), now=NOW)
        before = store.snapshot(SYSTEM_ID)

        recovered = issuer.issue(_bundle(2), now=NOW)
        after = store.snapshot(SYSTEM_ID)

        assert recovered.system_peer_key == first.system_peer_key
        assert recovered.peer_trust_generation == first.peer_trust_generation
        assert after == before
