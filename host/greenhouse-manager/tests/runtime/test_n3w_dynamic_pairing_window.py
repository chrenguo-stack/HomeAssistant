from __future__ import annotations

import base64
import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.n3w_dynamic_pairing_window import (
    DynamicPairingWindowController,
    DynamicPairingWindowControlServer,
    DynamicPairingWindowError,
    close_dynamic_pairing_window_over_socket,
    dynamic_pairing_window_status_over_socket,
    open_dynamic_pairing_window_over_socket,
)
from greenhouse_manager.runtime.n3w_simplified_pairing_runtime import (
    SIMPLE_PAIRING_PROTOCOL,
)
from greenhouse_manager.runtime.n3w_simplified_product_runtime import (
    build_simplified_product_pairing_composition,
)

TEST_BROKER_IP = str(
    ipaddress.IPv4Address(
        0xC0A83201
    )
)
TEST_PEER_IP = str(
    ipaddress.IPv4Address(
        0xC0A8320A
    )
)
TEST_PEER_2_IP = str(
    ipaddress.IPv4Address(
        0xC0A8320B
    )
)


class FakeRuntime:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            expiry_poll_s=0.01
        )
        self.started = 0
        self.closed = 0
        self.expired = 0

    def start(self) -> None:
        self.started += 1

    def expire(self) -> None:
        self.expired += 1

    def close(self) -> None:
        self.closed += 1


class FakePairingSocket:
    def __init__(self) -> None:
        self.is_alive = False
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1
        self.is_alive = True

    def stop(self) -> None:
        self.stopped += 1
        self.is_alive = False


class FakeComposition:
    def __init__(self) -> None:
        self.pairing_runtime = FakeRuntime()
        self.pairing_socket = (
            FakePairingSocket()
        )
        self.closed = 0

    def close(self) -> None:
        if self.closed:
            return
        self.closed += 1
        self.pairing_socket.stop()
        self.pairing_runtime.close()


class FakeIdentityProvisioner:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def provision(self, plan, credentials) -> None:
        return None

    def deprovision(self, plan) -> None:
        return None


def _private_root(
    tmp_path: Path,
) -> Path:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def _ca_file(root: Path) -> Path:
    path = root / "ca.pem"
    path.write_text(
        (
            "-----BEGIN CERTIFICATE-----\n"
            "TEST\n"
            "-----END CERTIFICATE-----\n"
        ),
        encoding="utf-8",
    )
    return path


def _free_port(
    socket_type: int,
) -> int:
    with socket.socket(
        socket.AF_INET,
        socket_type,
    ) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(
            probe.getsockname()[1]
        )


def _settings(
    root: Path,
    *,
    http_port: int = 47112,
    udp_port: int = 47111,
) -> Settings:
    return Settings(
        system_id="lab",
        mqtt_host="127.0.0.1",
        mqtt_port=8883,
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
        n3w_pairing_manager_id="manager_lab_01",
        n3w_pairing_bind_host="127.0.0.1",
        n3w_pairing_advertised_host="auto",
        n3w_pairing_http_port=http_port,
        n3w_pairing_udp_port=udp_port,
        n3w_provisioning_username="provisioner",
        n3w_provisioning_password="private-password",
        n3w_provisioning_client_id="provisioner-client",
        n3w_node_broker_host=(
            "gate-f-unbound.invalid"
        ),
        n3w_node_broker_port=8883,
        n3w_node_broker_tls_server_name=(
            "armbian"
        ),
        n3w_node_broker_ca_file=str(
            _ca_file(root)
        ),
        pairing_db_path=str(
            root / "registration.sqlite3"
        ),
        n3w_replay_db_path=str(
            root / "replay.sqlite3"
        ),
        n3w_relay_authorization_db_path=str(
            root / "node-keys.sqlite3"
        ),
        n3w_relay_key_dir=str(
            root / "node-keys"
        ),
        n3w_peer_trust_db_path=str(
            root / "peer-trust.sqlite3"
        ),
        n3w_credential_lifecycle_db_path=str(
            root
            / "credential-lifecycle.sqlite3"
        ),
        n3w_pairing_socket_path=str(
            root / "pairing.sock"
        ),
    )


def _fake_controller(
    root: Path,
    *,
    minimum: int = 180,
    maximum: int = 600,
) -> tuple[
    DynamicPairingWindowController,
    list[FakeComposition],
]:
    compositions: list[
        FakeComposition
    ] = []

    def config_factory(
        settings: Settings,
    ) -> object:
        assert (
            settings.n3w_product_pairing_enabled
            is True
        )
        assert (
            settings.n3w_node_broker_host
            == TEST_BROKER_IP
        )
        return object()

    def composition_factory(
        settings: Settings,
        config: object,
    ) -> FakeComposition:
        assert config is not None
        composition = FakeComposition()
        compositions.append(
            composition
        )
        return composition

    return (
        DynamicPairingWindowController(
            _settings(root),
            route_resolver=(
                lambda peer: TEST_BROKER_IP
            ),
            config_factory=config_factory,
            composition_factory=(
                composition_factory
            ),
            min_window_seconds=minimum,
            max_window_seconds=maximum,
        ),
        compositions,
    )


def test_dynamic_window_defaults_closed_and_hides_locator(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, _ = _fake_controller(
        root
    )

    status = controller.status()

    assert (
        status["pairing_window_state"]
        == "CLOSED"
    )
    assert (
        status["broker_host_sha256"]
        is None
    )
    assert (
        status["raw_locator_in_output"]
        is False
    )
    assert TEST_BROKER_IP not in json.dumps(
        status
    )


def test_dynamic_window_rejects_invalid_peer_and_duration(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, _ = _fake_controller(
        root
    )

    with pytest.raises(
        DynamicPairingWindowError,
        match="pairing_window_peer_invalid",
    ):
        controller.open_window(
            peer_ip="203.0.113.10",
            window_seconds=300,
        )

    for duration in (
        179,
        601,
    ):
        with pytest.raises(
            DynamicPairingWindowError,
            match="pairing_window_seconds_invalid",
        ):
            controller.open_window(
                peer_ip=TEST_PEER_IP,
                window_seconds=duration,
            )


def test_dynamic_window_allows_only_one_open_and_manual_close(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, compositions = (
        _fake_controller(root)
    )

    opened = controller.open_window(
        peer_ip=TEST_PEER_IP,
        window_seconds=180,
    )

    assert (
        opened["pairing_window_state"]
        == "OPEN"
    )
    assert (
        opened["broker_host_sha256"]
        is not None
    )
    assert (
        compositions[0]
        .pairing_runtime
        .started
        == 1
    )
    assert (
        compositions[0]
        .pairing_socket
        .started
        == 1
    )

    with pytest.raises(
        DynamicPairingWindowError,
        match="pairing_window_already_active",
    ):
        controller.open_window(
            peer_ip=TEST_PEER_2_IP,
            window_seconds=180,
        )

    closed = controller.close_window()

    assert (
        closed["pairing_window_state"]
        == "CLOSED"
    )
    assert (
        closed["close_reason"]
        == "manual"
    )
    assert compositions[0].closed == 1


def test_dynamic_window_deadline_closes_without_external_watchdog(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, compositions = (
        _fake_controller(
            root,
            minimum=1,
            maximum=2,
        )
    )

    controller.open_window(
        peer_ip=TEST_PEER_IP,
        window_seconds=1,
    )

    deadline = time.monotonic() + 3
    while (
        controller.status()[
            "pairing_window_state"
        ]
        != "CLOSED"
        and time.monotonic() < deadline
    ):
        time.sleep(0.02)

    status = controller.status()

    assert (
        status["pairing_window_state"]
        == "CLOSED"
    )
    assert (
        status["close_reason"]
        == "deadline"
    )
    assert compositions[0].closed == 1


def test_manager_shutdown_closes_dynamic_window(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, compositions = (
        _fake_controller(root)
    )
    controller.open_window(
        peer_ip=TEST_PEER_IP,
        window_seconds=180,
    )

    controller.stop()

    assert (
        controller.status()[
            "pairing_window_state"
        ]
        == "CLOSED"
    )
    assert (
        controller.status()[
            "close_reason"
        ]
        == "manager_shutdown"
    )
    assert compositions[0].closed == 1


def test_control_socket_is_separate_and_duplicate_open_is_rejected(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    controller, _ = _fake_controller(
        root
    )
    control_path = (
        root / "pairing-control.sock"
    )
    server = (
        DynamicPairingWindowControlServer(
            controller,
            control_path,
        )
    )
    server.start()
    try:
        initial = (
            dynamic_pairing_window_status_over_socket(
                control_path
            )
        )
        assert initial["accepted"] is True
        assert (
            initial["pairing_window_state"]
            == "CLOSED"
        )

        opened = (
            open_dynamic_pairing_window_over_socket(
                control_path,
                peer_ip=TEST_PEER_IP,
                window_seconds=180,
            )
        )
        assert opened["accepted"] is True
        assert (
            opened["pairing_window_state"]
            == "OPEN"
        )

        rejected = (
            open_dynamic_pairing_window_over_socket(
                control_path,
                peer_ip=TEST_PEER_2_IP,
                window_seconds=180,
            )
        )
        assert rejected["accepted"] is False
        assert (
            rejected["code"]
            == "pairing_window_already_active"
        )

        closed = (
            close_dynamic_pairing_window_over_socket(
                control_path
            )
        )
        assert closed["accepted"] is True
        assert (
            closed["pairing_window_state"]
            == "CLOSED"
        )
    finally:
        server.stop()
        controller.stop()

    assert not control_path.exists()


def _real_composition_factory(
    settings: Settings,
    config,
):
    return (
        build_simplified_product_pairing_composition(
            settings,
            config,
            identity_provisioner_factory=(
                FakeIdentityProvisioner
            ),
        )
    )


def _discovery_query() -> bytes:
    nonce = (
        base64.urlsafe_b64encode(
            bytes([0x42]) * 32
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    return json.dumps(
        {
            "schema": (
                "gh.discovery.query/1"
            ),
            "request_id": str(
                uuid.uuid4()
            ),
            "nonce": nonce,
            "hardware_id": (
                "ghw-c6-00000000000a"
            ),
            "protocols": [
                SIMPLE_PAIRING_PROTOCOL
            ],
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_real_pairing_resources_open_and_disappear_on_close(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    http_port = _free_port(
        socket.SOCK_STREAM
    )
    udp_port = _free_port(
        socket.SOCK_DGRAM
    )
    settings = _settings(
        root,
        http_port=http_port,
        udp_port=udp_port,
    )
    controller = (
        DynamicPairingWindowController(
            settings,
            route_resolver=(
                lambda peer: (
                    TEST_BROKER_IP
                )
            ),
            composition_factory=(
                _real_composition_factory
            ),
        )
    )
    control_path = (
        root / "pairing-control.sock"
    )
    server = (
        DynamicPairingWindowControlServer(
            controller,
            control_path,
        )
    )
    server.start()

    try:
        opened = (
            open_dynamic_pairing_window_over_socket(
                control_path,
                peer_ip=TEST_PEER_IP,
                window_seconds=180,
            )
        )
        assert opened["accepted"] is True

        with urllib.request.urlopen(
            (
                "http://127.0.0.1:"
                f"{http_port}/healthz"
            ),
            timeout=2,
        ) as response:
            assert response.status == 200

        assert (
            root / "pairing.sock"
        ).is_socket()
        assert control_path.is_socket()

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as client:
            client.settimeout(2)
            client.sendto(
                _discovery_query(),
                ("127.0.0.1", udp_port),
            )
            response, _ = (
                client.recvfrom(4096)
            )
        discovery = json.loads(
            response.decode("utf-8")
        )
        assert (
            discovery["candidate"]["host"]
            == "127.0.0.1"
        )
        assert (
            discovery["candidate"]["port"]
            == http_port
        )

        closed = (
            close_dynamic_pairing_window_over_socket(
                control_path
            )
        )
        assert closed["accepted"] is True
        assert (
            closed["pairing_window_state"]
            == "CLOSED"
        )
        assert not (
            root / "pairing.sock"
        ).exists()

        with pytest.raises(
            (
                urllib.error.URLError,
                ConnectionError,
                TimeoutError,
            )
        ):
            urllib.request.urlopen(
                (
                    "http://127.0.0.1:"
                    f"{http_port}/healthz"
                ),
                timeout=0.5,
            )
    finally:
        server.stop()
        controller.stop()

    assert not control_path.exists()


def test_closed_controller_does_not_reopen_after_new_instance(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    first, _ = _fake_controller(
        root
    )
    first.open_window(
        peer_ip=TEST_PEER_IP,
        window_seconds=180,
    )
    first.stop()

    second, _ = _fake_controller(
        root
    )

    assert (
        second.status()[
            "pairing_window_state"
        ]
        == "CLOSED"
    )
    assert (
        second.status()[
            "broker_host_sha256"
        ]
        is None
    )
