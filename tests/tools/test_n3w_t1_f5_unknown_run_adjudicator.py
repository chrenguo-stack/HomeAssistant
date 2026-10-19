from __future__ import annotations

import hashlib
import importlib.util
import json
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


def write_execution_record(
    execution: Path,
    tool,
    *,
    run_id: str | None = None,
    schema: str | None = None,
    wrong_filename: bool = False,
) -> Path:
    execution.mkdir(mode=0o700, exist_ok=True)
    execution.chmod(0o700)
    record = {
        "schema": schema or tool.PRODUCTION_EXECUTION_SCHEMA,
        "run_id": run_id or tool.RUN_ID,
        "phase": tool.PHASE,
        "phase_claim_sha256": "a" * 64,
        "plan_sha256": "b" * 64,
        "source_head": tool.SOURCE_HEAD,
        "payload_manifest_sha256": "c" * 64,
        "release_id": tool.RELEASE_ID,
        "phase_artifact_sha256": "d" * 64,
        "target_binding_sha256": "e" * 64,
        "state": "APPLYING",
        "result_sha256": None,
        "authorization_consumed": True,
        "replay_allowed": False,
    }
    digest = hashlib.sha256(
        (
            record["run_id"]
            + "\n"
            + record["phase"]
            + "\n"
            + record["phase_claim_sha256"]
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    if wrong_filename:
        digest = "0" * 64 if digest != "0" * 64 else "1" * 64
    path = execution / (digest + ".json")
    path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


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
    write_execution_record(execution, tool)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_business_execution_present",
    ):
        inspect(tool, ledger, execution, recovery, identity)



def test_inspect_rejects_schema_invalid_execution_record(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    write_execution_record(
        execution,
        tool,
        schema="gh.n3w-t1-fresh-production-execution/bad",
    )
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_execution_ledger_invalid",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_duplicate_key_execution_record(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = write_execution_record(execution, tool)
    document = json.loads(path.read_text(encoding="utf-8"))
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
    raw = raw[:-1] + ',"run_id":"' + tool.RUN_ID + '"}\n'
    path.write_text(raw, encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_execution_ledger_invalid",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_execution_ledger_metadata_drift(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    write_execution_record(execution, tool)
    execution.chmod(0o755)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_execution_ledger_invalid",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_wrong_execution_record_filename(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    write_execution_record(
        execution,
        tool,
        run_id="6" * 64,
        wrong_filename=True,
    )
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="f3_execution_record_filename_binding_invalid",
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



def test_inspect_rejects_nonterminal_run(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._run_path(ledger, tool.RUN_ID)
    run = authority._load_run(ledger, tool.RUN_ID)
    run["state"] = "IN_PROGRESS"
    run["terminal_state"] = None
    run["failure_class"] = None
    authority._replace(path, run)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_pass_run(monkeypatch, tmp_path):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._run_path(ledger, tool.RUN_ID)
    run = authority._load_run(ledger, tool.RUN_ID)
    run["terminal_state"] = "PASS"
    run["failure_class"] = None
    authority._replace(path, run)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_failed_run_without_recovery(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    run_path = authority._run_path(ledger, tool.RUN_ID)
    phase_path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    run = authority._load_run(ledger, tool.RUN_ID)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    run["failure_class"] = "FAILED"
    phase["state"] = "FAILED"
    authority._replace(run_path, run)
    authority._replace(phase_path, phase)
    assert not recovery.exists()
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_host_artifact_binding_drift(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._phase_path(ledger, tool.RUN_ID, "HOST_BASELINE")
    phase = authority._load_phase(ledger, tool.RUN_ID, "HOST_BASELINE")
    phase["binding"]["artifact_sha256"] = "9" * 64
    phase["binding_sha256"] = authority.canonical_sha256(phase["binding"])
    authority._replace(path, phase)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_f3_artifact_binding_drift(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    phase["binding"]["artifact_sha256"] = "8" * 64
    phase["binding_sha256"] = authority.canonical_sha256(phase["binding"])
    authority._replace(path, phase)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_f3_predecessor_binding_drift(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    phase["binding"]["predecessor_sha256"] = "7" * 64
    phase["binding_sha256"] = authority.canonical_sha256(phase["binding"])
    authority._replace(path, phase)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="unknown_run_prestate_mismatch",
    ):
        inspect(tool, ledger, execution, recovery, identity)


def test_inspect_rejects_same_second_later_target_run(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    incident = authority._load_run(ledger, tool.RUN_ID)
    other_id = "6" * 64
    other_plan = dict(incident["plan"])
    other_plan["run_id"] = other_id
    other_plan["plan_digest"] = "0" * 64
    other_plan["plan_digest"] = authority.canonical_sha256(other_plan)
    other = dict(incident)
    other["run_id"] = other_id
    other["plan"] = other_plan
    other["plan_sha256"] = authority.canonical_sha256(other_plan)
    other_dir = authority._run_dir(ledger, other_id)
    other_dir.mkdir(mode=0o700)
    other_dir.chmod(0o700)
    authority._write_new(authority._run_path(ledger, other_id), other)

    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="later_target_run_present",
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


def test_phase_split_state_rejects_preserved_run_drift(
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
    run = authority._load_run(ledger, tool.RUN_ID)
    run["created_at"] += 1
    authority._replace(run_path, run)

    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="historical_record_invariant_drift",
    ):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )


def test_resume_rejects_recovery_root_metadata_drift(
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
    recovery.chmod(0o755)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="recovery_root_metadata_invalid",
    ):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )


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


def test_adjudicated_state_rejects_preserved_phase_drift(
    monkeypatch,
    tmp_path,
):
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
    phase_path = authority._phase_path(ledger, tool.RUN_ID, tool.PHASE)
    phase = authority._load_phase(ledger, tool.RUN_ID, tool.PHASE)
    phase["claimed_at"] += 1
    authority._replace(phase_path, phase)

    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="historical_record_invariant_drift",
    ):
        adjudicate(
            tool,
            ledger,
            execution,
            recovery,
            identity,
            preflight,
        )


def test_verify_rejects_recovery_root_symlink(
    monkeypatch,
    tmp_path,
):
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
    real_recovery = tmp_path / "recovery-real"
    recovery.rename(real_recovery)
    recovery.symlink_to(real_recovery, target_is_directory=True)

    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="recovery_root_invalid",
    ):
        tool.verify_adjudicated_run(
            ledger_root=ledger,
            execution_root=execution,
            recovery_root=recovery,
            identity=identity,
            runtime_state=runtime_clean(),
        )


def test_verify_rejects_duplicate_key_recovery_record(
    monkeypatch,
    tmp_path,
):
    _authority, tool, ledger, execution, recovery, identity = create_incident(
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
    path = tool._recovery_path(recovery)
    document = json.loads(path.read_text(encoding="utf-8"))
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
    raw = raw[:-1] + ',"authorization_id":"' + AUTHORIZATION_ID + '"}\n'
    path.write_text(raw, encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="recovery_record_invalid",
    ):
        tool.verify_adjudicated_run(
            ledger_root=ledger,
            execution_root=execution,
            recovery_root=recovery,
            identity=identity,
            runtime_state=runtime_clean(),
        )


def test_claim_rechecks_hash_after_inspect_before_recovery_write(
    monkeypatch,
    tmp_path,
):
    authority, tool, ledger, execution, recovery, identity = create_incident(
        monkeypatch,
        tmp_path,
    )
    preflight = inspect(tool, ledger, execution, recovery, identity)
    original_inspect = tool.inspect_unknown_run
    run_path = authority._run_path(ledger, tool.RUN_ID)

    def drifting_inspect(**kwargs):
        report = original_inspect(**kwargs)
        run = authority._load_run(ledger, tool.RUN_ID)
        run["updated_at"] += 1
        authority._replace(run_path, run)
        return report

    monkeypatch.setattr(tool, "inspect_unknown_run", drifting_inspect)
    with pytest.raises(
        tool.UnknownRunAdjudicationError,
        match="run_record_sha256_drift",
    ):
        tool.adjudicate_unknown_run(
            expected_run_sha256=preflight["run_record_sha256"],
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
