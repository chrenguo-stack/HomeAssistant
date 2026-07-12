from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    build_production_executor_contract,
    verify_production_executor_contract,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str | bytes, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    return path


def _request() -> dict[str, object]:
    return {
        "commands": [
            {
                "command": "setDefaultACLAccess",
                "acls": [
                    {"acltype": "publishClientSend", "allow": False},
                    {"acltype": "publishClientReceive", "allow": False},
                    {"acltype": "subscribe", "allow": False},
                    {"acltype": "unsubscribe", "allow": True},
                ],
            },
            {
                "command": "createRole",
                "rolename": "gh-legacy-anonymous-shadow",
            },
            {
                "command": "createGroup",
                "groupname": "gh-legacy-anonymous-shadow",
            },
            {
                "command": "setAnonymousGroup",
                "groupname": "gh-legacy-anonymous-shadow",
            },
            *(
                {
                    "command": "createClient",
                    "username": f"gh-{label}",
                    "password": f"secret-{label}",
                    "clientid": f"gh-{label}-client",
                    "roles": [{"rolename": f"gh-{label}-role", "priority": 100}],
                }
                for label in ("provisioning", "manager", "homeassistant", "node")
            ),
        ]
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    handoff = tmp_path / "greenhouse-broker-identity-handoff-test"
    stage = tmp_path / "greenhouse-t1-auth-stage-test"
    handoff.mkdir(mode=0o700)
    stage.mkdir(mode=0o700)

    stage_manifest: dict[str, Any] = {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
    }
    stage_manifest_path = _write(
        stage / "stage-manifest.json",
        json.dumps(stage_manifest, sort_keys=True),
    )
    rollback = _write(handoff / "rollback/fresh.tar.gz", b"fresh rollback")
    manifest = {
        "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
        "stage": {
            "name": stage.name,
            "manifest_sha256": _sha(stage_manifest_path),
            "broker_config_sha256": "a" * 64,
        },
        "fresh_rollback": {
            "path": "rollback/fresh.tar.gz",
            "sha256": _sha(rollback),
        },
    }
    _write(handoff / "manifest.json", json.dumps(manifest, sort_keys=True))
    _write(
        handoff / "activation-plan.json",
        json.dumps({"schema": "gh.m2.t1-broker-identity-activation-plan/1"}),
    )
    _write(
        handoff / "material/broker/dynsec-request.json",
        json.dumps(_request(), sort_keys=True),
    )
    _write(
        handoff / "material/broker/mosquitto-plugin.conf",
        "# exact production contract\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
        "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
        "plugin_opt_password_init_file /mosquitto/config/dynsec-password-init\n",
    )
    _write(
        handoff / "material/bootstrap/dynsec-password-init",
        "bootstrap-secret\n",
    )
    _write(
        handoff / "material/bootstrap/admin-client.conf",
        "-u admin\n-P bootstrap-secret\n",
    )
    _write(
        handoff / "material/provisioning/mosquitto-client.conf",
        "-u gh-provisioning\n-P provisioning-secret\n",
    )
    _write(
        handoff / "material/homeassistant/mqtt-update.json",
        json.dumps(
            {
                "username": "gh-homeassistant",
                "password": "homeassistant-secret",
                "required_client_id": "gh-homeassistant-client",
            }
        ),
    )
    return handoff, stage, stage_manifest


def _handoff_verifier(_path: Path) -> dict[str, object]:
    return {
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        "preserve_anonymous": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def _build(tmp_path: Path) -> tuple[dict[str, object], Path, Path, dict[str, Any]]:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    contract = build_production_executor_contract(
        handoff,
        stage,
        handoff_verifier=_handoff_verifier,
        stage_verifier=lambda _path: stage_manifest,
    )
    return contract, handoff, stage, stage_manifest


def test_builds_secret_free_disabled_production_executor_contract(
    tmp_path: Path,
) -> None:
    contract, _handoff, _stage, _stage_manifest = _build(tmp_path)

    assert contract["schema"] == (
        "gh.m2.t1-broker-identity-production-executor-contract/1"
    )
    assert contract["contract_review_complete"] is True
    assert contract["production_executor_available"] is False
    assert contract["execution_enabled"] is False
    assert contract["apply_enabled"] is False
    assert contract["ready_for_live_activation"] is False
    assert contract["current_services_modified"] is False
    assert contract["preserve_anonymous"] is True
    assert contract["anonymous_closure_enabled"] is False
    assert contract["homeassistant_contract"] == {
        "mode": "official_mqtt_ui_config_flow",
        "automatic_storage_write_forbidden": True,
        "automatic_reconfigure_forbidden": True,
    }
    assert contract["node_credential_delivery_contract"] == {
        "real_device_path_verified": False,
        "automatic_write_forbidden": True,
        "blocks_anonymous_closure": True,
    }
    encoded = json.dumps(contract, sort_keys=True)
    assert "bootstrap-secret" not in encoded
    assert "provisioning-secret" not in encoded
    assert "homeassistant-secret" not in encoded

    verified = verify_production_executor_contract(contract)
    assert verified["verified"] is True
    assert verified["production_executor_available"] is False


def test_contract_restricts_mutation_and_restart_scope(tmp_path: Path) -> None:
    contract, _handoff, _stage, _stage_manifest = _build(tmp_path)
    scope = contract["mutation_scope"]

    assert scope["container"] == "mosquitto"
    assert scope["restart_services"] == ["mosquitto"]
    assert scope["compose_recreate_forbidden"] is True
    assert scope["homeassistant_restart_forbidden"] is True
    assert scope["manager_restart_forbidden"] is True
    assert "/config/.storage" in scope["forbidden_targets"]
    assert "/mosquitto/data/dynamic-security.json" in scope[
        "allowed_container_targets"
    ]


def test_rejects_forbidden_dynamic_security_command(tmp_path: Path) -> None:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    request_path = handoff / "material/broker/dynsec-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["commands"].append({"command": "deleteClient", "username": "victim"})
    request_path.write_text(json.dumps(request), encoding="utf-8")
    request_path.chmod(0o600)

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="forbidden command",
    ):
        build_production_executor_contract(
            handoff,
            stage,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
        )


def test_rejects_anonymous_group_closure(tmp_path: Path) -> None:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    request_path = handoff / "material/broker/dynsec-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    for command in request["commands"]:
        if command["command"] == "setAnonymousGroup":
            command["groupname"] = ""
    request_path.write_text(json.dumps(request), encoding="utf-8")
    request_path.chmod(0o600)

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="does not preserve",
    ):
        build_production_executor_contract(
            handoff,
            stage,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
        )


def test_rejects_stage_binding_drift(tmp_path: Path) -> None:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    stage_path = stage / "stage-manifest.json"
    stage_path.write_text("{}\n", encoding="utf-8")
    stage_path.chmod(0o600)

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="binding has drifted",
    ):
        build_production_executor_contract(
            handoff,
            stage,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
        )


def test_rejects_fresh_rollback_drift(tmp_path: Path) -> None:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    rollback = handoff / "rollback/fresh.tar.gz"
    rollback.write_bytes(b"changed")
    rollback.chmod(0o600)

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="rollback fingerprint has drifted",
    ):
        build_production_executor_contract(
            handoff,
            stage,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
        )


def test_rejects_non_private_material(tmp_path: Path) -> None:
    handoff, stage, stage_manifest = _fixture(tmp_path)
    path = handoff / "material/homeassistant/mqtt-update.json"
    path.chmod(0o644)

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="not mode 0600",
    ):
        build_production_executor_contract(
            handoff,
            stage,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
        )


def test_contract_fingerprint_detects_tampering(tmp_path: Path) -> None:
    contract, _handoff, _stage, _stage_manifest = _build(tmp_path)
    contract["apply_enabled"] = True

    with pytest.raises(
        BrokerIdentityProductionExecutorContractError,
        match="fingerprint does not match",
    ):
        verify_production_executor_contract(contract)


def test_module_imports_without_paho() -> None:
    project = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPaho(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "paho" or fullname.startswith("paho."):
                    raise ModuleNotFoundError("blocked", name=fullname)
                return None

        sys.meta_path.insert(0, BlockPaho())
        from greenhouse_manager.t1_broker_identity_production_executor_contract import SCHEMA
        assert SCHEMA.endswith("/1")
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_production_executor_contract.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "handoff_directory" in completed.stdout
    assert "stage_directory" in completed.stdout
