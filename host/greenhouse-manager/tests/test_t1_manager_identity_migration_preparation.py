from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_preparation import (
    ManagerIdentityMigrationPreparationError,
    prepare_manager_identity_migration,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
PASSWORD = "manager-password-secret"
PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"
PASSWORD_SOURCE = "/opt/greenhouse-secrets/mqtt/manager/password"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def _write_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    _write(path, json.dumps(value, separators=(",", ":")) + "\n", mode)


def _postactivation(tmp_path: Path) -> Path:
    root = tmp_path / "postactivation-secret-path"
    root.mkdir(mode=0o700)
    records: list[dict[str, object]] = []
    for name in (
        "broker-postactivation-audit.json",
        "homeassistant-postcheck-supplied.json",
        "homeassistant-postcheck-live.json",
        "operator-runbook.txt",
    ):
        path = root / name
        _write(path, f"{name}\n")
        records.append(
            {
                "path": name,
                "size": path.stat().st_size,
                "sha256": _sha(path),
                "contains_secret": False,
            }
        )
    _write_json(
        root / "manifest.json",
        {
            "schema": "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1",
            "read_only_live_services": True,
            "current_services_modified": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "broker_identity_activated": True,
            "homeassistant_authenticated": True,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_manager_migration_preparation": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": False,
            "source_paths_included": False,
            "records": records,
        },
    )
    return root


def _fragment(username: str = USERNAME, client_id: str = CLIENT_ID) -> str:
    return (
        "services:\n"
        "  greenhouse-manager:\n"
        "    environment:\n"
        f"      GH_MQTT_USERNAME: {username}\n"
        f"      GH_MQTT_PASSWORD_FILE: {PASSWORD_TARGET}\n"
        f"      GH_MQTT_CLIENT_ID: {client_id}\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {PASSWORD_SOURCE}\n"
        f"        target: {PASSWORD_TARGET}\n"
        "        read_only: true\n"
    )


def _stage(
    tmp_path: Path,
    compose_root: Path,
    compose_file: Path,
    secret_root: Path,
    *,
    env_file: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    root = tmp_path / "inactive-stage-secret-path"
    root.mkdir(mode=0o700)
    _write(
        root / "payload/manager/manager.env",
        f"GH_MQTT_USERNAME={USERNAME}\n"
        f"GH_MQTT_PASSWORD_FILE={PASSWORD_TARGET}\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    _write(root / "payload/manager/password", PASSWORD + "\n")
    _write(root / "payload/manager/compose-secret-fragment.yaml", _fragment())
    _write_json(
        root / "activation-plan.json",
        {
            "schema": "gh.m2.t1-auth-migration-stage-plan/1",
            "activation_enabled": False,
            "current_services_modified": False,
            "active_paths_modified": False,
            "requires_explicit_gate": True,
            "requires_fresh_backup_immediately_before_apply": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "active_secret_root": str(secret_root),
        },
    )
    deployment: dict[str, Any] = {
        "projects": ["t1"],
        "containers": ["greenhouse-manager"],
        "live_directory": str(compose_root),
        "configuration": [
            {
                "source_path": str(compose_file),
                "sha256": _sha(compose_file),
            }
        ],
        "environment": None,
    }
    if env_file is not None:
        deployment["environment"] = {
            "source_path": str(env_file),
            "sha256": _sha(env_file),
        }
    manifest = {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
        "readiness_binding": {"expected_retained_topic": TOPIC},
        "deployments": [deployment],
    }
    _write_json(root / "stage-manifest.json", manifest)
    return root, manifest


class FakeRunner:
    def __init__(
        self,
        compose_root: Path,
        compose_file: Path,
        *,
        state: str = "running",
        restart_count: int = 0,
        auth_username: str = "",
        auth_password_file: str = "",
        client_id: str = "greenhouse-manager",
        labels_complete: bool = True,
    ) -> None:
        labels = {
            "com.docker.compose.project": "t1",
            "com.docker.compose.project.working_dir": str(compose_root),
            "com.docker.compose.project.config_files": str(compose_file),
        }
        if not labels_complete:
            labels.pop("com.docker.compose.project.config_files")
        environment = [
            "GH_SYSTEM_ID=greenhouse",
            f"GH_MQTT_CLIENT_ID={client_id}",
        ]
        if auth_username:
            environment.append(f"GH_MQTT_USERNAME={auth_username}")
        if auth_password_file:
            environment.append(f"GH_MQTT_PASSWORD_FILE={auth_password_file}")
        self.document = [
            {
                "Id": "manager-container-id",
                "Image": "sha256:manager-image-id",
                "RestartCount": restart_count,
                "State": {"Status": state, "StartedAt": "2026-07-13T00:00:00Z"},
                "Config": {
                    "Image": "greenhouse-manager:0.4.43",
                    "Env": environment,
                    "Labels": labels,
                },
            }
        ]
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "inspect", "greenhouse-manager"):
            return 0, json.dumps(self.document)
        return 1, "unexpected command"


def _inputs(
    tmp_path: Path,
    *,
    env_present: bool = True,
    runner_kwargs: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path, Path, FakeRunner, dict[str, Any]]:
    postactivation = _postactivation(tmp_path)
    compose_root = tmp_path / "active-compose"
    compose_root.mkdir(mode=0o700)
    compose_file = compose_root / "docker-compose.manager.yml"
    _write(compose_file, "services:\n  greenhouse-manager:\n    image: manager\n", 0o600)
    env_file: Path | None = None
    if env_present:
        env_file = compose_root / ".env"
        _write(env_file, "GH_SYSTEM_ID=greenhouse\n", 0o600)
    secret_root = tmp_path / "active-secrets"
    stage, manifest = _stage(
        tmp_path,
        compose_root,
        compose_file,
        secret_root,
        env_file=env_file,
    )
    output = tmp_path / "preparations"
    output.mkdir(mode=0o700)
    runner = FakeRunner(compose_root, compose_file, **(runner_kwargs or {}))
    return postactivation, stage, output, secret_root, runner, manifest


def _prepare(
    tmp_path: Path,
    *,
    env_present: bool = True,
    runner_kwargs: dict[str, Any] | None = None,
) -> tuple[dict[str, object], Path, FakeRunner]:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(
        tmp_path,
        env_present=env_present,
        runner_kwargs=runner_kwargs,
    )
    report = prepare_manager_identity_migration(
        postactivation,
        stage,
        output,
        expected_retained_topic=TOPIC,
        secret_root=secret_root,
        runner=runner,
        now=datetime(2026, 7, 13, 2, 0, tzinfo=UTC),
        token_factory=lambda: "prepare",
        stage_verifier=lambda _path: manifest,
    )
    return report, output / str(report["preparation_name"]), runner


def test_prepare_creates_private_redacted_disabled_package(tmp_path: Path) -> None:
    report, root, runner = _prepare(tmp_path)

    assert report["prepared"] is True
    assert report["ready_for_manager_migration_authorization"] is True
    assert report["ready_for_manager_migration_apply"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert runner.commands == [("docker", "inspect", "greenhouse-manager")]
    assert root.stat().st_mode & 0o777 == 0o700
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in root.rglob("*")
        if path.is_file()
    )
    assert (root / "material/manager/password").read_text().strip() == PASSWORD
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["normal_report_contains_secrets"] is False
    assert manifest["ready_for_manager_migration_apply"] is False
    serialized = json.dumps(report)
    for protected in (USERNAME, CLIENT_ID, PASSWORD, str(tmp_path)):
        assert protected not in serialized


def test_prepare_accepts_absent_compose_env_when_stage_matches(tmp_path: Path) -> None:
    report, _root, _runner = _prepare(tmp_path, env_present=False)
    assert report["prepared"] is True


def test_rejects_postactivation_gate_drift(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    path = postactivation / "manifest.json"
    document = json.loads(path.read_text())
    document["homeassistant_authenticated"] = False
    _write_json(path, document)

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="homeassistant_authenticated",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_rejects_enabled_stage_plan(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    plan = stage / "activation-plan.json"
    document = json.loads(plan.read_text())
    document["activation_enabled"] = True
    _write_json(plan, document)

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="activation_enabled",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_rejects_inline_password_in_manager_environment(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    _write(
        stage / "payload/manager/manager.env",
        f"GH_MQTT_USERNAME={USERNAME}\n"
        f"GH_MQTT_PASSWORD_FILE={PASSWORD_TARGET}\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n"
        "GH_MQTT_PASSWORD=forbidden\n",
    )

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="unexpected key set",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_rejects_public_or_multiline_password(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    password = stage / "payload/manager/password"
    _write(password, "one\ntwo\n", 0o600)

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="exactly one",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )

    _write(password, PASSWORD + "\n", 0o644)
    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="mode 0600",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_rejects_noncanonical_compose_fragment(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    _write(
        stage / "payload/manager/compose-secret-fragment.yaml",
        _fragment().replace("read_only: true", "read_only: false"),
    )

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="not canonical",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


@pytest.mark.parametrize(
    ("runner_kwargs", "message"),
    [
        ({"state": "exited"}, "running with restart count zero"),
        ({"restart_count": 1}, "running with restart count zero"),
        ({"auth_username": USERNAME}, "already has MQTT authentication"),
        ({"labels_complete": False}, "Compose labels are incomplete"),
        ({"client_id": CLIENT_ID}, "already uses the staged MQTT client identity"),
    ],
)
def test_rejects_unsafe_live_manager_state(
    tmp_path: Path,
    runner_kwargs: dict[str, Any],
    message: str,
) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(
        tmp_path,
        runner_kwargs=runner_kwargs,
    )
    with pytest.raises(ManagerIdentityMigrationPreparationError, match=message):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_rejects_compose_or_environment_drift(tmp_path: Path) -> None:
    postactivation, stage, output, secret_root, runner, manifest = _inputs(tmp_path)
    compose_file = Path(runner.document[0]["Config"]["Labels"]["com.docker.compose.project.config_files"])
    compose_file.write_text("drift\n", encoding="utf-8")

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="configuration drifted",
    ):
        prepare_manager_identity_migration(
            postactivation,
            stage,
            output,
            expected_retained_topic=TOPIC,
            secret_root=secret_root,
            runner=runner,
            stage_verifier=lambda _path: manifest,
        )


def test_report_manifest_hash_matches_written_manifest(tmp_path: Path) -> None:
    report, root, _runner = _prepare(tmp_path)
    assert report["manifest_sha256"] == _sha(root / "manifest.json")
