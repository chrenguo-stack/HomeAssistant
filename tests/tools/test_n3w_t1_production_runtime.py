from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_tool():
    _load(
        TOOLS / "n3w_t1_production_contract.py",
        "n3w_t1_production_contract",
    )
    _load(
        TOOLS / "n3w_t1_ssh_transport.py",
        "n3w_t1_ssh_transport",
    )
    _load(
        TOOLS / "n3w_t1_fresh_product_staging_host.py",
        "n3w_t1_fresh_product_staging_host",
    )
    return _load(
        TOOLS / "n3w_t1_production_runtime.py",
        "n3w_t1_production_runtime",
    )


def test_mac_required_files_exist_and_cover_f2_production_dependencies() -> None:
    tool = load_tool()
    f2_relative = (
        "tools/execution_packages/n3w/f2/"
        "t1_fresh_readonly_preflight/executor.py"
    )
    f2 = _load(
        ROOT / f2_relative,
        "n3w_f2_packaging_dependency_contract",
    )
    required = {
        f2_relative,
        f2.IDENTITY_RELATIVE,
        f2.INVENTORY_RELATIVE,
        f2.STAGING_RELATIVE,
        "tools/n3w_t1_production_contract.py",
    }

    assert required.issubset(tool.MAC_REQUIRED_FILES)
    assert all((ROOT / relative).is_file() for relative in tool.MAC_REQUIRED_FILES)
    assert (
        "tools/execution_packages/n3w/f2/"
        "t1_fresh_readonly_identity/executor.py"
        not in tool.MAC_REQUIRED_FILES
    )


def test_file_set_manifest_requires_exact_bound_file_set(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    root = tmp_path / "files"
    root.mkdir()
    item = root / "one.py"
    item.write_text("print('one')\n", encoding="utf-8")
    manifest = {
        "schema": tool.FILE_SET_SCHEMA,
        "scope": "test_scope",
        "source_head": "a" * 40,
        "files": [
            {
                "path": "one.py",
                "sha256": tool._sha256_file(item),
                "size": item.stat().st_size,
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    observed = tool._file_set_manifest(
        path,
        root,
        expected_scope="test_scope",
        expected_sha256=tool._sha256_file(path),
        source_head="a" * 40,
        required_files=frozenset({"one.py"}),
    )
    assert observed == {"one.py": tool._sha256_file(item)}


def test_phase_claim_uses_target_record_predecessor_not_report_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    backend = object.__new__(tool.ProductionRuntimeBackend)
    backend.release = {"release_id": "1" * 64}
    plan = {
        "run_id": "2" * 64,
        "source_head": "a" * 40,
        "release_id": "1" * 64,
        "target_binding_sha256": "3" * 64,
    }
    backend.plan = plan
    backend._last_report_sha256 = "4" * 64
    backend._authority_predecessor_sha256 = "5" * 64
    backend._active_context = None
    backend._active_context_local = None
    backend._active_context_remote = None
    captured = {}

    monkeypatch.setattr(
        tool,
        "phase_artifact_sha256",
        lambda _release, _phase: "6" * 64,
    )

    def stage_json(name, document):
        captured[name] = document
        local = tmp_path / name
        local.write_text(json.dumps(document), encoding="utf-8")
        return local, f"/remote/{name}"

    backend._write_and_stage_json = stage_json
    calls = []

    def authority(args, **_kwargs):
        calls.append(args)
        if args[0] == "claim":
            return {
                "status": "PASS",
                "claim_sha256": "7" * 64,
            }
        if args[0] == "begin":
            return {
                "status": "PASS",
                "claim_sha256": "8" * 64,
            }
        return {
            "schema": "gh.n3w-t1-production-phase-context/1",
            "status": "PASS",
            "run_id": plan["run_id"],
            "phase": "PROVISION",
            "claim_sha256": "8" * 64,
            "plan_sha256": "9" * 64,
            "binding": captured["provision-binding.json"],
            "binding_sha256": "a" * 64,
            "authorization_consumed": True,
            "replay_allowed": False,
            "board_access": False,
        }

    backend._authority = authority

    backend._claim_phase(
        "PROVISION",
        plan=plan,
        predecessor_sha256="4" * 64,
    )

    binding = captured["provision-binding.json"]
    assert binding["predecessor_sha256"] == "5" * 64
    assert binding["predecessor_sha256"] != "4" * 64
    assert [call[0] for call in calls] == [
        "claim",
        "begin",
        "context",
    ]


def test_reboot_transition_orders_durable_claim_then_phase_close_then_reboot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    backend = object.__new__(tool.ProductionRuntimeBackend)
    backend.plan = {"run_id": "1" * 64}
    backend._active_context = {
        "phase": "REBOOT_CONTROL",
        "claim_sha256": "2" * 64,
    }
    backend._active_context_remote = "/remote/reboot-context.json"
    backend._reboot_pending_claim_sha256 = "3" * 64
    backend._reboot_control_report = {"status": "PASS"}
    backend._reboot_control_report_sha256 = "4" * 64
    backend.remote_reboot_package = "/var/tmp/reboot-package"
    backend._reboot_command_attempted = False
    order = []

    def actuation(*_args, **_kwargs):
        order.append("actuation")
        return {
            "status": "PASS",
            "state": "REBOOT_ACTUATION_CLAIMED",
            "reboot_actuation_attempted": True,
            "reboot_actuation_replay_allowed": False,
            "reboot_executed": False,
        }

    backend._run_target_python = actuation

    def complete(phase, report):
        assert phase == "REBOOT_CONTROL"
        assert report == {"status": "PASS"}
        order.append("complete")

    backend._complete_active = complete

    class Transport:
        def run_remote(self, argv, **_kwargs):
            assert tuple(argv) == ("sudo", "-n", "systemctl", "reboot")
            order.append("reboot")
            return subprocess.CompletedProcess(argv, 255, "", "")

    backend.transport = Transport()
    report = backend.transition_reboot()

    assert report["status"] == "PASS"
    assert report["replay_allowed"] is False
    assert order == ["actuation", "complete", "reboot"]


def test_reboot_transition_never_sends_reboot_when_actuation_claim_fails() -> None:
    tool = load_tool()
    backend = object.__new__(tool.ProductionRuntimeBackend)
    backend.plan = {"run_id": "1" * 64}
    backend._active_context = {
        "phase": "REBOOT_CONTROL",
        "claim_sha256": "2" * 64,
    }
    backend._active_context_remote = "/remote/reboot-context.json"
    backend._reboot_pending_claim_sha256 = "3" * 64
    backend._reboot_control_report = {"status": "PASS"}
    backend._reboot_control_report_sha256 = "4" * 64
    backend.remote_reboot_package = "/var/tmp/reboot-package"
    backend._reboot_command_attempted = False

    backend._run_target_python = lambda *_args, **_kwargs: {
        "status": "PASS",
        "state": "INVALID",
    }

    class Transport:
        def run_remote(self, *_args, **_kwargs):
            raise AssertionError("reboot must not be sent")

    backend.transport = Transport()
    with pytest.raises(
        tool.ProductionRuntimeError,
        match="reboot_actuation_claim_invalid",
    ):
        backend.transition_reboot()
