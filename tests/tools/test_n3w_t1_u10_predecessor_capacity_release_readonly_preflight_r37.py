from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u10_predecessor_capacity_release_readonly_preflight_r37"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u10_r37_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r37_manifest_is_ungranted_readonly_and_stops_before_u10():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["read_only_preflight"] is True
    assert manifest["real_t1_readonly_execution_authorized"] is False
    assert manifest["live_execution_authorized"] is False
    assert manifest["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = manifest["execution_contract"]
    assert contract["r35_consumed_no_replay_required"] is True
    assert contract["r36_consumed_no_replay_required"] is True
    assert contract["exact_u9_transaction_required"] is True
    assert contract["fresh_recovery_capacity_required"] is True
    assert contract["exact_homeassistant_stopped_container_allowlist_required"] is True
    assert contract["manager_broker_release_forbidden"] is True
    for key in (
        "transaction_mutation",
        "usb_mutation",
        "predecessor_runtime_delete",
        "predecessor_image_delete",
        "target_image_load",
        "service_mutation",
        "u10_transition",
        "u11_plus",
        "board_access",
        "merge",
    ):
        assert contract[key] is False
    assert manifest["expected_u9_entry"]["transaction_sha256"] == (
        "69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3"
    )


def test_r37_remote_payload_compiles_and_has_no_mutation_commands():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r37-remote>", "exec")
    source = executor.REMOTE_SCRIPT
    forbidden = (
        '["docker", "rm"',
        '["docker", "image", "rm"',
        '["docker", "load"',
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        "mkfs",
        "wipefs",
        "sgdisk",
        "parted",
        ".write_text(",
        ".write_bytes(",
        "os.replace(",
        ".unlink(",
        ".mkdir(",
        "record_predecessor_capacity_released(",
        "record_target_started(",
    )
    for token in forbidden:
        assert token not in source


def test_r37_local_entry_has_no_execute_switch_and_requires_separate_readonly_grant():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'parser.add_argument("--execute"' not in source
    assert "r37_real_t1_readonly_execution_not_authorized" in source
    assert "real_t1_readonly_execution_authorized" in source
    assert "readonly_authorized" in source
    assert '"granted": readonly_authorized' in source
    assert '"u10_transition": False' in source
    assert '"u11_plus": False' in source


def test_r37_binds_fail_closed_u10_source_and_r36_authority():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = manifest["source_authority"]
    assert authority["u9_closure_head"] == (
        "e841ede79abe9ca4b014adc9d2729c61a9cfbda1"
    )
    assert authority["u10_fail_closed_source_head"] == (
        "cbc28617c800a1b1c16e18b1d5762ea1b2123155"
    )
    assert authority["u10_fail_closed_ha_usb_blob"] == (
        "01ced6d4b643cc9a0881d48efc9b7601dc5fb4f6"
    )
    assert authority["r36_grant_head"] == (
        "f78dc7da7998ce2d3d275dc05e09d173d84f200b"
    )
