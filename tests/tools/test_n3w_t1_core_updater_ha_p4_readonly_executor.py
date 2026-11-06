from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "u2"
    / "ha_p4_readonly_premutation_baseline"
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


executor = load_module("ha_p4_executor", EXECUTOR_PATH)
remote = load_module("ha_p4_remote_probe", REMOTE_PATH)


def test_manifest_keeps_p4_strictly_readonly_and_bound_to_p3():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == (
        "N3W_T1_CORE_UPDATER_HOMEASSISTANT_"
        "P4_FRESH_READONLY_PREMUTATION_BASELINE_20261105_01"
    )
    assert manifest["authority_parent_head"] == (
        "bb845f5cca4f2fc3e4710d14b6176a043d2a4523"
    )
    assert manifest["p3_executable_source_head"] == (
        "b4409c11beda99f2aef43353b8129003760634b7"
    )
    authority = manifest["execution_authority"]
    assert authority["t1_access"] is True
    assert authority["temporary_scratch_write"] is True
    for key in (
        "t1_mutation",
        "persistent_t1_file_write",
        "service_restart",
        "image_load",
        "updater_apply",
        "updater_rollback",
        "credential_mutation",
        "board_access",
        "merge",
    ):
        assert authority[key] is False
    assert manifest["frozen_target"]["artifact_id"] == 13391983948
    assert manifest["frozen_target"]["target_image_prestate_required"] == "ABSENT"


def test_historical_execution_package_rejects_successor_source_drift():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen_blob = manifest["source_binding"][
        "tools/n3w_t1_core_updater_v2_state.py"
    ]
    assert frozen_blob == "a5260f1097983cad4818f626826accbb185e4a37"

    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    current_blob = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "rev-parse",
            f"{head}:tools/n3w_t1_core_updater_v2_state.py",
        ],
        text=True,
    ).strip()
    assert current_blob != frozen_blob
    with pytest.raises(
        executor.StopExecution,
        match="source_blob_mismatch:n3w_t1_core_updater_v2_state.py",
    ):
        executor.validate_source(head)


def test_bundle_is_flat_temporary_source_only():
    payload = executor.bundle_source()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        members = archive.getmembers()
    names = {item.name for item in members}
    assert "remote_probe.py" in names
    assert "target.json" in names
    assert "n3w_t1_core_updater.py" in names
    assert "n3w_t1_core_updater_v2.py" in names
    assert "n3w_t1_core_updater_host.py" in names
    assert all("/" not in item.name for item in members)
    assert all(not item.issym() and not item.islnk() for item in members)
    assert all(item.mode == 0o600 for item in members)


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
    assert document["operation"] == "readonly_premutation_baseline"
    assert document["mutation"] is False


def test_remote_probe_has_no_mutating_updater_entrypoint():
    text = REMOTE_PATH.read_text(encoding="utf-8")
    assert "updater.apply(" not in text
    assert "updater.rollback(" not in text
    assert "host.load_image(" not in text
    assert "rewrite_component_image(" not in text
    assert "stop_services(" not in text
    assert "start_services(" not in text
    assert "updater.status()" in text
    assert "updater.runtime_state()" in text
    assert 'updater.inspect("homeassistant")' in text
    assert "updater.baseline()" in text
    assert "updater.plan(" in text


def test_remote_pass_contract_accepts_only_complete_readonly_result():
    document = {
        "schema": executor.REMOTE_SCHEMA,
        "status": "PASS",
        "operation": "readonly_premutation_baseline",
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "component": "homeassistant",
        "runtime_class": "TARGET_BOUND_RUNNING",
        "health_state": "HEALTHY",
        "recovery_required": False,
        "baseline_double_read_stable": True,
        "target_image_prestate": "ABSENT",
        "target_archive_verified": False,
        "template_convergence_planned": True,
        "rollback_available": True,
        "readonly_state_stable": True,
    }
    for field in (
        "baseline_sha256",
        "plan_sha256",
        "transaction_sha256",
        "product_snapshot_sha256",
        "state_snapshot_sha256",
        "service_snapshot_sha256",
    ):
        document[field] = "a" * 64
    executor.require_remote_pass(document)

    broken = dict(document)
    broken["service_restart"] = True
    with pytest.raises(executor.StopExecution, match="p4_remote_pass_contract_invalid"):
        executor.require_remote_pass(broken)


def test_plan_contract_requires_legacy_static_to_dynamic_convergence():
    document = {
        "status": "PASS",
        "operation": "plan",
        "component": "homeassistant",
        "mutation": False,
        "current": {
            "image": remote.EXPECTED_PREDECESSOR,
            "binding_mode": "legacy_static",
        },
        "target": {
            "target_image_ref": remote.EXPECTED_TARGET,
            "expected_predecessor_image_ref": remote.EXPECTED_PREDECESSOR,
        },
        "target_image_prestate": "ABSENT",
        "target_archive_verified": False,
        "actions": [
            "verify_or_load_exact_target_image",
            "quiesce_homeassistant_production_owner",
            "converge_homeassistant_runtime_template",
            "replace_only_homeassistant_image_binding",
            "validate_effective_compose_delta_target_only",
            "activate_homeassistant_production_owner",
            "verify_target_and_peer_hard_contracts",
            "verify_a1_soft_runtime_health",
        ],
        "rollback_available": True,
    }
    remote.validate_plan(document)

    broken = dict(document)
    broken["actions"] = [
        action
        for action in document["actions"]
        if action != "converge_homeassistant_runtime_template"
    ]
    with pytest.raises(remote.StopProbe, match="plan_template_convergence_missing"):
        remote.validate_plan(broken)
