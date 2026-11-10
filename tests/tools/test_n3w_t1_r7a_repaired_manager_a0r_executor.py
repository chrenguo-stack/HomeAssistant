from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = ROOT / "tools/execution_packages/n3w/r7a/repaired_manager_a0r_live_apply/executor.py"
MANIFEST_PATH = EXECUTOR_PATH.with_name("manifest.json")

def load_executor():
    spec = importlib.util.spec_from_file_location("r7a_repaired_manager_a0r_executor", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_a0r_manifest_is_live_authorized_and_manager_only() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "gh.n3w-t1-r7a-repaired-manager-a0r-live-execution-package/1"
    assert document["live_execution_authorized"] is True
    assert document["preconditions"]["fresh_live_readonly_revalidation_required"] is True
    assert document["preconditions"]["derived_baseline_is_not_fresh_live_evidence"] is True
    contract = document["execution_contract"]
    assert contract["manager_only_mutation"] is True
    assert contract["homeassistant_image_mutation"] is False
    assert contract["broker_image_mutation"] is False
    assert contract["host_daemon_activation"] is False
    assert contract["usb_mutation"] is False
    assert contract["one_apply_maximum"] is True
    assert contract["automatic_retry"] is False
    assert contract["executor_explicit_rollback"] is False
    assert contract["updater_internal_failure_rollback"] is True

def test_a0r_exact_package_authority_is_frozen() -> None:
    executor = load_executor()
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    authority = document["package_authority"]
    assert executor.RUN_ID == authority["workflow_run_id"] == 42480154921
    assert executor.ARTIFACT_ID == authority["artifact_id"] == 13616844356
    assert executor.ARTIFACT_NAME == authority["artifact_name"] == "n3w-t1-core-updater-manager-v2-7807271e4c48"
    assert executor.ARTIFACT_DIGEST == authority["artifact_digest"] == "sha256:3c07406cd51258c8ef95f02e1e6cc80d09eb7235c218e7ead74a02a5521442fd"
    assert executor.PACKAGE_CONTROL_HEAD == authority["package_control_head"] == "4c883c02fbf3a64d944548a1dda8c7431d59ae61"
    assert executor.UPDATER_PYZ_SHA256 == authority["updater_pyz_sha256"] == "c0461a5097d8af0f8a6e7f3a175b7dadc82b55a436c6c229092262cd35521b44"
    assert executor.MANAGER_TAR_SHA256 == authority["manager_tar_sha256"] == "9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67"
    assert executor.MANAGER_BUILD_IMAGE_ID == authority["manager_build_image_id"] == "sha256:b1875c6ed969df108d2df768d61369a0c93956d146f284276b392c686c13a4f9"
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert 'binding.get("upstream_artifact_id") != 13615963302' in source

def test_a0r_target_chain_is_bf38_to_repaired_780727() -> None:
    executor = load_executor()
    assert executor.EXPECTED_PREDECESSOR == "local/greenhouse-manager:fresh-bf38e388497b"
    assert executor.TARGET_MANAGER == "local/greenhouse-manager:fresh-7807271e4c48"
    assert executor.EXPECTED_RUNTIME_IDS["manager"] == "sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff"
    target = json.loads((ROOT / executor.TARGET_RELATIVE).read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / executor.BASELINE_RELATIVE).read_text(encoding="utf-8"))
    assert target["expected_predecessor_image_ref"] == executor.EXPECTED_PREDECESSOR
    assert target["target_image_ref"] == executor.TARGET_MANAGER
    assert target["rollback_compatible"] is True
    assert baseline["stack_images"] == executor.EXPECTED_IMAGES

def test_a0r_new_authorization_is_distinct_and_enabled() -> None:
    executor = load_executor()
    assert executor.AUTHORIZATION == "N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01"
    assert executor.AUTHORIZATION != "N3W_T1_CORE_UPDATER_R7A_MANAGER_SUCCESSOR_A0_LIVE_APPLY_20261107_02"
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    document = executor.validate_local_source(head, require_live=True)
    assert document["live_execution_authorized"] is True

def test_a0r_orders_readonly_state_before_staging_and_captures_failure_state() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    assert execute_source.index("collect_updater_state_readonly(transport)") < execute_source.index("stage_package(transport, package)")
    post_status = execute_source.index('["status"]')
    post_inspect = execute_source.index('["inspect", "--component", "manager"]', post_status)
    decision = execute_source.index('raise StopExecution("apply_not_committed")')
    assert post_status < decision
    assert post_inspect < decision
    assert "apply_transport.json" in execute_source

def test_a0r_post_apply_binds_committed_runtime_image_id() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = source[source.index("def validate_post_apply("):source.index("def execute(")]
    assert 'transaction.get("authorization_consumed") is not True' in post
    assert 'transaction.get("authorization_id_sha256")' in post
    assert 'hashlib.sha256(AUTHORIZATION.encode("utf-8")).hexdigest()' in post
    assert 'transaction.get("target_runtime_image_id")' in post
    assert 'manager_runtime.get("image_id") != target_runtime_id' in post
    assert 'target_doc.get("Image") != target_runtime_id' in post


def test_a0r_executor_fail_closes_unexpected_runtime_errors() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    assert "except Exception as error:" in execute_source
    assert "executor_runtime_error:" in execute_source
    assert 'closure["first_failed_operation"]' in execute_source
