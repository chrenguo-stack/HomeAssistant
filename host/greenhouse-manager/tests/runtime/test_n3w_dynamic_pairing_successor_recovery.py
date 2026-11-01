from __future__ import annotations

import hashlib
import ipaddress
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialLifecycleStore,
)
from greenhouse_manager.runtime.n3w_dynamic_pairing_window import (
    DynamicPairingWindowController,
    DynamicPairingWindowControlServer,
    open_dynamic_pairing_window_over_socket,
    recover_expired_first_registration_over_socket,
)
from greenhouse_manager.runtime.registration import (
    RegistrationRegistry,
)

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
BROKER_IP = str(
    ipaddress.IPv4Address(
        0xC0A83201
    )
)
PEER_IP = str(
    ipaddress.IPv4Address(
        0xC0A8320A
    )
)


class FakeRuntime:
    def __init__(self) -> None:
        self.settings = type(
            "Settings",
            (),
            {"expiry_poll_s": 0.01},
        )()
        self.started = 0
        self.closed = 0

    def start(self) -> None:
        self.started += 1

    def expire(self) -> None:
        return None

    def close(self) -> None:
        self.closed += 1


class FakePairingSocket:
    def __init__(self) -> None:
        self.is_alive = False

    def start(self) -> None:
        self.is_alive = True

    def stop(self) -> None:
        self.is_alive = False


class FakeComposition:
    def __init__(self) -> None:
        self.pairing_runtime = FakeRuntime()
        self.pairing_socket = FakePairingSocket()

    def close(self) -> None:
        self.pairing_socket.stop()
        self.pairing_runtime.close()


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def _ca(root: Path) -> Path:
    path = root / "ca.pem"
    path.write_text(
        "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    return path


def _settings(root: Path) -> Settings:
    return Settings(
        system_id="lab",
        mqtt_host="127.0.0.1",
        mqtt_port=8883,
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
        n3w_pairing_manager_id="manager_lab_01",
        n3w_pairing_bind_host="127.0.0.1",
        n3w_pairing_advertised_host="auto",
        n3w_pairing_http_port=47112,
        n3w_pairing_udp_port=47111,
        n3w_provisioning_username="provisioner",
        n3w_provisioning_password="private-password",
        n3w_provisioning_client_id="provisioner-client",
        n3w_node_broker_host="gate-f-unbound.invalid",
        n3w_node_broker_port=8883,
        n3w_node_broker_tls_server_name="armbian",
        n3w_node_broker_ca_file=str(_ca(root)),
        pairing_db_path=str(root / "registration.sqlite3"),
        n3w_replay_db_path=str(root / "replay.sqlite3"),
        n3w_relay_authorization_db_path=str(
            root / "node-keys.sqlite3"
        ),
        n3w_relay_key_dir=str(root / "node-keys"),
        n3w_peer_trust_db_path=str(
            root / "peer-trust.sqlite3"
        ),
        n3w_credential_lifecycle_db_path=str(
            root / "credential-lifecycle.sqlite3"
        ),
        n3w_pairing_socket_path=str(root / "pairing.sock"),
    )


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": (
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0"
            "NTY3ODlhYmNkZWY"
        ),
        "capabilities": [
            "mqtt-runtime-credentials",
            "lcd-pairing-qr",
        ],
        "sent_at_ms": 120345,
    }


def _controller(
    root: Path,
) -> tuple[
    DynamicPairingWindowController,
    RegistrationRegistry,
]:
    settings = _settings(root)
    registration = RegistrationRegistry(
        settings.pairing_db_path,
        pending_ttl_s=1,
    )
    with CredentialLifecycleStore(
        settings.n3w_credential_lifecycle_db_path
    ):
        pass
    registration.observe_hello(
        _hello(),
        now=(
            datetime.now(UTC)
            - timedelta(seconds=5)
        ),
    )
    controller = DynamicPairingWindowController(
        settings,
        registration=registration,
        route_resolver=lambda peer: BROKER_IP,
        config_factory=lambda settings: object(),
        composition_factory=(
            lambda settings, config: FakeComposition()
        ),
    )
    return controller, registration


def test_closed_window_recovers_expired_first_registration(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    controller, registration = _controller(root)
    control_path = root / "pairing-control.sock"
    server = DynamicPairingWindowControlServer(
        controller,
        control_path,
    )
    server.start()
    hardware_sha = hashlib.sha256(
        HARDWARE_ID.encode()
    ).hexdigest()
    pairing_sha = hashlib.sha256(
        PAIRING_ID.encode()
    ).hexdigest()

    try:
        result = (
            recover_expired_first_registration_over_socket(
                control_path,
                hardware_id_sha256=hardware_sha,
                pairing_id_sha256=pairing_sha,
            )
        )
        assert result["accepted"] is True
        assert result[
            "current_registration_released"
        ] is True
        assert result[
            "replay_tombstone_preserved"
        ] is True
        assert result[
            "credential_history_absent"
        ] is True
        assert result["manager_recreated"] is False
        assert result["raw_identity_in_output"] is False
        assert registration.list_current() == ()

        replay = registration.observe_hello(
            _hello(),
            now=datetime.now(UTC),
        )
        assert replay.status == "rejected"
        assert replay.reason == "replay_detected"

        events = registration.list_events(
            hardware_id=HARDWARE_ID
        )
        assert events[0].event == (
            "expired_first_registration_abandoned"
        )
        assert events[0].reason == (
            "expired_first_pairing_recovery"
        )
        assert [
            event.event
            for event in events
        ].count("expired") == 1
    finally:
        server.stop()
        controller.stop()
        registration.close()


def test_active_window_blocks_expired_first_recovery(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    controller, registration = _controller(root)
    control_path = root / "pairing-control.sock"
    server = DynamicPairingWindowControlServer(
        controller,
        control_path,
    )
    server.start()

    try:
        opened = open_dynamic_pairing_window_over_socket(
            control_path,
            peer_ip=PEER_IP,
            window_seconds=180,
        )
        assert opened["accepted"] is True

        result = (
            recover_expired_first_registration_over_socket(
                control_path,
                hardware_id_sha256=(
                    hashlib.sha256(
                        HARDWARE_ID.encode()
                    ).hexdigest()
                ),
                pairing_id_sha256=(
                    hashlib.sha256(
                        PAIRING_ID.encode()
                    ).hexdigest()
                ),
            )
        )
        assert result["accepted"] is False
        assert result["code"] == (
            "pairing_recovery_requires_closed_window"
        )
        assert len(
            registration.list_current()
        ) == 1
    finally:
        if (
            controller.status()[
                "pairing_window_state"
            ]
            == "OPEN"
        ):
            controller.close_window()
        server.stop()
        controller.stop()
        registration.close()


def test_hash_mismatch_does_not_mutate_registration(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    controller, registration = _controller(root)
    control_path = root / "pairing-control.sock"
    server = DynamicPairingWindowControlServer(
        controller,
        control_path,
    )
    server.start()

    try:
        result = (
            recover_expired_first_registration_over_socket(
                control_path,
                hardware_id_sha256=("0" * 64),
                pairing_id_sha256=(
                    hashlib.sha256(
                        PAIRING_ID.encode()
                    ).hexdigest()
                ),
            )
        )
        assert result["accepted"] is False
        assert result["code"] == (
            "pairing_recovery_identity_not_unique"
        )
        assert len(
            registration.list_current()
        ) == 1
    finally:
        server.stop()
        controller.stop()
        registration.close()
