from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialState,
)
from greenhouse_manager.runtime.n3w_node_application_keys import (
    SqliteNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
    decrypt_credential_bundle,
    derive_bootstrap_key,
    verify_setup_proof,
)
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingState,
)
from greenhouse_manager.runtime.n3w_simplified_product_runtime import (
    build_simplified_product_config_from_settings,
    build_simplified_product_pairing_composition,
)
from greenhouse_manager.runtime.registration import (
    NodeIdLeaseState,
    RegistrationState,
)

HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = (
    "c83aeb0d-8f48-4a39-a34b-"
    "ea584a588475"
)
SETUP_SECRET = bytes(range(32))


def b64(value: bytes) -> str:
    return (
        base64.urlsafe_b64encode(value)
        .rstrip(b"=")
        .decode("ascii")
    )


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(
        value
        + "="
        * ((4 - len(value) % 4) % 4)
    )


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "fc4-product",
        "node_nonce": b64(
            bytes([0x31]) * 32
        ),
        "capabilities": [
            "simple-setup-secret"
        ],
        "sent_at_ms": 1,
    }


class FakeIdentityProvisioner:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.__class__.instances.append(
            self
        )

    def provision(
        self,
        plan,
        credentials,
    ):
        self.calls.append(
            (
                "provision",
                plan,
                credentials,
            )
        )

    def deprovision(
        self,
        plan,
    ):
        self.calls.append(
            (
                "deprovision",
                plan,
            )
        )


class FakePairingRuntime:
    def __init__(
        self,
        settings,
        coordinator,
    ):
        self.settings = settings
        self.coordinator = coordinator
        self.closed = False

    def close(self):
        self.closed = True


def fake_pairing_runtime_factory(
    settings,
    coordinator,
):
    return FakePairingRuntime(
        settings,
        coordinator,
    )


def make_private_root(
    tmp_path: Path,
) -> Path:
    root = tmp_path / "private"
    root.mkdir(
        mode=0o700
    )
    os.chmod(
        root,
        0o700
    )
    return root


def make_settings(
    root: Path,
) -> Settings:
    ca = root / "node-ca.pem"
    ca.write_text(
        (
            "-----BEGIN CERTIFICATE-----\n"
            "TEST\n"
            "-----END CERTIFICATE-----\n"
        ),
        encoding="utf-8",
    )

    return Settings(
        system_id="lab",
        mqtt_host="mosquitto",
        mqtt_port=1883,
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=True,
        pairing_db_path=str(
            root
            / "registration.sqlite3"
        ),
        n3w_replay_db_path=str(
            root
            / "replay.sqlite3"
        ),
        n3w_relay_authorization_db_path=str(
            root
            / "node-keys.sqlite3"
        ),
        n3w_relay_key_dir=str(
            root
            / "node-keys"
        ),
        n3w_pairing_manager_id=(
            "manager_lab_01"
        ),
        n3w_pairing_bind_host=(
            "127.0.0.1"
        ),
        n3w_pairing_advertised_host=(
            "192.0.2.10"
        ),
        n3w_provisioning_username=(
            "ghs_lab_provisioning"
        ),
        n3w_provisioning_password=(
            "private-test-password"
        ),
        n3w_provisioning_client_id=(
            "gh-provisioning-lab"
        ),
        n3w_node_broker_host=(
            "192.0.2.10"
        ),
        n3w_node_broker_port=8883,
        n3w_node_broker_tls_server_name=(
            "mqtt.lab.local"
        ),
        n3w_node_broker_ca_file=str(
            ca
        ),
        n3w_peer_trust_db_path=str(
            root
            / "peer-trust.sqlite3"
        ),
        n3w_credential_lifecycle_db_path=str(
            root
            / "credential-lifecycle.sqlite3"
        ),
        n3w_pairing_socket_path=str(root / "pairing.sock"),
    )


def test_first_registration_product_closure(
    tmp_path,
) -> None:
    root = make_private_root(
        tmp_path
    )

    settings = make_settings(
        root
    )

    config = (
        build_simplified_product_config_from_settings(
            settings
        )
    )

    FakeIdentityProvisioner.instances.clear()

    composition = (
        build_simplified_product_pairing_composition(
            settings,
            config,
            identity_provisioner_factory=(
                FakeIdentityProvisioner
            ),
            pairing_runtime_factory=(
                fake_pairing_runtime_factory
            ),
        )
    )

    try:
        observed = (
            composition
            .registry
            .observe_hello(
                hello()
            )
        )

        assert (
            observed.status
            == "created"
        )

        composition.coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )

        node_nonce = (
            bytes([0x21]) * 16
        )

        offer = (
            composition
            .coordinator
            .begin(
                HARDWARE_ID,
                PAIRING_ID,
                node_nonce=b64(
                    node_nonce
                ),
            )
        )

        transcript = PairingTranscript(
            pairing_id=PAIRING_ID,
            hardware_id=HARDWARE_ID,
            manager_id=offer.manager_id,
            node_nonce=node_nonce,
            manager_nonce=unb64(
                offer.manager_nonce
            ),
        )

        assert verify_setup_proof(
            SETUP_SECRET,
            transcript,
            role="manager",
            proof=unb64(
                offer.manager_proof
            ),
        )

        node_proof = build_setup_proof(
            SETUP_SECRET,
            transcript,
            role="node",
        )

        encrypted = (
            composition
            .coordinator
            .establish(
                offer.session_id,
                node_proof=b64(
                    node_proof
                ),
            )
        )

        plaintext = decrypt_credential_bundle(
            derive_bootstrap_key(
                SETUP_SECRET,
                transcript,
            ),
            transcript,
            nonce=unb64(
                encrypted.nonce
            ),
            ciphertext=unb64(
                encrypted.ciphertext
            ),
        )

        bundle = json.loads(
            plaintext.decode(
                "utf-8"
            )
        )

        assert (
            bundle["schema"]
            == "gh.pair.credentials/2"
        )

        assert (
            bundle["node_id"]
            == encrypted.node_id
        )

        assert (
            bundle["system_id"]
            == "lab"
        )

        assert (
            bundle[
                "mqtt_username"
            ].startswith(
                "ghn_"
            )
        )

        assert (
            bundle[
                "system_peer_key"
            ]
        )

        snapshot = (
            composition
            .coordinator
            .acknowledge(
                offer.session_id,
                delivery_digest=(
                    encrypted
                    .delivery_digest
                ),
            )
        )

        assert (
            snapshot.state
            is SimplifiedPairingState.CONSUMED
        )

        registration = (
            composition
            .registry
            .get(
                HARDWARE_ID
            )
        )

        assert (
            registration.state
            is RegistrationState.APPROVED
        )

        assert (
            registration.node_id
            == encrypted.node_id
        )

        assert (
            composition
            .registry
            .node_id_lease_state(
                encrypted.node_id
            )
            is NodeIdLeaseState.ACTIVE
        )

        lifecycle = (
            composition
            .credential_store
            .get(
                HARDWARE_ID
            )
        )

        assert (
            lifecycle.state
            is CredentialState.ACTIVE
        )

        assert (
            lifecycle.node_id
            == encrypted.node_id
        )

        application_key = unb64(
            bundle[
                "n3w_application_key"
            ]
        )

        with SqliteNodeApplicationKeyProvider(
            settings
            .n3w_relay_authorization_db_path,
            settings
            .n3w_relay_key_dir,
        ) as provider:
            assert (
                provider.resolve_key(
                    node_id=(
                        encrypted.node_id
                    ),
                    key_epoch=(
                        bundle[
                            "n3w_key_epoch"
                        ]
                    ),
                )
                == application_key
            )

        peer = (
            composition
            .peer_trust
            .get(
                "lab"
            )
        )

        assert (
            b64(
                peer.key
            )
            == bundle[
                "system_peer_key"
            ]
        )

        identity = (
            FakeIdentityProvisioner
            .instances[-1]
        )

        assert [
            call[0]
            for call
            in identity.calls
        ] == [
            "provision"
        ]

    finally:
        composition.close()
