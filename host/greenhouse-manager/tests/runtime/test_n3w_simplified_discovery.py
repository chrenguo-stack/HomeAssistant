from __future__ import annotations

import base64
import json
import socket
import threading
import uuid

import pytest

from greenhouse_manager.runtime.n3w_simplified_discovery import (
    SIMPLE_PAIRING_PROTOCOL,
    SimplifiedManagerCandidate,
    SimplifiedPairingUDPServer,
    build_simplified_udp_discovery_response,
)
from greenhouse_manager.runtime.pairing_discovery import (
    DiscoveryRateLimited,
    DiscoveryRejected,
    SlidingWindowRateLimiter,
)


def _candidate(
    host: str,
) -> SimplifiedManagerCandidate:
    return SimplifiedManagerCandidate(
        schema="gh.manager.candidate/1",
        manager_id="manager_lab_01",
        system_id="lab",
        host=host,
        scheme="http",
        port=47112,
    )


def _query() -> bytes:
    nonce = (
        base64.urlsafe_b64encode(
            bytes(range(32))
        )
        .rstrip(b"=")
        .decode("ascii")
    )

    return json.dumps(
        {
            "schema": "gh.discovery.query/1",
            "request_id": str(uuid.uuid4()),
            "nonce": nonce,
            "hardware_id": "ghw-c6-test-01",
            "protocols": [
                SIMPLE_PAIRING_PROTOCOL
            ],
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_explicit_host_candidate_is_unchanged() -> None:
    candidate = _candidate(
        "greenhouse-manager.local"
    )
    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=candidate,
        advertised_host_resolver=lambda source: (
            "192.168.1.10"
        ),
    )

    try:
        assert (
            server.candidate_for(
                "192.168.1.20"
            )
            is candidate
        )
    finally:
        server.server_close()


def test_auto_host_is_resolved_per_request_without_cache() -> None:
    observed = []

    def resolver(source_ip: str) -> str:
        observed.append(source_ip)
        return {
            "192.168.1.20": "192.168.1.2",
            "10.10.0.20": "10.10.0.2",
        }[source_ip]

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=resolver,
    )

    try:
        first = server.candidate_for(
            "192.168.1.20"
        )
        second = server.candidate_for(
            "10.10.0.20"
        )
    finally:
        server.server_close()

    assert first.host == "192.168.1.2"
    assert second.host == "10.10.0.2"
    assert observed == [
        "192.168.1.20",
        "10.10.0.20",
    ]


@pytest.mark.parametrize(
    ("source_ip", "selected_ip"),
    [
        ("192.168.1.20", "0.0.0.0"),
        ("192.168.1.20", "224.0.0.1"),
        ("192.168.1.20", "127.0.0.1"),
        ("192.168.1.20", "not-an-ip"),
    ],
)
def test_auto_host_rejects_invalid_route_selection(
    source_ip,
    selected_ip,
) -> None:
    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=lambda source: (
            selected_ip
        ),
    )

    try:
        with pytest.raises(
            DiscoveryRejected,
            match="dynamic advertised host",
        ):
            server.candidate_for(source_ip)
    finally:
        server.server_close()


def test_auto_host_resolver_failure_sends_no_response() -> None:
    def fail_resolver(source_ip: str) -> str:
        raise OSError("route unavailable")

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=fail_resolver,
    )

    client = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )
    client.settimeout(0.2)

    worker = threading.Thread(
        target=server.handle_request,
        daemon=True,
    )

    try:
        worker.start()
        client.sendto(
            _query(),
            server.server_address,
        )

        with pytest.raises(
            TimeoutError
        ):
            client.recvfrom(4096)

        worker.join(timeout=1)
        assert worker.is_alive() is False
    finally:
        client.close()
        server.server_close()


def test_response_keeps_request_binding_and_dynamic_host() -> None:
    payload = _query()
    request = json.loads(
        payload.decode("utf-8")
    )

    response = json.loads(
        build_simplified_udp_discovery_response(
            payload,
            source_ip="192.168.1.20",
            candidate=_candidate(
                "192.168.1.2"
            ),
            rate_limiter=(
                SlidingWindowRateLimiter(
                    limit=2,
                    window_s=60,
                )
            ),
        ).decode("utf-8")
    )

    assert (
        response["request_id"]
        == request["request_id"]
    )
    assert response["nonce"] == request["nonce"]
    assert (
        response["candidate"]["host"]
        == "192.168.1.2"
    )


def test_local_source_rejection_is_preserved() -> None:
    with pytest.raises(
        DiscoveryRejected,
        match="outside the local network",
    ):
        build_simplified_udp_discovery_response(
            _query(),
            source_ip="203.0.113.20",
            candidate=_candidate(
                "greenhouse-manager.local"
            ),
            rate_limiter=(
                SlidingWindowRateLimiter(
                    limit=2,
                    window_s=60,
                )
            ),
        )


def test_rate_limit_is_preserved() -> None:
    limiter = SlidingWindowRateLimiter(
        limit=1,
        window_s=60,
    )
    payload = _query()

    build_simplified_udp_discovery_response(
        payload,
        source_ip="192.168.1.20",
        candidate=_candidate(
            "greenhouse-manager.local"
        ),
        rate_limiter=limiter,
    )

    with pytest.raises(
        DiscoveryRateLimited,
        match="rate limit",
    ):
        build_simplified_udp_discovery_response(
            payload,
            source_ip="192.168.1.20",
            candidate=_candidate(
                "greenhouse-manager.local"
            ),
            rate_limiter=limiter,
        )
