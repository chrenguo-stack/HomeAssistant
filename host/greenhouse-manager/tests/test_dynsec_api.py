from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock

import pytest

from greenhouse_manager.dynsec_api import (
    CONTROL_TOPIC,
    RESPONSE_TOPIC,
    DynsecError,
    DynsecProvisioner,
    DynsecRollbackError,
    PahoDynsecTransport,
    baseline_commands,
    create_client_command,
    create_role_command,
    legacy_anonymous_shadow_commands,
    set_client_password_command,
)
from greenhouse_manager.dynsec_plan import (
    build_node_provisioning_plan,
    generate_node_credentials,
)
from greenhouse_manager.service_identity_plan import (
    build_service_identity_plan,
    generate_service_credentials,
)


class RecordingTransport:
    def __init__(self, *, fail_call: int | None = None) -> None:
        self.calls: list[tuple[dict[str, Any], ...]] = []
        self.fail_call = fail_call

    def execute(self, commands: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        self.calls.append(commands)
        if self.fail_call == len(self.calls):
            raise DynsecError("injected failure")
        return tuple({"command": command["command"]} for command in commands)


def plan_and_credentials() -> tuple[Any, Any]:
    plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-n1-a9f2f8", generation=1
    )
    credentials = generate_node_credentials(plan, random_bytes=lambda size: bytes(range(size)))
    return plan, credentials


def test_baseline_denies_receive_in_real_api_shape() -> None:
    plan, _credentials = plan_and_credentials()
    command = baseline_commands(plan)[0]

    defaults = {entry["acltype"]: entry["allow"] for entry in command["acls"]}
    assert defaults == {
        "publishClientSend": False,
        "publishClientReceive": False,
        "subscribe": False,
        "unsubscribe": True,
    }


def test_client_command_binds_role_and_client_id() -> None:
    plan, credentials = plan_and_credentials()

    command = create_client_command(plan, credentials)

    assert command["username"] == "ghn_gh-n1-a9f2f8"
    assert command["clientid"] == "gh-n1-a9f2f8"
    assert command["roles"] == [{"rolename": plan.role_name, "priority": 100}]


@pytest.mark.parametrize("service", ["provisioning", "manager", "homeassistant"])
def test_service_identity_uses_same_transactional_api(service: str) -> None:
    plan = build_service_identity_plan(
        system_id="greenhouse",
        service=service,  # type: ignore[arg-type]
        generation=1,
    )
    credentials = generate_service_credentials(
        plan, random_bytes=lambda size: bytes(range(size))
    )

    role = create_role_command(plan)
    client = create_client_command(plan, credentials)

    assert role["rolename"] == plan.role_name
    assert role["acls"]
    assert client["username"] == plan.username
    assert client["clientid"] == plan.client_id
    assert credentials.password not in repr(credentials)


def test_legacy_anonymous_shadow_preserves_apps_but_denies_control() -> None:
    role, group, anonymous = legacy_anonymous_shadow_commands()

    assert role["command"] == "createRole"
    acl_map = {
        (acl["acltype"], acl["topic"]): acl["allow"]
        for acl in role["acls"]
    }
    assert acl_map[("publishClientSend", "#")] is True
    assert acl_map[("subscribePattern", "#")] is True
    assert acl_map[("publishClientReceive", "#")] is True
    assert acl_map[("subscribePattern", "$SYS/#")] is True
    assert acl_map[("publishClientSend", "$CONTROL/#")] is False
    assert acl_map[("subscribePattern", "$CONTROL/#")] is False
    assert group["roles"] == [
        {"rolename": "gh-legacy-anonymous-shadow", "priority": 100}
    ]
    assert anonymous == {
        "command": "setAnonymousGroup",
        "groupname": "gh-legacy-anonymous-shadow",
    }


def test_applies_legacy_shadow_in_dependency_order() -> None:
    transport = RecordingTransport()

    DynsecProvisioner(transport).apply_legacy_anonymous_shadow()

    assert [call[0]["command"] for call in transport.calls] == [
        "createRole",
        "createGroup",
        "setAnonymousGroup",
    ]


def test_rolls_back_client_and_role_after_client_failure() -> None:
    plan, credentials = plan_and_credentials()
    transport = RecordingTransport(fail_call=2)

    with pytest.raises(DynsecError, match="injected"):
        DynsecProvisioner(transport).provision(plan, credentials)

    commands = [call[0]["command"] for call in transport.calls]
    assert commands == ["createRole", "createClient", "deleteClient", "deleteRole"]



def test_reports_provisioning_and_rollback_failure_without_secrets() -> None:
    plan, credentials = plan_and_credentials()

    class RollbackFailingTransport(RecordingTransport):
        def execute(
            self,
            commands: tuple[dict[str, Any], ...],
        ) -> tuple[dict[str, Any], ...]:
            self.calls.append(commands)
            command = commands[0]["command"]
            if command == "createClient":
                raise DynsecError("primary secret details")
            if command == "deleteClient":
                raise DynsecError("rollback client secret details")
            return tuple(
                {"command": item["command"]}
                for item in commands
            )

    transport = RollbackFailingTransport()

    with pytest.raises(DynsecRollbackError) as captured:
        DynsecProvisioner(transport).provision(plan, credentials)

    assert captured.value.operation == "provisioning"
    assert captured.value.rollback_failures == (
        ("deleteClient", "DynsecError"),
    )
    assert "primary secret details" not in str(captured.value)
    assert "rollback client secret details" not in str(captured.value)
    assert isinstance(captured.value.__cause__, DynsecError)


def test_rotates_password_only_after_verification() -> None:
    plan, current = plan_and_credentials()
    replacement_plan = build_node_provisioning_plan(
        system_id=plan.system_id, node_id=plan.node_id, generation=2
    )
    replacement = generate_node_credentials(
        replacement_plan, random_bytes=lambda size: bytes(reversed(range(size)))
    )
    transport = RecordingTransport()
    verified: list[Any] = []

    DynsecProvisioner(transport).rotate_password(
        plan, current, replacement, verified.append
    )

    assert verified == [replacement]
    assert transport.calls == [(set_client_password_command(plan, replacement),)]


def test_rotation_restores_current_password_when_verification_fails() -> None:
    plan, current = plan_and_credentials()
    replacement_plan = build_node_provisioning_plan(
        system_id=plan.system_id, node_id=plan.node_id, generation=2
    )
    replacement = generate_node_credentials(replacement_plan)
    transport = RecordingTransport()

    def reject(_credentials: Any) -> None:
        raise RuntimeError("probe rejected")

    with pytest.raises(RuntimeError, match="probe rejected"):
        DynsecProvisioner(transport).rotate_password(plan, current, replacement, reject)

    assert transport.calls == [
        (set_client_password_command(plan, replacement),),
        (set_client_password_command(plan, current),),
    ]


def test_rotation_reports_rollback_failure_without_secret() -> None:
    plan, current = plan_and_credentials()
    replacement_plan = build_node_provisioning_plan(
        system_id=plan.system_id, node_id=plan.node_id, generation=2
    )
    replacement = generate_node_credentials(replacement_plan)
    transport = RecordingTransport(fail_call=2)

    def reject(_credentials: Any) -> None:
        raise RuntimeError("probe rejected")

    with pytest.raises(DynsecRollbackError) as captured:
        DynsecProvisioner(transport).rotate_password(
            plan,
            current,
            replacement,
            reject,
        )

    assert captured.value.operation == "credential rotation verification"
    assert captured.value.rollback_failures == (
        ("setClientPassword", "DynsecError"),
    )
    assert replacement.password not in str(captured.value)
    assert current.password not in str(captured.value)
    assert isinstance(captured.value.__cause__, RuntimeError)


def test_rotation_rejects_non_increasing_generation_before_broker_call() -> None:
    plan, current = plan_and_credentials()
    transport = RecordingTransport()

    with pytest.raises(ValueError, match="generation must increase"):
        DynsecProvisioner(transport).rotate_password(
            plan, current, current, lambda _credentials: None
        )

    assert transport.calls == []


def test_paho_transport_correlates_and_ignores_unrelated_response() -> None:
    client = Mock()
    client.subscribe.return_value = (0, 1)
    transport = PahoDynsecTransport(client, timeout_s=0.1)

    def publish_side_effect(*args: Any, **kwargs: Any) -> Any:
        published = json.loads(kwargs["payload"])
        correlation = published["commands"][0]["correlationData"]

        unrelated = Mock(
            topic=RESPONSE_TOPIC,
            payload=json.dumps(
                {
                    "responses": [
                        {
                            "command": "listClients",
                            "correlationData": "healthcheck",
                        }
                    ]
                }
            ).encode(),
        )
        matched = Mock(
            topic=RESPONSE_TOPIC,
            payload=json.dumps(
                {
                    "responses": [
                        {
                            "command": "listClients",
                            "correlationData": correlation,
                        }
                    ]
                }
            ).encode(),
        )
        transport.on_message(client, None, unrelated)
        transport.on_message(client, None, matched)
        return Mock(rc=0)

    client.publish.side_effect = publish_side_effect

    result = transport.execute(({"command": "listClients"},))

    assert result[0]["command"] == "listClients"
    assert transport.ignored_response_count == 1
    client.subscribe.assert_called_once_with(RESPONSE_TOPIC, qos=1)
    assert client.publish.call_args.args[0] == CONTROL_TOPIC
    published = json.loads(client.publish.call_args.kwargs["payload"])
    correlation = published["commands"][0].pop("correlationData")
    assert isinstance(correlation, str) and correlation
    assert published == {"commands": [{"command": "listClients"}]}


@pytest.mark.parametrize(
    ("responses", "expected_ignored"),
    [
        (
            [
                {
                    "command": "getClient",
                    "correlationData": "{correlation}",
                }
            ],
            1,
        ),
        (
            [
                {
                    "command": "listClients",
                    "correlationData": "{correlation}",
                },
                {
                    "command": "listClients",
                    "correlationData": "{correlation}",
                },
            ],
            1,
        ),
        (
            [
                {
                    "command": "listClients",
                    "correlationData": "wrong",
                }
            ],
            1,
        ),
    ],
)
def test_paho_transport_rejects_mismatched_response_contract(
    responses: list[dict[str, Any]],
    expected_ignored: int,
) -> None:
    client = Mock()
    client.subscribe.return_value = (0, 1)
    transport = PahoDynsecTransport(client, timeout_s=0.01)

    def publish_side_effect(*args: Any, **kwargs: Any) -> Any:
        published = json.loads(kwargs["payload"])
        correlation = published["commands"][0]["correlationData"]
        rendered = [
            {
                key: (
                    correlation
                    if value == "{correlation}"
                    else value
                )
                for key, value in response.items()
            }
            for response in responses
        ]
        message = Mock(
            topic=RESPONSE_TOPIC,
            payload=json.dumps({"responses": rendered}).encode(),
        )
        transport.on_message(client, None, message)
        return Mock(rc=0)

    client.publish.side_effect = publish_side_effect

    with pytest.raises(
        DynsecError,
        match=rf"correlated response timed out ignored={expected_ignored}",
    ):
        transport.execute(({"command": "listClients"},))


def test_paho_transport_rejects_caller_correlation_data() -> None:
    client = Mock()
    client.subscribe.return_value = (0, 1)
    client.publish.return_value = Mock(rc=0)
    transport = PahoDynsecTransport(client, timeout_s=0.1)

    with pytest.raises(
        ValueError,
        match="caller supplied correlationData",
    ):
        transport.execute(
            (
                {
                    "command": "listClients",
                    "correlationData": "caller-owned",
                },
            )
        )

    client.publish.assert_not_called()


def test_rejects_error_without_echoing_broker_message() -> None:
    payload = b'{"responses":[{"command":"createClient","error":"secret details"}]}'

    with pytest.raises(DynsecError) as captured:
        PahoDynsecTransport._decode_response(payload)

    assert "createClient" in str(captured.value)
    assert "secret details" not in str(captured.value)
