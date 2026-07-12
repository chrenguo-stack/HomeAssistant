from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from greenhouse_manager.t1_broker_identity_production_activation_orchestrator import (
    BrokerIdentityProductionActivationOrchestratorError,
    build_production_activation_execution_request,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only production Broker activation execution request from "
            "a valid short-lived authorization and fully bound transaction materials."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    request = subparsers.add_parser("request")
    request.add_argument("authorization_file")
    request.add_argument("activation_readiness_bundle_file")
    request.add_argument("transaction_plan_file")
    request.add_argument("adapter_contract_file")
    request.add_argument("executor_contract_file")
    request.add_argument("runtime_binding_manifest_file")
    args = parser.parse_args(argv)

    try:
        result = build_production_activation_execution_request(
            args.authorization_file,
            args.activation_readiness_bundle_file,
            args.transaction_plan_file,
            args.adapter_contract_file,
            args.executor_contract_file,
            args.runtime_binding_manifest_file,
        )
    except (
        BrokerIdentityProductionActivationOrchestratorError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker production activation execution request failed: {error}",
            file=sys.stderr,
        )
        return 2

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
