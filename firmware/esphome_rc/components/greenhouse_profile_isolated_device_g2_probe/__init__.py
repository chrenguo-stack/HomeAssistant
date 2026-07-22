from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_BUILD_BINDING = "build_binding"

_SAFE_STORAGE_NAME = re.compile(r"^gh2d8_[A-Za-z0-9_]{1,8}$")
_SAFE_BINDING = re.compile(r"^[0-9a-f]{40}$")


def _storage_name(value: object) -> str:
    candidate = cv.string_strict(value)
    if _SAFE_STORAGE_NAME.fullmatch(candidate) is None or len(candidate) > 15:
        raise cv.Invalid(
            "Stage2D8 storage names must begin with gh2d8_, use only safe ASCII, "
            "and be at most 15 characters"
        )
    return candidate


def _build_binding(value: object) -> str:
    candidate = cv.string_strict(value).lower()
    if _SAFE_BINDING.fullmatch(candidate) is None:
        raise cv.Invalid("build_binding must be an exact lowercase 40-hex commit SHA")
    return candidate


def _validate_distinct(config: dict) -> dict:
    if config[CONF_PARTITION_LABEL] == config[CONF_NAMESPACE_NAME]:
        raise cv.Invalid("partition_label and namespace_name must be distinct")
    return config


AUTO_LOAD = [
    "greenhouse_profile_isolated_device_driver",
    "greenhouse_profile_isolated_acceptance",
    "greenhouse_profile_production_adapters",
]
DEPENDENCIES = ["esp32"]

stage2d8_ns = cg.esphome_ns.namespace("greenhouse_pairing_client")
Stage2D8G2ReadOnlyProbe = stage2d8_ns.class_(
    "Stage2D8G2ReadOnlyProbe", cg.Component
)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Stage2D8G2ReadOnlyProbe),
            cv.Required(CONF_PARTITION_LABEL): _storage_name,
            cv.Required(CONF_NAMESPACE_NAME): _storage_name,
            cv.Required(CONF_BUILD_BINDING): _build_binding,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _validate_distinct,
)


async def to_code(config: dict) -> None:
    # The G2 image links the physical implementation but exposes only one
    # automatic read-only inspection. No key, Wi-Fi, MQTT, write grant, command
    # transport, cleanup action or production identifier is compiled in.
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("mqtt")
    include_builtin_idf_component("esp_hw_support")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_partition_label(config[CONF_PARTITION_LABEL]))
    cg.add(var.set_namespace_name(config[CONF_NAMESPACE_NAME]))
    cg.add(var.set_build_binding(config[CONF_BUILD_BINDING]))
