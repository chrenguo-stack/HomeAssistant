from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_legacy_review_bridge import (
    OPERATOR_CONFIRMATION,
    ManagerIdentityLegacyReviewBridgeError,
    prepare_manager_identity_legacy_review_bridge,
    validate_legacy_manager_postrollback_audit,
    validate_manager_identity_legacy_review_bridge,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


def _legacy_audit(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "gh.m2.t1-manager-identity-postrollback-audit/1",
        "read_only": True,
        "rollback_audit_passed": False,
        "baseline_unavailable": True,
        "environment_baseline_unavailable": True,
        "directory_baseline_unavailable": True,
        "baseline_required_for_pass": True,
        "manual_recovery_required": False,
        "manual_review_required": True,
        "environment_restored": False,
        "environment_checks": {
            "gh_mqtt_password_file_restored": None,
            "gh_mqtt_password_restored": None,
            "gh_mqtt_username_restored": None,
        },
        "checks": {
            "anonymous_retained_path_readable": True,
            "auth_environment_exists": True,
            "auth_overlay_exists": True,
            "created_directory_targets_cleanup_complete": None,
            "homeassistant_unchanged": True,
            "journal_phase": True,
            "manager_image_preserved": True,
            "manager_restart_count_zero": True,
            "manager_running": True,
            "manager_stable_mqtt_socket": True,
            "mosquitto_unchanged": True,
            "password_mount_count": True,
            "password_target_exists": True,
            "rollback_completed": True,
            "rollback_failed": True,
        },
        "exact_target_checks": {
            "auth_environment_removed": True,
            "auth_overlay_removed": True,
            "created_directory_targets_clean": None,
            "password_mount_removed": True,
            "password_target_removed": True,
        },
        "broad_compose_directory_considered": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    report.update(overrides)
    return report


def _write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value)
    path.chmod(0o600)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    transaction = tmp_path / "transaction"
    execution = tmp_path / "execution-preparation"
    output = tmp_path / "output"
    for directory in (transaction, execution, output):
        directory.mkdir(mode=0o700)
    _write(transaction / "journal.json", b'{"phase":"rollback_completed"}\n')
    _write(execution / "fresh-rollback-manifest.json", b'{"legacy":true}\n')
    _write(execution / "fresh-manager-rollback.tar.gz", b"legacy-rollback-archive")
    return transaction, execution, output


def _prepare(tmp_path: Path) -> tuple[dict[str, object], Path]:
    transaction, execution, output = _fixture(tmp_path)

    def audit_builder(*_args: object, **_kwargs: object) -> dict[str, object]:
        return _legacy_audit()

    report = prepare_manager_identity_legacy_review_bridge(
        transaction,
        execution,
        output,
        expected_retained_topic=TOPIC,
        operator_confirmation=OPERATOR_CONFIRMATION,
        now=datetime(2026, 7, 14, 17, 0, tzinfo=UTC),
        token_factory=lambda: "review",
        audit_builder=audit_builder,
    )
    return report, output / str(report["bridge_name"])


def test_exact_legacy_manual_review_report_is_accepted() -> None:
    normalized = validate_legacy_manager_postrollback_audit(_legacy_audit())

    assert normalized["rollback_audit_passed"] is False
    assert normalized["manual_recovery_required"] is False
    assert normalized["manual_review_required"] is True


def test_prepare_creates_private_bound_decision_without_waiving_future_checks(
    tmp_path: Path,
) -> None:
    report, root = _prepare(tmp_path)

    assert report["prepared"] is True
    assert report["operator_decision_recorded"] is True
    assert report["legacy_baseline_gap_accepted"] is True
    assert report["rollback_audit_passed"] is False
    assert report["manual_review_resolved"] is True
    assert report["future_baseline_waiver_enabled"] is False
    assert report["ready_for_fresh_evidence_chain"] is True
    assert report["ready_for_production_execution"] is False
    assert report["authorization_created"] is False
    assert report["authorization_claimed"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert root.stat().st_mode & 0o077 == 0

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    decision = json.loads(
        (root / "operator-decision.json").read_text(encoding="utf-8")
    )
    audit = json.loads((root / "audit-report.json").read_text(encoding="utf-8"))
    assert manifest["rollback_audit_passed"] is False
    assert manifest["manual_review_resolved"] is True
    assert manifest["future_baseline_waiver_enabled"] is False
    assert decision["decision"] == (
        "accept_legacy_baseline_gap_for_fresh_evidence_chain_only"
    )
    assert audit == _legacy_audit()
    assert manifest["bindings"]["legacy_audit_sha256"] == hashlib.sha256(
        (json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in root.iterdir()
        if path.is_file()
    )

    serialized = json.dumps({"report": report, "manifest": manifest})
    assert str(tmp_path) not in serialized
    assert OPERATOR_CONFIRMATION not in serialized

    verified = validate_manager_identity_legacy_review_bridge(root)
    assert verified["verified"] is True
    assert verified["manifest_sha256"] == report["manifest_sha256"]
    assert verified["rollback_audit_passed"] is False
    assert verified["manual_review_resolved"] is True
    assert verified["future_baseline_waiver_enabled"] is False
    assert verified["ready_for_fresh_evidence_chain"] is True
    assert verified["ready_for_production_execution"] is False


def test_bridge_verifier_rejects_tampered_decision(tmp_path: Path) -> None:
    _report, root = _prepare(tmp_path)
    decision_path = root / "operator-decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["future_baseline_waiver_enabled"] = True
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    decision_path.chmod(0o600)

    with pytest.raises(
        ManagerIdentityLegacyReviewBridgeError,
        match="record verification failed",
    ):
        validate_manager_identity_legacy_review_bridge(root)


def test_bridge_verifier_rejects_unbound_extra_file(tmp_path: Path) -> None:
    _report, root = _prepare(tmp_path)
    extra = root / "unexpected.json"
    extra.write_text("{}\n", encoding="utf-8")
    extra.chmod(0o600)

    with pytest.raises(
        ManagerIdentityLegacyReviewBridgeError,
        match="file inventory",
    ):
        validate_manager_identity_legacy_review_bridge(root)


@pytest.mark.parametrize(
    "audit",
    (
        _legacy_audit(rollback_audit_passed=True, manual_review_required=False),
        _legacy_audit(manual_recovery_required=True, manual_review_required=False),
        _legacy_audit(environment_baseline_unavailable=False),
        _legacy_audit(directory_baseline_unavailable=False),
        _legacy_audit(current_services_modified=True),
    ),
)
def test_rejects_any_state_outside_the_exact_legacy_review_gap(
    audit: dict[str, Any],
) -> None:
    with pytest.raises(ManagerIdentityLegacyReviewBridgeError):
        validate_legacy_manager_postrollback_audit(audit)


def test_rejects_any_failed_definitive_check() -> None:
    audit = _legacy_audit()
    audit["checks"]["manager_stable_mqtt_socket"] = False

    with pytest.raises(
        ManagerIdentityLegacyReviewBridgeError,
        match="legacy postrollback checks",
    ):
        validate_legacy_manager_postrollback_audit(audit)


def test_rejects_confirmation_that_does_not_match_exact_decision(tmp_path: Path) -> None:
    transaction, execution, output = _fixture(tmp_path)

    with pytest.raises(
        ManagerIdentityLegacyReviewBridgeError,
        match="operator confirmation",
    ):
        prepare_manager_identity_legacy_review_bridge(
            transaction,
            execution,
            output,
            expected_retained_topic=TOPIC,
            operator_confirmation="A",
            audit_builder=lambda *_args, **_kwargs: _legacy_audit(),
        )


def test_cli_exposes_no_execution_or_authorization_action() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_manager_identity_migration_legacy_review_bridge.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "transaction_workspace" in completed.stdout
    assert "execution_preparation_directory" in completed.stdout
    assert "--operator-confirmation" in completed.stdout
    assert "--expected-retained-topic" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--apply" not in completed.stdout
