from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_real_t1_readonly_binding_preflight"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "u13b_real_t1_readonly_binding",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_authorizes_only_real_t1_readonly_binding():
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value["read_only_preflight"] is True
    assert value["real_t1_readonly_execution_authorized"] is True
    assert value["u13b_live_execution_authorized"] is False
    assert value["new_clean_ota_mutation_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    contract = value["execution_contract"]
    assert contract["delegate_existing_u13a_status_only"] is True
    assert contract["execute_mode_forbidden"] is True
    assert contract["current_probe_transaction_mutation"] is False
    assert contract["current_probe_usb_mutation"] is False
    assert contract["current_probe_service_mutation"] is False
    assert contract["current_probe_image_mutation"] is False
    assert contract["current_probe_ha_data_mutation"] is False
    assert contract["current_probe_authorization_claim"] is False
    assert contract["current_probe_u13b_transition"] is False
    assert value["stop_boundary"].startswith(
        "STOP_AFTER_FRESH_TERMINAL_U13A_BINDING"
    )


def test_wrapper_has_no_execute_or_authorization_arguments():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'parser.add_argument("--execute"' not in source
    assert 'parser.add_argument("--authorization-id"' not in source
    assert 'parser.add_argument("--confirm"' not in source
    assert '"--status-only"' in source


def test_normalize_separates_historical_u13a_mutation_from_current_probe():
    executor = load_executor()
    expected = {
        "transaction_phase": "U13A_COMMITTED",
        "transaction_status": "COMMITTED",
        "transaction_sha256": "a" * 64,
        "target_runtime_image_id": "sha256:" + "b" * 64,
    }
    delegated = {
        "status": "U13A_LIVE_COMMIT_PASS_RECONCILED",
        "terminal": True,
        "reconciled_from_durable_u13a": True,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "transaction_mutation": True,
        "usb_mutation": True,
        "u13b_transition": False,
        "post": {
            "transaction_phase": "U13A_COMMITTED",
            "transaction_status": "COMMITTED",
            "recovery_required": False,
            "transaction_sha256": "a" * 64,
            "usb_mirror": {"exact": True, "sha256": {"phase": "c" * 64}},
            "runtime": {"target_runtime_image_id": "sha256:" + "b" * 64},
        },
    }
    result = executor.normalize_status(delegated, expected)
    assert result["status"] == "U13B_REAL_T1_READONLY_BINDING_PASS"
    assert (
        result["historical_u13a_terminal_transition_previously_occurred"]
        is True
    )
    assert result["historical_u13a_transaction_was_mutated"] is True
    assert result["historical_u13a_usb_metadata_was_mutated"] is True
    assert result["delegated_status_reported_transaction_mutation"] is True
    assert result["delegated_status_reported_usb_mutation"] is True
    assert result["current_probe_transaction_mutation"] is False
    assert result["current_probe_usb_mutation"] is False
    assert result["current_probe_service_mutation"] is False
    assert result["current_probe_image_mutation"] is False
    assert result["current_probe_ha_data_mutation"] is False
    assert result["current_probe_authorization_claim"] is False
    assert result["current_probe_u13b_transition"] is False
    assert result["rollback_eligible"] is False
    assert result["new_clean_ota_required"] is True


def test_normalize_fails_closed_on_terminal_drift():
    executor = load_executor()
    expected = {
        "transaction_phase": "U13A_COMMITTED",
        "transaction_status": "COMMITTED",
        "transaction_sha256": "a" * 64,
        "target_runtime_image_id": "sha256:" + "b" * 64,
    }
    delegated = {
        "status": "U13A_LIVE_COMMIT_PASS_RECONCILED",
        "terminal": True,
        "reconciled_from_durable_u13a": True,
        "replay_permitted": False,
        "u13b_transition": False,
        "post": {
            "transaction_phase": "U12_TARGET_ACCEPTANCE",
            "transaction_status": "ACTIVE",
            "recovery_required": False,
            "transaction_sha256": "a" * 64,
            "usb_mirror": {"exact": True, "sha256": {"phase": "c" * 64}},
            "runtime": {"target_runtime_image_id": "sha256:" + "b" * 64},
        },
    }
    with pytest.raises(executor.Stop, match="delegated_terminal_binding_drift"):
        executor.normalize_status(delegated, expected)


def test_run_status_only_delegates_only_status_mode(monkeypatch, tmp_path):
    executor = load_executor()
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        delegated = {
            "status": "U13A_LIVE_COMMIT_PASS_RECONCILED",
            "terminal": True,
            "reconciled_from_durable_u13a": True,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "transaction_mutation": True,
            "usb_mutation": True,
            "u13b_transition": False,
            "post": {
                "transaction_phase": "U13A_COMMITTED",
                "transaction_status": "COMMITTED",
                "recovery_required": False,
                "transaction_sha256": "a" * 64,
                "usb_mirror": {
                    "exact": True,
                    "sha256": {"phase": "c" * 64},
                },
                "runtime": {
                    "target_runtime_image_id": "sha256:" + "b" * 64,
                },
            },
        }
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(delegated) + "\n",
            stderr="",
        )

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    _, result = executor.run_status_only(
        expected_commit="d" * 40,
        execution_id="p1-test",
        evidence_root=tmp_path,
        t1_ssh_target="operator@t1",
        known_hosts=tmp_path / "known_hosts",
        expected_host_key_sha256="SHA256:test",
        expected_terminal={
            "transaction_phase": "U13A_COMMITTED",
            "transaction_status": "COMMITTED",
            "transaction_sha256": "a" * 64,
            "target_runtime_image_id": "sha256:" + "b" * 64,
        },
    )
    command = observed["command"]
    assert "--status-only" in command
    assert "--execute" not in command
    assert "--authorization-id" not in command
    assert "--confirm" not in command
    assert result["current_probe_transaction_mutation"] is False
