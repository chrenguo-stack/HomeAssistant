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
    / "u13a_commit_readonly_preflight"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "u13a_readonly_executor",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_u13a_manifest_is_readonly_and_stops_before_terminal_mutation():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["read_only_preflight"] is True
    assert manifest["real_t1_readonly_execution_authorized"] is True
    assert manifest["u13a_live_execution_authorized"] is False
    assert manifest["u13b_live_execution_authorized"] is False
    assert manifest["expected_u12_entry"]["transaction_sha256"] == (
        "32a92edcd9fbdad1356b874a55d40f6e919518363c5740b495f9b5fa08a56071"
    )
    assert manifest["expected_u12_entry"]["mirror_sha256"]["phase"] == (
        "ca5cbcaa0d915f9a0fe590d2beeeace846ce7029bdf6dcb8b46331d205212283"
    )
    contract = manifest["execution_contract"]
    assert contract["exact_recovery_assets_reverified_before_commit"] is True
    assert contract["forward_commit_classification_required"] is True
    assert contract["rollback_not_selected_on_healthy_u12"] is True
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["service_mutation"] is False
    assert contract["image_mutation"] is False
    assert manifest["stop_boundary"] == (
        "STOP_AFTER_U13A_READONLY_PREFLIGHT_BEFORE_ANY_U13_TERMINAL_MUTATION"
    )


def test_u13a_remote_payload_compiles():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<u13a-readonly-remote>", "exec")


def test_u13a_requires_exact_durable_u12_and_live_ledger():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert 'transaction.get("phase") != "U12_TARGET_ACCEPTANCE"' in source
    assert 'success.get("status") != "U12_LIVE_ACCEPTANCE_PASS"' in source
    assert 'success.get("u12_acceptance") is not True' in source
    assert 'success.get("u13_plus") is not False' in source
    assert "u13a_preflight_u12_failure_ledger_present" in source
    assert 'claim.get("replay_permitted") is not False' in source


def test_u13a_reverifies_exact_recovery_assets_before_commit_eligibility():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    recovery = source.index("recovery = verify_recovery_assets(")
    classify = source.index(
        'classification = product["classify_power_loss_reentry"]('
    )
    assert recovery < classify
    assert "verify_recovery_assets_and_capacity(" in source
    assert "exact_recovery_content_verified=True" in source
    assert '"FORWARD_COMMIT_ELIGIBLE"' in source


def test_u13a_healthy_u12_selects_forward_commit_not_rollback():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert '"forward_commit_eligible": True' in source
    assert '"rollback_required": False' in source
    assert '"u13a_live_execution_authorized": False' in source
    assert '"u13a_transition": False' in source
    assert '"u13b_transition": False' in source


def test_u13a_readonly_path_has_no_mutation_operations():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    start = source.index("def run_u13a_readonly(plan):")
    end = source.index("\ndef main():", start)
    readonly = source[start:end]
    forbidden = (
        "record_commit(",
        "record_rollback_complete(",
        "store.write(",
        "sync_transaction_metadata(",
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
        assert token not in readonly


def test_u13a_rechecks_runtime_mqtt_and_http_after_recovery_assets():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    recovery = source.index("recovery = verify_recovery_assets(")
    runtime = source.index("runtime = verify_runtime_u11(plan)")
    readiness = source.index("readiness = observe_acceptance_readiness(plan)")
    assert recovery < runtime < readiness


def test_u13a_does_not_claim_end_to_end_ota_baseline():
    executor = load_executor()
    source = executor.REMOTE_SCRIPT
    assert '"normal_ota_baseline_available": False' in source
    assert '"preflight_total_ms"' in source
    assert '"recovery_assets_verification_ms"' in source


def test_u13a_local_manifest_binds_exact_package_sources():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "package_source_authority" in source
    assert "git_text(\"rev-parse\", \"HEAD:\" + relative)" in source
    assert "package_source_authority_drift:" in source
