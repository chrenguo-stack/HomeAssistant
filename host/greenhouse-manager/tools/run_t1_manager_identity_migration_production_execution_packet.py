from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from greenhouse_manager.t1_manager_identity_migration_production_execution_packet import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
