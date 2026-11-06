from __future__ import annotations

import argparse
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
EXECUTOR = (
    ROOT
    / "tools/execution_packages/n3w/u2/ha_template_convergence_readonly_preflight/executor.py"
)
MANIFEST = EXECUTOR.parent / "manifest.json"


def load():
    spec = importlib.util.spec_from_file_location("ha_template_preflight_executor", EXECUTOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def report(module):
    return {
        "schema": module.INSPECT_SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "mutation": False,
        "expected_homeassistant_image": module.EXPECTED_HA_IMAGE,
        "current_binding_mode": "legacy_static",
        "candidate_binding_mode": "dynamic",
        "current_compose_sha256": "1" * 64,
        "current_env_sha256": "2" * 64,
        "candidate_compose_sha256": "3" * 64,
        "candidate_env_sha256": "4" * 64,
        "current_render_sha256": "5" * 64,
        "candidate_render_sha256": "5" * 64,
        "render_semantically_equal": True,
        "product_path_write": False,
        "service_restart": False,
    }


def args(tmp_path: Path, module):
    return argparse.Namespace(
        execute=True,
        expected_source_head="a" * 40,
        evidence_root=tmp_path / "evidence",
        target="root@192.0.2.1",
        confirm=module.CONFIRMATION,
    )


def test_manifest_matches_frozen_source_bindings():
    module = load()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == module.GATE_ID
    assert manifest["source_binding"]["authority_parent_head"] == module.AUTHORITY_PARENT_HEAD
    assert manifest["source_binding"]["inspector_blob_sha"] == module.EXPECTED_INSPECTOR_BLOB
    assert manifest["source_binding"]["current_authority_blob_sha"] == module.EXPECTED_AUTHORITY_BLOB
    assert manifest["expected_runtime"]["homeassistant_image"] == module.EXPECTED_HA_IMAGE


@pytest.mark.parametrize(
    "target",
    ("", " root@host", "root@host ", "root@host extra", "-oBad", "<t1>", "example"),
)
def test_invalid_target_stops(target):
    module = load()
    with pytest.raises(module.StopExecution, match="t1_target_invalid"):
        module.validate_target(target)


def test_wrong_confirmation_stops_before_source_or_evidence(tmp_path, monkeypatch):
    module = load()
    a = args(tmp_path, module)
    a.confirm = "NO"
    monkeypatch.setattr(
        module,
        "validate_source",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not validate source")),
    )
    with pytest.raises(module.StopExecution, match="readonly_confirmation_invalid"):
        module.execute(a)
    assert not a.evidence_root.exists()


def test_report_requires_strict_readonly_contract():
    module = load()
    value = report(module)
    module.require_pass(value)

    value = report(module)
    value["mutation"] = True
    with pytest.raises(module.StopExecution, match="ha_template_convergence_report_invalid"):
        module.require_pass(value)

    value = report(module)
    value["product_path_write"] = True
    with pytest.raises(module.StopExecution, match="ha_template_convergence_report_invalid"):
        module.require_pass(value)

    value = report(module)
    value["service_restart"] = True
    with pytest.raises(module.StopExecution, match="ha_template_convergence_report_invalid"):
        module.require_pass(value)


def test_double_read_drift_stops():
    module = load()
    first = report(module)
    second = report(module)
    second["current_env_sha256"] = "9" * 64
    with pytest.raises(
        module.StopExecution,
        match="ha_template_readonly_stability_drift:current_env_sha256",
    ):
        module.compare_runs(first, second)


def test_execute_runs_two_readonly_inspections_and_keeps_private_evidence(
    tmp_path, monkeypatch
):
    module = load()
    a = args(tmp_path, module)
    seen = []

    monkeypatch.setattr(
        module,
        "validate_source",
        lambda head: {
            "expected_source_head": head,
            "authority_parent_head": module.AUTHORITY_PARENT_HEAD,
            "inspector_blob_sha": module.EXPECTED_INSPECTOR_BLOB,
            "current_authority_blob_sha": module.EXPECTED_AUTHORITY_BLOB,
        },
    )
    monkeypatch.setattr(module, "inspector_source", lambda: b"print('source')")
    monkeypatch.setattr(
        module,
        "ssh_inspect",
        lambda target, source: seen.append((target, source)) or report(module),
    )

    result = module.execute(a)

    assert result["status"] == "PASS"
    assert result["mutation"] is False
    assert result["persistent_t1_file_write"] is False
    assert result["temporary_scratch_write"] is True
    assert result["double_read_stable"] is True
    assert result["raw_target_public_output"] is False
    assert len(seen) == 2
    assert result["expected_homeassistant_image"] == module.EXPECTED_HA_IMAGE

    assert stat.S_IMODE(a.evidence_root.stat().st_mode) == 0o700
    for name in ("inspection-1.json", "inspection-2.json", "result.json"):
        path = a.evidence_root / name
        assert path.is_file()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_ssh_streams_inspector_over_stdin_without_remote_staging(monkeypatch):
    module = load()
    captured = {}

    def fake_run(argv, *, input_bytes=None, timeout=180, check=True):
        captured["argv"] = argv
        captured["input"] = input_bytes
        captured["check"] = check
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(report(module)).encode(),
            stderr=b"",
        )

    monkeypatch.setattr(module, "run", fake_run)
    result = module.ssh_inspect("root@192.0.2.1", b"source-bytes")

    assert result["status"] == "PASS"
    assert captured["input"] == b"source-bytes"
    assert captured["check"] is False
    command = captured["argv"][-1]
    assert "python3" in command
    assert module.EXPECTED_HA_IMAGE in command
    assert "/var/tmp" not in command
    assert "scp" not in " ".join(captured["argv"])


def test_source_binding_matches_git_blobs_when_run_on_exact_head():
    module = load()
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    assert (
        subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", f"{head}:{module.INSPECTOR_RELATIVE}"],
            text=True,
        ).strip()
        == module.EXPECTED_INSPECTOR_BLOB
    )
    assert (
        subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", f"{head}:{module.AUTHORITY_RELATIVE}"],
            text=True,
        ).strip()
        == module.EXPECTED_AUTHORITY_BLOB
    )
