from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
ENTRY = ROOT / "tools/execution_packages/n3w/kf089/id20_board_a_schema5_boot_postcheck/executor.py"
IMPL = ROOT / "tools/execution_packages/n3w/kf089/id20_board_a_schema5_boot_postcheck/executor_impl.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id20_board_a_schema5_boot_postcheck/manifest.json"

spec = importlib.util.spec_from_file_location("id20_executor_impl_test", IMPL)
assert spec and spec.loader
executor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = executor
spec.loader.exec_module(executor)

entry_spec = importlib.util.spec_from_file_location("id20_executor_entry_test", ENTRY)
assert entry_spec and entry_spec.loader
entry = importlib.util.module_from_spec(entry_spec)
sys.modules[entry_spec.name] = entry
entry_spec.loader.exec_module(entry)


def _snapshot() -> dict[str, int]:
    value = {
        "schema_version": 5,
        "boot_session": executor.PRIOR_BOARD_A_BOOT_SESSION + 1,
        "snapshot_uptime_ms": 45000,
        "runtime_start_mode": 0,
        "path_state": 0,
        "current_channel": 11,
        "direct_channel_hint": 11,
        "relay_advertisement_attempts": 20,
        "relay_advertisement_submit_success": 20,
        "relay_advertisement_submit_failure": 0,
        "broadcast_completion_count": 20,
        "broadcast_completion_success": 20,
        "broadcast_completion_failure": 0,
        "relay_active_count": 0,
        "relay_telemetry_attempts": 0,
    }
    for field in executor.COMPACT_COUNTER_FIELDS:
        value[field] = 0
    return value


def test_manifest_freezes_read_only_boot_postcheck_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id20_board_a_schema5_boot_postcheck"
    assert manifest["prestate_contract"]["selected_slot"] == 0
    assert manifest["prestate_contract"]["active_ota_seq"] == 5
    assert manifest["operator_contract"]["single_normal_boot"] is True
    assert manifest["operator_contract"]["minimum_interlock_elapsed_seconds"] == 45
    assert manifest["forbidden"]["flash_write"] is True
    assert manifest["forbidden"]["nvs_write"] is True
    assert manifest["forbidden"]["controlled_rf_experiment"] is True


def test_entrypoint_self_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENTRY), "--self-check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["self_check"] == "PASS"


def test_schema5_direct_runtime_baseline_passes() -> None:
    result = executor.adjudicate_snapshot(_snapshot())
    assert result["schema_version"] == 5
    assert result["boot_session_changed_from_id16"] is True
    assert result["path_state"] == 0
    assert result["compact_baseline_clean"] is True
    assert all(value == 0 for value in result["compact_counters"].values())


def test_discovery_start_mode_can_recover_to_direct() -> None:
    snapshot = _snapshot()
    snapshot["runtime_start_mode"] = 1
    result = executor.adjudicate_snapshot(snapshot)
    assert result["runtime_start_mode"] == 1
    assert result["path_state"] == 0


def test_schema_mismatch_stops() -> None:
    snapshot = _snapshot()
    snapshot["schema_version"] = 4
    try:
        executor.adjudicate_snapshot(snapshot)
    except executor.StopExecution as exc:
        assert "schema mismatch" in str(exc)
    else:
        raise AssertionError("schema mismatch must stop")


def test_stale_boot_session_stops() -> None:
    snapshot = _snapshot()
    snapshot["boot_session"] = executor.PRIOR_BOARD_A_BOOT_SESSION
    try:
        executor.adjudicate_snapshot(snapshot)
    except executor.StopExecution as exc:
        assert "did not change" in str(exc)
    else:
        raise AssertionError("stale boot session must stop")


def test_nonzero_compact_counter_stops_clean_baseline() -> None:
    snapshot = _snapshot()
    snapshot["compact_rx_count"] = 1
    try:
        executor.adjudicate_snapshot(snapshot)
    except executor.StopExecution as exc:
        assert "compact baseline is not zero" in str(exc)
    else:
        raise AssertionError("contaminated compact baseline must stop")


def test_runtime_without_advertisement_stops() -> None:
    snapshot = _snapshot()
    snapshot["relay_advertisement_attempts"] = 0
    try:
        executor.adjudicate_snapshot(snapshot)
    except executor.StopExecution as exc:
        assert "did not attempt" in str(exc)
    else:
        raise AssertionError("runtime without advertisement evidence must stop")


def test_interlock_completion_is_independent_of_postcheck_result() -> None:
    interlock = {
        "token_match": True,
        "single_normal_boot_attested": True,
        "fresh_rom_reentry_attested": True,
        "observed_elapsed_seconds": 60.0,
        "minimum_elapsed_seconds": 45,
    }
    assert entry._operator_interlock_completed(interlock) is True
    interlock["observed_elapsed_seconds"] = 44.9
    assert entry._operator_interlock_completed(interlock) is False
    interlock["observed_elapsed_seconds"] = 60.0
    interlock["token_match"] = False
    assert entry._operator_interlock_completed(interlock) is False


def test_source_contains_no_flash_mutation_calls() -> None:
    tree = ast.parse(IMPL.read_text(encoding="utf-8"))
    observed = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    prohibited = {
        "flash_" + "begin",
        "flash_" + "block",
        "flash_" + "finish",
        "write_" + "flash",
        "erase_" + "flash",
        "erase_" + "region",
        "write_" + "mem",
    }
    assert observed.isdisjoint(prohibited)
    assert "build_read_mac_command" in observed
    assert "build_read_flash_command" in observed
