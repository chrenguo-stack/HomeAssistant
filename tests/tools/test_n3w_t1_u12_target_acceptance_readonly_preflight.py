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
    / "u12_target_acceptance_readonly_preflight"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u12_preflight_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_u12_manifest_grants_readonly_only_and_binds_u11_r42():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["read_only_preflight"] is True
    assert manifest["real_t1_readonly_execution_authorized"] is True
    assert manifest["u12_live_execution_authorized"] is False
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert manifest["expected_u11_entry"]["transaction_sha256"] == (
        "33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471"
    )
    assert manifest["r42"]["execution_id"] == (
        "u11-r42-live02-20261116T152940Z"
    )
    assert manifest["r42"]["replay_permitted"] is False
    assert manifest["expected_u11_entry"]["mirror_sha256"]["phase"] == (
        "8f2ba37e93577452ffd2b6dfc1cc5febbf717d1bf8c3ed2de8ec57ccf69e6921"
    )


def test_u12_remote_payload_compiles_and_has_no_mutation_commands():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<u12-preflight-remote>", "exec")
    source = executor.REMOTE_SCRIPT
    forbidden = (
        '["docker", "load"',
        '["docker", "rm"',
        '["docker", "image", "rm"',
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        "mkfs",
        "wipefs",
        "sgdisk",
        "parted",
        "record_target_accepted(",
        "record_commit(",
        "rewrite_component_image(",
        "start_services(",
        "activate_component(",
    )
    for token in forbidden:
        assert token not in source


def test_u12_preflight_does_not_rehash_or_reread_large_archives():
    source = load_executor().REMOTE_SCRIPT
    assert "homeassistant-arm64.tar.gz" not in source
    assert "verify_prepared_target(" not in source
    assert "verify_recovery_assets_and_capacity(" not in source
    assert "docker load" not in source


def test_u12_preflight_uses_monotonic_timing_and_keeps_observation_readonly():
    source = load_executor().REMOTE_SCRIPT
    assert "time.monotonic_ns()" in source
    assert '"preflight_total_ms"' in source
    assert '"mqtt_acceptance_observation_ms"' in source
    assert '"homeassistant_readiness_observation_ms"' in source
    assert '"u12_acceptance": False' in source
    assert '"u12_live_execution_authorized": False' in source
    assert '"transaction_mutation": False' in source
    assert '"usb_mutation": False' in source
    assert '"service_mutation": False' in source
    assert '"u12_transition": False' in source


def test_u12_preflight_checks_durable_u11_usb_r42_and_runtime_before_eligibility():
    source = load_executor().REMOTE_SCRIPT
    ordered = [
        "verify_transaction_u11(plan)",
        "verify_r42_ledger(plan)",
        "require_bound_mount(plan)",
        "verify_usb_mirror_u11(plan, transaction)",
        "verify_runtime_u11(plan)",
        "observe_acceptance_readiness(plan)",
        '"u12_readonly_eligible": True',
    ]
    positions = [source.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_u12_r42_failure_ledger_or_existing_u12_state_fail_closed():
    source = load_executor().REMOTE_SCRIPT
    assert "u12_preflight_r42_failure_ledger_present" in source
    assert "u12_preflight_state_root_already_exists" in source
    assert 'transaction.get("phase") != "U11_TARGET_INSTALLED_STARTED"' in source


def test_u12_performance_targets_remain_design_targets_not_claimed_measurements():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    targets = manifest["performance_targets"]
    assert targets["user_visible_service_downtime_target_seconds"] == 300
    assert targets["user_visible_service_downtime_hard_limit_seconds"] == 600
    assert targets["no_progress_visibility_limit_seconds"] == 300
    assert targets["ota_total_target_seconds"] == 1800
    assert manifest["normal_ota_baseline_available"] is False
