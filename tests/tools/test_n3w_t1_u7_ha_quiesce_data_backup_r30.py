from __future__ import annotations

import ast
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
    / "u7_ha_quiesce_data_backup_r30"
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
    "U7_HA_QUIESCE_DATA_BACKUP_R30_20261115_01"
)
CONFIRM = "EXECUTE U7 R30 HA QUIESCE DATA BACKUP: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r30_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_and_requires_separate_live_authorization() -> None:
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
    assert (
        document["execution_contract"]["separate_single_use_live_grant_required"]
        is True
    )
    assert document["execution_contract"]["automatic_retry"] is False
    assert document["execution_contract"]["u8_plus"] is False
    assert (
        document["execution_contract"]["requires_r30s_prepare_host_activation"]
        is True
    )


def test_manifest_binds_exact_post_r29_u6_state_and_transitive_sources() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = document["expected_live_entry"]
    assert entry["transaction_sha256"] == (
        "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
    )
    assert entry["r29_gate_id"].endswith(
        "U7_SOURCE_ACTIVATION_R29_20261114_01"
    )
    assert document["mount_target"] == (
        "/run/n3w-t1-ota/media/ca89774eb4254d0f"
    )
    assert entry["r30s_gate_id"].endswith(
        "U7_PREPARE_HOST_SOURCE_ACTIVATION_R30S_20261115_01"
    )
    installed = document["installed_source_sha256"]
    assert installed[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py"
    ] == "72cdbc94e9e3e4694ac00ad8fb01f5a2877d8f80a4b07e9c0236b546e43874c2"
    for required in (
        "n3w_t1_core_updater_ha_backup.py",
        "n3w_t1_core_updater_ha_capacity.py",
        "n3w_t1_core_updater_ha_install.py",
        "n3w_t1_core_updater_ha_prepare_host.py",
        "n3w_t1_core_updater_ha_usb_state.py",
        "n3w_t1_core_updater_host.py",
        "n3w_t1_core_updater_v2_common.py",
        "n3w_t1_portable_image_identity.py",
    ):
        assert any(path.endswith(required) for path in installed)
    assert len(installed) >= 15


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r30>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM


def test_readonly_preflight_requires_existing_mount_before_product_resolve() -> None:
    remote = load_executor().REMOTE_SCRIPT
    preflight_start = remote.index("def verify_media_and_backup_inputs")
    preflight_end = remote.index("def verify_prestate", preflight_start)
    block = remote[preflight_start:preflight_end]
    assert block.index("require_existing_rw_mount(plan)") < block.index(
        "backend.resolve_transaction_media"
    )
    assert "write_required=False" in block
    assert '["systemctl", "stop"' not in block
    assert '["mount"' not in block
    assert '["umount"' not in block


def test_preflight_binds_r26_r29_source_runtime_media_and_backup_inputs() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_prestate")
    end = remote.index("def read_terminal_status", start)
    block = remote[start:end]
    for required in (
        "verify_source_hashes(plan)",
        "verify_transaction(plan)",
        "verify_r26(plan)",
        "verify_r29(plan)",
        "verify_r30s(plan)",
        "verify_running_runtime(plan)",
        "verify_media_and_backup_inputs(plan, transaction)",
    ):
        assert required in block
    assert "provider._validate_source_tree()" in remote
    assert "provider._verify_sqlite()" in remote
    assert "provider._root_key()" in remote
    assert 'shutil.which("openssl")' in remote
    assert 'shutil.which("tar")' in remote


def test_live_execute_invokes_existing_u7_product_controller_only_after_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def execute")
    end = remote.index("def main", start)
    block = remote[start:end]
    claim_index = block.index(
        'durable_json_once(state_root / "authorization_claim.json"'
    )
    controller_index = block.index('product["HaUsbU7BackupController"]')
    assert claim_index < controller_index
    assert 'product["ProtectedHaDataBackupProvider"]' in block
    assert 'product["SubprocessPrepareBackend"]' in block
    assert 'product["LocalHost"]' in block
    assert "controller.prepare_or_resume()" in block
    assert "record_recovery_admission" not in block
    assert "claim_live_authorization" not in block


def test_success_stops_in_u7_with_backup_verified_and_broker_preserved() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U7_HA_QUIESCED_DATA_BACKUP_PREPARING"' in remote
    assert 'status="U7_R30_HA_QUIESCE_DATA_BACKUP_PASS"' in remote
    assert "backup_verified=True" in remote
    assert "u8_plus=False" in remote
    assert 'verify_quiesced_runtime(plan, pre["runtime"])' in remote
    assert 'containers["broker"].get("status") != "running"' in remote
    assert 'containers["manager"].get("status") == "running"' in remote
    assert 'containers["homeassistant"].get("status") == "running"' in remote


def test_postclaim_failure_attempts_predecessor_owner_recovery_without_retry() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "runtime.resume_homeassistant_after_backup_failure()" in remote
    assert 'result["recovery_attempted"] = runtime.quiesce_invoked' in remote
    assert 'result["status"] = "STOP_RECOVERED"' in remote
    assert 'result["status"] = "STOP_RECOVERY_FAILED"' in remote
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["execution_contract"]["automatic_retry"] is False
    assert (
        manifest["execution_contract"][
            "postclaim_failure_consumes_authorization"
        ]
        is True
    )


def test_progress_and_terminal_ledgers_are_private_and_durable() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "durable_json_replace(" in remote
    assert '"progress.json"' in remote
    assert '"success.json"' in remote
    assert '"failure.json"' in remote
    assert '"authorization_claim.json"' in remote
    assert "os.fsync(" in remote
    assert "replay_permitted" in remote


def test_timeout_path_reconciles_status_and_never_blindly_reexecutes() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "def reconcile_after_invoke" in source
    assert '"status"' in source
    assert "status_reconciliation_attempted" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_consumed=True" in source
    main_tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(main_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "remote_mode"
    ]
    execute_calls = [
        node
        for node in calls
        if len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "execute"
    ]
    assert len(execute_calls) == 1


def test_product_u9_authorization_fields_remain_untouched() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'post.get("authorization_claimed") is not False' in remote
    assert 'post.get("authorization_consumed") is not False' in remote
    assert 'post.get("authorization_id_sha256") is not None' in remote
    assert "claim_live_authorization" not in remote
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert (
        manifest["execution_contract"]["product_u9_authorization_fields_untouched"]
        is True
    )


def test_target_binding_workflow_covers_r30_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u7_ha_quiesce_data_backup_r30/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "u7_ha_quiesce_data_backup_r30/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u7_ha_quiesce_data_backup_r30.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
