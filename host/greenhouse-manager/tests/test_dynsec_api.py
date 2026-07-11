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
    PahoDynsecTransport,
    baseline_commands,
    create_client_command,
)
from greenhouse_manager.dynsec_plan import (
    build_node_provisioning_plan,
    generate_node_credentials,
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


def test_rolls_back_client_and_role_after_client_failure() -> None:
    plan, credentials = plan_and_credentials()
    transport = RecordingTransport(fail_call=2)

    with pytest.raises(DynsecError, match="injected"):
        DynsecProvisioner(transport).provision(plan, credentials)

    commands = [call[0]["command"] for call in transport.calls]
    assert commands == ["createRole", "createClient", "deleteClient", "deleteRole"]


def test_paho_transport_uses_control_topics_without_logging_payload() -> None:
    client = Mock()
    client.subscribe.return_value = (0, 1)
    client.publish.return_value = Mock(rc=0)
    transport = PahoDynsecTransport(client, timeout_s=0.1)
    response = Mock(topic=RESPONSE_TOPIC, payload=b'{"responses":[{"command":"listClients"}]}')
    client.publish.side_effect = lambda *args, **kwargs: (
        transport.on_message(client, None, response) or Mock(rc=0)
    )

    result = transport.execute(({"command": "listClients"},))

    assert result == ({"command": "listClients"},)
    client.subscribe.assert_called_once_with(RESPONSE_TOPIC, qos=1)
    assert client.publish.call_args.args[0] == CONTROL_TOPIC
    published = json.loads(client.publish.call_args.kwargs["payload"])
    assert published == {"commands": [{"command": "listClients"}]}


def test_rejects_error_without_echoing_broker_message() -> None:
    payload = b'{"responses":[{"command":"createClient","error":"secret details"}]}'

    with pytest.raises(DynsecError) as captured:
        PahoDynsecTransport._decode_response(payload)

    assert "createClient" in str(captured.value)
    assert "secret details" not in str(captured.value)
