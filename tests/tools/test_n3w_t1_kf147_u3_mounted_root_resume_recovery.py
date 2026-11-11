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
    / "kf147_u3_mounted_root_resume_recovery"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U3_MOUNTED_ROOT_RESUME_TO_U4_R6_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u3_mounted_root_resume_recovery_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_new_fail_closed_r6_authority() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == (
        "gh.n3w-t1-kf147-u3-mounted-root-resume-recovery-manifest/1"
    )
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["confirmation"] == (
        "EXECUTE KF147 U3 MOUNTED ROOT RESUME TO U4 R6: YES"
    )
    assert doc["live_execution_authorized"] is True
    assert doc["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert doc["state_root"].endswith(
        "kf147-u3-mounted-root-resume-r6-20261111-01"
    )


def test_manifest_binds_exact_one_file_source_transition() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    predecessor = doc["predecessor_source_authority"]
    assert predecessor["source_head"] == (
        "675871a0567aca858c8af34f9eecf0a2e79ba063"
    )
    assert predecessor["prepare_host_blob"] == (
        "933dfb2a348ace88b0a54bf4adbd8851c1348be0"
    )
    assert predecessor["prepare_host_sha256"] == (
        "469a4de0a41ac8a3c513f29a2ef6566eecfe927b7cdc26ec169f664221fa52a4"
    )
    assert doc["target_prepare_host_sha256"] == (
        "a11089ef57cf68c40a648c85ac7e7569a281f7fad13f75a09c0a3b04bad80ecf"
    )
    assert doc["remote_target"] == (
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py"
    )
    contract = doc["execution_contract"]
    assert contract["exact_one_file_host_source_repair"] is True
    assert contract["predecessor_r5_consumed_failure_required"] is True
    assert contract["service_restart"] == "n3w-t1-ha-ota.service"


def test_predecessor_is_last_accepted_physical_source_deployment() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    predecessor = doc["predecessor_source_authority"]
    assert predecessor["source_head"] == (
        "675871a0567aca858c8af34f9eecf0a2e79ba063"
    )
    assert predecessor["source_head"] != (
        "ff17360ae74083190613f674c24506d35759c922"
    )
    assert predecessor["prepare_host_blob"] != (
        "fc5577b9aecc405a24fe1933a3597bc2f80f0e20"
    )


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u3-mounted-root-resume-r6>", "exec")
    assert module.GATE_ID == GATE


def test_preflight_requires_consumed_terminal_r5() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "R5_ROOT" in source
    assert 'R5_ROOT / "authorization_claim.json"' in source
    assert 'R5_ROOT / "permission_repair.json"' in source
    assert 'R5_ROOT / "failure.json"' in source
    assert 'failure.get("first_failed_operation") != "Stop:u3_permission_recovery_timeout"' in source
    assert "r5_terminal_failure_not_confirmed" in source


def test_preflight_binds_exact_live_mounted_root_failure_state() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'mount_root["mode"] != 0o755' in source
    assert 'update_dir["mode"] != 0o700' in source
    assert 'transaction_dir["mode"] != 0o700' in source
    assert "usb_target_directory_unexpectedly_present" in source
    assert 'ipc.get("phase") != "ERROR"' in source
    assert 'ipc.get("error_code") != "usb_runtime_directory_metadata_invalid"' in source
    assert 'sha_file(plan["remote_target"])' in source
    assert "installed_prepare_host_source_drift" in source


def test_only_exact_host_source_is_staged_and_installed() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    assert source.count("transport.scp_to(") == 1
    assert 'remote_source = remote_root + "/n3w_t1_core_updater_ha_prepare_host.py"' in source
    assert 'atomic_install(staged, plan["remote_target"])' in remote
    assert 'run(["systemctl", "restart", SERVICE]' in remote
    forbidden = (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"CONFIRM_USB_ERASE"',
        'run(["umount"',
        'run(["mount"',
        "os.fchmod(descriptor, 0o700)",
    )
    for token in forbidden:
        assert token not in remote


def test_authorization_claim_precedes_source_install_and_restart() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = source.index('state_root / "authorization_claim.json"')
    postclaim = source.index("postclaim = validate_preflight(plan)")
    install = source.index('atomic_install(staged, plan["remote_target"])')
    restart = source.index('run(["systemctl", "restart", SERVICE]', install)
    activation = source.index('result["source_activated"] = True')
    assert claim < postclaim < install < restart < activation


def test_pre_activation_failure_rolls_back_but_postactivation_failure_does_not() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "def rollback_pre_activation(plan, backup):" in source
    assert 'if not result["source_activated"]:' in source
    assert 'result["rollback"] = rollback_pre_activation(plan, backup)' in source
    assert 'raise Stop("u3_mounted_root_resume_timeout")' in source


def test_success_requires_exact_u4_archive_and_container_continuity() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'tx.get("phase") != U4' in source
    assert 'tx.get("target_artifact_verified") is not True' in source
    assert 'target.stat().st_size != live["target_archive_size_bytes"]' in source
    assert 'sha_file(target) != live["target_archive_sha256"]' in source
    assert 'raise Stop("u4_mount_binding_invalid")' in source
    assert 'raise Stop("u4_prepare_host_source_drift")' in source
    assert '"post_recovery_container_drift:" + key' in source
    assert '"u5_plus": False' in source


def test_postactivation_runtime_error_stops_without_waiting_for_timeout() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'ipc = ipc_status(pre["containers"]["manager"]["container_id"])' in source
    assert 'if ipc.get("phase") == "ERROR":' in source
    assert 'raise Stop("u3_resume_error:" + str(ipc.get("error_code")))' in source


def test_product_fix_preserves_private_pre_mount_check_only_for_unmounted_path() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_core_updater_ha_prepare_host.py"
    ).read_text(encoding="utf-8")
    find_mount = source.index('"--source",\n                partition,')
    unmounted = source.index("if raw_target is None:", find_mount)
    private_check = source.index(
        "_require_private_directory(mount_path, create=True)",
        unmounted,
    )
    mount_call = source.index('"nodev,nosuid,noexec",', private_check)
    bound_check = source.index("self._require_bound_media(media)", mount_call)
    assert find_mount < unmounted < private_check < mount_call < bound_check


def test_execution_contract_forbids_destructive_or_u5_plus_scope() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = doc["execution_contract"]
    assert contract["usb_wipe"] is False
    assert contract["usb_partition"] is False
    assert contract["usb_format"] is False
    assert contract["usb_permission_mutation"] is False
    assert contract["usb_target_write"] is True
    assert contract["destructive_confirmation_replay"] is False
    assert contract["homeassistant_runtime_mutation"] is False
    assert contract["manager_runtime_mutation"] is False
    assert contract["broker_runtime_mutation"] is False
    assert contract["u5_plus"] is False
    assert contract["board_access"] is False
    assert contract["merge"] is False


def test_target_binding_workflow_runs_r6_compile_and_regression() -> None:
    workflow = (
        ROOT
        / ".github"
        / "workflows"
        / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
    ).read_text(encoding="utf-8")
    package_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u3_mounted_root_resume_recovery/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u3_mounted_root_resume_recovery.py"
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u3_mounted_root_resume_recovery/**"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(package_path) == 1
    assert workflow.count(test_path) == 2
