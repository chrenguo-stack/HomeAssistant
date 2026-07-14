from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "gh.m2.t1-manager-identity-postrollback-audit/1"
AUTHENTICATION_ENVIRONMENT_KEYS = (
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD",
    "GH_MQTT_PASSWORD_FILE",
)

_REQUIRED_OBSERVATIONS: dict[str, object] = {
    "journal_phase": "rollback_completed",
    "rollback_completed": True,
    "rollback_failed": False,
    "auth_overlay_exists": False,
    "auth_environment_exists": False,
    "password_target_exists": False,
    "password_mount_count": 0,
    "created_directory_targets_cleanup_complete": True,
    "manager_running": True,
    "manager_restart_count_zero": True,
    "manager_stable_mqtt_socket": True,
    "manager_image_preserved": True,
    "mosquitto_unchanged": True,
    "homeassistant_unchanged": True,
    "anonymous_retained_path_readable": True,
}


class ManagerPostrollbackAuditError(RuntimeError):
    pass


def redacted_authentication_environment_state(
    environment: Mapping[str, str],
) -> dict[str, dict[str, bool]]:
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()):
        raise ManagerPostrollbackAuditError(
            "manager authentication environment input is invalid"
        )
    return {
        key: {
            "present": key in environment,
            "nonempty": bool(environment.get(key, "")),
        }
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }


def validate_authentication_environment_state(
    state: Mapping[str, Any],
) -> dict[str, dict[str, bool]]:
    if set(state) != set(AUTHENTICATION_ENVIRONMENT_KEYS):
        raise ManagerPostrollbackAuditError(
            "manager authentication environment baseline is incomplete"
        )
    normalized: dict[str, dict[str, bool]] = {}
    for key in AUTHENTICATION_ENVIRONMENT_KEYS:
        item = state.get(key)
        if not isinstance(item, Mapping):
            raise ManagerPostrollbackAuditError(
                "manager authentication environment state is invalid"
            )
        present = item.get("present")
        nonempty = item.get("nonempty")
        if not isinstance(present, bool) or not isinstance(nonempty, bool):
            raise ManagerPostrollbackAuditError(
                "manager authentication environment flags are invalid"
            )
        if nonempty and not present:
            raise ManagerPostrollbackAuditError(
                "manager authentication environment state is contradictory"
            )
        normalized[key] = {"present": present, "nonempty": nonempty}
    return normalized


def evaluate_manager_postrollback_audit(
    *,
    preclaim_environment: Mapping[str, Any] | None,
    current_environment: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> dict[str, object]:
    current = validate_authentication_environment_state(current_environment)
    baseline_unavailable = preclaim_environment is None
    baseline = (
        None
        if baseline_unavailable
        else validate_authentication_environment_state(preclaim_environment)
    )
    environment_checks = {
        f"{key.lower()}_restored": (
            None if baseline is None else current[key] == baseline[key]
        )
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }
    checks: dict[str, bool] = {
        name: observations.get(name) == expected
        for name, expected in _REQUIRED_OBSERVATIONS.items()
    }
    exact_target_checks = {
        "auth_overlay_removed": checks["auth_overlay_exists"],
        "auth_environment_removed": checks["auth_environment_exists"],
        "password_target_removed": checks["password_target_exists"],
        "password_mount_removed": checks["password_mount_count"],
        "created_directory_targets_clean": checks[
            "created_directory_targets_cleanup_complete"
        ],
    }
    environment_restored = baseline is not None and all(
        value is True for value in environment_checks.values()
    )
    definite_failure = any(value is not True for value in checks.values()) or (
        baseline is not None
        and any(value is not True for value in environment_checks.values())
    )
    audit_passed = (
        not baseline_unavailable
        and environment_restored
        and not definite_failure
    )
    manual_recovery_required = definite_failure
    return {
        "schema": SCHEMA,
        "read_only": True,
        "rollback_audit_passed": audit_passed,
        "baseline_unavailable": baseline_unavailable,
        "baseline_required_for_pass": True,
        "manual_recovery_required": manual_recovery_required,
        "manual_review_required": not audit_passed and not manual_recovery_required,
        "environment_restored": environment_restored,
        "environment_checks": environment_checks,
        "checks": checks,
        "exact_target_checks": exact_target_checks,
        "broad_compose_directory_considered": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
