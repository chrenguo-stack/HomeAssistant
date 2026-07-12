from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
sys.path.insert(0, str(SOURCE))

main = importlib.import_module(
    "greenhouse_manager.t1_broker_identity_activation_readiness_bundle"
).main


if __name__ == "__main__":
    raise SystemExit(main())
