from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "tools" / "execution_packages" / "n3w" / "u2"
    / "ha_p5_reapply_live_apply"
)
EXECUTOR_PATH = PACKAGE / "executor.py"
REMOTE_PATH = PACKAGE / "remote_live.py"
MANIFEST_PATH = PACKAGE / "manifest.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


executor = load_module("ha_p5_reapply_executor", EXECUTOR_PATH)
remote = load_module("ha_p5_reapply_remote", REMOTE_PATH)


def test_manifest_has_exact_one_shot_authorization_but_is_unclaimed():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == (
        "N3W_T1_CORE_UPDATER_HOMEASSISTANT_"
        "P5_REAPPLY_PREAUTHORIZATION_REVIEW_20261106_01"
    )
    assert manifest["authority_parent_head"] == (
        "72acefe2a4aa6505d6921f795d734db7cf3c64a8"
    )
    assert manifest["postcleanup_preflight_closure_blob_sha"] == (
        "5151dd8a63de7132e169068356674db001daec76"
    )
    assert manifest["live_reapply_authorized"] is True
    assert manifest["proposed_authorization_id"] == executor.AUTHORIZATION_ID
    assert manifest["authorization"]["granted"] is True
    assert manifest["authorization"]["granted_by"] == "explicit_user_authorization"
    assert manifest["authorization"]["granted_date"] == "2026-11-06"
    assert manifest["authorization"]["claimed"] is False
    assert manifest["authorization"]["consumed"] is False
    assert manifest["authorization"]["replay_permitted"] is False
    assert manifest["authorization"]["remaining_apply_invocations"] == 1
    assert manifest["final_source_review_closure_blob_sha"] == "43caa099cac495c7c0e169e40c9583a87db5f798"
    assert manifest["source_binding"]["docs/development/N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_REAPPLY_FINAL_SOURCE_REVIEW_CLOSURE_20261106.md"] == "43caa099cac495c7c0e169e40c9583a87db5f798"
    assert manifest["execution_contract"]["state"] == "AUTHORIZED_UNCLAIMED"
    contract = manifest["execution_contract"]
    assert contract["require_previous_rolled_back_transaction"] is True
    assert contract["require_target_image_prestate"] == "PRESENT_AND_EXACT"
    assert contract["expect_candidate_image_preexisting"] is True
    assert contract["expect_docker_load"] is False
    assert contract["homeassistant_readiness_timeout_seconds"] == 600
    assert contract["remote_apply_timeout_seconds"] == 3600
    assert contract["second_apply_allowed"] is False
    assert contract["blind_explicit_rollback_allowed"] is False


def test_historical_execution_package_rejects_successor_ancestry_and_source_drift():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen_blob = manifest["source_binding"][
        "tools/n3w_t1_core_updater_v2_state.py"
    ]
    assert frozen_blob == "a5260f1097983cad4818f626826accbb185e4a37"

    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    current_blob = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "rev-parse",
            f"{head}:tools/n3w_t1_core_updater_v2_state.py",
        ],
        text=True,
    ).strip()
    assert current_blob != frozen_blob
    with pytest.raises(
        executor.StopExecution,
        match="authority_parent_not_ancestor",
    ):
        executor.validate_source(head)


def test_unauthorized_reapply_stops_before_evidence_or_t1(tmp_path, monkeypatch):
    args = argparse.Namespace(
        authorization_id=executor.AUTHORIZATION_ID,
        confirm=executor.CONFIRMATION,
        target="root@192.0.2.1",
        expected_source_head="a" * 40,
        evidence_root=tmp_path / "evidence",
        known_hosts=tmp_path / "known_hosts",
        expected_host_key_sha256="b" * 64,
    )
    monkeypatch.setattr(
        executor,
        "validate_source",
        lambda expected_head: {
            "exact_source_head": expected_head,
            "live_reapply_authorized": False,
        },
    )
    with pytest.raises(executor.StopExecution, match="live_reapply_not_authorized"):
        executor.execute(args)
    assert not args.evidence_root.exists()


def test_capacity_for_preexisting_target_requires_archive_plus_reserve_only():
    artifact = {"image_uncompressed_bytes": 2 * 1024 * 1024 * 1024}
    required = executor.ARCHIVE_SIZE_BYTES + executor.P5_POST_PEAK_RESERVE_BYTES
    storage = {
        "staging_device": 1,
        "docker_device": 1,
        "image_store_device": 1,
        "image_store_backend": "classic",
        "image_store_root_source": "docker_root",
        "staging_free_bytes": required,
        "docker_free_bytes": required,
        "image_store_free_bytes": required,
    }
    report = executor.capacity_report(artifact, storage)
    assert report["capacity_pass"] is True
    assert report["preexisting_exact_target_required"] is True
    assert report["docker_load_expected"] is False
    assert report["required_peak_bytes"] == executor.ARCHIVE_SIZE_BYTES
    assert report["required_total_bytes"] == required

    too_small = dict(storage)
    too_small["docker_free_bytes"] = required - 1
    with pytest.raises(executor.StopExecution, match="remote_capacity_insufficient"):
        executor.capacity_report(artifact, too_small)


def test_preflight_contract_requires_rolled_back_runtime_and_present_exact_target():
    document = {
        "schema": executor.REMOTE_SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "runtime_class": "PREDECESSOR_BOUND_RUNNING",
        "health_state": "HEALTHY",
        "recovery_required": False,
        "baseline_double_read_stable": True,
        "baseline_sha256": executor.P4_BASELINE_SHA256,
        "transaction_sha256": "a" * 64,
        "plan_sha256": "b" * 64,
        "target_image_prestate": "PRESENT_AND_EXACT",
        "target_archive_verified": True,
        "template_convergence_planned": True,
        "rollback_available": True,
    }
    executor.require_preflight_pass(document)

    for key, value in (
        ("runtime_class", "TARGET_BOUND_RUNNING"),
        ("target_image_prestate", "ABSENT"),
        ("target_archive_verified", False),
    ):
        broken = dict(document)
        broken[key] = value
        with pytest.raises(
            executor.StopExecution,
            match="live_preflight_contract_invalid",
        ):
            executor.require_preflight_pass(broken)


def test_remote_accepts_only_attempt03_rolled_back_predecessor_state():
    status = {
        "status": "PASS",
        "operation": "status",
        "mutation": False,
        "recovery_required": False,
        "transaction": {
            "component": "homeassistant",
            "status": "ROLLED_BACK",
            "phase": "ROLLED_BACK",
            "authorization_consumed": True,
            "predecessor_image": remote.EXPECTED_PREDECESSOR_IMAGE,
            "predecessor_binding_mode": "legacy_static",
            "target": {
                "target_image_ref": remote.EXPECTED_TARGET_IMAGE,
            },
            "last_runtime_class": "PREDECESSOR_BOUND_RUNNING",
            "last_health_state": "HEALTHY",
        },
        "legacy_manager_transaction": None,
    }
    remote.validate_predecessor_status(status)
    broken = json.loads(json.dumps(status))
    broken["transaction"]["status"] = "COMMITTED"
    with pytest.raises(remote.StopLive, match="pre_transaction_status_invalid"):
        remote.validate_predecessor_status(broken)

    runtime = {
        "status": "PASS",
        "operation": "runtime-state",
        "mutation": False,
        "component": "homeassistant",
        "runtime_class": "PREDECESSOR_BOUND_RUNNING",
        "health_state": "HEALTHY",
        "observed": {
            "image_bindings": remote.EXPECTED_PREDECESSOR_IMAGES,
            "image_binding_modes": remote.EXPECTED_PREDECESSOR_MODES,
        },
    }
    remote.validate_predecessor_runtime(runtime)


def test_remote_plan_accepts_present_and_exact_only():
    plan = {
        "status": "PASS",
        "operation": "plan",
        "component": "homeassistant",
        "mutation": False,
        "current": {
            "image": remote.EXPECTED_PREDECESSOR_IMAGE,
            "binding_mode": "legacy_static",
        },
        "target": {
            "target_image_ref": remote.EXPECTED_TARGET_IMAGE,
            "expected_predecessor_image_ref": remote.EXPECTED_PREDECESSOR_IMAGE,
        },
        "target_image_prestate": "PRESENT_AND_EXACT",
        "target_archive_verified": True,
        "actions": [
            "converge_homeassistant_runtime_template",
            "replace_only_homeassistant_image_binding",
        ],
        "rollback_available": True,
    }
    remote.validate_plan(plan)
    broken = dict(plan)
    broken["target_image_prestate"] = "ABSENT"
    with pytest.raises(remote.StopLive, match="plan_target_prestate_invalid"):
        remote.validate_plan(broken)


def test_post_contract_proves_preexisting_candidate_path():
    document = {
        "schema": executor.REMOTE_SCHEMA,
        "status": "PASS",
        "operation": "post",
        "mutation": False,
        "recovery_required": False,
        "runtime_class": "TARGET_BOUND_RUNNING",
        "health_state": "HEALTHY",
        "image_bindings": {
            "manager": "local/greenhouse-manager:fresh-5b32e1ae8210",
            "homeassistant": executor.TARGET_IMAGE,
            "broker": "local/n3w-mosquitto:2.1.2-3184566d",
        },
        "image_binding_modes": {
            "manager": "dynamic",
            "homeassistant": "dynamic",
            "broker": "legacy_static",
        },
        "transaction_sha256": "c" * 64,
        "candidate_image_preexisting": True,
        "manager_mqtt_authenticated": True,
        "homeassistant_mqtt_authenticated": True,
        "homeassistant_http_status": 401,
        "listeners": {
            "tcp_8883": 1,
            "tcp_47110": 1,
            "udp_47111": 1,
            "tcp_47112": 0,
        },
    }
    executor.require_post_pass(document)
    broken = dict(document)
    broken["candidate_image_preexisting"] = False
    with pytest.raises(
        executor.StopExecution,
        match="live_post_contract_invalid",
    ):
        executor.require_post_pass(broken)


def test_reapply_has_one_apply_no_explicit_rollback_and_bound_scratch():
    executor_text = EXECUTOR_PATH.read_text(encoding="utf-8")
    remote_text = REMOTE_PATH.read_text(encoding="utf-8")
    assert executor_text.count('"apply",') == 1
    assert ".rollback(" not in executor_text
    assert ".rollback(" not in remote_text
    assert "READONLY_DIAGNOSE_AND_STOP" in MANIFEST_PATH.read_text(encoding="utf-8")
    assert "/var/tmp/n3w-ha-p5-reapply" in executor_text
    assert 'r"/var/tmp/n3w-ha-p5-reapply\\.' in executor_text
    assert executor.REMOTE_APPLY_TIMEOUT_SECONDS == 3600
