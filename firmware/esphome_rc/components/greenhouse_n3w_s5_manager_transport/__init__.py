"""Opt-in S5 isolated Relay-to-Manager transport compile component."""

from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["mqtt", "greenhouse_n3w_product_runtime"]

CONF_EXECUTION_ENABLED = "execution_enabled"
CONF_PRODUCT_RUNTIME_ID = "product_runtime_id"

ns = cg.esphome_ns.namespace("greenhouse_n3w_s5_manager_transport")
runtime_ns = cg.esphome_ns.namespace("greenhouse_n3w_product_runtime")

GreenhouseN3wS5ManagerTransportComponent = ns.class_(
    "GreenhouseN3wS5ManagerTransportComponent",
    cg.Component,
)
GreenhouseN3wProductIntegration = runtime_ns.class_(
    "GreenhouseN3wProductIntegration",
    cg.Component,
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wS5ManagerTransportComponent),
        cv.Required(CONF_PRODUCT_RUNTIME_ID): cv.use_id(
            GreenhouseN3wProductIntegration
        ),
        cv.Optional(CONF_EXECUTION_ENABLED, default=False): cv.boolean,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    integration = await cg.get_variable(config[CONF_PRODUCT_RUNTIME_ID])
    cg.add(var.set_product_integration(integration))
    cg.add(var.set_execution_enabled(config[CONF_EXECUTION_ENABLED]))
