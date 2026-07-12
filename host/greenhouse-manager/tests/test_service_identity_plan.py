from __future__ import annotations

from dataclasses import asdict

import pytest

from greenhouse_manager.service_identity_plan import (
    ServiceIdentityPlan,
    build_service_identity_plan,
    generate_service_credentials,
)


def _allowed(plan: ServiceIdentityPlan) -> set[tuple[str, str]]:
    return {
        (acl.acl_type, acl.topic)
        for acl in plan.acls
        if acl.allow
    }


def test_manager_identity_matches_current_runtime_topics() -> None:
    plan = build_service_identity_plan(
        system_id="greenhouse", service="manager", generation=1
    )
    allowed = _allowed(plan)

    assert plan.username == "ghs_greenhouse_manager"
    assert plan.client_id == "gh-manager-greenhouse"
    assert ("publishClientSend", "gh/v1/greenhouse/state/#") in allowed
    assert ("publishClientSend", "homeassistant/device/+/config") in allowed
    assert (
        "publishClientSend",
        "homeassistant/binary_sensor/+/config",
    ) in allowed
    assert not any("+_" in topic for _acl_type, topic in allowed)
    assert ("publishClientSend", "homeassistant/status") not in allowed
    assert (
        "subscribePattern",
        "gh/v1/greenhouse/ingress/node/+/telemetry",
    ) in allowed
    assert (
        "subscribePattern",
        "gh/v1/greenhouse/state/+/telemetry",
    ) in allowed


def test_home_assistant_identity_is_read_only_except_birth_status() -> None:
    plan = build_service_identity_plan(
        system_id="greenhouse", service="homeassistant", generation=1
    )
    allowed = _allowed(plan)

    assert ("subscribePattern", "homeassistant/#") in allowed
    assert ("subscribePattern", "gh/v1/greenhouse/state/#") in allowed
    assert ("publishClientSend", "homeassistant/status") in allowed
    assert not any(
        acl_type == "publishClientSend" and topic.startswith("gh/")
        for acl_type, topic in allowed
    )


def test_provisioning_identity_cannot_access_application_topics() -> None:
    plan = build_service_identity_plan(
        system_id="greenhouse", service="provisioning", generation=1
    )
    allowed = _allowed(plan)

    assert allowed == {
        ("publishClientSend", "$CONTROL/dynamic-security/v1"),
        ("subscribePattern", "$CONTROL/dynamic-security/v1/response"),
        ("publishClientReceive", "$CONTROL/dynamic-security/v1/response"),
        ("unsubscribePattern", "$CONTROL/dynamic-security/v1/response"),
    }
    denied = {(acl.acl_type, acl.topic) for acl in plan.acls if not acl.allow}
    assert ("publishClientSend", "gh/#") in denied
    assert ("publishClientSend", "homeassistant/#") in denied


def test_service_identities_are_distinct_and_default_deny() -> None:
    plans = [
        build_service_identity_plan(
            system_id="greenhouse", service=service, generation=1
        )
        for service in ("provisioning", "manager", "homeassistant")
    ]

    assert len({plan.username for plan in plans}) == 3
    assert len({plan.client_id for plan in plans}) == 3
    assert len({plan.role_name for plan in plans}) == 3
    assert all(plan.defaults.publish_client_send is False for plan in plans)
    assert all(plan.defaults.publish_client_receive is False for plan in plans)
    assert all(plan.defaults.subscribe is False for plan in plans)


def test_service_password_is_256_bit_and_redacted() -> None:
    plan = build_service_identity_plan(
        system_id="greenhouse", service="manager", generation=4
    )
    credentials = generate_service_credentials(
        plan, random_bytes=lambda size: bytes(range(size))
    )

    assert len(credentials.password) == 43
    assert credentials.password not in repr(credentials)
    assert "<redacted>" in repr(credentials)
    assert "password" not in asdict(plan)


@pytest.mark.parametrize(
    ("system_id", "service", "generation"),
    [
        ("x", "manager", 1),
        ("greenhouse", "unknown", 1),
        ("greenhouse", "manager", 0),
    ],
)
def test_rejects_invalid_service_identity(
    system_id: str, service: str, generation: int
) -> None:
    with pytest.raises(ValueError):
        build_service_identity_plan(
            system_id=system_id,
            service=service,  # type: ignore[arg-type]
            generation=generation,
        )
