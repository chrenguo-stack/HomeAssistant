from __future__ import annotations

import json
import queue
import secrets
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError as error:
    if error.name is None or not error.name.startswith("paho"):
        raise
    mqtt = None

from .dynsec_plan import NodeCredentials, NodeProvisioningPlan
from .service_identity_plan import ServiceCredentials, ServiceIdentityPlan

CONTROL_TOPIC = "$CONTROL/dynamic-security/v1"
RESPONSE_TOPIC = "$CONTROL/dynamic-security/v1/response"
LEGACY_ANONYMOUS_ROLE = "gh-legacy-anonymous-shadow"
LEGACY_ANONYMOUS_GROUP = "gh-legacy-anonymous-shadow"
IdentityPlan = NodeProvisioningPlan | ServiceIdentityPlan
IdentityCredentials = NodeCredentials | ServiceCredentials


class DynsecError(RuntimeError):
    pass


class DynsecRollbackError(DynsecError):
    """Reports a primary failure plus one or more failed cleanup commands.

    Error messages intentionally contain only operation and exception-class
    metadata so broker responses and credentials are not echoed.
    """

    def __init__(
        self,
        operation: str,
        rollback_failures: Sequence[tuple[str, BaseException]],
    ) -> None:
        self.operation = operation
        self.rollback_failures = tuple(
            (command, type(error).__name__)
            for command, error in rollback_failures
        )
        failed_commands = ",".join(
            command
            for command, _error_type in self.rollback_failures
        )
        super().__init__(
            f"{operation} failed and rollback failed: {failed_commands}"
        )


class DynsecTransport(Protocol):
    def execute(self, commands: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]: ...


def baseline_commands(plan: IdentityPlan) -> tuple[dict[str, Any], ...]:
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


def _plan_description(plan: IdentityPlan) -> str:
    if isinstance(plan, NodeProvisioningPlan):
        return f"Greenhouse node {plan.node_id} generation {plan.generation}"
    return f"Greenhouse {plan.service} service generation {plan.generation}"


def create_role_command(plan: IdentityPlan) -> dict[str, Any]:
    return {
        "command": "createRole",
        "rolename": plan.role_name,
        "textdescription": _plan_description(plan),
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
    plan: IdentityPlan, credentials: IdentityCredentials
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
        "textdescription": _plan_description(plan),
        "roles": [{"rolename": plan.role_name, "priority": 100}],
    }


def set_client_password_command(
    plan: IdentityPlan, credentials: IdentityCredentials
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

    def apply_baseline(self, plan: IdentityPlan) -> None:
        self.transport.execute(baseline_commands(plan))

    def apply_legacy_anonymous_shadow(self) -> None:
        for command in legacy_anonymous_shadow_commands():
            self.transport.execute((command,))

    def provision(
        self, plan: IdentityPlan, credentials: IdentityCredentials
    ) -> None:
        role_started = False
        client_started = False
        try:
            role_started = True
            self.transport.execute((create_role_command(plan),))
            client_started = True
            self.transport.execute((create_client_command(plan, credentials),))
        except Exception as provisioning_error:
            rollback_failures: list[tuple[str, BaseException]] = []
            rollback_commands: list[dict[str, Any]] = []

            if client_started:
                rollback_commands.append(
                    {"command": "deleteClient", "username": plan.username}
                )
            if role_started:
                rollback_commands.append(
                    {"command": "deleteRole", "rolename": plan.role_name}
                )

            for command in rollback_commands:
                try:
                    self.transport.execute((command,))
                except Exception as rollback_error:
                    rollback_failures.append(
                        (str(command["command"]), rollback_error)
                    )

            if rollback_failures:
                raise DynsecRollbackError(
                    "provisioning",
                    rollback_failures,
                ) from provisioning_error
            raise

    def deprovision(self, plan: IdentityPlan) -> None:
        self.transport.execute(({"command": "deleteClient", "username": plan.username},))
        self.transport.execute(({"command": "deleteRole", "rolename": plan.role_name},))

    def rotate_password(
        self,
        plan: IdentityPlan,
        current: IdentityCredentials,
        replacement: IdentityCredentials,
        verify: Callable[[IdentityCredentials], None],
    ) -> None:
        if replacement.generation <= current.generation:
            raise ValueError("replacement generation must increase")
        set_client_password_command(plan, current)
        replacement_command = set_client_password_command(plan, replacement)
        rollback_command = set_client_password_command(plan, current)
        self.transport.execute((replacement_command,))
        try:
            verify(replacement)
        except Exception as verification_error:
            try:
                self.transport.execute((rollback_command,))
            except Exception as rollback_error:
                raise DynsecRollbackError(
                    "credential rotation verification",
                    (("setClientPassword", rollback_error),),
                ) from verification_error
            raise


def _require_paho() -> Any:
    if mqtt is None:
        raise RuntimeError("paho-mqtt is required for PahoDynsecTransport")
    return mqtt


class PahoDynsecTransport:
    """Single-flight Dynamic Security topic API transport."""

    def __init__(self, client: Any, *, timeout_s: float = 10.0) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._mqtt = _require_paho()
        self.client = client
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._responses: queue.Queue[bytes] = queue.Queue()
        self.ignored_response_count = 0

    def on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        if message.topic == RESPONSE_TOPIC:
            self._responses.put(bytes(message.payload))

    def execute(self, commands: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        if not commands:
            raise ValueError("at least one command is required")

        with self._lock:
            while True:
                try:
                    self._responses.get_nowait()
                except queue.Empty:
                    break

            correlation_data = secrets.token_urlsafe(24)
            correlated_commands: list[dict[str, Any]] = []

            for command in commands:
                if "correlationData" in command:
                    raise ValueError(
                        "caller supplied correlationData is not allowed"
                    )

                correlated_command = dict(command)
                correlated_command["correlationData"] = correlation_data
                correlated_commands.append(correlated_command)

            expected_commands = tuple(
                command["command"]
                for command in correlated_commands
            )

            result, _mid = self.client.subscribe(
                RESPONSE_TOPIC,
                qos=1,
            )

            if result != self._mqtt.MQTT_ERR_SUCCESS:
                raise DynsecError(
                    "Dynamic Security response subscribe failed "
                    f"rc={result}"
                )

            payload = json.dumps(
                {"commands": correlated_commands},
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")

            info = self.client.publish(
                CONTROL_TOPIC,
                payload=payload,
                qos=1,
                retain=False,
            )

            if info.rc != self._mqtt.MQTT_ERR_SUCCESS:
                raise DynsecError(
                    "Dynamic Security command publish failed "
                    f"rc={info.rc}"
                )

            deadline = time.monotonic() + self.timeout_s
            ignored_this_call = 0

            while True:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise DynsecError(
                        "Dynamic Security correlated response timed out "
                        f"ignored={ignored_this_call}"
                    )

                try:
                    raw_response = self._responses.get(
                        timeout=remaining,
                    )
                except queue.Empty as exc:
                    raise DynsecError(
                        "Dynamic Security correlated response timed out "
                        f"ignored={ignored_this_call}"
                    ) from exc

                try:
                    document = json.loads(
                        raw_response.decode("utf-8")
                    )
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                ) as exc:
                    raise DynsecError(
                        "Dynamic Security returned invalid JSON"
                    ) from exc

                responses = (
                    document.get("responses")
                    if isinstance(document, dict)
                    else None
                )

                if not isinstance(responses, list):
                    raise DynsecError(
                        "Dynamic Security response is missing responses"
                    )

                if not all(
                    isinstance(response, dict)
                    for response in responses
                ):
                    raise DynsecError(
                        "Dynamic Security returned an invalid "
                        "response entry"
                    )

                response_commands = tuple(
                    response.get("command")
                    for response in responses
                )
                response_correlations = tuple(
                    response.get("correlationData")
                    for response in responses
                )

                matched = (
                    len(responses) == len(correlated_commands)
                    and response_commands == expected_commands
                    and all(
                        value == correlation_data
                        for value in response_correlations
                    )
                )

                if not matched:
                    ignored_this_call += 1
                    self.ignored_response_count += 1
                    print(
                        "DYNSEC_UNCORRELATED_RESPONSE_IGNORED="
                        f"{self.ignored_response_count}",
                        flush=True,
                    )
                    continue

                return self._decode_response(raw_response)

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
