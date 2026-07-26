from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import secrets
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_preparation_common import (
    ManagerIdentityExecutionPreparationError,
    canonical,
    parse_timestamp,
    private_dir,
    private_file,
    read_json,
    sha_bytes,
    sha_path,
    validate_gate,
    validate_preparation,
    write_json,
)
from .t1_manager_identity_migration_execution_preparation_verify import (
    verify_manager_identity_execution_preparation,
)
from .t1_manager_identity_migration_live_runtime_gate import (
    ManagerIdentityLiveRuntimeGateError,
    build_manager_identity_live_runtime_gate,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

REQUEST_SCHEMA = "gh.m2.t1-manager-identity-execution-authorization-request/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-manager-identity-execution-authorization/1"
VERIFY_SCHEMA = "gh.m2.t1-manager-identity-execution-authorization-verify/1"
OUTPUT_PREFIX = "greenhouse-m2-manager-execution-authorizations"
EXECUTION_PREFIX = "greenhouse-manager-execution-preparation-"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
BOUND_FIELDS = (
    "execution_preparation_manifest_sha256",
    "fresh_rollback_archive_sha256",
    "fresh_rollback_manifest_sha256",
    "live_runtime_gate_sha256",
    "preclaim_candidate_probe_sha256",
    "execution_plan_sha256",
    "driver_contract_sha256",
    "adapter_contract_sha256",
    "runtime_binding_sha256",
    "live_binding_sha256",
    "preparation_manifest_sha256",
    "preparation_record_set_sha256",
)

LiveGateBuilder = Callable[..., dict[str, object]]
TokenFactory = Callable[[], str]


class ManagerIdentityExecutionAuthorizationError(RuntimeError):
    pass


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ManagerIdentityExecutionAuthorizationError(f"{label} SHA-256 is invalid")
    return value


def _private_execution_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.name.startswith(EXECUTION_PREFIX):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation directory name is invalid"
        )
    return private_dir(resolved, "manager execution preparation directory")


def _bound_path(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerIdentityExecutionAuthorizationError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ManagerIdentityExecutionAuthorizationError(f"{label} is unsafe")
    return path.resolve()


def _record_digests(manifest: Mapping[str, Any]) -> dict[str, str]:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityExecutionAuthorizationError(
            "execution preparation record inventory is missing"
        )
    result: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ManagerIdentityExecutionAuthorizationError(
                "execution preparation record inventory is invalid"
            )
        name = record.get("path")
        digest = record.get("sha256")
        if not isinstance(name, str) or name in result:
            raise ManagerIdentityExecutionAuthorizationError(
                "execution preparation record path is invalid"
            )
        result[name] = _require_sha(digest, f"execution preparation record {name}")
    return result


def _protected_paths(
    execution_root: Path,
    driver: Path,
    preparation_root: Path,
    runtime: Mapping[str, Any],
) -> tuple[Path, ...]:
    compose = runtime.get("compose")
    if not isinstance(compose, dict):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager preparation Compose binding is missing"
        )
    working_dir = _bound_path(
        compose.get("working_dir"),
        "greenhouse-manager Compose working directory",
    )
    secret_root = _bound_path(
        runtime.get("target_secret_root"),
        "manager active secret root",
    )
    password_target = _bound_path(
        runtime.get("target_password_file"),
        "manager active password target",
    )
    return execution_root, driver, preparation_root, working_dir, secret_root, password_target


def _reject_output(output: Path, protected: Sequence[Path]) -> None:
    for path in protected:
        resolved = path.resolve()
        if output == resolved or output.is_relative_to(resolved):
            raise ManagerIdentityExecutionAuthorizationError(
                "manager execution authorization output overlaps protected paths"
            )


def _private_output(path: Path, protected: Sequence[Path]) -> Path:
    requested = path.expanduser().resolve()
    if not requested.name.startswith(OUTPUT_PREFIX):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization output directory name is not allowed"
        )
    _reject_output(requested, protected)
    return private_dir(
        requested,
        "manager execution authorization output directory",
        create=True,
    )


def _validated_execution_preparation(
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner,
    live_gate_builder: LiveGateBuilder,
    now: datetime,
) -> dict[str, Any]:
    execution_root = _private_execution_root(Path(execution_preparation_directory))
    driver = private_file(
        Path(driver_contract_file).expanduser().resolve(),
        "manager production driver contract",
    )
    preparation_root = Path(preparation_directory).expanduser().resolve()
    preparation = validate_preparation(preparation_root)
    verified = verify_manager_identity_execution_preparation(
        execution_root,
        now=now,
        require_fresh=True,
    )
    if verified.get("verified") is not True or verified.get("fresh_now") is not True:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation verification is incomplete"
        )

    manifest_path = execution_root / "manifest.json"
    manifest = read_json(manifest_path, "manager execution preparation manifest")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation bindings are missing"
        )
    records = _record_digests(manifest)
    required_records = {
        "fresh-manager-rollback.tar.gz",
        "fresh-rollback-manifest.json",
        "live-runtime-gate.json",
        "preclaim-candidate-probe.json",
        "execution-plan.json",
        "operator-runbook.txt",
    }
    if set(records) != required_records:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation record inventory is unexpected"
        )
    if bindings.get("preclaim_candidate_probe_sha256") != records[
        "preclaim-candidate-probe.json"
    ]:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager preclaim candidate probe binding does not match"
        )

    if preparation.get("manifest_sha256") != _require_sha(
        bindings.get("preparation_manifest_sha256"),
        "manager migration preparation manifest",
    ):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager migration preparation does not match execution preparation"
        )
    if preparation.get("record_set_sha256") != _require_sha(
        bindings.get("preparation_record_set_sha256"),
        "manager migration preparation record set",
    ):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager migration preparation record set does not match"
        )

    saved_gate = read_json(
        execution_root / "live-runtime-gate.json",
        "saved manager live runtime gate",
    )
    validate_gate(saved_gate)
    current_gate = live_gate_builder(
        driver,
        preparation_root,
        runner=runner,
    )
    validate_gate(current_gate)
    if canonical(saved_gate) != canonical(current_gate):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager live runtime gate drifted after execution preparation"
        )

    for field in (
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "runtime_binding_sha256",
        "live_binding_sha256",
    ):
        value = _require_sha(bindings.get(field), field)
        if current_gate.get(field) != value:
            raise ManagerIdentityExecutionAuthorizationError(
                f"manager live runtime binding failed: {field}"
            )

    expires = parse_timestamp(
        manifest.get("expires_at"),
        "manager execution preparation expiry",
    )
    if now > expires:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation fresh rollback has expired"
        )
    remaining = int((expires - now).total_seconds())
    if remaining < 60:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution preparation has insufficient freshness for authorization"
        )

    runtime = preparation.get("runtime")
    if not isinstance(runtime, dict):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager migration preparation runtime binding is missing"
        )
    protected = _protected_paths(execution_root, driver, preparation_root, runtime)
    return {
        "execution_root": execution_root,
        "driver": driver,
        "preparation_root": preparation_root,
        "protected_paths": protected,
        "execution_preparation_name": execution_root.name,
        "execution_preparation_manifest_sha256": sha_path(manifest_path),
        "execution_preparation_expires_at": manifest["expires_at"],
        "max_authorization_ttl_seconds": min(1800, remaining),
        "fresh_rollback_archive_sha256": _require_sha(
            bindings.get("fresh_rollback_archive_sha256"),
            "fresh manager rollback archive",
        ),
        "fresh_rollback_manifest_sha256": _require_sha(
            bindings.get("fresh_rollback_manifest_sha256"),
            "fresh manager rollback manifest",
        ),
        "live_runtime_gate_sha256": records["live-runtime-gate.json"],
        "preclaim_candidate_probe_sha256": records[
            "preclaim-candidate-probe.json"
        ],
        "execution_plan_sha256": records["execution-plan.json"],
        "driver_contract_sha256": bindings["driver_contract_sha256"],
        "adapter_contract_sha256": bindings["adapter_contract_sha256"],
        "runtime_binding_sha256": bindings["runtime_binding_sha256"],
        "live_binding_sha256": bindings["live_binding_sha256"],
        "preparation_manifest_sha256": bindings["preparation_manifest_sha256"],
        "preparation_record_set_sha256": bindings[
            "preparation_record_set_sha256"
        ],
    }


def _public_bindings(validated: Mapping[str, Any]) -> dict[str, object]:
    return {field: validated[field] for field in BOUND_FIELDS}


def _request_bindings(request: Mapping[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in BOUND_FIELDS:
        value = request.get(field)
        if not isinstance(value, str):
            raise ManagerIdentityExecutionAuthorizationError(
                f"manager execution authorization request binding is invalid: {field}"
            )
        result[field] = value
    return result


def _confirmation(validated: Mapping[str, Any]) -> str:
    return (
        "AUTHORIZE-M2-MANAGER-EXECUTION:"
        f"{str(validated['execution_preparation_manifest_sha256'])[:16]}:"
        f"{str(validated['fresh_rollback_archive_sha256'])[:16]}:"
        f"{str(validated['live_binding_sha256'])[:16]}"
    )


def _request_from_validated(validated: Mapping[str, Any]) -> dict[str, object]:
    return {
        "schema": REQUEST_SCHEMA,
        "execution_preparation_name": validated["execution_preparation_name"],
        "execution_preparation_expires_at": validated[
            "execution_preparation_expires_at"
        ],
        "max_authorization_ttl_seconds": validated[
            "max_authorization_ttl_seconds"
        ],
        "required_confirmation": _confirmation(validated),
        **_public_bindings(validated),
        "execution_preparation_fresh": True,
        "fresh_runtime_gate_passed": True,
        "fresh_rollback_verified": True,
        "authorization_created": False,
        "single_use": True,
        "operator_decision_required": True,
        "operator_action_authorized": False,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
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


def build_manager_identity_execution_authorization_request(
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    live_gate_builder: LiveGateBuilder = build_manager_identity_live_runtime_gate,
    now: datetime | None = None,
) -> dict[str, object]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    validated = _validated_execution_preparation(
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=runner or SubprocessRunner(),
        live_gate_builder=live_gate_builder,
        now=observed,
    )
    return _request_from_validated(validated)


def create_manager_identity_execution_authorization(
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    output_directory: str | Path,
    *,
    confirmation: str,
    ttl_seconds: int = 600,
    runner: CommandRunner | None = None,
    live_gate_builder: LiveGateBuilder = build_manager_identity_live_runtime_gate,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, object]:
    if ttl_seconds < 60 or ttl_seconds > 1800:
        raise ValueError("authorization TTL must be between 60 and 1800 seconds")
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    command_runner = runner or SubprocessRunner()
    first = _validated_execution_preparation(
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=command_runner,
        live_gate_builder=live_gate_builder,
        now=observed,
    )
    request = _request_from_validated(first)
    required = request.get("required_confirmation")
    if not isinstance(required, str) or not hmac.compare_digest(confirmation, required):
        raise ManagerIdentityExecutionAuthorizationError(
            "explicit manager execution authorization confirmation is missing or does not match"
        )
    if ttl_seconds > int(first["max_authorization_ttl_seconds"]):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization would outlive the fresh rollback package"
        )

    second = _validated_execution_preparation(
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=command_runner,
        live_gate_builder=live_gate_builder,
        now=observed,
    )
    refreshed = _request_from_validated(second)
    if canonical(request) != canonical(refreshed):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution state drifted during authorization creation"
        )

    protected = second.get("protected_paths")
    if not isinstance(protected, tuple):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization protected paths are incomplete"
        )
    output = _private_output(Path(output_directory), protected)
    token = token_factory() if token_factory else secrets.token_urlsafe(32)
    if not isinstance(token, str) or TOKEN.fullmatch(token) is None:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization token is invalid"
        )
    authorization_id = hashlib.sha256(token.encode()).hexdigest()[:24]
    expires = observed + timedelta(seconds=ttl_seconds)
    execution_expires = parse_timestamp(
        second["execution_preparation_expires_at"],
        "manager execution preparation expiry",
    )
    if expires > execution_expires:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization expiry exceeds fresh rollback expiry"
        )
    document = {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_id": authorization_id,
        "authorization_token": token,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "execution_preparation_name": request["execution_preparation_name"],
        "execution_preparation_expires_at": request[
            "execution_preparation_expires_at"
        ],
        **_request_bindings(request),
        "execution_preparation_fresh": True,
        "fresh_runtime_gate_passed": True,
        "fresh_rollback_verified": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_manager_migration_apply": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    destination = output / f"manager-execution-authorization-{authorization_id}.json"
    if destination.exists() or destination.is_symlink():
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization destination already exists"
        )
    write_json(destination, document)
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_file": destination.name,
        "authorization_id": authorization_id,
        "expires_at": document["expires_at"],
        "execution_preparation_expires_at": document[
            "execution_preparation_expires_at"
        ],
        "execution_preparation_manifest_sha256": document[
            "execution_preparation_manifest_sha256"
        ],
        "fresh_rollback_archive_sha256": document[
            "fresh_rollback_archive_sha256"
        ],
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
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


def verify_manager_identity_execution_authorization(
    authorization_file: str | Path,
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    live_gate_builder: LiveGateBuilder = build_manager_identity_live_runtime_gate,
    now: datetime | None = None,
) -> dict[str, object]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    auth_path = private_file(
        Path(authorization_file).expanduser().resolve(),
        "manager execution authorization",
    )
    authorization = read_json(auth_path, "manager execution authorization")
    validated = _validated_execution_preparation(
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=runner or SubprocessRunner(),
        live_gate_builder=live_gate_builder,
        now=observed,
    )
    request = _request_from_validated(validated)
    required: dict[str, object] = {
        "schema": AUTHORIZATION_SCHEMA,
        "execution_preparation_name": request["execution_preparation_name"],
        "execution_preparation_expires_at": request[
            "execution_preparation_expires_at"
        ],
        **_request_bindings(request),
        "execution_preparation_fresh": True,
        "fresh_runtime_gate_passed": True,
        "fresh_rollback_verified": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
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
            raise ManagerIdentityExecutionAuthorizationError(
                f"manager execution authorization binding failed: {field}"
            )

    token = authorization.get("authorization_token")
    authorization_id = authorization.get("authorization_id")
    if (
        not isinstance(token, str)
        or TOKEN.fullmatch(token) is None
        or not isinstance(authorization_id, str)
        or authorization_id != sha_bytes(token.encode())[:24]
    ):
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization token binding is invalid"
        )
    created = parse_timestamp(
        authorization.get("created_at"),
        "manager execution authorization creation",
    )
    expires = parse_timestamp(
        authorization.get("expires_at"),
        "manager execution authorization expiry",
    )
    execution_expires = parse_timestamp(
        authorization.get("execution_preparation_expires_at"),
        "manager execution preparation expiry",
    )
    if expires <= created or (expires - created).total_seconds() > 1800:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization lifetime is invalid"
        )
    if expires > execution_expires:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization outlives fresh rollback"
        )
    if not created <= observed <= expires:
        raise ManagerIdentityExecutionAuthorizationError(
            "manager execution authorization is not currently valid"
        )
    return {
        "schema": VERIFY_SCHEMA,
        "authorization_id": authorization_id,
        "execution_preparation_manifest_sha256": request[
            "execution_preparation_manifest_sha256"
        ],
        "fresh_rollback_archive_sha256": request[
            "fresh_rollback_archive_sha256"
        ],
        "valid_now": True,
        "execution_preparation_fresh": True,
        "fresh_runtime_gate_passed": True,
        "fresh_rollback_verified": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
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
            "Request, create, or verify a short-lived authorization bound to a fresh "
            "manager execution preparation package without claiming or applying it."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    request = subparsers.add_parser("request")
    request.add_argument("execution_preparation_directory")
    request.add_argument("driver_contract_file")
    request.add_argument("preparation_directory")

    create = subparsers.add_parser("create")
    create.add_argument("execution_preparation_directory")
    create.add_argument("driver_contract_file")
    create.add_argument("preparation_directory")
    create.add_argument("output_directory")
    create.add_argument("--confirmation", required=True)
    create.add_argument("--ttl-seconds", type=int, default=600)

    verify = subparsers.add_parser("verify")
    verify.add_argument("authorization_file")
    verify.add_argument("execution_preparation_directory")
    verify.add_argument("driver_contract_file")
    verify.add_argument("preparation_directory")

    args = parser.parse_args(argv)
    try:
        if args.command == "request":
            result = build_manager_identity_execution_authorization_request(
                args.execution_preparation_directory,
                args.driver_contract_file,
                args.preparation_directory,
            )
        elif args.command == "create":
            result = create_manager_identity_execution_authorization(
                args.execution_preparation_directory,
                args.driver_contract_file,
                args.preparation_directory,
                args.output_directory,
                confirmation=args.confirmation,
                ttl_seconds=args.ttl_seconds,
            )
        else:
            result = verify_manager_identity_execution_authorization(
                args.authorization_file,
                args.execution_preparation_directory,
                args.driver_contract_file,
                args.preparation_directory,
            )
    except (
        ManagerIdentityExecutionAuthorizationError,
        ManagerIdentityExecutionPreparationError,
        ManagerIdentityLiveRuntimeGateError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager execution authorization failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
