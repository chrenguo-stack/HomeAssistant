from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_manager_identity_migration_preparation import (
    SCHEMA as PREPARATION_SCHEMA,
)
from .t1_manager_identity_migration_preparation import (
    ManagerIdentityMigrationPreparationError,
    _compose_paths,
    _fingerprint,
    _live_manager,
    _path_record,
    _read_key_values,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

REQUEST_SCHEMA = "gh.m2.t1-manager-identity-migration-authorization-request/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-manager-identity-migration-authorization/1"
VERIFY_SCHEMA = "gh.m2.t1-manager-identity-migration-authorization-verify/1"
_RUNTIME_SCHEMA = "gh.m2.t1-manager-runtime-binding/1"
_PLAN_SCHEMA = "gh.m2.t1-manager-identity-migration-transaction-plan/1"
_PREPARATION_PREFIX = "greenhouse-manager-migration-preparation-"
_OUTPUT_PREFIX = "greenhouse-m2-manager-authorizations"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_RECORDS = {
    "material/manager/manager.env": True,
    "material/manager/password": True,
    "material/manager/compose-secret-fragment.yaml": True,
    "manager-runtime-binding.json": True,
    "transaction-plan.json": False,
    "operator-runbook.txt": False,
}
_BOUND_FIELDS = (
    "preparation_manifest_sha256",
    "manager_runtime_binding_sha256",
    "transaction_plan_sha256",
    "manager_env_sha256",
    "manager_password_sha256",
    "manager_fragment_sha256",
    "manager_runtime_fingerprint",
    "compose_binding_fingerprint",
    "postactivation_manifest_sha256",
    "migration_stage_manifest_sha256",
)

TokenFactory = Callable[[], str]


class ManagerIdentityMigrationAuthorizationError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
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


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManagerIdentityMigrationAuthorizationError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityMigrationAuthorizationError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityMigrationAuthorizationError(f"{label} must be an object")
    return document


def _must(
    document: Mapping[str, Any],
    required: Mapping[str, object],
    label: str,
) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityMigrationAuthorizationError(
                f"{label} verification failed: {field}"
            )


def _private_preparation_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if (
        not resolved.name.startswith(_PREPARATION_PREFIX)
        or not resolved.is_dir()
        or resolved.is_symlink()
        or resolved.stat().st_mode & 0o077
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation directory is missing or unsafe"
        )
    return resolved


def _verify_records(root: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation record inventory is missing"
        )
    observed: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ManagerIdentityMigrationAuthorizationError(
                "manager migration preparation record inventory is invalid"
            )
        raw = record.get("path")
        if not isinstance(raw, str):
            raise ManagerIdentityMigrationAuthorizationError(
                "manager migration preparation record path is invalid"
            )
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts or raw in observed:
            raise ManagerIdentityMigrationAuthorizationError(
                "manager migration preparation record path is unsafe"
            )
        if raw not in _EXPECTED_RECORDS:
            raise ManagerIdentityMigrationAuthorizationError(
                "manager migration preparation record inventory is unexpected"
            )
        path = root.joinpath(*relative.parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise ManagerIdentityMigrationAuthorizationError(
                f"manager migration preparation record is unsafe: {raw}"
            )
        digest = _sha(path)
        if (
            path.stat().st_size != record.get("size")
            or digest != record.get("sha256")
            or record.get("contains_secret") is not _EXPECTED_RECORDS[raw]
        ):
            raise ManagerIdentityMigrationAuthorizationError(
                f"manager migration preparation record verification failed: {raw}"
            )
        observed[raw] = digest
    if set(observed) != set(_EXPECTED_RECORDS):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation record inventory is incomplete"
        )
    return observed


def _current_compose(labels: Mapping[str, str]) -> dict[str, Any]:
    working_dir, files = _compose_paths(labels)
    env_path = working_dir / ".env"
    environment: dict[str, object] | None = None
    if env_path.exists():
        if (
            env_path.is_symlink()
            or not env_path.is_file()
            or env_path.stat().st_mode & 0o777 != 0o600
        ):
            raise ManagerIdentityMigrationAuthorizationError(
                "greenhouse-manager Compose environment is unsafe"
            )
        environment = _path_record(env_path)
    return {
        "project": labels["project"],
        "working_dir": str(working_dir),
        "config_files": [_path_record(path) for path in files],
        "environment": environment,
    }


def _bound_path(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerIdentityMigrationAuthorizationError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ManagerIdentityMigrationAuthorizationError(f"{label} is unsafe")
    return path.resolve()


def _validate_secret_target(binding: Mapping[str, Any]) -> tuple[Path, Path]:
    root = _bound_path(binding.get("target_secret_root"), "manager secret root")
    password = _bound_path(
        binding.get("target_password_file"),
        "manager active password path",
    )
    if not password.is_relative_to(root):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager active password escaped the secret root"
        )
    if root.exists() and (
        not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o077
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager secret root is not a private directory"
        )
    if password.exists():
        raise ManagerIdentityMigrationAuthorizationError(
            "manager active password already exists before authorization"
        )
    return root, password


def _fresh_runtime_check(
    runtime_binding: Mapping[str, Any],
    runner: CommandRunner,
) -> tuple[str, str, tuple[Path, ...]]:
    captured_runtime = runtime_binding.get("container")
    captured_compose = runtime_binding.get("compose")
    if not isinstance(captured_runtime, dict) or not isinstance(captured_compose, dict):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager runtime binding is incomplete"
        )
    try:
        current_runtime, labels = _live_manager(runner)
        current_compose = _current_compose(labels)
    except ManagerIdentityMigrationPreparationError as error:
        raise ManagerIdentityMigrationAuthorizationError(
            "fresh manager runtime preflight failed"
        ) from error
    if current_runtime != captured_runtime:
        raise ManagerIdentityMigrationAuthorizationError(
            "greenhouse-manager runtime identity drifted after preparation"
        )
    if current_compose != captured_compose:
        raise ManagerIdentityMigrationAuthorizationError(
            "greenhouse-manager Compose binding drifted after preparation"
        )
    secret_root, password = _validate_secret_target(runtime_binding)
    compose_root = _bound_path(
        current_compose.get("working_dir"),
        "greenhouse-manager Compose working directory",
    )
    return (
        _fingerprint(_canonical_json(current_runtime)),
        _fingerprint(_canonical_json(current_compose)),
        (compose_root, secret_root, password),
    )


def _validated_preparation(
    preparation_directory: str | Path,
    *,
    runner: CommandRunner,
) -> dict[str, Any]:
    root = _private_preparation_root(Path(preparation_directory))
    manifest_path = root / "manifest.json"
    manifest = _read_private_json(
        manifest_path,
        "manager migration preparation manifest",
    )
    _must(
        manifest,
        {
            "schema": PREPARATION_SCHEMA,
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
        },
        "manager migration preparation manifest",
    )
    records = _verify_records(root, manifest)
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation bindings are missing"
        )
    runtime_path = root / "manager-runtime-binding.json"
    plan_path = root / "transaction-plan.json"
    runtime_binding = _read_private_json(runtime_path, "manager runtime binding")
    plan = _read_private_json(plan_path, "manager transaction plan")
    _must(
        runtime_binding,
        {
            "schema": _RUNTIME_SCHEMA,
            "read_only_capture": True,
            "current_services_modified": False,
        },
        "manager runtime binding",
    )
    _must(
        plan,
        {
            "schema": _PLAN_SCHEMA,
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
        "manager transaction plan",
    )
    runtime_digest = records["manager-runtime-binding.json"]
    if (
        bindings.get("manager_runtime_binding_sha256") != runtime_digest
        or bindings.get("manager_runtime_fingerprint")
        != _fingerprint(_canonical_json(runtime_binding["container"]))
        or bindings.get("compose_binding_fingerprint")
        != _fingerprint(_canonical_json(runtime_binding["compose"]))
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation runtime binding does not match"
        )
    manager_env = _read_key_values(
        root / "material/manager/manager.env",
        "prepared manager environment",
    )
    username = manager_env.get("GH_MQTT_USERNAME")
    client_id = manager_env.get("GH_MQTT_CLIENT_ID")
    if (
        not isinstance(username, str)
        or not isinstance(client_id, str)
        or bindings.get("manager_username_fingerprint") != _fingerprint(username)
        or bindings.get("manager_client_id_fingerprint") != _fingerprint(client_id)
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "prepared manager identity fingerprint does not match"
        )
    runtime_fp, compose_fp, protected_paths = _fresh_runtime_check(
        runtime_binding,
        runner,
    )
    if (
        runtime_fp != bindings.get("manager_runtime_fingerprint")
        or compose_fp != bindings.get("compose_binding_fingerprint")
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "fresh manager runtime fingerprints do not match preparation"
        )
    return {
        "root": root,
        "manifest_sha256": _sha(manifest_path),
        "manager_runtime_binding_sha256": runtime_digest,
        "transaction_plan_sha256": records["transaction-plan.json"],
        "manager_env_sha256": records["material/manager/manager.env"],
        "manager_password_sha256": records["material/manager/password"],
        "manager_fragment_sha256": records[
            "material/manager/compose-secret-fragment.yaml"
        ],
        "manager_runtime_fingerprint": runtime_fp,
        "compose_binding_fingerprint": compose_fp,
        "postactivation_manifest_sha256": _require_sha(
            bindings.get("postactivation_manifest_sha256"),
            "postactivation manifest",
        ),
        "migration_stage_manifest_sha256": _require_sha(
            bindings.get("migration_stage_manifest_sha256"),
            "migration stage manifest",
        ),
        "protected_paths": protected_paths,
    }


def _public_bindings(validated: Mapping[str, Any]) -> dict[str, object]:
    return {
        "preparation_manifest_sha256": validated["manifest_sha256"],
        "manager_runtime_binding_sha256": validated[
            "manager_runtime_binding_sha256"
        ],
        "transaction_plan_sha256": validated["transaction_plan_sha256"],
        "manager_env_sha256": validated["manager_env_sha256"],
        "manager_password_sha256": validated["manager_password_sha256"],
        "manager_fragment_sha256": validated["manager_fragment_sha256"],
        "manager_runtime_fingerprint": validated["manager_runtime_fingerprint"],
        "compose_binding_fingerprint": validated["compose_binding_fingerprint"],
        "postactivation_manifest_sha256": validated[
            "postactivation_manifest_sha256"
        ],
        "migration_stage_manifest_sha256": validated[
            "migration_stage_manifest_sha256"
        ],
    }


def _request_bindings(request: Mapping[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in _BOUND_FIELDS:
        value = request.get(field)
        if not isinstance(value, str):
            raise ManagerIdentityMigrationAuthorizationError(
                f"manager authorization request binding is invalid: {field}"
            )
        result[field] = value
    return result


def _confirmation(validated: Mapping[str, Any]) -> str:
    return (
        "AUTHORIZE-M2-MANAGER-MIGRATION:"
        f"{validated['manifest_sha256'][:16]}:"
        f"{validated['manager_runtime_fingerprint']}:"
        f"{validated['compose_binding_fingerprint']}"
    )


def _request_from_validated(validated: Mapping[str, Any]) -> dict[str, object]:
    root = validated.get("root")
    if not isinstance(root, Path):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager migration preparation root binding is invalid"
        )
    return {
        "schema": REQUEST_SCHEMA,
        "preparation_name": root.name,
        "required_confirmation": _confirmation(validated),
        **_public_bindings(validated),
        "fresh_runtime_preflight_passed": True,
        "authorization_created": False,
        "single_use": True,
        "operator_action_authorized": False,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def build_manager_identity_migration_authorization_request(
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    validated = _validated_preparation(
        preparation_directory,
        runner=runner or SubprocessRunner(),
    )
    return _request_from_validated(validated)


def _private_output_directory(path: Path) -> Path:
    if not path.name.startswith(_OUTPUT_PREFIX):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization output directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization output directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization output directory must be private"
        )
    return resolved


def _reject_output(
    output: Path,
    preparation_root: Path,
    protected_paths: Sequence[Path],
) -> None:
    for protected in (preparation_root, *protected_paths):
        resolved = protected.resolve()
        if output == resolved or output.is_relative_to(resolved):
            raise ManagerIdentityMigrationAuthorizationError(
                "manager authorization output overlaps preparation or active paths"
            )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
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


def create_manager_identity_migration_authorization(
    preparation_directory: str | Path,
    output_directory: str | Path,
    *,
    confirmation: str,
    ttl_seconds: int = 900,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, object]:
    if ttl_seconds < 60 or ttl_seconds > 1800:
        raise ValueError("authorization TTL must be between 60 and 1800 seconds")
    command_runner = runner or SubprocessRunner()
    first = _validated_preparation(
        preparation_directory,
        runner=command_runner,
    )
    request = _request_from_validated(first)
    required = request.get("required_confirmation")
    if not isinstance(required, str) or not hmac.compare_digest(confirmation, required):
        raise ManagerIdentityMigrationAuthorizationError(
            "explicit manager migration authorization confirmation is missing or does not match"
        )
    second = _validated_preparation(
        preparation_directory,
        runner=command_runner,
    )
    refreshed = _request_from_validated(second)
    if _canonical_json(request) != _canonical_json(refreshed):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager runtime state drifted during authorization creation"
        )
    preparation_root = second.get("root")
    protected_paths = second.get("protected_paths")
    if not isinstance(preparation_root, Path) or not isinstance(protected_paths, tuple):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization path bindings are incomplete"
        )
    output = _private_output_directory(Path(output_directory).expanduser())
    _reject_output(output, preparation_root, protected_paths)
    token = token_factory() if token_factory else secrets.token_urlsafe(32)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization token is invalid"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    expires = observed + timedelta(seconds=ttl_seconds)
    authorization_id = _sha_bytes(token.encode("utf-8"))[:24]
    document = {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_id": authorization_id,
        "authorization_token": token,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "preparation_name": request["preparation_name"],
        **_request_bindings(request),
        "fresh_runtime_preflight_passed": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    destination = output / f"manager-migration-authorization-{authorization_id}.json"
    if destination.exists():
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization destination already exists"
        )
    _atomic_private_write(destination, _canonical_json(document) + "\n")
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_file": destination.name,
        "authorization_id": authorization_id,
        "expires_at": document["expires_at"],
        "preparation_manifest_sha256": document["preparation_manifest_sha256"],
        "single_use": True,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_redacted": True,
        "path_values_redacted": True,
    }


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ManagerIdentityMigrationAuthorizationError(
            f"manager authorization {label} is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ManagerIdentityMigrationAuthorizationError(
            f"manager authorization {label} is invalid"
        ) from error


def verify_manager_identity_migration_authorization(
    authorization_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    auth_path = Path(authorization_file).expanduser().resolve()
    authorization = _read_private_json(
        auth_path,
        "manager migration authorization",
    )
    validated = _validated_preparation(
        preparation_directory,
        runner=runner or SubprocessRunner(),
    )
    request = _request_from_validated(validated)
    required: dict[str, object] = {
        "schema": AUTHORIZATION_SCHEMA,
        "preparation_name": request["preparation_name"],
        **_request_bindings(request),
        "fresh_runtime_preflight_passed": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        actual = authorization.get(field)
        if isinstance(expected, str):
            valid = isinstance(actual, str) and hmac.compare_digest(actual, expected)
        else:
            valid = actual == expected
        if not valid:
            raise ManagerIdentityMigrationAuthorizationError(
                f"manager authorization binding failed: {field}"
            )
    token = authorization.get("authorization_token")
    authorization_id = authorization.get("authorization_id")
    if (
        not isinstance(token, str)
        or _TOKEN.fullmatch(token) is None
        or not isinstance(authorization_id, str)
        or authorization_id != _sha_bytes(token.encode("utf-8"))[:24]
    ):
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization token binding is invalid"
        )
    created = _parse_timestamp(authorization.get("created_at"), "creation timestamp")
    expires = _parse_timestamp(authorization.get("expires_at"), "expiry timestamp")
    if expires <= created or (expires - created).total_seconds() > 1800:
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization lifetime is invalid"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    if not created <= observed <= expires:
        raise ManagerIdentityMigrationAuthorizationError(
            "manager authorization is not currently valid"
        )
    return {
        "schema": VERIFY_SCHEMA,
        "authorization_id": authorization_id,
        "preparation_manifest_sha256": request["preparation_manifest_sha256"],
        "valid_now": True,
        "fresh_runtime_preflight_passed": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_redacted": True,
        "path_values_redacted": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build, create, or verify a short-lived manager migration authorization "
            "without applying it."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("preparation_directory")
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("preparation_directory")
    create_parser.add_argument("output_directory")
    create_parser.add_argument("--confirmation", required=True)
    create_parser.add_argument("--ttl-seconds", type=int, default=900)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("authorization_file")
    verify_parser.add_argument("preparation_directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "request":
            result = build_manager_identity_migration_authorization_request(
                args.preparation_directory
            )
        elif args.command == "create":
            result = create_manager_identity_migration_authorization(
                args.preparation_directory,
                args.output_directory,
                confirmation=args.confirmation,
                ttl_seconds=args.ttl_seconds,
            )
        else:
            result = verify_manager_identity_migration_authorization(
                args.authorization_file,
                args.preparation_directory,
            )
    except (
        ManagerIdentityMigrationAuthorizationError,
        ManagerIdentityMigrationPreparationError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager migration authorization failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
