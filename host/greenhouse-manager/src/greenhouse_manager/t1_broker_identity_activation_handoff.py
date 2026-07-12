from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_backup import BackupError, create_backup, verify_backup
from .t1_client_migration_audit import (
    ClientMigrationAuditError,
    build_client_migration_audit,
)
from .t1_migration_package import MigrationPackageError
from .t1_migration_readiness import ReadinessError
from .t1_migration_stage import MigrationStageError, verify_migration_stage
from .t1_migration_stage_rehearsal import run_migration_stage_rehearsal
from .t1_shadow import CommandRunner, ShadowError, SubprocessRunner

HANDOFF_SCHEMA = "gh.m2.t1-broker-identity-activation-handoff/1"
VERIFY_SCHEMA = "gh.m2.t1-broker-identity-activation-handoff-verify/1"
PLAN_SCHEMA = "gh.m2.t1-broker-identity-activation-plan/1"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{4,32}$")

_STAGE_FILES = (
    ("payload/broker/dynsec-request.json", True),
    ("payload/broker/mosquitto-plugin.conf", False),
    ("payload/bootstrap/dynsec-password-init", True),
    ("payload/bootstrap/admin-client.conf", True),
    ("payload/provisioning/mosquitto-client.conf", True),
    ("payload/provisioning/identity.json", False),
    ("payload/homeassistant/mqtt-update.json", True),
    ("payload/homeassistant/identity.json", False),
)

_REHEARSAL_TRUE = (
    "stage_verified",
    "staged_package_verified",
    "fault_after_exact_request_injected",
    "fault_candidate_cleanup",
    "success_candidate_cleanup",
    "stage_immutable",
    "live_sources_unchanged",
    "source_binding",
    "exact_package_request_applied",
    "exact_package_identity_matrix",
    "client_id_binding",
    "provisioning_control_only",
    "bootstrap_admin_removed",
    "provisioning_after_admin_removal",
    "legacy_anonymous_after_admin_removal",
    "anonymous_control_denied",
    "retained_state_recovered",
)

AuditBuilder = Callable[..., dict[str, object]]
RehearsalRunner = Callable[..., dict[str, object]]
BackupCreator = Callable[..., Path]
BackupVerifier = Callable[[str | Path], dict[str, Any]]
StageVerifier = Callable[[str | Path], dict[str, Any]]


class BrokerIdentityActivationHandoffError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise BrokerIdentityActivationHandoffError(
            "handoff directory must not be a symlink"
        )
    path.chmod(0o700)
    if path.stat().st_mode & 0o077:
        raise BrokerIdentityActivationHandoffError(
            "handoff directory must not be accessible by group or other"
        )


def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise BrokerIdentityActivationHandoffError(f"{label} is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationHandoffError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise BrokerIdentityActivationHandoffError(f"{label} must be an object")
    return value


def _write_private(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)


def _file_record(path: Path, root: Path, *, contains_secret: bool) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise BrokerIdentityActivationHandoffError("handoff file is missing or unsafe")
    if path.stat().st_mode & 0o777 != 0o600:
        raise BrokerIdentityActivationHandoffError("handoff file must use mode 0600")
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256_path(path),
        "mode": "0600",
        "contains_secret": contains_secret,
    }


def _copy_stage_file(
    stage: Path,
    root: Path,
    relative: str,
    *,
    contains_secret: bool,
) -> dict[str, object]:
    if not _safe_relative(relative):
        raise BrokerIdentityActivationHandoffError("stage file path is unsafe")
    source = stage / relative
    if (
        not source.is_file()
        or source.is_symlink()
        or source.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationHandoffError(
            f"staged activation material is missing or not private: {relative}"
        )
    target_relative = relative.removeprefix("payload/")
    target = root / "material" / target_relative
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as input_stream, target.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)
    target.chmod(0o600)
    return _file_record(target, root, contains_secret=contains_secret)


def _validate_stage_plan(stage: Path) -> dict[str, Any]:
    plan = _read_json(stage / "activation-plan.json", "stage activation plan")
    required = {
        "schema": "gh.m2.t1-auth-migration-stage-plan/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
        "requires_explicit_gate": True,
        "requires_fresh_backup_immediately_before_apply": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for key, expected in required.items():
        if plan.get(key) != expected:
            raise BrokerIdentityActivationHandoffError(
                f"stage activation safety requirement failed: {key}"
            )
    return plan


def _validate_client_audit(report: dict[str, object]) -> None:
    required = {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise BrokerIdentityActivationHandoffError(
                f"client migration audit requirement failed: {key}"
            )
    live = report.get("live_readiness")
    if not isinstance(live, dict) or (
        live.get("ready") is not True
        or live.get("source_binding") is not True
        or live.get("retained_topic_readable") is not True
    ):
        raise BrokerIdentityActivationHandoffError(
            "live readiness is not safe for activation handoff preparation"
        )
    stage = report.get("stage")
    if not isinstance(stage, dict) or (
        stage.get("verified") is not True
        or stage.get("activation_enabled") is not False
        or stage.get("active_paths_modified") is not False
    ):
        raise BrokerIdentityActivationHandoffError(
            "client migration audit stage binding is unsafe"
        )


def _validate_rehearsal(report: dict[str, object]) -> None:
    if report.get("schema") != "gh.m2.t1-auth-migration-stage-rehearsal/1":
        raise BrokerIdentityActivationHandoffError("stage rehearsal schema is invalid")
    for field in _REHEARSAL_TRUE:
        if report.get(field) is not True:
            raise BrokerIdentityActivationHandoffError(
                f"stage rehearsal requirement failed: {field}"
            )
    required_false = (
        "activation_enabled",
        "active_paths_modified",
        "current_services_modified",
    )
    for field in required_false:
        if report.get(field) is not False:
            raise BrokerIdentityActivationHandoffError(
                f"stage rehearsal safety flag is invalid: {field}"
            )
    if report.get("network") != "none":
        raise BrokerIdentityActivationHandoffError(
            "stage rehearsal candidate was not network isolated"
        )


def _reject_overlap(stage: Path, output: Path) -> None:
    if (
        output == stage
        or output.is_relative_to(stage)
        or stage.is_relative_to(output)
    ):
        raise BrokerIdentityActivationHandoffError(
            "handoff output and migration stage must not overlap"
        )


def _candidate_summary(rehearsal: dict[str, object]) -> dict[str, object]:
    return {
        field: rehearsal[field]
        for field in _REHEARSAL_TRUE
        if field in rehearsal
    }


def prepare_broker_identity_activation_handoff(
    stage_directory: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_stage_manifest_sha256: str | None = None,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    stage_verifier: StageVerifier = verify_migration_stage,
    audit_builder: AuditBuilder = build_client_migration_audit,
    rehearsal_runner: RehearsalRunner = run_migration_stage_rehearsal,
    backup_creator: BackupCreator = create_backup,
    backup_verifier: BackupVerifier = verify_backup,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    stage = Path(stage_directory).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not stage.is_dir() or stage.is_symlink():
        raise BrokerIdentityActivationHandoffError(
            "migration stage must be a regular directory"
        )
    _reject_overlap(stage, output)
    _private_directory(output)

    stage_manifest = stage_verifier(stage)
    stage_manifest_path = stage / "stage-manifest.json"
    stage_manifest_sha = _sha256_path(stage_manifest_path)
    if expected_stage_manifest_sha256 and not secrets.compare_digest(
        stage_manifest_sha,
        expected_stage_manifest_sha256,
    ):
        raise BrokerIdentityActivationHandoffError(
            "migration stage manifest fingerprint has drifted"
        )
    _validate_stage_plan(stage)

    audit = audit_builder(
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_broker="__m2_target_not_selected__",
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    _validate_client_audit(audit)

    rehearsal = rehearsal_runner(
        stage,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
    )
    _validate_rehearsal(rehearsal)

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN_RE.fullmatch(token) is None:
        raise BrokerIdentityActivationHandoffError(
            "activation handoff token contains unsupported characters"
        )
    name = (
        "greenhouse-broker-identity-handoff-"
        + observed.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + token
    )
    destination = output / name
    if destination.exists():
        raise BrokerIdentityActivationHandoffError(
            "activation handoff destination already exists"
        )

    readiness_binding = stage_manifest.get("readiness_binding")
    if not isinstance(readiness_binding, dict):
        raise BrokerIdentityActivationHandoffError(
            "migration stage readiness binding is missing"
        )
    live_config_sha = readiness_binding.get("broker_config_sha256")
    if not isinstance(live_config_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", live_config_sha
    ):
        raise BrokerIdentityActivationHandoffError(
            "migration stage Broker config fingerprint is invalid"
        )

    with tempfile.TemporaryDirectory(
        prefix=".gh-broker-identity-handoff-",
        dir=output,
    ) as temporary:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        records: list[dict[str, object]] = []

        for relative, contains_secret in _STAGE_FILES:
            records.append(
                _copy_stage_file(
                    stage,
                    root,
                    relative,
                    contains_secret=contains_secret,
                )
            )

        rollback_dir = root / "rollback"
        _private_directory(rollback_dir)
        rollback_archive = backup_creator(
            rollback_dir,
            runner=command_runner,
            now=observed,
        )
        rollback_manifest = backup_verifier(rollback_archive)
        if rollback_manifest.get("schema") != "gh.m2.t1-backup/1":
            raise BrokerIdentityActivationHandoffError(
                "fresh rollback archive schema is invalid"
            )
        if rollback_archive.parent != rollback_dir:
            raise BrokerIdentityActivationHandoffError(
                "fresh rollback archive escaped the handoff directory"
            )
        rollback_record = _file_record(
            rollback_archive,
            root,
            contains_secret=True,
        )
        records.append(rollback_record)

        activation_plan = {
            "schema": PLAN_SCHEMA,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "direct_live_apply_forbidden": True,
            "fresh_rollback_verified": True,
            "live_broker_config_sha256": live_config_sha,
            "required_sequence": [
                "revalidate_live_fingerprints",
                "verify_fresh_rollback_archive",
                "install_dynamic_security_preserving_anonymous",
                "restart_only_mosquitto_under_explicit_gate",
                "verify_legacy_anonymous_telemetry_and_retained_state",
                "verify_homeassistant_mqtt_v5_identity_and_acl",
                "verify_provisioning_identity_then_remove_bootstrap_admin",
                "run_read_only_post_activation_audit",
            ],
            "rollback_sequence": [
                "stop_failed_candidate_change",
                "restore_fresh_mosquitto_config_and_data",
                "restart_mosquitto",
                "verify_anonymous_legacy_path_and_retained_state",
            ],
        }
        plan_path = root / "activation-plan.json"
        _write_private(plan_path, _json_text(activation_plan))
        records.append(_file_record(plan_path, root, contains_secret=False))

        runbook = (
            "M2 Broker identity activation handoff\n"
            "\n"
            "This directory is preparation material only.\n"
            "Live apply is not authorized.\n"
            "Do not copy its contents to active Mosquitto paths.\n"
            "Do not restart Mosquitto, Home Assistant, greenhouse-manager, or nodes.\n"
            "Anonymous compatibility must remain enabled through all client migrations.\n"
            "A separate explicit live activation gate and post-activation audit are required.\n"
        )
        runbook_path = root / "operator-runbook.txt"
        _write_private(runbook_path, runbook)
        records.append(_file_record(runbook_path, root, contains_secret=False))

        manifest = {
            "schema": HANDOFF_SCHEMA,
            "created_at": observed.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "classification": "secret-local-inactive-handoff",
            "portable_off_host": False,
            "stage": {
                "name": stage.name,
                "manifest_sha256": stage_manifest_sha,
                "broker_config_sha256": live_config_sha,
            },
            "candidate_rehearsal": _candidate_summary(rehearsal),
            "fresh_rollback": rollback_record,
            "files": records,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
        }
        manifest_path = root / "manifest.json"
        _write_private(manifest_path, _json_text(manifest))

        os.replace(root, destination)

    report = {
        "schema": HANDOFF_SCHEMA,
        "handoff_directory": str(destination),
        "stage": stage.name,
        "stage_manifest_sha256": stage_manifest_sha,
        "live_broker_config_sha256": live_config_sha,
        "fresh_rollback_archive": rollback_record["path"],
        "fresh_rollback_sha256": rollback_record["sha256"],
        "candidate_rehearsal": _candidate_summary(rehearsal),
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }
    serialized = _json_text(report)
    for relative, contains_secret in _STAGE_FILES:
        if not contains_secret:
            continue
        value = (stage / relative).read_text(encoding="utf-8").strip()
        if value and value in serialized:
            raise BrokerIdentityActivationHandoffError(
                "activation handoff report contains staged secret material"
            )
    return report


def verify_broker_identity_activation_handoff(
    handoff_directory: str | Path,
    *,
    backup_verifier: BackupVerifier = verify_backup,
) -> dict[str, object]:
    root = Path(handoff_directory).expanduser().resolve()
    if (
        not root.is_dir()
        or root.is_symlink()
        or root.stat().st_mode & 0o777 != 0o700
    ):
        raise BrokerIdentityActivationHandoffError(
            "activation handoff directory is missing or not mode 0700"
        )
    manifest_path = root / "manifest.json"
    plan_path = root / "activation-plan.json"
    if manifest_path.stat().st_mode & 0o777 != 0o600:
        raise BrokerIdentityActivationHandoffError("handoff manifest must use mode 0600")
    manifest = _read_json(manifest_path, "activation handoff manifest")
    plan = _read_json(plan_path, "activation plan")
    required_manifest = {
        "schema": HANDOFF_SCHEMA,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }
    for key, expected in required_manifest.items():
        if manifest.get(key) != expected:
            raise BrokerIdentityActivationHandoffError(
                f"activation handoff manifest requirement failed: {key}"
            )
    required_plan = {
        "schema": PLAN_SCHEMA,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "direct_live_apply_forbidden": True,
        "fresh_rollback_verified": True,
    }
    for key, expected in required_plan.items():
        if plan.get(key) != expected:
            raise BrokerIdentityActivationHandoffError(
                f"activation plan requirement failed: {key}"
            )

    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise BrokerIdentityActivationHandoffError("handoff file inventory is missing")
    seen: set[str] = set()
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise BrokerIdentityActivationHandoffError("handoff file record is invalid")
        relative = str(raw_record.get("path", ""))
        if not _safe_relative(relative) or relative in seen:
            raise BrokerIdentityActivationHandoffError("handoff file path is invalid")
        seen.add(relative)
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise BrokerIdentityActivationHandoffError(
                f"handoff file is missing or not private: {relative}"
            )
        if path.stat().st_size != raw_record.get("size"):
            raise BrokerIdentityActivationHandoffError(
                f"handoff file size mismatch: {relative}"
            )
        if _sha256_path(path) != raw_record.get("sha256"):
            raise BrokerIdentityActivationHandoffError(
                f"handoff file checksum mismatch: {relative}"
            )

    rollback = manifest.get("fresh_rollback")
    if not isinstance(rollback, dict):
        raise BrokerIdentityActivationHandoffError("fresh rollback record is missing")
    rollback_relative = str(rollback.get("path", ""))
    if rollback_relative not in seen:
        raise BrokerIdentityActivationHandoffError(
            "fresh rollback archive is not in the file inventory"
        )
    rollback_manifest = backup_verifier(root / rollback_relative)
    if rollback_manifest.get("schema") != "gh.m2.t1-backup/1":
        raise BrokerIdentityActivationHandoffError(
            "fresh rollback archive verification failed"
        )

    return {
        "schema": VERIFY_SCHEMA,
        "handoff": root.name,
        "file_count": len(records),
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        "preserve_anonymous": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or verify a private, inactive Broker identity activation "
            "handoff without modifying live services."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("stage_directory")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--expected-retained-topic", required=True)
    prepare.add_argument("--expected-stage-manifest-sha256")
    prepare.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
    )
    prepare.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    verify = subparsers.add_parser("verify")
    verify.add_argument("handoff_directory")
    args = parser.parse_args(argv)

    try:
        if args.command == "prepare":
            report = prepare_broker_identity_activation_handoff(
                args.stage_directory,
                args.output,
                expected_retained_topic=args.expected_retained_topic,
                expected_stage_manifest_sha256=(
                    args.expected_stage_manifest_sha256
                ),
                compose_directory=args.compose_directory,
                secret_root=args.secret_root,
                runner=runner,
            )
        else:
            report = verify_broker_identity_activation_handoff(
                args.handoff_directory
            )
    except (
        BackupError,
        BrokerIdentityActivationHandoffError,
        ClientMigrationAuditError,
        MigrationPackageError,
        MigrationStageError,
        ReadinessError,
        ShadowError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker identity activation handoff failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
