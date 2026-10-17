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
        "preflight_sha256": "7" * 64,
        "phase_artifact_sha256": {
            phase: f"{index:064x}"
            for index, phase in enumerate(contract.PHASES, 1)
        },
        "plan_digest": "0" * 64,
        "approved_at": 100,
        "expires_at": 500,
        "max_duration_seconds": 400,
        "phases": list(contract.PHASES),
        "reboot_budget": 1,
    }
    plan["plan_digest"] = contract.canonical_sha256(plan)
    return plan


def binding(plan, predecessor=None, phase="HOST_BASELINE"):
    return {
        "source_head": plan["source_head"],
        "release_id": plan["release_id"],
        "artifact_sha256": plan["phase_artifact_sha256"][phase],
        "predecessor_sha256": predecessor,
        "target_binding_sha256": plan["target_binding_sha256"],
    }


def approve(monkeypatch, tmp_path):
    contract, tool = load_modules()
    monkeypatch.setattr(tool, "_require_root", lambda: None)
    ledger = tmp_path / "ledger"
    plan = make_plan(contract)
    tool.approve_run(
        plan,
        root=ledger,
        now=100,
        identity={
            "target_binding_sha256": plan["target_binding_sha256"],
            "ssh_host_key_sha256": plan["ssh_host_key_sha256"],
        },
    )
    return contract, tool, plan, ledger


def test_arbitrary_id_is_not_authorization(monkeypatch, tmp_path):
    _contract, tool = load_modules()
    monkeypatch.setattr(tool, "_require_root", lambda: None)
    with pytest.raises(tool.ProductionAuthorityError):
        tool.claim_phase(
            "8" * 64,
            "HOST_BASELINE",
            {},
            root=tmp_path / "ledger",
            now=101,
        )


def test_duplicate_claim_is_no_replay(monkeypatch, tmp_path):
    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    first = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=ledger,
        now=101,
    )
    assert first["replay_allowed"] is False
    with pytest.raises(tool.ProductionAuthorityError, match="phase_already_claimed"):
        tool.claim_phase(
            plan["run_id"],
            "HOST_BASELINE",
            binding(plan),
            root=ledger,
            now=102,
        )


def test_context_requires_exact_applying_claim(monkeypatch, tmp_path):
    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=ledger,
        now=101,
    )
    applying = tool.begin_phase(
        plan["run_id"],
        "HOST_BASELINE",
        claimed["claim_sha256"],
        root=ledger,
    )
    context = tool.phase_context(plan["run_id"], "HOST_BASELINE", root=ledger)
    assert context["claim_sha256"] == applying["claim_sha256"]
    assert tool.validate_phase_context(
        context,
        required_phase="HOST_BASELINE",
        root=ledger,
    )["status"] == "PASS"


def test_unknown_is_terminal_and_not_reusable(monkeypatch, tmp_path):
    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=ledger,
        now=101,
    )
    applying = tool.begin_phase(
        plan["run_id"],
        "HOST_BASELINE",
        claimed["claim_sha256"],
        root=ledger,
    )
    failed = tool.fail_phase(
        plan["run_id"],
        "HOST_BASELINE",
        applying["claim_sha256"],
        state="UNKNOWN",
        failure_code="lost_reply",
        root=ledger,
    )
    assert failed["replay_allowed"] is False
    with pytest.raises(tool.ProductionAuthorityError):
        tool.claim_phase(
            plan["run_id"],
            "F3_DEPLOY",
            binding(plan),
            root=ledger,
            now=103,
        )


def test_phase_rejects_valid_sha_not_bound_to_approved_release(
    monkeypatch,
    tmp_path,
):
    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    wrong = binding(plan)
    wrong["artifact_sha256"] = "f" * 64
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="phase_artifact_binding_mismatch",
    ):
        tool.claim_phase(
            plan["run_id"],
            "HOST_BASELINE",
            wrong,
            root=ledger,
            now=101,
        )


def test_duplicate_json_key_is_rejected(monkeypatch, tmp_path):
    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    run_path = ledger / plan["run_id"] / "run.json"
    raw = run_path.read_text(encoding="utf-8").strip()
    run_path.write_text(raw[:-1] + ',"state":"APPROVED"}\n', encoding="utf-8")
    run_path.chmod(0o600)
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="authority_record_duplicate_key",
    ):
        tool.inspect_run(plan["run_id"], root=ledger)


def test_unknown_run_field_is_rejected(monkeypatch, tmp_path):
    import json

    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    run_path = ledger / plan["run_id"] / "run.json"
    document = json.loads(run_path.read_text(encoding="utf-8"))
    document["unexpected"] = True
    run_path.write_text(json.dumps(document), encoding="utf-8")
    run_path.chmod(0o600)
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="run_record_fields_invalid",
    ):
        tool.inspect_run(plan["run_id"], root=ledger)


def test_unknown_phase_field_is_rejected(monkeypatch, tmp_path):
    import json

    _contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=ledger,
        now=101,
    )
    phase_path = ledger / plan["run_id"] / "phase-HOST_BASELINE.json"
    document = json.loads(phase_path.read_text(encoding="utf-8"))
    document["unexpected"] = True
    phase_path.write_text(json.dumps(document), encoding="utf-8")
    phase_path.chmod(0o600)
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="phase_record_fields_invalid",
    ):
        tool.begin_phase(
            plan["run_id"],
            "HOST_BASELINE",
            tool._sha256_file(phase_path),
            root=ledger,
        )


def test_unknown_prior_run_blocks_new_run_id(monkeypatch, tmp_path):
    contract, tool, plan, ledger = approve(monkeypatch, tmp_path)
    claimed = tool.claim_phase(
        plan["run_id"],
        "HOST_BASELINE",
        binding(plan),
        root=ledger,
        now=101,
    )
    applying = tool.begin_phase(
        plan["run_id"],
        "HOST_BASELINE",
        claimed["claim_sha256"],
        root=ledger,
    )
    tool.fail_phase(
        plan["run_id"],
        "HOST_BASELINE",
        applying["claim_sha256"],
        state="UNKNOWN",
        failure_code="lost_reply",
        root=ledger,
    )
    second = make_plan(contract)
    second["run_id"] = "8" * 64
    second["plan_digest"] = "0" * 64
    second["plan_digest"] = contract.canonical_sha256(second)
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="existing_unknown_run_blocks_approval",
    ):
        tool.approve_run(
            second,
            root=ledger,
            now=100,
            identity={
                "target_binding_sha256": second["target_binding_sha256"],
                "ssh_host_key_sha256": second["ssh_host_key_sha256"],
            },
        )


def test_active_prior_run_blocks_new_run_id(monkeypatch, tmp_path):
    contract, tool, _plan, ledger = approve(monkeypatch, tmp_path)
    second = make_plan(contract)
    second["run_id"] = "8" * 64
    second["plan_digest"] = "0" * 64
    second["plan_digest"] = contract.canonical_sha256(second)
    with pytest.raises(
        tool.ProductionAuthorityError,
        match="existing_active_run_blocks_approval",
    ):
        tool.approve_run(
            second,
            root=ledger,
            now=100,
            identity={
                "target_binding_sha256": second["target_binding_sha256"],
                "ssh_host_key_sha256": second["ssh_host_key_sha256"],
            },
        )
