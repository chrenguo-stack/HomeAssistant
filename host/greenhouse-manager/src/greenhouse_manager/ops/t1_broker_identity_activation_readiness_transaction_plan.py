from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_readiness_authorization import (
    BrokerIdentityActivationReadinessAuthorizationError,
    verify_activation_readiness_authorization,
)
from .t1_broker_identity_activation_readiness_bundle import (
    BrokerIdentityActivationReadinessBundleError,
    verify_activation_readiness_bundle,
)

PLAN_SCHEMA = "gh.m2.t1-broker-identity-activation-readiness-transaction-plan/1"
SUMMARY_SCHEMA = "gh.m2.t1-broker-identity-activation-readiness-transaction-summary/1"
_OUTPUT_PREFIX = "greenhouse-m2-activation-plans"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")
_AUTHORIZATION_ID = re.compile(r"^[0-9a-f]{24}$")
_REQUIRED_BLOCKERS = (
    "production_transaction_adapters_not_installed",
    "authorization_not_claimed",
    "production_executor_disabled",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)

AuthorizationVerifier = Callable[..., dict[str, object]]
BundleVerifier = Callable[[dict[str, object]], dict[str, object]]


class BrokerIdentityActivationReadinessTransactionPlanError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_document(document: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} must be a JSON object"
        )
    return document


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} is invalid"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            f"{label} is invalid"
        ) from error


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
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan output directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan output directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan output directory must be private"
        )
    return resolved


def _validate_bundle(
    path: Path,
    verifier: BundleVerifier,
) -> tuple[dict[str, Any], str]:
    bundle = _read_private_json(path, "activation readiness bundle")
    result = verifier(bundle)
    if result.get("verified") is not True:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "activation readiness bundle verification is incomplete"
        )
    digest = _require_sha256(
        result.get("bundle_sha256"),
        "activation readiness bundle",
    )
    if bundle.get("bundle_sha256") != digest:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "activation readiness bundle binding does not match"
        )
    return bundle, digest


def _authorization_binding(
    authorization: dict[str, Any],
    bundle: dict[str, Any],
    bundle_sha: str,
) -> dict[str, object]:
    authorization_id = authorization.get("authorization_id")
    if (
        not isinstance(authorization_id, str)
        or _AUTHORIZATION_ID.fullmatch(authorization_id) is None
    ):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "authorization ID is invalid"
        )
    expires_at = authorization.get("expires_at")
    _parse_timestamp(expires_at, "authorization expiry timestamp")
    fields = (
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
        "production_driver_preflight_sha256",
        "homeassistant_target_gate_sha256",
    )
    binding: dict[str, object] = {
        "authorization_id": authorization_id,
        "expires_at": expires_at,
        "bundle_sha256": bundle_sha,
        "authorization_document_sha256": _sha256_document(authorization),
    }
    for field in fields:
        expected = _require_sha256(bundle.get(field), field)
        if authorization.get(field) != expected:
            raise BrokerIdentityActivationReadinessTransactionPlanError(
                f"authorization-to-bundle binding failed: {field}"
            )
        binding[field] = expected
    runtime_fingerprint = bundle.get("broker_runtime_fingerprint")
    if (
        not isinstance(runtime_fingerprint, str)
        or _FINGERPRINT.fullmatch(runtime_fingerprint) is None
        or authorization.get("broker_runtime_fingerprint") != runtime_fingerprint
    ):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "authorization-to-bundle Broker runtime binding failed"
        )
    homeassistant = bundle.get("homeassistant_binding")
    scope = bundle.get("activation_scope")
    if (
        not isinstance(homeassistant, dict)
        or authorization.get("homeassistant_binding") != homeassistant
        or not isinstance(scope, dict)
        or authorization.get("activation_scope") != scope
    ):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "authorization-to-bundle activation scope binding failed"
        )
    binding["broker_runtime_fingerprint"] = runtime_fingerprint
    binding["homeassistant_binding"] = dict(homeassistant)
    binding["activation_scope"] = dict(scope)
    return binding


def build_activation_readiness_transaction_plan(
    authorization_file: str | Path,
    activation_readiness_bundle_file: str | Path,
    output_directory: str | Path,
    *,
    now: datetime | None = None,
    authorization_verifier: AuthorizationVerifier = (
        verify_activation_readiness_authorization
    ),
    bundle_verifier: BundleVerifier = verify_activation_readiness_bundle,
) -> dict[str, object]:
    authorization_path = Path(authorization_file).expanduser().resolve()
    bundle_path = Path(activation_readiness_bundle_file).expanduser().resolve()
    output = _private_output_directory(Path(output_directory).expanduser())
    if output in {authorization_path.parent, bundle_path.parent}:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan output must be separate from source artifacts"
        )
    authorization = _read_private_json(
        authorization_path,
        "activation authorization",
    )
    bundle, bundle_sha = _validate_bundle(bundle_path, bundle_verifier)
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    authorization_result = authorization_verifier(
        authorization_path,
        bundle_path,
        now=observed,
        bundle_verifier=bundle_verifier,
    )
    required_authorization = {
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
    for field, expected in required_authorization.items():
        if authorization_result.get(field) is not expected:
            raise BrokerIdentityActivationReadinessTransactionPlanError(
                f"authorization verification failed: {field}"
            )
    binding = _authorization_binding(authorization, bundle, bundle_sha)
    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        **binding,
        "transaction_contract": {
            "authorization_claim_required": True,
            "authorization_claim_method": "same_filesystem_hardlink_then_unlink",
            "private_journal_required": True,
            "postactivation_audit_required": True,
            "rollback_mandatory_on_failure": True,
            "successful_activation_restart_count": 1,
            "rollback_may_require_additional_restart": True,
            "homeassistant_reconfigure_after_activation_only": True,
            "node_credential_delivery_after_activation_only": True,
            "anonymous_closure_forbidden": True,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
        "transaction_plan_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_transaction_adapters_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    plan["plan_sha256"] = _sha256_document(plan)
    destination = output / (
        "broker-activation-transaction-plan-"
        f"{binding['authorization_id']}.json"
    )
    if destination.exists():
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan destination already exists"
        )
    _atomic_private_write(destination, _canonical_json(plan) + "\n")
    return {
        "schema": SUMMARY_SCHEMA,
        "transaction_plan_file": destination.name,
        "plan_sha256": plan["plan_sha256"],
        "authorization_id": binding["authorization_id"],
        "expires_at": binding["expires_at"],
        "bundle_sha256": bundle_sha,
        "transaction_plan_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_transaction_adapters_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_redacted": True,
        "path_values_redacted": True,
    }


def verify_activation_readiness_transaction_plan(
    plan: dict[str, object],
) -> dict[str, object]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan schema is invalid"
        )
    digest = _require_sha256(plan.get("plan_sha256"), "transaction plan")
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan fingerprint does not match"
        )
    for field in (
        "authorization_document_sha256",
        "bundle_sha256",
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
        "production_driver_preflight_sha256",
        "homeassistant_target_gate_sha256",
    ):
        _require_sha256(plan.get(field), field)
    required = {
        "transaction_plan_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_transaction_adapters_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    for field, expected in required.items():
        if plan.get(field) is not expected:
            raise BrokerIdentityActivationReadinessTransactionPlanError(
                f"transaction plan safety flag failed: {field}"
            )
    if plan.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan blockers have drifted"
        )
    expected_contract = {
        "authorization_claim_required": True,
        "authorization_claim_method": "same_filesystem_hardlink_then_unlink",
        "private_journal_required": True,
        "postactivation_audit_required": True,
        "rollback_mandatory_on_failure": True,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
        "homeassistant_reconfigure_after_activation_only": True,
        "node_credential_delivery_after_activation_only": True,
        "anonymous_closure_forbidden": True,
    }
    if plan.get("transaction_contract") != expected_contract:
        raise BrokerIdentityActivationReadinessTransactionPlanError(
            "transaction plan contract has drifted"
        )
    return {
        "schema": PLAN_SCHEMA,
        "plan_sha256": digest,
        "verified": True,
        "transaction_plan_ready": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify a private transaction plan bound to a valid readiness "
            "authorization without claiming it or enabling execution."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("authorization_file")
    build_parser.add_argument("activation_readiness_bundle_file")
    build_parser.add_argument("output_directory")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("transaction_plan_file")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_activation_readiness_transaction_plan(
                args.authorization_file,
                args.activation_readiness_bundle_file,
                args.output_directory,
            )
        else:
            plan = _read_private_json(
                Path(args.transaction_plan_file).expanduser().resolve(),
                "transaction plan",
            )
            result = verify_activation_readiness_transaction_plan(plan)
    except (
        BrokerIdentityActivationReadinessAuthorizationError,
        BrokerIdentityActivationReadinessBundleError,
        BrokerIdentityActivationReadinessTransactionPlanError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker bundle-bound transaction plan failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
