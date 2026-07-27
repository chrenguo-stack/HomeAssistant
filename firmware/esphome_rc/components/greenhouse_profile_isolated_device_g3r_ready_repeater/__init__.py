from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_REPEAT_INTERVAL_MS = "repeat_interval_ms"
CONF_REPEAT_WINDOW_MS = "repeat_window_ms"

_STAGE2D9R_PARTITION = "gh2d8_p2d9"
_STAGE2D9R_NAMESPACE = "gh2d8_s2d9"
_REPEAT_INTERVAL_MS = 1000
_REPEAT_WINDOW_MS = 180000


def _exact_string(value: object, expected: str, field: str) -> str:
    candidate = cv.string_strict(value)
    if candidate != expected:
        raise cv.Invalid(f"{field} must be {expected}")
    return candidate


def _exact_uint(value: object, expected: int, field: str) -> int:
    candidate = cv.positive_int(value)
    if candidate != expected:
        raise cv.Invalid(f"{field} must be {expected}")
    return candidate


DEPENDENCIES = ["esp32", "logger"]

stage2d9r_ns = cg.esphome_ns.namespace("greenhouse_pairing_client")
Stage2D9RG3RReadyRepeaterV1 = stage2d9r_ns.class_(
    "Stage2D9RG3RReadyRepeaterV1", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(Stage2D9RG3RReadyRepeaterV1),
        cv.Required(CONF_PARTITION_LABEL): lambda value: _exact_string(
            value, _STAGE2D9R_PARTITION, CONF_PARTITION_LABEL
        ),
        cv.Required(CONF_NAMESPACE_NAME): lambda value: _exact_string(
            value, _STAGE2D9R_NAMESPACE, CONF_NAMESPACE_NAME
        ),
        cv.Optional(
            CONF_REPEAT_INTERVAL_MS, default=_REPEAT_INTERVAL_MS
        ): lambda value: _exact_uint(
            value, _REPEAT_INTERVAL_MS, CONF_REPEAT_INTERVAL_MS
        ),
        cv.Optional(CONF_REPEAT_WINDOW_MS, default=_REPEAT_WINDOW_MS): lambda value: _exact_uint(
            value, _REPEAT_WINDOW_MS, CONF_REPEAT_WINDOW_MS
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_partition_label(config[CONF_PARTITION_LABEL]))
    cg.add(var.set_namespace_name(config[CONF_NAMESPACE_NAME]))
    cg.add(var.set_repeat_interval_ms(config[CONF_REPEAT_INTERVAL_MS]))
    cg.add(var.set_repeat_window_ms(config[CONF_REPEAT_WINDOW_MS]))
