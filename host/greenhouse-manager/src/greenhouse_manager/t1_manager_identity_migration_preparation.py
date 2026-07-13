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
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_migration_readiness import CommandRunner, SubprocessRunner
from .t1_migration_stage import MigrationStageError, verify_migration_stage

SCHEMA = "gh.m2.t1-manager-identity-migration-preparation/1"
POSTACTIVATION_SCHEMA = "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
_MANAGER_KEYS = {
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD",
    "GH_MQTT_PASSWORD_FILE",
    "GH_MQTT_CLIENT_ID",
}
_REQUIRED_POSTACTIVATION_RECORDS = {
    "broker-postactivation-audit.json",
    "homeassistant-postcheck-supplied.json",
    "homeassistant-postcheck-live.json",
    "operator-runbook.txt",
}
_PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"
_PASSWORD_SOURCE = "/opt/greenhouse-secrets/mqtt/manager/password"

StageVerifier = Callable[[str | Path], dict[str, Any]]


class ManagerIdentityMigrationPreparationError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))[:16]


def _private_directory(path: Path, label: str, *, create: bool = False) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ManagerIdentityMigrationPreparationError(
            f"{label} is missing, public, or unsafe"
        )


def _private_file(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityMigrationPreparationError(
            f"{label} is missing, unsafe, or not mode 0600"
        )


def _load_json(path: Path, label: str, *, private: bool = True) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ManagerIdentityMigrationPreparationError(f"{label} is missing or unsafe")
    if private and path.stat().st_mode & 0o777 != 0o600:
        raise ManagerIdentityMigrationPreparationError(f"{label} must use mode 0600")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityMigrationPreparationError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityMigrationPreparationError(f"{label} must be an object")
    return document


def _must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityMigrationPreparationError(
                f"{label} verification failed: {field}"
            )


def _verify_records(root: Path, manifest: Mapping[str, Any]) -> None:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityMigrationPreparationError(
            "postactivation record inventory is missing"
        )
    observed: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ManagerIdentityMigrationPreparationError(
                "postactivation record inventory is invalid"
            )
        raw = record.get("path")
        if not isinstance(raw, str):
            raise ManagerIdentityMigrationPreparationError(
                "postactivation record path is invalid"
            )
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts or raw in observed:
            raise ManagerIdentityMigrationPreparationError(
                "postactivation record path is unsafe"
            )
        path = root.joinpath(*relative.parts)
        _private_file(path, f"postactivation record {raw}")
        if (
            path.stat().st_size != record.get("size")
            or _sha(path) != record.get("sha256")
            or record.get("contains_secret") is not False
        ):
            raise ManagerIdentityMigrationPreparationError(
                f"postactivation record verification failed: {raw}"
            )
        observed.add(raw)
    if observed != _REQUIRED_POSTACTIVATION_RECORDS:
        raise ManagerIdentityMigrationPreparationError(
            "postactivation record inventory is incomplete"
        )


def _postactivation_handoff(root: Path) -> tuple[Path, dict[str, Any]]:
    _private_directory(root, "postactivation handoff directory")
    manifest_path = root / "manifest.json"
    manifest = _load_json(manifest_path, "postactivation handoff manifest")
    _must(
        manifest,
        {
            "schema": POSTACTIVATION_SCHEMA,
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
        },
        "postactivation handoff manifest",
    )
    _verify_records(root, manifest)
    return manifest_path, manifest


def _read_key_values(path: Path, label: str) -> dict[str, str]:
    _private_file(path, label)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeError as error:
        raise ManagerIdentityMigrationPreparationError(
            f"{label} must contain UTF-8 text"
        ) from error
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ManagerIdentityMigrationPreparationError(
                f"{label} contains invalid entries"
            )
        values[key] = value
    return values


def _read_password(path: Path) -> str:
    _private_file(path, "staged manager password")
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except UnicodeError as error:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager password must contain UTF-8 text"
        ) from error
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager password must contain exactly one non-empty secret"
        )
    return value


def _canonical_fragment(username: str, client_id: str) -> str:
    return (
        "services:\n"
        "  greenhouse-manager:\n"
        "    environment:\n"
        f"      GH_MQTT_USERNAME: {username}\n"
        f"      GH_MQTT_PASSWORD_FILE: {_PASSWORD_TARGET}\n"
        f"      GH_MQTT_CLIENT_ID: {client_id}\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {_PASSWORD_SOURCE}\n"
        f"        target: {_PASSWORD_TARGET}\n"
        "        read_only: true\n"
    )


def _manager_material(stage: Path) -> tuple[dict[str, str], Path, Path, Path]:
    manager = stage / "payload/manager"
    env_path = manager / "manager.env"
    password_path = manager / "password"
    fragment_path = manager / "compose-secret-fragment.yaml"
    values = _read_key_values(env_path, "staged manager environment")
    if set(values) != {
        "GH_MQTT_USERNAME",
        "GH_MQTT_PASSWORD_FILE",
        "GH_MQTT_CLIENT_ID",
    }:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager environment has an unexpected key set"
        )
    username = values["GH_MQTT_USERNAME"]
    client_id = values["GH_MQTT_CLIENT_ID"]
    if _ID.fullmatch(username) is None or _ID.fullmatch(client_id) is None:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager identity fields are invalid"
        )
    if values["GH_MQTT_PASSWORD_FILE"] != _PASSWORD_TARGET:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager password-file target is invalid"
        )
    _read_password(password_path)
    _private_file(fragment_path, "staged manager Compose fragment")
    try:
        fragment = fragment_path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise ManagerIdentityMigrationPreparationError(
            "staged manager Compose fragment must contain UTF-8 text"
        ) from error
    if fragment != _canonical_fragment(username, client_id):
        raise ManagerIdentityMigrationPreparationError(
            "staged manager Compose fragment is not canonical"
        )
    return values, env_path, password_path, fragment_path


def _stage(
    root: Path,
    verifier: StageVerifier,
    *,
    expected_retained_topic: str,
    secret_root: Path,
) -> tuple[Path, dict[str, Any], dict[str, str], tuple[Path, Path, Path]]:
    try:
        manifest = verifier(root)
    except (MigrationStageError, OSError, ValueError) as error:
        raise ManagerIdentityMigrationPreparationError(
            "verified inactive migration stage is required"
        ) from error
    activation_path = root / "activation-plan.json"
    activation = _load_json(activation_path, "migration stage activation plan")
    _must(
        activation,
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
        "migration stage activation plan",
    )
    readiness = manifest.get("readiness_binding")
    if (
        not isinstance(readiness, dict)
        or readiness.get("expected_retained_topic") != expected_retained_topic
    ):
        raise ManagerIdentityMigrationPreparationError(
            "migration stage retained-topic binding has drifted"
        )
    values, env_path, password_path, fragment_path = _manager_material(root)
    return (
        root / "stage-manifest.json",
        manifest,
        values,
        (env_path, password_path, fragment_path),
    )


def _run(runner: CommandRunner, command: Sequence[str], message: str) -> str:
    return_code, output = runner.run(tuple(command))
    if return_code != 0:
        raise ManagerIdentityMigrationPreparationError(message)
    return output


def _live_manager(runner: CommandRunner) -> tuple[dict[str, Any], dict[str, str]]:
    output = _run(
        runner,
        ("docker", "inspect", "greenhouse-manager"),
        "greenhouse-manager cannot be inspected",
    )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager inspection returned invalid JSON"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise ManagerIdentityMigrationPreparationError(
            "exactly one greenhouse-manager container is required"
        )
    document = documents[0]
    state = document.get("State")
    config = document.get("Config")
    if not isinstance(state, dict) or not isinstance(config, dict):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager runtime metadata is incomplete"
        )
    if state.get("Status") != "running" or int(document.get("RestartCount", -1)) != 0:
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager must be running with restart count zero"
        )
    raw_env = config.get("Env")
    if not isinstance(raw_env, list) or any(not isinstance(item, str) for item in raw_env):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager environment metadata is invalid"
        )
    environment: dict[str, str] = {}
    for item in raw_env:
        key, separator, value = item.partition("=")
        if separator:
            environment[key] = value
    if any(environment.get(key, "") for key in _MANAGER_KEYS - {"GH_MQTT_CLIENT_ID"}):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager already has MQTT authentication configured"
        )
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose labels are missing"
        )
    required_labels = {
        "project": str(labels.get("com.docker.compose.project", "")).strip(),
        "working_dir": str(
            labels.get("com.docker.compose.project.working_dir", "")
        ).strip(),
        "config_files": str(
            labels.get("com.docker.compose.project.config_files", "")
        ).strip(),
    }
    if not all(required_labels.values()):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose labels are incomplete"
        )
    runtime = {
        "container_id": str(document.get("Id", "")),
        "image_id": str(document.get("Image", "")),
        "image_ref": str(config.get("Image", "")),
        "started_at": str(state.get("StartedAt", "")),
        "state": "running",
        "restart_count": 0,
        "legacy_client_id_present": bool(environment.get("GH_MQTT_CLIENT_ID", "")),
        "legacy_client_id_fingerprint": (
            _fingerprint(environment["GH_MQTT_CLIENT_ID"])
            if environment.get("GH_MQTT_CLIENT_ID")
            else None
        ),
        "mqtt_username_present": False,
        "mqtt_password_present": False,
        "mqtt_password_file_present": False,
    }
    if not all(runtime[field] for field in ("container_id", "image_id", "image_ref")):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager runtime identity is incomplete"
        )
    return runtime, required_labels


def _compose_paths(labels: Mapping[str, str]) -> tuple[Path, tuple[Path, ...]]:
    working_dir = Path(labels["working_dir"]).expanduser()
    if not working_dir.is_absolute() or working_dir.is_symlink():
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose working directory is unsafe"
        )
    working_dir = working_dir.resolve()
    if not working_dir.is_dir():
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose working directory is missing"
        )
    files: list[Path] = []
    for raw in labels["config_files"].split(","):
        value = raw.strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = working_dir / path
        if path.is_symlink() or not path.is_file():
            raise ManagerIdentityMigrationPreparationError(
                "greenhouse-manager Compose configuration is missing or unsafe"
            )
        files.append(path.resolve())
    if not files:
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose configuration list is empty"
        )
    return working_dir, tuple(files)


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


def _stage_manager_deployment(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    deployments = manifest.get("deployments")
    if not isinstance(deployments, list):
        raise ManagerIdentityMigrationPreparationError(
            "migration stage deployment inventory is missing"
        )
    matches = [
        item
        for item in deployments
        if isinstance(item, dict)
        and isinstance(item.get("containers"), list)
        and "greenhouse-manager" in item["containers"]
    ]
    if len(matches) != 1:
        raise ManagerIdentityMigrationPreparationError(
            "migration stage must contain exactly one manager deployment"
        )
    return matches[0]


def _bind_compose(
    stage_manifest: Mapping[str, Any],
    labels: Mapping[str, str],
) -> dict[str, Any]:
    working_dir, config_files = _compose_paths(labels)
    staged = _stage_manager_deployment(stage_manifest)
    if str(working_dir) != staged.get("live_directory"):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose working directory drifted from stage"
        )
    staged_files = staged.get("configuration")
    if not isinstance(staged_files, list) or len(staged_files) != len(config_files):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose file inventory drifted from stage"
        )
    records = [_path_record(path) for path in config_files]
    for current, baseline in zip(records, staged_files, strict=True):
        if (
            not isinstance(baseline, dict)
            or baseline.get("source_path") != current["path"]
            or baseline.get("sha256") != current["sha256"]
        ):
            raise ManagerIdentityMigrationPreparationError(
                "greenhouse-manager Compose configuration drifted from stage"
            )
    env_path = working_dir / ".env"
    staged_env = staged.get("environment")
    env_record: dict[str, object] | None = None
    if env_path.exists():
        if env_path.is_symlink() or not env_path.is_file():
            raise ManagerIdentityMigrationPreparationError(
                "greenhouse-manager Compose environment file is unsafe"
            )
        if env_path.stat().st_mode & 0o777 != 0o600:
            raise ManagerIdentityMigrationPreparationError(
                "greenhouse-manager Compose environment file is not mode 0600"
            )
        env_record = _path_record(env_path)
        if (
            not isinstance(staged_env, dict)
            or staged_env.get("source_path") != env_record["path"]
            or staged_env.get("sha256") != env_record["sha256"]
        ):
            raise ManagerIdentityMigrationPreparationError(
                "greenhouse-manager Compose environment drifted from stage"
            )
    elif staged_env is not None:
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager Compose environment disappeared after staging"
        )
    return {
        "project": labels["project"],
        "working_dir": str(working_dir),
        "config_files": records,
        "environment": env_record,
    }


def _reject_output(
    output: Path,
    *,
    active_roots: Sequence[Path],
    source_roots: Sequence[Path],
) -> None:
    for root in (*active_roots, *source_roots):
        resolved = root.resolve()
        if output == resolved or output.is_relative_to(resolved):
            raise ManagerIdentityMigrationPreparationError(
                "manager migration preparation output overlaps a source or active path"
            )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _copy_private(source: Path, target: Path) -> None:
    _private_file(source, "manager migration preparation source")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as input_stream, target.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)
        output_stream.flush()
        os.fsync(output_stream.fileno())
    target.chmod(0o600)
    _fsync_directory(target.parent)


def _record(path: Path, root: Path, *, contains_secret: bool) -> dict[str, object]:
    _private_file(path, "manager migration preparation file")
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha(path),
        "mode": "0600",
        "contains_secret": contains_secret,
    }


def prepare_manager_identity_migration(
    postactivation_handoff_directory: str | Path,
    migration_stage_directory: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    stage_verifier: StageVerifier = verify_migration_stage,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    postactivation_root = Path(postactivation_handoff_directory).expanduser().resolve()
    stage_root = Path(migration_stage_directory).expanduser().resolve()
    output_root = Path(output_directory).expanduser().resolve()
    secret_root_path = Path(secret_root).expanduser().resolve()

    postactivation_manifest_path, postactivation = _postactivation_handoff(
        postactivation_root
    )
    stage_manifest_path, stage_manifest, values, material_paths = _stage(
        stage_root,
        stage_verifier,
        expected_retained_topic=expected_retained_topic,
        secret_root=secret_root_path,
    )
    runtime, labels = _live_manager(runner or SubprocessRunner())
    if runtime["legacy_client_id_fingerprint"] == _fingerprint(
        values["GH_MQTT_CLIENT_ID"]
    ):
        raise ManagerIdentityMigrationPreparationError(
            "greenhouse-manager already uses the staged MQTT client identity"
        )
    compose = _bind_compose(stage_manifest, labels)
    compose_root = Path(str(compose["working_dir"]))

    _reject_output(
        output_root,
        active_roots=(compose_root, secret_root_path),
        source_roots=(postactivation_root, stage_root),
    )
    _private_directory(output_root, "output directory", create=True)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise ManagerIdentityMigrationPreparationError(
            "manager migration preparation token is invalid"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    name = (
        "greenhouse-manager-migration-preparation-"
        f"{observed:%Y%m%dT%H%M%SZ}-{token}"
    )
    destination = output_root / name
    if destination.exists():
        raise ManagerIdentityMigrationPreparationError(
            "manager migration preparation destination already exists"
        )

    with tempfile.TemporaryDirectory(prefix=".gh-manager-preparation-", dir=output_root) as temporary:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        material_root = root / "material/manager"
        material_root.mkdir(parents=True, mode=0o700)
        copied_paths = (
            material_root / "manager.env",
            material_root / "password",
            material_root / "compose-secret-fragment.yaml",
        )
        for source, target in zip(material_paths, copied_paths, strict=True):
            _copy_private(source, target)

        runtime_binding = {
            "schema": "gh.m2.t1-manager-runtime-binding/1",
            "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "container": runtime,
            "compose": compose,
            "target_secret_root": str(secret_root_path),
            "target_password_file": _PASSWORD_SOURCE,
            "read_only_capture": True,
            "current_services_modified": False,
        }
        runtime_path = root / "manager-runtime-binding.json"
        _write_private(runtime_path, _json(runtime_binding) + "\n")

        transaction_plan = {
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
        }
        plan_path = root / "transaction-plan.json"
        _write_private(plan_path, _json(transaction_plan) + "\n")
        runbook_path = root / "operator-runbook.txt"
        _write_private(
            runbook_path,
            "Manager identity migration preparation only.\n"
            "No live apply is authorized. Do not edit Compose, .env, active secret paths, "
            "or running containers from this package.\n"
            "A fresh preflight, rollback snapshot and single-use authorization are required "
            "before a later manager-only transaction.\n"
            "Node credential delivery and anonymous closure remain separate later gates.\n",
        )
        records = [
            _record(copied_paths[0], root, contains_secret=True),
            _record(copied_paths[1], root, contains_secret=True),
            _record(copied_paths[2], root, contains_secret=True),
            _record(runtime_path, root, contains_secret=True),
            _record(plan_path, root, contains_secret=False),
            _record(runbook_path, root, contains_secret=False),
        ]
        manifest = {
            "schema": SCHEMA,
            "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "classification": "secret-local-manager-migration-preparation",
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
                "postactivation_manifest_sha256": _sha(postactivation_manifest_path),
                "postactivation_handoff_name_fingerprint": _fingerprint(
                    postactivation_root.name
                ),
                "migration_stage_manifest_sha256": _sha(stage_manifest_path),
                "migration_stage_name_fingerprint": _fingerprint(stage_root.name),
                "expected_retained_topic_sha256": _sha_bytes(
                    expected_retained_topic.encode("utf-8")
                ),
                "manager_username_fingerprint": _fingerprint(
                    values["GH_MQTT_USERNAME"]
                ),
                "manager_client_id_fingerprint": _fingerprint(
                    values["GH_MQTT_CLIENT_ID"]
                ),
                "manager_runtime_binding_sha256": _sha(runtime_path),
                "manager_runtime_fingerprint": _fingerprint(
                    _json(runtime)
                ),
                "compose_binding_fingerprint": _fingerprint(_json(compose)),
            },
            "blockers": [
                "manager_operator_authorization_required",
                "manager_live_execution_not_implemented",
                "node_credentials_not_delivered",
                "anonymous_closure_not_reviewed",
            ],
            "records": records,
            "secret_values_included": True,
            "normal_report_contains_secrets": False,
            "normal_report_contains_source_paths": False,
        }
        manifest_path = root / "manifest.json"
        _write_private(manifest_path, _json(manifest) + "\n")
        manifest_sha = _sha(manifest_path)
        os.replace(root, destination)
        _fsync_directory(output_root)

    report = {
        "schema": SCHEMA,
        "prepared": True,
        "preparation_name": name,
        "manifest_sha256": manifest_sha,
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "broker_identity_activated": postactivation["broker_identity_activated"],
        "homeassistant_authenticated": postactivation["homeassistant_authenticated"],
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_authorization": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "blockers": [
            "manager_operator_authorization_required",
            "manager_live_execution_not_implemented",
            "node_credentials_not_delivered",
            "anonymous_closure_not_reviewed",
        ],
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = _json(report)
    forbidden = (
        values["GH_MQTT_USERNAME"],
        values["GH_MQTT_CLIENT_ID"],
        _read_password(material_paths[1]),
        str(postactivation_root),
        str(stage_root),
        str(output_root),
        str(compose_root),
        str(secret_root_path),
    )
    if any(value and value in serialized for value in forbidden):
        raise ManagerIdentityMigrationPreparationError(
            "sanitized manager migration preparation report contains protected material"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a private, read-only greenhouse-manager MQTT identity migration handoff."
        )
    )
    parser.add_argument("postactivation_handoff_directory")
    parser.add_argument("migration_stage_directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    args = parser.parse_args(argv)
    try:
        report = prepare_manager_identity_migration(
            args.postactivation_handoff_directory,
            args.migration_stage_directory,
            args.output,
            expected_retained_topic=args.expected_retained_topic,
            secret_root=args.secret_root,
        )
    except (
        ManagerIdentityMigrationPreparationError,
        MigrationStageError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 manager identity migration preparation failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
