from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "u2"
    / "ha_storage_policy_review"
)
EXECUTOR_PATH = PACKAGE / "executor.py"
REMOTE_PATH = PACKAGE / "remote_probe.py"
MANIFEST_PATH = PACKAGE / "manifest.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


executor = load_module("ha_storage_policy_executor", EXECUTOR_PATH)


def test_manifest_keeps_live_apply_unauthorized():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == (
        "N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_20261105_01"
    )
    assert manifest["authority_parent_head"] == (
        "8310804a222676aba78334f3c0fd291da636242d"
    )
    assert manifest["live_ha_apply_authorized"] is False
    authority = manifest["execution_authority"]
    assert authority["t1_access"] is True
    assert authority["t1_mutation"] is False
    assert authority["persistent_t1_file_write"] is False
    assert authority["service_restart"] is False
    assert authority["image_load"] is False
    assert authority["updater_apply"] is False
    assert authority["updater_rollback"] is False
    assert authority["board_access"] is False


def test_historical_source_binding_rejects_successor_ancestry():
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    with pytest.raises(
        executor.StopExecution,
        match="authority_parent_not_ancestor",
    ):
        executor.validate_source(head)


def test_remote_probe_contains_no_mutating_entrypoints():
    source = REMOTE_PATH.read_text(encoding="utf-8")
    forbidden = (
        '"load"',
        "docker load",
        '"pull"',
        "docker pull",
        '"start"',
        '"stop"',
        '"restart"',
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        ".apply(",
        ".rollback(",
        "rm -",
        "unlink(",
        "write_text(",
        "write_bytes(",
    )
    for marker in forbidden:
        assert marker not in source


def test_bundle_is_flat_and_source_only():
    bundle = executor.bundle_source()
    import io
    import tarfile

    with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:*") as archive:
        names = [member.name for member in archive.getmembers()]
        assert set(names) == {
            "remote_probe.py",
            "n3w_t1_fresh_product_staging_host.py",
        }
        assert all("/" not in name for name in names)
        assert all(member.isfile() for member in archive.getmembers())


def test_remote_runner_accepts_pipe_backed_bundle_and_returns_json():
    result = subprocess.run(
        [sys.executable, "-c", executor.REMOTE_RUNNER],
        input=executor.bundle_source(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert result.returncode == 2
    document = json.loads(result.stdout.decode())
    assert document["schema"] == executor.REMOTE_SCHEMA
    assert document["status"] == "STOP"
    assert document["operation"] == "readonly_storage_policy_baseline"
    assert document["mutation"] is False


def fake_remote() -> dict:
    def container(service, image_size, rw, binds):
        return {
            "service": service,
            "container_id": service + "-id",
            "container_image_ref": service + ":image",
            "container_image_id": "sha256:" + service,
            "container_running": True,
            "container_started_at": "2026-11-05T00:00:00Z",
            "container_restart_count": 0,
            "container_size_rw_bytes": rw,
            "container_size_rootfs_bytes": image_size + rw,
            "image_id": "sha256:" + service,
            "image_size_bytes": image_size,
            "image_os": "linux",
            "image_architecture": "arm64",
            "image_layer_count": 4,
            "log_type": "json-file",
            "log_bytes": 100,
            "writable_binds": [
                {
                    "destination": destination,
                    "usage": {
                        "present": True,
                        "apparent_bytes": allocated,
                        "allocated_bytes": allocated,
                    },
                }
                for destination, allocated in binds
            ],
        }

    return {
        "schema": executor.REMOTE_SCHEMA,
        "status": "PASS",
        "operation": "readonly_storage_policy_baseline",
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "board_access": False,
        "runtime_state_stable": True,
        "storage_authority": {
            "staging_device": 1,
            "docker_device": 1,
            "image_store_device": 1,
            "staging_free_bytes": 8_000_000_000,
            "docker_free_bytes": 8_000_000_000,
            "image_store_free_bytes": 8_000_000_000,
            "image_store_backend": "classic",
        },
        "filesystems": {
            "root": {
                "total_bytes": 16_000_000_000,
                "used_bytes": 8_000_000_000,
                "free_bytes": 8_000_000_000,
                "block_size": 4096,
                "total_inodes": 1_000_000,
                "free_inodes": 900_000,
            }
        },
        "runtime": {
            "containers": {
                "broker": container("broker", 1000, 10, [("/mosquitto/data", 100)]),
                "manager": container(
                    "manager",
                    2000,
                    20,
                    [
                        ("/var/lib/greenhouse-manager/manager", 200),
                        ("/var/lib/greenhouse-manager/n3w", 300),
                    ],
                ),
                "homeassistant": container("homeassistant", 3000, 30, [("/config", 400)]),
            }
        },
        "extra_path_usage": {
            "/var/lib/n3wfc4-homeassistant": {
                "present": True,
                "apparent_bytes": 400,
                "allocated_bytes": 400,
            },
            "/var/lib/greenhouse-manager": {
                "present": True,
                "apparent_bytes": 500,
                "allocated_bytes": 500,
            },
            "/var/lib/n3wfc4-broker": {
                "present": True,
                "apparent_bytes": 100,
                "allocated_bytes": 100,
            },
        },
    }


def test_summary_reports_real_free_space_and_product_state():
    report = executor.summarize(fake_remote())
    assert report["staging_docker_image_store_same_device"] is True
    assert report["minimum_storage_authority_free_bytes"] == 8_000_000_000
    assert report["current_image_size_bytes"]["homeassistant"] == 3000
    assert report["writable_bind_allocated_bytes"] == {
        "broker": 100,
        "manager": 500,
        "homeassistant": 400,
    }
    assert report["runtime_state_stable"] is True


def test_summary_rejects_runtime_change_or_mutation():
    document = fake_remote()
    document["runtime_state_stable"] = False
    with pytest.raises(executor.StopExecution, match="remote_pass_contract_invalid"):
        executor.summarize(document)

    document = fake_remote()
    document["image_load"] = True
    with pytest.raises(executor.StopExecution, match="remote_pass_contract_invalid"):
        executor.summarize(document)
