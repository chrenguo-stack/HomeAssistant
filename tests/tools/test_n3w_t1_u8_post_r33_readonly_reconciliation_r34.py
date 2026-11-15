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
    / "u8_post_r33_readonly_reconciliation_r34"
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
    "U8_POST_R33_READONLY_RECONCILIATION_R34_20261115_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u8_r34_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_strictly_read_only() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["read_only"] is True
    assert document["live_execution_authorized"] is False
    assert document["stop_boundary"] == (
        "STOP_AFTER_R34_READONLY_U8_RECONCILIATION_BEFORE_U9"
    )
    contract = document["reconciliation_contract"]
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["service_mutation"] is False
    assert contract["u9_plus"] is False
    assert contract["destructive_cutover"] is False


def test_manifest_binds_exact_r33_failure_and_diag() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    entry = document["expected_live_entry"]
    assert authority["r33_execution_head"] == (
        "d0f7a9813e9f15343df6ab0ed4a84c00adb87214"
    )
    assert authority["r33_execution_id"] == "r33-live01-20261115T144821Z"
    assert authority["r33_result"] == "STOP_POSTCLAIM"
    assert authority["r33_authorization_claimed"] is True
    assert authority["r33_authorization_consumed"] is True
    assert authority["r33_replay_permitted"] is False
    assert authority["readonly_diag_unique_mismatch"] == (
        "manifest.public_fingerprint"
    )
    assert entry["transaction_sha256"] == (
        "b483236e9439e3e8bc5d6c3cce51bed6649c3feaecdef09cf8fa66a0afab5a3f"
    )
    assert entry["recovery_content_manifest_sha256"] == (
        "18698bcded28d0497ae3dcd3363ace68f54a3cbc1c42a1fd5710173a24d900f3"
    )


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u8-r34>", "exec")
    assert module.GATE_ID == GATE
    assert module.MANIFEST_SCHEMA == (
        "gh.n3w-t1-u8-r34-readonly-reconciliation-manifest/1"
    )
    assert module.LOCAL_RESULT_SCHEMA == (
        "gh.n3w-t1-u8-r34-local-result/1"
    )


def test_remote_reconciliation_contains_no_mutation_calls() -> None:
    remote = load_executor().REMOTE_SCRIPT
    forbidden = [
        "sync_transaction_metadata(",
        "store.write(",
        "record_recovery_admission(",
        "claim_live_authorization(",
        "docker image rm",
        "docker load",
        '["systemctl", "start"',
        '["systemctl", "stop"',
        "unlink(",
        "os.replace(",
        "write_text(",
        "write_bytes(",
    ]
    for token in forbidden:
        assert token not in remote


def test_session_fingerprint_is_not_cross_session_authority() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_mirror")
    end = remote.index("def main()", start)
    block = remote[start:end]
    assert "session_public_fingerprint_valid" in block
    assert "session_public_fingerprint_differs_from_transaction" in block
    assert '"session_public_fingerprint_cross_session_authority": False' in block
    assert '"filesystem_uuid_cross_session_authority": True' in block
    assert 'manifest.get("usb_filesystem_uuid")' in block
    assert "session_fingerprint != transaction_fingerprint" in block
    assert (
        "session_fingerprint == transaction_fingerprint"
        not in block
    )


def test_durable_mirror_fields_remain_exact() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_mirror")
    end = remote.index("def main()", start)
    block = remote[start:end]
    for key in (
        "manifest.transaction_id",
        "manifest.filesystem_uuid",
        "phase.transaction_id",
        "phase.phase",
        "phase.target_verified",
        "phase.capacity_verified",
        "authority.transaction_id",
        "authority.target_identity",
        "authority.predecessor_identity",
        "authority.backup_identity",
        "authority.recovery_manifest",
        "checksums.target_sha256",
        "checksums.target_size",
    ):
        assert key in block
    assert "r34_durable_usb_mirror_mismatch" in block


def test_r33_consumed_no_replay_is_required() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_r33_ledger")
    end = remote.index("def verify_transaction", start)
    block = remote[start:end]
    assert '"STOP_POSTCLAIM"' in block
    assert '"Stop:r33_terminal_usb_mirror_mismatch"' in block
    assert 'claim.get("claimed") is not True' in block
    assert 'claim.get("consumed") is not True' in block
    assert 'claim.get("replay_permitted") is not False' in block
    assert 'failure.get("u8_transition") is not True' in block
    assert 'failure.get("u9_plus") is not False' in block


def test_u8_transaction_and_recovery_manifest_are_revalidated() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_transaction")
    end = remote.index("def verify_mirror", start)
    block = remote[start:end]
    assert '"U8_RECOVERY_ADMISSION_COMPLETE"' in block
    assert 'transaction.get("authorization_claimed") is not False' in block
    assert 'transaction.get("authorization_consumed") is not False' in block
    assert 'transaction.get("authorization_id_sha256") is not None' in block
    assert "compute_manifest(transaction)" in block
    assert "r34_recovery_manifest_recompute_mismatch" in block


def test_runtime_and_image_boundaries_are_preserved() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "verify_runtime(plan)" in remote
    assert "verify_images(plan)" in remote
    assert "broker_not_running" in remote
    assert "manager_not_quiesced" in remote
    assert "homeassistant_not_quiesced" in remote
    assert "predecessor_internal_image_missing" in remote
    assert "target_internal_image_unexpectedly_present" in remote


def test_success_only_closes_u8_readonly_reconciliation() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U8_R34_POST_R33_READONLY_RECONCILIATION_PASS"' in remote
    assert '"r33_false_stop_confirmed": True' in remote
    assert '"u8_durable": True' in remote
    assert '"product_u9_authorization_claimed": False' in remote
    assert '"product_u9_authorization_consumed": False' in remote
    assert '"destructive_cutover": False' in remote
    assert '"u9_plus": False' in remote


def test_workflow_covers_r34_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u8_post_r33_readonly_reconciliation_r34/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u8_post_r33_readonly_reconciliation_r34/executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_u8_post_r33_readonly_reconciliation_r34.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
