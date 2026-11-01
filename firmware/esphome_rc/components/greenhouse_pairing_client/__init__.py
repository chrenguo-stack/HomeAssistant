from __future__ import annotations

import ipaddress
import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

CONF_HARDWARE_ID = "hardware_id"
CONF_PAIRING_ID = "pairing_id"
CONF_PAIRING_SECRET = "pairing_secret"
CONF_MAX_CANDIDATES = "max_candidates"
CONF_CANDIDATE_TTL_CAP = "candidate_ttl_cap"
CONF_NETWORK_ENABLED = "network_enabled"
CONF_MDNS_ENABLED = "mdns_enabled"
CONF_UDP_ENABLED = "udp_enabled"
CONF_UDP_TARGET = "udp_target"
CONF_UDP_PORT = "udp_port"
CONF_UDP_ATTEMPTS = "udp_attempts"
CONF_UDP_INITIAL_BACKOFF = "udp_initial_backoff"
CONF_MDNS_TIMEOUT = "mdns_timeout"
CONF_HTTP_TIMEOUT = "http_timeout"
CONF_RESPONSE_MAX_BYTES = "response_max_bytes"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_BASE64URL_32 = re.compile(r"^[A-Za-z0-9_-]{43}$")
# Integer network addresses avoid publishing environment-looking private IP
# literals while keeping the RFC-defined validation ranges exact.
_LOCAL_UDP_NETWORKS = (
    ipaddress.IPv4Network((0x0A000000, 8)),
    ipaddress.IPv4Network((0xAC100000, 12)),
    ipaddress.IPv4Network((0xC0A80000, 16)),
    ipaddress.IPv4Network((0x7F000000, 8)),
    ipaddress.IPv4Network((0xA9FE0000, 16)),
)


def _safe_id(value: object) -> str:
    candidate = cv.string_strict(value)
    if _SAFE_ID.fullmatch(candidate) is None:
        raise cv.Invalid("hardware_id must be 1-128 safe ASCII characters")
    return candidate


def _uuid(value: object) -> str:
    candidate = cv.string_strict(value)
    if _UUID.fullmatch(candidate) is None:
        raise cv.Invalid("pairing_id must be a canonical UUID")
    return candidate.lower()


def _pairing_secret(value: object) -> str:
    candidate = cv.string_strict(value)
    if _BASE64URL_32.fullmatch(candidate) is None:
        raise cv.Invalid("pairing_secret must be 32-byte unpadded base64url")
    return candidate


def _ttl_cap(value: object):
    period = cv.positive_time_period_seconds(value)
    if period.total_seconds > 3600:
        raise cv.Invalid("candidate_ttl_cap must not exceed 3600 seconds")
    return period


def _milliseconds_between(minimum: int, maximum: int):
    def validator(value: object):
        period = cv.positive_time_period_milliseconds(value)
        if not minimum <= period.total_milliseconds <= maximum:
            raise cv.Invalid(f"duration must be between {minimum}ms and {maximum}ms")
        return period

    return validator


def _udp_target(value: object) -> str:
    candidate = cv.string_strict(value)
    try:
        address = ipaddress.IPv4Address(candidate)
    except ipaddress.AddressValueError as error:
        raise cv.Invalid("udp_target must be an IPv4 address") from error
    if str(address) != "255.255.255.255" and not any(
        address in network for network in _LOCAL_UDP_NETWORKS
    ):
        raise cv.Invalid(
            "udp_target must be limited broadcast, loopback, RFC1918, or link-local"
        )
    return str(address)


def _validate_network(config: dict) -> dict:
    if config[CONF_NETWORK_ENABLED] and not (
        config[CONF_MDNS_ENABLED] or config[CONF_UDP_ENABLED]
    ):
        raise cv.Invalid(
            "network_enabled requires mdns_enabled or udp_enabled"
        )
    return config


greenhouse_pairing_client_ns = cg.esphome_ns.namespace(
    "greenhouse_pairing_client"
)
GreenhousePairingClient = greenhouse_pairing_client_ns.class_(
    "GreenhousePairingClient", cg.Component
)

_INSTANCE_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(GreenhousePairingClient),
            cv.Required(CONF_HARDWARE_ID): _safe_id,
            cv.Required(CONF_PAIRING_ID): _uuid,
            # ESPHome masks keys containing "secret" in rendered config output.
            # Stage 2C-2 only references non-production !secret values.
            cv.Required(CONF_PAIRING_SECRET): _pairing_secret,
            cv.Optional(CONF_MAX_CANDIDATES, default=4): cv.int_range(
                min=1, max=16
            ),
            cv.Optional(CONF_CANDIDATE_TTL_CAP, default="120s"): _ttl_cap,
            cv.Optional(CONF_NETWORK_ENABLED, default=False): cv.boolean,
            cv.Optional(CONF_MDNS_ENABLED, default=True): cv.boolean,
            cv.Optional(CONF_UDP_ENABLED, default=True): cv.boolean,
            cv.Optional(
                CONF_UDP_TARGET, default="255.255.255.255"
            ): _udp_target,
            cv.Optional(CONF_UDP_PORT, default=47111): cv.port,
            cv.Optional(CONF_UDP_ATTEMPTS, default=3): cv.int_range(
                min=1, max=5
            ),
            cv.Optional(
                CONF_UDP_INITIAL_BACKOFF, default="250ms"
            ): _milliseconds_between(50, 5000),
            cv.Optional(
                CONF_MDNS_TIMEOUT, default="1000ms"
            ): _milliseconds_between(100, 5000),
            cv.Optional(
                CONF_HTTP_TIMEOUT, default="5000ms"
            ): _milliseconds_between(250, 5000),
            cv.Optional(CONF_RESPONSE_MAX_BYTES, default=16384): cv.int_range(
                min=1024, max=16384
            ),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _validate_network,
)


def CONFIG_SCHEMA(value: object) -> dict:
    # Stage 2C-3 may auto-load this component only to compile its shared C++
    # transport library. Explicit non-empty instances retain the full strict
    # Stage 2C-1/2 schema and code generation path.
    if value is None or value == {}:
        return {}
    return _INSTANCE_SCHEMA(value)


async def to_code(config: dict) -> None:
    # ESPHome 2026.2+ excludes unused IDF components by default. The external
    # component directly uses esp_http_client.h, so re-enable that built-in
    # component for Stage 2C-1/2 instances and the Stage 2C-3 library load.
    include_builtin_idf_component("esp_http_client")

    if not config:
        return

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hardware_id(config[CONF_HARDWARE_ID]))
    cg.add(var.set_pairing_id(config[CONF_PAIRING_ID]))
    cg.add(var.set_pairing_secret(config[CONF_PAIRING_SECRET]))
    cg.add(var.set_max_candidates(config[CONF_MAX_CANDIDATES]))
    cg.add(
        var.set_candidate_ttl_cap_s(
            config[CONF_CANDIDATE_TTL_CAP].total_seconds
        )
    )
    cg.add(var.set_network_enabled(config[CONF_NETWORK_ENABLED]))
    cg.add(var.set_mdns_enabled(config[CONF_MDNS_ENABLED]))
    cg.add(var.set_udp_enabled(config[CONF_UDP_ENABLED]))
    cg.add(var.set_udp_target(config[CONF_UDP_TARGET]))
    cg.add(var.set_udp_port(config[CONF_UDP_PORT]))
    cg.add(var.set_udp_attempts(config[CONF_UDP_ATTEMPTS]))
    cg.add(
        var.set_udp_initial_backoff_ms(
            config[CONF_UDP_INITIAL_BACKOFF].total_milliseconds
        )
    )
    cg.add(
        var.set_mdns_timeout_ms(config[CONF_MDNS_TIMEOUT].total_milliseconds)
    )
    cg.add(
        var.set_http_timeout_ms(config[CONF_HTTP_TIMEOUT].total_milliseconds)
    )
    cg.add(var.set_response_max_bytes(config[CONF_RESPONSE_MAX_BYTES]))
