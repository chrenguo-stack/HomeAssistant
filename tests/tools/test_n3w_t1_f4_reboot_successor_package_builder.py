from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_successor_package_builder.py"


def load_tool():
    name = "n3w_t1_f4_reboot_successor_package_builder"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_successor_control_package(tmp_path: Path) -> None:
    tool = load_tool()
    destination = tmp_path / "package"
    result = tool.build_package(
        ROOT,
        destination,
        source_head="a" * 40,
    )

    assert result["status"] == "PASS"
    assert result["source_head"] == "a" * 40
    assert result["file_count"] == 4
    assert result["secret_values_included"] is False
    assert result["live_runtime_mutation"] is False
    assert result["reboot_executed"] is False
    assert result["board_access"] is False

    manifest = json.loads(
        (destination / tool.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["schema"] == tool.SCHEMA
    assert manifest["source_head"] == "a" * 40
    assert {item["path"] for item in manifest["files"]} == set(tool.FILES)
    assert manifest["secret_values_included"] is False
    assert manifest["live_runtime_mutation"] is False
    assert manifest["reboot_executed"] is False
    assert manifest["board_access"] is False


def test_package_file_set_matches_authority_contract() -> None:
    builder = load_tool()
    authority_path = ROOT / "tools/n3w_t1_f4_reboot_authority.py"
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_f4_reboot_authority_for_package_test",
        authority_path,
    )
    assert spec is not None and spec.loader is not None
    authority = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(authority)

    assert set(builder.FILES) == set(authority.CONTROL_TARGETS)
