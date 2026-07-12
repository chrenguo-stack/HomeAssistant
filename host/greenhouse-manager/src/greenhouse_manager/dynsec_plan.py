from __future__ import annotations

import base64
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_PATTERN_SUBSTITUTIONS = ("%c", "%u")


def _validate_topic_filter(topic: str) -> None:
    if not topic:
        raise ValueError("ACL topic filter must not be empty")
    levels = topic.split("/")
    for index, level in enumerate(levels):
        if "+" in level and level != "+":
            raise ValueError("MQTT + wildcard must occupy an entire topic level")
        if "#" in level and (level != "#" or index != len(levels) - 1):
            raise ValueError("MQTT # wildcard must occupy the final topic level")
        for substitution in _PATTERN_SUBSTITUTIONS:
            if substitution in level and level != substitution:
                raise ValueError(
                    f"Dynamic Security {substitution} substitution must occupy an entire topic level"
                )


@dataclass(frozen=True, slots=True)
class DynsecAcl:
    acl_type: str
    topic: str
    allow: bool
    priority: int

    def __post_init__(self) -> None:
        _validate_topic_filter(self.topic)


@dataclass(frozen=True, slots=True)
class DynsecDefaultAccess:
    publish_client_send: bool = False
    publish_client_receive: bool = False
    subscribe: bool = False
    unsubscribe: bool = True


@dataclass(frozen=True, slots=True)
class NodeProvisioningPlan:
    system_id: str
    node_id: str
    generation: int
    username: str
    client_id: str
    role_name: str
    defaults: DynsecDefaultAccess
    acls: tuple[DynsecAcl, ...]


@dataclass(frozen=True, slots=True, repr=False)
class NodeCredentials:
    username: str
    client_id: str
    generation: int
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return (
            "NodeCredentials("
            f"username={self.username!r}, client_id={self.client_id!r}, "
            f"generation={self.generation!r}, password=<redacted>)"
        )


def build_node_provisioning_plan(
    *, system_id: str, node_id: str, generation: int
) -> NodeProvisioningPlan:
    if _ID_PATTERN.fullmatch(system_id) is None:
        raise ValueError("system_id must match [A-Za-z0-9_-]{3,64}")
    if _ID_PATTERN.fullmatch(node_id) is None:
        raise ValueError("node_id must match [A-Za-z0-9_-]{3,64}")
    if not 1 <= generation <= 4294967295:
        raise ValueError("generation must be between 1 and 4294967295")

    ingress = f"gh/v1/{system_id}/ingress/node/{node_id}/#"
    outbound = f"gh/v1/{system_id}/out/node/{node_id}/#"
    role_name = f"gh-node-{system_id}-{node_id}"
    acls = (
        DynsecAcl("publishClientSend", "$CONTROL/#", False, 1000),
        DynsecAcl("publishClientSend", "homeassistant/#", False, 1000),
        DynsecAcl("publishClientSend", f"gh/v1/{system_id}/state/#", False, 1000),
        DynsecAcl("subscribePattern", "$CONTROL/#", False, 1000),
        DynsecAcl("subscribePattern", "homeassistant/#", False, 1000),
        DynsecAcl("subscribePattern", f"gh/v1/{system_id}/state/#", False, 1000),
        DynsecAcl("publishClientSend", ingress, True, 100),
        DynsecAcl("subscribePattern", outbound, True, 100),
        DynsecAcl("publishClientReceive", outbound, True, 100),
        DynsecAcl("unsubscribePattern", outbound, True, 100),
    )
    return NodeProvisioningPlan(
        system_id=system_id,
        node_id=node_id,
        generation=generation,
        username=f"ghn_{node_id}",
        client_id=node_id,
        role_name=role_name,
        defaults=DynsecDefaultAccess(),
        acls=acls,
    )


def generate_node_credentials(
    plan: NodeProvisioningPlan,
    *,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> NodeCredentials:
    password = base64.urlsafe_b64encode(random_bytes(32)).rstrip(b"=").decode("ascii")
    return NodeCredentials(
        username=plan.username,
        client_id=plan.client_id,
        generation=plan.generation,
        password=password,
    )
