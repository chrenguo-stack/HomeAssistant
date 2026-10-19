from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tools/n3w_t1_production_contract.py"
AUTHORITY = ROOT / "tools/n3w_t1_production_authority.py"
TOOL = ROOT / "tools/n3w_t1_f5_unknown_run_adjudicator.py"
AUTHORIZATION_ID = (
    "N3W_T1_F5_KF123_UNKNOWN_RUN_ADJUDICATION_LIVE_20261019_01"
)
OTHER_AUTHORIZATION_ID = (
    "N3W_T1_F5_KF123_UNKNOWN_RUN_ADJUDICATION_LIVE_20261019_02"
)


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
        "n3w_t1_f5_unknown_run_adjudicator_test",
        TOOL,
    )
    assert tool_spec is not None and tool_spec.loader is not None
    tool = importlib.util.module_from_spec(tool_spec)
    sys.modules["n3w_t1_f5_unknown_run_adjudicator_test"] = tool
    tool_spec.loader.exec_module(tool)
    return contract, authority, tool


def runtime_clean():
    return {
        "container_count": 0,
        "image_count": 0,
        "volume_count": 0,
        "product_network_count": 0,
        "product_path_count": 0,
        "product_unit_loaded_count": 0,
        "remote_f3_staging_count": 0,
        "docker_active": True,
    }


def make_plan(contract, tool):
    plan = {
        "schema": contract.PLAN_SCHEMA,
        "run_id": tool.RUN_ID,
        "release_id": tool.RELEASE_ID,
        "release_sha256": tool.RELEASE_SHA256,
        "source_head": tool.SOURCE_HEAD,
        "target_binding_sha256": "2" * 64,
        "ssh_host_key_sha256": "3" * 64,
        "preflight_sha256": "4" * 64,
        "phase_artifact_sha256": {
            phase: f"{index:064x}"
            for index, phase in enumerate(contract.PHASES, 1)
        },
        "plan_digest": "0" * 64,
        "approved_at": 100,
        "expires_at": 1000,
        "max_duration_seconds": 900,
        "phases": list(contract.PHASES),
        "reboot_budget": 1,
    }
    plan["plan_digest"] = contract.canonical_sha256(plan)
    return plan


def exact_identity(plan):
    return {
        "target_binding_sha256": plan["target_binding_sha256"],
        "ssh_host_key_sha256": plan["ssh_host_key_sha256"],
    }


def create_incident(monkeypatch, tmp_path):
    contract, authority, tool = load_modules()
    monkeypatch.setattr(authority, "_require_root", lambda: None)
    ledger = tmp_path / "production-ledger"
    execution = tmp_path / "f3-execution-ledger"
    recovery = tmp_path / "recovery-ledger"
    plan = make_plan(contract, tool)
    identity = exact_identity(plan)

    authority.approve_run(
        plan,
        root=ledger,
        now=100,
        identity=identity,
    )

    host_binding = {
        "source_head": tool.SOURCE_HEAD,
        "release_id": tool.RELEASE_ID,
        "artifact_sha256": plan["phase_artifact_sha256"]["HOST_BASELINE"],
        "predecessor_sha256": None,
        "target_binding_sha256": plan["target_binding_sha256"],
    }
    host_claim = authority.claim_phase(
        tool.RUN_ID,
        "HOST_BASELINE",
        host_binding,
        root=ledger,
        now=101,
    )
    host_apply = authority.begin_phase(
        tool.RUN_ID,
        "HOST_BASELINE",
        host_claim["claim_sha256"],
        root=ledger,
    )
    authority.complete_phase(
        tool.RUN_ID,
        "HOST_BASELINE",
        host_apply["claim_sha256"],
        tool.HOST_BASELINE_RESULT_SHA256,
        root=ledger,
    )

    host_phase_path = authority._phase_path(
        ledger,
        tool.RUN_ID,
        "HOST_BASELINE",
    )
    host_predecessor = authority._sha256_file(host_phase_path)
    f3_binding = {
        "source_head": tool.SOURCE_HEAD,
        "release_id": tool.RELEASE_ID,
        "artifact_sha256": plan["phase_artifact_sha256"]["F3_DEPLOY"],
        "predecessor_sha256": host_predecessor,
        "target_binding_sha256": plan["target_binding_sha256"],
    }
    f3_claim = authority.claim_phase(
        tool.RUN_ID,
        "F3_DEPLOY",
        f3_binding,
        root=ledger,
        now=102,
    )
    f3_apply = authority.begin_phase(
        tool.RUN_ID,
        "F3_DEPLOY",
        f3_claim["claim_sha256"],
        root=ledger,
    )
    authority.fail_phase(
        tool.RUN_ID,
        "F3_DEPLOY",
        f3_apply["claim_sha256"],
        state="UNKNOWN",
        failure_code=tool.F3_FAILURE_CODE,
        root=ledger,
    )

    return authority, tool, ledger, execution, recovery, identity


def inspect(tool, ledger, execution, recovery, identity):
    return tool.inspect_unknown_run(
        ledger_root=ledger,
        execution_root=execution,
        recovery_root=recovery,
        identity=identity,
        runtime_state=runtime_clean(),
    )


def adjudicate(
    tool,
    ledger,
    execution,
    recovery,
    identity,
    preflight,
    *,
    authorization_id=AUTHORIZATION_ID,
):
    return tool.adjudicate_unknown_run(
        expected_run_sha256=preflight["run_record_sha256"],
        expected_phase_sha256=preflight["phase_record_sha256"],
        authorization_id=authorization_id,
        confirmation=tool.CONFIRMATION,
        ledger_root=ledger,
        execution_root=execution,
        recovery_root=recovery,
        identity=identity,
        runtime_state=runtime_clean(),
    )


def test_inspect_accepts_exact_terminal_unknown_prestate(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    report = inspect(tool, ledger, execution, recovery, identity)
    assert report["status"] == "PASS"
    assert report["state"] == "ELIGIBLE_FOR_ADJUDICATION"
    assert report["f3_production_execution_record_count"] == 0
    assert report["recovery_root_absent"] is True
    assert report["mutation_performed"] is False
    assert report["mutation_state"] == "NONE"


def test_inspect_rejects_business_execution_record(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    execution.mkdir(mode=0o700)
    (execution / "record.json").write_text(
        (
            '{"run_id":"'
            + tool.RUN_ID
            + '","phase":"F3_DEPLOY"}\n'
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_business_execution_present",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_product_material(monkeypatch, tmp_path):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    state = runtime_clean()
    state["image_count"] = 1
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="product_material_present",
    ):
        tool.inspect_unknown_run(
            ledger_root=ledger,
            execution_root=execution,
            recovery_root=recovery,
            identity=identity,
            runtime_state=state,
        )


def test_inspect_rejects_changed_failure_code(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    phase["failure_code"] = "different"
    authority._replace(path, phase)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_wrong_hash_stops_before_recovery_claim(monkeypatch, tmp_path):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="run_record_sha256_drift",
    ):
        tool.adjudicate_unknown_run(
            expected_run_sha256="f" * 64,
            expected_phase_sha256=preflight["phase_record_sha256"],
            authorization_id=AUTHORIZATION_ID,
            confirmation=tool.CONFIRMATION,
            ledger_root=ledger,
            execution_root=execution,
            recovery_root=recovery,
            identity=identity,
            runtime_state=runtime_clean(),
        )
    assert not recovery.exists()


def test_exact_confirmation_required(monkeypatch, tmp_path):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="adjudication_confirmation_invalid",
    ):
        tool.adjudicate_unknown_run(
            expected_run_sha256=preflight["run_record_sha256"],
            expected_phase_sha256=preflight["phase_record_sha256"],
            authorization_id=AUTHORIZATION_ID,
            confirmation="YES",
            ledger_root=ledger,
            execution_root=execution,
            recovery_root=recovery,
            identity=identity,
            runtime_state=runtime_clean(),
        )
    assert not recovery.exists()


def test_adjudication_reclassifies_only_unknown_state(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    host_before = authority._load_phase(
        ledger,
        tool.RUN_ID,
        "HOST_BASELINE",
    )
    run_before = authority._load_run(ledger, tool.RUN_ID)
    plan_before = dict(run_before["plan"])

    report = adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )

    run = authority._load_run(ledger, tool.RUN_ID)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    host = authority._load_phase(
        ledger,
        tool.RUN_ID,
        "HOST_BASELINE",
    )
    assert report["status"] == "PASS"
    assert report["state"] == "UNKNOWN_RUN_ADJUDICATED"
    assert run["state"] == "TERMINAL"
    assert run["terminal_state"] == "FAIL"
    assert run["failure_class"] == "FAILED"
    assert run["last_completed_phase"] == "HOST_BASELINE"
    assert run["last_claimed_phase"] == "F3_DEPLOY"
    assert run["plan"] == plan_before
    assert phase["state"] == "FAILED"
    assert phase["failure_code"] == tool.F3_FAILURE_CODE
    assert phase["result_sha256"] is None
    assert host == host_before
    assert report["product_service_start"] is False
    assert report["reboot_executed"] is False
    assert report["board_access"] is False


def test_phase_split_state_resumes_same_authorization(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    original_replace = authority._replace
    run_path = authority._run_path(ledger, tool.RUN_ID)
    interrupted = {"done": False}

    def stop_on_run(path, document):
        if path == run_path and not interrupted["done"]:
            interrupted["done"] = True
            raise OSError("simulated-run-write-interruption")
        return original_replace(path, document)

    monkeypatch.setattr(authority, "_replace", stop_on_run)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="run_adjudication_persistence_unknown",
    ) as captured:
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )
    assert captured.value.mutation_state == "UNKNOWN"
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    run = authority._load_run(ledger, tool.RUN_ID)
    assert phase["state"] == "FAILED"
    assert run["failure_class"] == "UNKNOWN"

    monkeypatch.setattr(authority, "_replace", original_replace)
    report = adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )
    assert report["status"] == "PASS"
    assert authority._load_run(
        ledger,
        tool.RUN_ID,
    )["failure_class"] == "FAILED"


def test_different_authorization_cannot_resume(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    original_replace = authority._replace
    run_path = authority._run_path(ledger, tool.RUN_ID)

    def stop_on_run(path, document):
        if path == run_path:
            raise OSError("simulated-run-write-interruption")
        return original_replace(path, document)

    monkeypatch.setattr(authority, "_replace", stop_on_run)
    with pytest.raises(tool.UnknownRunAdjudicationError):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )

    monkeypatch.setattr(authority, "_replace", original_replace)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="recovery_authorization_binding_mismatch",
    ):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
            authorization_id=OTHER_AUTHORIZATION_ID,
        )


def test_run_split_state_resumes_to_adjudicated(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    original_set = tool._set_recovery_state
    interrupted = {"done": False}

    def stop_before_adjudicated(record, *, recovery_root, state):
        if state == "ADJUDICATED" and not interrupted["done"]:
            interrupted["done"] = True
            raise tool.UnknownRunAdjudicationError(
                "simulated-recovery-finalization-interruption",
                mutation_state="UNKNOWN",
            )
        return original_set(
            record,
            recovery_root=recovery_root,
            state=state,
        )

    monkeypatch.setattr(tool, "_set_recovery_state", stop_before_adjudicated)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="simulated-recovery-finalization-interruption",
    ):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )
    assert authority._load_phase(
        ledger,
        tool.RUN_ID,
        tool.PHASE,
    )["state"] == "FAILED"
    assert authority._load_run(
        ledger,
        tool.RUN_ID,
    )["failure_class"] == "FAILED"
    assert tool._read_recovery(
        tool._recovery_path(recovery)
    )["state"] == "APPLYING"

    monkeypatch.setattr(tool, "_set_recovery_state", original_set)
    report = adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )
    assert report["status"] == "PASS"
    assert tool._read_recovery(
        tool._recovery_path(recovery)
    )["state"] == "ADJUDICATED"


def test_repeated_adjudication_is_idempotent(monkeypatch, tmp_path):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    first = adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )
    second = adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )
    assert first["status"] == "PASS"
    assert second["status"] == "PASS"
    assert second["action"] == "ALREADY_ADJUDICATED"
    assert second["mutation_performed"] is False


def test_verify_is_read_only_after_adjudication(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    adjudicate(
        tool,
        ledger,
        execution,
        recovery,
        identity,
        preflight,
    )
    run_before = authority._sha256_file(
        authority._run_path(ledger, tool.RUN_ID)
    )
    phase_before = authority._sha256_file(
        authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    )
    recovery_before = authority._sha256_file(
        tool._recovery_path(recovery)
    )

    report = tool.verify_adjudicated_run(
        ledger_root=ledger,
        execution_root=execution,
        recovery_root=recovery,
        identity=identity,
        runtime_state=runtime_clean(),
    )

    assert report["status"] == "PASS"
    assert report["state"] == "ADJUDICATED_READONLY_VERIFIED"
    assert report["mutation_performed"] is False
    assert authority._sha256_file(
        authority._run_path(ledger, tool.RUN_ID)
    ) == run_before
    assert authority._sha256_file(
        authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    ) == phase_before
    assert authority._sha256_file(
        tool._recovery_path(recovery)
    ) == recovery_before
