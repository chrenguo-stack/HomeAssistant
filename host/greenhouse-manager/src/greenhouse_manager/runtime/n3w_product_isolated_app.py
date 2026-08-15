from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .config import Settings
from .n3w_product_isolated_launcher import run_isolated_manager

_OPT_IN_ENV = "GH_N3W_S5_ISOLATED_MANAGER_ENABLED"


def _explicitly_enabled() -> bool:
    return os.getenv(_OPT_IN_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _configuration_report(settings: Settings) -> dict[str, object]:
    return {
        "schema": "gh.n3w-product.s5-isolated-manager-launcher-check/1",
        "configuration_valid": True,
        "isolated_launcher_explicitly_enabled": True,
        "n3w_runtime_enabled": settings.n3w_runtime_enabled,
        "normal_manager_app_selected": False,
        "network_attempted": False,
        "secret_values_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the explicit isolated-lab N3-W Product S5 Manager service."
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate opt-in/configuration without opening Manager state or network transport",
    )
    args = parser.parse_args(argv)

    if not _explicitly_enabled():
        print(
            f"Configuration error: {_OPT_IN_ENV}=true is required",
            file=sys.stderr,
        )
        return 2
    try:
        settings = Settings.from_env()
    except (TypeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    if not settings.n3w_runtime_enabled:
        print("Configuration error: GH_N3W_RUNTIME_ENABLED=true is required", file=sys.stderr)
        return 2

    if args.check_config:
        print(json.dumps(_configuration_report(settings), sort_keys=True, separators=(",", ":")))
        return 0

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        run_isolated_manager(settings)
    except OSError as error:
        logging.getLogger(__name__).error("Isolated S5 Manager stopped by network error: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
