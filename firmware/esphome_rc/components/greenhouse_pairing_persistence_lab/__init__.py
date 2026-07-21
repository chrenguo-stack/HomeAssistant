from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID

AUTO_LOAD = ["greenhouse_pairing_client"]
DEPENDENCIES = ["esp32"]

CONF_PARTITION_LABEL = "partition_label"
CONF_NAMESPACE_NAME = "namespace_name"
CONF_HMAC_KEY_ID = "hmac_key_id"

_NVS_NAME = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def _nvs_name(value: object) -> str:
    candidate = cv.string_strict(value)
    if _NVS_NAME.fullmatch(candidate) is None:
        raise cv.Invalid("NVS partition and namespace names must be 1-15 safe ASCII characters")
    return candidate


greenhouse_pairing_persistence_lab_ns = cg.esphome_ns.namespace(
    "greenhouse_pairing_persistence_lab"
)
GreenhousePairingPersistenceLab = greenhouse_pairing_persistence_lab_ns.class_(
    "GreenhousePairingPersistenceLab", cg.Component
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhousePairingPersistenceLab),
        cv.Optional(CONF_PARTITION_LABEL, default="nvs"): _nvs_name,
        cv.Optional(CONF_NAMESPACE_NAME, default="gh_pair_v1"): _nvs_name,
        cv.Optional(CONF_HMAC_KEY_ID, default=0): cv.int_range(min=0, max=5),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_hw_support")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_partition_label(config[CONF_PARTITION_LABEL]))
    cg.add(var.set_namespace_name(config[CONF_NAMESPACE_NAME]))
    cg.add(var.set_hmac_key_id(config[CONF_HMAC_KEY_ID]))
