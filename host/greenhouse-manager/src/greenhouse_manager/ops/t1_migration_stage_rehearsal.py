from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .t1_backup import BackupError
from .t1_migration_package import (
    MigrationPackageError,
    verify_migration_package,
)
from .t1_migration_rehearsal import (
    PACKAGE_REHEARSAL_SCHEMA,
    PackageMaterial,
    run_migration_package_rehearsal,
)
from .t1_migration_stage import (
    MigrationStageError,
    verify_migration_stage,
)
from .t1_shadow import CommandRunner, ShadowError, SubprocessRunner
from .t1_shadow_services import MosquittoRRTransport

STAGE_REHEARSAL_SCHEMA = "gh.m2.t1-auth-migration-stage-rehearsal/1"
_FAULT_MESSAGE = "intentional stage rehearsal fault after exact package request"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise MigrationStageError(f"{label} must be a regular non-symlink file")


def _source_observations(
    manifest: dict[str, Any],
) -> tuple[dict[str, object], ...]:
    observations: list[dict[str, object]] = []
    source_rollback = manifest.get("source_rollback")
    source_package = manifest.get("source_migration_package")
    if not isinstance(source_rollback, dict) or not isinstance(source_package, dict):
        raise MigrationStageError("stage source inventory is incomplete")

    rollback_path = Path(str(source_rollback.get("path", ""))).expanduser().resolve()
    package_path = Path(str(source_package.get("path", ""))).expanduser().resolve()
    for label, path, expected_sha in (
        ("rollback", rollback_path, source_rollback.get("sha256")),
        ("migration_package", package_path, source_package.get("sha256")),
    ):
        _regular_file(path, f"stage {label} source")
        actual_sha = _sha256_path(path)
        if not isinstance(expected_sha, str) or actual_sha != expected_sha:
            raise MigrationStageError(f"stage {label} source checksum changed")
        observations.append(
            {
                "label": label,
                "path": str(path),
                "mode": format(path.stat().st_mode & 0o777, "03o"),
                "size": path.stat().st_size,
                "sha256": actual_sha,
            }
        )

    records = manifest.get("files")
    if not isinstance(records, list):
        raise MigrationStageError("stage file inventory is missing")
    for record in records:
        if not isinstance(record, dict):
            raise MigrationStageError("stage file inventory is invalid")
        relative = str(record.get("path", ""))
        source_path = record.get("source_path")
        if not relative.startswith("baseline/") or not isinstance(source_path, str):
            continue
        path = Path(source_path).expanduser().resolve()
        _regular_file(path, "stage live baseline source")
        actual_sha = _sha256_path(path)
        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or actual_sha != expected_sha:
            raise MigrationStageError(
                f"stage live baseline source checksum changed: {path}"
            )
        observations.append(
            {
                "label": relative,
                "path": str(path),
                "mode": format(path.stat().st_mode & 0o777, "03o"),
                "size": path.stat().st_size,
                "sha256": actual_sha,
            }
        )
    return tuple(observations)


def _assert_source_observations_unchanged(
    before: tuple[dict[str, object], ...],
    after: tuple[dict[str, object], ...],
) -> None:
    if before != after:
        raise MigrationStageError(
            "stage rehearsal changed or observed drift in live source files"
        )


def _assert_container_absent(
    runner: CommandRunner,
    container_name: str,
) -> None:
    return_code, _output = runner.run(("docker", "inspect", container_name))
    if return_code == 0:
        raise ShadowError(
            f"stage rehearsal candidate container remained: {container_name}"
        )


def _fault_after_request(
    _runner: CommandRunner,
    _container_id: str,
    _staging: Path,
    _bootstrap_transport: MosquittoRRTransport,
    _material: PackageMaterial,
    _expected_retained_topic: str,
) -> dict[str, bool]:
    raise ShadowError(_FAULT_MESSAGE)


def run_migration_stage_rehearsal(
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    stage_root = Path(stage_directory).expanduser().resolve()
    manifest = verify_migration_stage(stage_root)
    manifest_path = stage_root / "stage-manifest.json"
    manifest_sha_before = _sha256_path(manifest_path)
    sources_before = _source_observations(manifest)

    activation_plan_path = stage_root / "activation-plan.json"
    try:
        activation_plan = json.loads(
            activation_plan_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationStageError("stage activation plan is invalid") from error
    if (
        activation_plan.get("activation_enabled") is not False
        or activation_plan.get("current_services_modified") is not False
        or activation_plan.get("active_paths_modified") is not False
        or activation_plan.get("preserve_anonymous") is not True
        or activation_plan.get("anonymous_closure_enabled") is not False
    ):
        raise MigrationStageError("stage activation plan safety flags are invalid")

    source_rollback = manifest["source_rollback"]
    source_package = manifest["source_migration_package"]
    rollback_path = Path(str(source_rollback["path"])).expanduser().resolve()
    staged_package_path = stage_root / str(source_package["staged_copy"])
    _regular_file(staged_package_path, "staged migration package")
    if _sha256_path(staged_package_path) != source_package.get("sha256"):
        raise MigrationStageError("staged migration package checksum changed")
    verify_migration_package(staged_package_path)

    token = secrets.token_hex(4)
    fault_candidate = f"gh-m2-stage-fault-{token}"
    success_candidate = f"gh-m2-stage-rehearsal-{token}"
    try:
        run_migration_package_rehearsal(
            rollback_path,
            staged_package_path,
            expected_retained_topic=expected_retained_topic,
            runner=command_runner,
            name_factory=lambda: fault_candidate,
            verification_executor=_fault_after_request,
        )
    except ShadowError as error:
        if str(error) != _FAULT_MESSAGE:
            raise
    else:
        raise ShadowError("stage rehearsal fault injection did not trigger")
    _assert_container_absent(command_runner, fault_candidate)

    package_result = run_migration_package_rehearsal(
        rollback_path,
        staged_package_path,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
        name_factory=lambda: success_candidate,
    )
    if package_result.get("schema") != PACKAGE_REHEARSAL_SCHEMA:
        raise MigrationStageError("stage package rehearsal schema is invalid")
    _assert_container_absent(command_runner, success_candidate)

    final_manifest = verify_migration_stage(stage_root)
    manifest_sha_after = _sha256_path(manifest_path)
    sources_after = _source_observations(final_manifest)
    if manifest_sha_before != manifest_sha_after:
        raise MigrationStageError("stage manifest changed during rehearsal")
    _assert_source_observations_unchanged(sources_before, sources_after)

    return {
        "schema": STAGE_REHEARSAL_SCHEMA,
        "stage": stage_root.name,
        "stage_manifest_sha256": manifest_sha_after,
        "source_package": source_package["package"],
        "source_package_sha256": source_package["sha256"],
        "source_rollback": source_rollback["archive"],
        "source_rollback_sha256": source_rollback["sha256"],
        "network": "none",
        "stage_verified": True,
        "staged_package_verified": True,
        "fault_after_exact_request_injected": True,
        "fault_candidate_cleanup": True,
        "success_candidate_cleanup": True,
        "stage_immutable": True,
        "live_sources_unchanged": True,
        "activation_enabled": False,
        "active_paths_modified": False,
        **{
            key: value
            for key, value in package_result.items()
            if key
            not in {
                "schema",
                "archive",
                "package",
                "package_sha256",
                "network",
                "current_services_modified",
            }
        },
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rehearse an exact inactive T1 migration stage only on "
            "--network none snapshot candidates, including cleanup fault injection."
        )
    )
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_migration_stage_rehearsal(
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (
        BackupError,
        MigrationPackageError,
        MigrationStageError,
        ShadowError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 migration stage rehearsal failed: {error}", file=sys.stderr)
        return 2
    json.dump(
        result,
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
