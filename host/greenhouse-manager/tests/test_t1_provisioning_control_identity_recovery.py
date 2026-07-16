from __future__ import annotations

import pytest

from greenhouse_manager import (
    t1_provisioning_control_identity_recovery as module,
)


USERNAME = "ghs_greenhouse_provisioning"
CLIENT_ID = "gh-provisioning-greenhouse"
ROLE = "gh-service-greenhouse-provisioning"


def _state(encoded_password: str = "old-encoded") -> dict[str, object]:
    return {
        "clients": [
            {
                "username": USERNAME,
                "clientid": CLIENT_ID,
                "encoded_password": encoded_password,
                "roles": [{"rolename": ROLE, "priority": 100}],
                "textdescription": "Provisioning control",
            },
            {
                "username": "other",
                "clientid": "other",
                "encoded_password": "other-encoded",
                "roles": [],
            },
        ],
        "roles": [{"rolename": ROLE, "acls": []}],
        "defaultACLAccess": {"publishClientSend": False},
    }


def test_require_exact_control_identity() -> None:
    report = module.require_exact_control_identity(
        _state(),
        username=USERNAME,
        client_id=CLIENT_ID,
        role_name=ROLE,
    )
    assert report["identity_exact"] is True
    assert report["credential_state_field"] == "encoded_password"


def test_generate_recovery_password_is_urlsafe() -> None:
    password = module.generate_recovery_password(lambda size: b"x" * size)
    assert password == "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg"
    assert "=" not in password


def test_extract_isolated_encoded_password() -> None:
    assert (
        module.extract_isolated_encoded_password(
            _state("new-encoded"),
            username=USERNAME,
        )
        == "new-encoded"
    )


def test_build_and_verify_password_only_candidate() -> None:
    before = _state()
    after = module.build_candidate_state(
        before,
        username=USERNAME,
        encoded_password="new-encoded",
    )
    report = module.verify_password_only_candidate(
        before,
        after,
        username=USERNAME,
    )
    assert report["credential_material_changed"] is True
    assert report["non_credential_state_unchanged"] is True
    assert report["credential_state_field"] == "encoded_password"


def test_verify_rejects_role_drift() -> None:
    before = _state()
    after = module.build_candidate_state(
        before,
        username=USERNAME,
        encoded_password="new-encoded",
    )
    target = after["clients"][0]
    assert isinstance(target, dict)
    target["roles"] = [{"rolename": "drift", "priority": 100}]
    with pytest.raises(
        module.ProvisioningControlIdentityRecoveryError,
        match="outside provisioning credential material",
    ):
        module.verify_password_only_candidate(
            before,
            after,
            username=USERNAME,
        )


def test_require_rejects_ambiguous_credential_representation() -> None:
    state = _state()
    target = state["clients"][0]
    assert isinstance(target, dict)
    target["password"] = "legacy"
    with pytest.raises(
        module.ProvisioningControlIdentityRecoveryError,
        match="ambiguous",
    ):
        module.require_exact_control_identity(
            state,
            username=USERNAME,
            client_id=CLIENT_ID,
            role_name=ROLE,
        )


def test_authorization_record_freezes_recovery_scope() -> None:
    record = module.build_authorization_record(
        repository_sha="a" * 40,
        manager_source_version="0.4.86",
        operator_statement_fingerprint="b" * 16,
    )
    assert record["scope"] == "provisioning_control_identity_password_recovery"
    assert record["mosquitto_restart_authorized"] is True
    assert record["automatic_rollback_authorized"] is True
    assert record["preserve_anonymous"] is True
    assert record["homeassistant_storage_access_authorized"] is False


def test_sanitized_report_does_not_claim_anonymous_closure() -> None:
    report = module.sanitized_recovery_report(
        repository_sha="a" * 40,
        manager_source_version="0.4.86",
        identity={"identity_exact": True},
        state_change={"credential_material_changed": True},
        rollback_available=True,
    )
    assert report["recovery_committed"] is True
    assert report["mosquitto_restart_performed"] is True
    assert report["ready_for_homeassistant_password_rotation"] is True
    assert report["ready_for_anonymous_closure"] is False
    assert report["secret_values_included"] is False
