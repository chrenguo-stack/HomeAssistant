from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .t1_backup import BackupError, verify_backup
from .t1_migration_package import (
    MigrationPackageError,
    verify_migration_package,
)
from .t1_migration_readiness import CommandRunner, ReadinessError
from .t1_migration_readiness_live import build_live_readiness_report

STAGE_SCHEMA = "gh.m2.t1-auth-migration-stage/1"
STAGE_REPORT_SCHEMA = "gh.m2.t1-auth-migration-stage-report/1"
STAGE_MANIFEST_NAME = "stage-manifest.json"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")

ReadinessBuilder = Callable[..., dict[str, object]]
BackupVerifier = Callable[[str | Path], dict[str, Any]]
PackageVerifier = Callable[[str | Path], dict[str, Any]]


class MigrationStageError(RuntimeError):
    pass


def _json_text(document: Any) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256_path(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    if path.stat().st_mode & 0o077:
        raise MigrationStageError(
            "migration stage directory must not be accessible by group or other"
        )


def _ensure_private_parent(root: Path, parent: Path) -> None:
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = parent
    while True:
        current.chmod(0o700)
        if current == root:
            break
        if root not in current.parents:
            raise MigrationStageError("migration stage path escaped its root")
        current = current.parent


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _regular_private_source(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise MigrationStageError(f"{label} must be a regular non-symlink file")


def _record_file(
    root: Path,
    target: Path,
    records: list[dict[str, Any]],
    *,
    contains_secret: bool,
    source_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    relative = target.relative_to(root).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "size": target.stat().st_size,
        "sha256": _sha256_path(target),
        "mode": "0600",
        "contains_secret": contains_secret,
    }
    if source_path is not None:
        record["source_path"] = source_path
    if source_mode is not None:
        record["source_mode"] = source_mode
    records.append(record)
    return record


def _copy_private_file(
    root: Path,
    source: Path,
    relative: str,
    records: list[dict[str, Any]],
    *,
    contains_secret: bool,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    if not _safe_relative_path(relative):
        raise MigrationStageError("migration stage destination path is unsafe")
    _regular_private_source(source, "migration stage source")
    actual_sha256 = _sha256_path(source)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise MigrationStageError(
            f"migration stage source changed after readiness audit: {source}"
        )
    target = root / relative
    _ensure_private_parent(root, target.parent)
    with source.open("rb") as input_stream, target.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)
    target.chmod(0o600)
    return _record_file(
        root,
        target,
        records,
        contains_secret=contains_secret,
        source_path=str(source),
        source_mode=format(source.stat().st_mode & 0o777, "03o"),
    )


def _write_private_file(
    root: Path,
    relative: str,
    payload: str,
    records: list[dict[str, Any]],
    *,
    contains_secret: bool,
) -> dict[str, Any]:
    if not _safe_relative_path(relative):
        raise MigrationStageError("migration stage file path is unsafe")
    target = root / relative
    _ensure_private_parent(root, target.parent)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    target.chmod(0o600)
    return _record_file(
        root,
        target,
        records,
        contains_secret=contains_secret,
    )


def _require_source_binding(
    rollback_path: Path,
    rollback_manifest: dict[str, Any],
    package_manifest: dict[str, Any],
) -> None:
    source = package_manifest.get("source_rollback")
    if not isinstance(source, dict):
        raise MigrationStageError("migration package rollback binding is missing")
    expected = (
        rollback_path.name,
        _sha256_path(rollback_path),
        rollback_manifest.get("schema"),
        rollback_manifest.get("sources", {})
        .get("mosquitto", {})
        .get("image_id"),
    )
    actual = (
        source.get("archive"),
        source.get("sha256"),
        source.get("schema"),
        source.get("mosquitto_image_id"),
    )
    if actual != expected:
        raise MigrationStageError(
            "migration package does not match the selected rollback archive"
        )


def _require_ready_report(
    report: dict[str, object],
    rollback_path: Path,
    package_path: Path,
) -> None:
    required = {
        "schema": "gh.m2.t1-auth-migration-readiness/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "source_binding": True,
        "ready": True,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise MigrationStageError(
                f"live migration readiness requirement failed: {key}"
            )
    gates = report.get("gates")
    if not isinstance(gates, dict) or any(value is not True for value in gates.values()):
        raise MigrationStageError("live migration readiness gates are not all true")
    rollback = report.get("rollback")
    package = report.get("migration_package")
    if not isinstance(rollback, dict) or not isinstance(package, dict):
        raise MigrationStageError("live readiness source inventory is incomplete")
    if (
        rollback.get("path") != str(rollback_path)
        or rollback.get("sha256") != _sha256_path(rollback_path)
        or package.get("path") != str(package_path)
        or package.get("sha256") != _sha256_path(package_path)
    ):
        raise MigrationStageError("live readiness source binding changed")


def _deployment_inventory(report: dict[str, object]) -> list[dict[str, Any]]:
    compose = report.get("compose")
    if not isinstance(compose, dict):
        raise MigrationStageError("live readiness Compose inventory is missing")
    if (
        compose.get("source") != "docker_compose_labels"
        or compose.get("metadata_consistent") is not True
    ):
        raise MigrationStageError("live Compose deployment metadata is not ready")
    deployments = compose.get("deployments")
    if not isinstance(deployments, list) or not deployments:
        raise MigrationStageError("live Compose deployment inventory is empty")
    normalized: list[dict[str, Any]] = []
    for deployment in deployments:
        if not isinstance(deployment, dict):
            raise MigrationStageError("live Compose deployment entry is invalid")
        directory = Path(str(deployment.get("directory", ""))).expanduser().resolve()
        files = deployment.get("files")
        env = deployment.get("env")
        if not directory.is_absolute() or not isinstance(files, list) or not files:
            raise MigrationStageError("live Compose deployment paths are incomplete")
        if not isinstance(env, dict):
            raise MigrationStageError("live Compose environment observation is missing")
        normalized.append(
            {
                "projects": list(deployment.get("projects", [])),
                "containers": list(deployment.get("containers", [])),
                "directory": directory,
                "files": files,
                "env": env,
            }
        )
    return normalized


def _reject_active_output(
    output: Path,
    deployments: list[dict[str, Any]],
    secret_root: Path,
) -> None:
    active_roots = [secret_root, *(item["directory"] for item in deployments)]
    for active_root in active_roots:
        if output == active_root or output.is_relative_to(active_root):
            raise MigrationStageError(
                "migration stage output must not be inside an active path"
            )


def _extract_verified_package(
    package_path: Path,
    package_manifest: dict[str, Any],
    root: Path,
    records: list[dict[str, Any]],
) -> None:
    secret_by_path = {
        str(item.get("path")): bool(item.get("contains_secret"))
        for item in package_manifest.get("files", [])
        if isinstance(item, dict)
    }
    with tarfile.open(package_path, mode="r:gz") as package:
        for member in package.getmembers():
            if not member.isfile() or not _safe_relative_path(member.name):
                raise MigrationStageError(
                    "migration package contains an unsafe stage member"
                )
            stream = package.extractfile(member)
            if stream is None:
                raise MigrationStageError(
                    "migration package stage member cannot be read"
                )
            relative = f"payload/{member.name}"
            target = root / relative
            _ensure_private_parent(root, target.parent)
            with target.open("xb") as output_stream:
                shutil.copyfileobj(stream, output_stream)
            target.chmod(0o600)
            _record_file(
                root,
                target,
                records,
                contains_secret=secret_by_path.get(member.name, False),
                source_path=f"{package_path}::{member.name}",
                source_mode=format(member.mode & 0o777, "03o"),
            )


def _stage_deployments(
    root: Path,
    deployments: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    staged: list[dict[str, Any]] = []
    for index, deployment in enumerate(deployments, start=1):
        prefix = f"baseline/deployments/{index:02d}"
        staged_files: list[dict[str, Any]] = []
        for file_index, observation in enumerate(deployment["files"], start=1):
            if not isinstance(observation, dict) or observation.get("exists") is not True:
                raise MigrationStageError("live Compose configuration file is missing")
            source = Path(str(observation.get("path", ""))).expanduser().resolve()
            expected_sha = str(observation.get("sha256", ""))
            if not expected_sha:
                raise MigrationStageError("live Compose file checksum is missing")
            record = _copy_private_file(
                root,
                source,
                f"{prefix}/config-{file_index:02d}-{source.name}",
                records,
                contains_secret=True,
                expected_sha256=expected_sha,
            )
            staged_files.append(record)

        env = deployment["env"]
        staged_env: dict[str, Any] | None = None
        if env.get("exists") is True:
            source = Path(str(env.get("path", ""))).expanduser().resolve()
            expected_sha = str(env.get("sha256", ""))
            if env.get("mode") != "600" or not expected_sha:
                raise MigrationStageError(
                    "live Compose .env is not private or lacks a checksum"
                )
            staged_env = _copy_private_file(
                root,
                source,
                f"{prefix}/environment.env",
                records,
                contains_secret=True,
                expected_sha256=expected_sha,
            )
        elif env.get("exists") is not False:
            raise MigrationStageError("live Compose .env observation is invalid")

        staged.append(
            {
                "projects": deployment["projects"],
                "containers": deployment["containers"],
                "live_directory": str(deployment["directory"]),
                "configuration": staged_files,
                "environment": staged_env,
            }
        )
    return staged


def _readiness_binding(report: dict[str, object]) -> dict[str, Any]:
    broker = report.get("broker")
    containers = report.get("containers")
    if not isinstance(broker, dict) or not isinstance(containers, dict):
        raise MigrationStageError("live readiness runtime binding is incomplete")
    return {
        "schema": report.get("schema"),
        "generated_at": report.get("generated_at"),
        "broker_config_sha256": broker.get("live_config_sha256"),
        "anonymous_mode": broker.get("anonymous_mode"),
        "dynamic_security_configured": broker.get(
            "dynamic_security_configured"
        ),
        "expected_retained_topic": broker.get("expected_retained_topic"),
        "containers": {
            name: {
                "state": item.get("state"),
                "restart_count": item.get("restart_count"),
                "image_id": item.get("image_id"),
            }
            for name, item in containers.items()
            if isinstance(item, dict)
        },
    }


def create_migration_stage(
    rollback_archive: str | Path,
    migration_package: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    readiness_builder: ReadinessBuilder = build_live_readiness_report,
    backup_verifier: BackupVerifier = verify_backup,
    package_verifier: PackageVerifier = verify_migration_package,
) -> Path:
    rollback_path = Path(rollback_archive).expanduser().resolve()
    package_path = Path(migration_package).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    secret_root_path = Path(secret_root).expanduser().resolve()
    _regular_private_source(rollback_path, "rollback archive")
    _regular_private_source(package_path, "migration package")

    try:
        rollback_manifest = backup_verifier(rollback_path)
        package_manifest = package_verifier(package_path)
    except (BackupError, MigrationPackageError, OSError) as error:
        raise MigrationStageError(
            "verified rollback archive and migration package are required"
        ) from error
    _require_source_binding(rollback_path, rollback_manifest, package_manifest)

    report = readiness_builder(
        rollback_path,
        package_path,
        compose_directory=compose_directory,
        secret_root=secret_root_path,
        expected_retained_topic=expected_retained_topic,
        runner=runner,
        generated_at=now,
    )
    _require_ready_report(report, rollback_path, package_path)
    deployments = _deployment_inventory(report)
    _reject_active_output(output, deployments, secret_root_path)
    _private_directory(output)

    token = token_factory() if token_factory else secrets.token_hex(4)
    if _TOKEN_PATTERN.fullmatch(token) is None:
        raise MigrationStageError("migration stage token contains unsupported characters")
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    stage_name = (
        "greenhouse-t1-auth-stage-"
        + observed_at.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + token
    )
    destination = output / stage_name
    if destination.exists():
        raise MigrationStageError("migration stage destination already exists")

    with tempfile.TemporaryDirectory(prefix=".gh-auth-stage-", dir=output) as temporary:
        stage_root = Path(temporary) / "stage"
        stage_root.mkdir(mode=0o700)
        records: list[dict[str, Any]] = []

        package_copy = _copy_private_file(
            stage_root,
            package_path,
            f"source/{package_path.name}",
            records,
            contains_secret=True,
            expected_sha256=_sha256_path(package_path),
        )
        _extract_verified_package(
            package_path,
            package_manifest,
            stage_root,
            records,
        )
        staged_deployments = _stage_deployments(
            stage_root,
            deployments,
            records,
        )

        activation_plan = {
            "schema": "gh.m2.t1-auth-migration-stage-plan/1",
            "activation_enabled": False,
            "current_services_modified": False,
            "active_paths_modified": False,
            "requires_explicit_gate": True,
            "requires_fresh_backup_immediately_before_apply": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "planned_stages": [
                "capture_fresh_rollback_and_revalidate",
                "copy_private_secrets_to_active_root",
                "install_disabled_compose_overlays",
                "enable_dynamic_security_preserving_anonymous",
                "verify_provisioning_and_remove_bootstrap_admin",
                "migrate_manager_then_homeassistant_then_node",
                "observe_authenticated_stability",
                "close_anonymous_access_in_separate_gate",
            ],
            "active_secret_root": str(secret_root_path),
            "live_deployments": [
                {
                    "projects": item["projects"],
                    "containers": item["containers"],
                    "directory": str(item["directory"]),
                }
                for item in deployments
            ],
        }
        _write_private_file(
            stage_root,
            "activation-plan.json",
            _json_text(activation_plan),
            records,
            contains_secret=False,
        )
        _write_private_file(
            stage_root,
            "README.txt",
            "This private stage contains live MQTT credentials and deployment baselines.\n"
            "It must remain local to the T1 and must not be uploaded or committed.\n"
            "No active path was modified and activation-plan.json is disabled.\n"
            "A fresh rollback archive is still required immediately before any apply gate.\n"
            "Anonymous MQTT access must remain enabled through client migration.\n",
            records,
            contains_secret=False,
        )

        manifest = {
            "schema": STAGE_SCHEMA,
            "created_at": observed_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "classification": "secret-local-inactive-stage",
            "portable_off_host": False,
            "activation_enabled": False,
            "current_services_modified": False,
            "active_paths_modified": False,
            "fresh_backup_required_before_apply": True,
            "source_rollback": {
                "path": str(rollback_path),
                "archive": rollback_path.name,
                "sha256": _sha256_path(rollback_path),
                "schema": rollback_manifest.get("schema"),
            },
            "source_migration_package": {
                "path": str(package_path),
                "package": package_path.name,
                "sha256": _sha256_path(package_path),
                "schema": package_manifest.get("schema"),
                "staged_copy": package_copy["path"],
            },
            "readiness_binding": _readiness_binding(report),
            "deployments": staged_deployments,
            "files": records,
        }
        manifest_path = stage_root / STAGE_MANIFEST_NAME
        manifest_path.write_text(_json_text(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)

        os.replace(stage_root, destination)

    verify_migration_stage(destination)
    return destination


def verify_migration_stage(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o077:
        raise MigrationStageError("migration stage root is not a private directory")
    manifest_path = root / STAGE_MANIFEST_NAME
    _regular_private_source(manifest_path, "migration stage manifest")
    if manifest_path.stat().st_mode & 0o077:
        raise MigrationStageError("migration stage manifest permissions are unsafe")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise MigrationStageError("migration stage manifest is invalid") from error
    if manifest.get("schema") != STAGE_SCHEMA:
        raise MigrationStageError("migration stage schema is unsupported")
    for flag in (
        "activation_enabled",
        "current_services_modified",
        "active_paths_modified",
    ):
        if manifest.get(flag) is not False:
            raise MigrationStageError(f"migration stage safety flag is invalid: {flag}")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise MigrationStageError("migration stage file inventory is missing")
    expected: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise MigrationStageError("migration stage file inventory is invalid")
        relative = str(record.get("path", ""))
        if not _safe_relative_path(relative) or relative in expected:
            raise MigrationStageError("migration stage file path is invalid")
        expected[relative] = record

    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file()
    }
    if actual != set(expected) | {STAGE_MANIFEST_NAME}:
        raise MigrationStageError("migration stage inventory does not match files")
    for relative, record in expected.items():
        target = root / relative
        if target.is_symlink() or not target.is_file():
            raise MigrationStageError("migration stage contains an unsafe file")
        if target.stat().st_mode & 0o777 != 0o600:
            raise MigrationStageError("migration stage file permissions are unsafe")
        if target.stat().st_size != record.get("size"):
            raise MigrationStageError("migration stage file size verification failed")
        if _sha256_path(target) != record.get("sha256"):
            raise MigrationStageError("migration stage checksum verification failed")
    for directory in (item for item in root.rglob("*") if item.is_dir()):
        if directory.is_symlink() or directory.stat().st_mode & 0o077:
            raise MigrationStageError("migration stage directory permissions are unsafe")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a private inactive T1 MQTT migration stage from a ready live baseline."
        )
    )
    parser.add_argument("rollback_archive")
    parser.add_argument("migration_package")
    parser.add_argument("output_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
    )
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    args = parser.parse_args(argv)
    try:
        stage = create_migration_stage(
            args.rollback_archive,
            args.migration_package,
            args.output_directory,
            expected_retained_topic=args.expected_retained_topic,
            compose_directory=args.compose_directory,
            secret_root=args.secret_root,
        )
        manifest = verify_migration_stage(stage)
    except (
        BackupError,
        MigrationPackageError,
        MigrationStageError,
        ReadinessError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 inactive migration stage failed: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "schema": STAGE_REPORT_SCHEMA,
                "stage": stage.name,
                "source_package": manifest["source_migration_package"]["package"],
                "deployment_count": len(manifest["deployments"]),
                "file_count": len(manifest["files"]),
                "activation_enabled": False,
                "current_services_modified": False,
                "active_paths_modified": False,
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
