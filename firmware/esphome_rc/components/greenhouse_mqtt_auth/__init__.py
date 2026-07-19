from __future__ import annotations

import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import mqtt
from esphome.const import CONF_ID

DEPENDENCIES = ["mqtt"]

CONF_MQTT_ID = "mqtt_id"
CONF_CANDIDATE_USERNAME = "candidate_username"
CONF_CANDIDATE_PASSWORD = "candidate_password"
CONF_CANDIDATE_CLIENT_ID = "candidate_client_id"
CONF_ANONYMOUS_CLIENT_ID = "anonymous_client_id"
CONF_CANDIDATE_GENERATION = "candidate_generation"
CONF_SECRET_FINGERPRINT = "candidate_secret_fingerprint"
CONF_CANDIDATE_FAILURE_THRESHOLD = "candidate_failure_threshold"
CONF_OBSERVATION_SUCCESS_THRESHOLD = "observation_success_threshold"
CONF_RETRY_COOLDOWN = "retry_cooldown"
CONF_CANDIDATE_LEASE_TIMEOUT = "candidate_lease_timeout"


def _fingerprint(value: object) -> str:
    value = cv.string_strict(value)
    if re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise cv.Invalid(
            "candidate_secret_fingerprint must be 16 lowercase hex characters"
        )
    return value


def _validate_profiles(config: dict) -> dict:
    if config[CONF_CANDIDATE_CLIENT_ID] == config[CONF_ANONYMOUS_CLIENT_ID]:
        raise cv.Invalid("candidate and anonymous Client IDs must differ")
    if not config[CONF_CANDIDATE_USERNAME]:
        raise cv.Invalid("candidate_username must not be empty")
    if not config[CONF_CANDIDATE_PASSWORD]:
        raise cv.Invalid("candidate_password must not be empty")
    return config


greenhouse_mqtt_auth_ns = cg.esphome_ns.namespace("greenhouse_mqtt_auth")
GreenhouseMqttAuth = greenhouse_mqtt_auth_ns.class_(
    "GreenhouseMqttAuth", cg.Component
)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(GreenhouseMqttAuth),
            cv.Required(CONF_MQTT_ID): cv.use_id(mqtt.MQTTClientComponent),
            cv.Required(CONF_CANDIDATE_USERNAME): cv.string_strict,
            # ESPHome 2026.4.3 masks keys containing "password" in config output.
            # Committed examples only reference a non-production !secret value.
            cv.Required(CONF_CANDIDATE_PASSWORD): cv.string_strict,
            cv.Required(CONF_CANDIDATE_CLIENT_ID): cv.All(
                cv.string_strict, cv.Length(min=1, max=23)
            ),
            cv.Required(CONF_ANONYMOUS_CLIENT_ID): cv.All(
                cv.string_strict, cv.Length(min=1, max=23)
            ),
            cv.Optional(CONF_CANDIDATE_GENERATION, default=1): cv.int_range(
                min=1, max=65535
            ),
            cv.Required(CONF_SECRET_FINGERPRINT): _fingerprint,
            cv.Optional(CONF_CANDIDATE_FAILURE_THRESHOLD, default=3): cv.int_range(
                min=1, max=10
            ),
            cv.Optional(
                CONF_OBSERVATION_SUCCESS_THRESHOLD, default=3
            ): cv.int_range(min=1, max=20),
            cv.Optional(
                CONF_RETRY_COOLDOWN, default="300s"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(
                CONF_CANDIDATE_LEASE_TIMEOUT, default="10min"
            ): cv.positive_time_period_milliseconds,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _validate_profiles,
)


async def to_code(config: dict) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    mqtt_client = await cg.get_variable(config[CONF_MQTT_ID])
    cg.add(var.set_mqtt_client(mqtt_client))
    cg.add(var.set_candidate_username(config[CONF_CANDIDATE_USERNAME]))
    cg.add(var.set_candidate_password(config[CONF_CANDIDATE_PASSWORD]))
    cg.add(var.set_candidate_client_id(config[CONF_CANDIDATE_CLIENT_ID]))
    cg.add(var.set_anonymous_client_id(config[CONF_ANONYMOUS_CLIENT_ID]))
    cg.add(var.set_candidate_generation(config[CONF_CANDIDATE_GENERATION]))
    cg.add(var.set_candidate_secret_fingerprint(config[CONF_SECRET_FINGERPRINT]))
    cg.add(
        var.set_candidate_failure_threshold(
            config[CONF_CANDIDATE_FAILURE_THRESHOLD]
        )
    )
    cg.add(
        var.set_observation_success_threshold(
            config[CONF_OBSERVATION_SUCCESS_THRESHOLD]
        )
    )
    cg.add(
        var.set_retry_cooldown_ms(
            config[CONF_RETRY_COOLDOWN].total_milliseconds
        )
    )
    cg.add(
        var.set_candidate_lease_timeout_ms(
            config[CONF_CANDIDATE_LEASE_TIMEOUT].total_milliseconds
        )
    )
