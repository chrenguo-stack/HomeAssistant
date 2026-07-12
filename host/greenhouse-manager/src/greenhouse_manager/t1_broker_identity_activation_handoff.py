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
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
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
_PROOFS = (
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

Builder = Callable[..., dict[str, object]]
Verifier = Callable[[str | Path], dict[str, Any]]


class BrokerIdentityActivationHandoffError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise BrokerIdentityActivationHandoffError("private directory is a symlink")
    path.chmod(0o700)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _read(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise BrokerIdentityActivationHandoffError(f"{label} is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationHandoffError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise BrokerIdentityActivationHandoffError(f"{label} must be an object")
    return value


def _record(path: Path, root: Path, secret: bool) -> dict[str, object]:
    if path.stat().st_mode & 0o777 != 0o600:
        raise BrokerIdentityActivationHandoffError("handoff file must use mode 0600")
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha(path),
        "mode": "0600",
        "contains_secret": secret,
    }


def _copy(stage: Path, root: Path, relative: str, secret: bool) -> dict[str, object]:
    source = stage / relative
    if not source.is_file() or source.is_symlink() or source.stat().st_mode & 0o777 != 0o600:
        raise BrokerIdentityActivationHandoffError(
            f"staged activation material is missing or not private: {relative}"
        )
    target = root / "material" / relative.removeprefix("payload/")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    target.chmod(0o600)
    return _record(target, root, secret)


def _require(mapping: dict[str, object], required: dict[str, object], label: str) -> None:
    for key, expected in required.items():
        if mapping.get(key) != expected:
            raise BrokerIdentityActivationHandoffError(f"{label} requirement failed: {key}")


def _validate_stage(stage: Path) -> None:
    _require(
        _read(stage / "activation-plan.json", "stage activation plan"),
        {
            "schema": "gh.m2.t1-auth-migration-stage-plan/1",
            "activation_enabled": False,
            "current_services_modified": False,
            "active_paths_modified": False,
            "requires_explicit_gate": True,
            "requires_fresh_backup_immediately_before_apply": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        },
        "stage activation plan",
    )


def _validate_audit(report: dict[str, object]) -> None:
    _require(
        report,
        {
            "schema": "gh.m2.t1-auth-client-migration-audit/1",
            "read_only": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "audit_complete": True,
            "ready_for_live_apply": False,
        },
        "client audit",
    )
    live = report.get("live_readiness")
    if not isinstance(live, dict) or any(
        live.get(key) is not True for key in ("ready", "source_binding", "retained_topic_readable")
    ):
        raise BrokerIdentityActivationHandoffError("live readiness is not safe")


def _validate_rehearsal(report: dict[str, object]) -> None:
    _require(
        report,
        {
            "schema": "gh.m2.t1-auth-migration-stage-rehearsal/1",
            "network": "none",
            "activation_enabled": False,
            "active_paths_modified": False,
            "current_services_modified": False,
        },
        "stage rehearsal",
    )
    for proof in _PROOFS:
        if report.get(proof) is not True:
            raise BrokerIdentityActivationHandoffError(f"stage rehearsal proof failed: {proof}")


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
    stage_verifier: Verifier = verify_migration_stage,
    audit_builder: Builder = build_client_migration_audit,
    rehearsal_runner: Builder = run_migration_stage_rehearsal,
    backup_creator: Callable[..., Path] = create_backup,
    backup_verifier: Verifier = verify_backup,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    stage = Path(stage_directory).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not stage.is_dir() or stage.is_symlink():
        raise BrokerIdentityActivationHandoffError("migration stage is unsafe")
    if output == stage or output.is_relative_to(stage) or stage.is_relative_to(output):
        raise BrokerIdentityActivationHandoffError("handoff output and stage must not overlap")
    _private_dir(output)

    manifest = stage_verifier(stage)
    manifest_sha = _sha(stage / "stage-manifest.json")
    if expected_stage_manifest_sha256 and not secrets.compare_digest(
        manifest_sha, expected_stage_manifest_sha256
    ):
        raise BrokerIdentityActivationHandoffError("stage manifest fingerprint has drifted")
    _validate_stage(stage)
    audit = audit_builder(
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_broker="__m2_target_not_selected__",
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    _validate_audit(audit)
    rehearsal = rehearsal_runner(
        stage,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
    )
    _validate_rehearsal(rehearsal)

    binding = manifest.get("readiness_binding")
    live_sha = binding.get("broker_config_sha256") if isinstance(binding, dict) else None
    if not isinstance(live_sha, str) or re.fullmatch(r"[0-9a-f]{64}", live_sha) is None:
        raise BrokerIdentityActivationHandoffError("Broker config fingerprint is invalid")

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise BrokerIdentityActivationHandoffError("handoff token is invalid")
    name = f"greenhouse-broker-identity-handoff-{observed:%Y%m%dT%H%M%SZ}-{token}"
    destination = output / name
    if destination.exists():
        raise BrokerIdentityActivationHandoffError("handoff destination exists")

    with tempfile.TemporaryDirectory(prefix=".gh-broker-handoff-", dir=output) as temporary:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        records = [_copy(stage, root, relative, secret) for relative, secret in _STAGE_FILES]
        rollback_dir = root / "rollback"
        _private_dir(rollback_dir)
        rollback = backup_creator(rollback_dir, runner=command_runner, now=observed)
        if rollback.parent != rollback_dir or backup_verifier(rollback).get("schema") != "gh.m2.t1-backup/1":
            raise BrokerIdentityActivationHandoffError("fresh rollback verification failed")
        rollback_record = _record(rollback, root, True)
        records.append(rollback_record)

        plan = {
            "schema": PLAN_SCHEMA,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "direct_live_apply_forbidden": True,
            "fresh_rollback_verified": True,
            "live_broker_config_sha256": live_sha,
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
        }
        _write(root / "activation-plan.json", _json(plan))
        records.append(_record(root / "activation-plan.json", root, False))
        _write(
            root / "operator-runbook.txt",
            "Preparation only. Live apply is not authorized.\n",
        )
        records.append(_record(root / "operator-runbook.txt", root, False))
        handoff_manifest = {
            "schema": HANDOFF_SCHEMA,
            "stage": {
                "name": stage.name,
                "manifest_sha256": manifest_sha,
                "broker_config_sha256": live_sha,
            },
            "candidate_rehearsal": {key: True for key in _PROOFS},
            "fresh_rollback": rollback_record,
            "files": records,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
        }
        _write(root / "manifest.json", _json(handoff_manifest))
        os.replace(root, destination)

    return {
        "schema": HANDOFF_SCHEMA,
        "handoff_directory": str(destination),
        "stage": stage.name,
        "stage_manifest_sha256": manifest_sha,
        "live_broker_config_sha256": live_sha,
        "fresh_rollback_archive": rollback_record["path"],
        "fresh_rollback_sha256": rollback_record["sha256"],
        "candidate_rehearsal": {key: True for key in _PROOFS},
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def verify_broker_identity_activation_handoff(
    handoff_directory: str | Path,
    *,
    backup_verifier: Verifier = verify_backup,
) -> dict[str, object]:
    root = Path(handoff_directory).expanduser().resolve()
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o777 != 0o700:
        raise BrokerIdentityActivationHandoffError("handoff directory is unsafe")
    manifest = _read(root / "manifest.json", "handoff manifest")
    plan = _read(root / "activation-plan.json", "activation plan")
    safety = {
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    _require(manifest, {"schema": HANDOFF_SCHEMA, **safety}, "handoff manifest")
    _require(
        plan,
        {"schema": PLAN_SCHEMA, **safety, "direct_live_apply_forbidden": True},
        "activation plan",
    )
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise BrokerIdentityActivationHandoffError("handoff inventory is missing")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise BrokerIdentityActivationHandoffError("handoff record is invalid")
        relative = str(record.get("path", ""))
        path = PurePosixPath(relative)
        if not relative or path.is_absolute() or ".." in path.parts or relative in seen:
            raise BrokerIdentityActivationHandoffError("handoff path is invalid")
        seen.add(relative)
        file_path = root / relative
        if not file_path.is_file() or file_path.is_symlink() or file_path.stat().st_mode & 0o777 != 0o600:
            raise BrokerIdentityActivationHandoffError(f"handoff file is unsafe: {relative}")
        if file_path.stat().st_size != record.get("size") or _sha(file_path) != record.get("sha256"):
            raise BrokerIdentityActivationHandoffError(f"handoff file checksum mismatch: {relative}")
    rollback = manifest.get("fresh_rollback")
    relative = str(rollback.get("path", "")) if isinstance(rollback, dict) else ""
    if relative not in seen or backup_verifier(root / relative).get("schema") != "gh.m2.t1-backup/1":
        raise BrokerIdentityActivationHandoffError("fresh rollback verification failed")
    return {
        "schema": VERIFY_SCHEMA,
        "handoff": root.name,
        "file_count": len(records),
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        **safety,
    }


def main(argv: Sequence[str] | None = None, *, runner: CommandRunner | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("stage_directory")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--expected-retained-topic", required=True)
    prepare.add_argument("--expected-stage-manifest-sha256")
    verify = commands.add_parser("verify")
    verify.add_argument("handoff_directory")
    args = parser.parse_args(argv)
    try:
        result = (
            prepare_broker_identity_activation_handoff(
                args.stage_directory,
                args.output,
                expected_retained_topic=args.expected_retained_topic,
                expected_stage_manifest_sha256=args.expected_stage_manifest_sha256,
                runner=runner,
            )
            if args.command == "prepare"
            else verify_broker_identity_activation_handoff(args.handoff_directory)
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
        print(f"T1 Broker identity activation handoff failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
