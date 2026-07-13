from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_live_runtime_gate import (
    ManagerIdentityLiveRuntimeGateError,
    build_manager_identity_live_runtime_gate,
)
from greenhouse_manager.t1_manager_identity_migration_production_driver_contract import (
    build_manager_production_driver_contract,
)
from greenhouse_manager.t1_manager_identity_migration_production_transaction_adapter_contract import (
    build_manager_production_transaction_adapter_contract,
)

USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
LEGACY_CLIENT_ID = "greenhouse-manager"
PASSWORD = "manager-password-secret"
PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    _write(path, serialized + "\n")


def _path_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
        "size": stat.st_size,
        "sha256": _sha(path),
    }


def _record(path: Path, root: Path, secret: bool) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha(path),
        "mode": "0600",
        "contains_secret": secret,
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, FakeRunner, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp_path.chmod(0o700)
    compose_root = tmp_path / "active-compose"
    compose_root.mkdir(mode=0o700)
    compose_file = compose_root / "docker-compose.manager.yml"
    environment_file = compose_root / ".env"
    _write(
        compose_file,
        "services:\n"
        "  greenhouse-manager:\n"
        "    image: greenhouse-manager:n1\n"
        "    read_only: true\n",
    )
    _write(environment_file, "GH_SYSTEM_ID=greenhouse\n")

    secret_root = tmp_path / "active-secrets"
    secret_root.mkdir(mode=0o700)
    password_target = secret_root / "manager/password"

    container = {
        "container_id": "manager-container-id",
        "image_id": "sha256:manager-image-id",
        "image_ref": "greenhouse-manager:n1",
        "user_spec": "999:999",
        "started_at": "2026-07-13T00:00:00Z",
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": True,
        "legacy_client_id_fingerprint": _fingerprint(LEGACY_CLIENT_ID),
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
        "environment": _path_record(environment_file),
    }
    runtime = {
        "schema": "gh.m2.t1-manager-runtime-binding/1",
        "created_at": "2026-07-13T02:00:00Z",
        "container": container,
        "compose": compose,
        "target_secret_root": str(secret_root),
        "target_password_file": str(password_target),
        "manager_runtime_uid": 999,
        "manager_runtime_gid": 999,
        "manager_runtime_user_source": "container+image+isolated-candidate",
        "manager_runtime_image_id": "sha256:manager-image-id",
        "manager_runtime_user_spec": "999:999",
        "read_only_capture": True,
        "current_services_modified": False,
    }

    preparation = tmp_path / "greenhouse-manager-migration-preparation-test"
    preparation.mkdir(mode=0o700)
    manager_env = preparation / "material/manager/manager.env"
    password = preparation / "material/manager/password"
    fragment = preparation / "material/manager/compose-secret-fragment.yaml"
    runtime_path = preparation / "manager-runtime-binding.json"
    transaction_plan = preparation / "transaction-plan.json"
    runbook = preparation / "operator-runbook.txt"
    _write(
        manager_env,
        f"GH_MQTT_USERNAME={USERNAME}\n"
        f"GH_MQTT_PASSWORD_FILE={PASSWORD_TARGET}\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    _write(password, PASSWORD + "\n")
    _write(
        fragment,
        "services:\n"
        "  greenhouse-manager:\n"
        "    environment:\n"
        f"      GH_MQTT_USERNAME: {USERNAME}\n"
        f"      GH_MQTT_PASSWORD_FILE: {PASSWORD_TARGET}\n"
        f"      GH_MQTT_CLIENT_ID: {CLIENT_ID}\n",
    )
    _write_json(runtime_path, runtime)
    _write_json(
        transaction_plan,
        {
            "schema": "gh.m2.t1-manager-identity-migration-transaction-plan/1",
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_apply": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "restart_scope": ["greenhouse-manager"],
            "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
            "required_sequence": [
                "refresh_postactivation_and_runtime_bindings",
                "capture_fresh_manager_compose_and_secret_rollback",
                "create_short_lived_single_use_authorization",
                "atomically_install_manager_password",
                "apply_exact_manager_compose_overlay",
                "recreate_only_greenhouse_manager",
                "verify_manager_authenticated_client_id",
                "verify_ingress_subscription",
                "verify_canonical_and_discovery_publication",
                "verify_reconnect_and_existing_entities",
                "rollback_on_any_failure",
            ],
            "node_credentials_delivered": False,
        },
    )
    _write(runbook, "Preparation only.\n")
    records = [
        _record(manager_env, preparation, True),
        _record(password, preparation, True),
        _record(fragment, preparation, True),
        _record(runtime_path, preparation, True),
        _record(transaction_plan, preparation, False),
        _record(runbook, preparation, False),
    ]
    _write_json(
        preparation / "manifest.json",
        {
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
        },
    )

    adapter = build_manager_production_transaction_adapter_contract(preparation)
    adapter_path = tmp_path / "manager-production-adapter-contract.json"
    _write_json(adapter_path, adapter)
    driver = build_manager_production_driver_contract(adapter_path)
    driver_path = tmp_path / "manager-production-driver-contract.json"
    _write_json(driver_path, driver)
    runner = FakeRunner(compose_root, compose_file)
    return driver_path, preparation, runner, compose_file, password_target


class FakeRunner:
    def __init__(self, compose_root: Path, compose_file: Path) -> None:
        self.document: list[dict[str, Any]] = [
            {
                "Id": "manager-container-id",
                "Image": "sha256:manager-image-id",
                "RestartCount": 0,
                "State": {
                    "Status": "running",
                    "StartedAt": "2026-07-13T00:00:00Z",
                },
                "Config": {
                    "Image": "greenhouse-manager:n1",
                    "User": "999:999",
                    "Env": [
                        "GH_SYSTEM_ID=greenhouse",
                        "GH_MQTT_USERNAME=",
                        "GH_MQTT_PASSWORD=",
                        f"GH_MQTT_CLIENT_ID={LEGACY_CLIENT_ID}",
                    ],
                    "Labels": {
                        "com.docker.compose.project": "t1",
                        "com.docker.compose.project.working_dir": str(compose_root),
                        "com.docker.compose.project.config_files": str(compose_file),
                    },
                },
                "HostConfig": {
                    "ReadonlyRootfs": True,
                    "Privileged": False,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true"],
                },
                "Mounts": [],
            }
        ]
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "inspect", "greenhouse-manager"):
            return 0, json.dumps(self.document)
        if command == ("docker", "image", "inspect", "sha256:manager-image-id"):
            return 0, json.dumps([{"Config": {"User": "999:999"}}])
        if command[:3] == ("docker", "run", "--rm"):
            return 0, "999:999\n"
        return 1, "unexpected command"


def test_live_runtime_gate_is_read_only_bound_and_redacted(tmp_path: Path) -> None:
    driver, preparation, runner, _compose_file, password_target = _fixture(tmp_path)

    report = build_manager_identity_live_runtime_gate(
        driver,
        preparation,
        runner=runner,
    )

    assert len(runner.commands) == 3
    assert runner.commands[0] == ("docker", "inspect", "greenhouse-manager")
    assert runner.commands[1] == (
        "docker",
        "image",
        "inspect",
        "sha256:manager-image-id",
    )
    assert runner.commands[2][:5] == (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
    )
    assert report["read_only"] is True
    assert report["live_runtime_gate_ready"] is True
    assert report["ready_for_fresh_rollback_preparation"] is True
    assert report["production_manager_driver_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_manager_migration_apply"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert all(report["checks"].values())
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert str(password_target) not in serialized
    assert USERNAME not in serialized
    assert CLIENT_ID not in serialized
    assert PASSWORD not in serialized


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda runner: runner.document[0].update({"RestartCount": 1}),
            "running with restart count zero",
        ),
        (
            lambda runner: runner.document[0]["Config"]["Env"].append(
                "GH_MQTT_USERNAME=already-active"
            ),
            "already has active MQTT authentication",
        ),
        (
            lambda runner: runner.document[0]["HostConfig"].update(
                {"ReadonlyRootfs": False}
            ),
            "runtime security profile drifted",
        ),
        (
            lambda runner: runner.document[0]["Mounts"].append(
                {
                    "Type": "bind",
                    "Source": "/tmp/manager-password",
                    "Destination": PASSWORD_TARGET,
                    "RW": False,
                }
            ),
            "already mounted",
        ),
    ],
)
def test_live_runtime_gate_rejects_runtime_or_mount_drift(
    tmp_path: Path,
    mutation: Any,
    message: str,
) -> None:
    driver, preparation, runner, _compose_file, _password_target = _fixture(tmp_path)
    mutation(runner)

    with pytest.raises(ManagerIdentityLiveRuntimeGateError, match=message):
        build_manager_identity_live_runtime_gate(
            driver,
            preparation,
            runner=runner,
        )


def test_live_runtime_gate_rejects_compose_or_secret_activation(tmp_path: Path) -> None:
    driver, preparation, runner, compose_file, password_target = _fixture(tmp_path)
    compose_file.write_text(compose_file.read_text() + "# drift\n", encoding="utf-8")
    with pytest.raises(
        ManagerIdentityLiveRuntimeGateError,
        match="Compose binding drifted",
    ):
        build_manager_identity_live_runtime_gate(
            driver,
            preparation,
            runner=runner,
        )

    driver, preparation, runner, _compose_file, password_target = _fixture(
        tmp_path / "secret"
    )
    _write(password_target, "unexpected-active-secret\n")
    with pytest.raises(
        ManagerIdentityLiveRuntimeGateError,
        match="password target is already active",
    ):
        build_manager_identity_live_runtime_gate(
            driver,
            preparation,
            runner=runner,
        )


def test_live_runtime_gate_rejects_public_driver_contract(tmp_path: Path) -> None:
    driver, preparation, runner, _compose_file, _password_target = _fixture(tmp_path)
    driver.chmod(0o644)

    with pytest.raises(
        ManagerIdentityLiveRuntimeGateError,
        match="not mode 0600",
    ):
        build_manager_identity_live_runtime_gate(
            driver,
            preparation,
            runner=runner,
        )


def test_cli_exposes_no_execute_claim_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_manager_identity_migration_live_runtime_gate.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "driver_contract_file" in completed.stdout
    assert "preparation_directory" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
