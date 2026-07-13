from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
sys.path.insert(0, str(SOURCE))

main = importlib.import_module(
    "greenhouse_manager.t1_homeassistant_mqtt_postactivation_handoff"
).main


if __name__ == "__main__":
    raise SystemExit(main())
