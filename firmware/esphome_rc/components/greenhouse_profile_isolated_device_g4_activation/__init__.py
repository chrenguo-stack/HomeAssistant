from __future__ import annotations

import esphome.config_validation as cv
from esphome.components.esp32 import add_idf_component, include_builtin_idf_component

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_EXECUTION_GATE = "execution_gate"

_STAGE2D10_PARTITION = "gh2d8_p2d9"
_STAGE2D10_NAMESPACE = "gh2d8_s2d9"
_LOCKED_GATE = "LOCKED"


def _exact(value: object, expected: str, field: str) -> str:
    candidate = cv.string_strict(value)
    if candidate != expected:
        raise cv.Invalid(f"{field} must be {expected}")
    return candidate


def _partition(value: object) -> str:
    return _exact(value, _STAGE2D10_PARTITION, CONF_PARTITION_LABEL)


def _namespace(value: object) -> str:
    return _exact(value, _STAGE2D10_NAMESPACE, CONF_NAMESPACE_NAME)


def _execution_gate(value: object) -> str:
    return _exact(value, _LOCKED_GATE, CONF_EXECUTION_GATE)


AUTO_LOAD = [
    "greenhouse_pairing_client",
    "greenhouse_profile_isolated_acceptance",
    "greenhouse_profile_isolated_device_driver",
]
DEPENDENCIES = ["esp32", "logger"]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_PARTITION_LABEL): _partition,
        cv.Required(CONF_NAMESPACE_NAME): _namespace,
        cv.Required(CONF_EXECUTION_GATE): _execution_gate,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    del config
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("mqtt")
    include_builtin_idf_component("esp_hw_support")
    add_idf_component(name="espressif/mdns", ref="1.11.0")
