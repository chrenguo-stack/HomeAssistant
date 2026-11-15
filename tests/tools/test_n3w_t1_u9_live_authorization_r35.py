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
    / "u9_live_authorization_r35"
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
    "U9_LIVE_AUTHORIZATION_R35_20261115_01"
)
CONFIRM = "EXECUTE U9 R35 LIVE AUTHORIZATION CLAIM: YES"
U8_SHA = "b483236e9439e3e8bc5d6c3cce51bed6649c3feaecdef09cf8fa66a0afab5a3f"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u9_r35_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_explicitly_granted_for_u9_only() -> None:
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
    assert contract["explicit_u9_user_authorization"] is True
    assert contract["transaction_u8_to_u9_only"] is True
    assert contract["u10_plus"] is False
    assert contract["destructive_cutover"] is False
    assert document["stop_boundary"] == (
        "STOP_AFTER_U9_LIVE_AUTHORIZATION_CLAIM_BEFORE_U10_DESTRUCTIVE_CUTOVER"
    )


def test_manifest_binds_exact_u8_closed_pass() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    entry = document["expected_live_entry"]
    assert authority["u8_closure_archive_head"] == (
        "d1d024cba9250bab93344049aadcc69b58b87a32"
    )
    assert authority["r34_execution_head"] == (
        "bc9f955a4dc1945373acc681ba4d4a30e5547460"
    )
    assert authority["r34_result"] == (
        "U8_R34_POST_R33_READONLY_RECONCILIATION_PASS"
    )
    assert authority["u8_status"] == "CLOSED_PASS_RECONCILED"
    assert authority["r33_consumed_no_replay"] is True
    assert entry["transaction_sha256"] == U8_SHA
    assert entry["recovery_content_manifest_sha256"] == (
        "18698bcded28d0497ae3dcd3363ace68f54a3cbc1c42a1fd5710173a24d900f3"
    )
    assert entry["filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"


def test_executor_and_composed_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u9-r35>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM
    assert module.MANIFEST_SCHEMA == (
        "gh.n3w-t1-u9-r35-live-authorization-manifest/1"
    )
    assert module.LOCAL_RESULT_SCHEMA == "gh.n3w-t1-u9-r35-local-result/1"


def test_composed_remote_script_keeps_runtime_dependencies() -> None:
    remote = load_executor().REMOTE_SCRIPT
    tree = ast.parse(remote)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "base64" in imported
    assert "hashlib" in imported
    assert "os" in imported
    assert "time" in imported


def test_execute_revalidates_full_u8_prestate_before_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.rindex("def execute(")
    end = remote.rindex("def main()")
    block = remote[start:end]
    prestate = block.index("pre = verify_prestate_u9(plan)")
    state_root = block.index("state_root.mkdir(mode=0o700)")
    outer_claim = block.index(
        'durable_json_once(state_root / "authorization_claim.json"'
    )
    product_claim = block.index('product["claim_live_authorization"](')
    assert prestate < state_root < outer_claim < product_claim
    assert "verify_media_and_recovery_inputs(plan, transaction)" in remote
    assert "provider.verify_backup(" in remote
    assert "verify_archive_continuity(" in remote
    assert "backend.recovery_admission_capacity(" in remote
    assert "verify_mirror_u8(plan, transaction)" in remote


def test_product_u9_claim_is_durable_before_any_u10_successor() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.rindex("def execute(")
    end = remote.rindex("def main()")
    block = remote[start:end]
    claim = block.index('product["claim_live_authorization"](')
    usb_sync = block.index("backend.sync_transaction_metadata(claimed, media)")
    host_sync = block.index("store.write(claimed)")
    assert claim < usb_sync < host_sync
    assert '"U9_LIVE_AUTHORIZATION_CLAIMED"' in remote
    assert '"u10_plus": False' in block
    assert '"destructive_cutover": False' in block


def test_u9_preclaim_requires_unclaimed_product_authorization() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_transaction_u8")
    end = remote.index("def verify_r33_ledger", start)
    block = remote[start:end]
    assert '"U8_RECOVERY_ADMISSION_COMPLETE"' in block
    assert 'transaction.get("authorization_claimed") is not False' in block
    assert 'transaction.get("authorization_consumed") is not False' in block
    assert 'transaction.get("authorization_id_sha256") is not None' in block
    assert "recovery_content_manifest_sha256" in block
    assert "usb_filesystem_uuid" in block


def test_session_fingerprint_remains_non_authoritative_across_sessions() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_mirror_u8")
    end = remote.index("def verify_prestate_u9", start)
    block = remote[start:end]
    assert "session_public_fingerprint_valid" in block
    assert '"session_public_fingerprint_cross_session_authority": False' in block
    assert "usb_filesystem_uuid" in block
    assert "session_fingerprint ==" not in block


def test_terminal_u9_keeps_runtime_and_images_unchanged() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_terminal_u9_state")
    end = remote.index("def read_terminal_status", start)
    block = remote[start:end]
    assert '"U9_LIVE_AUTHORIZATION_CLAIMED"' in block
    assert 'transaction.get("authorization_claimed") is not True' in block
    assert 'transaction.get("authorization_consumed") is not True' in block
    assert "verify_quiesced_runtime(plan)" in block
    assert "verify_predecessor_internal_image(plan)" in block
    assert "verify_target_internal_image_absent(plan)" in block
    assert '"destructive_cutover_performed": False' in block
    assert '"predecessor_image_delete": False' in block
    assert '"target_image_load": False' in block


def test_execute_contains_no_u10_cutover_or_service_mutation() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.rindex("def execute(")
    end = remote.rindex("def main()")
    block = remote[start:end]
    forbidden = [
        "docker image rm",
        "docker load",
        '["systemctl", "start"',
        '["systemctl", "stop"',
        '["systemctl", "restart"',
    ]
    for token in forbidden:
        assert token not in block
    assert '"u10_plus": False' in block
    assert '"destructive_cutover": False' in block
    assert '"service_mutation": False' in block


def test_postclaim_path_is_no_replay() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert remote.count('product["claim_live_authorization"](') == 1
    assert '"STOP_POSTCLAIM"' in remote
    assert '"STOP_POSTSUCCESS_LOCAL"' in remote
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["execution_contract"]["automatic_retry"] is False
    assert (
        document["execution_contract"]["postclaim_failure_consumes_authorization"]
        is True
    )


def test_workflow_covers_r35_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u9_live_authorization_r35/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/u9_live_authorization_r35/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u9_live_authorization_r35.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
