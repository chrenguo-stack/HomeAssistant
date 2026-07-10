from __future__ import annotations

import logging
import sys

from .config import Settings
from .mqtt_service import ManagerMqttService


def main() -> int:
    try:
        settings = Settings.from_env()
    except (TypeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        ManagerMqttService(settings).run()
    except OSError as exc:
        logging.getLogger(__name__).error("Service stopped by network error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
