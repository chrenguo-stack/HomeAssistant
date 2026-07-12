from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_client_migration_audit as audit
from greenhouse_manager.t1_client_migration_audit import (
    ClientMigrationAuditError,
    build_client_migration_audit,
)


class FakeRunner:
    def __init__(
        self,
        *,
        entries: dict[str, Any],
        containers: list[dict[str, str]] | None = None,
        state: str = "running",
        restart_count: int = 0,
    ) -> None:
        self.entries = entries
        self.containers = containers or [
            {
                "Names": "homeassistant",
                "Image": "ghcr.io/home-assistant/home-assistant:stable",
            }
        ]
        self.state = state
        self.restart_count = restart_count
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "ps", "-a", "--format", "{{json .}}"):
            return 0, "\n".join(json.dumps(item) for item in self.containers)
        if command == ("docker", "inspect", "homeassistant"):
            return (
                0,
                json.dumps(
                    [
                        {
                            "State": {"Status": self.state},
                            "RestartCount": self.restart_count,
                            "Image": "sha256:homeassistant-image",
                            "Config": {
                                "Image": (
                                    "ghcr.io/home-assistant/"
                                    "home-assistant:stable"
                                ),
                                "Labels": {
                                    "com.docker.compose.project": "ha_docker",
                                    "com.docker.compose.project.working_dir": (
                                        "/opt/ha_docker"
                                    ),
                                    "com.docker.compose.project.config_files": (
                                        "/opt/ha_docker/docker-compose.yml"
                                    ),
                                },
                            },
                            "Mounts": [
                                {
                                    "Type": "bind",
                                    "Source": "/opt/ha_docker/config",
                                    "Destination": "/config",
                                }
                            ],
                        }
                    ]
                ),
            )
        if command == (
            "docker",
            "exec",
            "homeassistant",
            "python3",
            "-c",
            "import homeassistant.const as c; print(c.__version__)",
        ):
            return 0, "2026.7.1\n"
        if command == (
            "docker",
            "exec",
            "homeassistant",
            "sh",
            "-c",
            "cat /config/.storage/core.config_entries",
        ):
            return 0, json.dumps(self.entries)
        return 1, "unexpected command"


def _write(path: Path, payload: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    path.chmod(mode)


def _stage(tmp_path: Path) -> tuple[
    Path,
    dict[str, Any],
    dict[str, object],
]:
    stage = tmp_path / "greenhouse-t1-auth-stage-test"
    stage.mkdir(mode=0o700)
    _write(
        stage / "activation-plan.json",
        json.dumps(
            {
                "activation_enabled": False,
                "current_services_modified": False,
                "active_paths_modified": False,
                "preserve_anonymous": True,
                "anonymous_closure_enabled": False,
                "requires_explicit_gate": True,
                "requires_fresh_backup_immediately_before_apply": True,
            }
        ),
    )
    _write(
        stage / "payload/manager/manager.env",
        "GH_MQTT_USERNAME=gh-manager\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        "GH_MQTT_CLIENT_ID=gh-manager\n",
    )
    _write(stage / "payload/manager/password", "manager-secret-password\n")
    _write(
        stage / "payload/manager/compose-secret-fragment.yaml",
        "services:\n  greenhouse-manager: {}\n",
    )
    _write(
        stage / "payload/homeassistant/mqtt-update.json",
        json.dumps(
            {
                "schema": "gh.m2.homeassistant-mqtt-update/1",
                "automatic_apply": False,
                "operation": "update_existing_mqtt_config_entry",
                "broker": "mosquitto",
                "port": 1883,
                "username": "gh-homeassistant",
                "password": "homeassistant-secret-password",
                "required_client_id": "gh-homeassistant",
                "generation": 1,
                "preserve_discovery": True,
            }
        ),
    )
    _write(
        stage / "payload/manifest.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-auth-migration/1",
                "node_id": "gh-n1-a9f2f8",
            }
        ),
    )
    _write(
        stage / "payload/node/gh-n1-a9f2f8/mqtt-credentials.json",
        json.dumps(
            {
                "schema": "gh.m2.node-mqtt-credentials/1",
                "automatic_apply": False,
                "node_id": "gh-n1-a9f2f8",
                "system_id": "greenhouse",
                "username": "gh-node",
                "password": "node-secret-password",
                "client_id": "gh-n1-a9f2f8",
                "generation": 1,
            }
        ),
    )
    manifest: dict[str, Any] = {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
        "source_rollback": {
            "path": "/opt/backups/rollback.tar.gz",
            "archive": "rollback.tar.gz",
            "sha256": "rollback-sha",
        },
        "source_migration_package": {
            "path": "/opt/packages/migration.tar.gz",
            "package": "migration.tar.gz",
            "sha256": "package-sha",
            "staged_copy": "source/migration.tar.gz",
        },
    }
    readiness: dict[str, object] = {
        "schema": "gh.m2.t1-auth-migration-readiness/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "source_binding": True,
        "ready": True,
        "gates": {
            "retained_topic_readable": True,
            "all_other_gates": True,
        },
    }
    return stage, manifest, readiness


def _entries(
    *,
    broker: str = "mosquitto",
    include_mqtt: bool = True,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if include_mqtt:
        entries.append(
            {
                "entry_id": "mqtt-entry-sensitive-id",
                "domain": "mqtt",
                "title": "MQTT",
                "source": "user",
                "disabled_by": None,
                "data": {
                    "broker": broker,
                    "port": 1883,
                    "username": "legacy-user",
                    "password": "legacy-password-secret",
                    "client_id": "legacy-client",
                },
                "options": {"discovery": True},
            }
        )
    return {"version": 1, "data": {"entries": entries}}


def _patch_stage_and_readiness(
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, Any],
    readiness: dict[str, object],
) -> None:
    monkeypatch.setattr(audit, "verify_migration_stage", lambda _path: manifest)
    monkeypatch.setattr(
        audit,
        "build_live_readiness_report",
        lambda *_args, **_kwargs: readiness,
    )


def test_audit_reports_only_redacted_client_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest, readiness = _stage(tmp_path)
    _patch_stage_and_readiness(monkeypatch, manifest, readiness)
    runner = FakeRunner(entries=_entries())

    report = build_client_migration_audit(
        stage,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=runner,
    )

    assert report["schema"] == "gh.m2.t1-auth-client-migration-audit/1"
    assert report["read_only"] is True
    assert report["apply_enabled"] is False
    assert report["current_services_modified"] is False
    assert report["audit_complete"] is True
    assert report["ready_for_live_apply"] is False
    assert report["manager"]["staged_material_complete"] is True
    assert report["homeassistant"]["runtime"]["state"] == "running"
    assert report["homeassistant"]["runtime"]["restart_count"] == 0
    assert report["homeassistant"]["version"] == "2026.7.1"
    mqtt = report["homeassistant"]["mqtt_config_entry"]
    assert mqtt["entry_present"] is True
    assert mqtt["broker_matches_expected"] is True
    assert mqtt["username_present"] is True
    assert mqtt["password_present"] is True
    assert mqtt["client_id_present"] is True
    assert len(mqtt["entry_id_fingerprint"]) == 16
    assert report["node"]["staged_material_complete"] is True
    assert report["node"]["live_delivery_path_verified"] is False
    assert "homeassistant_operator_reconfigure_required" in report[
        "activation_blockers"
    ]
    assert "node_credential_delivery_path_unverified" in report[
        "activation_blockers"
    ]

    serialized = json.dumps(report, ensure_ascii=False)
    for secret in (
        "legacy-password-secret",
        "homeassistant-secret-password",
        "manager-secret-password",
        "node-secret-password",
        "legacy-user",
        "legacy-client",
        "mqtt-entry-sensitive-id",
    ):
        assert secret not in serialized


def test_audit_reports_missing_mqtt_entry_as_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest, readiness = _stage(tmp_path)
    _patch_stage_and_readiness(monkeypatch, manifest, readiness)

    report = build_client_migration_audit(
        stage,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=FakeRunner(entries=_entries(include_mqtt=False)),
    )

    assert report["homeassistant"]["mqtt_config_entry"]["entry_present"] is False
    assert "homeassistant_mqtt_entry_not_ready" in report[
        "activation_blockers"
    ]


def test_audit_reports_broker_mismatch_without_exposing_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest, readiness = _stage(tmp_path)
    _patch_stage_and_readiness(monkeypatch, manifest, readiness)
    report = build_client_migration_audit(
        stage,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        expected_broker="mosquitto",
        runner=FakeRunner(entries=_entries(broker="192.0.2.10")),
    )

    mqtt = report["homeassistant"]["mqtt_config_entry"]
    assert mqtt["broker_matches_expected"] is False
    assert "homeassistant_broker_target_mismatch" in report[
        "activation_blockers"
    ]
    assert "192.0.2.10" not in json.dumps(report)


def test_audit_rejects_ambiguous_homeassistant_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest, readiness = _stage(tmp_path)
    _patch_stage_and_readiness(monkeypatch, manifest, readiness)
    runner = FakeRunner(
        entries=_entries(),
        containers=[
            {
                "Names": "homeassistant",
                "Image": "homeassistant/home-assistant",
            },
            {
                "Names": "homeassistant-old",
                "Image": "homeassistant/home-assistant",
            },
        ],
    )

    with pytest.raises(ClientMigrationAuditError, match="exactly one"):
        build_client_migration_audit(
            stage,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=runner,
        )


def test_audit_rejects_enabled_activation_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest, readiness = _stage(tmp_path)
    _patch_stage_and_readiness(monkeypatch, manifest, readiness)
    _write(
        stage / "activation-plan.json",
        json.dumps(
            {
                "activation_enabled": True,
                "current_services_modified": False,
                "active_paths_modified": False,
                "preserve_anonymous": True,
                "anonymous_closure_enabled": False,
                "requires_explicit_gate": True,
                "requires_fresh_backup_immediately_before_apply": True,
            }
        ),
    )

    with pytest.raises(ClientMigrationAuditError, match="activation_enabled"):
        build_client_migration_audit(
            stage,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=FakeRunner(entries=_entries()),
        )


def test_client_migration_audit_imports_without_paho() -> None:
    project = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPaho(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "paho" or fullname.startswith("paho."):
                    raise ModuleNotFoundError(
                        "blocked for no-install host test",
                        name=fullname,
                    )
                return None

        sys.meta_path.insert(0, BlockPaho())

        from greenhouse_manager.t1_client_migration_audit import AUDIT_SCHEMA

        assert AUDIT_SCHEMA.endswith("/1")
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


def test_no_install_client_audit_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_client_migration_audit.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
    assert "expected-broker" in completed.stdout
