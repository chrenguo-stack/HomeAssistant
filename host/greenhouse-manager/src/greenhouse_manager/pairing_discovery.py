from __future__ import annotations

import ipaddress
import json
import re
import socketserver
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .pairing_secure_transport import decode_base64url_32

SERVICE_TYPE = "_greenhouse._tcp.local."
DISCOVERY_QUERY_SCHEMA = "gh.discovery.query/1"
DISCOVERY_RESPONSE_SCHEMA = "gh.discovery.response/1"
SECURE_PAIRING_PROTOCOL = "gh-h3-secure-pairing/1"
MAX_UDP_DATAGRAM = 1400
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOCAL_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


class DiscoveryError(RuntimeError):
    """Base error for Stage 2B-2 discovery."""


class DiscoveryRejected(DiscoveryError):
    pass


class DiscoveryRateLimited(DiscoveryError):
    pass


class NoManagerCandidate(DiscoveryError):
    pass


class MultipleManagerCandidates(DiscoveryError):
    def __init__(self, candidates: Sequence[ManagerCandidate]) -> None:
        super().__init__("multiple manager candidates require explicit selection")
        self.candidates = tuple(candidates)


@dataclass(frozen=True, slots=True)
class ManagerCandidate:
    schema: str
    manager_id: str
    system_id: str
    host: str
    scheme: str
    port: int
    pairing_path: str
    protocol: str
    priority: int
    ttl_s: int

    def __post_init__(self) -> None:
        if self.schema != "gh.manager.candidate/1":
            raise ValueError("manager candidate schema is invalid")
        for field_name, value in (
            ("manager_id", self.manager_id),
            ("system_id", self.system_id),
        ):
            if _SAFE_ID.fullmatch(value) is None:
                raise ValueError(f"{field_name} is invalid")
        if not self.host or any(character.isspace() for character in self.host):
            raise ValueError("host must be a non-empty hostname or address")
        if self.scheme not in {"http", "https"}:
            raise ValueError("scheme must be http or https")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.pairing_path.startswith("/") or "?" in self.pairing_path:
            raise ValueError("pairing_path must be an absolute path")
        if self.protocol != SECURE_PAIRING_PROTOCOL:
            raise ValueError("unsupported pairing protocol")
        if not 0 <= self.priority <= 65535:
            raise ValueError("priority must be between 0 and 65535")
        if not 1 <= self.ttl_s <= 3600:
            raise ValueError("ttl_s must be between 1 and 3600")

    def to_document(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> ManagerCandidate:
        required = {
            "schema",
            "manager_id",
            "system_id",
            "host",
            "scheme",
            "port",
            "pairing_path",
            "protocol",
            "priority",
            "ttl_s",
        }
        if set(document) != required:
            raise DiscoveryRejected("manager candidate fields are invalid")
        try:
            return cls(**dict(document))
        except (TypeError, ValueError) as error:
            raise DiscoveryRejected("manager candidate is invalid") from error


@dataclass(frozen=True, slots=True)
class DiscoveryQuery:
    schema: str
    request_id: str
    nonce: str
    hardware_id: str
    protocols: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema != DISCOVERY_QUERY_SCHEMA:
            raise ValueError("discovery query schema is invalid")
        try:
            uuid.UUID(self.request_id)
        except ValueError as error:
            raise ValueError("request_id must be a UUID") from error
        decode_base64url_32(self.nonce, field_name="nonce")
        if _SAFE_ID.fullmatch(self.hardware_id) is None:
            raise ValueError("hardware_id is invalid")
        if not self.protocols or len(self.protocols) > 8:
            raise ValueError("protocols must contain between 1 and 8 values")
        if any(_SAFE_ID.fullmatch(value) is None for value in self.protocols):
            raise ValueError("protocol value is invalid")

    def to_document(self) -> dict[str, Any]:
        document = asdict(self)
        document["protocols"] = list(self.protocols)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> DiscoveryQuery:
        required = {"schema", "request_id", "nonce", "hardware_id", "protocols"}
        if set(document) != required or not isinstance(document["protocols"], list):
            raise DiscoveryRejected("discovery query fields are invalid")
        try:
            return cls(
                schema=document["schema"],
                request_id=document["request_id"],
                nonce=document["nonce"],
                hardware_id=document["hardware_id"],
                protocols=tuple(document["protocols"]),
            )
        except (TypeError, ValueError) as error:
            raise DiscoveryRejected("discovery query is invalid") from error


@dataclass(frozen=True, slots=True)
class DiscoveryResponse:
    schema: str
    request_id: str
    nonce: str
    candidate: ManagerCandidate

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_id": self.request_id,
            "nonce": self.nonce,
            "candidate": self.candidate.to_document(),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> DiscoveryResponse:
        required = {"schema", "request_id", "nonce", "candidate"}
        if set(document) != required or document["schema"] != DISCOVERY_RESPONSE_SCHEMA:
            raise DiscoveryRejected("discovery response fields are invalid")
        try:
            uuid.UUID(document["request_id"])
            decode_base64url_32(document["nonce"], field_name="nonce")
            candidate = ManagerCandidate.from_document(document["candidate"])
        except (TypeError, ValueError) as error:
            raise DiscoveryRejected("discovery response is invalid") from error
        return cls(
            schema=DISCOVERY_RESPONSE_SCHEMA,
            request_id=document["request_id"],
            nonce=document["nonce"],
            candidate=candidate,
        )


@dataclass(slots=True)
class _ObservedCandidate:
    candidate: ManagerCandidate
    expires_at: float


class CandidateSet:
    """Dedupe manager observations and forbid silent multi-manager choice."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._candidates: dict[str, _ObservedCandidate] = {}

    def observe(self, candidate: ManagerCandidate, *, ttl_s: int | None = None) -> None:
        observed_ttl = ttl_s if ttl_s is not None else candidate.ttl_s
        if not 1 <= observed_ttl <= 3600:
            raise ValueError("observed ttl must be between 1 and 3600")
        with self._lock:
            self._prune_locked()
            self._candidates[candidate.manager_id] = _ObservedCandidate(
                candidate=candidate,
                expires_at=self._clock() + observed_ttl,
            )

    def candidates(self) -> tuple[ManagerCandidate, ...]:
        with self._lock:
            self._prune_locked()
            return tuple(
                sorted(
                    (observed.candidate for observed in self._candidates.values()),
                    key=lambda item: (item.priority, item.system_id, item.manager_id),
                )
            )

    def resolve(self, *, selected_manager_id: str | None = None) -> ManagerCandidate:
        candidates = self.candidates()
        if selected_manager_id is not None:
            matches = [candidate for candidate in candidates if candidate.manager_id == selected_manager_id]
            if not matches:
                raise NoManagerCandidate("selected manager is not available")
            return matches[0]
        if not candidates:
            raise NoManagerCandidate("no manager candidate is available")
        if len(candidates) > 1:
            raise MultipleManagerCandidates(candidates)
        return candidates[0]

    def _prune_locked(self) -> None:
        now = self._clock()
        expired = [key for key, observed in self._candidates.items() if observed.expires_at <= now]
        for key in expired:
            del self._candidates[key]


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1 or window_s <= 0:
            raise ValueError("rate limit and window must be positive")
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._lock = threading.RLock()
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        cutoff = now - self.window_s
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def is_local_source(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return any(parsed in network for network in _LOCAL_NETWORKS if parsed.version == network.version)


def decode_json_datagram(payload: bytes) -> Mapping[str, Any]:
    if not payload or len(payload) > MAX_UDP_DATAGRAM:
        raise DiscoveryRejected("discovery datagram size is invalid")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryRejected("discovery datagram is invalid JSON") from error
    if not isinstance(document, dict):
        raise DiscoveryRejected("discovery datagram must be a JSON object")
    return document


def encode_json_datagram(document: Mapping[str, Any]) -> bytes:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    if len(payload) > MAX_UDP_DATAGRAM:
        raise DiscoveryRejected("discovery response exceeds datagram limit")
    return payload


def build_udp_discovery_response(
    payload: bytes,
    *,
    source_ip: str,
    candidate: ManagerCandidate,
    rate_limiter: SlidingWindowRateLimiter,
) -> bytes:
    if not is_local_source(source_ip):
        raise DiscoveryRejected("discovery source is outside the local network")
    if not rate_limiter.allow(source_ip):
        raise DiscoveryRateLimited("discovery source exceeded the rate limit")
    query = DiscoveryQuery.from_document(decode_json_datagram(payload))
    if candidate.protocol not in query.protocols:
        raise DiscoveryRejected("no supported pairing protocol")
    response = DiscoveryResponse(
        schema=DISCOVERY_RESPONSE_SCHEMA,
        request_id=query.request_id,
        nonce=query.nonce,
        candidate=candidate,
    )
    return encode_json_datagram(response.to_document())


class _UDPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        if not isinstance(server, PairingUDPServer):
            return
        payload, transport = self.request
        try:
            response = build_udp_discovery_response(
                payload,
                source_ip=self.client_address[0],
                candidate=server.candidate,
                rate_limiter=server.rate_limiter,
            )
        except DiscoveryError:
            return
        transport.sendto(response, self.client_address)


class PairingUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        candidate: ManagerCandidate,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self.candidate = candidate
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(limit=12, window_s=60)
        super().__init__(server_address, _UDPHandler)


class ZeroconfLike(Protocol):
    def register_service(self, info: Any, **kwargs: Any) -> None: ...

    def unregister_service(self, info: Any) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class MdnsServiceDefinition:
    service_type: str
    name: str
    server: str
    port: int
    addresses: tuple[bytes, ...]
    properties: Mapping[str, str]


def build_mdns_service_definition(
    candidate: ManagerCandidate,
    *,
    instance_name: str,
    addresses: Sequence[str],
) -> MdnsServiceDefinition:
    if not instance_name or "." in instance_name:
        raise ValueError("instance_name must be a single DNS label")
    packed: list[bytes] = []
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if parsed.version != 4:
            raise ValueError("Stage 2B-2 mDNS advertisement currently supports IPv4 addresses")
        packed.append(parsed.packed)
    if not packed:
        raise ValueError("at least one mDNS address is required")
    server = candidate.host if candidate.host.endswith(".") else f"{candidate.host}."
    return MdnsServiceDefinition(
        service_type=SERVICE_TYPE,
        name=f"{instance_name}.{SERVICE_TYPE}",
        server=server,
        port=candidate.port,
        addresses=tuple(packed),
        properties={
            "schema": candidate.schema,
            "manager_id": candidate.manager_id,
            "system_id": candidate.system_id,
            "scheme": candidate.scheme,
            "pairing_path": candidate.pairing_path,
            "protocol": candidate.protocol,
            "priority": str(candidate.priority),
            "ttl_s": str(candidate.ttl_s),
        },
    )


class MdnsAdvertiser:
    """Register `_greenhouse._tcp.local.` using python-zeroconf lazily."""

    def __init__(
        self,
        definition: MdnsServiceDefinition,
        *,
        zeroconf_factory: Callable[[], ZeroconfLike] | None = None,
        service_info_factory: Callable[..., Any] | None = None,
    ) -> None:
        if zeroconf_factory is None or service_info_factory is None:
            try:
                from zeroconf import ServiceInfo, Zeroconf
            except ImportError as error:
                raise RuntimeError(
                    "mDNS advertisement requires greenhouse-manager[pairing]"
                ) from error
            zeroconf_factory = Zeroconf
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
        self._closed = False
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("mDNS advertiser is closed")
            if self._started:
                return
            self._zeroconf.register_service(
                self._info,
                allow_name_change=False,
                strict=True,
            )
            self._started = True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if self._started:
                self._zeroconf.unregister_service(self._info)
                self._started = False
            self._zeroconf.close()
            self._closed = True
