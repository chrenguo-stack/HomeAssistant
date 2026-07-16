from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager import (
    t1_manager_identity_postcommit_continuity_audit_v3 as module,
)

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


def _resolve(
    tmp_path: Path,
    execution: dict[str, object],
    *,
    expected_source: bool,
) -> tuple[dict[str, object], str]:
    path = _write_json(tmp_path / "execution-result.json", execution)
    return module._execution_result(
        path,
        _journal(),
        expected_repository_sha=(REPOSITORY_SHA if expected_source else None),
        expected_manager_version=(MANAGER_VERSION if expected_source else None),
    )


def test_legacy_wrapper_without_transaction_id_uses_single_use_authorization(
    tmp_path: Path,
) -> None:
    journal = _journal()
    result, mode = _resolve(
        tmp_path,
        _legacy_execution(journal),
        expected_source=True,
    )

    assert result["authorization_id"] == journal["authorization_id"]
    assert mode == "legacy-single-use-authorization"


def test_legacy_wrapper_requires_exact_source_binding(tmp_path: Path) -> None:
    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="legacy manager execution wrapper binding",
    ):
        _resolve(
            tmp_path,
            _legacy_execution(_journal()),
            expected_source=False,
        )


def test_legacy_wrapper_rejects_wrong_repository_sha(tmp_path: Path) -> None:
    execution = _legacy_execution(_journal())
    execution["repository_sha"] = "f" * 40

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="legacy manager execution wrapper binding",
    ):
        _resolve(tmp_path, execution, expected_source=True)


def test_packet_result_keeps_transaction_id_binding(tmp_path: Path) -> None:
    journal = _journal()
    result, mode = _resolve(
        tmp_path,
        _packet_execution(journal),
        expected_source=False,
    )

    assert result["transaction_id"] == journal["transaction_id"]
    assert mode == "journal-transaction-id"


def test_packet_result_rejects_other_transaction(tmp_path: Path) -> None:
    execution = _packet_execution(_journal())
    execution["transaction_id"] = "different-transaction"

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="execution result binding",
    ):
        _resolve(tmp_path, execution, expected_source=False)


def test_external_execution_result_must_be_private(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "execution-result.json",
        _legacy_execution(_journal()),
    )
    path.chmod(0o644)

    with pytest.raises(
        module.ManagerPostcommitContinuityAuditError,
        match="missing or unsafe",
    ):
        module._execution_result(
            path,
            _journal(),
            expected_repository_sha=REPOSITORY_SHA,
            expected_manager_version=MANAGER_VERSION,
        )
