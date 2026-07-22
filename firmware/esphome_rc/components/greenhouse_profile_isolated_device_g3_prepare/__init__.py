from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import add_idf_component, include_builtin_idf_component
from esphome.const import CONF_ID

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_BUILD_BINDING = "build_binding"

_STAGE2D9_PARTITION = "gh2d8_p2d9"
_STAGE2D9_NAMESPACE = "gh2d8_s2d9"
_SAFE_BINDING = re.compile(r"^[0-9a-f]{40}$")


def _exact_partition(value: object) -> str:
    candidate = cv.string_strict(value)
    if candidate != _STAGE2D9_PARTITION:
        raise cv.Invalid(f"partition_label must be {_STAGE2D9_PARTITION}")
    return candidate


def _exact_namespace(value: object) -> str:
    candidate = cv.string_strict(value)
    if candidate != _STAGE2D9_NAMESPACE:
        raise cv.Invalid(f"namespace_name must be {_STAGE2D9_NAMESPACE}")
    return candidate


def _build_binding(value: object) -> str:
    candidate = cv.string_strict(value).lower()
    if _SAFE_BINDING.fullmatch(candidate) is None:
        raise cv.Invalid("build_binding must be an exact lowercase 40-hex commit SHA")
    return candidate


AUTO_LOAD = [
    "greenhouse_profile_isolated_device_driver",
    "greenhouse_profile_isolated_acceptance",
    "greenhouse_profile_production_adapters",
]
DEPENDENCIES = ["esp32"]

stage2d9_ns = cg.esphome_ns.namespace("greenhouse_pairing_client")
Stage2D9G3LockedPrepareHarness = stage2d9_ns.class_(
    "Stage2D9G3LockedPrepareHarness", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(Stage2D9G3LockedPrepareHarness),
        cv.Required(CONF_PARTITION_LABEL): _exact_partition,
        cv.Required(CONF_NAMESPACE_NAME): _exact_namespace,
        cv.Required(CONF_BUILD_BINDING): _build_binding,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    # The public P3/P4 harness exposes no command transport and performs only an
    # automatic read-only inspection. The test partition is writable-capable for
    # a future exact D2 execution, but this image never loads a key, arms PREPARE,
    # calls prepare_candidate(), starts MQTT, activates, or cleans state.
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("mqtt")
    include_builtin_idf_component("esp_hw_support")

    # The inherited Stage2D8 physical-port translation unit contains dormant MQTT
    # adapters and a shared mDNS include. Link dependencies only; do not create a
    # network component or any MQTT session object in this harness.
    add_idf_component(name="espressif/mdns", ref="1.11.0")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_partition_label(config[CONF_PARTITION_LABEL]))
    cg.add(var.set_namespace_name(config[CONF_NAMESPACE_NAME]))
    cg.add(var.set_build_binding(config[CONF_BUILD_BINDING]))
