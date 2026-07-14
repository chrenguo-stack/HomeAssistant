from __future__ import annotations

import pytest

from greenhouse_manager.t1_manager_identity_migration_postrollback_audit import (
    AUTHENTICATION_ENVIRONMENT_KEYS,
    ManagerPostrollbackAuditError,
    evaluate_manager_postrollback_audit,
    redacted_authentication_environment_state,
)


def _baseline(*, present: bool = True, nonempty: bool = False) -> dict[str, object]:
    return {
        key: {"present": present, "nonempty": nonempty}
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }


def _observations() -> dict[str, object]:
    return {
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


def test_complete_postrollback_evidence_passes() -> None:
    baseline = _baseline()

    report = evaluate_manager_postrollback_audit(
        preclaim_environment=baseline,
        current_environment=baseline,
        observations=_observations(),
    )

    assert report["rollback_audit_passed"] is True
    assert report["manual_recovery_required"] is False
    assert report["manual_review_required"] is False
    assert report["broad_compose_directory_considered"] is False
    assert all(report["checks"].values())
    assert all(report["exact_target_checks"].values())


def test_missing_baseline_does_not_claim_manual_recovery() -> None:
    report = evaluate_manager_postrollback_audit(
        preclaim_environment=None,
        current_environment=_baseline(),
        observations=_observations(),
    )

    assert report["rollback_audit_passed"] is False
    assert report["baseline_unavailable"] is True
    assert report["manual_recovery_required"] is False
    assert report["manual_review_required"] is True


def test_missing_directory_baseline_requires_review_not_recovery() -> None:
    observations = _observations()
    observations["created_directory_targets_cleanup_complete"] = None

    report = evaluate_manager_postrollback_audit(
        preclaim_environment=_baseline(),
        current_environment=_baseline(),
        observations=observations,
    )

    assert report["rollback_audit_passed"] is False
    assert report["directory_baseline_unavailable"] is True
    assert report["manual_recovery_required"] is False
    assert report["manual_review_required"] is True


def test_empty_and_nonempty_environment_are_distinct() -> None:
    report = evaluate_manager_postrollback_audit(
        preclaim_environment=_baseline(present=True, nonempty=False),
        current_environment=_baseline(present=True, nonempty=True),
        observations=_observations(),
    )

    assert report["environment_restored"] is False
    assert report["manual_recovery_required"] is True
    assert not all(value is True for value in report["environment_checks"].values())


def test_absent_and_present_empty_environment_are_distinct() -> None:
    report = evaluate_manager_postrollback_audit(
        preclaim_environment=_baseline(present=False, nonempty=False),
        current_environment=_baseline(present=True, nonempty=False),
        observations=_observations(),
    )

    assert report["rollback_audit_passed"] is False
    assert report["manual_recovery_required"] is True


def test_broad_compose_directory_is_not_an_exact_cleanup_target() -> None:
    observations = _observations()
    observations["compose_working_directory_nonempty"] = True

    report = evaluate_manager_postrollback_audit(
        preclaim_environment=_baseline(),
        current_environment=_baseline(),
        observations=observations,
    )

    assert report["rollback_audit_passed"] is True
    assert report["broad_compose_directory_considered"] is False


@pytest.mark.parametrize(
    ("field", "unsafe"),
    (
        ("rollback_failed", True),
        ("auth_overlay_exists", True),
        ("password_mount_count", 1),
        ("manager_stable_mqtt_socket", False),
        ("manager_image_preserved", False),
        ("mosquitto_unchanged", False),
        ("homeassistant_unchanged", False),
        ("anonymous_retained_path_readable", False),
    ),
)
def test_definite_rollback_drift_requires_recovery(field: str, unsafe: object) -> None:
    observations = _observations()
    observations[field] = unsafe

    report = evaluate_manager_postrollback_audit(
        preclaim_environment=_baseline(),
        current_environment=_baseline(),
        observations=observations,
    )

    assert report["rollback_audit_passed"] is False
    assert report["manual_recovery_required"] is True


def test_environment_capture_contains_only_presence_flags() -> None:
    state = redacted_authentication_environment_state(
        {
            "GH_MQTT_USERNAME": "",
            "GH_MQTT_PASSWORD": "secret-value",
            "UNRELATED": "ignored-value",
        }
    )

    assert state == {
        "GH_MQTT_USERNAME": {"present": True, "nonempty": False},
        "GH_MQTT_PASSWORD": {"present": True, "nonempty": True},
        "GH_MQTT_PASSWORD_FILE": {"present": False, "nonempty": False},
    }
    assert "secret-value" not in repr(state)
    assert "ignored-value" not in repr(state)


def test_contradictory_environment_state_is_rejected() -> None:
    baseline = _baseline()
    baseline["GH_MQTT_USERNAME"] = {"present": False, "nonempty": True}

    with pytest.raises(ManagerPostrollbackAuditError, match="contradictory"):
        evaluate_manager_postrollback_audit(
            preclaim_environment=baseline,
            current_environment=_baseline(),
            observations=_observations(),
        )
