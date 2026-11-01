from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import (
    add_idf_component,
    add_idf_sdkconfig_option,
    idf_version,
    include_builtin_idf_component,
)

AUTO_LOAD = ["greenhouse_pairing_client"]
DEPENDENCIES = ["esp32"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config: dict) -> None:
    # Stage 2D-5 compiles the production adapters but does not construct them,
    # open NVS, start an MQTT client, or register an automatic lifecycle action.
    if idf_version() >= cv.Version(6, 0, 0):
        add_idf_component(name="espressif/mqtt", ref="1.0.0")
    else:
        include_builtin_idf_component("mqtt")
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_hw_support")

    add_idf_sdkconfig_option("CONFIG_MBEDTLS_CHACHA20_C", True)
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_POLY1305_C", True)
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_CHACHAPOLY_C", True)
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_HARDWARE_MPI", False)
    cg.add_define("USE_GREENHOUSE_PROFILE_PRODUCTION_ADAPTERS")
