from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv

AUTO_LOAD = ["greenhouse_profile_lifecycle_controller"]
DEPENDENCIES = ["esp32"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config: dict) -> None:
    # Stage 2D-7 is compile-only. It deliberately creates no driver, NVS
    # backend, MQTT client, command transport, startup hook, button, switch,
    # script, or write authorization. Stage 2D-8 must provide an explicitly
    # reviewed isolated-device binding before any runtime test can exist.
    cg.add_define("USE_GREENHOUSE_PROFILE_ISOLATED_ACCEPTANCE")
