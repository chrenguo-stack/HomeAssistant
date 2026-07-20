from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager.pairing_runtime_config import (
    FROZEN_PAIRING_HTTP_PORT,
    FROZEN_PAIRING_UDP_PORT,
    PairingRuntimeSettings,
)

PAIRING_ENV = (
    "GH_PAIRING_SERVICE_ENABLED",
    "GH_PAIRING_DEPLOYMENT_MODE",
    "GH_SYSTEM_ID",
    "GH_PAIRING_MANAGER_ID",
    "GH_PAIRING_BIND_HOST",
    "GH_PAIRING_HTTP_PORT",
    "GH_PAIRING_UDP_PORT",
    "GH_PAIRING_ADVERTISED_HOST",
    "GH_PAIRING_ADVERTISED_IPV4",
    "GH_PAIRING_MDNS_INSTANCE",
    "GH_PAIRING_PATH",
    "GH_PAIRING_PRIORITY",
    "GH_PAIRING_CANDIDATE_TTL_S",
    "GH_PAIRING_DB_PATH",
    "GH_PAIRING_PENDING_TTL_S",
    "GH_PAIRING_SESSION_TTL_S",
    "GH_PAIRING_MAX_PROOF_ATTEMPTS",
    "GH_PAIRING_BROKER_HOST",
    "GH_PAIRING_BROKER_PORT",
    "GH_PAIRING_BROKER_TLS_SERVER_NAME",
    "GH_PAIRING_BROKER_CA_FILE",
    "GH_PAIRING_EXPIRY_POLL_S",
)


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PAIRING_ENV:
        monkeypatch.delenv(name, raising=False)


def write_ca(path: Path) -> None:
    path.write_text(
        "-----BEGIN CERTIFICATE-----\n"
        "VEVTVA==\n"
        "-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )


def enabled_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    clear_env(monkeypatch)
    ca_file = tmp_path / "pairing-ca.pem"
    write_ca(ca_file)
    values = {
        "GH_PAIRING_SERVICE_ENABLED": "true",
        "GH_PAIRING_DEPLOYMENT_MODE": "isolated-lab",
        "GH_SYSTEM_ID": "greenhouse",
        "GH_PAIRING_MANAGER_ID": "manager-a",
        "GH_PAIRING_BIND_HOST": "127.0.0.1",
        "GH_PAIRING_HTTP_PORT": str(FROZEN_PAIRING_HTTP_PORT),
        "GH_PAIRING_UDP_PORT": str(FROZEN_PAIRING_UDP_PORT),
        "GH_PAIRING_ADVERTISED_HOST": "manager-a.local",
        "GH_PAIRING_ADVERTISED_IPV4": "127.0.0.1",
        "GH_PAIRING_MDNS_INSTANCE": "manager-a",
        "GH_PAIRING_DB_PATH": str(tmp_path / "registration.sqlite3"),
        "GH_PAIRING_BROKER_HOST": "mqtt.greenhouse.local",
        "GH_PAIRING_BROKER_PORT": "8883",
        "GH_PAIRING_BROKER_TLS_SERVER_NAME": "mqtt.greenhouse.local",
        "GH_PAIRING_BROKER_CA_FILE": str(ca_file),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return ca_file


def test_disabled_default_requires_no_pairing_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_env(monkeypatch)
    settings = PairingRuntimeSettings.from_env()
    assert settings.enabled is False
    assert settings.report() == {
        "schema": "gh.pair.runtime-config/1",
        "configuration_valid": True,
        "pairing_service_enabled": False,
        "deployment_mode": "disabled",
        "network_attempted": False,
        "listener_count": 0,
        "listeners": [],
        "mdns_enabled": False,
        "default_manager_runtime_modified": False,
        "secret_values_included": False,
        "ca_file_configured": False,
    }


def test_enabled_configuration_freezes_ports_and_redacts_ca_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ca_file = enabled_env(monkeypatch, tmp_path)
    settings = PairingRuntimeSettings.from_env()
    report = settings.report()

    assert settings.enabled is True
    assert settings.http_port == FROZEN_PAIRING_HTTP_PORT
    assert settings.udp_port == FROZEN_PAIRING_UDP_PORT
    assert settings.read_broker_ca_pem().startswith(
        "-----BEGIN CERTIFICATE-----"
    )
    assert report["listener_count"] == 2
    assert report["secret_values_included"] is False
    assert str(ca_file) not in json.dumps(report)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "GH_PAIRING_DEPLOYMENT_MODE",
            "production",
            "must be isolated-lab",
        ),
        (
            "GH_PAIRING_HTTP_PORT",
            "47112",
            "ports are frozen",
        ),
        (
            "GH_PAIRING_ADVERTISED_HOST",
            "manager.example.com",
            "must be a .local hostname",
        ),
        (
            "GH_PAIRING_ADVERTISED_IPV4",
            "8.8.8.8",
            "must be a local IPv4 address",
        ),
        (
            "GH_PAIRING_PATH",
            "/other",
            "frozen at /v1/pairing",
        ),
    ],
)
def test_enabled_configuration_rejects_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
    value: str,
    message: str,
) -> None:
    enabled_env(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        PairingRuntimeSettings.from_env()


def test_enabled_configuration_rejects_symlink_ca(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ca_file = enabled_env(monkeypatch, tmp_path)
    link = tmp_path / "ca-link.pem"
    link.symlink_to(ca_file)
    monkeypatch.setenv("GH_PAIRING_BROKER_CA_FILE", str(link))
    with pytest.raises(ValueError, match="regular non-symlink"):
        PairingRuntimeSettings.from_env()
