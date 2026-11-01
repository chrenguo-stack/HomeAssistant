from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

AUTO_LOAD = ["greenhouse_pairing_client"]
DEPENDENCIES = ["esp32"]


greenhouse_profile_lifecycle_lab_ns = cg.esphome_ns.namespace(
    "greenhouse_profile_lifecycle_lab"
)
GreenhouseProfileLifecycleLab = greenhouse_profile_lifecycle_lab_ns.class_(
    "GreenhouseProfileLifecycleLab", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {cv.GenerateID(): cv.declare_id(GreenhouseProfileLifecycleLab)}
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
