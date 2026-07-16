from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from . import t1_homeassistant_mqtt_credential_rotation as _v1

ROTATION_SCHEMA = _v1.ROTATION_SCHEMA
AUTHORIZATION_SCHEMA = _v1.AUTHORIZATION_SCHEMA
HANDOFF_SCHEMA = _v1.HANDOFF_SCHEMA
CONTROL_TOPIC = _v1.CONTROL_TOPIC
RESPONSE_TOPIC = _v1.RESPONSE_TOPIC
HomeAssistantMqttCredentialRotationError = (
    _v1.HomeAssistantMqttCredentialRotationError
)
ProvisioningOptions = _v1.ProvisioningOptions
fingerprint = _v1.fingerprint
canonical_json = _v1.canonical_json
generate_rotation_password = _v1.generate_rotation_password
parse_mosquitto_options = _v1.parse_mosquitto_options
require_provisioning_identity = _v1.require_provisioning_identity
build_control_request = _v1.build_control_request
build_get_client_request = _v1.build_get_client_request
build_set_client_password_request = _v1.build_set_client_password_request
decode_control_response = _v1.decode_control_response
build_reconfigure_values = _v1.build_reconfigure_values
build_authorization_record = _v1.build_authorization_record
sanitized_rotation_report = _v1.sanitized_rotation_report

_CREDENTIAL_FIELDS = ("encoded_password", "password")
_REDACTED_CREDENTIAL_VALUE = "<credential-rotation-field>"


def _clients(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    clients = state.get("clients")
    if not isinstance(clients, list):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security client inventory is missing"
        )
    return [dict(item) for item in clients if isinstance(item, Mapping)]


def _target_client(
    state: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    matches = [
        client for client in _clients(state) if client.get("username") == username
    ]
    if len(matches) != 1:
        raise HomeAssistantMqttCredentialRotationError(
            "exactly one target Dynamic Security client is required"
        )
    return matches[0]


def _credential_field_and_value(
    client: Mapping[str, Any],
) -> tuple[str, Any]:
    present = [field for field in _CREDENTIAL_FIELDS if field in client]
    if len(present) != 1:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security credential field is missing or ambiguous"
        )
    field = present[0]
    value = client[field]
    if value is None or value == "" or value == [] or value == {}:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security credential material is empty"
        )
    try:
        canonical_json(value)
    except (TypeError, ValueError) as error:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security credential material is not JSON-compatible"
        ) from error
    return field, value


def credential_material_fingerprint(
    state: Mapping[str, Any],
    *,
    username: str,
) -> tuple[str, str]:
    client = _target_client(state, username=username)
    field, value = _credential_field_and_value(client)
    return field, fingerprint(canonical_json(value))


def password_hash_fingerprint(
    state: Mapping[str, Any],
    *,
    username: str,
) -> str:
    _field, material_fingerprint = credential_material_fingerprint(
        state,
        username=username,
    )
    return material_fingerprint


def normalize_state_for_password_rotation(
    state: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(state))
    clients = normalized.get("clients")
    if not isinstance(clients, list):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security client inventory is missing"
        )
    matches = 0
    for client in clients:
        if not isinstance(client, dict) or client.get("username") != username:
            continue
        matches += 1
        field, _value = _credential_field_and_value(client)
        client[field] = _REDACTED_CREDENTIAL_VALUE
    if matches != 1:
        raise HomeAssistantMqttCredentialRotationError(
            "exactly one target Dynamic Security client is required"
        )
    return normalized


def verify_password_only_state_change(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, object]:
    before_field, before_fingerprint = credential_material_fingerprint(
        before,
        username=username,
    )
    after_field, after_fingerprint = credential_material_fingerprint(
        after,
        username=username,
    )
    if before_field != after_field:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security credential field changed"
        )
    if before_fingerprint == after_fingerprint:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security credential material did not change"
        )
    if normalize_state_for_password_rotation(
        before,
        username=username,
    ) != normalize_state_for_password_rotation(after, username=username):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security state changed outside the target credential material"
        )
    return {
        "password_hash_changed": True,
        "non_password_state_unchanged": True,
        "credential_material_changed": True,
        "non_credential_state_unchanged": True,
        "credential_state_field": before_field,
        "before_password_hash_fingerprint": before_fingerprint,
        "after_password_hash_fingerprint": after_fingerprint,
    }
