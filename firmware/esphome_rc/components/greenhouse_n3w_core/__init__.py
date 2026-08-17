from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]

CONF_PHASE4_SOURCE_HARNESS = "phase4_source_harness"

greenhouse_n3w_core_ns = cg.esphome_ns.namespace("greenhouse_n3w_core")
GreenhouseN3wCore = greenhouse_n3w_core_ns.class_("GreenhouseN3wCore", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wCore),
        cv.Optional(CONF_PHASE4_SOURCE_HARNESS, default=False): cv.boolean,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_event")
    include_builtin_idf_component("esp_netif")
    include_builtin_idf_component("esp_wifi")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_phase4_source_harness_enabled(config[CONF_PHASE4_SOURCE_HARNESS]))
