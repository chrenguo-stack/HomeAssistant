from __future__ import annotations

import base64
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from .dynsec_plan import DynsecAcl, DynsecDefaultAccess

ServiceKind = Literal["provisioning", "manager", "homeassistant"]
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_SERVICES: tuple[ServiceKind, ...] = (
    "provisioning",
    "manager",
    "homeassistant",
)


@dataclass(frozen=True, slots=True)
class ServiceIdentityPlan:
    system_id: str
    service: ServiceKind
    generation: int
    username: str
    client_id: str
    role_name: str
    defaults: DynsecDefaultAccess
    acls: tuple[DynsecAcl, ...]


@dataclass(frozen=True, slots=True, repr=False)
class ServiceCredentials:
    username: str
    client_id: str
    generation: int
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return (
            "ServiceCredentials("
            f"username={self.username!r}, client_id={self.client_id!r}, "
            f"generation={self.generation!r}, password=<redacted>)"
        )


def _allow_topic(topic: str) -> tuple[DynsecAcl, ...]:
    return (
        DynsecAcl("subscribePattern", topic, True, 100),
        DynsecAcl("publishClientReceive", topic, True, 100),
        DynsecAcl("unsubscribePattern", topic, True, 100),
    )


def _manager_acls(system_id: str) -> tuple[DynsecAcl, ...]:
    ingress = f"gh/v1/{system_id}/ingress/node/+/telemetry"
    state_telemetry = f"gh/v1/{system_id}/state/+/telemetry"
    return (
        DynsecAcl("publishClientSend", "$CONTROL/#", False, 1000),
        DynsecAcl("subscribePattern", "$CONTROL/#", False, 1000),
        DynsecAcl("publishClientSend", f"gh/v1/{system_id}/state/#", True, 100),
        DynsecAcl("publishClientSend", "homeassistant/device/+/config", True, 100),
        DynsecAcl(
            "publishClientSend",
            "homeassistant/binary_sensor/+_connectivity/config",
            True,
            100,
        ),
        *_allow_topic(ingress),
        *_allow_topic(state_telemetry),
        *_allow_topic("gh/bootstrap/v1/node/+/hello"),
    )


def _home_assistant_acls(system_id: str) -> tuple[DynsecAcl, ...]:
    return (
        DynsecAcl("publishClientSend", "$CONTROL/#", False, 1000),
        DynsecAcl("subscribePattern", "$CONTROL/#", False, 1000),
        DynsecAcl("publishClientSend", "homeassistant/status", True, 100),
        *_allow_topic("homeassistant/#"),
        *_allow_topic(f"gh/v1/{system_id}/state/#"),
    )


def _provisioning_acls() -> tuple[DynsecAcl, ...]:
    control = "$CONTROL/dynamic-security/v1"
    response = "$CONTROL/dynamic-security/v1/response"
    return (
        DynsecAcl("publishClientSend", control, True, 1000),
        DynsecAcl("subscribePattern", response, True, 1000),
        DynsecAcl("publishClientReceive", response, True, 1000),
        DynsecAcl("unsubscribePattern", response, True, 1000),
        DynsecAcl("publishClientSend", "$CONTROL/#", False, 100),
        DynsecAcl("subscribePattern", "$CONTROL/#", False, 100),
        DynsecAcl("publishClientSend", "gh/#", False, 1000),
        DynsecAcl("subscribePattern", "gh/#", False, 1000),
        DynsecAcl("publishClientSend", "homeassistant/#", False, 1000),
        DynsecAcl("subscribePattern", "homeassistant/#", False, 1000),
    )


def build_service_identity_plan(
    *, system_id: str, service: ServiceKind, generation: int
) -> ServiceIdentityPlan:
    if _ID_PATTERN.fullmatch(system_id) is None:
        raise ValueError("system_id must match [A-Za-z0-9_-]{3,64}")
    if service not in _SERVICES:
        raise ValueError("unsupported service identity")
    if not 1 <= generation <= 4294967295:
        raise ValueError("generation must be between 1 and 4294967295")
    acls = {
        "provisioning": _provisioning_acls(),
        "manager": _manager_acls(system_id),
        "homeassistant": _home_assistant_acls(system_id),
    }[service]
    return ServiceIdentityPlan(
        system_id=system_id,
        service=service,
        generation=generation,
        username=f"ghs_{system_id}_{service}",
        client_id=f"gh-{service}-{system_id}",
        role_name=f"gh-service-{system_id}-{service}",
        defaults=DynsecDefaultAccess(),
        acls=acls,
    )


def generate_service_credentials(
    plan: ServiceIdentityPlan,
    *,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> ServiceCredentials:
    password = base64.urlsafe_b64encode(random_bytes(32)).rstrip(b"=").decode("ascii")
    return ServiceCredentials(
        username=plan.username,
        client_id=plan.client_id,
        generation=plan.generation,
        password=password,
    )
