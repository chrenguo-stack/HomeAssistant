from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools/execution_packages/n3w/u2/ha_p5_attempt03_residue_cleanup"
EXECUTOR_PATH = PACKAGE / "executor.py"
MANIFEST_PATH = PACKAGE / "manifest.json"

def load_module():
    spec = importlib.util.spec_from_file_location("ha_p5_residue_cleanup_test", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

executor = load_module()

def test_cleanup_package_is_prepared_but_not_authorized():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["live_cleanup_authorized"] is False
    assert manifest["authorization_id"] is None
    assert manifest["expected_residue_container_id_sha256"] == "b795e09bf6bf2b47216c124430bdb768d9c914a8e2abd99f20dd8b5f0eb59bb9"
    assert manifest["classification_source_head"] == "89ddb7415e0642167a819c521bd083509549c016"
    assert manifest["classification_gate_id"] == "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_ATTEMPT03_RESIDUE_READONLY_20261105_01"
    assert manifest["permitted_container_deletions"] == 1
    assert manifest["target_image_delete_allowed"] is False
    assert manifest["service_restart_allowed"] is False

def test_execute_stops_before_ssh_when_cleanup_not_authorized(monkeypatch):
    monkeypatch.setattr(
        executor,
        "validate_source",
        lambda head: {
            "live_cleanup_authorized": False,
            "authorization_id": None,
            "expected_residue_container_id_sha256": "b795e09bf6bf2b47216c124430bdb768d9c914a8e2abd99f20dd8b5f0eb59bb9",
        },
    )
    called = {"ssh": False}
    class ForbiddenTransport:
        def __init__(self, **kwargs):
            called["ssh"] = True
    monkeypatch.setattr(executor, "SSHTransport", ForbiddenTransport)
    args = argparse.Namespace(
        expected_source_head="a" * 40,
        evidence_root=Path("/tmp/never-evidence"),
        target="root@example",
        known_hosts=Path("/tmp/never"),
        expected_host_key_sha256="b" * 64,
        authorization_id="unused",
        confirm=executor.CONFIRMATION,
    )
    with pytest.raises(executor.StopExecution, match="live_cleanup_not_authorized"):
        executor.execute(args)
    assert called["ssh"] is False

def test_cleanup_source_has_single_bounded_container_delete():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert source.count('["docker", "rm", raw_id]') == 1
    assert '"docker", "rm", "-f"' not in source
    assert "docker image rm" not in source
    assert "systemctl restart" not in source
    assert 'evidence / "authorization-claim.json"' in source
    assert 'evidence / "cleanup-mutation.json"' in source
    assert 'evidence / "post-cleanup-report.json"' in source
    assert 'evidence / "failure.json"' in source
    assert source.index('evidence / "authorization-claim.json"') < source.index(
        '["docker", "rm", raw_id]'
    )


def test_cleanup_requires_private_evidence_root():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert 'parser.add_argument("--evidence-root", type=Path, required=True)' in source
    assert "evidence_root_inside_repository" in source
    assert "evidence_root_invalid" in source
