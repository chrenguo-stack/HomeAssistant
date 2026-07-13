from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_authorization import (
    ManagerIdentityMigrationAuthorizationError,
    build_manager_identity_migration_authorization_request,
    create_manager_identity_migration_authorization,
    verify_manager_identity_migration_authorization,
)
from greenhouse_manager.t1_manager_identity_migration_preparation import (
    _fingerprint,
    _path_record,
)

USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
PASSWORD = "manager-password-secret"
NOW = datetime(2026, 7, 13, 3, 0, tzinfo=UTC)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, _json(value) + "\n")


def _runtime(
    compose_root: Path,
    compose_file: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    container = {
        "container_id": "manager-container-id",
        "image_id": "sha256:manager-image-id",
        "image_ref": "greenhouse-manager:0.4.44",
        "user_spec": "999:999",
        "started_at": "2026-07-13T00:00:00Z",
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": True,
        "legacy_client_id_fingerprint": _fingerprint("greenhouse-manager"),
        "mqtt_username_present": False,
        "mqtt_password_present": False,
        "mqtt_password_file_present": False,
        "manager_runtime_uid": 999,
        "manager_runtime_gid": 999,
        "manager_runtime_user_source": "container+image+isolated-candidate",
        "manager_runtime_image_id": "sha256:manager-image-id",
        "manager_runtime_user_spec": "999:999",
    }
    compose = {
        "project": "t1",
        "working_dir": str(compose_root),
        "config_files": [_path_record(compose_file)],
        "environment": None,
    }
    return container, compose


class FakeRunner:
    def __init__(
        self,
        compose_root: Path,
        compose_file: Path,
        *,
        started_at: str = "2026-07-13T00:00:00Z",
    ) -> None:
        self.compose_root = compose_root
        self.compose_file = compose_file
        self.started_at = started_at
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "inspect", "greenhouse-manager"):
            document = [
                {
                    "Id": "manager-container-id",
                    "Image": "sha256:manager-image-id",
                    "RestartCount": 0,
                    "State": {
                        "Status": "running",
                        "StartedAt": self.started_at,
                    },
                    "Config": {
                        "Image": "greenhouse-manager:0.4.44",
                        "User": "999:999",
                        "Env": [
                            "GH_SYSTEM_ID=greenhouse",
                            "GH_MQTT_CLIENT_ID=greenhouse-manager",
                        ],
                        "Labels": {
                            "com.docker.compose.project": "t1",
                            "com.docker.compose.project.working_dir": str(
                                self.compose_root
                            ),
                            "com.docker.compose.project.config_files": str(
                                self.compose_file
                            ),
                        },
                    },
                }
            ]
            return 0, json.dumps(document)
        if command == (
            "docker",
            "image",
            "inspect",
            "sha256:manager-image-id",
        ):
            return 0, json.dumps([{"Config": {"User": "999:999"}}])
        if command[:3] == ("docker", "run", "--rm"):
            return 0, "999:999\n"
        return 1, "unexpected command"


def _record(path: Path, root: Path, secret: bool) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha(path),
        "mode": "0600",
        "contains_secret": secret,
    }


def _preparation(tmp_path: Path) -> tuple[Path, Path, FakeRunner]:
    tmp_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    compose_root = tmp_path / "active-compose"
    compose_root.mkdir(mode=0o700)
    compose_file = compose_root / "docker-compose.manager.yml"
    _write(
        compose_file,
        "services:\n  greenhouse-manager:\n    image: manager\n",
    )
    secret_root = tmp_path / "active-secrets"
    secret_root.mkdir(mode=0o700)
    root = tmp_path / "greenhouse-manager-migration-preparation-test"
    root.mkdir(mode=0o700)

    manager_env = root / "material/manager/manager.env"
    password = root / "material/manager/password"
    fragment = root / "material/manager/compose-secret-fragment.yaml"
    _write(
        manager_env,
        f"GH_MQTT_USERNAME={USERNAME}\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    _write(password, PASSWORD + "\n")
    _write(fragment, "services:\n  greenhouse-manager: {}\n")

    container, compose = _runtime(compose_root, compose_file)
    runtime_binding = {
        "schema": "gh.m2.t1-manager-runtime-binding/1",
        "created_at": "2026-07-13T02:00:00Z",
        "container": container,
        "compose": compose,
        "target_secret_root": str(secret_root),
        "target_password_file": str(secret_root / "manager/password"),
        "read_only_capture": True,
        "current_services_modified": False,
    }
    runtime_path = root / "manager-runtime-binding.json"
    _write_json(runtime_path, runtime_binding)
    plan = {
        "schema": "gh.m2.t1-manager-identity-migration-transaction-plan/1",
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_apply": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "restart_scope": ["greenhouse-manager"],
        "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
        "node_credentials_delivered": False,
        "required_sequence": ["fresh_preflight", "rollback_on_failure"],
    }
    plan_path = root / "transaction-plan.json"
    _write_json(plan_path, plan)
    runbook = root / "operator-runbook.txt"
    _write(runbook, "Preparation only.\n")
    records = [
        _record(manager_env, root, True),
        _record(password, root, True),
        _record(fragment, root, True),
        _record(runtime_path, root, True),
        _record(plan_path, root, False),
        _record(runbook, root, False),
    ]
    manifest = {
        "schema": "gh.m2.t1-manager-identity-migration-preparation/1",
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "broker_identity_activated": True,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_authorization": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": True,
        "normal_report_contains_secrets": False,
        "normal_report_contains_source_paths": False,
        "bindings": {
            "postactivation_manifest_sha256": "1" * 64,
            "migration_stage_manifest_sha256": "2" * 64,
            "manager_username_fingerprint": _fingerprint(USERNAME),
            "manager_client_id_fingerprint": _fingerprint(CLIENT_ID),
            "manager_runtime_binding_sha256": _sha(runtime_path),
            "manager_runtime_fingerprint": _fingerprint(_json(container)),
            "compose_binding_fingerprint": _fingerprint(_json(compose)),
        },
        "records": records,
    }
    _write_json(root / "manifest.json", manifest)
    return (
        root,
        tmp_path / "greenhouse-m2-manager-authorizations-test",
        FakeRunner(compose_root, compose_file),
    )


def test_request_is_fresh_disabled_and_redacted(tmp_path: Path) -> None:
    preparation, _output, runner = _preparation(tmp_path)

    request = build_manager_identity_migration_authorization_request(
        preparation,
        runner=runner,
    )

    assert request["fresh_runtime_preflight_passed"] is True
    assert request["authorization_created"] is False
    assert request["operator_action_authorized"] is False
    assert request["ready_for_manager_migration_apply"] is False
    assert request["preserve_anonymous"] is True
    assert request["required_confirmation"].startswith(
        "AUTHORIZE-M2-MANAGER-MIGRATION:"
    )
    serialized = json.dumps(request)
    for protected in (USERNAME, CLIENT_ID, PASSWORD, str(tmp_path)):
        assert protected not in serialized
    assert runner.commands[0] == ("docker", "inspect", "greenhouse-manager")
    assert runner.commands[1] == (
        "docker",
        "image",
        "inspect",
        "sha256:manager-image-id",
    )
    assert runner.commands[2][:3] == ("docker", "run", "--rm")
    assert len(runner.commands) == 3


def test_create_and_verify_short_lived_single_use_authorization(
    tmp_path: Path,
) -> None:
    preparation, output, runner = _preparation(tmp_path)
    request = build_manager_identity_migration_authorization_request(
        preparation,
        runner=runner,
    )
    report = create_manager_identity_migration_authorization(
        preparation,
        output,
        confirmation=str(request["required_confirmation"]),
        runner=runner,
        now=NOW,
        token_factory=lambda: "managerauthorizationtoken123456",
    )

    authorization = output / str(report["authorization_file"])
    assert authorization.stat().st_mode & 0o777 == 0o600
    assert report["operator_action_authorized"] is True
    assert report["apply_enabled"] is False
    verified = verify_manager_identity_migration_authorization(
        authorization,
        preparation,
        runner=runner,
        now=NOW + timedelta(seconds=30),
    )
    assert verified["valid_now"] is True
    assert verified["single_use"] is True
    assert verified["consumed"] is False
    assert verified["ready_for_manager_migration_apply"] is False
    serialized = json.dumps(report)
    assert "managerauthorizationtoken123456" not in serialized
    assert PASSWORD not in serialized


def test_create_rejects_wrong_confirmation(tmp_path: Path) -> None:
    preparation, output, runner = _preparation(tmp_path)
    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="confirmation",
    ):
        create_manager_identity_migration_authorization(
            preparation,
            output,
            confirmation="wrong",
            runner=runner,
            now=NOW,
        )


def test_verify_rejects_expired_or_consumed_authorization(
    tmp_path: Path,
) -> None:
    preparation, output, runner = _preparation(tmp_path)
    request = build_manager_identity_migration_authorization_request(
        preparation,
        runner=runner,
    )
    report = create_manager_identity_migration_authorization(
        preparation,
        output,
        confirmation=str(request["required_confirmation"]),
        runner=runner,
        now=NOW,
        ttl_seconds=60,
        token_factory=lambda: "managerauthorizationtoken123456",
    )
    authorization = output / str(report["authorization_file"])
    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="not currently valid",
    ):
        verify_manager_identity_migration_authorization(
            authorization,
            preparation,
            runner=runner,
            now=NOW + timedelta(seconds=61),
        )

    document = json.loads(authorization.read_text())
    document["consumed"] = True
    _write_json(authorization, document)
    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="consumed",
    ):
        verify_manager_identity_migration_authorization(
            authorization,
            preparation,
            runner=runner,
            now=NOW + timedelta(seconds=30),
        )


def test_request_rejects_runtime_or_compose_drift(tmp_path: Path) -> None:
    preparation, _output, runner = _preparation(tmp_path)
    runner.started_at = "2026-07-13T00:01:00Z"
    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="runtime identity drifted",
    ):
        build_manager_identity_migration_authorization_request(
            preparation,
            runner=runner,
        )

    preparation, _output, runner = _preparation(tmp_path / "compose-case")
    runner.compose_file.write_text("drift\n", encoding="utf-8")
    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="Compose binding drifted",
    ):
        build_manager_identity_migration_authorization_request(
            preparation,
            runner=runner,
        )


def test_request_rejects_existing_active_manager_password(
    tmp_path: Path,
) -> None:
    preparation, _output, runner = _preparation(tmp_path)
    binding = json.loads(
        (preparation / "manager-runtime-binding.json").read_text()
    )
    password = Path(binding["target_password_file"])
    _write(password, PASSWORD + "\n")

    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="active password already exists",
    ):
        build_manager_identity_migration_authorization_request(
            preparation,
            runner=runner,
        )


def test_request_rejects_tampered_preparation_record(tmp_path: Path) -> None:
    preparation, _output, runner = _preparation(tmp_path)
    (preparation / "material/manager/password").write_text("tampered\n")

    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="record verification failed",
    ):
        build_manager_identity_migration_authorization_request(
            preparation,
            runner=runner,
        )
