from __future__ import annotations

import ast
import hashlib
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
    / "kf147_removable_media_content_authority_v1_2_source_activation_r2"
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
    "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_R2_20261113_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_v1_2_source_activation_r2_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_exact_successor() -> None:
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
    assert document["authorization_grant"] == {
        "source": "not_granted",
        "date": "2026-11-13",
        "scope": "successor_exact_8_file_v1_2_source_slice_on_real_t1_only",
        "execute_in_next_chat": False,
    }
    predecessor = document["predecessor_consumed_gate"]
    assert predecessor["authorization_consumed"] is True
    assert predecessor["replay_permitted"] is False
    assert predecessor["rollback_restoration_readonly_verified"] is True
    assert predecessor["u4_preserved"] is True
    assert len(document["source_files"]) == 8
    contract = document["execution_contract"]
    assert contract["bounded_post_restart_readiness"] is True
    assert contract["post_restart_readiness_timeout_seconds"] == 120
    assert contract["automatic_retry"] is False
    assert contract["maximum_rollback_attempts"] == 1
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False


def test_manifest_target_hashes_match_exact_repository_files() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for item in document["source_files"]:
        source = ROOT / item["repo_path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["target_sha256"]


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<v1-2-source-activation-r2>", "exec")
    assert module.GATE_ID == GATE

    tree = ast.parse(module.REMOTE_SCRIPT)
    constants = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert GATE in constants
    assert (
        "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
        "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_20261112_01"
        not in constants
    )


def test_manifest_binds_exact_r2_executor_blob() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = document["package_source_authority"][
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_source_activation_r2/"
        "executor.py"
    ]
    import subprocess

    observed = subprocess.run(
        ["git", "-C", str(ROOT), "hash-object", str(EXECUTOR)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    assert observed == expected


def test_runtime_readiness_wait_is_bounded_and_post_restart_only() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "def wait_runtime_baseline(" in source
    assert "timeout_seconds=120" in source
    assert '"container_cardinality_invalid:"' in source
    assert '"container_not_ready:"' in source
    assert '"ipc_status_unavailable:"' in source
    assert '"ipc_not_ready_to_install"' in source
    assert 'raise Stop("runtime_readiness_timeout:" + last_reason[:180])' in source

    verify_start = source.index("def verify_containers(plan):")
    wait_start = source.index("def wait_runtime_baseline(")
    rollback_start = source.index("def rollback(plan, backup_dir):")
    execute_start = source.index("def execute(plan, authorization, confirmation):")
    assert verify_start < wait_start < rollback_start < execute_start

    verify_body = source[verify_start:wait_start]
    assert 'raise Stop("container_drift:" + name)' in verify_body
    assert 'raise Stop("container_not_ready:" + name)' in verify_body
    assert 'observed["restart_count"] != 0' in verify_body

    rollback_body = source[rollback_start:execute_start]
    assert "wait_runtime_baseline(" in rollback_body
    assert "target_sources=False" in rollback_body

    execute_body = source[execute_start:]
    assert "post = wait_runtime_baseline(" in execute_body
    assert "target_sources=True" in execute_body
    assert "postclaim = baseline(plan, target_sources=False)" in execute_body
    assert "pre = baseline(plan, target_sources=False)" in execute_body


def test_successor_keeps_old_gate_non_replayable_and_u4_only() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = load_executor().REMOTE_SCRIPT
    assert document["predecessor_consumed_gate"]["terminal_status"] == "STOP"
    assert document["execution_contract"]["transaction_mutation"] is False
    assert document["execution_contract"]["usb_mutation"] is False
    assert document["execution_contract"]["mount"] is False
    assert document["execution_contract"]["umount"] is False
    assert document["execution_contract"]["u5_transition"] is False
    assert document["execution_contract"]["u6_plus"] is False
    assert '"action": "INSTALL"' not in source
    assert "request_install(" not in source


def test_ungranted_package_allows_preflight_but_not_execute() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'if execute and document.get("live_execution_authorized") is not True' in source
    assert 'if not execute and document.get("live_execution_authorized") is not False' in source
    assert 'raise Stop("live_execution_not_authorized")' in source


def test_target_binding_workflow_covers_r2_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_source_activation_r2/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_source_activation_r2/"
        "executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_kf147_removable_media_content_authority_v1_2_"
        "source_activation_r2.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
