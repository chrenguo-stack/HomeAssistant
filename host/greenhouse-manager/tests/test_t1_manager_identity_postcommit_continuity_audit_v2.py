from __future__ import annotations

import json
from pathlib import Path

import pytest

import greenhouse_manager.t1_manager_identity_postcommit_continuity_audit_v2 as module

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"


def _write_json(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    return path


def _materials(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "transactions" / "transaction-test"
    workspace.mkdir(parents=True, mode=0o700)
    workspace.chmod(0o700)
    journal = {
        "schema": "gh.m2.t1-manager-identity-production-journal/1",
        "phase": "committed",
        "transaction_id": "transaction-test-123456",
        "authorization_id": "0" * 24,
        "created_at": "2026-07-16T10:00:00Z",
        "updated_at": "2026-07-16T10:05:00Z",
        "target": "greenhouse-manager",
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    execution = {
        "schema": "gh.m2.t1-manager-target-production-execution/70",
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
    _write_json(workspace / "journal.json", journal)
    execution_path = _write_json(tmp_path / "external" / "execution-result.json", execution)
    return workspace, execution_path


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = {
        "greenhouse-manager": ("manager-id", "manager-image", "2026-07-16T10:02:00Z", 0, "running"),
        "mosquitto": ("mosquitto-id", "mosquitto-image", "2026-07-16T09:00:00Z", 0, "running"),
        "homeassistant": ("ha-id", "ha-image", "2026-07-16T09:00:00Z", 0, "running"),
    }
    manager = {
        "State": {
            "Status": "running",
            "StartedAt": "2026-07-16T10:02:00Z",
            "Pid": 123,
        }
    }
    monkeypatch.setattr(module, "_snapshot", lambda _runner: snapshot)
    monkeypatch.setattr(module, "_inspect", lambda _runner, _name: manager)
    monkeypatch.setattr(module, "_validate_manager_identity", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(module, "_stable_socket", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "_validate_retained", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "_validate_logs", lambda *_args, **_kwargs: None)

    def retained(_runner: object, topic: str, *, timeout_s: float) -> dict[str, object]:
        assert timeout_s > 0
        if topic.endswith("/telemetry"):
            return {"node_id": NODE_ID}
        if topic.endswith("/availability"):
            return {"node_id": NODE_ID, "state": "online"}
        return {"device": {"identifiers": [NODE_ID]}}

    monkeypatch.setattr(module, "_retained", retained)


def test_external_execution_result_binding_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, execution_path = _materials(tmp_path)
    _patch_runtime(monkeypatch)

    result = module.build_manager_identity_postcommit_continuity_audit(
        workspace,
        execution_path,
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        runner=object(),
    )

    assert result["continuity_audit_passed"] is True
    assert result["execution_result_file_modified"] is False
    assert result["authorization_reused"] is False
    assert result["production_execution_invoked"] is False


def test_external_execution_result_must_match_journal(tmp_path: Path) -> None:
    workspace, execution_path = _materials(tmp_path)
    document = json.loads(execution_path.read_text(encoding="utf-8"))
    document["transaction_id"] = "different-transaction"
    _write_json(execution_path, document)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="execution result binding",
    ):
        module.build_manager_identity_postcommit_continuity_audit(
            workspace,
            execution_path,
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=object(),
        )


def test_external_execution_result_must_be_private(tmp_path: Path) -> None:
    workspace, execution_path = _materials(tmp_path)
    execution_path.chmod(0o644)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="missing or unsafe",
    ):
        module.build_manager_identity_postcommit_continuity_audit(
            workspace,
            execution_path,
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=object(),
        )
