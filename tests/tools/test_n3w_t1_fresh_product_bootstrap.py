from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_fresh_product_bootstrap.py"


def load_tool():
    name = "n3w_t1_fresh_product_bootstrap"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_future_authorization_is_fresh_bootstrap_specific() -> None:
    tool = load_tool()
    assert tool.AUTHORIZATION_ID == (
        "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_"
        "LIVE_APPLY_20261012_01"
    )
    assert "PRODUCTION_STACK_STAGING" not in tool.AUTHORIZATION_ID


def test_final_targets_do_not_include_host_baseline() -> None:
    tool = load_tool()
    targets = set(tool.FINAL_DIRS) | set(tool.FINAL_FILES)

    assert "/var/lib/docker" not in targets
    assert "/etc/NetworkManager" not in targets
    assert "/etc/ssh" not in targets
    assert "/" not in targets


def test_apply_rejects_wrong_authorization_before_root_check(
    tmp_path: Path,
) -> None:
    tool = load_tool()

    with pytest.raises(tool.BootstrapError, match="authorization_id_mismatch"):
        tool.execute_apply(tmp_path, "WRONG")


def test_source_forbids_broad_prune_and_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "docker system prune" not in source.split("def self_check", 1)[0]
    assert "docker volume prune" not in source.split("def self_check", 1)[0]
    assert "docker network prune" not in source.split("def self_check", 1)[0]
    assert "docker compose up" not in source.split("def self_check", 1)[0]
