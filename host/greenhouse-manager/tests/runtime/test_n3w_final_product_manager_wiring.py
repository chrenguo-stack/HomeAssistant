from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        "auto",
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

    # Legacy LAB filesystem-inbox environment must not become part
    # of final product Settings.
    assert not hasattr(
        settings,
        "n3w_setup_secret_inbox_dir",
    )


def _product_pairing_settings(
    tmp_path: Path,
    advertised_host: str,
) -> Settings:
    ca = tmp_path / (
        "node-ca-"
        + advertised_host.replace(".", "-")
        + ".pem"
    )
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
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=True,
        n3w_pairing_manager_id="manager_lab_01",
        n3w_pairing_advertised_host=advertised_host,
        n3w_provisioning_username="provisioner",
        n3w_provisioning_password="private-password",
        n3w_provisioning_client_id="provisioner-client",
        n3w_node_broker_ca_file=str(ca),
    )


@pytest.mark.parametrize(
    "advertised_host",
    [
        "auto",
        "greenhouse-manager.local",
    ],
)
def test_product_pairing_accepts_portable_advertised_host(
    tmp_path,
    advertised_host,
) -> None:
    settings = _product_pairing_settings(
        tmp_path,
        advertised_host,
    )

    settings.validate()


@pytest.mark.parametrize(
    "advertised_host",
    [
        "192.0.2.10",
        "::1",
        "2001:db8::10",
    ],
)
def test_product_pairing_rejects_durable_ip_advertised_host(
    tmp_path,
    advertised_host,
) -> None:
    settings = _product_pairing_settings(
        tmp_path,
        advertised_host,
    )

    with pytest.raises(
        ValueError,
        match=(
            "GH_N3W_PAIRING_ADVERTISED_HOST "
            "must be auto or a hostname"
        ),
    ):
        settings.validate()


def test_pairing_disabled_selector_uses_dynamic_manager(
    monkeypatch,
) -> None:
    sentinel = object()

    monkeypatch.setattr(
        wiring,
        "build_n3w_simplified_manager_service",
        lambda settings: sentinel,
    )

    settings = Settings(
        system_id="lab",
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
    )

    assert (
        wiring.build_manager_mqtt_service(
            settings
        )
        is sentinel
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


def test_dynamic_pairing_close_does_not_stop_normal_manager_runtime(
    monkeypatch,
) -> None:
    parent_entered = threading.Event()
    release_parent = threading.Event()

    class FakeControl:
        def __init__(self) -> None:
            self.started = 0
            self.stopped = 0

        def start(self) -> None:
            self.started += 1

        def stop(self) -> None:
            self.stopped += 1

    class FakeDynamic:
        def __init__(self) -> None:
            self.closed = 0
            self.stopped = 0

        def close_window(self) -> None:
            self.closed += 1

        def stop(self) -> None:
            self.stopped += 1

    def parent_run(self) -> None:
        parent_entered.set()
        assert release_parent.wait(2)

    monkeypatch.setattr(
        wiring.N3wSimplifiedManagerMqttService,
        "run",
        parent_run,
    )

    service = object.__new__(
        wiring.N3wDynamicPairingManagerMqttService
    )
    control = FakeControl()
    dynamic = FakeDynamic()
    service._pairing_control = control
    service._dynamic_pairing = dynamic

    thread = threading.Thread(
        target=service.run,
        daemon=True,
    )
    thread.start()

    assert parent_entered.wait(2)
    assert thread.is_alive()
    assert control.started == 1

    dynamic.close_window()

    assert dynamic.closed == 1
    assert thread.is_alive()
    assert control.stopped == 0
    assert dynamic.stopped == 0

    release_parent.set()
    thread.join(2)

    assert thread.is_alive() is False
    assert control.stopped == 1
    assert dynamic.stopped == 1


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
        self.pairing_socket = (
            FakeInbox()
        )
        self.closed = 0

    def close(self):
        self.closed += 1
        self.pairing_socket.stop()
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
        composition.pairing_socket.started
        == 1
    )

    worker.stop()

    assert worker.is_alive is False
    assert composition.closed == 1
    assert (
        composition.pairing_runtime.expired
        >= 1
    )
