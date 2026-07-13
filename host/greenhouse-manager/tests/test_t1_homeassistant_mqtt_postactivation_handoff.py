from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_homeassistant_mqtt_postactivation_handoff import (
    HomeAssistantMqttPostactivationHandoffError,
    prepare_homeassistant_mqtt_postactivation_handoff,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


class FakeRunner:
    pass


def _write_json(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(mode)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    transaction_root = tmp_path / "greenhouse-m2-production-transactions-test"
    transaction_root.mkdir(mode=0o700)
    journal = transaction_root / "transaction-success/journal.json"
    _write_json(
        journal,
        {
            "schema": "gh.m2.t1-broker-identity-production-activation-journal/1",
            "phase": "committed",
            "transaction_id": "transaction-secret-id",
            "authorization_id": "authorization-secret-id",
            "bundle_sha256": "a" * 64,
            "adapter_contract_sha256": "b" * 64,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": False,
            "path_values_redacted": True,
        },
    )

    broker_handoff = tmp_path / "broker-handoff-secret-name"
    broker_handoff.mkdir(mode=0o700)
    _write_json(
        broker_handoff / "manifest.json",
        {
            "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
        },
    )

    ha_handoff = tmp_path / "ha-handoff-secret-name"
    ha_handoff.mkdir(mode=0o700)
    _write_json(
        ha_handoff / "manifest.json",
        {
            "schema": "gh.m2.t1-homeassistant-mqtt-reconfigure-handoff/1",
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "expected_retained_topic": TOPIC,
        },
    )

    postcheck = tmp_path / "postcheck-result.json"
    _write_json(postcheck, _ha_postcheck(), mode=0o644)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    return transaction_root, broker_handoff, ha_handoff, postcheck, output


def _ha_postcheck(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "gh.m2.t1-homeassistant-mqtt-reconfigure-postcheck/1",
        "read_only": True,
        "current_services_modified": False,
        "homeassistant_runtime": {"state": "running", "restart_count": 0},
        "runtime_healthy": True,
        "entry_fingerprint_unchanged": True,
        "storage_changed": True,
        "discovery_preserved": True,
        "field_matches": {
            "broker": True,
            "port": True,
            "username": True,
            "password": True,
            "client_id": True,
        },
        "reconfigure_verified": True,
        "rollback_required": False,
        "ready_for_live_apply": False,
    }
    report.update(overrides)
    return report


def _broker_audit(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "gh.m2.t1-broker-identity-postactivation-audit/1",
        "read_only": True,
        "checks": {
            "services_running_zero_restart": True,
            "dynamic_security_plugin_configured": True,
            "anonymous_compatibility_enabled": True,
        },
        "activation_verified": True,
        "rollback_required": False,
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "operator_action_authorized": False,
        "ready_for_live_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "current_services_modified": False,
    }
    report.update(overrides)
    return report


def _prepare(
    tmp_path: Path,
    *,
    broker_report: dict[str, Any] | None = None,
    live_postcheck: dict[str, Any] | None = None,
) -> tuple[dict[str, object], Path]:
    transaction_root, broker_handoff, ha_handoff, postcheck, output = _inputs(tmp_path)
    report = prepare_homeassistant_mqtt_postactivation_handoff(
        transaction_root,
        broker_handoff,
        ha_handoff,
        postcheck,
        output,
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        now=datetime(2026, 7, 13, 1, 0, tzinfo=UTC),
        token_factory=lambda: "bridge",
        broker_auditor=lambda *_args, **_kwargs: broker_report or _broker_audit(),
        homeassistant_auditor=lambda *_args, **_kwargs: live_postcheck
        or _ha_postcheck(),
    )
    return report, output / str(report["handoff_name"])


def test_prepare_creates_private_read_only_redacted_handoff(tmp_path: Path) -> None:
    report, root = _prepare(tmp_path)

    assert report["prepared"] is True
    assert report["ready_for_manager_migration_preparation"] is True
    assert report["ready_for_manager_migration_apply"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert root.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in root.iterdir())

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["direct_storage_edit_forbidden"] is True
    assert manifest["source_paths_included"] is False
    assert manifest["blockers"] == [
        "manager_identity_not_migrated",
        "node_credentials_not_delivered",
        "anonymous_closure_not_reviewed",
    ]
    serialized = json.dumps({"report": report, "manifest": manifest})
    for secret in (
        "transaction-secret-id",
        "authorization-secret-id",
        "broker-handoff-secret-name",
        "ha-handoff-secret-name",
        str(tmp_path),
    ):
        assert secret not in serialized
    assert len(str(report["manifest_sha256"])) == 64


def test_rejects_uncommitted_broker_transaction(tmp_path: Path) -> None:
    transaction_root, broker_handoff, ha_handoff, postcheck, output = _inputs(tmp_path)
    journal = transaction_root / "transaction-success/journal.json"
    document = json.loads(journal.read_text(encoding="utf-8"))
    document["phase"] = "rollback_completed"
    _write_json(journal, document)

    with pytest.raises(
        HomeAssistantMqttPostactivationHandoffError,
        match="exactly one committed",
    ):
        prepare_homeassistant_mqtt_postactivation_handoff(
            transaction_root,
            broker_handoff,
            ha_handoff,
            postcheck,
            output,
            expected_retained_topic=TOPIC,
            runner=FakeRunner(),
            broker_auditor=lambda *_args, **_kwargs: _broker_audit(),
            homeassistant_auditor=lambda *_args, **_kwargs: _ha_postcheck(),
        )


def test_rejects_failed_supplied_homeassistant_postcheck(tmp_path: Path) -> None:
    transaction_root, broker_handoff, ha_handoff, postcheck, output = _inputs(tmp_path)
    failed = _ha_postcheck(reconfigure_verified=False, rollback_required=True)
    _write_json(postcheck, failed, mode=0o644)

    with pytest.raises(
        HomeAssistantMqttPostactivationHandoffError,
        match="reconfigure_verified",
    ):
        prepare_homeassistant_mqtt_postactivation_handoff(
            transaction_root,
            broker_handoff,
            ha_handoff,
            postcheck,
            output,
            expected_retained_topic=TOPIC,
            runner=FakeRunner(),
            broker_auditor=lambda *_args, **_kwargs: _broker_audit(),
            homeassistant_auditor=lambda *_args, **_kwargs: _ha_postcheck(),
        )


def test_rejects_supplied_and_live_postcheck_drift(tmp_path: Path) -> None:
    drifted = _ha_postcheck(
        field_matches={
            "broker": True,
            "port": True,
            "username": True,
            "password": True,
            "client_id": False,
        }
    )
    with pytest.raises(
        HomeAssistantMqttPostactivationHandoffError,
        match="field verification is incomplete",
    ):
        _prepare(tmp_path, live_postcheck=drifted)


def test_rejects_failed_live_broker_audit(tmp_path: Path) -> None:
    failed = _broker_audit(activation_verified=False, rollback_required=True)
    with pytest.raises(
        HomeAssistantMqttPostactivationHandoffError,
        match="activation_verified",
    ):
        _prepare(tmp_path, broker_report=failed)


def test_rejects_retained_topic_mismatch(tmp_path: Path) -> None:
    transaction_root, broker_handoff, ha_handoff, postcheck, output = _inputs(tmp_path)

    with pytest.raises(
        HomeAssistantMqttPostactivationHandoffError,
        match="expected_retained_topic",
    ):
        prepare_homeassistant_mqtt_postactivation_handoff(
            transaction_root,
            broker_handoff,
            ha_handoff,
            postcheck,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/other/telemetry",
            runner=FakeRunner(),
            broker_auditor=lambda *_args, **_kwargs: _broker_audit(),
            homeassistant_auditor=lambda *_args, **_kwargs: _ha_postcheck(),
        )


def test_report_manifest_hash_matches_written_manifest(tmp_path: Path) -> None:
    report, root = _prepare(tmp_path)
    digest = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    assert report["manifest_sha256"] == digest
