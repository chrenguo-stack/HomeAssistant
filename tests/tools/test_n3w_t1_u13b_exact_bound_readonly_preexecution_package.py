from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_exact_bound_readonly_preexecution"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u13b_p2_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_observed(module, manifest):
    expected = manifest["fresh_binding"]
    return {
        "status": "U13B_REAL_T1_READONLY_BINDING_PASS",
        "read_only": True,
        "fresh_binding": True,
        "expected_terminal_u13a": True,
        "rollback_eligible": False,
        "historical_transaction_phase": expected["phase"],
        "historical_transaction_status": expected["status"],
        "historical_transaction_sha256": expected["transaction_sha256"],
        "historical_usb_phase_sha256": expected["usb_metadata_sha256"]["phase"],
        "historical_u13a_authorization_claimed": True,
        "historical_u13a_authorization_consumed": True,
        "historical_u13a_replay_permitted": False,
        "current_probe_transaction_mutation": False,
        "current_probe_usb_mutation": False,
        "current_probe_service_mutation": False,
        "current_probe_image_mutation": False,
        "current_probe_ha_data_mutation": False,
        "current_probe_authorization_claim": False,
        "current_probe_u13a_transition": False,
        "current_probe_u13b_transition": False,
    }


def test_manifest_is_exact_bound_and_stops_before_live_access():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["read_only_preexecution"] is True
    assert manifest["real_t1_readonly_execution_authorized"] is False
    assert manifest["u13b_live_execution_authorized"] is False
    assert manifest["new_clean_ota_mutation_authorized"] is False
    assert manifest["controlled_rollback_mutation_authorized"] is False
    assert manifest["fresh_binding"]["phase"] == "U13A_COMMITTED"
    assert manifest["fresh_binding"]["status"] == "COMMITTED"
    assert manifest["fresh_binding"]["transaction_sha256"] == (
        "06951ac4d8a8723ae808f25d955560052eee02f884ab78f5c6ffe0580e84b600"
    )
    assert manifest["fresh_binding"]["usb_metadata_sha256"]["phase"] == (
        "11d150bc3828a0e400a90670671a607a02f6d1a53350ef53b3366d95fcb64288"
    )


def test_manifest_binds_u13b_source_and_p1_delegate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = manifest["package_source_authority"]
    required = {
        "tools/n3w_t1_core_updater_ha_u13b.py",
        "tools/n3w_t1_core_updater_ha_u13b_host.py",
        "tools/n3w_t1_core_updater_ha_u13b_postcondition.py",
        "tools/n3w_t1_core_updater_ha_u13b_preexecution.py",
        "tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/executor.py",
        "tools/execution_packages/n3w/r7a/u13b_real_t1_readonly_binding_preflight/manifest.json",
        "tools/n3w_t1_ssh_transport.py",
        "tools/execution_packages/n3w/r7a/u13b_exact_bound_readonly_preexecution/executor.py",
    }
    assert required.issubset(authority)


def test_terminal_u13a_classifies_only_as_safe_stop():
    module = load_executor()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = module.classify_bound_state(manifest["fresh_binding"])
    assert result["status"] == module.SAFE_STOP_STATUS
    assert result["outside_u13b_rollback_domain"] is True
    assert result["expected_safe_stop"] is True
    assert result["rollback_eligible"] is False
    assert result["new_clean_ota_required"] is True
    assert result["read_only"] is True
    assert all(
        result[name] is False
        for name in (
            "current_probe_transaction_mutation",
            "current_probe_usb_mutation",
            "current_probe_service_mutation",
            "current_probe_image_mutation",
            "current_probe_ha_data_mutation",
            "current_probe_authorization_claim",
            "current_probe_u13a_transition",
            "current_probe_u13b_transition",
        )
    )


def test_non_terminal_binding_is_not_reinterpreted():
    module = load_executor()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drifted = dict(manifest["fresh_binding"])
    drifted["phase"] = "U11_TARGET_INSTALLED_STARTED"
    with pytest.raises(module.Stop, match="bound_state_not_terminal_u13a"):
        module.classify_bound_state(drifted)


def test_p1_binding_drift_fails_closed():
    module = load_executor()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    observed = exact_observed(module, manifest)
    module.verify_fresh_binding(observed, manifest["fresh_binding"])
    observed["current_probe_usb_mutation"] = True
    with pytest.raises(module.Stop, match="fresh_p1_binding_drift"):
        module.verify_fresh_binding(observed, manifest["fresh_binding"])


def test_executor_contains_no_u13b_mutating_entrypoint():
    source = EXECUTOR.read_text(encoding="utf-8")
    forbidden = (
        "U13BAutomaticRollbackCoordinator",
        "U13BHostOnlyReconciliationWriter",
        ".rollback(",
        ".reconcile(",
        "sync_transaction_metadata(",
        "record_rollback_",
        "start_rollback(",
        "prepare_new(",
    )
    for token in forbidden:
        assert token not in source
