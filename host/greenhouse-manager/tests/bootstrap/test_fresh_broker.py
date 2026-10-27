from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509

from greenhouse_manager.bootstrap.fresh_broker import (
    FreshBrokerBootstrapError,
    audit_fresh_dynsec_document,
    create_fresh_broker_materials,
    provision_fresh_service_identities,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute(self, commands):
        self.commands.extend(dict(command) for command in commands)
        return tuple(
            {"command": command["command"]}
            for command in commands
        )


def test_create_and_verify_fresh_broker_materials(tmp_path: Path) -> None:
    report = create_fresh_broker_materials(
        tmp_path / "broker",
        system_id="greenhouse-test",
        now=datetime(2026, 10, 11, tzinfo=UTC),
    )

    assert report.service_count == 3
    assert report.node_credential_count == 0
    assert report.dynsec_admin_secret_created is True
    assert report.secret_values_included is False
    assert report.production_service_start is False
    assert report.network_operation is False
    assert report.server_name == "mqtt.greenhouse.local"
    assert report.san_dns == ("mqtt.greenhouse.local", "armbian")
    assert report.san_ip == ("127.0.0.1",)

    root = tmp_path / "broker"
    assert root.stat().st_mode & 0o777 == 0o700
    for relative in (
        "tls/ca.key",
        "tls/ca.pem",
        "tls/server.key",
        "tls/server.pem",
        "tls/registration.key",
        "tls/registration.pem",
        "private/dynsec-admin-password",
        "manifest.json",
    ):
        assert (root / relative).stat().st_mode & 0o777 == 0o600

    ca = x509.load_pem_x509_certificate((root / "tls/ca.pem").read_bytes())
    server = x509.load_pem_x509_certificate((root / "tls/server.pem").read_bytes())
    assert ca.subject == ca.issuer
    assert server.issuer == ca.subject
    assert report.ca_sha256 != report.server_sha256

    passwords = {
        (root / "service-credentials" / service / "password")
        .read_text(encoding="utf-8")
        .strip()
        for service in ("manager", "provisioning", "homeassistant")
    }
    assert len(passwords) == 3


def test_create_rejects_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "broker"
    destination.mkdir()
    with pytest.raises(
        FreshBrokerBootstrapError,
        match="destination_already_exists",
    ):
        create_fresh_broker_materials(
            destination,
            system_id="greenhouse-test",
        )


def test_provision_fresh_service_identities_has_no_node_accounts(
    tmp_path: Path,
) -> None:
    create_fresh_broker_materials(
        tmp_path / "broker",
        system_id="greenhouse-test",
    )
    transport = RecordingTransport()

    report = provision_fresh_service_identities(
        transport,
        tmp_path / "broker" / "service-credentials",
        system_id="greenhouse-test",
    )

    assert report["service_count"] == 3
    assert report["node_credential_count"] == 0
    assert report["secret_values_included"] is False

    names = [command["command"] for command in transport.commands]
    assert names == [
        "setDefaultACLAccess",
        "createRole",
        "createClient",
        "createRole",
        "createClient",
        "createRole",
        "createClient",
    ]
    clients = [
        command
        for command in transport.commands
        if command["command"] == "createClient"
    ]
    assert len(clients) == 3
    assert all(not str(command["username"]).startswith("ghn_") for command in clients)
    assert len({str(command["password"]) for command in clients}) == 3


def test_dynsec_document_audit_accepts_exact_fresh_service_inventory(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dynamic-security.json"
    document = {
        "defaultACLAccess": {
            "publishClientSend": False,
            "publishClientReceive": False,
            "subscribe": False,
            "unsubscribe": True,
        },
        "clients": [
            {"username": "admin"},
            {"username": "ghs_greenhouse-test_provisioning"},
            {"username": "ghs_greenhouse-test_manager"},
            {"username": "ghs_greenhouse-test_homeassistant"},
        ],
        "roles": [
            {"rolename": "gh-service-greenhouse-test-provisioning"},
            {"rolename": "gh-service-greenhouse-test-manager"},
            {"rolename": "gh-service-greenhouse-test-homeassistant"},
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    os.chmod(path, 0o600)

    report = audit_fresh_dynsec_document(
        path,
        system_id="greenhouse-test",
    )

    assert report["status"] == "PASS"
    assert report["default_acl_exact"] is True
    assert report["service_client_count"] == 3
    assert report["node_client_count"] == 0


def test_dynsec_document_audit_rejects_precreated_node(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dynamic-security.json"
    document = {
        "defaultACLAccess": {
            "publishClientSend": False,
            "publishClientReceive": False,
            "subscribe": False,
            "unsubscribe": True,
        },
        "clients": [
            {"username": "admin"},
            {"username": "ghs_greenhouse-test_provisioning"},
            {"username": "ghs_greenhouse-test_manager"},
            {"username": "ghs_greenhouse-test_homeassistant"},
            {"username": "ghn_node-001"},
        ],
        "roles": [
            {"rolename": "gh-service-greenhouse-test-provisioning"},
            {"rolename": "gh-service-greenhouse-test-manager"},
            {"rolename": "gh-service-greenhouse-test-homeassistant"},
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    os.chmod(path, 0o600)

    with pytest.raises(
        FreshBrokerBootstrapError,
        match="dynsec_node_client_precreated",
    ):
        audit_fresh_dynsec_document(
            path,
            system_id="greenhouse-test",
        )


def test_registration_bootstrap_tls_is_dedicated_from_broker_leaf(tmp_path) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    root = tmp_path / "broker"
    create_fresh_broker_materials(
        root,
        system_id="greenhouse-test",
        now=NOW,
        random_bytes=FixedRandom(),
    )

    broker_cert = x509.load_pem_x509_certificate(
        (root / "tls/server.pem").read_bytes()
    )
    registration_cert = x509.load_pem_x509_certificate(
        (root / "tls/registration.pem").read_bytes()
    )
    broker_public = broker_cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    registration_public = (
        registration_cert.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    assert broker_public != registration_public
    assert registration_cert.subject == registration_cert.issuer
    assert (
        verify_fresh_broker_materials(root).secret_values_included
        is False
    )
