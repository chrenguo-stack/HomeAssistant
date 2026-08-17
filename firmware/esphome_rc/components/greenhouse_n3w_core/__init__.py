from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import (
    add_idf_sdkconfig_option,
    include_builtin_idf_component,
)
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]
AUTO_LOAD = ["json"]

CONF_PHASE4_SOURCE_HARNESS = "phase4_source_harness"
CONF_PHASE4_PRODUCT_RUNTIME = "phase4_product_runtime"

greenhouse_n3w_core_ns = cg.esphome_ns.namespace("greenhouse_n3w_core")
GreenhouseN3wCore = greenhouse_n3w_core_ns.class_("GreenhouseN3wCore", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wCore),
        cv.Optional(CONF_PHASE4_SOURCE_HARNESS, default=False): cv.boolean,
        cv.Optional(CONF_PHASE4_PRODUCT_RUNTIME, default=False): cv.boolean,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_HKDF_C", True)
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_event")
    include_builtin_idf_component("esp_netif")
    include_builtin_idf_component("esp_wifi")
    include_builtin_idf_component("esp_http_client")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_phase4_source_harness_enabled(config[CONF_PHASE4_SOURCE_HARNESS]))
    cg.add(var.set_phase4_product_runtime_enabled(config[CONF_PHASE4_PRODUCT_RUNTIME]))
