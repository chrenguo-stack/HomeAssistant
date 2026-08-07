from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]

greenhouse_n3w_core_ns = cg.esphome_ns.namespace("greenhouse_n3w_core")
GreenhouseN3wCore = greenhouse_n3w_core_ns.class_(
    "GreenhouseN3wCore", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wCore),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    # Compile/link support only. This P4a component does not initialize ESP-NOW,
    # connect a Broker, load a production key, or transmit any frame.
    include_builtin_idf_component("nvs_flash")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
