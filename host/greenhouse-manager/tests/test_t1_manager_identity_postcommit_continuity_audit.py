from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_manager_identity_postcommit_continuity_audit as module

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
CREATED_AT = "2026-07-16T10:00:00Z"
COMMITTED_AT = "2026-07-16T10:05:00Z"
MANAGER_STARTED_AT = "2026-07-16T10:02:00Z"
PROTECTED_STARTED_AT = "2026-07-16T09:00:00Z"


def _write(path: Path, content: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def _workspace(tmp_path: Path) -> Path:
    workspace = (
        tmp_path
        / "greenhouse-m2-manager-production-transactions-v70"
        / "transaction-test"
    )
    workspace.mkdir(parents=True, mode=0o700)
    workspace.chmod(0o700)
    journal = {
        "schema": "gh.m2.t1-manager-identity-production-journal/1",
        "phase": "committed",
        "transaction_id": "transaction-test-123456",
        "authorization_id": "0" * 24,
        "created_at": CREATED_AT,
        "updated_at": COMMITTED_AT,
        "target": "greenhouse-manager",
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    execution = {
        "schema": "gh.m2.t1-manager-identity-production-execution-packet/1",
        "transaction_id": journal["transaction_id"],
        "authorization_id": journal["authorization_id"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "greenhouse_manager_image_preserved": True,
        "rollback_completed": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    _write(workspace / "journal.json", json.dumps(journal))
    _write(workspace / "execution-result.json", json.dumps(execution))
    return workspace


def _inspect(
    name: str,
    *,
    password_source: Path,
    password_env: str = "",
) -> dict[str, Any]:
    started_at = (
        MANAGER_STARTED_AT if name == "greenhouse-manager" else PROTECTED_STARTED_AT
    )
    config: dict[str, Any] = {"Env": []}
    mounts: list[dict[str, Any]] = []
    pid = 123 if name == "greenhouse-manager" else 200
    if name == "greenhouse-manager":
        config["Env"] = [
            "GH_MQTT_USERNAME=gh-manager-user",
            "GH_MQTT_CLIENT_ID=gh-manager-client",
            "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password",
            f"GH_MQTT_PASSWORD={password_env}",
        ]
        mounts = [
            {
                "Source": str(password_source),
                "Destination": "/run/secrets/gh_manager_mqtt_password",
                "RW": False,
            }
        ]
    return {
        "Id": name[0] * 64,
        "Image": "sha256:" + name[-1] * 64,
        "Name": f"/{name}",
        "RestartCount": 0,
        "Config": config,
        "Mounts": mounts,
        "State": {
            "Status": "running",
            "StartedAt": started_at,
            "Pid": pid,
        },
    }


def _payloads() -> dict[str, dict[str, Any]]:
    return {
        f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry": {
            "schema": "gh.telemetry/1",
            "node_id": NODE_ID,
            "measurements": {"air_temperature_c": 22.5},
        },
        f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability": {
            "node_id": NODE_ID,
            "state": "online",
        },
        DISCOVERY_TOPIC: {
            "device": {"identifiers": [f"gh_{SYSTEM_ID}_{NODE_ID}"]},
            "components": {
                "temperature": {"unique_id": f"{NODE_ID}_temperature"},
                "node_id": {"unique_id": f"{NODE_ID}_node_id"},
            },
            "state_topic": f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry",
            "availability": [
                {"topic": f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability"}
            ],
        },
    }


class Runner:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents
        self.payloads = _payloads()
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command[:2] == ("docker", "inspect"):
            return 0, json.dumps([self.documents[command[2]]])
        if command[:3] == ("docker", "logs", "--since"):
            output = "\n".join(
                (
                    f"Subscribed to gh/v1/{SYSTEM_ID}/ingress/node/+/telemetry",
                    f"Subscribed to gh/v1/{SYSTEM_ID}/state/+/telemetry",
                    f"Accepted telemetry node={NODE_ID} key=('boot', 1)",
                    (
                        "Published Home Assistant discovery "
                        f"node={NODE_ID} topic={DISCOVERY_TOPIC}"
                    ),
                )
            )
            return 0, output
        if command[:4] == ("docker", "exec", "mosquitto", "mosquitto_sub"):
            topic = command[-1]
            return 0, json.dumps(self.payloads[topic])
        raise AssertionError(f"unexpected command: {command}")


def _proc(tmp_path: Path) -> Path:
    proc = tmp_path / "proc"
    uid = os.getuid()
    gid = os.getgid()
    _write(
        proc / "123/status",
        f"Name:\tpython\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}\n",
        0o644,
    )
    _write(
        proc / "123/net/tcp",
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when "
        "retrnsmt   uid  timeout inode\n"
        "   0: 0100007F:C350 0100007F:075B 01 00000000:00000000 "
        "00:00000000 00000000 1000 0 12345\n",
        0o644,
    )
    return proc


def test_postcommit_continuity_audit_passes_without_mutation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    password = _write(tmp_path / "secrets/manager/password", "secret\n")
    documents = {
        name: _inspect(name, password_source=password)
        for name in ("greenhouse-manager", "mosquitto", "homeassistant")
    }
    runner = Runner(documents)

    result = module.build_manager_identity_postcommit_continuity_audit(
        workspace,
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        timeout_s=0.03,
        poll_interval_s=0.01,
        proc_root=_proc(tmp_path),
        runner=runner,
    )

    assert result["continuity_audit_passed"] is True
    assert result["current_services_modified"] is False
    assert result["transaction_files_modified"] is False
    assert result["runtime_manager_image_preserved"] is True
    assert result["runtime_manager_upgrade_performed"] is False
    assert result["preserve_anonymous"] is True
    assert result["authorization_reused"] is False


def test_postcommit_continuity_audit_rejects_inline_password(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    password = _write(tmp_path / "secrets/manager/password", "secret\n")
    documents = {
        name: _inspect(
            name,
            password_source=password,
            password_env="forbidden" if name == "greenhouse-manager" else "",
        )
        for name in ("greenhouse-manager", "mosquitto", "homeassistant")
    }

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="authenticated environment",
    ):
        module.build_manager_identity_postcommit_continuity_audit(
            workspace,
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            timeout_s=0.03,
            poll_interval_s=0.01,
            proc_root=_proc(tmp_path),
            runner=Runner(documents),
        )


def test_postcommit_continuity_audit_rejects_manager_recreated_after_commit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    password = _write(tmp_path / "secrets/manager/password", "secret\n")
    documents = {
        name: _inspect(name, password_source=password)
        for name in ("greenhouse-manager", "mosquitto", "homeassistant")
    }
    documents["greenhouse-manager"]["State"]["StartedAt"] = "2026-07-16T11:00:00Z"

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="not preserved",
    ):
        module.build_manager_identity_postcommit_continuity_audit(
            workspace,
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            timeout_s=0.03,
            poll_interval_s=0.01,
            proc_root=_proc(tmp_path),
            runner=Runner(documents),
        )
