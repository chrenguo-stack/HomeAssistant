from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .t1_manager_identity_migration_production_host_adapters import (
    ManagerProductionHostAdaptersError,
)
from .t1_manager_identity_migration_production_integration import (
    ManagerProductionIntegrationError,
    ManagerRuntimeProbeConfiguration,
    build_manager_production_adapters_factory,
)
from .t1_manager_identity_migration_production_orchestrator import (
    ManagerIdentityProductionOrchestratorError,
    execute_manager_identity_production_migration,
)
from .t1_manager_identity_migration_production_runtime_probe import (
    ManagerProductionRuntimeProbe,
    ManagerProductionRuntimeProbeError,
    ReaderFactory,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-production-execution-packet/1"
_TARGET = "greenhouse-manager"
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROTECTED_SERVICES = ("mosquitto", "homeassistant")
_ALL_SERVICES = (_TARGET, *_PROTECTED_SERVICES)


class ManagerProductionExecutionPacketError(RuntimeError):
    pass


class RuntimeProbe(Protocol):
    def capture_baseline(self) -> dict[str, object]: ...

    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_availability_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class ContainerIdentity:
    name: str
    container_id: str
    image_id: str
    started_at: str
    restart_count: int


Orchestrator = Callable[..., dict[str, object]]
ProbeFactory = Callable[..., RuntimeProbe]


def _inspect_container(runner: CommandRunner, name: str) -> ContainerIdentity:
    if name not in _ALL_SERVICES:
        raise ManagerProductionExecutionPacketError(
            "container inspection target is not allowed"
        )
    code, output = runner.run(("docker", "inspect", name))
    if code != 0:
        raise ManagerProductionExecutionPacketError(
            f"required container is not inspectable: {name}"
        )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerProductionExecutionPacketError(
            f"container inspection returned invalid JSON: {name}"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise ManagerProductionExecutionPacketError(
            f"exactly one container is required: {name}"
        )
    document = documents[0]
    state = document.get("State")
    config = document.get("Config")
    if not isinstance(state, dict) or not isinstance(config, dict):
        raise ManagerProductionExecutionPacketError(
            f"container runtime metadata is incomplete: {name}"
        )
    container_id = document.get("Id")
    image_id = document.get("Image")
    started_at = state.get("StartedAt")
    actual_name = str(document.get("Name", "")).removeprefix("/")
    restart_count = document.get("RestartCount")
    if (
        actual_name != name
        or not isinstance(container_id, str)
        or _CONTAINER_ID.fullmatch(container_id) is None
        or not isinstance(image_id, str)
        or _IMAGE_ID.fullmatch(image_id) is None
        or not isinstance(started_at, str)
        or not started_at
        or state.get("Status") != "running"
        or not isinstance(restart_count, int)
        or restart_count != 0
    ):
        raise ManagerProductionExecutionPacketError(
            f"container must be running with stable identity and zero restarts: {name}"
        )
    return ContainerIdentity(
        name=name,
        container_id=container_id,
        image_id=image_id,
        started_at=started_at,
        restart_count=restart_count,
    )


class ProtectedServicesGuard:
    def __init__(
        self,
        runner: CommandRunner,
        baseline: Mapping[str, ContainerIdentity],
    ) -> None:
        if set(baseline) != set(_ALL_SERVICES):
            raise ManagerProductionExecutionPacketError(
                "protected-service baseline is incomplete"
            )
        self.runner = runner
        self.baseline = dict(baseline)
        self.last_manager: ContainerIdentity | None = None

    @classmethod
    def capture(cls, runner: CommandRunner) -> ProtectedServicesGuard:
        return cls(
            runner,
            {name: _inspect_container(runner, name) for name in _ALL_SERVICES},
        )

    def _current(self) -> dict[str, ContainerIdentity]:
        return {name: _inspect_container(self.runner, name) for name in _ALL_SERVICES}

    def verify_protected_services_unchanged(self) -> None:
        current = self._current()
        for name in _PROTECTED_SERVICES:
            if current[name] != self.baseline[name]:
                raise ManagerProductionExecutionPacketError(
                    f"protected service changed during manager transaction: {name}"
                )
        manager = current[_TARGET]
        if manager.image_id != self.baseline[_TARGET].image_id:
            raise ManagerProductionExecutionPacketError(
                "greenhouse-manager image changed during identity migration"
            )
        self.last_manager = manager

    def verify_manager_recreated_and_protected_unchanged(self) -> None:
        self.verify_protected_services_unchanged()
        assert self.last_manager is not None
        if self.last_manager.container_id == self.baseline[_TARGET].container_id:
            raise ManagerProductionExecutionPacketError(
                "greenhouse-manager container was not recreated"
            )

    def summary(self) -> dict[str, object]:
        manager = self.last_manager
        return {
            "greenhouse_manager_image_preserved": bool(
                manager is not None
                and manager.image_id == self.baseline[_TARGET].image_id
            ),
            "greenhouse_manager_recreated": bool(
                manager is not None
                and manager.container_id != self.baseline[_TARGET].container_id
            ),
            "mosquitto_unchanged": True,
            "homeassistant_unchanged": True,
            "all_containers_running_zero_restart": True,
            "container_ids_included": False,
            "image_ids_included": False,
        }


class GuardedRuntimeProbe:
    def __init__(self, inner: RuntimeProbe, guard: ProtectedServicesGuard) -> None:
        self.inner = inner
        self.guard = guard

    def capture_baseline(self) -> dict[str, object]:
        return self.inner.capture_baseline()

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        self.inner.verify_authenticated_identity(username, client_id)

    def verify_ingress_subscription(self) -> None:
        self.inner.verify_ingress_subscription()

    def verify_canonical_publication(self) -> None:
        self.inner.verify_canonical_publication()

    def verify_availability_publication(self) -> None:
        self.inner.verify_availability_publication()

    def verify_discovery_publication(self) -> None:
        self.inner.verify_discovery_publication()

    def verify_reconnect(self) -> None:
        self.inner.verify_reconnect()

    def verify_existing_entities(self) -> None:
        self.inner.verify_existing_entities()
        self.guard.verify_manager_recreated_and_protected_unchanged()

    def verify_legacy_anonymous_path(self) -> None:
        self.inner.verify_legacy_anonymous_path()
        self.guard.verify_protected_services_unchanged()

    def postactivation_audit(self) -> dict[str, object]:
        report = dict(self.inner.postactivation_audit())
        self.guard.verify_manager_recreated_and_protected_unchanged()
        checks = report.get("checks")
        if not isinstance(checks, dict):
            raise ManagerProductionExecutionPacketError(
                "manager postactivation check inventory is invalid"
            )
        checks = dict(checks)
        checks.update(
            {
                "greenhouse_manager_image_preserved": True,
                "greenhouse_manager_recreated": True,
                "mosquitto_unchanged": True,
                "homeassistant_unchanged": True,
            }
        )
        report["checks"] = checks
        report["protected_services_unchanged"] = True
        report["greenhouse_manager_image_preserved"] = True
        report["greenhouse_manager_recreated"] = True
        return report


def execute_manager_identity_production_packet(
    authorization_file: str | Path,
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    transaction_directory: str | Path,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    execution_confirmation: str,
    target: str,
    execute_manager_migration: bool = False,
    enable_production_execution: bool = False,
    mqtt_port: int = 1883,
    timeout_s: float = 35.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: CommandRunner | None = None,
    reader_factory: ReaderFactory | None = None,
    now: datetime | None = None,
    orchestrator: Orchestrator = execute_manager_identity_production_migration,
    probe_factory: ProbeFactory = ManagerProductionRuntimeProbe,
) -> dict[str, object]:
    if target != _TARGET:
        raise ManagerProductionExecutionPacketError(
            "production execution target must be greenhouse-manager"
        )
    if not execute_manager_migration or not enable_production_execution:
        raise ManagerProductionExecutionPacketError(
            "both production execution enable flags are required"
        )
    if not execution_confirmation.startswith("EXECUTE-M2-MANAGER-MIGRATION:"):
        raise ManagerProductionExecutionPacketError(
            "exact second manager migration confirmation is required"
        )

    command_runner = runner or SubprocessRunner()
    guard = ProtectedServicesGuard.capture(command_runner)

    def guarded_probe_factory(*args: object, **kwargs: object) -> GuardedRuntimeProbe:
        return GuardedRuntimeProbe(probe_factory(*args, **kwargs), guard)

    adapters_factory = build_manager_production_adapters_factory(
        ManagerRuntimeProbeConfiguration(
            system_id=system_id,
            node_id=node_id,
            discovery_topic=discovery_topic,
            mqtt_port=mqtt_port,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
        ),
        reader_factory=reader_factory,
        proc_root=proc_root,
        now=now,
        probe_factory=guarded_probe_factory,
    )

    try:
        transaction = orchestrator(
            authorization_file,
            execution_preparation_directory,
            driver_contract_file,
            preparation_directory,
            transaction_directory,
            execution_confirmation=execution_confirmation,
            execution_enabled=True,
            runner=command_runner,
            now=now,
            adapters_factory=adapters_factory,
        )
    except Exception:
        guard.verify_protected_services_unchanged()
        raise

    required = {
        "authorization_claimed": True,
        "authorization_consumed": True,
        "mutation_completed": True,
        "postactivation_verified": True,
        "rollback_completed": False,
        "manager_identity_migrated": True,
        "node_credentials_delivered": False,
        "current_services_modified": True,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    for field, expected in required.items():
        if transaction.get(field) is not expected:
            raise ManagerProductionExecutionPacketError(
                f"manager production transaction result failed: {field}"
            )

    guard.verify_manager_recreated_and_protected_unchanged()
    transaction_id = transaction.get("transaction_id")
    authorization_id = transaction.get("authorization_id")
    if not isinstance(transaction_id, str) or not transaction_id:
        raise ManagerProductionExecutionPacketError(
            "manager production transaction ID is missing"
        )
    if not isinstance(authorization_id, str) or not authorization_id:
        raise ManagerProductionExecutionPacketError(
            "manager production authorization ID is missing"
        )
    return {
        "schema": SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": authorization_id,
        "production_execution_completed": True,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "manager_identity_migrated": True,
        "postactivation_verified": True,
        "rollback_completed": False,
        **guard.summary(),
        "node_credentials_delivered": False,
        "current_services_modified": True,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "ready_for_node_credential_delivery_preparation": True,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the single-use greenhouse-manager MQTT identity migration "
            "transaction after both exact operator confirmations."
        )
    )
    parser.add_argument("authorization_file")
    parser.add_argument("execution_preparation_directory")
    parser.add_argument("driver_contract_file")
    parser.add_argument("preparation_directory")
    parser.add_argument("transaction_directory")
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--discovery-topic", required=True)
    parser.add_argument("--execution-confirmation", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=35.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--execute-manager-migration", action="store_true")
    parser.add_argument("--enable-production-execution", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = execute_manager_identity_production_packet(
            args.authorization_file,
            args.execution_preparation_directory,
            args.driver_contract_file,
            args.preparation_directory,
            args.transaction_directory,
            system_id=args.system_id,
            node_id=args.node_id,
            discovery_topic=args.discovery_topic,
            execution_confirmation=args.execution_confirmation,
            target=args.target,
            execute_manager_migration=args.execute_manager_migration,
            enable_production_execution=args.enable_production_execution,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
        )
    except (
        ManagerProductionExecutionPacketError,
        ManagerIdentityProductionOrchestratorError,
        ManagerProductionIntegrationError,
        ManagerProductionHostAdaptersError,
        ManagerProductionRuntimeProbeError,
        ValueError,
    ) as error:
        print(f"T1 manager production execution failed: {error}", file=sys.stderr)
        return 2
    except OSError:
        print(
            "T1 manager production execution failed: protected host operation failed",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0
