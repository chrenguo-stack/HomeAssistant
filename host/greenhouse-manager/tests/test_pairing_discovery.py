from __future__ import annotations

import base64
import json
import socket
import threading
import uuid
from typing import Any

import pytest

from greenhouse_manager.pairing_discovery import (
    DISCOVERY_QUERY_SCHEMA,
    DISCOVERY_RESPONSE_SCHEMA,
    SECURE_PAIRING_PROTOCOL,
    CandidateSet,
    DiscoveryQuery,
    DiscoveryRateLimited,
    DiscoveryRejected,
    DiscoveryResponse,
    ManagerCandidate,
    MdnsAdvertiser,
    MultipleManagerCandidates,
    NoManagerCandidate,
    PairingUDPServer,
    SlidingWindowRateLimiter,
    build_mdns_service_definition,
    build_udp_discovery_response,
    decode_json_datagram,
    encode_json_datagram,
)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


NONCE = b64(bytes(range(32)))
REQUEST_ID = str(uuid.UUID("20323fb7-09df-4b88-9aae-871794ac6e91"))


def candidate(
    manager_id: str = "manager-a",
    *,
    system_id: str = "greenhouse-a",
    priority: int = 10,
) -> ManagerCandidate:
    return ManagerCandidate(
        schema="gh.manager.candidate/1",
        manager_id=manager_id,
        system_id=system_id,
        host="greenhouse.local",
        scheme="http",
        port=8443,
        pairing_path="/v1/pairing",
        protocol=SECURE_PAIRING_PROTOCOL,
        priority=priority,
        ttl_s=30,
    )


def query_document() -> dict[str, Any]:
    return {
        "schema": DISCOVERY_QUERY_SCHEMA,
        "request_id": REQUEST_ID,
        "nonce": NONCE,
        "hardware_id": "ghw-c6-98a316a9f2f8",
        "protocols": [SECURE_PAIRING_PROTOCOL],
    }


def test_discovery_query_roundtrip_is_strict() -> None:
    query = DiscoveryQuery.from_document(query_document())
    assert query.to_document() == query_document()

    invalid = query_document()
    invalid["extra"] = True
    with pytest.raises(DiscoveryRejected, match="fields are invalid"):
        DiscoveryQuery.from_document(invalid)


def test_udp_response_echoes_nonce_and_request_id_without_pair_secret() -> None:
    response_payload = build_udp_discovery_response(
        encode_json_datagram(query_document()),
        source_ip="192.168.1.50",
        candidate=candidate(),
        rate_limiter=SlidingWindowRateLimiter(limit=2, window_s=60),
    )
    document = decode_json_datagram(response_payload)
    response = DiscoveryResponse.from_document(document)

    assert response.schema == DISCOVERY_RESPONSE_SCHEMA
    assert response.request_id == REQUEST_ID
    assert response.nonce == NONCE
    assert response.candidate == candidate()
    assert "secret" not in response_payload.decode("utf-8").lower()


def test_udp_discovery_rejects_public_source_and_protocol_mismatch() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_s=60)
    payload = encode_json_datagram(query_document())
    with pytest.raises(DiscoveryRejected, match="outside the local network"):
        build_udp_discovery_response(
            payload,
            source_ip="8.8.8.8",
            candidate=candidate(),
            rate_limiter=limiter,
        )

    invalid = query_document()
    invalid["protocols"] = ["unsupported-protocol"]
    with pytest.raises(DiscoveryRejected, match="no supported pairing protocol"):
        build_udp_discovery_response(
            encode_json_datagram(invalid),
            source_ip="10.0.0.5",
            candidate=candidate(),
            rate_limiter=limiter,
        )


def test_udp_discovery_enforces_rate_limit() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_s=60)
    payload = encode_json_datagram(query_document())
    build_udp_discovery_response(
        payload,
        source_ip="192.168.1.50",
        candidate=candidate(),
        rate_limiter=limiter,
    )
    with pytest.raises(DiscoveryRateLimited):
        build_udp_discovery_response(
            payload,
            source_ip="192.168.1.50",
            candidate=candidate(),
            rate_limiter=limiter,
        )


def test_candidate_set_never_auto_selects_multiple_managers() -> None:
    clock = [100.0]
    candidates = CandidateSet(clock=lambda: clock[0])
    first = candidate("manager-a", priority=20)
    second = candidate("manager-b", system_id="greenhouse-b", priority=1)
    candidates.observe(first)
    candidates.observe(second)

    with pytest.raises(MultipleManagerCandidates) as error:
        candidates.resolve()
    assert {item.manager_id for item in error.value.candidates} == {
        "manager-a",
        "manager-b",
    }
    assert candidates.resolve(selected_manager_id="manager-b") == second

    clock[0] = 131.0
    with pytest.raises(NoManagerCandidate):
        candidates.resolve()


def test_mdns_definition_contains_only_public_discovery_metadata() -> None:
    definition = build_mdns_service_definition(
        candidate(),
        instance_name="greenhouse-manager-a",
        addresses=["192.168.1.20"],
    )
    assert definition.service_type == "_greenhouse._tcp.local."
    assert definition.name == "greenhouse-manager-a._greenhouse._tcp.local."
    assert definition.addresses == (socket.inet_aton("192.168.1.20"),)
    assert definition.properties["manager_id"] == "manager-a"
    assert definition.properties["scheme"] == "http"
    assert "secret" not in json.dumps(definition.properties).lower()


class FakeZeroconf:
    def __init__(self) -> None:
        self.registered: list[tuple[Any, dict[str, Any]]] = []
        self.unregistered: list[Any] = []
        self.closed = 0

    def register_service(self, info: Any, **kwargs: Any) -> None:
        self.registered.append((info, kwargs))

    def unregister_service(self, info: Any) -> None:
        self.unregistered.append(info)

    def close(self) -> None:
        self.closed += 1


class FakeServiceInfo:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_mdns_advertiser_registers_and_unregisters_once() -> None:
    definition = build_mdns_service_definition(
        candidate(),
        instance_name="greenhouse-manager-a",
        addresses=["192.168.1.20"],
    )
    fake = FakeZeroconf()
    advertiser = MdnsAdvertiser(
        definition,
        zeroconf_factory=lambda: fake,
        service_info_factory=FakeServiceInfo,
    )

    advertiser.start()
    advertiser.start()
    advertiser.close()
    advertiser.close()

    assert len(fake.registered) == 1
    assert fake.registered[0][1] == {
        "allow_name_change": False,
        "strict": True,
    }
    assert len(fake.unregistered) == 1
    assert fake.closed == 1


def test_udp_server_performs_real_loopback_roundtrip() -> None:
    server = PairingUDPServer(("127.0.0.1", 0), candidate=candidate())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.sendto(
                encode_json_datagram(query_document()),
                server.server_address,
            )
            payload, _address = client.recvfrom(2048)
        response = DiscoveryResponse.from_document(decode_json_datagram(payload))
        assert response.request_id == REQUEST_ID
        assert response.nonce == NONCE
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
