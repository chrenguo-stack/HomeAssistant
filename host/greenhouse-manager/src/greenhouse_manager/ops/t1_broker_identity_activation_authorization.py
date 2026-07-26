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
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    BrokerIdentityActivationHandoffError,
    Runner,
    Verifier,
    read_json,
    sha256_path,
    validated_handoff,
)
from .t1_broker_identity_activation_handoff import (
    verify_broker_identity_activation_handoff,
)
from .t1_broker_identity_preactivation_gate import (
    build_broker_identity_preactivation_gate,
)
from .t1_shadow import SubprocessRunner

REQUEST_SCHEMA = "gh.m2.t1-broker-identity-activation-authorization-request/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-broker-identity-activation-authorization/1"
VERIFY_SCHEMA = "gh.m2.t1-broker-identity-activation-authorization-verify/1"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

PreactivationBuilder = Callable[..., dict[str, object]]
TokenFactory = Callable[[], str]


class BrokerIdentityActivationAuthorizationError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise BrokerIdentityActivationAuthorizationError(
            "authorization directory must be private and not a symlink"
        )


def _atomic_private_write(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _confirmation(root: Path) -> str:
    digest = sha256_path(root / "manifest.json")
    return f"AUTHORIZE-M2-BROKER:{root.name}:{digest[:16]}"


def _validate_preactivation(report: dict[str, object]) -> None:
    required = {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "read_only": True,
        "preconditions_ready": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationAuthorizationError(
                f"preactivation gate is unsafe or incomplete: {field}"
            )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityActivationAuthorizationError(
            "preactivation checks are not all passing"
        )


def _run_preactivation(
    root: Path,
    stage: Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str,
    runner: Runner,
    handoff_verifier: Verifier,
    preactivation_builder: PreactivationBuilder,
) -> dict[str, object]:
    report = preactivation_builder(
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=runner,
        handoff_verifier=handoff_verifier,
    )
    _validate_preactivation(report)
    return report


def build_activation_authorization_request(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    runner: Runner | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    preactivation_builder: PreactivationBuilder = (
        build_broker_identity_preactivation_gate
    ),
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    validated_handoff(root, handoff_verifier)
    report = _run_preactivation(
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=command_runner,
        handoff_verifier=handoff_verifier,
        preactivation_builder=preactivation_builder,
    )
    return {
        "schema": REQUEST_SCHEMA,
        "preconditions_ready": True,
        "required_confirmation": _confirmation(root),
        "handoff": root.name,
        "handoff_manifest_sha256": sha256_path(root / "manifest.json"),
        "stage_manifest_sha256": sha256_path(stage / "stage-manifest.json"),
        "target_kind": report.get("target_kind"),
        "target_fingerprint": report.get("target_fingerprint"),
        "entry_fingerprint": report.get("entry_fingerprint"),
        "storage_sha256": report.get("storage_sha256"),
        "single_use": True,
        "operator_action_authorized": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def create_activation_authorization(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    confirmation: str,
    expected_target_kind: str = "loopback",
    ttl_seconds: int = 900,
    runner: Runner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    preactivation_builder: PreactivationBuilder = (
        build_broker_identity_preactivation_gate
    ),
) -> dict[str, object]:
    if ttl_seconds < 60 or ttl_seconds > 3600:
        raise ValueError("authorization TTL must be between 60 and 3600 seconds")
    command_runner = runner or SubprocessRunner()
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not hmac.compare_digest(confirmation, _confirmation(root)):
        raise BrokerIdentityActivationAuthorizationError(
            "explicit authorization confirmation is missing or does not match"
        )
    request = build_activation_authorization_request(
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=command_runner,
        handoff_verifier=handoff_verifier,
        preactivation_builder=preactivation_builder,
    )
    _private_directory(output)
    token = token_factory() if token_factory else secrets.token_urlsafe(24)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise BrokerIdentityActivationAuthorizationError(
            "authorization token is invalid"
        )
    created = (now or datetime.now(UTC)).astimezone(UTC)
    expires = created + timedelta(seconds=ttl_seconds)
    document = {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_id": _fingerprint(token)[:24],
        "authorization_token": token,
        "created_at": created.isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "expires_at": expires.isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "handoff": request["handoff"],
        "handoff_manifest_sha256": request["handoff_manifest_sha256"],
        "stage_manifest_sha256": request["stage_manifest_sha256"],
        "target_kind": request["target_kind"],
        "target_fingerprint": request["target_fingerprint"],
        "entry_fingerprint": request["entry_fingerprint"],
        "storage_sha256": request["storage_sha256"],
        "retained_topic_fingerprint": _fingerprint(
            expected_retained_topic
        )[:24],
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    destination = output / (
        f"broker-activation-authorization-{document['authorization_id']}.json"
    )
    if destination.exists():
        raise BrokerIdentityActivationAuthorizationError(
            "authorization destination already exists"
        )
    _atomic_private_write(destination, _json(document))
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_file": str(destination),
        "authorization_id": document["authorization_id"],
        "expires_at": document["expires_at"],
        "handoff": document["handoff"],
        "single_use": True,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BrokerIdentityActivationAuthorizationError(
            f"authorization {label} is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise BrokerIdentityActivationAuthorizationError(
            f"authorization {label} is invalid"
        ) from error


def verify_activation_authorization(
    authorization_file: str | Path,
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    now: datetime | None = None,
) -> dict[str, object]:
    path = Path(authorization_file).expanduser().resolve()
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationAuthorizationError(
            "authorization file is missing or unsafe"
        )
    document = read_json(path, "activation authorization")
    required = {
        "schema": AUTHORIZATION_SCHEMA,
        "handoff": root.name,
        "handoff_manifest_sha256": sha256_path(root / "manifest.json"),
        "stage_manifest_sha256": sha256_path(stage / "stage-manifest.json"),
        "target_kind": expected_target_kind,
        "target_fingerprint": expected_target_fingerprint,
        "entry_fingerprint": expected_entry_fingerprint,
        "storage_sha256": expected_storage_sha256,
        "retained_topic_fingerprint": _fingerprint(
            expected_retained_topic
        )[:24],
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        actual = document.get(field)
        if isinstance(expected, str):
            valid = isinstance(actual, str) and hmac.compare_digest(
                actual,
                expected,
            )
        else:
            valid = actual == expected
        if not valid:
            raise BrokerIdentityActivationAuthorizationError(
                f"authorization binding failed: {field}"
            )
    token = document.get("authorization_token")
    authorization_id = document.get("authorization_id")
    if (
        not isinstance(token, str)
        or _TOKEN.fullmatch(token) is None
        or not isinstance(authorization_id, str)
        or not hmac.compare_digest(
            authorization_id,
            _fingerprint(token)[:24],
        )
    ):
        raise BrokerIdentityActivationAuthorizationError(
            "authorization token binding is invalid"
        )
    created = _parse_timestamp(document.get("created_at"), "created_at")
    expires = _parse_timestamp(document.get("expires_at"), "expires_at")
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    if expires <= created or observed < created or observed >= expires:
        raise BrokerIdentityActivationAuthorizationError(
            "authorization is not currently valid"
        )
    return {
        "schema": VERIFY_SCHEMA,
        "authorization_id": authorization_id,
        "handoff": root.name,
        "valid_now": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build, create, or verify a one-time Broker activation "
            "authorization without modifying live services."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    request = commands.add_parser("request")
    authorize = commands.add_parser("authorize")
    verify = commands.add_parser("verify")
    for command in (request, authorize):
        command.add_argument("handoff_directory")
        command.add_argument("stage_directory")
        command.add_argument("--expected-retained-topic", required=True)
        command.add_argument("--expected-target-fingerprint", required=True)
        command.add_argument("--expected-entry-fingerprint", required=True)
        command.add_argument("--expected-storage-sha256", required=True)
        command.add_argument("--expected-target-kind", default="loopback")
    authorize.add_argument("--output", required=True)
    authorize.add_argument("--confirm", required=True)
    authorize.add_argument("--ttl-seconds", type=int, default=900)
    verify.add_argument("authorization_file")
    verify.add_argument("handoff_directory")
    verify.add_argument("stage_directory")
    verify.add_argument("--expected-retained-topic", required=True)
    verify.add_argument("--expected-target-fingerprint", required=True)
    verify.add_argument("--expected-entry-fingerprint", required=True)
    verify.add_argument("--expected-storage-sha256", required=True)
    verify.add_argument("--expected-target-kind", default="loopback")
    args = parser.parse_args(argv)
    common = {
        "expected_retained_topic": args.expected_retained_topic,
        "expected_target_fingerprint": args.expected_target_fingerprint,
        "expected_entry_fingerprint": args.expected_entry_fingerprint,
        "expected_storage_sha256": args.expected_storage_sha256,
        "expected_target_kind": args.expected_target_kind,
    }
    try:
        if args.command == "request":
            result = build_activation_authorization_request(
                args.handoff_directory,
                args.stage_directory,
                runner=runner,
                **common,
            )
        elif args.command == "authorize":
            result = create_activation_authorization(
                args.handoff_directory,
                args.stage_directory,
                args.output,
                confirmation=args.confirm,
                ttl_seconds=args.ttl_seconds,
                runner=runner,
                **common,
            )
        else:
            result = verify_activation_authorization(
                args.authorization_file,
                args.handoff_directory,
                args.stage_directory,
                **common,
            )
    except (
        BrokerIdentityActivationAuthorizationError,
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker activation authorization failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
