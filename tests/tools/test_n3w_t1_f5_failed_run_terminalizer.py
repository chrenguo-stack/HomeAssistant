from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tools/n3w_t1_production_contract.py"
AUTHORITY = ROOT / "tools/n3w_t1_production_authority.py"
TOOL = ROOT / "tools/n3w_t1_f5_failed_run_terminalizer.py"
AUTHORIZATION_ID = "N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01"


def load_modules():
    contract_spec = importlib.util.spec_from_file_location(
        "n3w_t1_production_contract",
        CONTRACT,
    )
    assert contract_spec is not None and contract_spec.loader is not None
    contract = importlib.util.module_from_spec(contract_spec)
    sys.modules["n3w_t1_production_contract"] = contract
    contract_spec.loader.exec_module(contract)

    authority_spec = importlib.util.spec_from_file_location(
        "n3w_t1_production_authority",
        AUTHORITY,
    )
    assert authority_spec is not None and authority_spec.loader is not None
    authority = importlib.util.module_from_spec(authority_spec)
    sys.modules["n3w_t1_production_authority"] = authority
    authority_spec.loader.exec_module(authority)

    tool_spec = importlib.util.spec_from_file_location(
        "n3w_t1_f5_failed_run_terminalizer_test",
        TOOL,
    )
    assert tool_spec is not None and tool_spec.loader is not None
    tool = importlib.util.module_from_spec(tool_spec)
    sys.modules["n3w_t1_f5_failed_run_terminalizer_test"] = tool
    tool_spec.loader.exec_module(tool)
    return contract, authority, tool


def exact_identity(tool):
    return {
        "target_binding_sha256": tool.TARGET_BINDING_SHA256,
        "ssh_host_key_sha256": tool.SSH_HOST_KEY_SHA256,
    }


def make_plan(contract, tool):
    plan = {
        "schema": contract.PLAN_SCHEMA,
        "run_id": tool.RUN_ID,
        "release_id": tool.RELEASE_ID,
        "release_sha256": tool.RELEASE_SHA256,
        "source_head": tool.SOURCE_HEAD,
        "target_binding_sha256": tool.TARGET_BINDING_SHA256,
        "ssh_host_key_sha256": tool.SSH_HOST_KEY_SHA256,
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


def create_failed_prestate(monkeypatch, tmp_path):
    contract, authority, tool = load_modules()
    monkeypatch.setattr(authority, "_require_root", lambda: None)
    ledger = tmp_path / "production-ledger"
    baseline = tmp_path / "baseline-ledger"
    recovery = tmp_path / "recovery-ledger"
    plan = make_plan(contract, tool)
    authority.approve_run(
        plan,
        root=ledger,
        now=100,
        identity=exact_identity(tool),
    )
    binding = {
        "source_head": tool.SOURCE_HEAD,
        "release_id": tool.RELEASE_ID,
        "artifact_sha256": plan["phase_artifact_sha256"][tool.PHASE],
        "predecessor_sha256": None,
        "target_binding_sha256": tool.TARGET_BINDING_SHA256,
    }
    claimed = authority.claim_phase(
        tool.RUN_ID,
        tool.PHASE,
        binding,
        root=ledger,
        now=101,
    )
    applying = authority.begin_phase(
        tool.RUN_ID,
        tool.PHASE,
        claimed["claim_sha256"],
        root=ledger,
    )
    return authority, tool, ledger, baseline, recovery, applying["claim_sha256"]


def terminalize(tool, ledger, baseline, recovery, expected):
    return tool.terminalize_failed_run(
        expected_claim_sha256=expected,
        confirmation=tool.CONFIRMATION,
        authorization_id=AUTHORIZATION_ID,
        ledger_root=ledger,
        baseline_root=baseline,
        recovery_root=recovery,
        identity=exact_identity(tool),
    )


def test_inspect_accepts_exact_applying_prestate(monkeypatch, tmp_path):
    _authority, tool, ledger, baseline, _recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    report = tool.inspect_failed_run(
        ledger_root=ledger,
        baseline_root=baseline,
        identity=exact_identity(tool),
    )
    assert report["status"] == "PASS"
    assert report["state"] == "ELIGIBLE_FOR_TERMINALIZATION"
    assert report["phase_claim_sha256"] == expected
    assert report["mutation_performed"] is False
    assert report["mutation_state"] == "NONE"
    assert report["replay_allowed"] is False


def test_inspect_rejects_business_execution_claim(monkeypatch, tmp_path):
    _authority, tool, ledger, baseline, _recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    claim, _complete = tool._baseline_paths(expected, baseline)
    claim.parent.mkdir(parents=True)
    claim.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        tool.FailedRunTerminalizationError,
        match="host_baseline_business_execution_present",
    ):
        tool.inspect_failed_run(
            ledger_root=ledger,
            baseline_root=baseline,
            identity=exact_identity(tool),
        )


def test_terminalize_closes_only_authority_and_recovery_ledgers(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    report = terminalize(tool, ledger, baseline, recovery, expected)
    assert report["status"] == "PASS"
    assert report["state"] == "FAILED_RUN_TERMINALIZED"
    assert (
        report["mutation_scope"]
        == "f5_production_authority_and_recovery_ledger_only"
    )
    assert report["recovery_state"] == "TERMINALIZED"
    assert report["product_service_start"] is False
    assert report["reboot_executed"] is False
    inspected = authority.inspect_run(tool.RUN_ID, root=ledger)
    assert inspected["state"] == "TERMINAL"
    assert inspected["terminal_state"] == "FAIL"
    assert inspected["replay_allowed"] is False
    recovery_record = tool._read_recovery(tool._recovery_path(recovery))
    assert recovery_record["state"] == "TERMINALIZED"
    assert recovery_record["authorization_id"] == AUTHORIZATION_ID


def test_terminalize_rejects_wrong_claim_before_recovery_claim(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, baseline, recovery, _expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    with pytest.raises(
        tool.FailedRunTerminalizationError,
        match="phase_claim_sha256_drift",
    ):
        tool.terminalize_failed_run(
            expected_claim_sha256="f" * 64,
            confirmation=tool.CONFIRMATION,
            authorization_id=AUTHORIZATION_ID,
            ledger_root=ledger,
            baseline_root=baseline,
            recovery_root=recovery,
            identity=exact_identity(tool),
        )
    assert not recovery.exists()


def test_terminalize_requires_exact_confirmation(monkeypatch, tmp_path):
    _authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    with pytest.raises(
        tool.FailedRunTerminalizationError,
        match="terminalization_confirmation_invalid",
    ):
        tool.terminalize_failed_run(
            expected_claim_sha256=expected,
            confirmation="YES",
            authorization_id=AUTHORIZATION_ID,
            ledger_root=ledger,
            baseline_root=baseline,
            recovery_root=recovery,
            identity=exact_identity(tool),
        )
    assert not recovery.exists()


def test_partial_phase_failure_resumes_same_authorization(monkeypatch, tmp_path):
    authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    record = tool._claim_or_load_recovery(
        recovery_root=recovery,
        authorization_id=AUTHORIZATION_ID,
        expected_claim_sha256=expected,
    )
    record = tool._set_recovery_state(
        record,
        recovery_root=recovery,
        state="APPLYING",
    )
    assert record["state"] == "APPLYING"

    with authority._exclusive(ledger, tool.RUN_ID):
        phase_path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
        phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
        phase["state"] = "FAILED"
        phase["failure_code"] = tool.FAILURE_CODE
        authority._replace(phase_path, phase)

    run = authority._load_run(ledger, tool.RUN_ID)
    assert run["state"] == "IN_PROGRESS"

    report = terminalize(tool, ledger, baseline, recovery, expected)
    assert report["status"] == "PASS"
    assert report["target_run_state"] == "TERMINAL"
    assert report["recovery_state"] == "TERMINALIZED"


def test_existing_recovery_error_reports_recovery_present(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    tool._claim_or_load_recovery(
        recovery_root=recovery,
        authorization_id=AUTHORIZATION_ID,
        expected_claim_sha256=expected,
    )
    claim, _complete = tool._baseline_paths(expected, baseline)
    claim.parent.mkdir(parents=True)
    claim.write_text("{}\n", encoding="utf-8")
    with pytest.raises(tool.FailedRunTerminalizationError) as caught:
        terminalize(tool, ledger, baseline, recovery, expected)
    assert str(caught.value) == "host_baseline_business_execution_present"
    assert caught.value.mutation_state == "RECOVERY_PRESENT"


def test_recovery_authorization_cannot_be_rebound(monkeypatch, tmp_path):
    _authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    terminalize(tool, ledger, baseline, recovery, expected)
    with pytest.raises(
        tool.FailedRunTerminalizationError,
        match="recovery_authorization_binding_mismatch",
    ):
        tool.terminalize_failed_run(
            expected_claim_sha256=expected,
            confirmation=tool.CONFIRMATION,
            authorization_id=(
                "N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_02"
            ),
            ledger_root=ledger,
            baseline_root=baseline,
            recovery_root=recovery,
            identity=exact_identity(tool),
        )


def test_terminalized_run_cannot_be_replayed(monkeypatch, tmp_path):
    authority, tool, ledger, baseline, recovery, expected = (
        create_failed_prestate(monkeypatch, tmp_path)
    )
    terminalize(tool, ledger, baseline, recovery, expected)
    with pytest.raises(authority.ProductionAuthorityError):
        authority.claim_phase(
            tool.RUN_ID,
            "F3_DEPLOY",
            {},
            root=ledger,
            now=103,
        )
