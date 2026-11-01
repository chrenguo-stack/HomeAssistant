from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_authorization import (
    ManagerIdentityExecutionAuthorizationError,
    verify_manager_identity_execution_authorization,
)
from .t1_manager_identity_migration_execution_preparation_common import (
    ManagerIdentityExecutionPreparationError,
    parse_timestamp,
    private_file,
    read_json,
    sha_path,
    validate_gate,
    validate_preparation,
)
from .t1_manager_identity_migration_execution_preparation_verify import (
    verify_manager_identity_execution_preparation,
)
from .t1_manager_identity_migration_live_runtime_gate import (
    ManagerIdentityLiveRuntimeGateError,
    build_manager_identity_live_runtime_gate,
)
from .t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
    verify_manager_production_driver_contract,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-execution-transaction-gate/1"
AUTH_SCHEMA = "gh.m2.t1-manager-identity-execution-authorization/1"
EXECUTION_PREFIX = "greenhouse-manager-execution-preparation-"

AuthorizationVerifier = Callable[..., dict[str, object]]
LiveGateBuilder = Callable[..., dict[str, object]]


class ManagerIdentityExecutionTransactionGateError(RuntimeError):
    pass


def _must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityExecutionTransactionGateError(
                f"{label} verification failed: {field}"
            )


def _execution_root(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.name.startswith(EXECUTION_PREFIX):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution preparation directory name is invalid"
        )
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o077:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution preparation directory is missing or unsafe"
        )
    return root


def _authorization_document(path: Path) -> dict[str, Any]:
    private_file(path, "manager execution authorization")
    document = read_json(path, "manager execution authorization")
    _must(
        document,
        {
            "schema": AUTH_SCHEMA,
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
        },
        "manager execution authorization",
    )
    return document


def _verify_authorization_report(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
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
        },
        "manager execution authorization verification",
    )


def _verify_driver(path: Path, execution_manifest: Mapping[str, Any]) -> str:
    private_file(path, "manager production driver contract")
    contract = read_json(path, "manager production driver contract")
    verified = verify_manager_production_driver_contract(contract)
    if verified.get("verified") is not True:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager production driver contract verification is incomplete"
        )
    logical_sha = verified.get("driver_contract_sha256")
    bindings = execution_manifest.get("bindings")
    if not isinstance(bindings, dict) or logical_sha != bindings.get(
        "driver_contract_sha256"
    ):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager production driver contract does not match execution preparation"
        )
    if contract.get("driver_contract_sha256") != logical_sha:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager production driver logical fingerprint does not match"
        )
    return str(logical_sha)


def _saved_gate(root: Path, execution_manifest: Mapping[str, Any]) -> dict[str, Any]:
    gate_path = root / "live-runtime-gate.json"
    private_file(gate_path, "saved manager live runtime gate")
    gate = read_json(gate_path, "saved manager live runtime gate")
    validate_gate(gate)
    records = execution_manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution preparation record inventory is missing"
        )
    record = next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get("path") == "live-runtime-gate.json"
        ),
        None,
    )
    if not isinstance(record, dict) or record.get("sha256") != sha_path(gate_path):
        raise ManagerIdentityExecutionTransactionGateError(
            "saved manager live runtime gate record does not match"
        )
    return gate


def _confirmation(
    authorization_id: str,
    execution_manifest_sha256: str,
    rollback_sha256: str,
    live_binding_sha256: str,
) -> str:
    return (
        "EXECUTE-M2-MANAGER-MIGRATION:"
        f"{authorization_id}:"
        f"{execution_manifest_sha256[:16]}:"
        f"{rollback_sha256[:16]}:"
        f"{live_binding_sha256[:16]}"
    )


def build_manager_identity_execution_transaction_gate(
    authorization_file: str | Path,
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    authorization_verifier: AuthorizationVerifier = (
        verify_manager_identity_execution_authorization
    ),
    live_gate_builder: LiveGateBuilder = build_manager_identity_live_runtime_gate,
) -> dict[str, object]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    command_runner = runner or SubprocessRunner()
    authorization_path = Path(authorization_file).expanduser().resolve()
    execution_root = _execution_root(execution_preparation_directory)
    driver_path = Path(driver_contract_file).expanduser().resolve()
    preparation_root = Path(preparation_directory).expanduser().resolve()

    authorization_document = _authorization_document(authorization_path)
    authorization = authorization_verifier(
        authorization_path,
        execution_root,
        driver_path,
        preparation_root,
        runner=command_runner,
        live_gate_builder=live_gate_builder,
        now=observed,
    )
    _verify_authorization_report(authorization)

    verified_execution = verify_manager_identity_execution_preparation(
        execution_root,
        now=observed,
        require_fresh=True,
    )
    _must(
        verified_execution,
        {
            "verified": True,
            "fresh_now": True,
            "fresh_rollback_verified": True,
            "execution_preparation_ready": True,
            "authorization_created": False,
            "execution_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        },
        "manager execution preparation",
    )

    preparation = validate_preparation(preparation_root)
    execution_manifest_path = execution_root / "manifest.json"
    execution_manifest = read_json(
        execution_manifest_path,
        "manager execution preparation manifest",
    )
    bindings = execution_manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution preparation bindings are missing"
        )
    if preparation.get("manifest_sha256") != bindings.get(
        "preparation_manifest_sha256"
    ) or preparation.get("record_set_sha256") != bindings.get(
        "preparation_record_set_sha256"
    ):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager migration preparation does not match execution preparation"
        )

    driver_sha = _verify_driver(driver_path, execution_manifest)
    saved_gate = _saved_gate(execution_root, execution_manifest)
    current_gate = live_gate_builder(
        driver_path,
        preparation_root,
        runner=command_runner,
    )
    validate_gate(current_gate)
    if current_gate != saved_gate:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager live runtime gate drifted after authorization verification"
        )

    authorization_id = authorization_document.get("authorization_id")
    if not isinstance(authorization_id, str) or not authorization_id:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution authorization ID is missing"
        )
    if authorization.get("authorization_id") != authorization_id:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution authorization ID binding failed"
        )

    auth_expires = parse_timestamp(
        authorization_document.get("expires_at"),
        "manager execution authorization expiry",
    )
    execution_expires = parse_timestamp(
        execution_manifest.get("expires_at"),
        "manager execution preparation expiry",
    )
    if observed > auth_expires or observed > execution_expires:
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution authorization or rollback package has expired"
        )

    execution_manifest_sha = sha_path(execution_manifest_path)
    rollback_sha = bindings.get("fresh_rollback_archive_sha256")
    live_binding_sha = bindings.get("live_binding_sha256")
    if not isinstance(rollback_sha, str) or not isinstance(live_binding_sha, str):
        raise ManagerIdentityExecutionTransactionGateError(
            "manager execution rollback or live binding is missing"
        )

    return {
        "schema": SCHEMA,
        "transaction_gate_ready": True,
        "authorization_id": authorization_id,
        "authorization_valid": True,
        "authorization_single_use": True,
        "authorization_expires_at": authorization_document["expires_at"],
        "execution_preparation_name": execution_root.name,
        "execution_preparation_expires_at": execution_manifest["expires_at"],
        "execution_preparation_manifest_sha256": execution_manifest_sha,
        "fresh_rollback_archive_sha256": rollback_sha,
        "driver_contract_sha256": driver_sha,
        "adapter_contract_sha256": bindings["adapter_contract_sha256"],
        "runtime_binding_sha256": bindings["runtime_binding_sha256"],
        "live_binding_sha256": live_binding_sha,
        "preclaim_candidate_probe_sha256": bindings[
            "preclaim_candidate_probe_sha256"
        ],
        "required_confirmation": _confirmation(
            authorization_id,
            execution_manifest_sha,
            rollback_sha,
            live_binding_sha,
        ),
        "operator_decision_required": True,
        "second_operator_confirmation_present": False,
        "authorization_claim_required": True,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "rollback_mandatory_on_any_post_claim_failure": True,
        "postactivation_audit_mandatory": True,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only second-confirmation gate for a future manager-only "
            "migration transaction without claiming authorization or applying changes."
        )
    )
    parser.add_argument("authorization_file")
    parser.add_argument("execution_preparation_directory")
    parser.add_argument("driver_contract_file")
    parser.add_argument("preparation_directory")
    args = parser.parse_args(argv)
    try:
        result = build_manager_identity_execution_transaction_gate(
            args.authorization_file,
            args.execution_preparation_directory,
            args.driver_contract_file,
            args.preparation_directory,
        )
    except (
        ManagerIdentityExecutionTransactionGateError,
        ManagerIdentityExecutionAuthorizationError,
        ManagerIdentityExecutionPreparationError,
        ManagerIdentityLiveRuntimeGateError,
        ManagerIdentityProductionDriverContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager execution transaction gate failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
