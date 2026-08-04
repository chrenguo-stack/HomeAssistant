from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .c06b2_runtime_wiring import (
    manager_c06b2_runtime_enabled,
    run_manager_service,
)
from .config import Settings


def _configuration_report(
    settings: Settings,
    *,
    c06b2_runtime_enabled: bool,
) -> dict[str, object]:
    return {
        "configuration_valid": True,
        "mqtt_authentication_configured": bool(
            settings.mqtt_username and settings.mqtt_password
        ),
        "password_file_used": bool(os.getenv("GH_MQTT_PASSWORD_FILE")),
        "inline_password_used": bool(os.getenv("GH_MQTT_PASSWORD")),
        "manager_c06b2_runtime_enabled": c06b2_runtime_enabled,
        "network_attempted": False,
        "secret_values_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run greenhouse-manager.")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate configuration and secret-file readability without network access",
    )
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        c06b2_runtime_enabled = manager_c06b2_runtime_enabled()
    except (TypeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.check_config:
        print(
            json.dumps(
                _configuration_report(
                    settings,
                    c06b2_runtime_enabled=c06b2_runtime_enabled,
                ),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        run_manager_service(settings)
    except OSError as exc:
        logging.getLogger(__name__).error("Service stopped by network error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
