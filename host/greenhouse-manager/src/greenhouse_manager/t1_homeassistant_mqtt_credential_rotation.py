from __future__ import annotations

import base64
import copy
import hashlib
import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

ROTATION_SCHEMA = "gh.m2.t1-homeassistant-mqtt-credential-rotation/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-homeassistant-mqtt-credential-rotation-authorization/1"
HANDOFF_SCHEMA = "gh.m2.homeassistant-mqtt-reconfigure-values/1"
CONTROL_TOPIC = "$CONTROL/dynamic-security/v1"
RESPONSE_TOPIC = "$CONTROL/dynamic-security/v1/response"


class HomeAssistantMqttCredentialRotationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class ProvisioningOptions:
    host: str
    username: str
    password: str
    client_id: str
    protocol: str

    def __repr__(self) -> str:
        return (
            "ProvisioningOptions("
            "host=<redacted>,username=<redacted>,password=<redacted>,"
            "client_id=<redacted>,protocol="
            f"{self.protocol!r})"
        )

    @property
    def binding_fingerprint(self) -> str:
        return fingerprint(
            "\0".join(
                (
                    self.host,
                    self.username,
                    self.password,
                    self.client_id,
                    self.protocol,
                )
            )
        )


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def generate_rotation_password(
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> str:
    material = random_bytes(32)
    if len(material) != 32:
        raise HomeAssistantMqttCredentialRotationError(
            "password generator must return exactly 32 bytes"
        )
    return base64.urlsafe_b64encode(material).rstrip(b"=").decode("ascii")


def parse_mosquitto_options(text: str) -> ProvisioningOptions:
    values: dict[str, str] = {}
    aliases = {
        "-h": "host",
        "--host": "host",
        "-u": "username",
        "--username": "username",
        "-P": "password",
        "--pw": "password",
        "-i": "client_id",
        "--id": "client_id",
        "-V": "protocol",
        "--protocol-version": "protocol",
    }
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        option, separator, value = line.partition(" ")
        key = aliases.get(option)
        if key is None or not separator or not value.strip():
            raise HomeAssistantMqttCredentialRotationError(
                "provisioning options contain unsupported or incomplete entries"
            )
        if key in values:
            raise HomeAssistantMqttCredentialRotationError(
                "provisioning options contain duplicate entries"
            )
        values[key] = value.strip()
    required = {"host", "username", "password", "client_id", "protocol"}
    if set(values) != required:
        raise HomeAssistantMqttCredentialRotationError(
            "provisioning options are incomplete"
        )
    if values["protocol"] not in {"5", "mqttv5"}:
        raise HomeAssistantMqttCredentialRotationError(
            "provisioning options must require MQTT v5"
        )
    return ProvisioningOptions(**values)


def require_provisioning_identity(
    options: ProvisioningOptions,
    *,
    system_id: str,
) -> dict[str, object]:
    expected_username = f"ghs_{system_id}_provisioning"
    expected_client_id = f"gh-provisioning-{system_id}"
    if options.username != expected_username or options.client_id != expected_client_id:
        raise HomeAssistantMqttCredentialRotationError(
            "provisioning options do not match the expected identity"
        )
    if options.host not in {"127.0.0.1", "localhost"}:
        raise HomeAssistantMqttCredentialRotationError(
            "provisioning control must use the local Broker"
        )
    return {
        "identity_verified": True,
        "username_fingerprint": fingerprint(expected_username),
        "client_id_fingerprint": fingerprint(expected_client_id),
        "binding_fingerprint": options.binding_fingerprint,
    }


def build_control_request(command: Mapping[str, Any]) -> str:
    name = command.get("command")
    if not isinstance(name, str) or not name:
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security command is missing"
        )
    return canonical_json({"commands": [dict(command)]})


def build_get_client_request(username: str) -> str:
    return build_control_request(
        {"command": "getClient", "username": username}
    )


def build_set_client_password_request(username: str, password: str) -> str:
    if not username or not password:
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security password rotation inputs are incomplete"
        )
    return build_control_request(
        {
            "command": "setClientPassword",
            "username": username,
            "password": password,
        }
    )


def decode_control_response(payload: str, *, expected_command: str) -> dict[str, Any]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security returned invalid JSON"
        ) from error
    responses = document.get("responses") if isinstance(document, dict) else None
    if not isinstance(responses, list) or len(responses) != 1:
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security response count is invalid"
        )
    response = responses[0]
    if (
        not isinstance(response, dict)
        or response.get("command") != expected_command
        or response.get("error")
    ):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security command failed"
        )
    return dict(response)


def _clients(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    clients = state.get("clients")
    if not isinstance(clients, list):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security client inventory is missing"
        )
    return [dict(item) for item in clients if isinstance(item, Mapping)]


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
        if "password" not in client or not isinstance(client["password"], str):
            raise HomeAssistantMqttCredentialRotationError(
                "target Dynamic Security password hash is missing"
            )
        client["password"] = "<password-rotation-field>"
    if matches != 1:
        raise HomeAssistantMqttCredentialRotationError(
            "exactly one target Dynamic Security client is required"
        )
    return normalized


def password_hash_fingerprint(
    state: Mapping[str, Any],
    *,
    username: str,
) -> str:
    matches = [
        client
        for client in _clients(state)
        if client.get("username") == username
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("password"), str):
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security password hash is missing"
        )
    return fingerprint(str(matches[0]["password"]))


def verify_password_only_state_change(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, object]:
    before_hash = password_hash_fingerprint(before, username=username)
    after_hash = password_hash_fingerprint(after, username=username)
    if before_hash == after_hash:
        raise HomeAssistantMqttCredentialRotationError(
            "target Dynamic Security password did not change"
        )
    if normalize_state_for_password_rotation(
        before, username=username
    ) != normalize_state_for_password_rotation(after, username=username):
        raise HomeAssistantMqttCredentialRotationError(
            "Dynamic Security state changed outside the target password"
        )
    return {
        "password_hash_changed": True,
        "non_password_state_unchanged": True,
        "before_password_hash_fingerprint": before_hash,
        "after_password_hash_fingerprint": after_hash,
    }


def build_reconfigure_values(
    *,
    broker: str,
    port: int,
    username: str,
    password: str,
    client_id: str,
    generation: int,
) -> dict[str, object]:
    if (
        not broker
        or not 1 <= port <= 65535
        or not username
        or not password
        or not client_id
        or generation < 1
    ):
        raise HomeAssistantMqttCredentialRotationError(
            "Home Assistant reconfigure values are incomplete"
        )
    return {
        "schema": HANDOFF_SCHEMA,
        "official_config_flow_only": True,
        "broker": broker,
        "port": port,
        "username": username,
        "password": password,
        "client_id": client_id,
        "generation": generation,
        "preserve_discovery": True,
        "advanced_options_required": True,
    }


def build_authorization_record(
    *,
    repository_sha: str,
    manager_source_version: str,
    operator_statement_fingerprint: str,
) -> dict[str, object]:
    if len(repository_sha) != 40 or not manager_source_version:
        raise HomeAssistantMqttCredentialRotationError(
            "rotation authorization binding is incomplete"
        )
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorized": True,
        "scope": "homeassistant_password_only",
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "operator_statement_fingerprint": operator_statement_fingerprint,
        "preserve_username": True,
        "preserve_client_id": True,
        "preserve_role_and_acls": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "node_credentials_delivered": False,
        "homeassistant_storage_access_authorized": False,
        "manager_identity_change_authorized": False,
        "production_manager_upgrade_authorized": False,
    }


def sanitized_rotation_report(
    *,
    repository_sha: str,
    manager_source_version: str,
    provisioning: Mapping[str, object],
    state_change: Mapping[str, object],
    handoff_fingerprint: str,
) -> dict[str, object]:
    return {
        "schema": ROTATION_SCHEMA,
        "status": "homeassistant_mqtt_credential_rotation_succeeded",
        "rotation_committed": True,
        "provisioning_control_verified": True,
        "provisioning": dict(provisioning),
        "state_change": dict(state_change),
        "replacement_identity_verified": True,
        "wrong_client_id_rejected": True,
        "private_handoff_created": True,
        "handoff_fingerprint": handoff_fingerprint,
        "homeassistant_identity_runtime_verified": False,
        "homeassistant_official_reconfigure_pending": True,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "manager_identity_modified": False,
        "production_manager_upgraded": False,
        "current_services_restarted": False,
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "secret_values_included": False,
        "source_paths_included": False,
        "path_values_redacted": True,
        "ready_for_homeassistant_official_reconfigure": True,
        "ready_for_anonymous_closure": False,
    }
