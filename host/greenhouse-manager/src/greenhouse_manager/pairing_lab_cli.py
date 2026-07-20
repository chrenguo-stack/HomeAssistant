from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field

from .dynsec_plan import NodeCredentials, NodeProvisioningPlan
from .pairing_runtime import (
    PairingRuntime,
    PairingRuntimeDisabled,
    assemble_pairing_runtime,
)
from .pairing_runtime_config import PairingRuntimeSettings


@dataclass(slots=True)
class IsolatedLabProvisioner:
    """Process-local provisioner for the isolated deployment contract only."""

    plans: dict[str, NodeProvisioningPlan] = field(default_factory=dict)

    def provision(
        self,
        plan: NodeProvisioningPlan,
        credentials: NodeCredentials,
    ) -> None:
        if credentials.username != plan.username:
            raise ValueError("credentials do not match provisioning plan")
        if plan.username in self.plans:
            raise RuntimeError("identity is already provisioned")
        self.plans[plan.username] = plan

    def deprovision(self, plan: NodeProvisioningPlan) -> None:
        current = self.plans.get(plan.username)
        if current != plan:
            raise RuntimeError("identity is not provisioned")
        del self.plans[plan.username]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the disabled-by-default H3/N2 isolated pairing runtime"
        )
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate configuration without opening sockets",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="start the isolated-lab pairing service",
    )
    return parser


def _install_signal_handlers(runtime: PairingRuntime) -> None:
    def stop(_signum: int, _frame: object) -> None:
        runtime.request_stop()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = PairingRuntimeSettings.from_env()
    except (OSError, TypeError, ValueError) as error:
        print(f"Pairing configuration error: {error}", file=sys.stderr)
        return 2

    if args.check_config or not args.serve:
        print(
            json.dumps(
                settings.report(),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    if not settings.enabled:
        print(
            json.dumps(
                settings.report(),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        runtime = assemble_pairing_runtime(
            settings,
            IsolatedLabProvisioner(),
        )
    except PairingRuntimeDisabled:
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        logging.getLogger(__name__).error(
            "Pairing runtime assembly failed: %s",
            type(error).__name__,
        )
        return 3

    _install_signal_handlers(runtime)
    try:
        runtime.run()
    except OSError as error:
        logging.getLogger(__name__).error(
            "Pairing runtime network failure: %s",
            type(error).__name__,
        )
        return 4
    except RuntimeError as error:
        logging.getLogger(__name__).error(
            "Pairing runtime failed closed: %s",
            type(error).__name__,
        )
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
