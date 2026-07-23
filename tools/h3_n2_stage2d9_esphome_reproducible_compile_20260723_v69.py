#!/usr/bin/env python3
"""Run ESPHome 2026.4.3 with the frozen Stage2D9 V69 timestamp."""
from __future__ import annotations

import os

FIXED_BUILD_EPOCH = 1784764800
FIXED_BUILD_TIME_STR = "2026-07-23 00:00:00 +0000"
REQUIRED_ESPHOME_VERSION = "2026.4.3"


def main() -> int:
    os.environ["TZ"] = "UTC"
    if hasattr(__import__("time"), "tzset"):
        __import__("time").tzset()

    from esphome import const, writer
    from esphome.core import CORE

    if const.__version__ != REQUIRED_ESPHOME_VERSION:
        raise SystemExit(
            f"unexpected ESPHome version: {const.__version__}; "
            f"required {REQUIRED_ESPHOME_VERSION}"
        )
    if not hasattr(writer, "get_build_info"):
        raise SystemExit("ESPHome writer.get_build_info is unavailable")

    def fixed_get_build_info() -> tuple[int, int, str, str]:
        return (
            CORE.config_hash,
            FIXED_BUILD_EPOCH,
            FIXED_BUILD_TIME_STR,
            CORE.comment or "",
        )

    writer.get_build_info = fixed_get_build_info

    from esphome.__main__ import main as esphome_main

    return int(esphome_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
