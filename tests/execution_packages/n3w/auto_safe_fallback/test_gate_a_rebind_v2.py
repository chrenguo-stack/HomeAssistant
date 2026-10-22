from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
NETWORK_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_t1_network_preflight_v2/executor.py"
REBUILD_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_private_rebuild_v2/executor.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


network = load(NETWORK_PATH, "gate_a_t1_network_preflight_v2")
rebuild = load(REBUILD_PATH, "gate_a_private_rebuild_v2")


def test_network_preflight_is_t1_readonly_and_has_no_board_transport() -> None:
    source = NETWORK_PATH.read_text(encoding="utf-8").lower()
    for token in (
        "esptool",
        "write-flash",
        "/dev/cu.",
        "/dev/tty",
        '"docker", "run"',
        '"docker", "rm"',
        '"docker", "restart"',
        '"ip", "addr", "add"',
        '"ip", "addr", "del"',
        '"systemctl"',
    ):
        assert token.lower() not in source


def test_network_preflight_proves_new_runtime_bindings() -> None:
    source = network.REMOTE
    for token in (
        '"ip", "-j", "-4", "route", "show", "default"',
        '"ip", "-j", "-4", "addr", "show", "dev", dev',
        '"docker", "inspect", broker_ids[0]',
        '"docker", "inspect", "greenhouse-manager"',
        '"ss", "-H", "-ltn4"',
    ):
        assert token in source
    assert network.SCHEMA == "n3w.auto-safe-fallback.gate-a-t1-network-preflight-v2/1"


def test_private_rebuild_reuses_exact_legacy_builder_and_no_live_board_access() -> None:
    assert rebuild.LEGACY_EXECUTOR_BLOB == "18e5d3543c10bb1d5c35b6c8a69c57849cf79f70"
    assert rebuild.BOARD_B_HARDWARE_ID_SHA256 == "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
    assert rebuild.PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    source = REBUILD_PATH.read_text(encoding="utf-8").lower()
    for token in ("esptool", "write-flash", "/dev/cu.", "/dev/tty"):
        assert token not in source
    assert "frozen_public_authority_not_live_board_access" in source
    assert '"board_access": false' in source


def test_private_rebuild_marks_prior_application_superseded() -> None:
    source = REBUILD_PATH.read_text(encoding="utf-8")
    assert '"prior_private_application_superseded": True' in source
    assert '"restore_host": network["t1"]["current_ip"]' in source
