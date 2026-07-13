from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

packet = import_module(
    "greenhouse_manager.t1_manager_identity_migration_production_execution_packet"
)
host_adapters = import_module(
    "greenhouse_manager.t1_manager_identity_migration_production_host_adapters"
)
integration = import_module(
    "greenhouse_manager.t1_manager_identity_migration_production_integration"
)
orchestrator = import_module(
    "greenhouse_manager.t1_manager_identity_migration_production_orchestrator"
)
runtime_probe = import_module(
    "greenhouse_manager.t1_manager_identity_migration_production_runtime_probe"
)
stdlib_mqtt = import_module(
    "greenhouse_manager.t1_manager_identity_migration_stdlib_mqtt"
)


def main(argv: list[str] | None = None) -> int:
    args = packet._parser().parse_args(argv)
    try:
        result = packet.execute_manager_identity_production_packet(
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
            reader_factory=lambda: stdlib_mqtt.StdlibAnonymousRetainedReader(
                port=args.mqtt_port,
                timeout_s=min(args.timeout_seconds, 8.0),
            ),
        )
    except (
        packet.ManagerProductionExecutionPacketError,
        orchestrator.ManagerIdentityProductionOrchestratorError,
        integration.ManagerProductionIntegrationError,
        host_adapters.ManagerProductionHostAdaptersError,
        runtime_probe.ManagerProductionRuntimeProbeError,
        stdlib_mqtt.ManagerStdlibMqttError,
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


if __name__ == "__main__":
    raise SystemExit(main())
