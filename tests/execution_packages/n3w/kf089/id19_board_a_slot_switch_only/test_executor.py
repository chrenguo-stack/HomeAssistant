from __future__ import annotations

import ast
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
ENTRY = ROOT / "tools/execution_packages/n3w/kf089/id19_board_a_slot_switch_only/executor.py"
IMPL = ROOT / "tools/execution_packages/n3w/kf089/id19_board_a_slot_switch_only/executor_impl.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id19_board_a_slot_switch_only/manifest.json"

spec = importlib.util.spec_from_file_location("id19_executor_impl_test", IMPL)
assert spec and spec.loader
executor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = executor
spec.loader.exec_module(executor)


def _entry(seq: int, state: int) -> bytes:
    raw = bytearray(b"\xff" * executor.OTA_ENTRY_SIZE)
    struct.pack_into("<I", raw, 0, seq)
    struct.pack_into("<I", raw, 24, state)
    struct.pack_into("<I", raw, 28, executor.ota_crc(seq))
    return bytes(raw)


def _pre_otadata(target_state: int = 2) -> bytes:
    raw = bytearray(b"\xff" * executor.id18.OTADATA_SIZE)
    raw[0:executor.OTA_ENTRY_SIZE] = _entry(3, target_state)
    start = 0x1000
    raw[start:start + executor.OTA_ENTRY_SIZE] = _entry(4, 2)
    return bytes(raw)


def test_manifest_freezes_slot_switch_only_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id19_board_a_slot_switch_only"
    assert manifest["prestate_contract"]["selected_slot"] == 1
    assert manifest["prestate_contract"]["target_slot"] == 0
    assert manifest["mutation_contract"]["application_boot_in_same_gate"] is False
    assert manifest["forbidden"]["app0_write"] is True
    assert manifest["forbidden"]["app1_write"] is True


def test_entrypoint_self_check_passes() -> None:
    proc = subprocess.run([sys.executable, str(ENTRY), "--self-check"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["self_check"] == "PASS"


def test_plan_switches_seq4_app1_to_seq5_app0() -> None:
    pre = _pre_otadata()
    plan = executor.plan_slot_switch(pre)
    assert plan.current_slot == 1
    assert plan.target_slot == 0
    assert plan.target_copy_index == 0
    assert plan.old_active_seq == 4
    assert plan.new_seq == 5
    post = executor.verify_post_otadata(pre, plan.expected_post_otadata, plan)
    assert post["selected_slot"] == 0
    assert post["active_seq"] == 5
    assert post["non_target_sector_unchanged"] is True


def test_plan_rejects_unsafe_target_state() -> None:
    try:
        executor.plan_slot_switch(_pre_otadata(target_state=3))
    except executor.StopExecution as exc:
        assert "unsafe to preserve" in str(exc)
    else:
        raise AssertionError("unsafe target state must stop")


def test_source_has_bounded_direct_rom_calls_only() -> None:
    tree = ast.parse(IMPL.read_text(encoding="utf-8"))
    observed = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    prohibited = {"write_" + "flash", "flash_" + "finish"}
    assert observed.isdisjoint(prohibited)
    assert {"flash_begin", "flash_block", "flash_md5sum"}.issubset(observed)


def test_post_verification_rejects_nonexact_image() -> None:
    pre = _pre_otadata()
    plan = executor.plan_slot_switch(pre)
    bad = bytearray(plan.expected_post_otadata)
    bad[-1] ^= 1
    try:
        executor.verify_post_otadata(pre, bytes(bad), plan)
    except executor.StopExecution as exc:
        assert "exact planned image" in str(exc)
    else:
        raise AssertionError("nonexact postimage must stop")
