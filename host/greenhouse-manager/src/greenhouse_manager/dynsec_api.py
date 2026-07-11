from __future__ import annotations

import json
import threading
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any, Protocol

import paho.mqtt.client as mqtt

from .dynsec_plan import NodeCredentials, NodeProvisioningPlan

CONTROL_TOPIC = "$CONTROL/dynamic-security/v1"
RESPONSE_TOPIC = "$CONTROL/dynamic-security/v1/response"
LEGACY_ANONYMOUS_ROLE = "gh-legacy-anonymous-shadow"
LEGACY_ANONYMOUS_GROUP = "gh-legacy-anonymous-shadow"


class DynsecError(RuntimeError):
    pass


class DynsecTransport(Protocol):
    def execute(self, commands: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]: ...


def baseline_commands(plan: NodeProvisioningPlan) -> tuple[dict[str, Any], ...]:
    defaults = plan.defaults
    return (
        {
            "command": "setDefaultACLAccess",
            "acls": [
                {"acltype": "publishClientSend", "allow": defaults.publish_client_send},
                {"acltype": "publishClientReceive", "allow": defaults.publish_client_receive},
                {"acltype": "subscribe", "allow": defaults.subscribe},
                {"acltype": "unsubscribe", "allow": defaults.unsubscribe},
            ],
        },
    )


def create_role_command(plan: NodeProvisioningPlan) -> dict[str, Any]:
    return {
        "command": "createRole",
        "rolename": plan.role_name,
        "textdescription": f"Greenhouse node {plan.node_id} generation {plan.generation}",
        "acls": [
            {
                "acltype": acl.acl_type,
                "topic": acl.topic,
                "priority": acl.priority,
                "allow": acl.allow,
            }
            for acl in plan.acls
        ],
    }


def create_client_command(
    plan: NodeProvisioningPlan, credentials: NodeCredentials
) -> dict[str, Any]:
    if credentials.username != plan.username or credentials.client_id != plan.client_id:
        raise ValueError("credentials do not match provisioning plan")
    if credentials.generation != plan.generation:
        raise ValueError("credential generation does not match provisioning plan")
    return {
        "command": "createClient",
        "username": plan.username,
        "password": credentials.password,
        "clientid": plan.client_id,
        "textdescription": f"Greenhouse node {plan.node_id} generation {plan.generation}",
        "roles": [{"rolename": plan.role_name, "priority": 100}],
    }


def set_client_password_command(
    plan: NodeProvisioningPlan, credentials: NodeCredentials
) -> dict[str, Any]:
    if credentials.username != plan.username or credentials.client_id != plan.client_id:
        raise ValueError("credentials do not match provisioning plan")
    return {
        "command": "setClientPassword",
        "username": plan.username,
        "password": credentials.password,
    }


def legacy_anonymous_shadow_commands() -> tuple[dict[str, Any], ...]:
    return (
        {
            "command": "createRole",
            "rolename": LEGACY_ANONYMOUS_ROLE,
            "textdescription": "Temporary compatibility role during authenticated migration",
            "acls": [
                {
                    "acltype": "publishClientSend",
                    "topic": "$CONTROL/#",
                    "priority": 1000,
                    "allow": False,
                },
                {
                    "acltype": "subscribePattern",
                    "topic": "$CONTROL/#",
                    "priority": 1000,
                    "allow": False,
                },
                *(
                    {
                        "acltype": acl_type,
                        "topic": "#",
                        "priority": 100,
                        "allow": True,
                    }
                    for acl_type in (
                        "publishClientSend",
                        "subscribePattern",
                        "publishClientReceive",
                        "unsubscribePattern",
                    )
                ),
                *(
                    {
                        "acltype": acl_type,
                        "topic": "$SYS/#",
                        "priority": 100,
                        "allow": True,
                    }
                    for acl_type in (
                        "subscribePattern",
                        "publishClientReceive",
                        "unsubscribePattern",
                    )
                ),
            ],
        },
        {
            "command": "createGroup",
            "groupname": LEGACY_ANONYMOUS_GROUP,
            "textdescription": "Temporary anonymous clients during shadow migration",
            "roles": [{"rolename": LEGACY_ANONYMOUS_ROLE, "priority": 100}],
        },
        {
            "command": "setAnonymousGroup",
            "groupname": LEGACY_ANONYMOUS_GROUP,
        },
    )


class DynsecProvisioner:
    def __init__(self, transport: DynsecTransport) -> None:
        self.transport = transport

    def apply_baseline(self, plan: NodeProvisioningPlan) -> None:
        self.transport.execute(baseline_commands(plan))

    def apply_legacy_anonymous_shadow(self) -> None:
        for command in legacy_anonymous_shadow_commands():
            self.transport.execute((command,))

    def provision(self, plan: NodeProvisioningPlan, credentials: NodeCredentials) -> None:
        role_started = False
        client_started = False
        try:
            role_started = True
            self.transport.execute((create_role_command(plan),))
            client_started = True
            self.transport.execute((create_client_command(plan, credentials),))
        except Exception:
            if client_started:
                self._best_effort(({"command": "deleteClient", "username": plan.username},))
            if role_started:
                self._best_effort(({"command": "deleteRole", "rolename": plan.role_name},))
            raise

    def deprovision(self, plan: NodeProvisioningPlan) -> None:
        self.transport.execute(({"command": "deleteClient", "username": plan.username},))
        self.transport.execute(({"command": "deleteRole", "rolename": plan.role_name},))

    def rotate_password(
        self,
        plan: NodeProvisioningPlan,
        current: NodeCredentials,
        replacement: NodeCredentials,
        verify: Callable[[NodeCredentials], None],
    ) -> None:
        if replacement.generation <= current.generation:
            raise ValueError("replacement generation must increase")
        set_client_password_command(plan, current)
        replacement_command = set_client_password_command(plan, replacement)
        rollback_command = set_client_password_command(plan, current)
        self.transport.execute((replacement_command,))
        try:
            verify(replacement)
        except Exception:
            try:
                self.transport.execute((rollback_command,))
            except Exception as rollback_error:
                raise DynsecError(
                    "credential rotation verification and rollback failed"
                ) from rollback_error
            raise

    def _best_effort(self, commands: Sequence[dict[str, Any]]) -> None:
        with suppress(Exception):
            self.transport.execute(commands)


class PahoDynsecTransport:
    """Single-flight Dynamic Security topic API transport."""

    def __init__(self, client: mqtt.Client, *, timeout_s: float = 10.0) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.client = client
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._response_ready = threading.Event()
        self._response: bytes | None = None

    def on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        if message.topic == RESPONSE_TOPIC:
            self._response = bytes(message.payload)
            self._response_ready.set()

    def execute(self, commands: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        if not commands:
            raise ValueError("at least one command is required")
        with self._lock:
            self._response = None
            self._response_ready.clear()
            result, _mid = self.client.subscribe(RESPONSE_TOPIC, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise DynsecError(f"Dynamic Security response subscribe failed rc={result}")
            payload = json.dumps(
                {"commands": list(commands)}, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            info = self.client.publish(CONTROL_TOPIC, payload=payload, qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise DynsecError(f"Dynamic Security command publish failed rc={info.rc}")
            if not self._response_ready.wait(self.timeout_s):
                raise DynsecError("Dynamic Security response timed out")
            return self._decode_response(self._response or b"")

    @staticmethod
    def _decode_response(payload: bytes) -> tuple[dict[str, Any], ...]:
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DynsecError("Dynamic Security returned invalid JSON") from exc
        responses = document.get("responses") if isinstance(document, dict) else None
        if not isinstance(responses, list):
            raise DynsecError("Dynamic Security response is missing responses")
        for response in responses:
            if not isinstance(response, dict):
                raise DynsecError("Dynamic Security returned an invalid response entry")
            if response.get("error"):
                command = response.get("command", "unknown")
                raise DynsecError(f"Dynamic Security command failed: {command}")
        return tuple(responses)
