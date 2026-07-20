from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv

CONF_HARDWARE_ID = "hardware_id"
CONF_PAIRING_ID = "pairing_id"
CONF_PAIRING_SECRET = "pairing_secret"
CONF_MAX_CANDIDATES = "max_candidates"
CONF_CANDIDATE_TTL_CAP = "candidate_ttl_cap"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_BASE64URL_32 = re.compile(r"^[A-Za-z0-9_-]{43}$")


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
        raise cv.Invalid(
            "pairing_secret must be 32-byte unpadded base64url"
        )
    return candidate


def _ttl_cap(value: object):
    period = cv.positive_time_period_seconds(value)
    if period.total_seconds > 3600:
        raise cv.Invalid("candidate_ttl_cap must not exceed 3600 seconds")
    return period


greenhouse_pairing_client_ns = cg.esphome_ns.namespace(
    "greenhouse_pairing_client"
)
GreenhousePairingClient = greenhouse_pairing_client_ns.class_(
    "GreenhousePairingClient", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhousePairingClient),
        cv.Required(CONF_HARDWARE_ID): _safe_id,
        cv.Required(CONF_PAIRING_ID): _uuid,
        # ESPHome masks keys containing "secret" in rendered config output.
        # Committed targets only reference non-production !secret values.
        cv.Required(CONF_PAIRING_SECRET): _pairing_secret,
        cv.Optional(CONF_MAX_CANDIDATES, default=4): cv.int_range(
            min=1, max=16
        ),
        cv.Optional(CONF_CANDIDATE_TTL_CAP, default="120s"): _ttl_cap,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
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
