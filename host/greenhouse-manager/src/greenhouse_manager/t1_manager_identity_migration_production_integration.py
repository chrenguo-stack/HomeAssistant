from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_production_host_adapters import (
    LiveProductionManagerDriver,
    ManagerHostBinding,
    ManagerProductionHostAdaptersError,
    ManagerProductionHostTransactionAdapters,
    _load_binding,
)
from .t1_manager_identity_migration_production_runtime_probe import (
    ManagerProductionRuntimeProbe,
    ReaderFactory,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-production-integration/1"


class ManagerProductionIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagerRuntimeProbeConfiguration:
    system_id: str
    node_id: str
    discovery_topic: str
    mqtt_port: int = 1883
    timeout_s: float = 35.0
    poll_interval_s: float = 1.0


BindingLoader = Callable[..., tuple[ManagerHostBinding, dict[str, Any], dict[str, Any]]]
ProbeFactory = Callable[..., ManagerProductionRuntimeProbe]


def _private_empty_subdirectory(workspace: Path) -> Path:
    if not workspace.is_dir() or workspace.is_symlink() or workspace.stat().st_mode & 0o077:
        raise ManagerProductionIntegrationError(
            "manager production transaction workspace is missing or unsafe"
        )
    destination = workspace / "host-adapters"
    if destination.exists() or destination.is_symlink():
        raise ManagerProductionIntegrationError(
            "manager production host-adapters workspace already exists"
        )
    destination.mkdir(mode=0o700)
    if destination.stat().st_mode & 0o777 != 0o700:
        raise ManagerProductionIntegrationError(
            "manager production host-adapters workspace must be mode 0700"
        )
    return destination


def build_manager_production_adapters_factory(
    configuration: ManagerRuntimeProbeConfiguration,
    *,
    reader_factory: ReaderFactory | None = None,
    proc_root: str | Path = "/proc",
    now: datetime | None = None,
    binding_loader: BindingLoader = _load_binding,
    probe_factory: ProbeFactory = ManagerProductionRuntimeProbe,
) -> Callable[..., ManagerProductionHostTransactionAdapters]:
    def factory(
        driver_contract_file: str | Path,
        execution_preparation_directory: str | Path,
        preparation_directory: str | Path,
        workspace_directory: str | Path,
        *,
        runner: CommandRunner | None = None,
    ) -> ManagerProductionHostTransactionAdapters:
        command_runner = runner or SubprocessRunner()
        driver_path = Path(driver_contract_file).expanduser().resolve()
        execution_root = Path(execution_preparation_directory).expanduser().resolve()
        preparation_root = Path(preparation_directory).expanduser().resolve()
        workspace = Path(workspace_directory).expanduser().resolve()
        host_workspace = _private_empty_subdirectory(workspace)
        try:
            binding, _rollback, _manifest = binding_loader(
                driver_path,
                execution_root,
                preparation_root,
                now=now,
            )
        except ManagerProductionHostAdaptersError:
            raise
        except Exception as error:
            raise ManagerProductionIntegrationError(
                "manager production host binding could not be loaded"
            ) from error
        probe = probe_factory(
            binding,
            system_id=configuration.system_id,
            node_id=configuration.node_id,
            discovery_topic=configuration.discovery_topic,
            runner=command_runner,
            reader_factory=reader_factory,
            proc_root=proc_root,
            mqtt_port=configuration.mqtt_port,
            timeout_s=configuration.timeout_s,
            poll_interval_s=configuration.poll_interval_s,
        )
        baseline = probe.capture_baseline()
        if baseline.get("baseline_captured") is not True:
            raise ManagerProductionIntegrationError(
                "manager runtime continuity baseline capture is incomplete"
            )
        driver = LiveProductionManagerDriver(
            binding,
            probe=probe,
            runner=command_runner,
        )
        return ManagerProductionHostTransactionAdapters(
            driver_path,
            execution_root,
            preparation_root,
            host_workspace,
            driver=driver,
            now=now,
        )

    return factory


def production_integration_capabilities() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "production_runtime_probe_implemented": True,
        "production_host_adapters_implemented": True,
        "orchestrator_integration_factory_implemented": True,
        "execution_entrypoint_installed": False,
        "authorization_claimed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
