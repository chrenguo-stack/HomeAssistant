from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production_contract.py"


def load_tool():
    name = "n3w_t1_production_contract_test"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def release(tool):
    document = {
        "schema": tool.RELEASE_SCHEMA,
        "release_id": "0" * 64,
        "source_head": "a" * 40,
        "artifacts": {
            name: {"sha256": f"{index:064x}"}
            for index, name in enumerate(tool.REQUIRED_ARTIFACT_NAMES, 1)
        },
        "environment": {
            "os": {"id": "ubuntu", "version": "26.04", "codename": "resolute"},
            "architecture": "aarch64",
            "packages": {
                "docker.io": "28.2.2-0ubuntu1",
                "docker-compose-v2": "2.37.1+ds1-1",
            },
        },
        "check_policy": {
            "schema": tool.CHECK_POLICY_SCHEMA,
            "allow_overrides": [],
        },
        "result_schema": tool.RESULT_SCHEMA,
    }
    document["release_id"] = tool.canonical_sha256(
        {key: value for key, value in document.items() if key != "release_id"}
    )
    return document


def test_release_binds_environment_and_artifacts():
    tool = load_tool()
    assert tool.validate_release(release(tool)) == release(tool)


def test_release_drift_is_rejected():
    tool = load_tool()
    document = release(tool)
    document["environment"]["packages"]["docker.io"] = "later"
    with pytest.raises(tool.ProductionContractError, match="release_id_binding_invalid"):
        tool.validate_release(document)


def test_production_override_allowlist_is_empty():
    tool = load_tool()
    policy = {"schema": tool.CHECK_POLICY_SCHEMA, "allow_overrides": []}
    decision = tool.evaluate_check(
        "USABILITY.NONCRITICAL",
        "FAIL",
        policy=policy,
        operator_approved=True,
    )
    assert decision["decision"] == "STOP"
    assert decision["override_used"] is False


def test_hard_stop_and_unknown_check_cannot_be_overridden():
    tool = load_tool()
    policy = {"schema": tool.CHECK_POLICY_SCHEMA, "allow_overrides": []}
    for check_id in ("AUTH.RUN_PHASE", "FUTURE.UNKNOWN"):
        decision = tool.evaluate_check(
            check_id,
            "FAIL",
            policy=policy,
            operator_approved=True,
        )
        assert decision["decision"] == "STOP"
        assert decision["severity"] == "HARD_STOP"


def test_public_result_drops_non_allowlisted_material():
    tool = load_tool()
    private = {
        "schema": tool.RESULT_SCHEMA,
        "status": "PASS",
        "final_outcome": "PASS",
        "release_id": "1" * 64,
        "release_sha256": "2" * 64,
        "source_head": "a" * 40,
        "run_id_sha256": "3" * 64,
        "target_binding_sha256": "4" * 64,
        "ssh_host_key_sha256": "5" * 64,
        "device_acceptance": True,
        "operator_session_closed": True,
        "evidence_complete": True,
        "override_used": False,
        "override_check_ids": [],
        "terminal_phase": "CLOSE_RUN",
        "board_access": False,
        "production_service_start": True,
        "internal_material": "example.invalid",
    }
    public = tool.public_result(private)
    assert "internal_material" not in public
    assert public["final_outcome"] == "PASS"
    assert public["private_result_sha256"] == tool.canonical_sha256(private)


def test_unknown_check_pass_is_still_hard_stop():
    tool = load_tool()
    decision = tool.evaluate_check(
        "FUTURE.UNKNOWN",
        "PASS",
        policy={"schema": tool.CHECK_POLICY_SCHEMA, "allow_overrides": []},
    )
    assert decision == {
        "check_id": "FUTURE.UNKNOWN",
        "severity": "HARD_STOP",
        "decision": "STOP",
        "override_used": False,
    }


def test_production_release_rejects_nonempty_override_allowlist():
    tool = load_tool()
    document = release(tool)
    document["check_policy"]["allow_overrides"] = ["USABILITY.NONCRITICAL"]
    document["release_id"] = tool.canonical_sha256(
        {key: value for key, value in document.items() if key != "release_id"}
    )
    with pytest.raises(
        tool.ProductionContractError,
        match="release_override_policy_not_empty",
    ):
        tool.validate_release(document)


def test_public_result_rejects_hard_stop_override_id():
    tool = load_tool()
    private = {
        "schema": tool.RESULT_SCHEMA,
        "status": "PASS",
        "final_outcome": "PASS_WITH_OVERRIDE",
        "release_id": "1" * 64,
        "release_sha256": "2" * 64,
        "source_head": "a" * 40,
        "run_id_sha256": "3" * 64,
        "target_binding_sha256": "4" * 64,
        "ssh_host_key_sha256": "5" * 64,
        "device_acceptance": True,
        "operator_session_closed": True,
        "evidence_complete": True,
        "override_used": True,
        "override_check_ids": ["AUTH.RUN_PHASE"],
        "terminal_phase": "CLOSE_RUN",
        "board_access": False,
        "production_service_start": True,
    }
    with pytest.raises(
        tool.ProductionContractError,
        match="result_override_check_ids_invalid",
    ):
        tool.public_result(private)


def test_release_requires_complete_exact_artifact_set():
    tool = load_tool()
    document = release(tool)
    document["artifacts"].pop("transport_contract")
    document["release_id"] = tool.canonical_sha256(
        {key: value for key, value in document.items() if key != "release_id"}
    )
    with pytest.raises(tool.ProductionContractError, match="release_artifacts_invalid"):
        tool.validate_release(document)


def test_phase_artifact_digest_is_bound_to_approved_release():
    tool = load_tool()
    document = release(tool)
    original = tool.phase_artifact_sha256(document, "F3_DEPLOY")
    document["artifacts"]["manager_image_tar"]["sha256"] = "f" * 64
    document["release_id"] = tool.canonical_sha256(
        {key: value for key, value in document.items() if key != "release_id"}
    )
    changed = tool.phase_artifact_sha256(document, "F3_DEPLOY")
    assert changed != original


def test_preflight_requires_every_frozen_readonly_check():
    tool = load_tool()
    report = {
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "checks": {check_id: "PASS" for check_id in tool.PREFLIGHT_CHECK_IDS},
    }
    assert tool.validate_preflight_report(report) == report
    report["checks"].pop("HOST.PRODUCT_ABSENT")
    with pytest.raises(tool.ProductionContractError, match="preflight_checks_invalid"):
        tool.validate_preflight_report(report)
