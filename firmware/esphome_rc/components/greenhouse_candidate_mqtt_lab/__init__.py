from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

AUTO_LOAD = ["greenhouse_pairing_client"]
DEPENDENCIES = ["esp32"]

CONF_PROBE_TIMEOUT = "probe_timeout"


greenhouse_candidate_mqtt_lab_ns = cg.esphome_ns.namespace(
    "greenhouse_candidate_mqtt_lab"
)
GreenhouseCandidateMqttLab = greenhouse_candidate_mqtt_lab_ns.class_(
    "GreenhouseCandidateMqttLab", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseCandidateMqttLab),
        cv.Optional(CONF_PROBE_TIMEOUT, default="15s"): cv.All(
            cv.positive_time_period_milliseconds,
            cv.Range(min=cv.TimePeriod(milliseconds=1000), max=cv.TimePeriod(seconds=60)),
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    # The adapter owns a second esp_mqtt_client_handle_t. Loading the built-in
    # ESP-IDF mqtt component only supplies compile/link support; setup does not
    # create a client or contact a Broker.
    include_builtin_idf_component("mqtt")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_probe_timeout_ms(config[CONF_PROBE_TIMEOUT].total_milliseconds))
