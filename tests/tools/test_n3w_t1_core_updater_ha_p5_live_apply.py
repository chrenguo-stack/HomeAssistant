from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "u2"
    / "ha_p5_live_apply"
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


executor = load_module("ha_p5_executor", EXECUTOR_PATH)
remote = load_module("ha_p5_remote_live", REMOTE_PATH)


def test_manifest_is_preauth_only_and_single_use():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == (
        "N3W_T1_CORE_UPDATER_HOMEASSISTANT_"
        "P5_LIVE_APPLY_PREAUTHORIZATION_REVIEW_20261105_01"
    )
    assert manifest["authority_parent_head"] == (
        "d6b6d0f89837a85d94d60b4df45ab9eb4000d764"
    )
    assert manifest["p4_execution_head"] == (
        "8232707eb2c91d3fa9881e4cadba6b78eefc1494"
    )
    assert manifest["live_apply_authorized"] is False
    assert manifest["proposed_authorization_id"] == executor.AUTHORIZATION_ID
    contract = manifest["execution_contract"]
    assert contract["state"] == "PREAUTH_ONLY"
    assert contract["permitted_apply_invocations"] == 1
    assert contract["second_apply_allowed"] is False
    assert contract["blind_explicit_rollback_allowed"] is False
    assert contract["fresh_preflight_before_claim"] is True
    assert contract["require_p4_baseline_match"] is True
    assert contract["require_p4_transaction_match"] is True
    assert contract["require_archive_verified_plan"] is True
    assert contract["claim_immediately_before_apply"] is True
    assert contract["apply_failure_route"] == "READONLY_DIAGNOSE_AND_STOP"
    capacity = contract["capacity_policy"]
    assert capacity["storage_probe_authority"] == "tools/n3w_t1_fresh_product_staging_host.py"
    assert capacity["historical_fixed_5_gib_retired"] is True
    assert capacity["post_peak_reserve_bytes"] == 1610612736
    assert capacity["verify_post_cleanup_reserve"] is True
    assert capacity["product_runtime_min_free_requirement_state"] == "UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED"
    assert capacity["stop_before_remote_staging_on_failure"] is True


def test_exact_source_binding_validates_current_head():
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    report = executor.validate_source(head)
    assert report["exact_source_head"] == head
    assert report["authority_parent_head"] == (
        "d6b6d0f89837a85d94d60b4df45ab9eb4000d764"
    )
    assert report["p4_execution_head"] == (
        "8232707eb2c91d3fa9881e4cadba6b78eefc1494"
    )
    assert report["target_manifest_blob_sha"] == (
        "6966b4fe4d7620ccc436643cc840da9ae95e6010"
    )
    assert report["live_apply_authorized"] is False
    assert report["storage_policy_blob_sha"] == "01a5cec8877e2837504ed798e91ca552ab6f2a0e"


def test_storage_policy_derivation_is_bound_to_real_t1_evidence():
    policy = executor.validate_storage_policy()
    baseline = policy["measured_baseline"]
    admission = policy["p5_upgrade_admission"]
    assert baseline["filesystem_total_bytes"] == 14453903360
    assert baseline["filesystem_free_bytes"] == 5785710592
    assert baseline["observed_mutable_allocated_bytes"] == 174047232
    assert admission["derived_post_peak_reserve_bytes"] == 1610612736
    assert admission["exact_target_archive_staging_bytes"] == executor.ARCHIVE_SIZE_BYTES
    assert admission["rollback_predecessor_already_resident"] is True
    assert admission["predecessor_bytes_double_counted"] is False


def test_execute_stops_before_t1_while_manifest_is_not_authorized(tmp_path):
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    args = argparse.Namespace(
        authorization_id=executor.AUTHORIZATION_ID,
        confirm=executor.CONFIRMATION,
        target="root@192.0.2.1",
        expected_source_head=head,
        evidence_root=tmp_path / "evidence",
    )
    with pytest.raises(executor.StopExecution, match="live_apply_not_authorized"):
        executor.execute(args)
    assert not args.evidence_root.exists()


def test_live_sources_have_no_second_apply_or_explicit_rollback_route():
    executor_text = EXECUTOR_PATH.read_text(encoding="utf-8")
    remote_text = REMOTE_PATH.read_text(encoding="utf-8")

    assert executor_text.count('"apply",') == 1
    assert 'args.command == "apply"' in remote_text
    assert ".rollback(" not in executor_text
    assert ".rollback(" not in remote_text
    assert "blind_explicit_rollback_allowed" in executor_text
    assert "READONLY_DIAGNOSE_AND_STOP" in MANIFEST_PATH.read_text(encoding="utf-8")
    assert '"diagnose"' in executor_text


def test_capacity_gate_uses_evidence_bound_one_point_five_gib_reserve():
    artifact = {
        "image_uncompressed_bytes": 2 * 1024 * 1024 * 1024,
    }
    required = (
        executor.ARCHIVE_SIZE_BYTES
        + artifact["image_uncompressed_bytes"]
        + executor.P5_POST_PEAK_RESERVE_BYTES
    )
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
    assert report["post_peak_reserve_bytes"] == 1610612736
    assert report["historical_fixed_5_gib_retired"] is True
    assert report["rollback_predecessor_already_resident"] is True
    assert report["predecessor_bytes_double_counted"] is False
    assert report["product_runtime_min_free_requirement_state"] == "UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED"

    too_small = dict(storage)
    too_small["image_store_free_bytes"] = required - 1
    with pytest.raises(executor.StopExecution, match="remote_capacity_insufficient"):
        executor.capacity_report(artifact, too_small)


def test_preflight_contract_requires_p4_authority_and_verified_archive():
    document = {
        "schema": executor.REMOTE_SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "runtime_class": "TARGET_BOUND_RUNNING",
        "health_state": "HEALTHY",
        "recovery_required": False,
        "baseline_double_read_stable": True,
        "baseline_sha256": executor.P4_BASELINE_SHA256,
        "transaction_sha256": executor.P4_TRANSACTION_SHA256,
        "plan_sha256": "a" * 64,
        "target_image_prestate": "ABSENT",
        "target_archive_verified": True,
        "template_convergence_planned": True,
        "rollback_available": True,
    }
    executor.require_preflight_pass(document)

    for key, replacement in (
        ("baseline_sha256", "b" * 64),
        ("transaction_sha256", "c" * 64),
        ("target_archive_verified", False),
        ("target_image_prestate", "PRESENT_AND_EXACT"),
    ):
        broken = dict(document)
        broken[key] = replacement
        with pytest.raises(executor.StopExecution, match="live_preflight_contract_invalid"):
            executor.require_preflight_pass(broken)


def test_post_contract_requires_ha_target_and_peer_continuity():
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
        "transaction_sha256": "d" * 64,
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
    broken["image_bindings"] = dict(document["image_bindings"])
    broken["image_bindings"]["manager"] = "local/greenhouse-manager:fresh-deadbeefdead"
    with pytest.raises(executor.StopExecution, match="live_post_contract_invalid"):
        executor.require_post_pass(broken)


def test_remote_predecessor_and_target_validators():
    pre_status = {
        "status": "PASS",
        "operation": "status",
        "mutation": False,
        "recovery_required": False,
        "transaction": {
            "component": "manager",
            "status": "COMMITTED",
            "phase": "COMMITTED",
            "authorization_consumed": True,
        },
        "legacy_manager_transaction": None,
    }
    expected_tx = remote.sha256_bytes(remote.canonical(pre_status["transaction"]))
    original = remote.P4_TRANSACTION_SHA256
    try:
        remote.P4_TRANSACTION_SHA256 = expected_tx
        remote.validate_predecessor_status(pre_status)
    finally:
        remote.P4_TRANSACTION_SHA256 = original

    post_status = {
        "status": "PASS",
        "operation": "status",
        "mutation": False,
        "component": "homeassistant",
        "recovery_required": False,
        "transaction": {
            "component": "homeassistant",
            "status": "COMMITTED",
            "phase": "COMMITTED",
            "authorization_consumed": True,
            "predecessor_image": remote.EXPECTED_PREDECESSOR_IMAGE,
            "predecessor_binding_mode": "legacy_static",
        },
    }
    remote.validate_target_status(post_status)
