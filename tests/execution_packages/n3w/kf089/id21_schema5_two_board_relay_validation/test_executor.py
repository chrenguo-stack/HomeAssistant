from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
ENTRY = ROOT / "tools/execution_packages/n3w/kf089/id21_schema5_two_board_relay_validation/executor.py"
IMPL = ROOT / "tools/execution_packages/n3w/kf089/id21_schema5_two_board_relay_validation/executor_impl.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id21_schema5_two_board_relay_validation/manifest.json"

spec = importlib.util.spec_from_file_location("id21_executor_impl_test", IMPL)
assert spec and spec.loader
executor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = executor
spec.loader.exec_module(executor)


def _snapshot(*, session: int, path: int = 0) -> dict[str, int]:
    value = {
        "schema_version": 5,
        "boot_session": session,
        "snapshot_uptime_ms": 70000,
        "runtime_start_mode": 0,
        "path_state": path,
        "current_channel": 11,
        "direct_channel_hint": 11,
        "relay_advertisement_attempts": 10,
        "relay_advertisement_submit_success": 10,
        "relay_advertisement_submit_failure": 0,
        "relay_active_count": 0,
        "relay_telemetry_attempts": 0,
        "relay_telemetry_success": 0,
        "accept_verify": 0,
        "peer_install_success": 0,
        "unicast_completion_count": 0,
        "unicast_completion_success": 0,
        "unicast_completion_failure": 0,
    }
    for field in executor.COMPACT_FIELDS:
        value[field] = 0
    return value


def _relay_pair() -> tuple[dict[str, int], dict[str, int]]:
    a = _snapshot(session=200, path=0)
    b = _snapshot(session=300, path=2)
    b.update(
        {
            "relay_active_count": 1,
            "accept_verify": 1,
            "peer_install_success": 1,
            "relay_telemetry_attempts": 8,
            "relay_telemetry_success": 8,
            "unicast_completion_count": 8,
            "unicast_completion_success": 7,
            "unicast_completion_failure": 1,
        }
    )
    a.update(
        {
            "compact_rx_count": 7,
            "compact_decode_success": 7,
            "compact_forward_attempts": 7,
            "compact_forward_submit_success": 7,
        }
    )
    return a, b


def test_manifest_freezes_two_session_read_only_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id21_schema5_two_board_relay_validation"
    assert manifest["predecessor"]["execution_package_commit"] == executor.ID20R1_EXECUTION_PACKAGE_COMMIT
    assert manifest["operator_contract"]["normal_boots_per_board"] == 2
    assert manifest["operator_contract"]["direct_baseline_min_seconds"] == 60
    assert manifest["operator_contract"]["relay_staging_min_seconds"] == 45
    assert manifest["operator_contract"]["relay_window_min_seconds"] == 150
    assert manifest["forbidden"]["flash_write"] is True
    assert manifest["forbidden"]["nvs_write"] is True
    assert manifest["forbidden"]["t1_access"] is True
    assert manifest["forbidden"]["third_normal_boot"] is True


def test_entrypoint_self_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENTRY), "--self-check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["self_check"] == "PASS"


def test_board_a_prestate_requires_exact_zero_compact_baseline() -> None:
    snapshot = _snapshot(session=100)
    summary = {
        "selected_slot": 0,
        "active_seq": 5,
        "active_state": 2,
        "app0_sha256": executor.SCHEMA5_FIRMWARE_SHA256,
        "app1_sha256": "0" * 64,
        "selected_image_sha256": executor.SCHEMA5_FIRMWARE_SHA256,
        "snapshot": snapshot,
    }
    result = executor.adjudicate_prestate("board_a", summary)
    assert result["selected_slot"] == 0
    snapshot["compact_rx_count"] = 1
    try:
        executor.adjudicate_prestate("board_a", summary)
    except executor.StopExecution as exc:
        assert "compact baseline" in str(exc)
    else:
        raise AssertionError("nonzero Board A prestate compact counter must stop")


def test_direct_baseline_requires_new_direct_clean_session() -> None:
    snapshot = _snapshot(session=101, path=0)
    result = executor.adjudicate_direct_baseline(
        role="board_a", snapshot=snapshot, pre_boot_session=100
    )
    assert result["boot_session_changed"] is True
    assert result["path_state"] == 0
    snapshot["relay_active_count"] = 1
    try:
        executor.adjudicate_direct_baseline(
            role="board_a", snapshot=snapshot, pre_boot_session=100
        )
    except executor.StopExecution as exc:
        assert "RelayActive" in str(exc)
    else:
        raise AssertionError("RelayActive contamination must stop Direct baseline")


def test_relay_chain_success_localizes_through_a_forward_submit() -> None:
    a, b = _relay_pair()
    assert executor.relay_first_unproven_stage(a, b) is None
    result = executor.adjudicate_relay_phase(
        a=a,
        b=b,
        baseline_a_boot_session=101,
        baseline_b_boot_session=102,
    )
    assert result["board_side_relay_chain_proven"] is True
    assert result["first_unproven_stage"] is None
    assert result["board_a"]["compact_counters"]["compact_forward_submit_success"] == 7
    assert result["board_b"]["unicast_completion_success"] == 7


def test_relay_chain_reports_a_compact_rx_first() -> None:
    a, b = _relay_pair()
    for field in executor.COMPACT_FIELDS:
        a[field] = 0
    assert executor.relay_first_unproven_stage(a, b) == "A_COMPACT_RX"


def test_relay_chain_distinguishes_child_binding_and_decode() -> None:
    a, b = _relay_pair()
    a["compact_rx_count"] = 3
    a["compact_decode_success"] = 0
    a["compact_forward_attempts"] = 0
    a["compact_forward_submit_success"] = 0
    a["compact_child_binding_failure"] = 3
    assert executor.relay_first_unproven_stage(a, b) == "A_COMPACT_CHILD_BINDING"
    a["compact_child_binding_failure"] = 0
    a["compact_decode_failure"] = 3
    assert executor.relay_first_unproven_stage(a, b) == "A_COMPACT_DECODE"


def test_relay_chain_requires_b_unicast_completion_before_a() -> None:
    a, b = _relay_pair()
    b["unicast_completion_success"] = 0
    assert executor.relay_first_unproven_stage(a, b) == "B_UNICAST_TX_COMPLETION"


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
