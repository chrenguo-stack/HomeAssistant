from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools/execution_packages/n3w/u2/ha_p5_postcleanup_reapply_readonly"
EXECUTOR_PATH = PACKAGE / "executor.py"
MANIFEST_PATH = PACKAGE / "manifest.json"

def load_module():
    spec = importlib.util.spec_from_file_location(
        "ha_p5_postcleanup_reapply_readonly_test",
        EXECUTOR_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

executor = load_module()

def test_manifest_is_strictly_readonly_and_has_no_live_reapply_authority():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["t1_access"] is True
    assert manifest["t1_mutation"] is False
    assert manifest["persistent_t1_write"] is False
    assert manifest["temporary_t1_write"] is False
    assert manifest["service_restart"] is False
    assert manifest["container_delete"] is False
    assert manifest["image_load"] is False
    assert manifest["compose_mutation"] is False
    assert manifest["board_access"] is False
    assert manifest["live_reapply_authorized"] is False
    assert manifest["cleanup_authority"]["status"] == "CLOSED_PASS"
    assert manifest["cleanup_authority"]["authorization_replay_permitted"] is False

def test_frozen_target_identity_matches_reviewed_constants():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    identity = manifest["frozen_target_identity"]
    assert identity["target_image_ref"] == executor.TARGET_IMAGE
    assert identity["target_image_id"] == executor.TARGET_IMAGE_ID
    assert identity["config_semantics_sha256"] == executor.TARGET_CONFIG_SEMANTICS_SHA256
    assert identity["rootfs_diff_ids_sha256"] == executor.TARGET_ROOTFS_DIFF_IDS_SHA256

def test_runtime_rejects_non_single_container(monkeypatch):
    monkeypatch.setattr(executor, "container_ids", lambda transport, service: ["a", "b"])
    with pytest.raises(executor.StopExecution, match="homeassistant_container_count_invalid"):
        executor.runtime(object(), "homeassistant", executor.PREDECESSOR_IMAGE)

def test_target_fingerprint_is_deterministic():
    document = {
        "Id": "sha256:" + "a" * 64,
        "Os": "linux",
        "Architecture": "arm64",
        "Config": {
            "Entrypoint": ["/init"],
            "Cmd": None,
            "User": "",
            "Env": ["A=B"],
            "WorkingDir": "/config",
            "Labels": {"x": "y"},
            "Healthcheck": None,
            "StopSignal": None,
            "Volumes": None,
            "ExposedPorts": None,
        },
        "RootFS": {
            "Layers": [
                "sha256:" + "1" * 64,
                "sha256:" + "2" * 64,
            ]
        },
    }
    first = executor.target_fingerprint(document)
    second = executor.target_fingerprint(document)
    assert first == second
    assert first["image_id"] == document["Id"]
    assert first["os"] == "linux"
    assert first["architecture"] == "arm64"
    assert len(first["config_semantics_sha256"]) == 64
    assert len(first["rootfs_diff_ids_sha256"]) == 64

def test_source_contains_no_mutating_remote_command():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    forbidden = (
        "docker rm",
        "docker load",
        "docker stop",
        "docker start",
        "systemctl restart",
        "systemctl stop",
        "docker compose up",
        "docker compose down",
    )
    for item in forbidden:
        assert item not in source

def test_source_requires_exact_cleanup_closure_binding():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert executor.CLEANUP_CLOSURE_BLOB in source
    assert "cleanup_closure_blob_drift" in source
