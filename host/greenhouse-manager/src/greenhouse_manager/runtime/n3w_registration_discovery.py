from __future__ import annotations

import ipaddress
import json
import re
import socketserver
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

from .n3w_simplified_discovery import resolve_route_selected_ipv4
from .n3w_trusted_product_lan import (
    TrustedProductLanState,
    load_trusted_product_lan,
)
from .pairing_discovery import (
    DiscoveryQuery,
    DiscoveryRateLimited,
    DiscoveryRejected,
    MdnsServiceDefinition,
    SlidingWindowRateLimiter,
    decode_json_datagram,
    encode_json_datagram,
)

REGISTRATION_PROTOCOL = "gh.n3w.first-registration/1"
CANDIDATE_SCHEMA = "gh.registration.candidate/1"
RESPONSE_SCHEMA = "gh.registration.discovery-result/1"
REGISTRATION_SERVICE_TYPE = "_greenhouse-reg._tcp.local."
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RegistrationCandidate:
    manager_id: str
    system_id: str
    system_id_hint: str
    host: str
    bootstrap_tls_sha256: str
    busy: bool = False
    bootstrap_scheme: str = "https"
    bootstrap_port: int = 47110
    bootstrap_path: str = "/v1/registration/confirm"
    protocol: str = REGISTRATION_PROTOCOL
    ttl_s: int = 30
    schema: str = CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CANDIDATE_SCHEMA:
            raise ValueError("registration candidate schema invalid")
        if _SAFE_ID.fullmatch(self.manager_id) is None:
            raise ValueError("manager_id invalid")
        if _SAFE_ID.fullmatch(self.system_id) is None:
            raise ValueError("system_id invalid")
        if not self.system_id_hint or len(self.system_id_hint) > 32:
            raise ValueError("system_id_hint invalid")
        if not self.host or any(character.isspace() for character in self.host):
            raise ValueError("host invalid")
        if self.bootstrap_scheme != "https":
            raise ValueError("bootstrap_scheme invalid")
        if self.bootstrap_port != 47110:
            raise ValueError("bootstrap_port invalid")
        if self.bootstrap_path != "/v1/registration/confirm":
            raise ValueError("bootstrap_path invalid")
        if self.protocol != REGISTRATION_PROTOCOL:
            raise ValueError("registration protocol invalid")
        if self.ttl_s != 30:
            raise ValueError("candidate ttl invalid")
        if _SHA256.fullmatch(self.bootstrap_tls_sha256) is None:
            raise ValueError("bootstrap_tls_sha256 invalid")

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def build_registration_udp_response(
    payload: bytes,
    *,
    source_ip: str,
    candidate_for: Callable[[str], RegistrationCandidate],
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
    rate_limiter: SlidingWindowRateLimiter,
) -> bytes:
    state = state_loader()
    if not state.authorizes(source_ip):
        raise DiscoveryRejected("source_not_trusted_product_lan")
    if not rate_limiter.allow(source_ip):
        raise DiscoveryRateLimited("registration discovery rate limited")
    query = DiscoveryQuery.from_document(decode_json_datagram(payload))
    if REGISTRATION_PROTOCOL not in query.protocols:
        raise DiscoveryRejected("registration protocol unsupported")
    candidate = candidate_for(source_ip)
    response = {
        "schema": RESPONSE_SCHEMA,
        "request_id": query.request_id,
        "nonce": query.nonce,
        "candidate": candidate.to_document(),
    }
    encoded = encode_json_datagram(response)
    if len(encoded) > len(payload):
        raise DiscoveryRejected("registration discovery amplification forbidden")
    return encoded


def decode_registration_candidate(payload: bytes) -> RegistrationCandidate:
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("registration candidate document invalid")
    return RegistrationCandidate(**document)


class _RegistrationUDPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        if not isinstance(server, RegistrationDiscoveryUDPServer):
            return
        payload, transport = self.request
        try:
            response = build_registration_udp_response(
                payload,
                source_ip=self.client_address[0],
                candidate_for=server.candidate_for,
                state_loader=server.state_loader,
                rate_limiter=server.rate_limiter,
            )
        except (DiscoveryRejected, DiscoveryRateLimited, ValueError, json.JSONDecodeError):
            return
        transport.sendto(response, self.client_address)


class RegistrationDiscoveryUDPServer(socketserver.UDPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        candidate: RegistrationCandidate,
        state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        advertised_host_resolver: Callable[[str], str] = resolve_route_selected_ipv4,
    ) -> None:
        self.candidate = candidate
        self.state_loader = state_loader
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            limit=12,
            window_s=60,
        )
        self.advertised_host_resolver = advertised_host_resolver
        super().__init__(server_address, _RegistrationUDPHandler)

    def candidate_for(self, source_ip: str) -> RegistrationCandidate:
        if self.candidate.host != "auto":
            return self.candidate
        selected = self.advertised_host_resolver(source_ip)
        parsed = ipaddress.ip_address(selected)
        state = self.state_loader()
        if (
            not isinstance(parsed, ipaddress.IPv4Address)
            or not state.authorizes(str(parsed))
        ):
            raise DiscoveryRejected("registration advertised host is outside trusted product LAN")
        return replace(self.candidate, host=str(parsed))


class ZeroconfLike(Protocol):
    def register_service(self, info: Any, **kwargs: Any) -> None: ...

    def unregister_service(self, info: Any) -> None: ...

    def close(self) -> None: ...


def build_registration_mdns_definition(
    candidate: RegistrationCandidate,
    *,
    instance_name: str,
    interface_ip: str,
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
) -> MdnsServiceDefinition:
    state = state_loader()
    if not state.authorizes(interface_ip):
        raise DiscoveryRejected("mDNS interface is outside trusted product LAN")
    parsed = ipaddress.ip_address(interface_ip)
    if not isinstance(parsed, ipaddress.IPv4Address):
        raise DiscoveryRejected("mDNS interface must be IPv4")
    explicit_candidate = (
        candidate
        if candidate.host != "auto"
        else replace(candidate, host=str(parsed))
    )
    if explicit_candidate.host != str(parsed):
        raise DiscoveryRejected("mDNS candidate host must match trusted interface IPv4")
    if not instance_name or any(character.isspace() for character in instance_name):
        raise ValueError("mDNS instance name invalid")
    return MdnsServiceDefinition(
        service_type=REGISTRATION_SERVICE_TYPE,
        name=f"{instance_name}.{REGISTRATION_SERVICE_TYPE}",
        server=f"{explicit_candidate.host}.",
        port=explicit_candidate.bootstrap_port,
        addresses=(parsed.packed,),
        properties={
            "schema": explicit_candidate.schema,
            "manager_id": explicit_candidate.manager_id,
            "system_id": explicit_candidate.system_id,
            "system_id_hint": explicit_candidate.system_id_hint,
            "bootstrap_scheme": explicit_candidate.bootstrap_scheme,
            "bootstrap_path": explicit_candidate.bootstrap_path,
            "bootstrap_tls_sha256": explicit_candidate.bootstrap_tls_sha256,
            "protocol": explicit_candidate.protocol,
            "ttl_s": str(explicit_candidate.ttl_s),
            "busy": "1" if explicit_candidate.busy else "0",
        },
    )


class RegistrationMdnsAdvertiser:
    def __init__(
        self,
        definition: MdnsServiceDefinition,
        *,
        interface_ip: str,
        zeroconf_factory: Callable[..., ZeroconfLike] | None = None,
        service_info_factory: Callable[..., Any] | None = None,
    ) -> None:
        if (zeroconf_factory is None) != (service_info_factory is None):
            raise ValueError("zeroconf factories must be provided together")
        if zeroconf_factory is None:
            try:
                from zeroconf import IPVersion, ServiceInfo, Zeroconf
            except ImportError as error:
                raise RuntimeError(
                    "registration mDNS requires greenhouse-manager[pairing]"
                ) from error

            def scoped_zeroconf() -> ZeroconfLike:
                return Zeroconf(
                    interfaces=[interface_ip],
                    ip_version=IPVersion.V4Only,
                )

            zeroconf_factory = scoped_zeroconf
            service_info_factory = ServiceInfo
        self.definition = definition
        self._zeroconf = zeroconf_factory()
        self._info = service_info_factory(
            type_=definition.service_type,
            name=definition.name,
            addresses=list(definition.addresses),
            port=definition.port,
            properties=dict(definition.properties),
            server=definition.server,
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._zeroconf.register_service(
            self._info,
            allow_name_change=False,
            strict=True,
        )
        self._started = True

    def close(self) -> None:
        if self._started:
            self._zeroconf.unregister_service(self._info)
            self._started = False
        self._zeroconf.close()
