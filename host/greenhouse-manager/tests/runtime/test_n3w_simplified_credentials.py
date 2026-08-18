import inspect
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from greenhouse_manager.runtime import n3w_simplified_credentials as simplified_credentials
from greenhouse_manager.runtime.n3w_peer_trust_store import SystemPeerTrustStore
from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    decrypt_credential_bundle,
    derive_bootstrap_key,
)
from greenhouse_manager.runtime.n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
    encrypt_for_setup_secret,
)

SYSTEM_ID = "gh-system-01"
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
PEER_KEY = bytes(range(32))
SETUP_SECRET = bytes(range(32, 64))


@dataclass(frozen=True, slots=True)
class BaseCredentialBundleFixture:
    schema: str
    system_id: str
    node_id: str
    broker_host: str
    broker_port: int
    broker_tls_server_name: str
    ca_pem: str
    mqtt_username: str
    mqtt_client_id: str
    credential_generation: int
    n3w_key_epoch: int
    mqtt_password: str
    n3w_application_key: str


def base_bundle() -> BaseCredentialBundleFixture:
    return BaseCredentialBundleFixture(
        schema="gh.pair.credentials/1",
        system_id=SYSTEM_ID,
        node_id="node_child01",
        broker_host="broker.local",
        broker_port=8883,
        broker_tls_server_name="broker.local",
        ca_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
        mqtt_username="node_child01",
        mqtt_client_id="gh-node_child01",
        credential_generation=7,
        n3w_key_epoch=4,
        mqtt_password="mqtt-secret",
        n3w_application_key="application-secret",
    )


def test_simplified_credentials_do_not_import_legacy_product_pairing() -> None:
    source = inspect.getsource(simplified_credentials)
    assert "n3w_product_pairing" not in source
    assert "ProductCredentialSource" in source
    assert "n3w_simple_pairing_crypto" in source
    assert "n3w_long_lived_peer_trust" in source


def test_v2_bundle_preserves_per_node_credentials_and_adds_peer_trust(tmp_path) -> None:
    with SystemPeerTrustStore(
        tmp_path / "peer.sqlite3",
        random_bytes=lambda _: PEER_KEY,
    ) as store:
        bundle = SimplifiedCredentialBundleIssuer(store).issue(base_bundle(), now=NOW)

    document = bundle.to_document()
    assert document["schema"] == "gh.pair.credentials/2"
    assert document["mqtt_username"] == "node_child01"
    assert document["mqtt_password"] == "mqtt-secret"
    assert document["n3w_application_key"] == "application-secret"
    assert document["n3w_key_epoch"] == 4
    assert document["peer_trust_generation"] == 1
    assert document["system_peer_key"] == "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
    assert "mqtt-secret" not in repr(bundle)
    assert "application-secret" not in repr(bundle)
    assert PEER_KEY.hex() not in repr(bundle)


def test_v2_bundle_encrypts_over_setup_secret_channel(tmp_path) -> None:
    transcript = PairingTranscript(
        pairing_id="pairing-20260816-01",
        hardware_id="ghw-c6-98a316a9f2f8",
        manager_id="manager-01",
        node_nonce=b"N" * 16,
        manager_nonce=b"M" * 16,
    )
    with SystemPeerTrustStore(
        tmp_path / "peer.sqlite3",
        random_bytes=lambda _: PEER_KEY,
    ) as store:
        bundle = SimplifiedCredentialBundleIssuer(store).issue(base_bundle(), now=NOW)
        ciphertext = encrypt_for_setup_secret(
            bundle,
            setup_secret=SETUP_SECRET,
            transcript=transcript,
            nonce=b"I" * 12,
        )

    plaintext = decrypt_credential_bundle(
        derive_bootstrap_key(SETUP_SECRET, transcript),
        transcript,
        nonce=b"I" * 12,
        ciphertext=ciphertext,
    )
    document = json.loads(plaintext)
    assert document == bundle.to_document()
