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
    # P4b compiles the ESP-NOW/Wi-Fi driver and radio policy, but the component
    # remains inert: setup() does not initialize Wi-Fi/ESP-NOW, provision keys,
    # transmit packets, connect a Broker, or activate a product firmware path.
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_wifi")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
