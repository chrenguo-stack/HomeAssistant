from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_production_driver_contract import (
    BrokerIdentityProductionDriverContractError,
    BrokerIdentityProductionDriverDisabledError,
    build_production_driver_contract,
    execute_production_driver_contract,
    verify_production_driver_contract,
)

CONTRACT_SHA = "a" * 64
SKELETON_SHA = "b" * 64
MOUNT_SHA = "c" * 64


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
        "mutation_scope": {
            "allowed_container_targets": [
                "/mosquitto/config/mosquitto.conf",
                "/mosquitto/config/dynsec-password-init",
                "/mosquitto/data/dynamic-security.json",
            ]
        },
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    skeleton = {
        "schema": "gh.m2.t1-broker-identity-production-adapter-skeleton/1",
        "skeleton_sha256": SKELETON_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "production_adapter_skeleton_available": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    gate = {
        "schema": "gh.m2.t1-broker-identity-live-mount-gate/1",
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "checks": {"all": True},
        "read_only": True,
        "mount_binding_ready": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    return (
        _write_private(tmp_path / "executor.json", executor),
        _write_private(tmp_path / "skeleton.json", skeleton),
        _write_private(tmp_path / "gate.json", gate),
    )


def _build(tmp_path: Path) -> dict[str, object]:
    executor, skeleton, gate = _fixture(tmp_path)
    return build_production_driver_contract(
        executor,
        skeleton,
        gate,
        executor_verifier=lambda _document: {
            "verified": True,
            "contract_sha256": CONTRACT_SHA,
        },
        skeleton_verifier=lambda _document: {
            "verified": True,
            "skeleton_sha256": SKELETON_SHA,
        },
    )


def test_builds_strict_default_disabled_driver_contract(tmp_path: Path) -> None:
    report = _build(tmp_path)
    verified = verify_production_driver_contract(report)

    assert report["schema"] == "gh.m2.t1-broker-identity-production-driver-contract/1"
    assert verified["verified"] is True
    assert report["production_driver_contract_available"] is True
    assert report["production_driver_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False

    controller = report["runtime_controller"]
    assert controller["commands"] == [
        {
            "name": "inspect_mosquitto",
            "argv": ["docker", "inspect", "mosquitto"],
            "mutation": False,
        },
        {
            "name": "restart_mosquitto",
            "argv": ["docker", "restart", "mosquitto"],
            "mutation": True,
        },
    ]
    assert controller["docker_exec_allowed"] is False
    assert controller["docker_cp_allowed"] is False
    assert controller["compose_allowed"] is False
    assert controller["systemd_allowed"] is False
    assert controller["ssh_allowed"] is False
    assert controller["secret_values_in_argv"] is False

    transport = report["mqtt_control_transport"]
    assert transport["implementation"] == "paho_mqtt_in_process"
    assert transport["password_in_argv"] is False
    assert transport["password_in_environment"] is False
    assert transport["password_in_stdout"] is False
    assert transport["external_mqtt_cli_allowed"] is False


def test_rejects_live_mount_binding_drift(tmp_path: Path) -> None:
    executor, skeleton, gate = _fixture(tmp_path)
    document = json.loads(gate.read_text(encoding="utf-8"))
    document["mount_binding_sha256"] = "d" * 64
    _write_private(gate, document)

    with pytest.raises(
        BrokerIdentityProductionDriverContractError,
        match="mount binding does not match",
    ):
        build_production_driver_contract(
            executor,
            skeleton,
            gate,
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            skeleton_verifier=lambda _document: {
                "verified": True,
                "skeleton_sha256": SKELETON_SHA,
            },
        )


def test_rejects_executor_target_outside_mosquitto(tmp_path: Path) -> None:
    executor, skeleton, gate = _fixture(tmp_path)
    document = json.loads(executor.read_text(encoding="utf-8"))
    document["mutation_scope"]["allowed_container_targets"].append(
        "/config/.storage/core.config_entries"
    )
    _write_private(executor, document)

    with pytest.raises(
        BrokerIdentityProductionDriverContractError,
        match="target allowlist is invalid",
    ):
        build_production_driver_contract(
            executor,
            skeleton,
            gate,
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            skeleton_verifier=lambda _document: {
                "verified": True,
                "skeleton_sha256": SKELETON_SHA,
            },
        )


def test_rejects_tampered_driver_contract(tmp_path: Path) -> None:
    report = _build(tmp_path)
    report["execution_enabled"] = True
    with pytest.raises(
        BrokerIdentityProductionDriverContractError,
        match="fingerprint does not match",
    ):
        verify_production_driver_contract(report)


def test_execution_entrypoint_is_unconditionally_disabled() -> None:
    with pytest.raises(
        BrokerIdentityProductionDriverDisabledError,
        match="not installed",
    ):
        execute_production_driver_contract()


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_production_driver_contract.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "executor_contract_file" in completed.stdout
    assert "adapter_skeleton_file" in completed.stdout
    assert "live_mount_gate_file" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
