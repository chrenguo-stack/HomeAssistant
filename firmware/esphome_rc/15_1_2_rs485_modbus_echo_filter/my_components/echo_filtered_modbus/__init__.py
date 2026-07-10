from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import modbus, uart
from esphome.const import (
    CONF_DISABLE_CRC,
    CONF_FLOW_CONTROL_PIN,
    CONF_ID,
)
from esphome.cpp_helpers import gpio_pin_expression

CODEOWNERS = []
DEPENDENCIES = ["uart"]
AUTO_LOAD = ["modbus"]
MULTI_CONF = True

CONF_ECHO_TIMEOUT = "echo_timeout"
CONF_FILTER_FUNCTION_CODES = "filter_function_codes"
CONF_LOG_FILTERED_ECHO = "log_filtered_echo"

echo_filtered_modbus_ns = cg.esphome_ns.namespace("echo_filtered_modbus")
EchoFilteredModbus = echo_filtered_modbus_ns.class_(
    "EchoFilteredModbus", modbus.Modbus
)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(EchoFilteredModbus),
            cv.Optional(modbus.CONF_ROLE, default="client"): cv.enum(
                modbus.MODBUS_ROLES
            ),
            cv.Optional(CONF_FLOW_CONTROL_PIN): pins.gpio_output_pin_schema,
            cv.Optional(
                modbus.CONF_SEND_WAIT_TIME, default="500ms"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(
                modbus.CONF_TURNAROUND_TIME, default="200ms"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_DISABLE_CRC, default=False): cv.boolean,
            cv.Optional(
                CONF_ECHO_TIMEOUT, default="100ms"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(
                CONF_FILTER_FUNCTION_CODES, default=[0x03]
            ): cv.ensure_list(cv.hex_uint8_t),
            cv.Optional(CONF_LOG_FILTERED_ECHO, default=True): cv.boolean,
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(uart.UART_DEVICE_SCHEMA)
)


async def to_code(config):
    cg.add_global(echo_filtered_modbus_ns.using)
    cg.add_global(modbus.modbus_ns.using)

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)

    cg.add(var.set_role(config[modbus.CONF_ROLE]))

    if CONF_FLOW_CONTROL_PIN in config:
        pin = await gpio_pin_expression(config[CONF_FLOW_CONTROL_PIN])
        cg.add(var.set_flow_control_pin(pin))

    cg.add(var.set_send_wait_time(config[modbus.CONF_SEND_WAIT_TIME]))
    cg.add(var.set_turnaround_time(config[modbus.CONF_TURNAROUND_TIME]))
    cg.add(var.set_disable_crc(config[CONF_DISABLE_CRC]))
    cg.add(var.set_echo_timeout(config[CONF_ECHO_TIMEOUT]))
    cg.add(var.set_log_filtered_echo(config[CONF_LOG_FILTERED_ECHO]))

    for function_code in config[CONF_FILTER_FUNCTION_CODES]:
        cg.add(var.add_filter_function_code(function_code))
