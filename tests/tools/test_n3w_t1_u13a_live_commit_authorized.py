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
    / "u13a_live_commit_authorized"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "u13a_live_executor",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_u13a_live_authorized_manifest_is_exactly_granted_once():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["u13a_live_execution_authorized"] is True
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = manifest["execution_contract"]
    assert contract["fresh_u13a_readonly_preflight_required"] is True
    assert contract["exact_recovery_assets_required_preclaim"] is True
    assert contract["forward_commit_classification_required"] is True
    assert contract["explicit_u13a_user_authorization_granted"] is True
    assert contract["one_shot_outer_authorization"] is True
    assert contract["postclaim_replay_forbidden"] is True
    assert contract["usb_u13a_metadata_sync_before_host_transaction"] is True
    assert contract["service_mutation"] is False
    assert contract["image_mutation"] is False
    assert contract["ha_data_restore"] is False
    assert contract["predecessor_image_restore"] is False
    assert contract["u13b_transition"] is False
    assert contract["board_access"] is False
    assert contract["merge"] is False
    assert manifest["stop_boundary"] == ("STOP_BEFORE_REAL_T1_U13A_LIVE_EXECUTION_" "UNTIL_AUTHORIZED_PACKAGE_CI_PASS")


def test_u13a_live_remote_payload_compiles():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<u13a-live-remote>", "exec")


def test_u13a_live_performs_fresh_readonly_before_remote_execute():
    source = EXECUTOR.read_text(encoding="utf-8")
    preflight = source.index("pre_transport, pre = readonly.remote_preflight(")
    execute = source.index('result["remote_execute_invoked"] = True')
    assert preflight < execute
    between = source[preflight:execute]
    assert "U13A_COMMIT_READONLY_PREFLIGHT_PASS" in between
    assert 'pre.get("forward_commit_eligible") is not True' in between
    assert 'pre.get("rollback_required") is not False' in between


def test_u13a_live_authorized_package_requires_exact_granted_state():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert manifest["source_authority"]["authorization_grant"] == (
        "EXECUTE U13A LIVE COMMIT: YES"
    )
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'raise Stop("local_u13a_live_authorization_invalid")' in source


def test_u13a_live_claims_once_and_forbids_replay():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'durable_json_once(state_root / "authorization_claim.json", claim)' in source
    assert '"consumed": True' in source
    assert '"replay_permitted": False' in source
    assert "u13a_live_state_root_residue" in source


def test_u13a_live_transition_is_u12_to_u13a_only():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'transition = namespace.get("record_commit")' in source
    assert 'current.get("phase") != "U12_TARGET_ACCEPTANCE"' in source
    assert 'next_tx.get("phase") != "U13A_COMMITTED"' in source
    assert 'next_tx.get("status") != "COMMITTED"' in source
    assert "record_rollback_complete(" not in source


def test_u13a_live_requires_forward_commit_after_claim():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert (
        'classification != "FORWARD_COMMIT_ELIGIBLE"'
        in source
    )
    assert "u13a_live_forward_commit_not_eligible_after_claim" in source


def test_u13a_live_persists_usb_before_host_transaction():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    usb_index = source.index(
        "backend.sync_transaction_metadata(next_tx, media)"
    )
    host_index = source.index("store.write(next_tx)")
    assert usb_index < host_index


def test_u13a_live_terminal_requires_host_and_usb_u13a():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'transaction.get("phase") != "U13A_COMMITTED"' in source
    assert 'transaction.get("status") != "COMMITTED"' in source
    assert 'transaction.get("recovery_required") is not False' in source
    assert 'phase.get("phase") != "U13A_COMMITTED"' in source


def test_u13a_live_detects_partial_usb_only_and_host_only():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert "STOP_PARTIAL_U13A_USB_ONLY" in source
    assert "STOP_PARTIAL_U13A_HOST_ONLY" in source
    assert '"replay_permitted": False' in source


def test_u13a_live_transport_ambiguity_reconciles_without_replay():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "reconcile_after_invoke" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert "--status-only" in source


def test_u13a_live_does_not_mutate_services_images_or_restore_data():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    live_start = source.index("def execute(plan, authorization_id, confirmation):")
    live_execute = source[live_start:]
    forbidden = (
        '["systemctl", "start"',
        '["systemctl", "stop"',
        '["systemctl", "restart"',
        '["docker", "load"',
        '["docker", "rm"',
        '["docker", "image", "rm"',
        "docker system prune",
        "docker image prune",
        "record_rollback_complete(",
        "restore_backup(",
        "restore_predecessor(",
    )
    for token in forbidden:
        assert token not in live_execute
    assert '"service_mutation": False' in live_execute
    assert '"image_mutation": False' in live_execute


def test_u13a_live_keeps_static_usb_authority_hashes_unchanged():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'observed["manifest"] != prior["manifest"]' in source
    assert (
        'observed["content_authority"] != prior["content_authority"]'
        in source
    )
    assert 'observed["checksums"] != prior["checksums"]' in source


def test_u13a_live_package_source_authority_includes_executor_and_transition():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = manifest["package_source_authority"]
    assert (
        "tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/executor.py"
        in authority
    )
    assert "tools/n3w_t1_core_updater_ha_usb.py" in authority
