from __future__ import annotations

import json
from pathlib import Path

from greenhouse_manager.t1_broker_identity_production_driver_contract import (
    build_production_driver_contract,
    verify_production_driver_contract,
)

CONTRACT_SHA = "a" * 64
SKELETON_SHA = "b" * 64
MOUNT_SHA = "c" * 64


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_verifier_accepts_json_round_tripped_driver_contract(tmp_path: Path) -> None:
    executor = _write_private(
        tmp_path / "executor.json",
        {
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
        },
    )
    skeleton = _write_private(
        tmp_path / "skeleton.json",
        {
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
        },
    )
    gate = _write_private(
        tmp_path / "gate.json",
        {
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
        },
    )

    report = build_production_driver_contract(
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
    serialized = json.loads(json.dumps(report, sort_keys=True))

    verified = verify_production_driver_contract(serialized)

    assert verified["verified"] is True
    assert verified["driver_contract_sha256"] == report["driver_contract_sha256"]
