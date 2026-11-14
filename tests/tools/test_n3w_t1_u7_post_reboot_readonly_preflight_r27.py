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
    / "u7_post_reboot_readonly_preflight_r27"
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
    "U7_POST_REBOOT_READONLY_PREFLIGHT_R27_20261114_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r27_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_strictly_readonly_and_ungranted() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = document["execution_contract"]
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment"] is False
    assert contract["service_stop"] is False
    assert contract["service_restart"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_data_mutation"] is False
    assert contract["readonly_no_journal_replay_mount_allowed"] is True
    assert contract["readonly_mount_restored"] is True
    assert contract["u7_transition"] is False
    assert contract["u8_plus"] is False
    assert contract["merge"] is False


def test_manifest_binds_closed_u7_review_and_r26_u6_entry() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = document["source_authority"]
    assert source["prior_source_head"] == (
        "d973136d05054ce6a547b4e1b43b596f8eb46d60"
    )
    assert source["u7_critical_node_review"] == "PASS"
    assert source["u7_critical_node_fresh_ci"] == "16_OF_16_SUCCESS"
    assert source["u7_new_source_blocker_count"] == 0
    assert source["r26_result"] == "U6_R26_PREDECESSOR_RECOVERY_PASS"
    assert source["r26_replay_permitted"] is False
    assert document["transaction_sha256"] == (
        "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
    )
    predecessor = document["predecessor_identity"]
    assert predecessor["archive_sha256"] == (
        "34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d"
    )
    assert predecessor["archive_size_bytes"] == 743074537
    assert predecessor["portable_identity_sha256"] == (
        "8b4d4376e2ab339347abb4aa554d3a5cc6f93ea20b0ee3c22ca8e29ae14b16c3"
    )


def test_local_wrapper_uses_strict_existing_ssh_transport_contract() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "--t1-ssh-target" in source
    assert "--known-hosts" in source
    assert "--expected-host-key-sha256" in source
    assert "transport.start_epoch()" in source
    assert "transport.close_epoch()" in source
    assert "target=args.t1_ssh_target" in source
    assert "expected_host_key_sha256=args.expected_host_key_sha256" in source
    assert "base64.b64encode(" in source
    remote = load_executor().REMOTE_SCRIPT
    assert "base64.b64decode(sys.argv[1])" in remote


def test_executor_and_embedded_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r27>", "exec")
    assert module.GATE_ID == GATE


def test_remote_preflight_has_no_live_u7_mutation_path() -> None:
    remote = load_executor().REMOTE_SCRIPT
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "--preflight-only" in source
    assert "--execute" not in source
    assert '["systemctl", "stop"' not in remote
    assert '["systemctl", "start"' not in remote
    assert '["systemctl", "restart"' not in remote
    assert '["docker", "load"' not in remote
    assert '["docker", "image", "rm"' not in remote
    assert "transaction_store.write" not in remote
    assert "HaUsbU7BackupController" not in remote
    assert "create_consistent_backup" not in remote
    assert "record_ha_data_backup_verified" not in remote


def test_readonly_mount_is_noload_and_restored() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"ro,noload,nodev,nosuid,noexec"' in remote
    assert '{"noload", "norecovery"}.intersection(options)' in remote
    assert 'run(["umount", str(temp_path)]' in remote
    assert '"readonly_mount_attempted": mounted_by_us' in remote
    assert '"physical_identity_used_as_business_authority": False' in remote
    assert "/dev/sda" not in remote
    assert "/dev/sdb" not in remote
    assert "expected_uuid" not in remote
    assert "usb_public_fingerprint" not in remote


def test_post_reboot_restart_counts_are_not_historical_equality_gates() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'observed["restart_count"] != 0' not in remote
    assert 'observed.get("NRestarts") != "0"' not in remote
    assert 'observed["restart_count"] < 0' in remote
    assert 'str(observed.get("NRestarts", "")).isdigit()' in remote


def test_r27_requires_r26_success_to_predate_current_boot() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"post_reboot_epoch_not_proven"' in remote
    assert '"success_predates_current_boot": True' in remote


def test_u6_transaction_and_recovery_content_are_exactly_revalidated() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert 'transaction.get("ha_data_backup_verified") is not False' in remote
    assert 'transaction.get("authorization_claimed") is not False' in remote
    assert 'transaction.get("authorization_consumed") is not False' in remote
    assert 'content.get("predecessor_recovery_identity")' in remote
    assert 'content.get("ha_data_backup_identity") is not None' in remote
    assert '"u7_recovery_asset_drift"' in remote
    assert '"u7_backup_residue_present"' in remote


def test_preflight_checks_u7_backup_runtime_dependencies_without_reading_key() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "/var/lib/n3wfc4-homeassistant" in remote
    assert "/var/lib/greenhouse-manager/identity/system-root.key" in remote
    assert 'meta.st_size != 32' in remote
    assert 'stat.S_IMODE(meta.st_mode) != 0o600' in remote
    assert '"key_bytes_read": False' in remote
    assert "PRAGMA quick_check" not in remote
    assert "sqlite3.connect" not in remote
    assert "DEFERRED_UNTIL_QUIESCE" in remote
    assert "EXTERNAL_DB_RE" in remote
    assert '"openssl", "enc", "-help"' in remote
    assert '"openssl", "enc", "-list"' in remote
    assert '"aes-256-ctr" not in cipher_list' in remote
    assert '"--utc"' in remote
    assert '"tar", "--version"' in remote
    key_function = remote.split("def verify_root_key_metadata():", 1)[1].split(
        "def tool_capabilities():", 1
    )[0]
    assert "read_bytes" not in key_function


def test_capacity_is_revalidated_for_remaining_u7_work() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "capacity.compute_capacity(" in remote
    assert "breakdown.ha_data_backup_budget_bytes" in remote
    assert "breakdown.transaction_working_budget_bytes" in remote
    assert "breakdown.removable_reserve_bytes" in remote
    assert '"u7_current_usb_capacity_insufficient"' in remote


def test_source_activation_is_separate_from_live_u7_execution() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"u7_source_activation_required": True' in remote
    assert '"u7_source_activation_eligible": True' in remote
    assert '"u7_live_execution_eligible": False' in remote
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["package_source_authority"]
    assert authority["tools/n3w_t1_core_updater_ha_install.py"]
    assert authority["tools/n3w_t1_core_updater_ha_backup.py"]
    assert authority["tools/n3w_t1_core_updater_ha_usb.py"]
    assert authority["tools/n3w_t1_core_updater_host.py"]
    assert document["installed_host_git_blob_sha1"] == (
        "ee7ec0da27823a7b25408d90d61d03d25d5f1297"
    )
    assert 'git_blob_sha(host_path)' in remote


def test_target_binding_workflow_covers_r27() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u7_post_reboot_readonly_preflight_r27/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u7_post_reboot_readonly_preflight_r27/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u7_post_reboot_readonly_preflight_r27.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
