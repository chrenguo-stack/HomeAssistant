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
    / "u12_target_acceptance_live"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "u12_live_executor",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_u12_live_manifest_is_bounded_and_explicitly_authorized():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["u12_live_execution_authorized"] is True
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = manifest["execution_contract"]
    assert contract["fresh_u12_readonly_preflight_required"] is True
    assert contract["explicit_u12_user_authorization_granted"] is True
    assert contract["usb_u12_metadata_sync_before_host_transaction"] is True
    assert contract["one_shot_outer_authorization"] is True
    assert contract["postclaim_replay_forbidden"] is True
    assert contract["service_mutation"] is False
    assert contract["image_mutation"] is False
    assert contract["r42_replay"] is False
    assert contract["u13_plus"] is False
    assert contract["board_access"] is False
    assert contract["merge"] is False
    assert manifest["stop_boundary"] == (
        "STOP_AFTER_DURABLE_U12_BEFORE_U13_PLUS"
    )


def test_u12_live_remote_payload_compiles():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<u12-live-remote>", "exec")


def test_u12_live_performs_fresh_readonly_before_remote_execute():
    source = EXECUTOR.read_text(encoding="utf-8")
    preflight = source.index("pre_transport, pre = readonly.remote_mode(")
    execute = source.index('result["remote_execute_invoked"] = True')
    assert preflight < execute
    assert "U12_READONLY_PREFLIGHT_PASS" in source[preflight:execute]


def test_u12_live_claims_once_and_forbids_replay():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'durable_json_once(state_root / "authorization_claim.json", claim)' in source
    assert '"consumed": True' in source
    assert '"replay_permitted": False' in source
    assert "u12_live_state_root_residue" in source


def test_u12_live_transition_is_u11_to_u12_only():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'transition = namespace.get("record_target_accepted")' in source
    assert 'next_tx.get("phase") != "U12_TARGET_ACCEPTANCE"' in source
    assert "record_commit(" not in source
    assert "U13A_COMMITTED" not in source


def test_u12_live_persists_usb_before_host_transaction():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    usb_index = source.index(
        "backend.sync_transaction_metadata(next_tx, media)"
    )
    host_index = source.index("store.write(next_tx)")
    assert usb_index < host_index


def test_u12_live_does_not_mutate_services_or_images():
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
    )
    for token in forbidden:
        assert token not in live_execute
    assert '"service_mutation": False' in live_execute
    assert '"image_mutation": False' in live_execute


def test_u12_live_records_acceptance_performance_without_fake_ota_baseline():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert "acceptance_started = time.monotonic_ns()" in source
    assert '"u12_acceptance_duration_ms": acceptance_ms' in source
    assert '"mqtt_acceptance_duration_ms"' in source
    assert '"homeassistant_readiness_duration_ms"' in source
    assert '"normal_ota_baseline_available": False' in source
    assert '"user_visible_downtime_measured": False' in source
    assert '"performance_target_status": "U12_ACCEPTANCE_PHASE_ONLY_PASS"' in source


def test_u12_live_transport_ambiguity_reconciles_without_replay():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "reconcile_after_invoke" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert "--status-only" in source
