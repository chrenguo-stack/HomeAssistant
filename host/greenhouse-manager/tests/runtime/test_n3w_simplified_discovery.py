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
            "192.0.2.10"
        ),
    )

    try:
        assert (
            server.candidate_for(
                "192.0.2.20"
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
            "192.0.2.20": "192.0.2.2",
            "198.51.100.20": "198.51.100.2",
        }[source_ip]

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=resolver,
    )

    try:
        first = server.candidate_for(
            "192.0.2.20"
        )
        second = server.candidate_for(
            "198.51.100.20"
        )
    finally:
        server.server_close()

    assert first.host == "192.0.2.2"
    assert second.host == "198.51.100.2"
    assert observed == [
        "192.0.2.20",
        "198.51.100.20",
    ]


@pytest.mark.parametrize(
    ("source_ip", "selected_ip"),
    [
        ("192.0.2.20", "0.0.0.0"),
        ("192.0.2.20", "224.0.0.1"),
        ("192.0.2.20", "127.0.0.1"),
        ("192.0.2.20", "not-an-ip"),
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
            source_ip="127.0.0.2",
            candidate=_candidate(
                "192.0.2.2"
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
        == "192.0.2.2"
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
        source_ip="127.0.0.2",
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
            source_ip="127.0.0.2",
            candidate=_candidate(
                "greenhouse-manager.local"
            ),
            rate_limiter=limiter,
        )


def test_same_runtime_response_tracks_route_change() -> None:
    routes = {
        "127.0.0.2": "127.0.0.4",
        "127.0.0.3": "127.0.0.5",
    }

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=routes.__getitem__,
    )
    limiter = SlidingWindowRateLimiter(
        limit=4,
        window_s=60,
    )

    try:
        first = json.loads(
            build_simplified_udp_discovery_response(
                _query(),
                source_ip="127.0.0.2",
                candidate=server.candidate,
                candidate_resolver=server.candidate_for,
                rate_limiter=limiter,
            ).decode("utf-8")
        )
        second = json.loads(
            build_simplified_udp_discovery_response(
                _query(),
                source_ip="127.0.0.3",
                candidate=server.candidate,
                candidate_resolver=server.candidate_for,
                rate_limiter=limiter,
            ).decode("utf-8")
        )
    finally:
        server.server_close()

    assert first["candidate"]["host"] == "127.0.0.4"
    assert second["candidate"]["host"] == "127.0.0.5"



def test_same_client_same_runtime_does_not_reuse_stale_host_after_failure() -> None:
    outcomes = [
        "127.0.0.4",
        OSError("route unavailable"),
        "127.0.0.5",
    ]
    observed = []

    def resolver(source_ip: str) -> str:
        observed.append(source_ip)
        outcome = outcomes[len(observed) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=resolver,
        rate_limiter=SlidingWindowRateLimiter(
            limit=6,
            window_s=60,
        ),
    )
    client = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )
    client.bind(("127.0.0.2", 0))
    client.settimeout(0.2)

    def exchange() -> bytes:
        worker = threading.Thread(
            target=server.handle_request,
            daemon=True,
        )
        worker.start()
        client.sendto(
            _query(),
            server.server_address,
        )
        payload, _ = client.recvfrom(4096)
        worker.join(timeout=1)
        assert worker.is_alive() is False
        return payload

    try:
        first = json.loads(
            exchange().decode("utf-8")
        )

        worker = threading.Thread(
            target=server.handle_request,
            daemon=True,
        )
        worker.start()
        client.sendto(
            _query(),
            server.server_address,
        )
        with pytest.raises(TimeoutError):
            client.recvfrom(4096)
        worker.join(timeout=1)
        assert worker.is_alive() is False

        third = json.loads(
            exchange().decode("utf-8")
        )
    finally:
        client.close()
        server.server_close()

    assert first["candidate"]["host"] == "127.0.0.4"
    assert third["candidate"]["host"] == "127.0.0.5"
    assert observed == ["127.0.0.2"] * 3



def test_untrusted_source_is_rejected_before_route_resolution() -> None:
    calls = []

    def resolver(source_ip: str) -> str:
        calls.append(source_ip)
        return "192.0.2.2"

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=resolver,
    )

    try:
        with pytest.raises(
            DiscoveryRejected,
            match="outside the local network",
        ):
            build_simplified_udp_discovery_response(
                _query(),
                source_ip="203.0.113.20",
                candidate=server.candidate,
                candidate_resolver=server.candidate_for,
                rate_limiter=SlidingWindowRateLimiter(
                    limit=2,
                    window_s=60,
                ),
            )
    finally:
        server.server_close()

    assert calls == []


def test_rate_limit_is_checked_before_route_resolution() -> None:
    calls = []

    def resolver(source_ip: str) -> str:
        calls.append(source_ip)
        return "127.0.0.4"

    server = SimplifiedPairingUDPServer(
        ("127.0.0.1", 0),
        candidate=_candidate("auto"),
        advertised_host_resolver=resolver,
    )
    limiter = SlidingWindowRateLimiter(
        limit=1,
        window_s=60,
    )

    try:
        build_simplified_udp_discovery_response(
            _query(),
            source_ip="127.0.0.2",
            candidate=server.candidate,
            candidate_resolver=server.candidate_for,
            rate_limiter=limiter,
        )

        with pytest.raises(
            DiscoveryRateLimited,
            match="rate limit",
        ):
            build_simplified_udp_discovery_response(
                _query(),
                source_ip="127.0.0.2",
                candidate=server.candidate,
                candidate_resolver=server.candidate_for,
                rate_limiter=limiter,
            )
    finally:
        server.server_close()

    assert calls == ["127.0.0.2"]
