from __future__ import annotations

import os

import pytest

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
