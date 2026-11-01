from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv

AUTO_LOAD = [
    "greenhouse_profile_isolated_acceptance",
    "greenhouse_profile_production_adapters",
]
DEPENDENCIES = ["esp32"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config: dict) -> None:
    # Stage 2D-8 compiles the physical-port implementation but creates no
    # runtime object and exposes no startup hook, command transport, NVS open,
    # MQTT connection, write grant, or cleanup action. A later exact execution
    # manifest must bind the dedicated board, test partition, Broker and three
    # one-shot authorizations before this code may be instantiated.
    cg.add_define("USE_GREENHOUSE_PROFILE_ISOLATED_DEVICE_DRIVER")
