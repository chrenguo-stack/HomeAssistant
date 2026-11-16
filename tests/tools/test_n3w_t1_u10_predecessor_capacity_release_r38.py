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
    / "u10_predecessor_capacity_release_r38"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "u10_r38_executor",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r38_manifest_is_explicitly_granted_and_stops_before_u11():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["live_execution_authorized"] is True
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert manifest["transition_source_delivery"] == (
        "EXACT_PACKAGE_BOUND_IN_MEMORY_NO_LIVE_SOURCE_MUTATION"
    )
    contract = manifest["execution_contract"]
    assert contract["r37_preclaim_required"] is True
    assert contract["exact_stopped_homeassistant_container_only"] is True
    assert contract["exact_predecessor_image_only"] is True
    assert contract["manager_broker_release_forbidden"] is True
    assert contract["broad_prune_forbidden"] is True
    assert contract["target_image_load_forbidden"] is True
    assert contract["service_mutation_forbidden"] is True
    assert contract["u11_plus_forbidden"] is True
    assert contract["live_source_mutation"] is False
    assert contract["usb_u10_metadata_sync_before_host_transaction"] is True
    assert contract["one_shot_outer_authorization"] is True
    assert contract["postclaim_replay_forbidden"] is True
    assert contract["transport_ambiguity_requires_reconciliation"] is True
    assert manifest["stop_boundary"] == (
        "STOP_AFTER_REAL_T1_U10_BEFORE_U11_TARGET_INSTALL"
    )


def test_r38_remote_payload_compiles_and_has_no_forbidden_broad_actions():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r38-remote>", "exec")
    source = executor.REMOTE_SCRIPT
    forbidden = (
        "docker system prune",
        "docker image prune",
        '["docker", "load"',
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        "record_target_started(",
        "U11_TARGET_INSTALLED_STARTED",
    )
    for token in forbidden:
        assert token not in source


def test_r38_deletes_only_exact_ha_container_and_exact_predecessor_image():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'run(["docker", "rm", ha_id]' in source
    assert 'run(["docker", "image", "rm", predecessor_id]' in source
    assert 'plan["containers"]["homeassistant"]["container_id"]' in source
    assert 'plan["predecessor_runtime_image_id"]' in source
    assert 'verify_peer_continuity(plan)' in source
    assert '"manager_broker_release_forbidden": True' in source


def test_r38_requires_observed_release_before_u10_transition():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert "predecessor_runtime_released=True" in source
    assert "predecessor_image_released=True" in source
    assert "target_internal_image_absent=True" in source
    transition_index = source.index("next_tx = transition(")
    runtime_verify_index = source.index(
        'result["predecessor_runtime_delete"] = True'
    )
    image_verify_index = source.index(
        'result["predecessor_image_delete"] = True'
    )
    assert runtime_verify_index < transition_index
    assert image_verify_index < transition_index


def test_r38_persists_u10_usb_before_host_transaction():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    usb_index = source.index(
        "backend.sync_transaction_metadata(next_tx, media)"
    )
    host_index = source.index("store.write(next_tx)")
    assert usb_index < host_index


def test_r38_uses_exact_package_transition_source_without_live_source_write():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    local = EXECUTOR.read_text(encoding="utf-8")
    assert "load_exact_transition_source(plan)" in source
    assert 'plan["transition_source_b64"]' in source
    assert 'plan["transition_source_sha256"]' in source
    assert "TRANSITION_SOURCE.read_bytes()" in local
    assert "host_source_mutation" not in source
    assert "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb.py" not in source


def test_r38_requires_r37_preclaim_before_remote_execute():
    source = EXECUTOR.read_text(encoding="utf-8")
    gate_bind = source.index('r37_plan["gate_id"] = r37.GATE_ID')
    preclaim = source.index("pre_transport, pre = r37.remote_preflight(")
    execute = source.index('result["remote_execute_invoked"] = True')
    assert gate_bind < preclaim < execute
    assert "r37_plan," in source[preclaim:execute]
    assert "r38_live_execution_not_authorized" in source
    assert "authorization_invalid" in source

def test_r38_postclaim_ambiguity_is_consumed_no_replay():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "reconcile_after_invoke" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert "destructive_cutover=True" in source


def test_r38_binds_r37_and_fail_closed_u10_transition_source():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["source_authority"]["r37_result"] == (
        "U10_R37_READONLY_PREFLIGHT_PASS"
    )
    assert manifest["source_authority"]["r37_execution_id"] == (
        "u10-r37-readonly-20261116T024337Z"
    )
    assert manifest["source_authority"]["u10_fail_closed_ha_usb_blob"] == (
        "01ced6d4b643cc9a0881d48efc9b7601dc5fb4f6"
    )
    assert manifest["expected_u9_entry"]["transaction_sha256"] == (
        "69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3"
    )
