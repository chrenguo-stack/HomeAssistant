from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_migration_stage import (
    MigrationStageError,
    create_migration_stage,
    verify_migration_stage,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    path.chmod(mode)
    return path


def _package(
    path: Path,
    rollback: Path,
    rollback_manifest: dict[str, Any],
    *,
    password: str = "stage-secret-password",
) -> dict[str, Any]:
    files = {
        "manager/password": (password + "\n", True),
        "manager/manager.env": (
            "GH_MQTT_USERNAME=gh-manager\n"
            "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
            "GH_MQTT_CLIENT_ID=gh-manager\n",
            False,
        ),
        "README.txt": ("private package\n", False),
    }
    inventory = []
    for name, (payload, contains_secret) in files.items():
        encoded = payload.encode("utf-8")
        inventory.append(
            {
                "path": name,
                "size": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "mode": 0o600,
                "contains_secret": contains_secret,
            }
        )
    manifest = {
        "schema": "gh.m2.t1-auth-migration/1",
        "classification": "secret-local-migration",
        "portable_off_host": False,
        "apply_enabled": False,
        "current_services_modified": False,
        "source_rollback": {
            "archive": rollback.name,
            "sha256": _sha256(rollback),
            "schema": rollback_manifest["schema"],
            "mosquitto_image_id": rollback_manifest["sources"]["mosquitto"][
                "image_id"
            ],
        },
        "files": inventory,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, mode="w:gz") as archive:
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest_bytes)
        manifest_info.mode = 0o600
        archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for name, (payload, _contains_secret) in files.items():
            encoded = payload.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(encoded)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(encoded))
    path.chmod(0o600)
    return manifest


def _readiness(
    rollback: Path,
    package: Path,
    manager_dir: Path,
    broker_dir: Path,
) -> dict[str, object]:
    manager_compose = manager_dir / "docker-compose.manager.yml"
    manager_env = manager_dir / ".env"
    broker_compose = broker_dir / "docker-compose.yml"
    return {
        "schema": "gh.m2.t1-auth-migration-readiness/1",
        "generated_at": "2026-07-12T04:26:56.909Z",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "source_binding": True,
        "rollback": {
            "path": str(rollback),
            "sha256": _sha256(rollback),
        },
        "migration_package": {
            "path": str(package),
            "sha256": _sha256(package),
        },
        "containers": {
            "mosquitto": {
                "state": "running",
                "restart_count": 0,
                "image_id": "sha256:mosquitto-image",
            },
            "greenhouse_manager": {
                "state": "running",
                "restart_count": 0,
                "image_id": "sha256:manager-image",
            },
        },
        "broker": {
            "live_config_sha256": "broker-config-sha",
            "anonymous_mode": "true",
            "dynamic_security_configured": False,
            "expected_retained_topic": (
                "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
            ),
        },
        "compose": {
            "source": "docker_compose_labels",
            "metadata_consistent": True,
            "deployments": [
                {
                    "projects": ["t1"],
                    "containers": ["greenhouse-manager"],
                    "directory": str(manager_dir),
                    "files": [
                        {
                            "path": str(manager_compose),
                            "exists": True,
                            "mode": "644",
                            "sha256": _sha256(manager_compose),
                        }
                    ],
                    "env": {
                        "path": str(manager_env),
                        "exists": True,
                        "mode": "600",
                        "sha256": _sha256(manager_env),
                    },
                },
                {
                    "projects": ["ha_docker"],
                    "containers": ["mosquitto"],
                    "directory": str(broker_dir),
                    "files": [
                        {
                            "path": str(broker_compose),
                            "exists": True,
                            "mode": "644",
                            "sha256": _sha256(broker_compose),
                        }
                    ],
                    "env": {
                        "path": str(broker_dir / ".env"),
                        "exists": False,
                        "mode": None,
                        "sha256": None,
                    },
                },
            ],
        },
        "host_secret_root": {
            "path": str(manager_dir.parent / "active-secrets"),
            "exists": False,
            "safe": True,
        },
        "gates": {
            "first": True,
            "second": True,
        },
        "ready": True,
    }


def _inputs(tmp_path: Path) -> tuple[
    Path,
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, object],
    Path,
]:
    rollback = _write(tmp_path / "backups/rollback.tar.gz", "rollback-bytes")
    rollback_manifest = {
        "schema": "gh.m2.t1-backup/1",
        "sources": {
            "mosquitto": {"image_id": "sha256:mosquitto-image"},
        },
    }
    package = tmp_path / "packages/migration.tar.gz"
    package_manifest = _package(package, rollback, rollback_manifest)
    manager_dir = tmp_path / "live/manager"
    broker_dir = tmp_path / "live/broker"
    _write(
        manager_dir / "docker-compose.manager.yml",
        "services:\n  greenhouse-manager: {}\n",
        0o644,
    )
    _write(manager_dir / ".env", "LOCAL_ONLY=value\n", 0o600)
    _write(
        broker_dir / "docker-compose.yml",
        "services:\n  mosquitto: {}\n",
        0o644,
    )
    readiness = _readiness(
        rollback,
        package,
        manager_dir,
        broker_dir,
    )
    secret_root = tmp_path / "active-secrets"
    return (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    )


def test_creates_private_inactive_stage_for_two_deployments(
    tmp_path: Path,
) -> None:
    (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    ) = _inputs(tmp_path)
    output = tmp_path / "stages"
    output.mkdir(mode=0o700)

    stage = create_migration_stage(
        rollback,
        package,
        output,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        secret_root=secret_root,
        now=datetime(2026, 7, 12, 4, 30, tzinfo=UTC),
        token_factory=lambda: "feedface",
        readiness_builder=lambda *_args, **_kwargs: readiness,
        backup_verifier=lambda _path: rollback_manifest,
        package_verifier=lambda _path: package_manifest,
    )

    assert stage.name == "greenhouse-t1-auth-stage-20260712T043000Z-feedface"
    manifest = verify_migration_stage(stage)
    assert manifest["schema"] == "gh.m2.t1-auth-migration-stage/1"
    assert manifest["activation_enabled"] is False
    assert manifest["current_services_modified"] is False
    assert manifest["active_paths_modified"] is False
    assert manifest["fresh_backup_required_before_apply"] is True
    assert len(manifest["deployments"]) == 2
    assert (
        manifest["source_migration_package"]["sha256"]
        == _sha256(package)
    )
    assert (stage / f"source/{package.name}").is_file()
    assert (stage / "payload/manager/password").read_text(
        encoding="utf-8"
    ).strip() == "stage-secret-password"
    assert (
        stage
        / "baseline/deployments/01/config-01-docker-compose.manager.yml"
    ).is_file()
    assert (
        stage / "baseline/deployments/02/config-01-docker-compose.yml"
    ).is_file()
    assert (stage / "baseline/deployments/01/environment.env").is_file()
    assert not (stage / "baseline/deployments/02/environment.env").exists()

    manifest_text = (stage / "stage-manifest.json").read_text(
        encoding="utf-8"
    )
    assert "stage-secret-password" not in manifest_text
    assert "activation_enabled\":false" in manifest_text

    assert format(stage.stat().st_mode & 0o777, "03o") == "700"
    for item in stage.rglob("*"):
        expected_mode = "700" if item.is_dir() else "600"
        assert format(item.stat().st_mode & 0o777, "03o") == expected_mode


def test_rejects_output_inside_live_deployment(tmp_path: Path) -> None:
    (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    ) = _inputs(tmp_path)
    live_directory = Path(
        readiness["compose"]["deployments"][0]["directory"]  # type: ignore[index]
    )

    with pytest.raises(MigrationStageError, match="active path"):
        create_migration_stage(
            rollback,
            package,
            live_directory / "stage",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            secret_root=secret_root,
            readiness_builder=lambda *_args, **_kwargs: readiness,
            backup_verifier=lambda _path: rollback_manifest,
            package_verifier=lambda _path: package_manifest,
        )


def test_rejects_not_ready_baseline_before_staging(tmp_path: Path) -> None:
    (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    ) = _inputs(tmp_path)
    readiness["ready"] = False
    readiness["gates"]["compose_env_private"] = False  # type: ignore[index]
    output = tmp_path / "stages"

    with pytest.raises(MigrationStageError, match="ready"):
        create_migration_stage(
            rollback,
            package,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            secret_root=secret_root,
            readiness_builder=lambda *_args, **_kwargs: readiness,
            backup_verifier=lambda _path: rollback_manifest,
            package_verifier=lambda _path: package_manifest,
        )

    assert not output.exists()


def test_rejects_package_bound_to_another_rollback(tmp_path: Path) -> None:
    (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    ) = _inputs(tmp_path)
    package_manifest["source_rollback"]["sha256"] = "different"  # type: ignore[index]

    with pytest.raises(MigrationStageError, match="does not match"):
        create_migration_stage(
            rollback,
            package,
            tmp_path / "stages",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            secret_root=secret_root,
            readiness_builder=lambda *_args, **_kwargs: readiness,
            backup_verifier=lambda _path: rollback_manifest,
            package_verifier=lambda _path: package_manifest,
        )


def test_stage_verifier_detects_tampering(tmp_path: Path) -> None:
    (
        rollback,
        package,
        rollback_manifest,
        package_manifest,
        readiness,
        secret_root,
    ) = _inputs(tmp_path)
    output = tmp_path / "stages"
    output.mkdir(mode=0o700)
    stage = create_migration_stage(
        rollback,
        package,
        output,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        secret_root=secret_root,
        token_factory=lambda: "tamper01",
        readiness_builder=lambda *_args, **_kwargs: readiness,
        backup_verifier=lambda _path: rollback_manifest,
        package_verifier=lambda _path: package_manifest,
    )
    (stage / "payload/manager/password").write_text(
        "changed\n",
        encoding="utf-8",
    )

    with pytest.raises(MigrationStageError, match="size|checksum"):
        verify_migration_stage(stage)


def test_stage_module_imports_without_paho() -> None:
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

        from greenhouse_manager.t1_migration_stage import STAGE_SCHEMA

        assert STAGE_SCHEMA.endswith("/1")
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


def test_no_install_stage_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_migration_stage.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
