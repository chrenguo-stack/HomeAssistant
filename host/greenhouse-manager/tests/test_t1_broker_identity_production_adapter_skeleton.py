from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_production_adapter_skeleton import (
    BrokerIdentityProductionAdapterDisabledError,
    BrokerIdentityProductionAdapterSkeletonError,
    build_production_adapter_skeleton,
    execute_production_adapter_skeleton,
    verify_production_adapter_skeleton,
)

CONTRACT_SHA = "a" * 64
MOUNT_SHA = "b" * 64


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _contract() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _gate() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-live-mount-gate/1",
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "checks": {
            "contract_verified_and_rebuilt": True,
            "fresh_rollback_image_bound": True,
            "live_config_bound": True,
        },
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


def _contract_verifier(contract: dict[str, object]) -> dict[str, object]:
    return {
        "schema": contract["schema"],
        "contract_sha256": contract["contract_sha256"],
        "verified": True,
    }


def _build(
    tmp_path: Path,
    *,
    contract: dict[str, object] | None = None,
    gate: dict[str, object] | None = None,
) -> dict[str, object]:
    contract_file = _write_private(
        tmp_path / "production-executor-contract.json",
        contract or _contract(),
    )
    gate_file = _write_private(
        tmp_path / "live-mount-gate.json",
        gate or _gate(),
    )
    return build_production_adapter_skeleton(
        contract_file,
        gate_file,
        contract_verifier=_contract_verifier,
    )


def test_builds_non_callable_adapter_inventory(tmp_path: Path) -> None:
    skeleton = _build(tmp_path)

    assert skeleton["schema"] == (
        "gh.m2.t1-broker-identity-production-adapter-skeleton/1"
    )
    assert skeleton["contract_sha256"] == CONTRACT_SHA
    assert skeleton["mount_binding_sha256"] == MOUNT_SHA
    assert skeleton["production_adapter_skeleton_available"] is True
    assert skeleton["production_executor_available"] is False
    assert skeleton["execution_enabled"] is False
    assert skeleton["apply_enabled"] is False
    assert skeleton["operator_action_authorized"] is False
    assert skeleton["ready_for_live_activation"] is False
    assert skeleton["current_services_modified"] is False
    assert skeleton["preserve_anonymous"] is True
    assert skeleton["anonymous_closure_enabled"] is False
    assert tuple(skeleton["adapters"]) == (
        "mutation",
        "postactivation",
        "rollback",
    )
    for adapter in skeleton["adapters"].values():
        assert adapter["installed"] is False
        assert adapter["callable"] is False
        assert adapter["host_write_capability"] is False
        assert adapter["docker_mutation_capability"] is False
        assert adapter["authorization_claim_capability"] is False
    assert verify_production_adapter_skeleton(skeleton)["verified"] is True


def test_rejects_live_gate_contract_drift(tmp_path: Path) -> None:
    gate = _gate()
    gate["contract_sha256"] = "c" * 64

    with pytest.raises(
        BrokerIdentityProductionAdapterSkeletonError,
        match="contract binding does not match",
    ):
        _build(tmp_path, gate=gate)


def test_rejects_non_passing_live_gate(tmp_path: Path) -> None:
    gate = _gate()
    gate["checks"] = {"live_config_bound": False}

    with pytest.raises(
        BrokerIdentityProductionAdapterSkeletonError,
        match="checks are not all passing",
    ):
        _build(tmp_path, gate=gate)


def test_rejects_tampered_skeleton_fingerprint(tmp_path: Path) -> None:
    skeleton = _build(tmp_path)
    skeleton["apply_enabled"] = True

    with pytest.raises(
        BrokerIdentityProductionAdapterSkeletonError,
        match="fingerprint does not match",
    ):
        verify_production_adapter_skeleton(skeleton)


def test_execute_path_is_unconditionally_absent() -> None:
    with pytest.raises(
        BrokerIdentityProductionAdapterDisabledError,
        match="adapters are not installed",
    ):
        execute_production_adapter_skeleton()


def test_no_install_launcher_has_no_execute_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_production_adapter_skeleton.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "contract_file" in completed.stdout
    assert "live_mount_gate_file" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--enable" not in completed.stdout
