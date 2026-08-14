"""N3-W Product Completion S3/S4 board integration."""

from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID
from voluptuous import Invalid

DEPENDENCIES = ["esp32", "greenhouse_n3w_core", "greenhouse_n3w_product_core"]

CONF_EXECUTION_ENABLED = "execution_enabled"
CONF_ROLE = "role"
CONF_PMK_HEX = "pmk_hex"
CONF_LAST_DIRECT_CHANNEL = "last_direct_channel"

ns = cg.esphome_ns.namespace("greenhouse_n3w_product_runtime")
GreenhouseN3wProductIntegration = ns.class_(
    "GreenhouseN3wProductIntegration", cg.Component
)


def _link_key(value: object) -> str:
    parsed = cv.string_strict(value)
    if len(parsed) != 32 or any(character not in "0123456789abcdefABCDEF" for character in parsed):
        raise Invalid("expected exactly 32 hexadecimal characters")
    if set(parsed) <= {"0"}:
        raise Invalid("link key must not be all zero")
    return parsed


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wProductIntegration),
        cv.Optional(CONF_EXECUTION_ENABLED, default=False): cv.boolean,
        cv.Required(CONF_ROLE): cv.one_of("child", "relay", lower=True),
        cv.Required(CONF_PMK_HEX): _link_key,
        cv.Optional(CONF_LAST_DIRECT_CHANNEL, default=1): cv.int_range(min=1, max=14),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    include_builtin_idf_component("esp_wifi")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_execution_enabled(config[CONF_EXECUTION_ENABLED]))
    cg.add(var.set_role(config[CONF_ROLE]))
    cg.add(var.set_pmk_hex(config[CONF_PMK_HEX]))
    cg.add(var.set_last_direct_channel(config[CONF_LAST_DIRECT_CHANNEL]))
