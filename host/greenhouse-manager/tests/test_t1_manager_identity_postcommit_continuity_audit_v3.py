from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager import (
    t1_manager_identity_postcommit_continuity_audit_v3 as module,
)

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
REPOSITORY_SHA = "1e992a6acba0ba7ac54b2adc7fa8e87f0a7bf1b3"
MANAGER_VERSION = "0.4.77"


def _write_json(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    return path


def _journal() -> dict[str, object]:
    return {
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


def _legacy_execution(journal: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-manager-target-production-execution/70",
        "status": "manager_identity_production_execution_succeeded",
        "repository_sha": REPOSITORY_SHA,
        "manager_version": MANAGER_VERSION,
        "authorization_id": journal["authorization_id"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "greenhouse_manager_image_preserved": True,
        "rollback_completed": False,
        "mosquitto_unchanged": True,
        "homeassistant_unchanged": True,
        "nodes_modified": False,
        "node_credentials_delivered": False,
        "current_services_modified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "bound_source_bundle_sha_exact": True,
        "bound_source_repository_sha_exact": True,
        "secret_values_included": False,
        "source_paths_included": False,
    }


def _packet_execution(journal: dict[str, object]) -> dict[str, object]:
    result = _legacy_execution(journal)
    result.update(
        {
            "schema": "gh.m2.t1-manager-identity-production-execution-packet/1",
            "transaction_id": journal["transaction_id"],
        }
    )
    return result


def _materials(
    tmp_path: Path,
    execution: dict[str, object],
) -> tuple[Path, Path]:
    workspace = tmp_path / "transactions" / "transaction-test"
    workspace.mkdir(parents=True, mode=0o700)
    workspace.chmod(0o700)
    _write_json(workspace / "journal.json", _journal())
    execution_path = _write_json(
        tmp_path / "external" / "execution-result.json",
        execution,
    )
    return workspace, execution_path


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = {
        "greenhouse-manager": (
            "manager-id",
            "manager-image",
            "2026-07-16T10:02:00Z",
            0,
            "running",
        ),
        "mosquitto": (
            "mosquitto-id",
            "mosquitto-image",
            "2026-07-16T09:00:00Z",
            0,
            "running",
        ),
        "homeassistant": (
            "ha-id",
            "ha-image",
            "2026-07-16T09:00:00Z",
            0,
            "running",
        ),
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
    monkeypatch.setattr(
        module,
        "_validate_manager_identity",
        lambda *_args, **_kwargs: 123,
    )
    monkeypatch.setattr(
        module,
        "_stable_socket",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        module,
        "_validate_retained",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        module,
        "_validate_logs",
        lambda *_args, **_kwargs: None,
    )

    def retained(
        _runner: object,
        topic: str,
        *,
        timeout_s: float,
    ) -> dict[str, object]:
        assert timeout_s > 0
        if topic.endswith("/telemetry"):
            return {"node_id": NODE_ID}
        if topic.endswith("/availability"):
            return {"node_id": NODE_ID, "state": "online"}
        return {"device": {"identifiers": [NODE_ID]}}

    monkeypatch.setattr(module, "_retained", retained)


def _run(
    workspace: Path,
    execution_path: Path,
    *,
    expected_source: bool,
) -> dict[str, object]:
    return module.build_manager_identity_postcommit_continuity_audit(
        workspace,
        execution_path,
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        expected_execution_repository_sha=(
            REPOSITORY_SHA if expected_source else None
        ),
        expected_execution_manager_version=(
            MANAGER_VERSION if expected_source else None
        ),
        runner=object(),
    )


def test_legacy_wrapper_without_transaction_id_is_bound_by_single_use_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal()
    workspace, execution_path = _materials(
        tmp_path,
        _legacy_execution(journal),
    )
    _patch_runtime(monkeypatch)

    result = _run(workspace, execution_path, expected_source=True)

    assert result["continuity_audit_passed"] is True
    assert result["execution_result_binding_mode"] == (
        "legacy-single-use-authorization"
    )
    assert result["authorization_reused"] is False
    assert result["production_execution_invoked"] is False


def test_legacy_wrapper_requires_exact_source_binding(tmp_path: Path) -> None:
    journal = _journal()
    workspace, execution_path = _materials(
        tmp_path,
        _legacy_execution(journal),
    )

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="legacy manager execution wrapper binding",
    ):
        _run(workspace, execution_path, expected_source=False)


def test_legacy_wrapper_rejects_wrong_repository_sha(tmp_path: Path) -> None:
    journal = _journal()
    execution = _legacy_execution(journal)
    execution["repository_sha"] = "f" * 40
    workspace, execution_path = _materials(tmp_path, execution)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="legacy manager execution wrapper binding",
    ):
        _run(workspace, execution_path, expected_source=True)


def test_packet_result_keeps_transaction_id_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = _journal()
    workspace, execution_path = _materials(
        tmp_path,
        _packet_execution(journal),
    )
    _patch_runtime(monkeypatch)

    result = _run(workspace, execution_path, expected_source=False)

    assert result["continuity_audit_passed"] is True
    assert result["execution_result_binding_mode"] == "journal-transaction-id"


def test_packet_result_rejects_other_transaction(tmp_path: Path) -> None:
    journal = _journal()
    execution = _packet_execution(journal)
    execution["transaction_id"] = "different-transaction"
    workspace, execution_path = _materials(tmp_path, execution)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="execution result binding",
    ):
        _run(workspace, execution_path, expected_source=False)


def test_external_execution_result_must_be_private(tmp_path: Path) -> None:
    journal = _journal()
    workspace, execution_path = _materials(
        tmp_path,
        _legacy_execution(journal),
    )
    execution_path.chmod(0o644)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="missing or unsafe",
    ):
        _run(workspace, execution_path, expected_source=True)
