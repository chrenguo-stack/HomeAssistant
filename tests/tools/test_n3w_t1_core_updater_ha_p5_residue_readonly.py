from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = ROOT / "tools/execution_packages/n3w/u2/ha_p5_attempt03_residue_readonly/executor.py"

def load_module():
    spec = importlib.util.spec_from_file_location("ha_p5_residue_readonly_test", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

executor = load_module()

def report():
    predecessor_id = "sha256:" + "a" * 64
    target_id = "sha256:" + "b" * 64
    return {
        "unit_state": "active",
        "containers": [
            {
                "container_id": "1" * 64,
                "name": "/n3wfc4-homeassistant-1",
                "image_ref": executor.PREDECESSOR_IMAGE,
                "image_id": predecessor_id,
                "status": "running",
                "running": True,
                "exit_code": 0,
                "started_at": "2026-11-05T22:54:53Z",
                "finished_at": "0001-01-01T00:00:00Z",
                "project": executor.PROJECT,
                "service": executor.SERVICE,
                "replace": "",
            },
            {
                "container_id": "2" * 64,
                "name": "/replacement",
                "image_ref": executor.TARGET_IMAGE,
                "image_id": target_id,
                "status": "created",
                "running": False,
                "exit_code": 0,
                "started_at": "0001-01-01T00:00:00Z",
                "finished_at": "0001-01-01T00:00:00Z",
                "project": executor.PROJECT,
                "service": executor.SERVICE,
                "replace": "homeassistant-1",
            },
        ],
        "predecessor_image": {
            "reference": executor.PREDECESSOR_IMAGE,
            "image_id": predecessor_id,
            "os": "linux",
            "architecture": "arm64",
        },
        "target_image": {
            "reference": executor.TARGET_IMAGE,
            "image_id": target_id,
            "os": "linux",
            "architecture": "arm64",
        },
    }

def test_classifies_exact_attempt03_created_residue():
    result = executor.classify_remote(report())
    assert result["classification"] == "ATTEMPT03_TARGET_RECREATE_CREATED_RESIDUE"
    assert result["residue_container_id_sha256"] == executor.sha256_text("2" * 64)
    assert result["target_image_prestate"] == "PRESENT_AND_EXACT_CANDIDATE"
    assert result["cleanup_required_before_reapply"] is True

@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("status", "exited", "attempt03_residue_identity_invalid"),
        ("running", True, "running_homeassistant_container_count_invalid"),
        ("image_ref", "local/other:bad", "attempt03_residue_identity_invalid"),
        ("replace", "", "attempt03_residue_identity_invalid"),
        ("started_at", "2026-11-05T22:53:00Z", "attempt03_residue_started"),
    ],
)
def test_rejects_residue_identity_drift(field, value, error):
    value_doc = report()
    value_doc["containers"][1][field] = value
    with pytest.raises(executor.StopExecution, match=error):
        executor.classify_remote(value_doc)

def test_remote_probe_contains_no_mutating_docker_command():
    source = executor.REMOTE_PROBE
    assert '"docker", "rm"' not in source
    assert '"docker", "stop"' not in source
    assert '"docker", "start"' not in source
    assert '"docker", "compose"' not in source
    assert '"systemctl", "restart"' not in source
    assert '"systemctl", "stop"' not in source
