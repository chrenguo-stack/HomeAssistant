from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production_v2_contract.py"


def load_tool():
    name = "n3w_t1_production_v2_contract_test"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    sys.modules[name] = tool
    spec.loader.exec_module(tool)
    return tool


contract = load_tool()


def release_document():
    return {
        "schema": contract.RELEASE_SCHEMA,
        "release_id": "a" * 64,
        "source_head": "b" * 40,
        "source_tree": "c" * 40,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": {
            name: {"sha256": str(index % 10) * 64, "size_bytes": index}
            for index, name in enumerate(
                sorted(contract.REQUIRED_RELEASE_ARTIFACTS), start=1
            )
        },
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": [
            "status",
            "release_id",
            "source_head",
            "run_id_sha256",
        ],
    }


def test_release_contract_accepts_frozen_v2_environment():
    value = release_document()
    assert contract.validate_release(value) == value


def test_release_rejects_latest_package_ambiguity():
    value = release_document()
    value["packages"]["docker.io"] = ""
    with pytest.raises(contract.ProductionV2ContractError, match="package_docker.io_invalid"):
        contract.validate_release(value)


def test_release_requires_distinct_f3_image_binding():
    value = release_document()
    del value["artifacts"]["f3_image"]
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="release_artifacts_missing",
    ):
        contract.validate_release(value)


def test_release_rejects_sensitive_public_field():
    value = release_document()
    value["public_evidence_fields"].append("mqtt_password")
    with pytest.raises(contract.ProductionV2ContractError, match="public_evidence_field_sensitive"):
        contract.validate_release(value)


def test_run_context_is_external_f3_deploy_authority():
    value = {
        "schema": contract.RUN_CONTEXT_SCHEMA,
        "run_id": "1" * 64,
        "release_id": "2" * 64,
        "release_sha256": "3" * 64,
        "source_head": "4" * 40,
        "target_binding_sha256": "5" * 64,
        "production_marker_sha256": "6" * 64,
        "action": "F3_DEPLOY",
    }
    assert contract.validate_run_context(value) == value
    value["action"] = "REPAIR"
    with pytest.raises(contract.ProductionV2ContractError, match="run_context_action_invalid"):
        contract.validate_run_context(value)


def test_marker_acceptance_requires_ready_true_and_acceptance_hash():
    started = {
        "schema": contract.RUN_MARKER_SCHEMA,
        "run_id": "1" * 64,
        "release_id": "2" * 64,
        "release_sha256": "3" * 64,
        "source_head": "4" * 40,
        "target_binding_sha256": "5" * 64,
        "ssh_host_key_sha256": "6" * 64,
        "plan_sha256": "7" * 64,
        "state": "STARTED",
        "replay_allowed": False,
        "created_at": "2026-10-20T00:00:00Z",
    }
    assert contract.validate_marker(started) == started
    accepted = copy.deepcopy(started)
    accepted.update(
        {
            "state": "ACCEPTED",
            "acceptance_sha256": "8" * 64,
            "accepted_at": "2026-10-20T00:05:00Z",
            "T1_PRODUCTION_READY": True,
        }
    )
    assert contract.validate_marker(accepted) == accepted
    accepted["T1_PRODUCTION_READY"] = False
    with pytest.raises(contract.ProductionV2ContractError, match="marker_ready_invalid"):
        contract.validate_marker(accepted)


def test_plan_action_order_is_frozen():
    value = {
        "schema": contract.PLAN_SCHEMA,
        "run_id": "1" * 64,
        "release_id": "2" * 64,
        "release_sha256": "3" * 64,
        "source_head": "4" * 40,
        "target_binding_sha256": "5" * 64,
        "ssh_host_key_sha256": "6" * 64,
        "actions": list(contract.V2_ACTIONS),
    }
    assert contract.validate_plan(value) == value
    value["actions"].reverse()
    with pytest.raises(contract.ProductionV2ContractError, match="plan_actions_invalid"):
        contract.validate_plan(value)


def test_canonical_hash_is_order_independent():
    a = {"a": 1, "b": {"x": True, "y": False}}
    b = {"b": {"y": False, "x": True}, "a": 1}
    assert contract.canonical_sha256(a) == contract.canonical_sha256(b)


def result_document():
    return {
        "schema": contract.RESULT_SCHEMA,
        "status": "PASS",
        "release_id": "1" * 64,
        "release_sha256": "2" * 64,
        "source_head": "3" * 40,
        "run_id_sha256": "4" * 64,
        "target_binding_sha256": "5" * 64,
        "marker_state": "ACCEPTED",
        "error_class": "NONE",
        "device_acceptance": "PASS",
        "T1_PRODUCTION_READY": True,
        "operator_session_closed": True,
        "evidence_complete": True,
        "reflash_required": False,
        "terminal_stage": "COMPLETE",
        "private_result_sha256": "6" * 64,
    }


def test_result_pass_requires_accepted_ready_closed_and_evidence_complete():
    value = result_document()
    assert contract.validate_result(value) == value

    for key, replacement, error in (
        ("marker_state", "STARTED", "result_device_acceptance_without_accepted_marker"),
        ("error_class", "PROCESS_CLEANUP_FAIL", "result_pass_error_class_invalid"),
        ("device_acceptance", "NOT_REACHED", "result_acceptance_ready_mismatch"),
        ("T1_PRODUCTION_READY", False, "result_acceptance_ready_mismatch"),
        ("operator_session_closed", False, "result_pass_without_session_close"),
        ("evidence_complete", False, "result_pass_without_evidence"),
        ("reflash_required", True, "result_accepted_device_reflash_forbidden"),
    ):
        candidate = copy.deepcopy(value)
        candidate[key] = replacement
        with pytest.raises(contract.ProductionV2ContractError, match=error):
            contract.validate_result(candidate)


def test_result_allows_accepted_device_with_later_mac_cleanup_failure():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "error_class": "PROCESS_CLEANUP_FAIL",
            "operator_session_closed": False,
            "evidence_complete": False,
            "reflash_required": False,
            "terminal_stage": "PROCESS_CLEANUP_FAIL",
        }
    )
    assert contract.validate_result(value) == value


def test_result_rejects_reflash_for_durable_accepted_device():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "reflash_required": True,
            "terminal_stage": "PROCESS_CLEANUP_FAIL",
        }
    )
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="result_accepted_device_reflash_forbidden",
    ):
        contract.validate_result(value)


def test_result_started_failure_requires_reflash():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "STARTED",
            "error_class": "MUTATION_FAIL_REFLASH_REQUIRED",
            "device_acceptance": "NOT_REACHED",
            "T1_PRODUCTION_READY": False,
            "operator_session_closed": True,
            "evidence_complete": True,
            "reflash_required": True,
            "terminal_stage": "F3_DEPLOY",
        }
    )
    assert contract.validate_result(value) == value

    value["reflash_required"] = False
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="result_started_failure_requires_reflash",
    ):
        contract.validate_result(value)


def test_result_post_reboot_acceptance_failure_requires_reflash():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "STARTED",
            "error_class": "POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED",
            "device_acceptance": "FAIL",
            "T1_PRODUCTION_READY": False,
            "operator_session_closed": True,
            "evidence_complete": True,
            "reflash_required": True,
            "terminal_stage": "POST_REBOOT_ACCEPTANCE",
        }
    )
    assert contract.validate_result(value) == value


def test_result_pre_mutation_failure_can_be_non_reflash():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "ABSENT",
            "error_class": "PRE_MUTATION_FAIL",
            "device_acceptance": "NOT_REACHED",
            "T1_PRODUCTION_READY": False,
            "operator_session_closed": True,
            "evidence_complete": True,
            "reflash_required": False,
            "terminal_stage": "QUALIFICATION",
        }
    )
    assert contract.validate_result(value) == value

    value["reflash_required"] = True
    assert contract.validate_result(value) == value


def test_result_absent_marker_cannot_claim_mutation_failure_class():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "ABSENT",
            "error_class": "MUTATION_FAIL_REFLASH_REQUIRED",
            "device_acceptance": "NOT_REACHED",
            "T1_PRODUCTION_READY": False,
            "reflash_required": True,
            "terminal_stage": "QUALIFICATION",
        }
    )
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="result_absent_marker_error_class_invalid",
    ):
        contract.validate_result(value)


def test_result_started_marker_cannot_claim_pre_mutation_failure():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "STARTED",
            "error_class": "PRE_MUTATION_FAIL",
            "device_acceptance": "NOT_REACHED",
            "T1_PRODUCTION_READY": False,
            "reflash_required": True,
            "terminal_stage": "HOST_BASELINE",
        }
    )
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="result_started_error_class_invalid",
    ):
        contract.validate_result(value)


def test_result_absent_marker_cannot_claim_device_acceptance():
    value = result_document()
    value.update(
        {
            "status": "FAIL",
            "marker_state": "ABSENT",
            "error_class": "PRE_MUTATION_FAIL",
            "device_acceptance": "FAIL",
            "T1_PRODUCTION_READY": False,
            "reflash_required": True,
            "terminal_stage": "QUALIFICATION",
        }
    )
    with pytest.raises(
        contract.ProductionV2ContractError,
        match="result_absent_marker_device_acceptance_invalid",
    ):
        contract.validate_result(value)
