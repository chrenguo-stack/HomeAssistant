from __future__ import annotations

import base64
import copy
import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from typing import Any

RECOVERY_SCHEMA = "gh.m2.t1-provisioning-control-identity-recovery/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-provisioning-control-identity-recovery-authorization/1"


class ProvisioningControlIdentityRecoveryError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def generate_recovery_password(
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> str:
    material = random_bytes(32)
    if len(material) != 32:
        raise ProvisioningControlIdentityRecoveryError(
            "password generator must return exactly 32 bytes"
        )
    return base64.urlsafe_b64encode(material).rstrip(b"=").decode("ascii")


def _clients(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    clients = state.get("clients")
    if not isinstance(clients, list):
        raise ProvisioningControlIdentityRecoveryError(
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
        raise ProvisioningControlIdentityRecoveryError(
            "exactly one provisioning client is required"
        )
    return matches[0]


def _role_names(client: Mapping[str, Any]) -> list[str]:
    roles = client.get("roles")
    if not isinstance(roles, list):
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning role binding is missing"
        )
    return [
        role["rolename"]
        for role in roles
        if isinstance(role, Mapping) and isinstance(role.get("rolename"), str)
    ]


def require_exact_control_identity(
    state: Mapping[str, Any],
    *,
    username: str,
    client_id: str,
    role_name: str,
) -> dict[str, object]:
    client = _target_client(state, username=username)
    if client.get("clientid") != client_id:
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning client id does not match"
        )
    if client.get("disabled") is True:
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning client is disabled"
        )
    role_names = _role_names(client)
    if role_names != [role_name]:
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning role binding does not match"
        )
    encoded_password = client.get("encoded_password")
    if not isinstance(encoded_password, str) or not encoded_password:
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning encoded password is missing"
        )
    if any(field in client for field in ("password", "salt", "iterations")):
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning credential representation is ambiguous"
        )
    return {
        "identity_exact": True,
        "username_fingerprint": fingerprint(username),
        "client_id_fingerprint": fingerprint(client_id),
        "role_fingerprint": fingerprint(role_name),
        "credential_state_field": "encoded_password",
    }


def extract_isolated_encoded_password(
    isolated_state: Mapping[str, Any],
    *,
    username: str,
) -> str:
    client = _target_client(isolated_state, username=username)
    encoded_password = client.get("encoded_password")
    if not isinstance(encoded_password, str) or not encoded_password:
        raise ProvisioningControlIdentityRecoveryError(
            "isolated encoded password is missing"
        )
    if any(field in client for field in ("password", "salt", "iterations")):
        raise ProvisioningControlIdentityRecoveryError(
            "isolated credential representation is ambiguous"
        )
    return encoded_password


def build_candidate_state(
    live_state: Mapping[str, Any],
    *,
    username: str,
    encoded_password: str,
) -> dict[str, Any]:
    if not encoded_password:
        raise ProvisioningControlIdentityRecoveryError(
            "replacement encoded password is empty"
        )
    candidate = copy.deepcopy(dict(live_state))
    clients = candidate.get("clients")
    if not isinstance(clients, list):
        raise ProvisioningControlIdentityRecoveryError(
            "Dynamic Security client inventory is missing"
        )
    matches = 0
    for client in clients:
        if not isinstance(client, dict) or client.get("username") != username:
            continue
        matches += 1
        if not isinstance(client.get("encoded_password"), str):
            raise ProvisioningControlIdentityRecoveryError(
                "provisioning encoded password is missing"
            )
        client["encoded_password"] = encoded_password
    if matches != 1:
        raise ProvisioningControlIdentityRecoveryError(
            "exactly one provisioning client is required"
        )
    return candidate


def _normalized_without_target_credential(
    state: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(state))
    clients = normalized.get("clients")
    if not isinstance(clients, list):
        raise ProvisioningControlIdentityRecoveryError(
            "Dynamic Security client inventory is missing"
        )
    matches = 0
    for client in clients:
        if not isinstance(client, dict) or client.get("username") != username:
            continue
        matches += 1
        encoded_password = client.get("encoded_password")
        if not isinstance(encoded_password, str) or not encoded_password:
            raise ProvisioningControlIdentityRecoveryError(
                "provisioning encoded password is missing"
            )
        client["encoded_password"] = "<provisioning-recovery-field>"
    if matches != 1:
        raise ProvisioningControlIdentityRecoveryError(
            "exactly one provisioning client is required"
        )
    return normalized


def verify_password_only_candidate(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, object]:
    before_client = _target_client(before, username=username)
    after_client = _target_client(after, username=username)
    before_value = before_client.get("encoded_password")
    after_value = after_client.get("encoded_password")
    if not isinstance(before_value, str) or not isinstance(after_value, str):
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning encoded password is missing"
        )
    if before_value == after_value:
        raise ProvisioningControlIdentityRecoveryError(
            "provisioning credential material did not change"
        )
    if _normalized_without_target_credential(
        before,
        username=username,
    ) != _normalized_without_target_credential(after, username=username):
        raise ProvisioningControlIdentityRecoveryError(
            "Dynamic Security state changed outside provisioning credential material"
        )
    return {
        "credential_material_changed": True,
        "non_credential_state_unchanged": True,
        "credential_state_field": "encoded_password",
        "before_credential_fingerprint": fingerprint(before_value),
        "after_credential_fingerprint": fingerprint(after_value),
    }


def build_authorization_record(
    *,
    repository_sha: str,
    manager_source_version: str,
    operator_statement_fingerprint: str,
) -> dict[str, object]:
    if len(repository_sha) != 40 or not manager_source_version:
        raise ProvisioningControlIdentityRecoveryError(
            "recovery authorization binding is incomplete"
        )
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorized": True,
        "scope": "provisioning_control_identity_password_recovery",
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "operator_statement_fingerprint": operator_statement_fingerprint,
        "offline_target_password_replacement_authorized": True,
        "mosquitto_restart_authorized": True,
        "automatic_rollback_authorized": True,
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


def sanitized_recovery_report(
    *,
    repository_sha: str,
    manager_source_version: str,
    identity: Mapping[str, object],
    state_change: Mapping[str, object],
    rollback_available: bool,
) -> dict[str, object]:
    return {
        "schema": RECOVERY_SCHEMA,
        "status": "provisioning_control_identity_recovery_succeeded",
        "recovery_committed": True,
        "identity": dict(identity),
        "state_change": dict(state_change),
        "replacement_control_identity_verified": True,
        "wrong_client_id_rejected": True,
        "rollback_available": rollback_available,
        "mosquitto_restart_performed": True,
        "other_protected_services_restarted": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "node_credentials_delivered": False,
        "manager_identity_modified": False,
        "production_manager_upgraded": False,
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "secret_values_included": False,
        "source_paths_included": False,
        "path_values_redacted": True,
        "ready_for_homeassistant_password_rotation": True,
        "ready_for_anonymous_closure": False,
    }
