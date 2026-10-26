from __future__ import annotations

import base64
import ipaddress
import json
import uuid

import pytest

from greenhouse_manager.runtime.n3w_registration_bootstrap import (
    RegistrationBootstrapRejected,
    evaluate_confirm_skeleton,
)
from greenhouse_manager.runtime.n3w_registration_discovery import (
    REGISTRATION_PROTOCOL,
    RegistrationCandidate,
    RegistrationDiscoveryUDPServer,
    build_registration_mdns_definition,
    build_registration_udp_response,
)
from greenhouse_manager.runtime.n3w_trusted_product_lan import (
    TrustedProductLanError,
    TrustedProductLanState,
    parse_trusted_product_lan_document,
)
from greenhouse_manager.runtime.pairing_discovery import (
    DiscoveryRejected,
    SlidingWindowRateLimiter,
)


def _state(subnet: str = "192.0.2.0/24") -> TrustedProductLanState:
    return TrustedProductLanState(
        available=True,
        subnet=ipaddress.ip_network(subnet),
        reason="unique_ipv4_subnet",
        generation="a" * 64,
        published_at="2026-10-26T07:00:00Z",
    )


def _query() -> bytes:
    nonce = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode("ascii")
    return json.dumps(
        {
            "schema": "gh.discovery.query/1",
            "request_id": str(uuid.uuid4()),
            "nonce": nonce,
            "hardware_id": "ghw-c6-test-01",
            "protocols": [REGISTRATION_PROTOCOL],
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _candidate(_source: str) -> RegistrationCandidate:
    return RegistrationCandidate(
        manager_id="manager_lab_01",
        system_id="system_lab_01",
        system_id_hint="LAB01",
        host="192.0.2.10",
        bootstrap_tls_sha256="a" * 64,
    )


def _confirm() -> dict[str, str]:
    return {
        "schema": "gh.registration.confirm/1",
        "manager_id": "manager_lab_01",
        "system_id": "system_lab_01",
        "hardware_id": "ghw-c6-001122334455",
        "pairing_id": "12345678-1234-4234-8234-123456789abc",
        "setup_secret": "A" * 43,
    }


def test_trusted_product_lan_accepts_only_exact_ipv4_subnet() -> None:
    state = _state()
    assert state.authorizes("192.0.2.1") is True
    assert state.authorizes("192.0.2.254") is True
    assert state.authorizes("10.0.0.2") is False
    assert state.authorizes("127.0.0.1") is False
    assert state.authorizes("fe80::1") is False


@pytest.mark.parametrize(
    "document",
    [
        {
            "schema": "gh.trusted-product-lan/1",
            "interface": "eth0",
            "available": True,
            "subnet": "0.0.0.0/0",
            "reason": "unique_ipv4_subnet",
            "published_at": "2026-10-26T07:00:00Z",
            "generation": "a" * 64,
        },
        {
            "schema": "gh.trusted-product-lan/1",
            "interface": "lo",
            "available": True,
            "subnet": "192.0.2.0/24",
            "reason": "unique_ipv4_subnet",
            "published_at": "2026-10-26T07:00:00Z",
            "generation": "a" * 64,
        },
        {
            "schema": "gh.trusted-product-lan/1",
            "interface": "eth0",
            "available": False,
            "subnet": "192.0.2.0/24",
            "reason": "interface_not_connected",
            "published_at": "2026-10-26T07:00:00Z",
            "generation": "a" * 64,
        },
    ],
)
def test_trusted_product_lan_rejects_invalid_or_stale_shape(document) -> None:
    with pytest.raises(TrustedProductLanError):
        parse_trusted_product_lan_document(document)


def test_unavailable_state_is_fail_closed_without_subnet() -> None:
    state = parse_trusted_product_lan_document(
        {
            "schema": "gh.trusted-product-lan/1",
            "interface": "eth0",
            "available": False,
            "reason": "interface_not_connected",
            "published_at": "2026-10-26T07:00:00Z",
            "generation": "a" * 64,
        }
    )
    assert state.available is False
    assert state.subnet is None
    assert state.authorizes("192.0.2.20") is False


def test_registration_discovery_uses_exact_trusted_subnet_not_rfc1918() -> None:
    limiter = SlidingWindowRateLimiter(limit=4, window_s=60)
    response = json.loads(
        build_registration_udp_response(
            _query(),
            source_ip="192.0.2.20",
            candidate_for=_candidate,
            state_loader=_state,
            rate_limiter=limiter,
        ).decode("utf-8")
    )
    assert response["schema"] == "gh.registration.discovery-result/1"
    assert response["candidate"]["bootstrap_port"] == 47110
    assert response["candidate"]["bootstrap_path"] == "/v1/registration/confirm"
    assert response["candidate"]["protocol"] == REGISTRATION_PROTOCOL
    assert "setup_secret" not in json.dumps(response).lower()
    assert "pairing_id" not in json.dumps(response).lower()

    with pytest.raises(DiscoveryRejected, match="source_not_trusted_product_lan"):
        build_registration_udp_response(
            _query(),
            source_ip="10.0.0.20",
            candidate_for=_candidate,
            state_loader=_state,
            rate_limiter=limiter,
        )


def test_bootstrap_skeleton_is_trusted_subnet_gated_and_never_starts_transaction() -> None:
    result = evaluate_confirm_skeleton(
        _confirm(),
        source_ip="192.0.2.20",
        expected_manager_id="manager_lab_01",
        expected_system_id="system_lab_01",
        state_loader=_state,
    )
    assert result.status == "unavailable"
    assert result.reason == "first_registration_transaction_not_implemented"
    assert result.transaction_started is False
    assert "setup_secret" not in json.dumps(result.to_document()).lower()

    with pytest.raises(
        RegistrationBootstrapRejected,
        match="source_not_trusted_product_lan",
    ):
        evaluate_confirm_skeleton(
            _confirm(),
            source_ip="10.0.0.20",
            expected_manager_id="manager_lab_01",
            expected_system_id="system_lab_01",
            state_loader=_state,
        )


def test_bootstrap_skeleton_rejects_bad_setup_secret_shape() -> None:
    document = _confirm()
    document["setup_secret"] = "too-short"
    with pytest.raises(RegistrationBootstrapRejected, match="identity_invalid"):
        evaluate_confirm_skeleton(
            document,
            source_ip="192.0.2.20",
            expected_manager_id="manager_lab_01",
            expected_system_id="system_lab_01",
            state_loader=_state,
        )


def test_registration_udp_auto_host_must_remain_inside_trusted_subnet() -> None:
    server = RegistrationDiscoveryUDPServer(
        ("127.0.0.1", 0),
        candidate=RegistrationCandidate(
            manager_id="manager_lab_01",
            system_id="system_lab_01",
            system_id_hint="LAB01",
            host="auto",
            bootstrap_tls_sha256="a" * 64,
        ),
        state_loader=_state,
        advertised_host_resolver=lambda _source: "192.0.2.10",
    )
    try:
        assert server.candidate_for("192.0.2.20").host == "192.0.2.10"
        server.advertised_host_resolver = lambda _source: "10.0.0.10"
        with pytest.raises(
            DiscoveryRejected,
            match="outside trusted product LAN",
        ):
            server.candidate_for("192.0.2.20")
    finally:
        server.server_close()


def test_registration_mdns_definition_is_exact_interface_scoped() -> None:
    candidate = RegistrationCandidate(
        manager_id="manager_lab_01",
        system_id="system_lab_01",
        system_id_hint="LAB01",
        host="auto",
        bootstrap_tls_sha256="b" * 64,
    )
    definition = build_registration_mdns_definition(
        candidate,
        instance_name="n3w-registration-test",
        interface_ip="192.0.2.10",
        state_loader=_state,
    )
    assert definition.port == 47110
    assert definition.addresses == (bytes((192, 0, 2, 10)),)
    assert definition.server == "192.0.2.10."
    assert definition.properties["protocol"] == REGISTRATION_PROTOCOL
    assert definition.properties["bootstrap_tls_sha256"] == "b" * 64

    with pytest.raises(
        DiscoveryRejected,
        match="outside trusted product LAN",
    ):
        build_registration_mdns_definition(
            candidate,
            instance_name="n3w-registration-test",
            interface_ip="10.0.0.10",
            state_loader=_state,
        )


def test_r1_source_keeps_registration_runtime_isolated_from_manager_app() -> None:
    from greenhouse_manager.runtime import app as manager_app
    from greenhouse_manager.runtime import n3w_registration_runtime as registration_runtime

    app_source = manager_app.__file__
    runtime_source = registration_runtime.__file__
    assert app_source is not None
    assert runtime_source is not None
    assert "n3w_registration_runtime" not in open(
        app_source,
        encoding="utf-8",
    ).read()
    assert "first_registration_transaction_not_implemented" in open(
        __import__(
            "greenhouse_manager.runtime.n3w_registration_bootstrap",
            fromlist=["__file__"],
        ).__file__,
        encoding="utf-8",
    ).read()
