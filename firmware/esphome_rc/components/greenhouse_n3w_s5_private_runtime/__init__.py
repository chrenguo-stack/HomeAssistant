"""Private-package-only S5 runtime composition seam.

The component accepts only this endpoint's own post-registration material. It
has no peer identity or pair-LMK fields and is never referenced by public or
factory profiles.
"""

from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID
from voluptuous import Invalid

DEPENDENCIES = ["greenhouse_n3w_product_runtime"]

CONF_ROLE = "role"
CONF_PRODUCT_RUNTIME_ID = "product_runtime_id"
CONF_MANAGER_TRANSPORT_ID = "manager_transport_id"
CONF_SYSTEM_ID = "system_id"
CONF_NODE_ID = "node_id"
CONF_CREDENTIAL_GENERATION = "credential_generation"
CONF_KEY_EPOCH = "key_epoch"
CONF_APPLICATION_KEY_HEX = "application_key_hex"
CONF_LOCAL_MAC = "local_mac"
CONF_RELAY_CAPABLE = "relay_capable"
CONF_LOW_BATTERY = "low_battery"
CONF_OVERLOADED = "overloaded"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_COMPACT_MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")

ns = cg.esphome_ns.namespace("greenhouse_n3w_s5_private_runtime")
runtime_ns = cg.esphome_ns.namespace("greenhouse_n3w_product_runtime")
manager_ns = cg.esphome_ns.namespace("greenhouse_n3w_s5_manager_transport")

GreenhouseN3wS5PrivateRuntimeMaterial = ns.class_(
    "GreenhouseN3wS5PrivateRuntimeMaterial",
    cg.Component,
)
GreenhouseN3wProductIntegration = runtime_ns.class_(
    "GreenhouseN3wProductIntegration",
    cg.Component,
)
GreenhouseN3wS5ManagerTransportComponent = manager_ns.class_(
    "GreenhouseN3wS5ManagerTransportComponent",
    cg.Component,
)


def _identity(value: object) -> str:
    parsed = cv.string_strict(value)
    if _ID_RE.fullmatch(parsed) is None:
        raise Invalid("expected [A-Za-z0-9_-]{3,64}")
    return parsed


def _application_key(value: object) -> str:
    parsed = cv.string_strict(value)
    if len(parsed) != 64 or any(c not in "0123456789abcdefABCDEF" for c in parsed):
        raise Invalid("application_key_hex must encode exactly 32 bytes")
    if set(parsed) <= {"0"}:
        raise Invalid("application key must be nonzero")
    return parsed.lower()


def _local_mac(value: object) -> str:
    parsed = cv.string_strict(value)
    if _COMPACT_MAC_RE.fullmatch(parsed) is None:
        raise Invalid("local_mac must be exactly 12 hexadecimal characters")
    first = int(parsed[0:2], 16)
    if first & 0x01:
        raise Invalid("local_mac must be unicast")
    if int(parsed, 16) == 0:
        raise Invalid("local_mac must be nonzero")
    return parsed.lower()


def _role_contract(config: dict) -> dict:
    role = config[CONF_ROLE]
    manager_present = CONF_MANAGER_TRANSPORT_ID in config
    if role == "relay" and not manager_present:
        raise Invalid("relay private runtime requires manager_transport_id")
    if role == "child" and manager_present:
        raise Invalid("child private runtime must not bind a Manager transport")
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(GreenhouseN3wS5PrivateRuntimeMaterial),
            cv.Required(CONF_PRODUCT_RUNTIME_ID): cv.use_id(GreenhouseN3wProductIntegration),
            cv.Optional(CONF_MANAGER_TRANSPORT_ID): cv.use_id(
                GreenhouseN3wS5ManagerTransportComponent
            ),
            cv.Required(CONF_ROLE): cv.one_of("child", "relay", lower=True),
            cv.Required(CONF_SYSTEM_ID): _identity,
            cv.Required(CONF_NODE_ID): _identity,
            cv.Required(CONF_CREDENTIAL_GENERATION): cv.int_range(min=1, max=0xFFFFFFFF),
            cv.Required(CONF_KEY_EPOCH): cv.int_range(min=1, max=0xFFFFFFFF),
            cv.Required(CONF_APPLICATION_KEY_HEX): _application_key,
            cv.Required(CONF_LOCAL_MAC): _local_mac,
            cv.Optional(CONF_RELAY_CAPABLE, default=True): cv.boolean,
            cv.Optional(CONF_LOW_BATTERY, default=False): cv.boolean,
            cv.Optional(CONF_OVERLOADED, default=False): cv.boolean,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _role_contract,
)


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_role(config[CONF_ROLE]))
    cg.add(var.set_system_id(config[CONF_SYSTEM_ID]))
    cg.add(var.set_node_id(config[CONF_NODE_ID]))
    cg.add(var.set_credential_generation(config[CONF_CREDENTIAL_GENERATION]))
    cg.add(var.set_key_epoch(config[CONF_KEY_EPOCH]))
    cg.add(var.set_application_key_hex(config[CONF_APPLICATION_KEY_HEX]))
    cg.add(var.set_local_mac(config[CONF_LOCAL_MAC]))
    cg.add(var.set_relay_capable(config[CONF_RELAY_CAPABLE]))
    cg.add(var.set_low_battery(config[CONF_LOW_BATTERY]))
    cg.add(var.set_overloaded(config[CONF_OVERLOADED]))

    integration = await cg.get_variable(config[CONF_PRODUCT_RUNTIME_ID])
    if config[CONF_ROLE] == "child":
        cg.add(var.configure_child(integration))
        return

    manager = await cg.get_variable(config[CONF_MANAGER_TRANSPORT_ID])
    cg.add(manager.configure_private(var, var))
