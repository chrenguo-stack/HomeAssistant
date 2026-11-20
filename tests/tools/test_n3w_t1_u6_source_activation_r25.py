from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u6_source_activation_r25"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
)

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U6_SOURCE_ACTIVATION_R25_20261114_01"
)
CONFIRM = "EXECUTE U6 R25 SOURCE ACTIVATION: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u6_r25_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_granted_two_file_source_activation() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is True
    assert document["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = document["execution_contract"]
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment_on_execute"] is True
    assert contract["activated_source_file_count"] == 2
    assert contract["activated_source_files"] == [
        "tools/n3w_t1_core_updater_ha_prepare_host.py",
        "tools/n3w_t1_core_updater_ha_install.py",
    ]
    assert contract["service_restart"] is False
    assert contract["current_daemon_process_not_reloaded"] is True
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["u6_transition"] is False
    assert contract["u7_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["maximum_rollback_attempts"] == 1


def test_manifest_binds_r24_pass_and_exact_u5_prestate() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    assert authority["u6_source_slice_head"] == (
        "70afdc6a0c9a30c91d047d038eec665bc43d8539"
    )
    assert authority["r24_readonly_head"] == (
        "70f3ddc435508324ea76ad6b71f6c042f4a0ca63"
    )
    assert authority["r24_real_t1_readonly_preflight"] == "CLOSED_PASS"
    assert authority["r24_new_blocker_count"] == 0

    entry = document["expected_live_entry"]
    assert entry["transaction_sha256"] == (
        "adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144"
    )
    assert entry["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py"
    ] == "fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005"
    assert entry["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py"
    ] == "12cb70cdcbebfd7430aef0d5a55a83eaa17e3c3ebd5bed2846fcb047dcac6358"


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u6-r25>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM


def test_preflight_is_readonly_and_requires_install_source_absent() -> None:
    module = load_executor()
    remote = module.REMOTE_SCRIPT
    assert '"install_source_predecessor_not_absent"' in remote
    assert '"source_activation_eligible": True' in remote
    assert '"host_source_mutation": False' in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u6_transition": False' in remote


def test_execute_does_not_restart_services_or_enter_u6() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'run(["systemctl", "stop"' not in remote
    assert 'run(["systemctl", "start"' not in remote
    assert 'run(["systemctl", "restart"' not in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u6_transition": False' in remote
    assert "start_predecessor_recovery(" not in remote
    assert "transaction_store.write" not in remote


def test_activation_is_exactly_prepare_host_plus_new_install_module() -> None:
    module = load_executor()
    remote = module.REMOTE_SCRIPT
    source = EXECUTOR.read_text(encoding="utf-8")

    assert "TARGET_PREPARE_HOST" in source
    assert "TARGET_INSTALL" in source
    assert "target_prepare_host_sha256" in source
    assert "target_install_sha256" in source
    assert 'atomic_install(\n            staged_prepare,' in remote
    assert 'atomic_install(\n            staged_install,' in remote
    assert "n3w_t1_core_updater_ha_prepare_host" in remote
    assert "n3w_t1_core_updater_ha_install" in remote


def test_rollback_restores_prepare_host_and_removes_new_install() -> None:
    remote = load_executor().REMOTE_SCRIPT
    rollback_start = remote.index("def rollback(")
    execute_start = remote.index("def execute(", rollback_start)
    rollback = remote[rollback_start:execute_start]

    assert 'atomic_install(old_prepare, plan["prepare_host_remote_path"])' in rollback
    assert 'install_path = Path(plan["install_remote_path"])' in rollback
    assert "install_path.unlink()" in rollback
    assert "verify_prestate(plan, target_sources=False)" in rollback
    assert "systemctl" not in rollback


def test_claim_persistence_unknown_is_consumed_no_replay() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"authorization_claim_persistence_unknown"' in remote
    assert 'status="STOP_UNKNOWN"' in remote
    assert "authorization_claimed=True" in remote
    assert "authorization_consumed=True" in remote
    assert "replay_permitted=False" in remote


def test_postinvoke_transport_unknown_is_consumed_no_replay() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'result["remote_execute_invoked"] = True' in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert 'reason="remote_execute_claim_state_unknown"' in source


def test_postsuccess_cleanup_failure_does_not_rollback_success() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"STOP_POSTSUCCESS_CLEANUP"' in remote
    assert 'result["rollback_required"] = False' in remote
    assert '"postsuccess_cleanup_failure.json"' in remote


def test_success_requires_u5_transaction_and_same_unit_pids() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"u5_transaction_sha256_drift"' in remote
    assert '"postclaim_transaction_drift"' in remote
    assert '"u5_transaction_drift_after_activation"' in remote
    assert '"host_pid_drift_before_activation"' in remote
    assert '"unit_pid_drift_after_activation:"' in remote
    assert '"U6_R25_SOURCE_ACTIVATION_PASS"' in remote


def test_target_binding_workflow_covers_r25() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u6_source_activation_r25/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u6_source_activation_r25/executor.py"
    )
    test_path = (
        "tests/tools/test_n3w_t1_u6_source_activation_r25.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
