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
    / "u7_repaired_ha_quiesce_data_backup_r32"
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
    "U7_REPAIRED_HA_QUIESCE_DATA_BACKUP_R32_20261115_01"
)
CONFIRM = "EXECUTE U7 R32 REPAIRED HA QUIESCE DATA BACKUP: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r32_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_after_r31_closure() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["stop_boundary"] == (
        "STOP_AFTER_R32_READONLY_PREFLIGHT_"
        "BEFORE_REPAIRED_U7_LIVE_AUTHORIZATION"
    )


def test_manifest_binds_r31_live_pass_and_exact_repaired_sources() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    assert authority["r31_grant_head"] == (
        "1f3921693b4f559d8c85d3b1b41805080e58458e"
    )
    assert authority["r31_result"] == "U7_R31_REPAIR_SOURCE_ACTIVATION_PASS"
    assert authority["r31_authorization_consumed"] is True
    assert authority["r31_replay_permitted"] is False
    assert authority["r31_activated_source_file_count"] == 2
    assert authority["kf158_status"] == "RESOLVED_CLOSED_PASS"

    installed = document["installed_source_sha256"]
    assert installed[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_install.py"
    ] == "726f58d3bae8fa9544bc1d42a72dc8e163fc2f59e61fbc9dca32a1de0ba18b62"
    assert installed[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_host.py"
    ] == "0992f45b4093957382cc6e5864721e34c9479db403a78b95d2194f08ebe1344e"
    assert len(installed) == 15


def test_manifest_keeps_r32_live_ungranted_and_u8_blocked() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = document["execution_contract"]
    assert contract["separate_single_use_live_grant_required"] is True
    assert contract["r31_consumed_no_replay_required"] is True
    assert contract["preflight_service_stop"] is False
    assert contract["preflight_transaction_mutation"] is False
    assert contract["preflight_usb_write"] is False
    assert contract["automatic_retry"] is False
    assert contract["u7_transition_on_success"] is True
    assert contract["u8_plus"] is False
    assert contract[
        "application_owner_quiesced_state_accepts_inactive_or_failed"
    ] is True


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r32>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM
    assert module.PREFLIGHT_TIMEOUT_SECONDS == 1200
    assert module.PREFLIGHT_REMOTE_PROCESS_TIMEOUT_SECONDS == 1170


def test_r30_closure_check_is_scoped_to_r31_verifier() -> None:
    remote = load_executor().REMOTE_SCRIPT
    r29_start = remote.index("def verify_r29(plan):")
    r30s_start = remote.index("def verify_r30s(plan):", r29_start)
    r31_start = remote.index("def verify_r31(plan):", r30s_start)
    import_start = remote.index("def import_product():", r31_start)
    r29_block = remote[r29_start:r30s_start]
    r31_block = remote[r31_start:import_start]
    assert "post_r30" not in r29_block
    assert 'post_r30 = post.get("r30")' in r31_block
    assert 'post_r30.get("claim_consumed_no_replay") is not True' in r31_block
    assert 'post_r30.get("stop_recovered") is not True' in r31_block
    assert 'post_r30.get("transaction_preserved_u6") is not True' in r31_block


def test_r32_preflight_requires_r31_consumed_no_replay() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "def verify_r31(plan):" in remote
    assert 'R31 / "authorization_claim.json"' in remote
    assert 'R31 / "success.json"' in remote
    assert '"U7_R31_REPAIR_SOURCE_ACTIVATION_PASS"' in remote
    assert 'success.get("activated_source_file_count") != 2' in remote
    assert 'success.get("rollback_required") is not False' in remote
    assert 'post_r30.get("claim_consumed_no_replay") is not True' in remote
    assert 'post_r30.get("stop_recovered") is not True' in remote
    assert 'post_r30.get("transaction_preserved_u6") is not True' in remote

    start = remote.index("def verify_prestate")
    end = remote.index("def verify_terminal_u7_state", start)
    block = remote[start:end]
    assert "verify_r31(plan)" in block
    assert '"r31_consumed_no_replay": True' in block


def test_r32_preflight_remains_readonly() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_media_and_backup_inputs")
    end = remote.index("def verify_prestate", start)
    block = remote[start:end]
    assert "require_existing_rw_mount(plan)" in block
    assert "write_required=False" in block
    assert "verify_archive_continuity(" in block
    assert '["systemctl", "stop"' not in block
    assert '["mount"' not in block
    assert '["umount"' not in block


def test_r32_post_u7_owner_verifier_accepts_failed_or_inactive() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_quiesced_runtime")
    end = remote.index("def verify_source_hashes", start)
    block = remote[start:end]
    assert 'not in {"inactive", "failed"}' in block
    assert "services_owner_not_quiesced_post_u7" in block
    assert '!= "inactive"' not in block


def test_r32_execute_still_claims_before_product_controller() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def execute")
    end = remote.index("def main", start)
    block = remote[start:end]
    claim = block.index(
        'durable_json_once(state_root / "authorization_claim.json"'
    )
    controller = block.index('product["HaUsbU7BackupController"]')
    assert claim < controller
    assert "controller.prepare_or_resume()" in block
    assert "record_recovery_admission" not in block
    assert "claim_live_authorization" not in block


def test_r32_success_stops_before_u8_and_preserves_broker() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U7_HA_QUIESCED_DATA_BACKUP_PREPARING"' in remote
    assert 'status="U7_R32_REPAIRED_HA_QUIESCE_DATA_BACKUP_PASS"' in remote
    assert "backup_verified=True" in remote
    assert "u8_plus=False" in remote
    assert 'verify_quiesced_runtime(plan, pre["runtime"])' in remote
    assert 'containers["broker"].get("status") != "running"' in remote


def test_r32_failure_recovery_does_not_retry_u7() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "if runtime.resume_invoked:" in remote
    assert "elif runtime.quiesce_invoked:" in remote
    assert remote.count("runtime.resume_homeassistant_after_backup_failure()") == 1
    assert 'result["status"] = "STOP_RECOVERED"' in remote
    assert 'result["status"] = "STOP_RECOVERY_FAILED"' in remote
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["execution_contract"]["automatic_retry"] is False


def test_workflow_covers_r32_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u7_repaired_ha_quiesce_data_backup_r32/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u7_repaired_ha_quiesce_data_backup_r32/executor.py"
    )
    test_path = (
        "tests/tools/test_n3w_t1_u7_repaired_ha_quiesce_data_backup_r32.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
