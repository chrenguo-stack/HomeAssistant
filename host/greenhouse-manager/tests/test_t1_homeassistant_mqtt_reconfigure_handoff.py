from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_homeassistant_mqtt_reconfigure_handoff as handoff
from greenhouse_manager.t1_homeassistant_mqtt_reconfigure_handoff import (
    HomeAssistantMqttReconfigureHandoffError,
    audit_homeassistant_mqtt_reconfigure_postcheck,
    prepare_homeassistant_mqtt_reconfigure_handoff,
)
from greenhouse_manager.t1_homeassistant_mqtt_target_gate import BrokerCandidate


class FakeRunner:
    def __init__(self, storage: dict[str, Any]) -> None:
        self.storage = storage
        self.commands: list[tuple[str, ...]] = []

    def raw_storage(self) -> str:
        return json.dumps(self.storage, separators=(",", ":")) + "\n"

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "ps", "-a", "--format", "{{json .}}"):
            return 0, json.dumps(
                {"Names": "homeassistant", "Image": "homeassistant/home-assistant"}
            )
        if command == (
            "docker",
            "exec",
            "homeassistant",
            "sh",
            "-c",
            "cat /config/.storage/core.config_entries",
        ):
            return 0, self.raw_storage()
        if command == ("docker", "inspect", "homeassistant"):
            return 0, json.dumps([{"State": {"Status": "running"}, "RestartCount": 0}])
        return 1, "unexpected command"


def _storage(
    *,
    broker: str = "192.0.2.20",
    username: str = "",
    password: str = "",
    client_id: str = "",
    discovery: bool = True,
) -> dict[str, Any]:
    return {
        "version": 1,
        "data": {
            "entries": [
                {
                    "entry_id": "mqtt-entry-secret-id",
                    "domain": "mqtt",
                    "disabled_by": None,
                    "data": {
                        "broker": broker,
                        "port": 1883,
                        "username": username,
                        "password": password,
                        "client_id": client_id,
                    },
                    "options": {"discovery": discovery},
                }
            ]
        },
    }


def _stage(tmp_path: Path) -> Path:
    stage = tmp_path / "stage"
    path = stage / "payload/homeassistant/mqtt-update.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "gh.m2.homeassistant-mqtt-update/1",
                "automatic_apply": False,
                "operation": "update_existing_mqtt_config_entry",
                "broker": "mosquitto",
                "port": 1883,
                "username": "gh-homeassistant-user",
                "password": "homeassistant-password-secret-1234567890",
                "required_client_id": "gh-homeassistant-client",
                "generation": 1,
                "preserve_discovery": True,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return stage


def _target_report(runner: FakeRunner) -> dict[str, object]:
    raw = runner.raw_storage()
    entry_fp = hashlib.sha256(b"mqtt-entry-secret-id").hexdigest()[:16]
    return {
        "schema": "gh.m2.t1-homeassistant-mqtt-target-gate/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "prior_audit_complete": True,
        "target_model_ready": True,
        "selected_target_kind": "loopback",
        "selected_target_fingerprint": hashlib.sha256(b"127.0.0.1").hexdigest()[:16],
        "homeassistant_official_reconfigure": {
            "official_config_flow_only": True,
            "direct_storage_edit_forbidden": True,
            "automatic_apply": False,
            "operator_action_authorized": False,
            "staged_material_complete": True,
            "discovery_preserved": True,
            "retained_baseline_readable": True,
            "pre_change_entry_fingerprint": entry_fp,
            "pre_change_storage_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        },
        "activation_blockers": [
            "broker_identity_not_activated",
            "homeassistant_operator_reconfigure_required",
            "node_credential_delivery_path_unverified",
        ],
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
    }


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: FakeRunner,
    report: dict[str, object] | None = None,
) -> None:
    monkeypatch.setattr(
        handoff,
        "build_homeassistant_mqtt_target_gate",
        lambda *_args, **_kwargs: report or _target_report(runner),
    )

    def fake_create_backup(output: Path, **_kwargs: object) -> Path:
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = output / "greenhouse-t1-rollback-test.tar.gz"
        path.write_bytes(b"rollback")
        path.chmod(0o600)
        return path

    monkeypatch.setattr(handoff, "create_backup", fake_create_backup)
    monkeypatch.setattr(
        handoff,
        "verify_backup",
        lambda _path: {
            "schema": "gh.m2.t1-backup/1",
            "created_at": "2026-07-12T06:00:00.000Z",
        },
    )


def test_prepare_creates_private_redacted_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    runner = FakeRunner(_storage())
    _patch_dependencies(monkeypatch, tmp_path, runner)

    report = prepare_homeassistant_mqtt_reconfigure_handoff(
        stage,
        output,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        expected_target_fingerprint=hashlib.sha256(b"127.0.0.1").hexdigest()[:16],
        expected_entry_fingerprint=hashlib.sha256(b"mqtt-entry-secret-id").hexdigest()[
            :16
        ],
        expected_storage_sha256=hashlib.sha256(
            runner.raw_storage().encode()
        ).hexdigest(),
        runner=runner,
        now=datetime(2026, 7, 12, 6, 0, tzinfo=UTC),
        token_factory=lambda: "testtoken",
    )

    assert report["schema"] == "gh.m2.t1-homeassistant-mqtt-reconfigure-handoff/1"
    assert report["prepared"] is True
    assert report["operator_action_authorized"] is False
    assert report["ready_for_operator_reconfigure"] is False
    assert report["rollback_material_complete"] is True
    root = Path(str(report["handoff_directory"]))
    assert root.stat().st_mode & 0o777 == 0o700
    values = json.loads(
        (root / "homeassistant/reconfigure-values.json").read_text(encoding="utf-8")
    )
    assert values["broker"] == "127.0.0.1"
    assert values["username"] == "gh-homeassistant-user"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["rollback"]["emergency_storage_restore_authorized"] is False
    serialized = json.dumps(report)
    for secret in (
        "127.0.0.1",
        "gh-homeassistant-user",
        "homeassistant-password-secret-1234567890",
        "gh-homeassistant-client",
        "mqtt-entry-secret-id",
    ):
        assert secret not in serialized


def test_prepare_rejects_target_fingerprint_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    runner = FakeRunner(_storage())
    _patch_dependencies(monkeypatch, tmp_path, runner)

    with pytest.raises(
        HomeAssistantMqttReconfigureHandoffError, match="fingerprint has drifted"
    ):
        prepare_homeassistant_mqtt_reconfigure_handoff(
            stage,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            expected_target_fingerprint="0" * 16,
            runner=runner,
        )


def test_prepare_rejects_unexpected_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    runner = FakeRunner(_storage())
    target = _target_report(runner)
    target["activation_blockers"] = ["unexpected"]
    _patch_dependencies(monkeypatch, tmp_path, runner, target)

    with pytest.raises(
        HomeAssistantMqttReconfigureHandoffError, match="unexpected blockers"
    ):
        prepare_homeassistant_mqtt_reconfigure_handoff(
            stage,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=runner,
        )


def _prepared_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: FakeRunner,
) -> Path:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    _patch_dependencies(monkeypatch, tmp_path, runner)
    report = prepare_homeassistant_mqtt_reconfigure_handoff(
        stage,
        output,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        now=datetime(2026, 7, 12, 6, 0, tzinfo=UTC),
        token_factory=lambda: "postcheck",
    )
    return Path(str(report["handoff_directory"]))


def test_postcheck_verifies_matching_official_reconfigure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner(_storage())
    root = _prepared_handoff(tmp_path, monkeypatch, runner)
    runner.storage = _storage(
        broker="127.0.0.1",
        username="gh-homeassistant-user",
        password="homeassistant-password-secret-1234567890",
        client_id="gh-homeassistant-client",
    )

    report = audit_homeassistant_mqtt_reconfigure_postcheck(root, runner=runner)

    assert report["reconfigure_verified"] is True
    assert report["rollback_required"] is False
    assert report["runtime_healthy"] is True
    assert report["discovery_preserved"] is True
    assert all(report["field_matches"].values())


def test_postcheck_requires_rollback_on_password_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner(_storage())
    root = _prepared_handoff(tmp_path, monkeypatch, runner)
    runner.storage = _storage(
        broker="127.0.0.1",
        username="gh-homeassistant-user",
        password="wrong-password",
        client_id="gh-homeassistant-client",
    )

    report = audit_homeassistant_mqtt_reconfigure_postcheck(root, runner=runner)

    assert report["reconfigure_verified"] is False
    assert report["rollback_required"] is True
    assert report["field_matches"]["password"] is False
    assert "wrong-password" not in json.dumps(report)


def test_postcheck_requires_rollback_when_discovery_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner(_storage())
    root = _prepared_handoff(tmp_path, monkeypatch, runner)
    runner.storage = _storage(
        broker="127.0.0.1",
        username="gh-homeassistant-user",
        password="homeassistant-password-secret-1234567890",
        client_id="gh-homeassistant-client",
        discovery=False,
    )

    report = audit_homeassistant_mqtt_reconfigure_postcheck(root, runner=runner)

    assert report["reconfigure_verified"] is False
    assert report["rollback_required"] is True
    assert report["discovery_preserved"] is False


def test_candidate_binding_must_be_unique(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    runner = FakeRunner(_storage())
    _patch_dependencies(monkeypatch, tmp_path, runner)
    candidates = (
        BrokerCandidate("loopback_a", "loopback", "127.0.0.1"),
        BrokerCandidate("loopback_b", "loopback", "127.0.0.1"),
    )

    with pytest.raises(HomeAssistantMqttReconfigureHandoffError, match="one candidate"):
        prepare_homeassistant_mqtt_reconfigure_handoff(
            stage,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            candidates=candidates,
            runner=runner,
        )
