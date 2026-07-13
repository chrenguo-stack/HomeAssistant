from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_homeassistant_mqtt_legacy_evidence_bridge import (
    HomeAssistantMqttLegacyEvidenceBridgeError,
    prepare_homeassistant_mqtt_legacy_evidence_bridge,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


class FakeRunner:
    pass


def _write_json(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(mode)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_postcheck(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "gh.m2.t1-homeassistant-mqtt-ui-retry-postcheck/1",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_id": "legacy-authorization-secret",
        "operator_reported_submission": True,
        "operator_validation_required": True,
        "homeassistant_reconfigured": True,
        "mqtt_socket_established": True,
        "services_stable": True,
        "entry_identity_unchanged": True,
        "entry_semantic_changed": True,
        "entry_semantic_stable": True,
        "storage_changed": True,
        "storage_stable": True,
        "discovery_preserved": True,
        "field_matches": {
            "broker": True,
            "port": True,
            "username": True,
            "password": True,
            "client_id": True,
        },
        "postcheck_verified": True,
        "rollback_required": False,
        "current_services_modified": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
    }
    report.update(overrides)
    return report


def _current_postcheck(**overrides: Any) -> dict[str, Any]:
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


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    legacy = tmp_path / "legacy-homeassistant-handoff"
    legacy.mkdir(mode=0o700)
    values_path = legacy / "homeassistant/reconfigure-values.json"
    _write_json(
        values_path,
        {
            "schema": "gh.m2.homeassistant-mqtt-reconfigure-values/1",
            "official_config_flow_only": True,
            "broker": "127.0.0.1",
            "port": 1883,
            "username": "legacy-ha-user",
            "password": "legacy-password-secret",
            "client_id": "legacy-client-secret",
            "generation": 1,
            "preserve_discovery": True,
            "advanced_options_required": True,
        },
    )
    _write_json(
        legacy / "manifest.json",
        {
            "schema": "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1",
            "created_at": "2026-07-12T13:03:45Z",
            "classification": "sensitive-local-operator-handoff",
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_decision_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "broker_identity_activated": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "expected_retained_topic": TOPIC,
            "target": {
                "kind": "loopback",
                "fingerprint": "1" * 16,
                "port": 1883,
            },
            "pre_change": {
                "entry_fingerprint": "2" * 16,
                "storage_sha256": "3" * 64,
                "mqtt_semantic_sha256": "4" * 64,
            },
            "rollback": {
                "archive": "legacy-backup.tar.gz",
                "archive_sha256": "5" * 64,
                "homeassistant_checkpoint_sha256": "6" * 64,
                "official_reconfigure_values_present": True,
                "emergency_storage_restore_authorized": False,
            },
            "records": [
                {
                    "path": "homeassistant/reconfigure-values.json",
                    "sha256": _sha(values_path),
                    "size": values_path.stat().st_size,
                    "mode": 0o600,
                    "contains_secret": True,
                }
            ],
        },
    )
    postcheck = tmp_path / "legacy-postcheck.json"
    _write_json(postcheck, _legacy_postcheck())
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    return legacy, postcheck, output


def _prepare(
    tmp_path: Path,
    *,
    live_postcheck: dict[str, Any] | None = None,
) -> tuple[dict[str, object], Path]:
    legacy, postcheck, output = _inputs(tmp_path)

    def audit(normalized: Path, **_kwargs: object) -> dict[str, object]:
        manifest = json.loads((normalized / "manifest.json").read_text(encoding="utf-8"))
        values = json.loads(
            (normalized / "homeassistant/reconfigure-values.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["schema"] == "gh.m2.t1-homeassistant-mqtt-reconfigure-handoff/1"
        assert manifest["compatibility_source"]["schema"] == (
            "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1"
        )
        assert values["password"] == "legacy-password-secret"
        return live_postcheck or _current_postcheck()

    report = prepare_homeassistant_mqtt_legacy_evidence_bridge(
        legacy,
        postcheck,
        output,
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        now=datetime(2026, 7, 13, 4, 0, tzinfo=UTC),
        token_factory=lambda: "bridge",
        homeassistant_auditor=audit,
    )
    return report, output / str(report["bridge_name"])


def test_prepare_creates_private_bound_normalized_evidence(tmp_path: Path) -> None:
    report, root = _prepare(tmp_path)

    assert report["prepared"] is True
    assert report["ready_for_postactivation_handoff"] is True
    assert report["ready_for_manager_migration_apply"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert root.stat().st_mode & 0o077 == 0

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    normalized = root / "homeassistant-reconfigure-handoff"
    normalized_manifest = json.loads(
        (normalized / "manifest.json").read_text(encoding="utf-8")
    )
    postcheck = json.loads((root / "postcheck-result.json").read_text(encoding="utf-8"))
    assert manifest["ready_for_postactivation_handoff"] is True
    assert manifest["source_paths_included"] is False
    assert normalized_manifest["operator_action_required"] is True
    assert postcheck["reconfigure_verified"] is True
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in root.rglob("*")
        if path.is_file()
    )

    serialized = json.dumps({"report": report, "manifest": manifest})
    for secret in (
        "legacy-password-secret",
        "legacy-client-secret",
        "legacy-authorization-secret",
        str(tmp_path),
    ):
        assert secret not in serialized
    assert len(str(report["manifest_sha256"])) == 64


def test_rejects_tampered_legacy_record(tmp_path: Path) -> None:
    legacy, postcheck, output = _inputs(tmp_path)
    values = legacy / "homeassistant/reconfigure-values.json"
    values.write_text(values.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(
        HomeAssistantMqttLegacyEvidenceBridgeError,
        match="record size verification failed",
    ):
        prepare_homeassistant_mqtt_legacy_evidence_bridge(
            legacy,
            postcheck,
            output,
            expected_retained_topic=TOPIC,
            runner=FakeRunner(),
            homeassistant_auditor=lambda *_args, **_kwargs: _current_postcheck(),
        )


def test_rejects_incomplete_legacy_postcheck(tmp_path: Path) -> None:
    legacy, postcheck, output = _inputs(tmp_path)
    failed = _legacy_postcheck(
        field_matches={
            "broker": True,
            "port": True,
            "username": True,
            "password": True,
            "client_id": False,
        }
    )
    _write_json(postcheck, failed)

    with pytest.raises(
        HomeAssistantMqttLegacyEvidenceBridgeError,
        match="field verification is incomplete",
    ):
        prepare_homeassistant_mqtt_legacy_evidence_bridge(
            legacy,
            postcheck,
            output,
            expected_retained_topic=TOPIC,
            runner=FakeRunner(),
            homeassistant_auditor=lambda *_args, **_kwargs: _current_postcheck(),
        )


def test_rejects_failed_live_postcheck(tmp_path: Path) -> None:
    failed = _current_postcheck(reconfigure_verified=False, rollback_required=True)

    with pytest.raises(
        HomeAssistantMqttLegacyEvidenceBridgeError,
        match="reconfigure_verified",
    ):
        _prepare(tmp_path, live_postcheck=failed)
