from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import add_idf_component, include_builtin_idf_component
from esphome.const import CONF_ID

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_BUILD_BINDING = "build_binding"
CONF_UNLOCK_DIGEST = "unlock_digest"
CONF_CA_PEM_SHA256 = "ca_pem_sha256"

_STAGE2D9R_PARTITION = "gh2d8_p2d9"
_STAGE2D9R_NAMESPACE = "gh2d8_s2d9"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _exact(value: object, expected: str, field: str) -> str:
    candidate = cv.string_strict(value)
    if candidate != expected:
        raise cv.Invalid(f"{field} must be {expected}")
    return candidate


def _partition(value: object) -> str:
    return _exact(value, _STAGE2D9R_PARTITION, CONF_PARTITION_LABEL)


def _namespace(value: object) -> str:
    return _exact(value, _STAGE2D9R_NAMESPACE, CONF_NAMESPACE_NAME)


def _hex(value: object, pattern: re.Pattern[str], field: str) -> str:
    candidate = cv.string_strict(value).lower()
    if pattern.fullmatch(candidate) is None:
        raise cv.Invalid(f"{field} has invalid hexadecimal shape")
    return candidate


AUTO_LOAD = [
    "greenhouse_profile_isolated_device_g3_prepare",
    "greenhouse_profile_isolated_device_driver",
    "greenhouse_profile_isolated_acceptance",
    "greenhouse_profile_production_adapters",
]
DEPENDENCIES = ["esp32", "logger"]

stage2d9r_ns = cg.esphome_ns.namespace("greenhouse_pairing_client")
Stage2D9RG3RPrepareExecutorV1 = stage2d9r_ns.class_(
    "Stage2D9RG3RPrepareExecutorV1", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(Stage2D9RG3RPrepareExecutorV1),
        cv.Required(CONF_PARTITION_LABEL): _partition,
        cv.Required(CONF_NAMESPACE_NAME): _namespace,
        cv.Required(CONF_BUILD_BINDING): lambda value: _hex(
            value, _HEX40, CONF_BUILD_BINDING
        ),
        cv.Required(CONF_UNLOCK_DIGEST): lambda value: _hex(
            value, _HEX64, CONF_UNLOCK_DIGEST
        ),
        cv.Required(CONF_CA_PEM_SHA256): lambda value: _hex(
            value, _HEX64, CONF_CA_PEM_SHA256
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("mqtt")
    include_builtin_idf_component("esp_hw_support")
    add_idf_component(name="espressif/mdns", ref="1.11.0")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_partition_label(config[CONF_PARTITION_LABEL]))
    cg.add(var.set_namespace_name(config[CONF_NAMESPACE_NAME]))
    cg.add(var.set_build_binding(config[CONF_BUILD_BINDING]))
    cg.add(var.set_unlock_digest(config[CONF_UNLOCK_DIGEST]))
    cg.add(var.set_ca_pem_sha256(config[CONF_CA_PEM_SHA256]))
