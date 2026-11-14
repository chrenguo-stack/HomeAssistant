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
    / "u6_predecessor_recovery_readonly_preflight_r24"
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
    "U6_PREDECESSOR_RECOVERY_READONLY_PREFLIGHT_R24_20261114_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u6_r24_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_readonly_and_binds_closed_u6_source() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["source_authority"]["u6_source_slice_head"] == (
        "70afdc6a0c9a30c91d047d038eec665bc43d8539"
    )
    assert document["source_authority"]["fresh_ci"] == "16_OF_16_SUCCESS"
    assert document["source_authority"]["final_source_review"] == "PASS"
    assert document["source_authority"]["new_blocker_count"] == 0
    contract = document["execution_contract"]
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment"] is False
    assert contract["remote_staging"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["service_restart"] is False
    assert contract["u6_transition"] is False
    assert contract["u7_plus"] is False
    assert contract["fixed_dev_sdx_authority"] is False
    assert contract["cross_session_physical_usb_identity_authority"] is False
    assert contract["content_authority_required"] is True


def test_manifest_binds_r23_consumed_no_replay_and_exact_u5_entry() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    predecessor = document["predecessor_terminal"]
    assert predecessor["authorization_claimed"] is True
    assert predecessor["authorization_consumed"] is True
    assert predecessor["replay_permitted"] is False
    assert predecessor["transaction_phase"] == "U5_INSTALL_REQUESTED_REVALIDATING"
    entry = document["expected_live_entry"]
    assert entry["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert entry["transaction_sha256"] == (
        "adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144"
    )
    assert entry["current_image_ref"] == (
        "local/n3w-homeassistant:2026.10.0-0c73235a"
    )
    assert entry["current_runtime_image_id"].startswith("sha256:")
    assert entry["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py"
    ] == "12cb70cdcbebfd7430aef0d5a55a83eaa17e3c3ebd5bed2846fcb047dcac6358"


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u6-r24>", "exec")
    assert module.GATE_ID == GATE


def test_remote_preflight_is_strictly_readonly() -> None:
    module = load_executor()
    remote = module.REMOTE_SCRIPT
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "--preflight-only" in source
    assert "--execute" not in source
    assert "scp_to" not in source
    assert "remote_staging" in source
    assert 'run(["mount"' not in remote
    assert 'run(["umount"' not in remote
    assert 'run(["systemctl", "stop"' not in remote
    assert 'run(["systemctl", "start"' not in remote
    assert 'run(["systemctl", "restart"' not in remote
    assert 'run(["docker", "load"' not in remote
    assert 'run(["docker", "image", "rm"' not in remote
    assert '"operation":"install"' not in remote.casefold()
    assert "transaction_store.write" not in remote


def test_preflight_uses_v12_content_authority_not_old_physical_identity() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'filesystem_type.stdout.strip() != "ext4"' in remote
    assert 'filesystem_label.stdout.strip() != "N3W-UPDATE"' in remote
    assert '"physical_identity_used_as_business_authority": False' in remote
    assert "usb_public_fingerprint" not in remote
    assert "expected_uuid" not in remote
    assert "/dev/sda" not in remote
    assert "/dev/sdb" not in remote
    assert 'content.get("target_artifact_identity")' in remote
    assert 'content.get("predecessor_recovery_identity") is not None' in remote
    assert 'raise Stop("unexpected_u6_predecessor_residue")' in remote


def test_preflight_proves_r23_terminal_u5_and_predecessor_runtime() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'claim.get("consumed") is not True' in remote
    assert 'claim.get("replay_permitted") is not False' in remote
    assert 'transaction.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING"' in remote
    assert 'transaction.get("authorization_claimed") is not False' in remote
    assert 'transaction.get("authorization_consumed") is not False' in remote
    assert 'HOMEASSISTANT_CONTAINER = "n3wfc4-homeassistant-1"' in remote
    assert 'exact_ha["runtime_image_id"]' in remote
    assert 'exact_ha["configured_image_ref"]' in remote
    assert '"u6_source_activation_eligible": True' in remote
    assert '"u6_live_transition_eligible": False' in remote


def test_package_source_authority_binds_u6_candidate_modules() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["package_source_authority"]
    assert authority[
        "tools/n3w_t1_core_updater_ha_install.py"
    ] == "c1da3f299d7091d2b49455299e7ad77801fc02dd"
    assert authority[
        "tools/n3w_t1_core_updater_ha_prepare_host.py"
    ] == "59b06d3aa595a6c4801b96d6b992b174a700ca31"
    assert authority[
        "tools/n3w_t1_core_updater_ha_usb.py"
    ] == "dc8218344061d93f524ca7cc786f7aacfa27e1db"
    assert authority[
        "tools/n3w_t1_core_updater_ha_usb_state.py"
    ] == "4bd0c268bb8258d05eadf92d52a322a1d3e51f36"


def test_target_binding_workflow_covers_r24() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u6_predecessor_recovery_readonly_preflight_r24/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u6_predecessor_recovery_readonly_preflight_r24/executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_u6_predecessor_recovery_readonly_preflight_r24.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
