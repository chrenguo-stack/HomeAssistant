from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "u7_source_activation_r28"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_SOURCE_ACTIVATION_R28_20261114_01"
CONFIRM = "EXECUTE U7 R28 SOURCE ACTIVATION: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r28_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_starts_ungranted_four_file_activation() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["authorization_id"] == GATE
    assert d["confirmation"] == CONFIRM
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    c = d["execution_contract"]
    assert c["read_only_preflight"] is True
    assert c["source_deployment_on_execute"] is True
    assert c["activated_source_file_count"] == 4
    assert c["service_stop"] is False
    assert c["service_restart"] is False
    assert c["transaction_mutation"] is False
    assert c["usb_mutation"] is False
    assert c["u7_transition"] is False
    assert c["u8_plus"] is False
    assert c["automatic_retry"] is False
    assert c["maximum_rollback_attempts"] == 1


def test_manifest_binds_r27_pass_u6_prestate_and_targets() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    a = d["source_authority"]
    assert a["r27_retest03"] == "CLOSED_PASS"
    assert a["r27_retest03_rc"] == 0
    assert a["r27_exact_head"] == "2e9105e6b9e166779a2d898c30b788ca6f42f66f"
    assert a["r27_exact_head_ci"] == "16_OF_16_SUCCESS"
    e = d["expected_live_entry"]
    assert e["transaction_sha256"] == "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
    assert d["predecessor_sha256"]["/opt/HomeAssistant/tools/n3w_t1_core_updater_host.py"] is None
    assert set(d["remote_paths"]) == {"backup", "usb", "install", "host"}
    assert len(d["unchanged_source_sha256"]) == 9
    assert d["package_source_authority"]["tools/n3w_t1_ssh_transport.py"] == "5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7"


def test_executor_and_embedded_remote_compile() -> None:
    m = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<u7-r28>", "exec")
    assert m.GATE_ID == GATE
    assert m.CONFIRMATION == CONFIRM


def test_preflight_requires_exact_u6_r26_and_pre_u7_host_absence() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert '"U6_R26_PREDECESSOR_RECOVERY_PASS"' in remote
    assert '"u7_u6_transaction_invalid"' in remote
    assert '"r26_claim_invalid"' in remote
    assert '"pre_u7_source_not_absent:"' in remote
    assert '"unchanged_u6_source_drift:"' in remote
    assert '"source_activation_eligible":True' in remote


def test_activation_has_no_service_usb_or_transaction_transition() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '["systemctl","stop"' not in remote
    assert '["systemctl","start"' not in remote
    assert '["systemctl","restart"' not in remote
    assert '"service_stop":False' in remote
    assert '"service_restart":False' in remote
    assert '"transaction_mutation":False' in remote
    assert '"usb_mutation":False' in remote
    assert '"u7_transition":False' in remote
    assert '"u8_plus":False' in remote
    assert "transaction_store.write" not in remote
    assert "create_consistent_backup" not in remote


def test_activation_targets_exact_four_u7_sources_and_imports_them() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    for name in (
        "n3w_t1_core_updater_ha_backup.py",
        "n3w_t1_core_updater_ha_usb.py",
        "n3w_t1_core_updater_ha_install.py",
        "n3w_t1_core_updater_host.py",
    ):
        assert name in source
    assert "n3w_t1_core_updater_ha_backup" in remote
    assert "n3w_t1_core_updater_ha_usb" in remote
    assert "n3w_t1_core_updater_ha_install" in remote
    assert "n3w_t1_core_updater_host" in remote
    assert '"activated_source_file_count":0' in remote
    assert '"U7_R28_SOURCE_ACTIVATION_PASS"' in remote


def test_rollback_restores_predecessors_and_removes_previously_absent_host() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    remote = load_executor().REMOTE_SCRIPT
    assert d["predecessor_sha256"][d["remote_paths"]["host"]] is None
    assert 'd.unlink();fsyncdir(d.parent)' in remote
    assert 'install(q,d)' in remote
    assert 'r["post"]=pre(p,False)' in remote



def test_rollback_is_armed_before_first_atomic_replace() -> None:
    remote = load_executor().REMOTE_SCRIPT
    armed = remote.index('result["host_source_mutation"]=True')
    loop = remote.index('for k,dst in p["remote_paths"].items():install(stage/(k+".py"),dst)')
    assert armed < loop
    assert 'result["rollback_required"]=bool(result["host_source_mutation"])' in remote

def test_claim_and_transport_uncertainty_are_consumed_no_replay() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    assert '"authorization_claim_persistence_unknown"' in remote
    assert 'status="STOP_UNKNOWN"' in remote
    assert "authorization_claimed=True" in remote
    assert "authorization_consumed=True" in remote
    assert "replay_permitted=False" in remote
    assert 'result["remote_execute_invoked"]=True' in source
    assert 'reason="remote_execute_claim_state_unknown"' in source


def test_success_is_durable_and_pids_transaction_remain_stable() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'durable(state/"success.json",result)' in remote
    assert '"postclaim_transaction_drift"' in remote
    assert '"unit_pid_drift_before_activation:"' in remote
    assert '"u6_transaction_drift_after_activation"' in remote
    assert '"unit_pid_drift_after_activation:"' in remote


def test_package_reuses_frozen_r25_transport_helpers_only_locally() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "u6_source_activation_r25" in source
    assert "base.load_transport()" in source
    assert "base.prepare_evidence_root" in source
    assert "base.write_remote_evidence" in source


def test_target_binding_workflow_covers_r28() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = "tools/execution_packages/n3w/r7a/u7_source_activation_r28/**"
    executor = "tools/execution_packages/n3w/r7a/u7_source_activation_r28/executor.py"
    test_path = "tests/tools/test_n3w_t1_u7_source_activation_r28.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
