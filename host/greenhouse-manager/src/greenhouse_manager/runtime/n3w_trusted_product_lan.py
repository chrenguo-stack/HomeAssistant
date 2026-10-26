from __future__ import annotations

import fcntl
import ipaddress
import json
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "gh.trusted-product-lan/1"
INTERFACE = "eth0"
DEFAULT_STATE_PATH = Path("/run/n3w/trusted-product-lan/state.json")


class TrustedProductLanError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TrustedProductLanState:
    available: bool
    subnet: ipaddress.IPv4Network | None
    reason: str
    generation: str
    published_at: str

    def authorizes(self, source_ip: str) -> bool:
        if not self.available or self.subnet is None:
            return False
        try:
            source = ipaddress.ip_address(source_ip)
        except ValueError:
            return False
        return isinstance(source, ipaddress.IPv4Address) and source in self.subnet


def _require_exact_keys(document: dict[str, Any], expected: set[str]) -> None:
    if set(document) != expected:
        raise TrustedProductLanError("trusted_product_lan_schema_fields_invalid")


def parse_trusted_product_lan_document(document: Any) -> TrustedProductLanState:
    if not isinstance(document, dict):
        raise TrustedProductLanError("trusted_product_lan_document_invalid")
    available = document.get("available")
    if available is True:
        _require_exact_keys(
            document,
            {
                "schema",
                "interface",
                "available",
                "subnet",
                "reason",
                "published_at",
                "generation",
            },
        )
    elif available is False:
        _require_exact_keys(
            document,
            {
                "schema",
                "interface",
                "available",
                "reason",
                "published_at",
                "generation",
            },
        )
    else:
        raise TrustedProductLanError("trusted_product_lan_available_invalid")

    if document["schema"] != SCHEMA:
        raise TrustedProductLanError("trusted_product_lan_schema_invalid")
    if document["interface"] != INTERFACE:
        raise TrustedProductLanError("trusted_product_lan_interface_invalid")
    reason = document["reason"]
    published_at = document["published_at"]
    generation = document["generation"]
    if not all(isinstance(value, str) and value for value in (reason, published_at, generation)):
        raise TrustedProductLanError("trusted_product_lan_metadata_invalid")

    subnet = None
    if available:
        try:
            parsed = ipaddress.ip_network(document["subnet"], strict=True)
        except (TypeError, ValueError) as error:
            raise TrustedProductLanError("trusted_product_lan_subnet_invalid") from error
        if not isinstance(parsed, ipaddress.IPv4Network):
            raise TrustedProductLanError("trusted_product_lan_subnet_invalid")
        if (
            parsed.prefixlen == 0
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_unspecified
        ):
            raise TrustedProductLanError("trusted_product_lan_subnet_invalid")
        subnet = parsed

    return TrustedProductLanState(
        available=available,
        subnet=subnet,
        reason=reason,
        generation=generation,
        published_at=published_at,
    )


def load_trusted_product_lan(
    path: str | Path = DEFAULT_STATE_PATH,
) -> TrustedProductLanState:
    state_path = Path(path)
    if not state_path.is_absolute() or state_path.is_symlink():
        raise TrustedProductLanError("trusted_product_lan_path_invalid")
    try:
        payload = state_path.read_text(encoding="utf-8")
        document = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TrustedProductLanError("trusted_product_lan_state_unavailable") from error
    return parse_trusted_product_lan_document(document)


def source_is_trusted_product_lan(
    source_ip: str,
    *,
    path: str | Path = DEFAULT_STATE_PATH,
) -> bool:
    try:
        return load_trusted_product_lan(path).authorizes(source_ip)
    except TrustedProductLanError:
        return False


def resolve_interface_ipv4(
    interface: str = INTERFACE,
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> str:
    if interface != INTERFACE:
        raise TrustedProductLanError("trusted_product_lan_interface_invalid")
    encoded = interface.encode("ascii")
    if not encoded or len(encoded) > 15:
        raise TrustedProductLanError("trusted_product_lan_interface_invalid")
    request = struct.pack("256s", encoded[:15])
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            result = fcntl.ioctl(probe.fileno(), 0x8915, request)
        address = socket.inet_ntoa(result[20:24])
    except OSError as error:
        raise TrustedProductLanError(
            "trusted_product_lan_interface_address_unavailable"
        ) from error
    state = load_trusted_product_lan(state_path)
    if not state.authorizes(address):
        raise TrustedProductLanError(
            "trusted_product_lan_interface_address_not_authorized"
        )
    return address
