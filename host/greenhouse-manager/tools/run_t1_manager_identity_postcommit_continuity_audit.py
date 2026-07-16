from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODULE = "greenhouse_manager.t1_manager_identity_postcommit_continuity_audit_v2"
main = import_module(MODULE).main


if __name__ == "__main__":
    raise SystemExit(main())
