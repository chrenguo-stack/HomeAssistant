from __future__ import annotations

from typing import Any

import pytest

from greenhouse_manager.runtime.dynsec_api import (
    DynsecError,
    DynsecOutcomeUncertain,
    DynsecProvisioner,
)
from greenhouse_manager.runtime.dynsec_plan import (
    build_node_provisioning_plan,
    generate_node_credentials,
)


class OwnershipTransport:
    def __init__(
        self,
        *,
        username: str,
        role_name: str,
        client_present: bool = False,
        role_present: bool = False,
        client_outcome: str = "normal",
    ) -> None:
        self.username = username
        self.role_name = role_name
        self.client_present = client_present
        self.role_present = role_present
        self.client_outcome = client_outcome
        self.calls: list[str] = []

    def execute(
        self,
        commands: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        assert len(commands) == 1
        command = commands[0]
        name = str(command["command"])
        self.calls.append(name)

        if name == "createRole":
            assert command["rolename"] == self.role_name
            if self.role_present:
                raise DynsecError("role already exists")
            self.role_present = True
            return ({"command": name},)

        if name == "createClient":
            assert command["username"] == self.username
            if self.client_present:
                raise DynsecError("client already exists")
            if self.client_outcome == "uncertain_before_apply":
                raise DynsecOutcomeUncertain("client outcome uncertain")
            self.client_present = True
            if self.client_outcome == "uncertain_after_apply":
                raise DynsecOutcomeUncertain("client outcome uncertain")
            return ({"command": name},)

        if name == "deleteClient":
            assert command["username"] == self.username
            self.client_present = False
            return ({"command": name},)

        if name == "deleteRole":
            assert command["rolename"] == self.role_name
            self.role_present = False
            return ({"command": name},)

        if name == "listClients":
            clients = [self.username] if self.client_present else []
            return ({"command": name, "data": {"clients": clients}},)

        if name == "listRoles":
            roles = [self.role_name] if self.role_present else []
            return ({"command": name, "data": {"roles": roles}},)

        raise AssertionError(name)


def _plan_and_credentials() -> tuple[Any, Any]:
    plan = build_node_provisioning_plan(
        system_id="greenhouse",
        node_id="gh-n1-kf060",
        generation=7,
    )
    credentials = generate_node_credentials(
        plan,
        random_bytes=lambda size: bytes(range(size)),
    )
    return plan, credentials


def test_preserves_preexisting_role_and_client_on_role_collision() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
        client_present=True,
        role_present=True,
    )

    with pytest.raises(DynsecError, match="role already exists"):
        DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is True
    assert transport.role_present is True
    assert transport.calls == ["createRole"]


def test_preserves_preexisting_client_and_removes_only_new_role() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
        client_present=True,
        role_present=False,
    )

    with pytest.raises(DynsecError, match="client already exists"):
        DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is True
    assert transport.role_present is False
    assert transport.calls == ["createRole", "createClient", "deleteRole"]


def test_never_deletes_preexisting_role_after_create_role_collision() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
        client_present=False,
        role_present=True,
    )

    with pytest.raises(DynsecError, match="role already exists"):
        DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is False
    assert transport.role_present is True
    assert transport.calls == ["createRole"]


def test_clean_target_provisions_normally() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
    )

    DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is True
    assert transport.role_present is True
    assert transport.calls == ["createRole", "createClient"]


def test_uncertain_client_success_leaves_complete_target_for_reconciliation() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
        client_outcome="uncertain_after_apply",
    )

    with pytest.raises(DynsecOutcomeUncertain, match="outcome uncertain"):
        DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is True
    assert transport.role_present is True
    assert transport.calls == [
        "createRole",
        "createClient",
        "listClients",
        "listRoles",
    ]


def test_uncertain_client_absence_rolls_back_confirmed_new_role() -> None:
    plan, credentials = _plan_and_credentials()
    transport = OwnershipTransport(
        username=plan.username,
        role_name=plan.role_name,
        client_outcome="uncertain_before_apply",
    )

    with pytest.raises(DynsecOutcomeUncertain, match="outcome uncertain"):
        DynsecProvisioner(transport).provision(plan, credentials)

    assert transport.client_present is False
    assert transport.role_present is False
    assert transport.calls == [
        "createRole",
        "createClient",
        "listClients",
        "listRoles",
        "deleteRole",
    ]
