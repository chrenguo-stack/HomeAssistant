from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path

import pytest

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
)
from greenhouse_manager.runtime.n3w_simplified_product_runtime import (
    PrivateSetupSecretInbox,
    SimplifiedProductCompositionConfig,
    build_simplified_product_pairing_composition,
)
from greenhouse_manager.runtime.registration import (
    RegistrationRegistry,
)

HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SETUP_SECRET = bytes(range(32))


def b64(value: bytes) -> str:
    return (
        base64.urlsafe_b64encode(value)
        .rstrip(b"=")
        .decode("ascii")
    )


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": b64(
            bytes([0x31]) * 32
        ),
        "capabilities": [
            "simple-setup-secret"
        ],
        "sent_at_ms": 1,
    }


class FakeIdentityProvisioner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

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


def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def make_settings(root: Path) -> Settings:
    return Settings(
        system_id="lab",
        mqtt_host="mosquitto",
        mqtt_port=1883,
        n3w_runtime_enabled=True,
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
    )


def make_config(
    root: Path,
) -> SimplifiedProductCompositionConfig:
    return SimplifiedProductCompositionConfig(
        manager_id="manager_lab_01",
        advertised_host="192.0.2.10",
        provisioning_username=(
            "ghs_lab_provisioning"
        ),
        provisioning_password=(
            "private-test-password"
        ),
        provisioning_client_id=(
            "gh-provisioning-lab"
        ),
        node_broker_host="192.0.2.10",
        node_broker_port=8883,
        node_broker_tls_server_name=(
            "mqtt.lab.local"
        ),
        node_ca_pem="",
        peer_trust_db_path=str(
            root
            / "peer-trust.sqlite3"
        ),
        credential_lifecycle_db_path=str(
            root
            / "credential-lifecycle.sqlite3"
        ),
        setup_secret_inbox_dir=str(
            root
            / "setup-secret-inbox"
        ),
    )


def test_product_pairing_composition_is_source_only_and_grant_free(
    tmp_path,
) -> None:
    root = private_root(tmp_path)

    composition = (
        build_simplified_product_pairing_composition(
            make_settings(root),
            make_config(root),
            identity_provisioner_factory=(
                FakeIdentityProvisioner
            ),
            pairing_runtime_factory=(
                fake_pairing_runtime_factory
            ),
        )
    )

    try:
        assert (
            composition.pairing_runtime.closed
            is False
        )

        with sqlite3.connect(
            root
            / "node-keys.sqlite3"
        ) as connection:
            names = {
                row[0]
                for row
                in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type='table'
                    """
                ).fetchall()
            }

        assert (
            "n3w_relay_gateway_nodes"
            not in names
        )

        assert (
            composition
            .peer_trust
            .audit()[
                "normal_get_rotates"
            ]
            is False
        )

        assert (
            composition
            .setup_secret_inbox
            .is_alive
            is False
        )

        for path in (
            root
            / "registration.sqlite3",
            root
            / "node-keys.sqlite3",
            root
            / "peer-trust.sqlite3",
            root
            / "credential-lifecycle.sqlite3",
        ):
            assert (
                path.stat().st_mode
                & 0o777
                == 0o600
            )

        assert (
            (
                root
                / "setup-secret-inbox"
            ).stat().st_mode
            & 0o777
            == 0o700
        )
    finally:
        composition.close()

    assert (
        composition
        .pairing_runtime
        .closed
        is True
    )


class CaptureCoordinator:
    def __init__(self):
        self.calls = []

    def import_setup_secret(
        self,
        hardware_id,
        pairing_id,
        *,
        setup_secret,
    ):
        self.calls.append(
            (
                hardware_id,
                pairing_id,
                setup_secret,
            )
        )


def test_private_setup_secret_inbox_consumes_mode_0600_handoff(
    tmp_path,
) -> None:
    root = private_root(tmp_path)
    coordinator = CaptureCoordinator()

    inbox = PrivateSetupSecretInbox(
        coordinator,
        root / "inbox",
    )

    path = (
        root
        / "inbox"
        / (
            "handoff-"
            "0123456789abcdef"
            "0123456789abcdef"
            ".json"
        )
    )

    path.write_text(
        json.dumps(
            {
                "schema": (
                    "gh.pair."
                    "setup-secret-import/1"
                ),
                "hardware_id": (
                    HARDWARE_ID
                ),
                "pairing_id": (
                    PAIRING_ID
                ),
                "setup_secret": b64(
                    SETUP_SECRET
                ),
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    os.chmod(path, 0o600)

    result = inbox.process_once()

    assert result == {
        "accepted": 1,
        "rejected": 0,
    }

    assert not path.exists()

    assert coordinator.calls == [
        (
            HARDWARE_ID,
            PAIRING_ID,
            SETUP_SECRET,
        )
    ]


def test_private_setup_secret_inbox_rejects_non_private_file(
    tmp_path,
) -> None:
    root = private_root(tmp_path)
    coordinator = CaptureCoordinator()

    inbox = PrivateSetupSecretInbox(
        coordinator,
        root / "inbox",
    )

    path = (
        root
        / "inbox"
        / (
            "handoff-"
            "abcdef0123456789"
            "abcdef0123456789"
            ".json"
        )
    )

    path.write_text(
        "{}",
        encoding="utf-8",
    )

    os.chmod(path, 0o644)

    result = inbox.process_once()

    assert result == {
        "accepted": 0,
        "rejected": 1,
    }

    assert coordinator.calls == []
    assert not path.exists()


def test_setup_secret_import_is_idempotent_but_conflict_fails(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "registration.sqlite3"
    )

    with RegistrationRegistry(
        database
    ) as registry:
        registry.observe_hello(
            hello()
        )

        coordinator = (
            SimplifiedPairingCoordinator(
                registry,
                object(),
                manager_id=(
                    "manager_lab_01"
                ),
            )
        )

        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )

        coordinator.import_setup_secret(
            HARDWARE_ID,
            PAIRING_ID,
            setup_secret=SETUP_SECRET,
        )

        with pytest.raises(
            SimplifiedPairingConflict,
            match=(
                "setup_secret_"
                "conflicting_import"
            ),
        ):
            coordinator.import_setup_secret(
                HARDWARE_ID,
                PAIRING_ID,
                setup_secret=(
                    bytes([0xFF]) * 32
                ),
            )
