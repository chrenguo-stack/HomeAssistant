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
    / "kf147_removable_media_content_authority_v1_2_source_activation"
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
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_20261112_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_v1_2_source_activation_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_and_exact_eight_file_slice() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert len(document["source_files"]) == 8
    assert len({item["repo_path"] for item in document["source_files"]}) == 8
    contract = document["execution_contract"]
    assert contract["exact_eight_file_source_slice"] is True
    assert contract["source_deployment_on_execute"] is True
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["mount"] is False
    assert contract["umount"] is False
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["automatic_source_rollback"] is True
    assert contract["maximum_rollback_attempts"] == 1


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<v1-2-source-activation>", "exec")
    assert module.GATE_ID == GATE


def test_remote_preflight_uses_content_media_not_old_identity() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "def safe_compatible_media(transaction):" in source
    assert 'fs.stdout.strip() != "ext4"' in source
    assert 'label.stdout.strip() != "N3W-UPDATE"' in source
    assert 'transaction.get("usb_filesystem_uuid")' not in source
    assert (
        'transaction.get("usb_device_identity_public_fingerprint")'
        not in source
    )
    assert '["mount"' not in source
    assert '["umount"' not in source


def test_remote_requires_exact_legacy_u4_and_keeps_it_unmodified() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"U4_READY_TO_INSTALL"' in source
    assert '"target_artifact_identity"' in source
    assert '"predecessor_recovery_identity"' in source
    assert '"ha_data_backup_identity"' in source
    assert '"recovery_content_manifest_sha256"' in source
    assert 'transaction_mutation": False' in source
    assert 'u5_transition": False' in source
    assert '"action": "INSTALL"' not in source
    assert "request_install(" not in source


def test_execute_has_single_claim_source_swap_and_rollback() -> None:
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def execute(plan, authorization, confirmation):")
    body = source[start:]
    assert 'plan.get("live_execution_authorized") is not True' in body
    assert '"granted": True' in body
    assert 'state_root / "authorization_claim.json"' in body
    assert 'result["host_source_mutation"] = True' in body
    assert "atomic_install(" in body
    assert 'result["rollback"] = rollback(plan, backup_dir)' in body
    assert 'run(["systemctl", "stop", SERVICES_UNIT]' in body
    assert 'run(["systemctl", "stop", HOST_UNIT]' in body
    assert 'run(["systemctl", "start", HOST_UNIT]' in body
    assert 'run(["systemctl", "start", SERVICES_UNIT]' in body


def test_local_ungranted_manifest_blocks_execute_before_transport() -> None:
    module = load_executor()
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["live_execution_authorized"] is False
    source = EXECUTOR.read_text(encoding="utf-8")
    manifest = source.index("manifest = read_manifest(")
    transport = source.index("transport_type = load_transport()", manifest)
    assert manifest < transport
    assert "execute=args.execute" in source
    assert 'raise Stop("live_execution_not_authorized")' in source


def test_target_binding_workflow_covers_v1_2_source_activation() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_source_activation/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_source_activation/"
        "executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_kf147_removable_media_content_authority_v1_2_"
        "source_activation.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
