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
    assert manifest["expected_residue_container_id_sha256"] is None
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
            "expected_residue_container_id_sha256": None,
        },
    )
    called = {"ssh": False}
    class ForbiddenTransport:
        def __init__(self, **kwargs):
            called["ssh"] = True
    monkeypatch.setattr(executor, "SSHTransport", ForbiddenTransport)
    args = argparse.Namespace(
        expected_source_head="a" * 40,
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
