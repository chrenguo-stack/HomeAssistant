from __future__ import annotations

import importlib.util
import json
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production.py"
CONTRACT = ROOT / "tools/n3w_t1_production_contract.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_tool():
    _load(CONTRACT, "n3w_t1_production_contract")
    return _load(TOOL, "n3w_t1_production")


def release(tool):
    contract = sys.modules["n3w_t1_production_contract"]
    value = {
        "schema": contract.RELEASE_SCHEMA,
        "release_id": "0" * 64,
        "source_head": "a" * 40,
        "artifacts": {
            name: {"sha256": f"{index:064x}"}
            for index, name in enumerate(contract.REQUIRED_ARTIFACT_NAMES, 1)
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
            "schema": contract.CHECK_POLICY_SCHEMA,
            "allow_overrides": [],
        },
        "result_schema": contract.RESULT_SCHEMA,
    }
    value["release_id"] = contract.canonical_sha256(
        {key: item for key, item in value.items() if key != "release_id"}
    )
    return value


class FakeBackend:
    def __init__(
        self,
        finalize_accepts=True,
        close_ok=True,
        target_close_ok=True,
    ):
        self.finalize_accepts = finalize_accepts
        self.close_ok = close_ok
        self.target_close_ok = target_close_ok
        self.approvals = 0
        self.epochs = 0
        self.reboots = 0
        self.phases = []
        self.preflights = 0
        self.approval_record_path = None

    def connect_pre_reboot(self):
        self.epochs += 1
        return {"status": "PASS"}

    def target_identity(self):
        return {
            "target_binding_sha256": "b" * 64,
            "ssh_host_key_sha256": "c" * 64,
        }

    def preflight(self, *, release, identity):
        self.preflights += 1
        contract = sys.modules["n3w_t1_production_contract"]
        return {
            "status": "PASS",
            "read_only": True,
            "mutation_performed": False,
            "checks": {
                check_id: "PASS" for check_id in contract.PREFLIGHT_CHECK_IDS
            },
        }

    def approve_run(self, plan):
        if self.approval_record_path is not None:
            assert self.approval_record_path.is_file()
            approval = json.loads(self.approval_record_path.read_text())
            assert approval["state"] == "APPROVED_PENDING_TARGET_CLAIM"
            assert approval["plan"] == plan
        self.approvals += 1
        return {"status": "PASS"}

    def execute_phase(self, phase, *, plan, predecessor_sha256):
        self.phases.append(phase)
        report = {
            "status": "PASS",
            "phase": phase,
            "predecessor_sha256": predecessor_sha256,
            "override_check_ids": [],
        }
        if phase == "FINALIZE":
            report["device_acceptance"] = self.finalize_accepts
        if phase == "CLOSE_RUN":
            report.update(
                {
                    "target_run_terminal": self.target_close_ok,
                    "target_terminal_state": (
                        "PASS" if self.target_close_ok else None
                    ),
                    "device_acceptance": self.finalize_accepts,
                    "evidence_complete": self.target_close_ok,
                    "operator_session_closed_claimed": False,
                }
            )
        return report

    def transition_reboot(self):
        self.reboots += 1
        return {"status": "PASS"}

    def connect_post_reboot(self):
        self.epochs += 1
        return {"status": "PASS"}

    def close_session(self):
        return {
            "status": "PASS" if self.close_ok else "FAIL",
            "session_closed": self.close_ok,
        }


def run(tmp_path, tool, backend, approval=lambda _summary: True):
    private_path = tmp_path / "private.json"
    backend.approval_record_path = tool._approval_record_path(private_path)
    return tool.run_production(
        release(tool),
        release_sha256="d" * 64,
        backend=backend,
        approval=approval,
        private_record_path=private_path,
        public_record_path=tmp_path / "public.json",
        now=100,
        run_id="e" * 64,
    )


def test_full_run_has_one_approval_two_epochs_and_fixed_phases(tmp_path):
    tool = load_tool()
    backend = FakeBackend()
    result = run(tmp_path, tool, backend)
    assert result["status"] == "PASS"
    assert result["final_outcome"] == "PASS"
    assert backend.approvals == 1
    assert backend.preflights == 1
    assert backend.epochs == 2
    assert backend.reboots == 1
    assert backend.phases == list(tool.PHASES)
    public = json.loads((tmp_path / "public.json").read_text())
    assert "plan" not in public
    assert public["final_outcome"] == "PASS"


def test_declined_approval_stops_before_durable_approval(tmp_path):
    tool = load_tool()
    backend = FakeBackend()
    result = run(tmp_path, tool, backend, approval=lambda _summary: False)
    assert result["status"] == "FAIL"
    assert result["failure_code"] == "production_approval_declined"
    assert backend.approvals == 0
    assert backend.phases == []


def test_finalize_requires_device_acceptance(tmp_path):
    tool = load_tool()
    result = run(tmp_path, tool, FakeBackend(finalize_accepts=False))
    assert result["status"] == "FAIL"
    assert result["device_acceptance"] is False


def test_cleanup_failure_preserves_device_fact_but_fails_process(tmp_path):
    tool = load_tool()
    result = run(tmp_path, tool, FakeBackend(close_ok=False))
    assert result["device_acceptance"] is True
    assert result["operator_session_closed"] is False
    assert result["evidence_complete"] is True
    assert result["final_outcome"] == "FAIL"


def test_cli_has_no_repair_or_shell_surface():
    source = TOOL.read_text(encoding="utf-8")
    assert "repair-" not in source
    assert 'add_parser("run")' in source
    assert 'add_parser("inspect")' in source
    assert 'add_parser("verify")' in source


def test_approval_record_is_durable_before_target_approval(tmp_path):
    tool = load_tool()
    backend = FakeBackend()
    result = run(tmp_path, tool, backend)
    approval_path = tool._approval_record_path(tmp_path / "private.json")
    approval = json.loads(approval_path.read_text())
    assert result["approval_record_sha256"] == tool._sha256_file(approval_path)
    assert approval["state"] == "APPROVED_PENDING_TARGET_CLAIM"
    assert backend.approvals == 1


def test_prompt_displays_plan_before_reading_confirmation(monkeypatch, capsys):
    tool = load_tool()
    observed = {}

    def fake_input(prompt):
        observed["output_before_input"] = capsys.readouterr().out
        observed["prompt"] = prompt
        return "START PRODUCTION RUN"

    monkeypatch.setattr("builtins.input", fake_input)
    assert tool.prompt_for_approval("PLAN SUMMARY") is True
    assert "PLAN SUMMARY" in observed["output_before_input"]
    assert "START PRODUCTION RUN" in observed["prompt"]


def test_public_result_is_not_written_if_private_write_fails(tmp_path, monkeypatch):
    tool = load_tool()
    backend = FakeBackend()
    private_path = tmp_path / "private.json"
    public_path = tmp_path / "public.json"
    backend.approval_record_path = tool._approval_record_path(private_path)
    original = tool._atomic_new_json

    def fail_private(path, document, mode=0o600):
        if path == private_path:
            raise OSError("injected_private_write_failure")
        return original(path, document, mode)

    monkeypatch.setattr(tool, "_atomic_new_json", fail_private)
    with pytest.raises(tool.ProductionError, match="evidence_write_failed"):
        tool.run_production(
            release(tool),
            release_sha256="d" * 64,
            backend=backend,
            approval=lambda _summary: True,
            private_record_path=private_path,
            public_record_path=public_path,
            now=100,
            run_id="e" * 64,
        )
    assert not private_path.exists()
    assert not public_path.exists()
    assert not tool._evidence_seal_path(private_path).exists()


def test_public_write_failure_cannot_leave_false_public_pass(tmp_path, monkeypatch):
    tool = load_tool()
    backend = FakeBackend()
    private_path = tmp_path / "private.json"
    public_path = tmp_path / "public.json"
    backend.approval_record_path = tool._approval_record_path(private_path)
    original = tool._atomic_new_json

    def fail_public(path, document, mode=0o600):
        if path == public_path:
            raise OSError("injected_public_write_failure")
        return original(path, document, mode)

    monkeypatch.setattr(tool, "_atomic_new_json", fail_public)
    with pytest.raises(tool.ProductionError, match="evidence_write_failed"):
        tool.run_production(
            release(tool),
            release_sha256="d" * 64,
            backend=backend,
            approval=lambda _summary: True,
            private_record_path=private_path,
            public_record_path=public_path,
            now=100,
            run_id="e" * 64,
        )
    assert private_path.is_file()
    assert not public_path.exists()
    assert not tool._evidence_seal_path(private_path).exists()
    with pytest.raises(tool.ProductionError, match="evidence_seal_missing"):
        tool.inspect_record(private_path)


def test_seal_write_failure_leaves_uncommitted_evidence_unusable(tmp_path, monkeypatch):
    tool = load_tool()
    backend = FakeBackend()
    private_path = tmp_path / "private.json"
    public_path = tmp_path / "public.json"
    seal_path = tool._evidence_seal_path(private_path)
    backend.approval_record_path = tool._approval_record_path(private_path)
    original = tool._atomic_new_json

    def fail_seal(path, document, mode=0o600):
        if path == seal_path:
            raise OSError("injected_seal_write_failure")
        return original(path, document, mode)

    monkeypatch.setattr(tool, "_atomic_new_json", fail_seal)
    with pytest.raises(tool.ProductionError, match="evidence_write_failed"):
        tool.run_production(
            release(tool),
            release_sha256="d" * 64,
            backend=backend,
            approval=lambda _summary: True,
            private_record_path=private_path,
            public_record_path=public_path,
            now=100,
            run_id="e" * 64,
        )
    assert private_path.is_file()
    assert public_path.is_file()
    assert not seal_path.exists()
    with pytest.raises(tool.ProductionError, match="evidence_seal_missing"):
        tool.inspect_record(private_path)


def test_successful_result_files_are_created_once_without_in_place_promotion(
    tmp_path,
):
    tool = load_tool()
    result = run(tmp_path, tool, FakeBackend())
    private = json.loads((tmp_path / "private.json").read_text())
    public = json.loads((tmp_path / "public.json").read_text())
    assert private == result
    assert private["evidence_complete"] is True
    assert public["private_result_sha256"] == sys.modules[
        "n3w_t1_production_contract"
    ].canonical_sha256(private)
    seal_path = tool._evidence_seal_path(tmp_path / "private.json")
    seal = json.loads(seal_path.read_text())
    assert seal["evidence_complete"] is True
    assert seal["private_result_sha256"] == tool._sha256_file(
        tmp_path / "private.json"
    )
    assert seal["public_result_sha256"] == tool._sha256_file(
        tmp_path / "public.json"
    )
    assert tool.inspect_record(tmp_path / "private.json")["final_outcome"] == "PASS"



def test_close_run_requires_target_terminal_proof(tmp_path):
    tool = load_tool()
    result = run(
        tmp_path,
        tool,
        FakeBackend(target_close_ok=False),
    )
    assert result["status"] == "FAIL"
    assert result["device_acceptance"] is True
    assert result["evidence_complete"] is False
    assert result["operator_session_closed"] is True
    assert result["failure_code"] == "target_run_not_closed"
    assert result["final_outcome"] == "FAIL"


def test_target_close_does_not_claim_operator_session_cleanup(tmp_path):
    tool = load_tool()
    result = run(tmp_path, tool, FakeBackend(close_ok=False))
    close_report = result["phase_reports"]["CLOSE_RUN"]
    assert close_report["target_run_terminal"] is True
    assert close_report["operator_session_closed_claimed"] is False
    assert result["device_acceptance"] is True
    assert result["operator_session_closed"] is False
    assert result["evidence_complete"] is True
    assert result["final_outcome"] == "FAIL"
