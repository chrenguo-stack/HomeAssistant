from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tools/n3w_t1_production_contract.py"
TOOL = ROOT / "tools/n3w_t1_production_authority.py"


def load_modules():
    contract_spec = importlib.util.spec_from_file_location(
        "n3w_t1_production_contract",
        CONTRACT,
    )
    assert contract_spec is not None and contract_spec.loader is not None
    contract = importlib.util.module_from_spec(contract_spec)
    sys.modules["n3w_t1_production_contract"] = contract
    contract_spec.loader.exec_module(contract)
    spec = importlib.util.spec_from_file_location("authority_test", TOOL)
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    sys.modules["authority_test"] = tool
    spec.loader.exec_module(tool)
    return contract, tool


def make_plan(contract):
    plan = {
        "schema": contract.PLAN_SCHEMA,
        "run_id": "9" * 64,
        "release_id": "1" * 64,
        "release_sha256": "2" * 64,
        "source_head": "a" * 40,
        "target_binding_sha256": "4" * 64,
        "ssh_host_key_sha256": "5" * 64,
        "plan_digest": "0" * 64,
        "approved_at": 100,
        "expires_at": 500,
        "max_duration_seconds": 400,
        "phases": list(contract.PHASES),
        "reboot_budget": 1,
    }
    plan["plan_digest"] = contract.canonical_sha256(plan)
    return plan


def binding(plan, predecessor=None):
    return {
        "source_head": plan["source_head"],
        "release_id": plan["release_id"],
        "artifact_sha256": "6" * 64,
        "predecessor_sha256": predecessor,
        "target_binding_sha256": plan["target_binding_sha256"],
    }


def approve(monkeypatch, tmp_path):
    contract, tool = load_modules()
    monkeypatch.setattr(tool, "_require_root", lambda: None)
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    plan = make_plan(contract)
    tool.approve_run(
        plan,
        root=tmp_path,
        now=100,
        identity={
            "target_binding_sha256": plan["target_binding_sha256"],
            "ssh_host_key_sha256": plan["ssh_host_key_sha256"],
        },
    )
    return contract, tool, plan


def test_arbitrary_id_is_not_authorization(monkeypatch, tmp_path):
    _contract, tool = load_modules()
    monkeypatch.setattr(tool, "_require_root", lambda: None)
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    with pytest.raises(tool.ProductionAuthorityError):
        tool.claim_phase("8" * 64, "HOST_BASELINE", {}, root=tmp_path, now=101)


def test_duplicate_claim_is_no_replay(monkeypatch, tmp_path):
    _contract, tool, plan = approve(monkeypatch, tmp_path)
    first = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=tmp_path,
        now=101,
    )
    assert first["replay_allowed"] is False
    with pytest.raises(tool.ProductionAuthorityError, match="phase_already_claimed"):
        tool.claim_phase(
            plan["run_id"],
            "HOST_BASELINE",
            binding(plan),
            root=tmp_path,
            now=102,
        )


def test_context_requires_exact_applying_claim(monkeypatch, tmp_path):
    _contract, tool, plan = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=tmp_path,
        now=101,
    )
    applying = tool.begin_phase(
        plan["run_id"],
        "HOST_BASELINE",
        claimed["claim_sha256"],
        root=tmp_path,
    )
    context = tool.phase_context(plan["run_id"], "HOST_BASELINE", root=tmp_path)
    assert context["claim_sha256"] == applying["claim_sha256"]
    assert tool.validate_phase_context(
        context,
        required_phase="HOST_BASELINE",
        root=tmp_path,
    )["status"] == "PASS"


def test_unknown_is_terminal_and_not_reusable(monkeypatch, tmp_path):
    _contract, tool, plan = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=tmp_path,
        now=101,
    )
    applying = tool.begin_phase(
        plan["run_id"],
        "HOST_BASELINE",
        claimed["claim_sha256"],
        root=tmp_path,
    )
    failed = tool.fail_phase(
        plan["run_id"],
        "HOST_BASELINE",
        applying["claim_sha256"],
        state="UNKNOWN",
        failure_code="lost_reply",
        root=tmp_path,
    )
    assert failed["replay_allowed"] is False
    with pytest.raises(tool.ProductionAuthorityError):
        tool.claim_phase(
            plan["run_id"],
            "F3_DEPLOY",
            binding(plan),
            root=tmp_path,
            now=103,
        )
