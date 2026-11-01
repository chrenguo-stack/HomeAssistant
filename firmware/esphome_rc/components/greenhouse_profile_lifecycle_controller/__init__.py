from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv

AUTO_LOAD = ["greenhouse_profile_production_adapters"]
DEPENDENCIES = ["esp32"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config: dict) -> None:
    # Stage 2D-6 compiles the lifecycle assembly only. It does not construct a
    # controller, open NVS, start MQTT, recover at boot, or expose an activation
    # action. Runtime wiring remains a later explicitly authorized stage.
    cg.add_define("USE_GREENHOUSE_PROFILE_LIFECYCLE_CONTROLLER")
