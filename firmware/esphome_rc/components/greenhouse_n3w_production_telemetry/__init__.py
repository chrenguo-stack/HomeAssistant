from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor, sensor
from esphome.const import CONF_ID

DEPENDENCIES = ["greenhouse_n3w_core", "sensor", "binary_sensor"]
AUTO_LOAD = ["json"]

CONF_N3W_CORE_ID = "n3w_core_id"
CONF_CAP_HASH = "cap_hash"
CONF_FW_VERSION = "fw_version"
CONF_AIR_TEMPERATURE_ID = "air_temperature_id"
CONF_AIR_HUMIDITY_ID = "air_humidity_id"
CONF_CO2_ID = "co2_id"
CONF_ILLUMINANCE_ID = "illuminance_id"
CONF_SOIL_TEMPERATURE_ID = "soil_temperature_id"
CONF_SOIL_MOISTURE_ID = "soil_moisture_id"
CONF_SOIL_EC_ID = "soil_ec_id"
CONF_VPD_ID = "vpd_id"
CONF_DEW_POINT_ID = "dew_point_id"
CONF_ABSOLUTE_HUMIDITY_ID = "absolute_humidity_id"
CONF_PPFD_ID = "ppfd_id"
CONF_DLI_TODAY_ID = "dli_today_id"
CONF_DLI_YESTERDAY_ID = "dli_yesterday_id"
CONF_BATTERY_VOLTAGE_ID = "battery_voltage_id"
CONF_BATTERY_LEVEL_ID = "battery_level_id"
CONF_MAIN_POWER_ID = "main_power_id"
CONF_LOW_BATTERY_ID = "low_battery_id"

core_ns = cg.esphome_ns.namespace("greenhouse_n3w_core")
GreenhouseN3wCore = core_ns.class_("GreenhouseN3wCore", cg.Component)

ns = cg.esphome_ns.namespace("greenhouse_n3w_production_telemetry")
GreenhouseN3wProductionTelemetry = ns.class_(
    "GreenhouseN3wProductionTelemetry",
    cg.PollingComponent,
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wProductionTelemetry),
        cv.Required(CONF_N3W_CORE_ID): cv.use_id(GreenhouseN3wCore),
        cv.Required(CONF_CAP_HASH): cv.string_strict,
        cv.Required(CONF_FW_VERSION): cv.string_strict,
        cv.Required(CONF_AIR_TEMPERATURE_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_AIR_HUMIDITY_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_CO2_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_ILLUMINANCE_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_SOIL_TEMPERATURE_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_SOIL_MOISTURE_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_SOIL_EC_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_VPD_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_DEW_POINT_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_ABSOLUTE_HUMIDITY_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_PPFD_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_DLI_TODAY_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_DLI_YESTERDAY_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_BATTERY_VOLTAGE_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_BATTERY_LEVEL_ID): cv.use_id(sensor.Sensor),
        cv.Required(CONF_MAIN_POWER_ID): cv.use_id(binary_sensor.BinarySensor),
        cv.Required(CONF_LOW_BATTERY_ID): cv.use_id(binary_sensor.BinarySensor),
    }
).extend(cv.polling_component_schema("5s"))


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    core = await cg.get_variable(config[CONF_N3W_CORE_ID])
    cg.add(var.set_core(core))
    cg.add(var.set_cap_hash(config[CONF_CAP_HASH]))
    cg.add(var.set_fw_version(config[CONF_FW_VERSION]))

    bindings = (
        (CONF_AIR_TEMPERATURE_ID, "set_air_temperature"),
        (CONF_AIR_HUMIDITY_ID, "set_air_humidity"),
        (CONF_CO2_ID, "set_co2"),
        (CONF_ILLUMINANCE_ID, "set_illuminance"),
        (CONF_SOIL_TEMPERATURE_ID, "set_soil_temperature"),
        (CONF_SOIL_MOISTURE_ID, "set_soil_moisture"),
        (CONF_SOIL_EC_ID, "set_soil_ec"),
        (CONF_VPD_ID, "set_vpd"),
        (CONF_DEW_POINT_ID, "set_dew_point"),
        (CONF_ABSOLUTE_HUMIDITY_ID, "set_absolute_humidity"),
        (CONF_PPFD_ID, "set_ppfd"),
        (CONF_DLI_TODAY_ID, "set_dli_today"),
        (CONF_DLI_YESTERDAY_ID, "set_dli_yesterday"),
        (CONF_BATTERY_VOLTAGE_ID, "set_battery_voltage"),
        (CONF_BATTERY_LEVEL_ID, "set_battery_level"),
        (CONF_MAIN_POWER_ID, "set_main_power"),
        (CONF_LOW_BATTERY_ID, "set_low_battery"),
    )
    for config_key, setter in bindings:
        entity = await cg.get_variable(config[config_key])
        cg.add(getattr(var, setter)(entity))
