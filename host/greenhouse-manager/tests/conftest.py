from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HOMEASSISTANT_TEST_ROOT = Path(__file__).resolve().parents[2] / "homeassistant"
if str(_HOMEASSISTANT_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOMEASSISTANT_TEST_ROOT))

_STAGE2C2_NODE_E2E_FILE = "test_stage2c2_node_manager_e2e_20260721_v47.py"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run the C++ peer closure only when its compiled peer is supplied."""
    if os.environ.get("STAGE2C2_NODE_PEER"):
        return

    missing_peer = pytest.mark.skip(
        reason="requires the Stage 2C-2 compiled C++ node peer"
    )
    for item in items:
        if _STAGE2C2_NODE_E2E_FILE in item.nodeid:
            item.add_marker(missing_peer)
