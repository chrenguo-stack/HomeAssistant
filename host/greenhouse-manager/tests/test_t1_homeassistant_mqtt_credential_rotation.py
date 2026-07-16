from __future__ import annotations

import json

import pytest

from greenhouse_manager import t1_homeassistant_mqtt_credential_rotation as module


def test_parse_provisioning_options_and_binding() -> None:
    text = (
        "-h 127.0.0.1\n"
        "-u ghs_greenhouse_provisioning\n"
        "-P secret\n"
        "-i gh-provisioning-greenhouse\n"
        "-V 5\n"
    )
    options = module.parse_mosquitto_options(text)
    report = module.require_provisioning_identity(
        options,
        system_id="greenhouse",
    )
    assert report["identity_verified"] is True
    assert "secret" not in repr(options)


def test_parse_provisioning_options_rejects_extra_entry() -> None:
    text = (
        "-h 127.0.0.1\n"
        "-u ghs_greenhouse_provisioning\n"
        "-P secret\n"
        "-i gh-provisioning-greenhouse\n"
        "-V 5\n"
        "-q 1\n"
    )
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="unsupported",
    ):
        module.parse_mosquitto_options(text)


def test_password_generation_is_urlsafe_and_32_bytes() -> None:
    password = module.generate_rotation_password(lambda size: b"x" * size)
    assert password == "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg"
    assert "=" not in password


def test_set_password_control_request() -> None:
    payload = module.build_set_client_password_request("user", "new-secret")
    assert json.loads(payload) == {
        "commands": [
            {
                "command": "setClientPassword",
                "username": "user",
                "password": "new-secret",
            }
        ]
    }


def test_decode_control_response_rejects_error() -> None:
    payload = json.dumps(
        {
            "responses": [
                {
                    "command": "setClientPassword",
                    "error": "permission denied",
                }
            ]
        }
    )
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="command failed",
    ):
        module.decode_control_response(
            payload,
            expected_command="setClientPassword",
        )


def _state(password: str) -> dict[str, object]:
    return {
        "clients": [
            {
                "username": "ghs_greenhouse_homeassistant",
                "clientid": "gh-homeassistant-greenhouse",
                "password": password,
                "disabled": False,
                "roles": [
                    {
                        "rolename": "gh-service-greenhouse-homeassistant",
                        "priority": 100,
                    }
                ],
            },
            {
                "username": "other",
                "clientid": "other",
                "password": "other-hash",
            },
        ],
        "roles": [{"rolename": "role"}],
    }


def test_verify_password_only_state_change() -> None:
    report = module.verify_password_only_state_change(
        _state("old-hash"),
        _state("new-hash"),
        username="ghs_greenhouse_homeassistant",
    )
    assert report["password_hash_changed"] is True
    assert report["non_password_state_unchanged"] is True


def test_verify_password_only_state_change_rejects_acl_drift() -> None:
    before = _state("old-hash")
    after = _state("new-hash")
    after["roles"] = [{"rolename": "drift"}]
    with pytest.raises(
        module.HomeAssistantMqttCredentialRotationError,
        match="outside the target password",
    ):
        module.verify_password_only_state_change(
            before,
            after,
            username="ghs_greenhouse_homeassistant",
        )


def test_reconfigure_values_require_official_flow() -> None:
    values = module.build_reconfigure_values(
        broker="127.0.0.1",
        port=1883,
        username="user",
        password="secret",
        client_id="client",
        generation=2,
    )
    assert values["official_config_flow_only"] is True
    assert values["advanced_options_required"] is True
    assert values["preserve_discovery"] is True


def test_authorization_record_freezes_scope() -> None:
    record = module.build_authorization_record(
        repository_sha="a" * 40,
        manager_source_version="0.4.84",
        operator_statement_fingerprint="b" * 16,
    )
    assert record["authorized"] is True
    assert record["scope"] == "homeassistant_password_only"
    assert record["preserve_anonymous"] is True
    assert record["node_credentials_delivered"] is False
    assert record["homeassistant_storage_access_authorized"] is False


def test_sanitized_report_has_no_runtime_apply_claim() -> None:
    report = module.sanitized_rotation_report(
        repository_sha="a" * 40,
        manager_source_version="0.4.84",
        provisioning={"identity_verified": True},
        state_change={
            "password_hash_changed": True,
            "non_password_state_unchanged": True,
        },
        handoff_fingerprint="c" * 16,
    )
    assert report["rotation_committed"] is True
    assert report["homeassistant_identity_runtime_verified"] is False
    assert report["homeassistant_official_reconfigure_pending"] is True
    assert report["ready_for_anonymous_closure"] is False
    assert report["secret_values_included"] is False
