from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_host_replica_adapters import (
    FAULT_PHASES,
    MARKER_SCHEMA,
    ManagerIdentityHostReplicaError,
    build_manager_host_replica_plan,
    run_manager_host_replica_fault_matrix,
    run_manager_host_replica_transaction,
)

USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
PASSWORD = "manager-password-secret"


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
    _write(path, _json(value) + "\n")


def _path_record(path: Path, source_path: str) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": source_path,
        "device": 1,
        "inode": 2,
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


def _preparation_and_template(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    preparation = tmp_path / "greenhouse-manager-migration-preparation-test"
    preparation.mkdir(mode=0o700)

    manager_env = preparation / "material/manager/manager.env"
    password = preparation / "material/manager/password"
    fragment = preparation / "material/manager/compose-secret-fragment.yaml"
    _write(
        manager_env,
        f"GH_MQTT_USERNAME={USERNAME}\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    _write(password, PASSWORD + "\n")
    _write(
        fragment,
        "services:\n"
        "  greenhouse-manager:\n"
        "    environment:\n"
        f"      GH_MQTT_USERNAME: {USERNAME}\n"
        "      GH_MQTT_PASSWORD_FILE: /run/secrets/gh_manager_mqtt_password\n"
        f"      GH_MQTT_CLIENT_ID: {CLIENT_ID}\n",
    )

    template = tmp_path / "gh-m2-manager-replica-template"
    template.mkdir(mode=0o700)
    manager_root = template / "manager"
    compose_root = manager_root / "compose"
    secret_root = manager_root / "secrets"
    compose_root.mkdir(parents=True, mode=0o700)
    secret_root.mkdir(mode=0o700)
    baseline_compose = compose_root / "docker-compose.manager.yml"
    _write(
        baseline_compose,
        "services:\n  greenhouse-manager:\n    image: manager:baseline\n",
    )
    baseline_env = compose_root / ".env"
    _write(baseline_env, "GH_SYSTEM_ID=greenhouse\n")

    container = {
        "container_id": "manager-container-id",
        "image_id": "sha256:manager-image-id",
        "image_ref": "greenhouse-manager:0.4.45",
        "started_at": "2026-07-13T00:00:00Z",
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": True,
        "legacy_client_id_fingerprint": _fingerprint("greenhouse-manager"),
        "mqtt_username_present": False,
        "mqtt_password_present": False,
        "mqtt_password_file_present": False,
    }
    compose = {
        "project": "t1",
        "working_dir": "/opt/HomeAssistant/infra/compose/t1",
        "config_files": [
            _path_record(
                baseline_compose,
                "/opt/HomeAssistant/infra/compose/t1/docker-compose.manager.yml",
            )
        ],
        "environment": _path_record(
            baseline_env,
            "/opt/HomeAssistant/infra/compose/t1/.env",
        ),
    }
    runtime = {
        "schema": "gh.m2.t1-manager-runtime-binding/1",
        "created_at": "2026-07-13T02:00:00Z",
        "container": container,
        "compose": compose,
        "target_secret_root": "/opt/greenhouse-secrets/mqtt",
        "target_password_file": "/opt/greenhouse-secrets/mqtt/manager/password",
        "read_only_capture": True,
        "current_services_modified": False,
    }
    runtime_path = preparation / "manager-runtime-binding.json"
    _write_json(runtime_path, runtime)
    plan_path = preparation / "transaction-plan.json"
    _write_json(
        plan_path,
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
            "node_credentials_delivered": False,
        },
    )
    runbook = preparation / "operator-runbook.txt"
    _write(runbook, "Preparation only.\n")
    records = [
        _record(manager_env, preparation, True),
        _record(password, preparation, True),
        _record(fragment, preparation, True),
        _record(runtime_path, preparation, True),
        _record(plan_path, preparation, False),
        _record(runbook, preparation, False),
    ]
    bindings = {
        "postactivation_manifest_sha256": "1" * 64,
        "migration_stage_manifest_sha256": "2" * 64,
        "manager_username_fingerprint": _fingerprint(USERNAME),
        "manager_client_id_fingerprint": _fingerprint(CLIENT_ID),
        "manager_runtime_binding_sha256": _sha(runtime_path),
        "manager_runtime_fingerprint": _fingerprint(_json(container)),
        "compose_binding_fingerprint": _fingerprint(_json(compose)),
    }
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
        "bindings": bindings,
        "records": records,
    }
    manifest_path = preparation / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(
        template / ".gh-m2-manager-host-replica.json",
        {
            "schema": MARKER_SCHEMA,
            "replica_only": True,
            "preparation_manifest_sha256": _sha(manifest_path),
            "manager_runtime_fingerprint": bindings["manager_runtime_fingerprint"],
            "compose_binding_fingerprint": bindings["compose_binding_fingerprint"],
        },
    )
    return preparation, template


def _inventory(root: Path) -> tuple[tuple[str, int, str], ...]:
    records: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            records.append((relative + "/", path.stat().st_mode & 0o777, "directory"))
        else:
            records.append((relative, path.stat().st_mode & 0o777, _sha(path)))
    return tuple(records)


class FakeDriver:
    def __init__(self, root: Path, *, audit_ok: bool = True) -> None:
        self.root = root
        self.audit_ok = audit_ok
        self.calls: list[str] = []

    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None:
        assert environment_file.read_text().startswith("GH_MQTT_USERNAME=")
        assert password_file.read_text().strip() == PASSWORD
        assert "greenhouse-manager" in overlay_file.read_text()
        self.calls.append("recreate")

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        assert username == USERNAME
        assert client_id == CLIENT_ID
        self.calls.append("identity")

    def verify_ingress_subscription(self) -> None:
        self.calls.append("subscription")

    def verify_canonical_publication(self) -> None:
        self.calls.append("canonical")

    def verify_discovery_publication(self) -> None:
        self.calls.append("discovery")

    def verify_reconnect(self) -> None:
        self.calls.append("reconnect")

    def postactivation_audit(self) -> dict[str, object]:
        self.calls.append("audit")
        return {
            "manager_identity_verified": self.audit_ok,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "rollback_required": not self.audit_ok,
            "replica_only": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def recreate_after_rollback(self) -> None:
        self.calls.append("rollback_recreate")

    def verify_legacy_anonymous_path(self) -> None:
        self.calls.append("legacy")


def _candidate(template: Path, parent: Path, name: str) -> Path:
    destination = parent / name
    shutil.copytree(template, destination, copy_function=shutil.copy2)
    return destination


def test_plan_binds_private_replica_and_keeps_live_apply_disabled(
    tmp_path: Path,
) -> None:
    preparation, template = _preparation_and_template(tmp_path)

    plan = build_manager_host_replica_plan(preparation, template)

    assert plan["replica_transaction_ready"] is True
    assert plan["replica_only"] is True
    assert plan["real_t1_target_allowed"] is False
    assert plan["docker_commands_available"] is False
    assert plan["authorization_claimed"] is False
    assert plan["apply_enabled"] is False
    assert plan["ready_for_manager_migration_apply"] is False
    assert plan["manager_identity_migrated"] is False
    assert plan["node_credentials_delivered"] is False
    assert plan["fault_phases"] == list(FAULT_PHASES)
    assert len(str(plan["plan_sha256"])) == 64


def test_success_transaction_verifies_manager_identity_and_publications(
    tmp_path: Path,
) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    candidate = _candidate(template, tmp_path, "success-candidate")
    driver = FakeDriver(candidate)

    report = run_manager_host_replica_transaction(
        preparation,
        candidate,
        driver=driver,
    )

    assert report["mutation_completed"] is True
    assert report["postactivation_verified"] is True
    assert report["rollback_completed"] is False
    assert report["manager_identity_migrated_in_replica"] is True
    assert report["manager_identity_migrated"] is False
    assert report["apply_enabled"] is False
    assert (candidate / "manager/secrets/manager/password").is_file()
    assert (candidate / "manager/compose/manager-auth.env").is_file()
    assert (candidate / "manager/compose/docker-compose.manager-auth.yml").is_file()
    assert driver.calls == [
        "recreate",
        "identity",
        "subscription",
        "canonical",
        "discovery",
        "reconnect",
        "audit",
    ]


@pytest.mark.parametrize(
    "phase",
    [item for item in FAULT_PHASES if item != "rollback_incomplete"],
)
def test_each_write_or_postwrite_fault_restores_complete_baseline(
    tmp_path: Path,
    phase: str,
) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    candidate = _candidate(template, tmp_path, f"candidate-{phase}")
    baseline = _inventory(candidate)

    report = run_manager_host_replica_transaction(
        preparation,
        candidate,
        driver=FakeDriver(candidate),
        fault_phase=phase,
    )

    assert report["fault_injected"] is True
    assert report["rollback_completed"] is True
    assert report["manager_identity_migrated_in_replica"] is False
    assert _inventory(candidate) == baseline


def test_postactivation_failure_forces_verified_rollback(tmp_path: Path) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    candidate = _candidate(template, tmp_path, "audit-failure")
    baseline = _inventory(candidate)

    report = run_manager_host_replica_transaction(
        preparation,
        candidate,
        driver=FakeDriver(candidate, audit_ok=False),
    )

    assert report["postactivation_verified"] is False
    assert report["rollback_completed"] is True
    assert _inventory(candidate) == baseline


def test_incomplete_rollback_is_terminal_and_explicit(tmp_path: Path) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    candidate = _candidate(template, tmp_path, "rollback-incomplete")

    with pytest.raises(
        ManagerIdentityHostReplicaError,
        match="rollback failed",
    ):
        run_manager_host_replica_transaction(
            preparation,
            candidate,
            driver=FakeDriver(candidate),
            fault_phase="rollback_incomplete",
        )


def test_fault_matrix_exercises_all_phases_and_preserves_template(
    tmp_path: Path,
) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    before = _inventory(template)

    report = run_manager_host_replica_fault_matrix(
        preparation,
        template,
        driver_factory=lambda root: FakeDriver(root),
    )

    assert report["success_rehearsal_passed"] is True
    assert report["all_faults_exercised"] is True
    assert report["rollback_failure_reported_explicitly"] is True
    assert report["fault_phase_count"] == len(FAULT_PHASES)
    assert report["template_immutable"] is True
    assert _inventory(template) == before


def test_plan_rejects_marker_or_material_drift(tmp_path: Path) -> None:
    preparation, template = _preparation_and_template(tmp_path)
    marker = template / ".gh-m2-manager-host-replica.json"
    document = json.loads(marker.read_text())
    document["preparation_manifest_sha256"] = "0" * 64
    _write_json(marker, document)

    with pytest.raises(ManagerIdentityHostReplicaError, match="marker binding"):
        build_manager_host_replica_plan(preparation, template)

    preparation, template = _preparation_and_template(tmp_path / "material-case")
    (preparation / "material/manager/password").write_text("tampered\n")
    with pytest.raises(ManagerIdentityHostReplicaError, match="record verification"):
        build_manager_host_replica_plan(preparation, template)


def test_plan_rejects_non_temporary_replica_target(tmp_path: Path) -> None:
    preparation, _template = _preparation_and_template(tmp_path)
    with pytest.raises(ManagerIdentityHostReplicaError, match="system temporary"):
        build_manager_host_replica_plan(
            preparation,
            "/opt/gh-m2-manager-replica-forbidden",
        )
