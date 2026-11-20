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
    / "u11_target_install_r40"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u11_r40_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_r40_manifest_is_explicitly_granted_and_one_shot():
    value = manifest()
    assert value["live_execution_authorized"] is True
    assert value["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert value["execution_contract"][
        "explicit_r40_user_authorization_required"
    ] is True
    assert value["execution_contract"][
        "explicit_r40_user_authorization_granted"
    ] is True
    assert value["source_authority"]["r40_pre_authorization_source_head"] == (
        "a187e70f4c3aef4657be3d47983a404d61ea07e3"
    )
    assert value["source_authority"]["r40_pre_authorization_ci"] == (
        "16_OF_16_SUCCESS"
    )
    assert value["source_authority"]["r40_pre_authorization_review"] == "PASS"
    assert value["next_boundary"] == "EXECUTE_REAL_T1_U11_TARGET_INSTALL_ONCE"
    assert value["stop_boundary"] == (
        "STOP_AFTER_REAL_T1_U11_BEFORE_U12_TARGET_ACCEPTANCE"
    )


def test_r40_manifest_binds_r39_physical_pass_and_exact_u10():
    value = manifest()
    authority = value["source_authority"]
    entry = value["expected_u10_entry"]
    assert authority["r39_source_ci"] == "16_OF_16_SUCCESS"
    assert authority["r39_result"] == "U11_R39_READONLY_PREFLIGHT_PASS"
    assert authority["r39_rc"] == 0
    assert authority["r39_execution_id"] == (
        "u11-r39-readonly-20261116T042337Z"
    )
    assert entry["transaction_sha256"] == (
        "c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3"
    )
    assert entry["target_image"] == (
        "local/n3w-homeassistant:2026.10.4-5881590f"
    )


def test_r40_manifest_binds_exact_controller_adapter_and_executor():
    value = manifest()
    bound = value["package_source_authority"]
    assert bound["tools/n3w_t1_core_updater_ha_u11.py"] == (
        "33bd5e486db17b2476674009a6c23eecf750c12a"
    )
    assert bound["tools/n3w_t1_core_updater_ha_u11_host.py"] == (
        "1ec5adaf63fe9ae5024be05922536cfe4f2168ba"
    )
    assert bound[
        "tools/execution_packages/n3w/r7a/u11_target_install_r40/executor.py"
    ] == "f3b42958bbffeeb1b49afc2ad6be9ad8e59c4425"
    assert value["exact_source_delivery"] == (
        "TEMPORARY_PACKAGE_BOUND_MODULES_NO_LIVE_SOURCE_MUTATION"
    )


def test_r40_remote_script_compiles():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r40-remote>", "exec")


def test_r40_embedded_r39_preclaim_precedes_claim():
    source = load_executor().REMOTE_SCRIPT
    preclaim = source.index("pre = run_readonly(r39_plan)")
    state_root = source.index("state_root.mkdir(mode=0o700)")
    claim_write = source.index(
        'durable_json_once(state_root / "authorization_claim.json", claim)'
    )
    controller_install = source.index("installed = controller.install()")
    assert preclaim < state_root < claim_write < controller_install


def test_r40_local_authorization_gate_precedes_transport_creation():
    source = EXECUTOR.read_text(encoding="utf-8")
    gate = source.index(
        'if manifest["live_execution_authorized"] is not True:'
    )
    transport = source.index("transport_type = base.load_transport()")
    assert gate < transport
    assert "r40_live_execution_not_authorized" in source


def test_r40_success_persists_usb_before_host_and_stops_before_u12():
    controller = (
        ROOT / "tools" / "n3w_t1_core_updater_ha_u11.py"
    ).read_text(encoding="utf-8")
    usb = controller.index('mutation_stage = "usb_u11_persist"')
    host = controller.index('mutation_stage = "host_u11_persist"')
    assert usb < host

    remote = load_executor().REMOTE_SCRIPT
    assert "record_target_accepted(" not in remote
    assert "U12_TARGET_ACCEPTANCE" not in remote
    assert '"u12_plus": False' in remote
    assert '"u12_acceptance": False' in remote


def test_r40_success_ledger_is_last_fallible_success_write():
    source = load_executor().REMOTE_SCRIPT
    progress = source.index('progress("executor_success")')
    success = source.index(
        'durable_json_once(state_root / "success.json", result)'
    )
    assert progress < success


def test_r40_postclaim_failure_is_no_replay_and_conservatively_observed():
    source = load_executor().REMOTE_SCRIPT
    assert 'result["status"] = "STOP_POSTCLAIM"' in source
    assert 'result["recovery_required"] = True' in source
    assert 'result["replay_permitted"] = False' in source
    assert 'result["target_image_load"] = True' in source
    assert 'result["compose_binding_mutation"] = True' in source
    assert 'result["service_mutation"] = True' in source
    assert 'result["usb_mutation"] = True' in source
    assert 'observed_phase == "U11_TARGET_INSTALLED_STARTED"' in source


def test_r40_transport_ambiguity_reconciles_without_replay():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "reconcile_after_invoke(" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert "recovery_required=True" in source


def test_r40_contract_requires_production_owner_and_config_mount():
    contract = manifest()["execution_contract"]
    assert contract["production_owner_start_required"] is True
    assert contract["exact_manager_peer_identity_required"] is True
    assert contract["exact_broker_peer_identity_required"] is True
    assert contract["production_config_mount_required"] is True
    assert contract["usb_u11_metadata_before_host_transaction"] is True
    assert contract["u12_acceptance_forbidden"] is True
    assert contract["partial_failure_requires_recovery"] is True
    assert contract["postclaim_replay_forbidden"] is True
