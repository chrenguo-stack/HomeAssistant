from __future__ import annotations

import pytest

from greenhouse_manager import t1_homeassistant_mqtt_credential_rotation_v2 as module


def _state(
    credential: object,
    *,
    field: str = "encoded_password",
) -> dict[str, object]:
    target = {
        "username": "ghs_greenhouse_homeassistant",
        "clientid": "gh-homeassistant-greenhouse",
        field: credential,
        "roles": [
            {
                "rolename": "gh-service-greenhouse-homeassistant",
                "priority": 100,
            }
        ],
        "textdescription": "Home Assistant",
    }
    return {
        "clients": [
            target,
            {
                "username": "other",
                "clientid": "other",
                "encoded_password": "other-hash",
            },
        ],
        "roles": [{"rolename": "role"}],
    }


def test_verify_encoded_password_only_state_change() -> None:
    report = module.verify_password_only_state_change(
        _state("old-hash"),
        _state("new-hash"),
        username="ghs_greenhouse_homeassistant",
    )
    assert report["password_hash_changed"] is True
    assert report["non_password_state_unchanged"] is True
    assert report["credential_material_changed"] is True
    assert report["non_credential_state_unchanged"] is True
    assert report["credential_state_field"] == "encoded_password"


def test_verify_structured_encoded_password_state_change() -> None:
    before = {"salt": "a", "iterations": 100, "digest": "old"}
    after = {"salt": "b", "iterations": 100, "digest": "new"}
    report = module.verify_password_only_state_change(
        _state(before),
        _state(after),
        username="ghs_greenhouse_homeassistant",
    )
    assert report["credential_state_field"] == "encoded_password"


def test_verify_legacy_password_field_state_change() -> None:
    report = module.verify_password_only_state_change(
        _state("old-hash", field="password"),
        _state("new-hash", field="password"),
        username="ghs_greenhouse_homeassistant",
    )
    assert report["credential_state_field"] == "password"


def test_verify_rejects_credential_field_drift() -> None:
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="credential field changed",
    ):
        module.verify_password_only_state_change(
            _state("old-hash", field="encoded_password"),
            _state("new-hash", field="password"),
            username="ghs_greenhouse_homeassistant",
        )


def test_verify_rejects_acl_drift() -> None:
    before = _state("old-hash")
    after = _state("new-hash")
    after["roles"] = [{"rolename": "drift"}]
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="outside the target credential material",
    ):
        module.verify_password_only_state_change(
            before,
            after,
            username="ghs_greenhouse_homeassistant",
        )


def test_verify_rejects_missing_credential_field() -> None:
    before = _state("old-hash")
    target = before["clients"][0]
    assert isinstance(target, dict)
    target.pop("encoded_password")
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="missing or ambiguous",
    ):
        module.verify_password_only_state_change(
            before,
            _state("new-hash"),
            username="ghs_greenhouse_homeassistant",
        )


def test_verify_rejects_ambiguous_credential_fields() -> None:
    before = _state("old-hash")
    target = before["clients"][0]
    assert isinstance(target, dict)
    target["password"] = "legacy"
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="missing or ambiguous",
    ):
        module.verify_password_only_state_change(
            before,
            _state("new-hash"),
            username="ghs_greenhouse_homeassistant",
        )
