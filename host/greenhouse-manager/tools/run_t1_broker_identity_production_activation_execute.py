from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from greenhouse_manager.t1_broker_identity_production_activation_orchestrator import (
    BrokerIdentityProductionActivationOrchestratorError,
    execute_production_activation,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute one fully bound production Broker identity activation with "
            "an explicit enable flag and exact execution confirmation."
        )
    )
    parser.add_argument("authorization_file")
    parser.add_argument("activation_readiness_bundle_file")
    parser.add_argument("transaction_plan_file")
    parser.add_argument("adapter_contract_file")
    parser.add_argument("executor_contract_file")
    parser.add_argument("runtime_binding_manifest_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("transaction_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--execution-confirmation", required=True)
    parser.add_argument(
        "--enable-production-execution",
        action="store_true",
        help="Required explicit opt-in for the live Broker transaction.",
    )
    args = parser.parse_args(argv)

    try:
        result = execute_production_activation(
            args.authorization_file,
            args.activation_readiness_bundle_file,
            args.transaction_plan_file,
            args.adapter_contract_file,
            args.executor_contract_file,
            args.runtime_binding_manifest_file,
            args.handoff_directory,
            args.transaction_directory,
            expected_retained_topic=args.expected_retained_topic,
            execution_confirmation=args.execution_confirmation,
            execution_enabled=args.enable_production_execution,
        )
    except (
        BrokerIdentityProductionActivationOrchestratorError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker production activation failed: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
