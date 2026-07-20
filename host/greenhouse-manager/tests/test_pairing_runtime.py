from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.pairing_lab_cli import IsolatedLabProvisioner
from greenhouse_manager.pairing_runtime import (
    PairingRuntimeDisabled,
    assemble_pairing_runtime,
)
from greenhouse_manager.pairing_runtime_config import PairingRuntimeSettings


class FakeAdvertiser:
    def __init__(self, definition: Any) -> None:
        self.definition = definition
        self.started = False
        self.closed = False

    def start(self) -> None:
        if self.closed:
            raise RuntimeError("advertiser is closed")
        self.started = True

    def close(self) -> None:
        self.started = False
        self.closed = True


def write_ca(path: Path) -> None:
    path.write_text(
        "-----BEGIN CERTIFICATE-----\n"
        "VEVTVA==\n"
        "-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )


def test_settings(tmp_path: Path) -> PairingRuntimeSettings:
    ca_file = tmp_path / "ca.pem"
    write_ca(ca_file)
    return PairingRuntimeSettings(
        enabled=True,
        deployment_mode="isolated-lab",
        system_id="greenhouse",
        manager_id="manager-a",
        bind_host="127.0.0.1",
        http_port=0,
        udp_port=0,
        advertised_host="manager-a.local",
        advertised_ipv4="127.0.0.1",
        mdns_instance_name="manager-a",
        registration_db_path=str(tmp_path / "registration.sqlite3"),
        broker_host="mqtt.greenhouse.local",
        broker_port=8883,
        broker_tls_server_name="mqtt.greenhouse.local",
        broker_ca_file=str(ca_file),
        expiry_poll_s=0.1,
    )


def test_disabled_runtime_does_not_assemble() -> None:
    with pytest.raises(PairingRuntimeDisabled):
        assemble_pairing_runtime(
            PairingRuntimeSettings(),
            IsolatedLabProvisioner(),
        )


def test_runtime_starts_only_explicit_listeners_and_closes(
    tmp_path: Path,
) -> None:
    advertiser_holder: list[FakeAdvertiser] = []

    def make_advertiser(definition: Any) -> FakeAdvertiser:
        advertiser = FakeAdvertiser(definition)
        advertiser_holder.append(advertiser)
        return advertiser

    runtime = assemble_pairing_runtime(
        test_settings(tmp_path),
        IsolatedLabProvisioner(),
        advertiser_factory=make_advertiser,
    )
    before = runtime.snapshot()
    assert before.started is False
    assert before.secret_values_included is False

    started = runtime.start()
    assert started.started is True
    assert started.http_address is not None
    assert started.udp_address is not None
    assert started.http_address[1] > 0
    assert started.udp_address[1] > 0
    assert advertiser_holder[0].started is True

    with urllib.request.urlopen(
        f"http://127.0.0.1:{started.http_address[1]}/healthz",
        timeout=2,
    ) as response:
        document = json.loads(response.read())
    assert document == {"schema": "gh.pair.health/1", "status": "ok"}

    closed = runtime.close()
    assert closed.closed is True
    assert closed.started is False
    assert advertiser_holder[0].closed is True
    assert runtime.close() == closed


def test_qr_import_requires_started_runtime(tmp_path: Path) -> None:
    runtime = assemble_pairing_runtime(
        test_settings(tmp_path),
        IsolatedLabProvisioner(),
        advertiser_factory=FakeAdvertiser,
    )
    try:
        with pytest.raises(
            RuntimeError,
            match="must be started before QR import",
        ):
            runtime.import_scanned_pairing(
                "ghw-c6-98a316a9f2f8",
                "416ccfd2-5a5b-46e0-84d1-44c4067dbde0",
                pairing_secret=(
                    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
                ),
            )
    finally:
        runtime.close()
