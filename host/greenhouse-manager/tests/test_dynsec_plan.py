from __future__ import annotations

from dataclasses import asdict

import pytest

from greenhouse_manager.dynsec_plan import (
    DynsecAcl,
    build_node_provisioning_plan,
    generate_node_credentials,
)


def test_builds_exact_per_node_acl_profile() -> None:
    plan = build_node_provisioning_plan(
        system_id="greenhouse", node_id="gh-n1-a9f2f8", generation=1
    )
    allowed = {(acl.acl_type, acl.topic) for acl in plan.acls if acl.allow}

    assert plan.username == "ghn_gh-n1-a9f2f8"
    assert plan.client_id == "gh-n1-a9f2f8"
    assert ("publishClientSend", "gh/v1/greenhouse/ingress/node/gh-n1-a9f2f8/#") in allowed
    assert ("subscribePattern", "gh/v1/greenhouse/out/node/gh-n1-a9f2f8/#") in allowed
    assert ("publishClientReceive", "gh/v1/greenhouse/out/node/gh-n1-a9f2f8/#") in allowed
    assert all("+/" not in topic and "/+" not in topic for _acl_type, topic in allowed)


def test_defaults_deny_publish_receive_and_subscribe() -> None:
    plan = build_node_provisioning_plan(system_id="greenhouse", node_id="node-001", generation=1)

    assert plan.defaults.publish_client_send is False
    assert plan.defaults.publish_client_receive is False
    assert plan.defaults.subscribe is False
    assert plan.defaults.unsubscribe is True


@pytest.mark.parametrize("dangerous", ["$CONTROL/#", "homeassistant/#", "gh/v1/greenhouse/state/#"])
def test_explicitly_denies_dangerous_namespaces(dangerous: str) -> None:
    plan = build_node_provisioning_plan(system_id="greenhouse", node_id="node-001", generation=1)

    denies = {acl.topic for acl in plan.acls if not acl.allow and acl.priority == 1000}
    assert dangerous in denies


def test_two_nodes_never_share_identity_or_allowed_topics() -> None:
    first = build_node_provisioning_plan(system_id="greenhouse", node_id="node-001", generation=1)
    second = build_node_provisioning_plan(system_id="greenhouse", node_id="node-002", generation=1)

    assert first.username != second.username
    assert first.role_name != second.role_name
    first_allowed = {acl.topic for acl in first.acls if acl.allow}
    second_allowed = {acl.topic for acl in second.acls if acl.allow}
    assert first_allowed.isdisjoint(second_allowed)


def test_generates_256_bit_password_without_repr_leak() -> None:
    plan = build_node_provisioning_plan(system_id="greenhouse", node_id="node-001", generation=7)
    credentials = generate_node_credentials(plan, random_bytes=lambda size: bytes(range(size)))

    assert credentials.password == "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
    assert len(credentials.password) == 43
    assert credentials.password not in repr(credentials)
    assert "<redacted>" in repr(credentials)
    assert "password" not in asdict(plan)


@pytest.mark.parametrize(
    "topic",
    [
        "homeassistant/binary_sensor/+_connectivity/config",
        "gh/#/invalid",
        "room/%c_suffix/temperature",
    ],
)
def test_rejects_nonportable_acl_topic_filters(topic: str) -> None:
    with pytest.raises(ValueError):
        DynsecAcl("publishClientSend", topic, True, 100)


@pytest.mark.parametrize(
    "topic",
    [
        "homeassistant/binary_sensor/+/config",
        "gh/v1/greenhouse/#",
        "room/%c/temperature",
    ],
)
def test_accepts_standard_acl_topic_filters(topic: str) -> None:
    acl = DynsecAcl("publishClientSend", topic, True, 100)

    assert acl.topic == topic


@pytest.mark.parametrize(
    ("system_id", "node_id", "generation"),
    [("x", "node-001", 1), ("greenhouse", "bad/node", 1), ("greenhouse", "node-001", 0)],
)
def test_rejects_invalid_identity_or_generation(
    system_id: str, node_id: str, generation: int
) -> None:
    with pytest.raises(ValueError):
        build_node_provisioning_plan(
            system_id=system_id, node_id=node_id, generation=generation
        )
