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
    / "u7_prepare_host_source_activation_r30s"
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
    "U7_PREPARE_HOST_SOURCE_ACTIVATION_R30S_20261115_01"
)
CONFIRM = "EXECUTE U7 R30S PREPARE HOST SOURCE ACTIVATION: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r30s_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_single_file_source_activation() -> None:
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
    contract = document["execution_contract"]
    assert contract["activated_source_file_count"] == 1
    assert contract["service_stop"] is False
    assert contract["service_restart"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["u7_transition"] is False
    assert contract["u8_plus"] is False
    assert contract["automatic_retry"] is False


def test_manifest_binds_exact_prepare_host_predecessor_and_target() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["predecessor_sha256"] == (
        "0d0c96d7ae2f26c2d2ae8388e6ee75ad0616081a6cdcb98727f2131dab31c30e"
    )
    assert document["target_sha256"] == (
        "72cdbc94e9e3e4694ac00ad8fb01f5a2877d8f80a4b07e9c0236b546e43874c2"
    )
    authority = document["source_authority"]
    assert authority["predecessor_prepare_host_blob"] == (
        "59b06d3aa595a6c4801b96d6b992b174a700ca31"
    )
    assert authority["target_prepare_host_blob"] == (
        "9e3dd9180d88e354f81480458220f1c092b30aa8"
    )
    assert authority["blocker"] == (
        "INSTALLED_PREPARE_HOST_LACKS_BACKUP_CAPACITY_REVALIDATION"
    )


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r30s>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM


def test_preflight_requires_old_source_and_missing_u7_method() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_prestate")
    end = remote.index("def rollback", start)
    block = remote[start:end]
    assert "verify_transaction(plan)" in block
    assert "verify_r26(plan)" in block
    assert "verify_r29(plan)" in block
    assert "verify_sources(plan, target=False)" in block
    assert 'installed_capability("NO")' in block
    assert "verify_runtime(plan)" in block
    assert "atomic_install(" not in block
    assert '["systemctl", "stop"' not in block


def test_staged_target_import_is_verified_before_authorization_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def execute")
    end = remote.index("def main", start)
    block = remote[start:end]
    staged = block.index("staged_import_preflight(plan)")
    claim = block.index('state_root / "authorization_claim.json"')
    install = block.index("atomic_install(stage_root / TARGET.name, TARGET)")
    assert staged < claim < install
    assert "'backup_capacity_revalidation'" in remote


def test_success_mutates_only_prepare_host_and_preserves_u6_runtime() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'status="U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS"' in remote
    assert "activated_source_file_count=1" in remote
    assert 'if sha_file(TX) != plan["transaction_sha256"]' in remote
    assert "verify_runtime(plan)" in remote
    assert '"service_stop": False' in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u7_transition": False' in remote
    assert '"u8_plus": False' in remote


def test_postclaim_failure_has_bounded_single_file_rollback() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "def rollback(plan, backup_path)" in remote
    assert "atomic_install(backup_path, TARGET)" in remote
    assert 'installed_capability("NO")' in remote
    assert 'result["rollback_required"] = bool(result["host_source_mutation"])' in remote
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["execution_contract"]["maximum_rollback_attempts"] == 1
    assert (
        manifest["execution_contract"]["postclaim_failure_consumes_authorization"]
        is True
    )


def test_status_reconciliation_never_false_passes_with_staging_residue() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"POSTSUCCESS_CLEANUP_UNCERTAIN"' in remote
    assert '"staging_residue": True' in remote
    assert '"terminal": False' in remote
    assert 'verify_sources(plan, target=True)' in remote
    assert 'installed_capability("YES")' in remote
    assert "r30s_terminal_transaction_drift" in remote
    assert "verify_runtime(plan)" in remote
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert (
        manifest["execution_contract"]["postsuccess_cleanup_must_be_reconciled"]
        is True
    )


def test_local_evidence_failure_never_leaves_pass_status() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert '"STOP_POSTSUCCESS_LOCAL"' in source
    assert '"completed_remote_status"' in source
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert (
        manifest["execution_contract"]["local_evidence_failure_never_reports_pass"]
        is True
    )


def test_timeout_path_reconciles_status_without_second_execute() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "def reconcile_after_invoke" in source
    assert '"status"' in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_consumed=True" in source
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
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


def test_target_binding_workflow_covers_r30s_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u7_prepare_host_source_activation_r30s/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "u7_prepare_host_source_activation_r30s/executor.py"
    )
    test_path = (
        "tests/tools/test_n3w_t1_u7_prepare_host_source_activation_r30s.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
