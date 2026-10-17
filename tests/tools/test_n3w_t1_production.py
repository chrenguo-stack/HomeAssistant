from __future__ import annotations

import importlib.util
import json
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
    def __init__(self, finalize_accepts=True, close_ok=True):
        self.finalize_accepts = finalize_accepts
        self.close_ok = close_ok
        self.approvals = 0
        self.epochs = 0
        self.reboots = 0
        self.phases = []

    def connect_pre_reboot(self):
        self.epochs += 1
        return {"status": "PASS"}

    def target_identity(self):
        return {
            "target_binding_sha256": "b" * 64,
            "ssh_host_key_sha256": "c" * 64,
        }

    def approve_run(self, plan):
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
    return tool.run_production(
        release(tool),
        release_sha256="d" * 64,
        backend=backend,
        approval=approval,
        private_record_path=tmp_path / "private.json",
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
    assert result["final_outcome"] == "FAIL"


def test_cli_has_no_repair_or_shell_surface():
    source = TOOL.read_text(encoding="utf-8")
    assert "repair-" not in source
    assert 'add_parser("run")' in source
    assert 'add_parser("inspect")' in source
    assert 'add_parser("verify")' in source
