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
            "f3": {"sha256": "1" * 64},
            "f4": {"sha256": "2" * 64},
            "reboot": {"sha256": "3" * 64},
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


def test_public_result_drops_private_material():
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
        "private_password": "x",
        "raw_target": "10.0.0.2",
    }
    public = tool.public_result(private)
    assert "private_password" not in public
    assert "raw_target" not in public
    assert public["final_outcome"] == "PASS"
