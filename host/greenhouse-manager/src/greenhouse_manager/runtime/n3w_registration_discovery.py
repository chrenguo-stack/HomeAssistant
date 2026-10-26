from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .n3w_trusted_product_lan import (
    TrustedProductLanState,
    load_trusted_product_lan,
)
from .pairing_discovery import (
    DiscoveryQuery,
    DiscoveryRateLimited,
    DiscoveryRejected,
    SlidingWindowRateLimiter,
    decode_json_datagram,
    encode_json_datagram,
)

REGISTRATION_PROTOCOL = "gh.n3w.first-registration/1"
CANDIDATE_SCHEMA = "gh.registration.candidate/1"
RESPONSE_SCHEMA = "gh.registration.discovery-result/1"
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
    if len(encoded) > max(len(payload) * 4, 1024):
        raise DiscoveryRejected("registration discovery amplification limit")
    return encoded


def decode_registration_candidate(payload: bytes) -> RegistrationCandidate:
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("registration candidate document invalid")
    return RegistrationCandidate(**document)
