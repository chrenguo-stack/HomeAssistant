from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

import greenhouse_manager.runtime.n3w_manager_runtime_wiring as wiring
from greenhouse_manager.runtime.config import Settings


def _private_file(
    path: Path,
    value: str,
) -> Path:
    path.write_text(
        value,
        encoding="utf-8",
    )
    os.chmod(
        path,
        0o600,
    )
    return path


def test_settings_read_product_pairing_without_network(
    tmp_path,
    monkeypatch,
) -> None:
    password = _private_file(
        tmp_path / "provisioning-password",
        "private-provisioning-password\n",
    )

    ca = tmp_path / "node-ca.pem"
    ca.write_text(
        (
            "-----BEGIN CERTIFICATE-----\n"
            "TEST\n"
            "-----END CERTIFICATE-----\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GH_SYSTEM_ID",
        "lab",
    )
    monkeypatch.setenv(
        "GH_N3W_RUNTIME_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "GH_N3W_PRODUCT_PAIRING_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "GH_N3W_PAIRING_MANAGER_ID",
        "manager_lab_01",
    )
    monkeypatch.setenv(
        "GH_N3W_PAIRING_ADVERTISED_HOST",
        "192.0.2.10",
    )
    monkeypatch.setenv(
        "GH_N3W_PROVISIONING_USERNAME",
        "ghs_lab_provisioning",
    )
    monkeypatch.setenv(
        "GH_N3W_PROVISIONING_PASSWORD_FILE",
        str(password),
    )
    monkeypatch.setenv(
        "GH_N3W_PROVISIONING_CLIENT_ID",
        "gh-provisioning-lab",
    )
    monkeypatch.setenv(
        "GH_N3W_NODE_BROKER_HOST",
        "192.0.2.10",
    )
    monkeypatch.setenv(
        "GH_N3W_NODE_BROKER_TLS_SERVER_NAME",
        "mqtt.lab.local",
    )
    monkeypatch.setenv(
        "GH_N3W_NODE_BROKER_CA_FILE",
        str(ca),
    )
    monkeypatch.setenv(
        "GH_PAIRING_DB_PATH",
        str(
            tmp_path
            / "registration.sqlite3"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_REPLAY_DB_PATH",
        str(
            tmp_path
            / "replay.sqlite3"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_RELAY_AUTHORIZATION_DB_PATH",
        str(
            tmp_path
            / "node-keys.sqlite3"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_RELAY_KEY_DIR",
        str(
            tmp_path
            / "node-keys"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_PEER_TRUST_DB_PATH",
        str(
            tmp_path
            / "peer-trust.sqlite3"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH",
        str(
            tmp_path
            / "credential-lifecycle.sqlite3"
        ),
    )
    monkeypatch.setenv(
        "GH_N3W_SETUP_SECRET_INBOX_DIR",
        str(
            tmp_path
            / "setup-secret-inbox"
        ),
    )

    settings = Settings.from_env()

    assert (
        settings.n3w_product_pairing_enabled
        is True
    )

    assert (
        settings.n3w_provisioning_password
        == "private-provisioning-password"
    )

    assert (
        settings.n3w_pairing_manager_id
        == "manager_lab_01"
    )


def test_product_selector_uses_product_manager(
    monkeypatch,
) -> None:
    sentinel = object()

    monkeypatch.setattr(
        wiring,
        "build_n3w_simplified_product_manager_service",
        lambda settings: sentinel,
    )

    settings = Settings(
        system_id="lab",
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=True,
    )

    assert (
        wiring.build_manager_mqtt_service(
            settings
        )
        is sentinel
    )


class FakeRuntime:
    def __init__(self):
        self.settings = SimpleNamespace(
            expiry_poll_s=0.01
        )
        self.started = 0
        self.expired = 0
        self.closed = 0

    def start(self):
        self.started += 1

    def expire(self):
        self.expired += 1

    def close(self):
        self.closed += 1


class FakeInbox:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.is_alive = False

    def start(self):
        self.started += 1
        self.is_alive = True

    def stop(self):
        self.stopped += 1
        self.is_alive = False


class FakeComposition:
    def __init__(self):
        self.pairing_runtime = (
            FakeRuntime()
        )
        self.setup_secret_inbox = (
            FakeInbox()
        )
        self.closed = 0

    def close(self):
        self.closed += 1
        self.setup_secret_inbox.stop()
        self.pairing_runtime.close()


def test_product_pairing_worker_owns_lifecycle() -> None:
    composition = FakeComposition()

    worker = (
        wiring
        .N3wSimplifiedProductPairingWorker(
            composition
        )
    )

    worker.start()

    time.sleep(0.04)

    assert worker.is_alive is True
    assert (
        composition.pairing_runtime.started
        == 1
    )
    assert (
        composition.setup_secret_inbox.started
        == 1
    )

    worker.stop()

    assert worker.is_alive is False
    assert composition.closed == 1
    assert (
        composition.pairing_runtime.expired
        >= 1
    )
