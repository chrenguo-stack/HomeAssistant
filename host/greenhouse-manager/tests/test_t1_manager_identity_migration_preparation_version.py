from __future__ import annotations

import tomllib
from pathlib import Path


def test_manager_package_version_includes_node_auth_fallback_model() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        document = tomllib.load(stream)
    assert document["project"]["version"] == "0.4.89"
