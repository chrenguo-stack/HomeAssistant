from __future__ import annotations

from pathlib import Path

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import (
    add_extra_script,
    add_idf_sdkconfig_option,
    include_builtin_idf_component,
)
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]
AUTO_LOAD = ["json"]

CONF_PRODUCT_RUNTIME = "product_runtime"
CONF_FIRMWARE_VERSION = "firmware_version"
CONF_PHASE4_SOURCE_HARNESS = "phase4_source_harness"
CONF_PHASE4_PRODUCT_RUNTIME = "phase4_product_runtime"
CONF_PHASE4_LAB_DIAGNOSTICS = "phase4_lab_diagnostics"

def _firmware_version(value: object) -> str:
    candidate = cv.string_strict(value)
    if not 1 <= len(candidate) <= 64:
        raise cv.Invalid("firmware_version must be 1-64 characters")
    return candidate


greenhouse_n3w_core_ns = cg.esphome_ns.namespace("greenhouse_n3w_core")
GreenhouseN3wCore = greenhouse_n3w_core_ns.class_("GreenhouseN3wCore", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wCore),
        cv.Optional(CONF_PRODUCT_RUNTIME, default=False): cv.boolean,
        cv.Optional(CONF_FIRMWARE_VERSION, default="phase4-simple"): _firmware_version,
        cv.Optional(CONF_PHASE4_SOURCE_HARNESS, default=False): cv.boolean,
        cv.Optional(CONF_PHASE4_PRODUCT_RUNTIME, default=False): cv.boolean,
        cv.Optional(CONF_PHASE4_LAB_DIAGNOSTICS, default=False): cv.boolean,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    add_extra_script(
        "pre",
        "n3w_tls_server_name_patch.py",
        Path(__file__).with_name("n3w_tls_server_name_patch.py.script"),
    )
    add_extra_script(
        "pre",
        "n3w_mqtt_retarget_barrier_patch.py",
        Path(__file__).with_name("n3w_mqtt_retarget_barrier_patch.py.script"),
    )
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_HKDF_C", True)
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_event")
    include_builtin_idf_component("esp_netif")
    include_builtin_idf_component("esp_wifi")
    include_builtin_idf_component("esp_http_client")
    include_builtin_idf_component("mbedtls")
    cg.add_build_flag('-DMBEDTLS_CONFIG_FILE=\\"mbedtls/esp_config.h\\"')
    production_deharness = (
        config[CONF_PRODUCT_RUNTIME]
        and not config[CONF_PHASE4_SOURCE_HARNESS]
        and not config[CONF_PHASE4_PRODUCT_RUNTIME]
        and not config[CONF_PHASE4_LAB_DIAGNOSTICS]
    )
    if production_deharness:
        cg.add_build_flag("-DGH_N3W_PRODUCTION_DEHARNESS=1")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_product_runtime_enabled(config[CONF_PRODUCT_RUNTIME]))
    cg.add(var.set_pairing_firmware_version(config[CONF_FIRMWARE_VERSION]))
    if not production_deharness:
        cg.add(var.set_phase4_source_harness_enabled(config[CONF_PHASE4_SOURCE_HARNESS]))
        cg.add(var.set_phase4_product_runtime_enabled(config[CONF_PHASE4_PRODUCT_RUNTIME]))
        cg.add(var.set_phase4_lab_diagnostics_enabled(config[CONF_PHASE4_LAB_DIAGNOSTICS]))
