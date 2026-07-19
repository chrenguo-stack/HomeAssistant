from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from greenhouse_manager import h3_legacy_bootstrap_preflight as module


def _write_private_json(path: Path, document: dict[str, object]) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _static_pair(root: Path, suffix: str) -> tuple[Path, Path]:
    transaction = root / f"transaction-{suffix}"
    execution = root / f"execution-{suffix}"
    transaction.mkdir(mode=0o700)
    execution.mkdir(mode=0o700)
    transaction.chmod(0o700)
    execution.chmod(0o700)
    rollback: dict[str, object] = {
        "schema": "gh.m2.t1-manager-identity-fresh-rollback/1",
        "manager_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "compose_working_directory": str(root / "compose"),
        "manager_secret_root": str(root / "secrets"),
        "manager_password_target": str(root / "secrets" / "manager-password"),
    }
    _write_private_json(execution / "fresh-rollback-manifest.json", rollback)
    payload = json.dumps(
        rollback,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    archive = execution / "fresh-manager-rollback.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("rollback-manifest.json")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    archive.chmod(0o600)
    journal = {
        "schema": "gh.m2.t1-manager-identity-production-journal/1",
        "target": "greenhouse-manager",
        "phase": "rollback_completed",
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "fresh_rollback_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    _write_private_json(transaction / "journal.json", journal)
    return transaction, execution


def _readiness() -> dict[str, object]:
    return {
        "status": "gh_h3_readiness_succeeded",
        "gate_id": "H3_MANAGER_IDENTITY_FIELD_ACCEPTANCE",
        "implementation_ready": True,
        "ready_for_field_acceptance_preflight": True,
        "ready_for_live_apply": False,
        "live_action_authorized": False,
        "repository": {
            "head_sha": "b" * 40,
            "baseline_is_ancestor": True,
            "tracked_worktree_clean": True,
        },
    }


def test_inventory_selects_one_valid_static_pair_without_paths(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    _static_pair(tmp_path, "one")

    inventory = module.inspect_legacy_static_evidence(tmp_path)
    report = module.build_h3_legacy_bootstrap_preflight_report(
        _readiness(),
        inventory,
    )

    assert inventory.transaction_candidate_count == 1
    assert inventory.execution_candidate_count == 1
    assert len(inventory.valid_pairs) == 1
    assert report["ready_for_read_only_legacy_rollback_audit_scope_review"] is True
    assert report["next_action"] == "REVIEW_READ_ONLY_LEGACY_ROLLBACK_AUDIT_SCOPE"
    assert report["live_services_inspected"] is False
    assert report["broker_operation_performed"] is False
    assert report["production_probe_invoked"] is False
    assert report["production_execution_invoked"] is False
    assert report["operator_decision_recorded"] is False
    assert report["credential_material_read"] is False
    assert report["current_services_modified"] is False
    assert report["node_credentials_delivered"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False
    assert report["source_paths_included"] is False
    assert str(tmp_path) not in json.dumps(report)


def test_empty_inventory_requests_static_evidence_not_topic(tmp_path: Path) -> None:
    inventory = module.inspect_legacy_static_evidence(tmp_path)
    report = module.build_h3_legacy_bootstrap_preflight_report(
        _readiness(),
        inventory,
    )

    assert report["valid_static_pair_count"] == 0
    assert report["selected_static_pair"] is None
    assert report["next_action"] == "LOCATE_LEGACY_ROLLBACK_STATIC_EVIDENCE"


def test_duplicate_static_pairs_fail_closed(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    _static_pair(tmp_path, "one")
    _static_pair(tmp_path, "two")

    inventory = module.inspect_legacy_static_evidence(tmp_path)
    report = module.build_h3_legacy_bootstrap_preflight_report(
        _readiness(),
        inventory,
    )

    assert report["valid_static_pair_count"] > 1
    assert report["selected_static_pair"] is None
    assert report["ready_for_read_only_legacy_rollback_audit_scope_review"] is False
    assert report["next_action"] == ("RESOLVE_LEGACY_ROLLBACK_STATIC_EVIDENCE_AMBIGUITY")


def test_tampered_archive_is_rejected_without_diagnostic_leak(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    _transaction, execution = _static_pair(tmp_path, "bad")
    archive = execution / "fresh-manager-rollback.tar.gz"
    archive.write_bytes(b"not an archive")
    archive.chmod(0o600)

    inventory = module.inspect_legacy_static_evidence(tmp_path)

    assert inventory.valid_pairs == ()
    assert inventory.rejected_pair_count == 1


def test_search_root_symlink_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)

    with pytest.raises(
        module.H3LegacyBootstrapPreflightError,
        match="missing or unsafe",
    ):
        module.inspect_legacy_static_evidence(alias)
