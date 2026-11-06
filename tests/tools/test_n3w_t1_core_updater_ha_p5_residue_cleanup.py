from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools/execution_packages/n3w/u2/ha_p5_attempt03_residue_cleanup"
EXECUTOR_PATH = PACKAGE / "executor.py"
MANIFEST_PATH = PACKAGE / "manifest.json"

def load_module():
    spec = importlib.util.spec_from_file_location(
        "ha_p5_residue_cleanup_test",
        EXECUTOR_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

executor = load_module()

def test_cleanup_package_is_consumed_closed_and_non_replayable():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["live_cleanup_authorized"] is False
    assert manifest["authorization_id"] == "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_ATTEMPT03_RESIDUE_CLEANUP_LIVE_20261105_01"
    assert manifest["authorization"]["granted"] is True
    assert manifest["authorization"]["claimed"] is True
    assert manifest["authorization"]["consumed"] is True
    assert manifest["authorization"]["replay_permitted"] is False
    assert manifest["authorization"]["remaining_cleanup_invocations"] == 0
    assert manifest["authorization"]["second_cleanup_allowed"] is False
    assert manifest["authorization"]["cleanup_result"] == "CLOSED_PASS"
    assert manifest["execution_state"] == "CONSUMED_CLOSED_PASS"
    assert manifest["stop_boundary"] == "CLOSED_NO_REPLAY"

def test_executor_stops_before_transport_when_manifest_is_closed(monkeypatch):
    monkeypatch.setattr(
        executor,
        "validate_source",
        lambda head: {
            "live_cleanup_authorized": False,
            "authorization_id": "closed",
            "expected_residue_container_id_sha256": "b795e09bf6bf2b47216c124430bdb768d9c914a8e2abd99f20dd8b5f0eb59bb9",
        },
    )
    called = {"transport": False}

    class ForbiddenTransport:
        def __init__(self, **kwargs):
            called["transport"] = True

    monkeypatch.setattr(executor, "SSHTransport", ForbiddenTransport)

    class Args:
        expected_source_head = "a" * 40
        evidence_root = Path("/tmp/unused")
        target = "root@example"
        known_hosts = Path("/tmp/unused")
        expected_host_key_sha256 = "b" * 64
        authorization_id = "closed"
        confirm = executor.CONFIRMATION

    with pytest.raises(executor.StopExecution, match="live_cleanup_not_authorized"):
        executor.execute(Args())
    assert called["transport"] is False

def test_cleanup_executor_still_requires_private_evidence_root():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert 'parser.add_argument("--evidence-root", type=Path, required=True)' in source
    assert "authorization-claim.json" in source
    assert "cleanup-mutation.json" in source
    assert "post-cleanup-report.json" in source
