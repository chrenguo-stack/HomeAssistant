from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("n3w_t1_production_v2_contract", "n3w_t1_production_v2_contract.py")
marker = load("n3w_t1_production_marker_test", "n3w_t1_production_marker.py")


def binding():
    return {
        "run_id": "1" * 64,
        "release_id": "2" * 64,
        "release_sha256": "3" * 64,
        "source_head": "4" * 40,
        "target_binding_sha256": "5" * 64,
        "ssh_host_key_sha256": "6" * 64,
        "plan_sha256": "7" * 64,
    }


def test_start_creates_durable_started_marker_without_replay(tmp_path):
    path = tmp_path / "run.json"
    result = marker.start_marker(
        path,
        binding(),
        created_at="2026-10-20T00:00:00Z",
    )
    assert result["state"] == "STARTED"
    assert result["replay_allowed"] is False
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert marker.read_marker(path) == result
    assert marker.inspect_marker(path)["T1_PRODUCTION_READY"] is False


def test_duplicate_start_is_rejected_and_original_bytes_are_preserved(tmp_path):
    path = tmp_path / "run.json"
    marker.start_marker(path, binding(), created_at="2026-10-20T00:00:00Z")
    before = path.read_bytes()
    with pytest.raises(marker.ProductionMarkerError, match="marker_already_exists"):
        marker.start_marker(path, binding(), created_at="2026-10-20T00:00:01Z")
    assert path.read_bytes() == before


def test_accept_requires_exact_started_binding(tmp_path):
    path = tmp_path / "run.json"
    original = binding()
    marker.start_marker(path, original, created_at="2026-10-20T00:00:00Z")
    changed = dict(original)
    changed["release_id"] = "9" * 64
    with pytest.raises(marker.ProductionMarkerError, match="marker_binding_mismatch:release_id"):
        marker.accept_marker(
            path,
            changed,
            acceptance_sha256="8" * 64,
            accepted_at="2026-10-20T00:05:00Z",
        )
    assert marker.read_marker(path)["state"] == "STARTED"


def test_accept_is_terminal_and_sets_production_ready(tmp_path):
    path = tmp_path / "run.json"
    values = binding()
    marker.start_marker(path, values, created_at="2026-10-20T00:00:00Z")
    result = marker.accept_marker(
        path,
        values,
        acceptance_sha256="8" * 64,
        accepted_at="2026-10-20T00:05:00Z",
    )
    assert result["state"] == "ACCEPTED"
    assert result["T1_PRODUCTION_READY"] is True
    assert marker.inspect_marker(path)["T1_PRODUCTION_READY"] is True
    with pytest.raises(marker.ProductionMarkerError, match="marker_not_started"):
        marker.accept_marker(
            path,
            values,
            acceptance_sha256="8" * 64,
            accepted_at="2026-10-20T00:06:00Z",
        )


def test_marker_rejects_symlink(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    real.chmod(0o600)
    link = tmp_path / "run.json"
    link.symlink_to(real)
    with pytest.raises(marker.ProductionMarkerError, match="marker_file_invalid"):
        marker.read_marker(link)


def test_parser_exposes_only_inspect_start_accept():
    parser = marker.parser()
    choices = None
    for action in parser._actions:
        if getattr(action, "choices", None):
            choices = set(action.choices)
    assert choices == {"inspect", "start", "accept"}
    assert not {"resume", "repair", "clear", "reset", "force", "reopen"} & choices


def test_marker_file_sha_is_raw_file_binding(tmp_path):
    path = tmp_path / "run.json"
    marker.start_marker(path, binding(), created_at="2026-10-20T00:00:00Z")
    import hashlib

    assert marker.marker_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()
