from __future__ import annotations

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.esp32 import include_builtin_idf_component
from esphome.const import CONF_ID
from voluptuous import Invalid

DEPENDENCIES = ["esp32", "wifi", "mqtt"]

CONF_ROLE = "role"
CONF_EXECUTION_ENABLED = "execution_enabled"
CONF_SYSTEM_ID = "system_id"
CONF_NODE_ID = "node_id"
CONF_GATEWAY_ID = "gateway_id"
CONF_PEER_MAC = "peer_mac"
CONF_PMK_HEX = "pmk_hex"
CONF_LMK_HEX = "lmk_hex"
CONF_APP_KEY_EPOCH1_HEX = "app_key_epoch1_hex"
CONF_APP_KEY_EPOCH2_HEX = "app_key_epoch2_hex"
CONF_SESSION_FLOOR = "session_floor"
CONF_PUBLISH_INTERVAL_MS = "publish_interval_ms"

ns = cg.esphome_ns.namespace("greenhouse_n3w_p5_lab")
GreenhouseN3wP5Lab = ns.class_("GreenhouseN3wP5Lab", cg.Component)


def _hex_length(chars: int):
    def validate(value):
        value = cv.string_strict(value)
        if len(value) != chars:
            raise Invalid(f"expected exactly {chars} hexadecimal characters")
        if any(character not in "0123456789abcdefABCDEF" for character in value):
            raise Invalid("expected hexadecimal characters only")
        return value

    return validate


def _peer_mac(value):
    value = cv.string_strict(value)
    if value == "compile-only-peer":
        return value
    try:
        return str(cv.mac_address(value))
    except Invalid as exc:
        raise Invalid("expected a MAC address or the compile-only sentinel") from exc


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(GreenhouseN3wP5Lab),
        cv.Required(CONF_ROLE): cv.one_of("child", "relay", lower=True),
        cv.Optional(CONF_EXECUTION_ENABLED, default=False): cv.boolean,
        cv.Required(CONF_SYSTEM_ID): cv.string_strict,
        cv.Required(CONF_NODE_ID): cv.string_strict,
        cv.Required(CONF_GATEWAY_ID): cv.string_strict,
        cv.Required(CONF_PEER_MAC): _peer_mac,
        cv.Required(CONF_PMK_HEX): _hex_length(32),
        cv.Required(CONF_LMK_HEX): _hex_length(32),
        cv.Optional(CONF_APP_KEY_EPOCH1_HEX, default=""): cv.Any("", _hex_length(64)),
        cv.Optional(CONF_APP_KEY_EPOCH2_HEX, default=""): cv.Any("", _hex_length(64)),
        cv.Optional(CONF_SESSION_FLOOR, default=1): cv.int_range(min=1),
        cv.Optional(CONF_PUBLISH_INTERVAL_MS, default=5000): cv.int_range(
            min=1000, max=60000
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config: dict) -> None:
    include_builtin_idf_component("nvs_flash")
    include_builtin_idf_component("esp_wifi")
    # Re-enable the ESP-IDF mbedTLS component and compile the generated ESPHome
    # src component against the same ESP-IDF mbedTLS configuration as the
    # library itself. Without MBEDTLS_CONFIG_FILE, n3w_core.cpp sees the
    # upstream GCM ABI while ESP-IDF 5.5.4 builds mbedTLS with its ALT ABI.
    include_builtin_idf_component("mbedtls")
    cg.add_build_flag('-DMBEDTLS_CONFIG_FILE=\\"mbedtls/esp_config.h\\"')
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_role(config[CONF_ROLE]))
    cg.add(var.set_execution_enabled(config[CONF_EXECUTION_ENABLED]))
    cg.add(var.set_system_id(config[CONF_SYSTEM_ID]))
    cg.add(var.set_node_id(config[CONF_NODE_ID]))
    cg.add(var.set_gateway_id(config[CONF_GATEWAY_ID]))
    cg.add(var.set_peer_mac(str(config[CONF_PEER_MAC])))
    cg.add(var.set_pmk_hex(config[CONF_PMK_HEX]))
    cg.add(var.set_lmk_hex(config[CONF_LMK_HEX]))
    cg.add(var.set_app_key_epoch1_hex(config[CONF_APP_KEY_EPOCH1_HEX]))
    cg.add(var.set_app_key_epoch2_hex(config[CONF_APP_KEY_EPOCH2_HEX]))
    cg.add(var.set_session_floor(config[CONF_SESSION_FLOOR]))
    cg.add(var.set_publish_interval_ms(config[CONF_PUBLISH_INTERVAL_MS]))
