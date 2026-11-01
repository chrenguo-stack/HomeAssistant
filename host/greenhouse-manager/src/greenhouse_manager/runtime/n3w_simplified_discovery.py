from __future__ import annotations

import ipaddress
import json
import re
import socket
import socketserver
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Any

from .pairing_discovery import (
    DISCOVERY_RESPONSE_SCHEMA,
    DiscoveryQuery,
    DiscoveryRateLimited,
    DiscoveryRejected,
    SlidingWindowRateLimiter,
    decode_json_datagram,
    encode_json_datagram,
    is_local_source,
)

SIMPLE_PAIRING_PROTOCOL = "gh-n3w-simple-pairing/1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")
_PAIRING_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]{1,255}$")


@dataclass(frozen=True, slots=True)
class SimplifiedManagerCandidate:
    schema: str
    manager_id: str
    system_id: str
    host: str
    scheme: str
    port: int
    pairing_path: str = "/v2/pairing"
    protocol: str = SIMPLE_PAIRING_PROTOCOL
    priority: int = 100
    ttl_s: int = 30

    def __post_init__(self) -> None:
        if self.schema != "gh.manager.candidate/1":
            raise ValueError("manager candidate schema is invalid")
        if _SAFE_ID.fullmatch(self.manager_id) is None:
            raise ValueError("manager_id is invalid")
        if _SAFE_ID.fullmatch(self.system_id) is None:
            raise ValueError("system_id is invalid")
        if _SAFE_HOST.fullmatch(self.host) is None or ".." in self.host:
            raise ValueError("host is invalid")
        if self.scheme not in {"http", "https"}:
            raise ValueError("scheme is invalid")
        if not 1 <= self.port <= 65535:
            raise ValueError("port is invalid")
        if _PAIRING_PATH.fullmatch(
            self.pairing_path
        ) is None or self.pairing_path.startswith("//"):
            raise ValueError("pairing_path is invalid")
        if self.protocol != SIMPLE_PAIRING_PROTOCOL:
            raise ValueError("protocol is invalid")
        if not 0 <= self.priority <= 65535:
            raise ValueError("priority is invalid")
        if not 1 <= self.ttl_s <= 3600:
            raise ValueError("ttl_s is invalid")

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimplifiedDiscoveryResponse:
    schema: str
    request_id: str
    nonce: str
    candidate: SimplifiedManagerCandidate

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_id": self.request_id,
            "nonce": self.nonce,
            "candidate": self.candidate.to_document(),
        }


def _validated_dynamic_ipv4(
    source_ip: str,
    selected_ip: str,
) -> str:
    try:
        source = ipaddress.ip_address(source_ip)
        selected = ipaddress.ip_address(selected_ip)
    except ValueError as error:
        raise DiscoveryRejected(
            "dynamic advertised host is invalid"
        ) from error

    if (
        source.version != 4
        or selected.version != 4
        or selected.is_unspecified
        or selected.is_multicast
        or (
            selected.is_loopback
            and not source.is_loopback
        )
    ):
        raise DiscoveryRejected(
            "dynamic advertised host is invalid"
        )

    return str(selected)


def resolve_route_selected_ipv4(source_ip: str) -> str:
    try:
        source = ipaddress.ip_address(source_ip)
    except ValueError as error:
        raise DiscoveryRejected(
            "discovery source address is invalid"
        ) from error

    if source.version != 4:
        raise DiscoveryRejected(
            "discovery source address is invalid"
        )

    try:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as probe:
            probe.connect(
                (
                    str(source),
                    9,
                )
            )
            selected_ip = str(
                probe.getsockname()[0]
            )
    except OSError as error:
        raise DiscoveryRejected(
            "dynamic advertised host unavailable"
        ) from error

    return _validated_dynamic_ipv4(
        str(source),
        selected_ip,
    )


def build_simplified_udp_discovery_response(
    payload: bytes,
    *,
    source_ip: str,
    candidate: SimplifiedManagerCandidate,
    rate_limiter: SlidingWindowRateLimiter,
    candidate_resolver: Callable[
        [str],
        SimplifiedManagerCandidate,
    ]
    | None = None,
) -> bytes:
    if not is_local_source(source_ip):
        raise DiscoveryRejected("discovery source is outside the local network")
    if not rate_limiter.allow(source_ip):
        raise DiscoveryRateLimited("discovery source exceeded the rate limit")
    query = DiscoveryQuery.from_document(decode_json_datagram(payload))
    if SIMPLE_PAIRING_PROTOCOL not in query.protocols:
        raise DiscoveryRejected("no supported simplified pairing protocol")

    response_candidate = (
        candidate_resolver(source_ip)
        if candidate_resolver is not None
        else candidate
    )

    response = SimplifiedDiscoveryResponse(
        schema=DISCOVERY_RESPONSE_SCHEMA,
        request_id=query.request_id,
        nonce=query.nonce,
        candidate=response_candidate,
    )
    return encode_json_datagram(response.to_document())


class _SimplifiedUDPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        if not isinstance(server, SimplifiedPairingUDPServer):
            return
        payload, transport = self.request
        try:
            source_ip = self.client_address[0]
            response = build_simplified_udp_discovery_response(
                payload,
                source_ip=source_ip,
                candidate=server.candidate,
                rate_limiter=server.rate_limiter,
                candidate_resolver=server.candidate_for,
            )
        except (DiscoveryRejected, DiscoveryRateLimited, ValueError, json.JSONDecodeError):
            return
        transport.sendto(response, self.client_address)


class SimplifiedPairingUDPServer(socketserver.UDPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        candidate: SimplifiedManagerCandidate,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        advertised_host_resolver: Callable[[str], str]
        = resolve_route_selected_ipv4,
    ) -> None:
        self.candidate = candidate
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            limit=12,
            window_s=60,
        )
        self.advertised_host_resolver = (
            advertised_host_resolver
        )
        super().__init__(server_address, _SimplifiedUDPHandler)

    def candidate_for(
        self,
        source_ip: str,
    ) -> SimplifiedManagerCandidate:
        if self.candidate.host != "auto":
            return self.candidate

        try:
            selected_ip = (
                self.advertised_host_resolver(
                    source_ip
                )
            )
        except DiscoveryRejected:
            raise
        except (OSError, ValueError) as error:
            raise DiscoveryRejected(
                "dynamic advertised host unavailable"
            ) from error

        return replace(
            self.candidate,
            host=_validated_dynamic_ipv4(
                source_ip,
                selected_ip,
            ),
        )
