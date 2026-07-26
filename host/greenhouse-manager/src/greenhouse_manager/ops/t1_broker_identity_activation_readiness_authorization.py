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

from .t1_broker_identity_activation_readiness_bundle import (
    BrokerIdentityActivationReadinessBundleError,
    verify_activation_readiness_bundle,
)

REQUEST_SCHEMA = (
    "gh.m2.t1-broker-identity-activation-readiness-authorization-request/1"
)
AUTHORIZATION_SCHEMA = (
    "gh.m2.t1-broker-identity-activation-readiness-authorization/1"
)
VERIFY_SCHEMA = (
    "gh.m2.t1-broker-identity-activation-readiness-authorization-verify/1"
)
_OUTPUT_PREFIX = "greenhouse-m2-activation-authorizations"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")

BundleVerifier = Callable[[dict[str, object]], dict[str, object]]
TokenFactory = Callable[[], str]


class BrokerIdentityActivationReadinessAuthorizationError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(value: str) -> str:
    return _sha256_text(value)


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"{label} must be a JSON object"
        )
    return document


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
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _private_output_directory(path: Path) -> Path:
    if not path.name.startswith(_OUTPUT_PREFIX):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization output directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization output directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization output directory must be private"
        )
    return resolved


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"authorization {label} is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            f"authorization {label} is invalid"
        ) from error


def _validated_bundle(
    path: Path,
    verifier: BundleVerifier,
) -> tuple[dict[str, Any], str]:
    bundle = _read_private_json(path, "activation readiness bundle")
    result = verifier(bundle)
    if result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "activation readiness bundle verification is incomplete"
        )
    bundle_sha = _require_sha256(
        result.get("bundle_sha256"),
        "activation readiness bundle",
    )
    if bundle.get("bundle_sha256") != bundle_sha:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "activation readiness bundle binding does not match"
        )
    required = {
        "readiness_bundle_complete": True,
        "operator_decision_required": True,
        "single_use_authorization_created": False,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "path_values_redacted": True,
        "secret_values_included": False,
    }
    for field, expected in required.items():
        if bundle.get(field) is not expected:
            raise BrokerIdentityActivationReadinessAuthorizationError(
                f"activation readiness bundle safety flag failed: {field}"
            )
    return bundle, bundle_sha


def _confirmation(bundle: dict[str, Any], bundle_sha: str) -> str:
    runtime_fingerprint = bundle.get("broker_runtime_fingerprint")
    if (
        not isinstance(runtime_fingerprint, str)
        or _FINGERPRINT.fullmatch(runtime_fingerprint) is None
    ):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "Broker runtime fingerprint is invalid"
        )
    return (
        "AUTHORIZE-M2-BROKER-BUNDLE:"
        f"{bundle_sha[:16]}:{runtime_fingerprint}"
    )


def _binding(bundle: dict[str, Any], bundle_sha: str) -> dict[str, object]:
    fields = {
        "bundle_sha256": bundle_sha,
        "driver_contract_sha256": _require_sha256(
            bundle.get("driver_contract_sha256"),
            "production driver contract",
        ),
        "contract_sha256": _require_sha256(
            bundle.get("contract_sha256"),
            "production executor contract",
        ),
        "mount_binding_sha256": _require_sha256(
            bundle.get("mount_binding_sha256"),
            "mount binding",
        ),
        "runtime_binding_manifest_sha256": _require_sha256(
            bundle.get("runtime_binding_manifest_sha256"),
            "runtime binding manifest",
        ),
        "production_driver_preflight_sha256": _require_sha256(
            bundle.get("production_driver_preflight_sha256"),
            "production driver preflight",
        ),
        "homeassistant_target_gate_sha256": _require_sha256(
            bundle.get("homeassistant_target_gate_sha256"),
            "Home Assistant target gate",
        ),
    }
    runtime_fingerprint = bundle.get("broker_runtime_fingerprint")
    if (
        not isinstance(runtime_fingerprint, str)
        or _FINGERPRINT.fullmatch(runtime_fingerprint) is None
    ):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "Broker runtime fingerprint is invalid"
        )
    homeassistant = bundle.get("homeassistant_binding")
    if not isinstance(homeassistant, dict):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "Home Assistant binding is missing"
        )
    return {
        **fields,
        "broker_runtime_fingerprint": runtime_fingerprint,
        "homeassistant_binding": dict(homeassistant),
    }


def build_activation_readiness_authorization_request(
    activation_readiness_bundle_file: str | Path,
    *,
    bundle_verifier: BundleVerifier = verify_activation_readiness_bundle,
) -> dict[str, object]:
    path = Path(activation_readiness_bundle_file).expanduser().resolve()
    bundle, bundle_sha = _validated_bundle(path, bundle_verifier)
    binding = _binding(bundle, bundle_sha)
    return {
        "schema": REQUEST_SCHEMA,
        "activation_readiness_file": path.name,
        "required_confirmation": _confirmation(bundle, bundle_sha),
        **binding,
        "activation_scope": dict(bundle["activation_scope"]),
        "single_use": True,
        "operator_action_authorized": False,
        "authorization_created": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def create_activation_readiness_authorization(
    activation_readiness_bundle_file: str | Path,
    output_directory: str | Path,
    *,
    confirmation: str,
    ttl_seconds: int = 900,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    bundle_verifier: BundleVerifier = verify_activation_readiness_bundle,
) -> dict[str, object]:
    if ttl_seconds < 60 or ttl_seconds > 1800:
        raise ValueError("authorization TTL must be between 60 and 1800 seconds")
    bundle_path = Path(activation_readiness_bundle_file).expanduser().resolve()
    request = build_activation_readiness_authorization_request(
        bundle_path,
        bundle_verifier=bundle_verifier,
    )
    required_confirmation = request["required_confirmation"]
    if not isinstance(required_confirmation, str) or not hmac.compare_digest(
        confirmation,
        required_confirmation,
    ):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "explicit bundle-bound authorization confirmation is missing or does not match"
        )
    output = _private_output_directory(Path(output_directory).expanduser())
    if output == bundle_path.parent or output.is_relative_to(bundle_path.parent):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization output must be separate from runtime binding artifacts"
        )
    token = token_factory() if token_factory else secrets.token_urlsafe(32)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization token is invalid"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    expires = observed + timedelta(seconds=ttl_seconds)
    authorization_id = _fingerprint(token)[:24]
    document: dict[str, object] = {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_id": authorization_id,
        "authorization_token": token,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "activation_readiness_file": bundle_path.name,
        "bundle_sha256": request["bundle_sha256"],
        "driver_contract_sha256": request["driver_contract_sha256"],
        "contract_sha256": request["contract_sha256"],
        "mount_binding_sha256": request["mount_binding_sha256"],
        "runtime_binding_manifest_sha256": request[
            "runtime_binding_manifest_sha256"
        ],
        "production_driver_preflight_sha256": request[
            "production_driver_preflight_sha256"
        ],
        "homeassistant_target_gate_sha256": request[
            "homeassistant_target_gate_sha256"
        ],
        "broker_runtime_fingerprint": request["broker_runtime_fingerprint"],
        "homeassistant_binding": request["homeassistant_binding"],
        "activation_scope": request["activation_scope"],
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
        "broker-activation-readiness-authorization-"
        f"{authorization_id}.json"
    )
    if destination.exists():
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "authorization destination already exists"
        )
    _atomic_private_write(destination, _canonical_json(document) + "\n")
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorization_file": destination.name,
        "authorization_id": authorization_id,
        "expires_at": document["expires_at"],
        "bundle_sha256": document["bundle_sha256"],
        "single_use": True,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_redacted": True,
        "path_values_redacted": True,
    }


def verify_activation_readiness_authorization(
    authorization_file: str | Path,
    activation_readiness_bundle_file: str | Path,
    *,
    now: datetime | None = None,
    bundle_verifier: BundleVerifier = verify_activation_readiness_bundle,
) -> dict[str, object]:
    auth_path = Path(authorization_file).expanduser().resolve()
    bundle_path = Path(activation_readiness_bundle_file).expanduser().resolve()
    authorization = _read_private_json(auth_path, "activation authorization")
    bundle, bundle_sha = _validated_bundle(bundle_path, bundle_verifier)
    binding = _binding(bundle, bundle_sha)
    required = {
        "schema": AUTHORIZATION_SCHEMA,
        "activation_readiness_file": bundle_path.name,
        **binding,
        "activation_scope": dict(bundle["activation_scope"]),
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
        actual = authorization.get(field)
        if isinstance(expected, str):
            valid = isinstance(actual, str) and hmac.compare_digest(actual, expected)
        else:
            valid = actual == expected
        if not valid:
            raise BrokerIdentityActivationReadinessAuthorizationError(
                f"activation authorization binding failed: {field}"
            )
    token = authorization.get("authorization_token")
    authorization_id = authorization.get("authorization_id")
    if (
        not isinstance(token, str)
        or _TOKEN.fullmatch(token) is None
        or not isinstance(authorization_id, str)
        or authorization_id != _fingerprint(token)[:24]
    ):
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "activation authorization token binding is invalid"
        )
    created = _parse_timestamp(authorization.get("created_at"), "creation timestamp")
    expires = _parse_timestamp(authorization.get("expires_at"), "expiry timestamp")
    if expires <= created or (expires - created).total_seconds() > 1800:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "activation authorization lifetime is invalid"
        )
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    valid_now = created <= observed <= expires
    if not valid_now:
        raise BrokerIdentityActivationReadinessAuthorizationError(
            "activation authorization is not currently valid"
        )
    return {
        "schema": VERIFY_SCHEMA,
        "authorization_id": authorization_id,
        "bundle_sha256": bundle_sha,
        "valid_now": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_redacted": True,
        "path_values_redacted": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build, create, or verify a short-lived single-use authorization bound "
            "to a verified activation readiness bundle without applying it."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("activation_readiness_bundle_file")

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("activation_readiness_bundle_file")
    create_parser.add_argument("output_directory")
    create_parser.add_argument("--confirmation", required=True)
    create_parser.add_argument("--ttl-seconds", type=int, default=900)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("authorization_file")
    verify_parser.add_argument("activation_readiness_bundle_file")

    args = parser.parse_args(argv)
    try:
        if args.command == "request":
            result = build_activation_readiness_authorization_request(
                args.activation_readiness_bundle_file
            )
        elif args.command == "create":
            result = create_activation_readiness_authorization(
                args.activation_readiness_bundle_file,
                args.output_directory,
                confirmation=args.confirmation,
                ttl_seconds=args.ttl_seconds,
            )
        else:
            result = verify_activation_readiness_authorization(
                args.authorization_file,
                args.activation_readiness_bundle_file,
            )
    except (
        BrokerIdentityActivationReadinessAuthorizationError,
        BrokerIdentityActivationReadinessBundleError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker bundle-bound authorization failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
