from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .t1_manager_identity_migration_execution_preparation_common import (
    PLAN_SCHEMA,
    REQUIRED_SEQUENCE,
    SCHEMA,
    ManagerIdentityExecutionPreparationError,
    canonical,
    must,
    parse_timestamp,
    private_dir,
    read_json,
    require_sha,
    sha_path,
    validate_gate,
    verify_rollback_archive,
)
from .t1_manager_identity_migration_execution_preparation_verify_records import (
    verify_execution_records,
    verify_record_bindings,
)
from .t1_manager_identity_migration_preclaim_candidate import (
    validate_preclaim_candidate_report,
)


def verify_manager_identity_execution_preparation(
    directory: str | Path,
    *,
    now: datetime | None = None,
    require_fresh: bool = True,
) -> dict[str, object]:
    root = Path(directory).expanduser().resolve()
    if not root.name.startswith("greenhouse-manager-execution-preparation-"):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation directory name is invalid"
        )
    private_dir(root, "execution preparation directory")
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path, "execution preparation manifest")
    must(
        manifest,
        {
            "schema": SCHEMA,
            "prepared": True,
            "fresh_rollback_captured": True,
            "fresh_rollback_verified": True,
            "execution_preparation_ready": True,
            "preclaim_candidate_probe_passed": True,
            "read_only_live_services": True,
            "current_services_modified": False,
            "authorization_created": False,
            "authorization_claimed": False,
            "production_manager_driver_installed": False,
            "production_executor_available": False,
            "execution_enabled": False,
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
        "execution preparation manifest",
    )
    created = parse_timestamp(
        manifest.get("created_at"),
        "execution preparation creation",
    )
    expires = parse_timestamp(
        manifest.get("expires_at"),
        "execution preparation expiry",
    )
    if expires <= created:
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation expiry is not after creation"
        )
    observed = verify_execution_records(root, manifest)
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation bindings are missing"
        )
    verify_record_bindings(bindings, observed)
    for field in (
        "runtime_binding_sha256",
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "live_binding_sha256",
        "preparation_manifest_sha256",
        "preparation_record_set_sha256",
        "preclaim_candidate_probe_sha256",
    ):
        require_sha(bindings.get(field), field)

    rollback_path = root / "fresh-rollback-manifest.json"
    rollback = read_json(rollback_path, "fresh rollback manifest")
    archived = verify_rollback_archive(root / "fresh-manager-rollback.tar.gz")
    if canonical(rollback) != canonical(archived):
        raise ManagerIdentityExecutionPreparationError(
            "fresh rollback archive and manifest do not match"
        )
    for field in (
        "runtime_binding_sha256",
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "live_binding_sha256",
        "preparation_manifest_sha256",
        "preclaim_candidate_probe_sha256",
    ):
        if rollback.get(field) != bindings.get(field):
            raise ManagerIdentityExecutionPreparationError(
                f"fresh rollback binding failed: {field}"
            )

    gate = read_json(root / "live-runtime-gate.json", "live runtime gate")
    validate_gate(gate)
    for field in (
        "runtime_binding_sha256",
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "live_binding_sha256",
    ):
        if gate.get(field) != bindings.get(field):
            raise ManagerIdentityExecutionPreparationError(
                f"live runtime gate binding failed: {field}"
            )

    preclaim = read_json(
        root / "preclaim-candidate-probe.json",
        "preclaim candidate probe",
    )
    validate_preclaim_candidate_report(preclaim)
    if bindings.get("preclaim_candidate_probe_sha256") != sha_path(
        root / "preclaim-candidate-probe.json"
    ):
        raise ManagerIdentityExecutionPreparationError(
            "preclaim candidate probe binding does not match"
        )

    plan = read_json(root / "execution-plan.json", "execution plan")
    must(
        plan,
        {
            "schema": PLAN_SCHEMA,
            "required_sequence": REQUIRED_SEQUENCE,
            "restart_scope": ["greenhouse-manager"],
            "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
            "fresh_rollback_required": True,
            "fresh_rollback_captured": True,
            "fresh_rollback_verified": True,
            "execution_preparation_ready": True,
            "preclaim_candidate_probe_passed": True,
            "authorization_created": False,
            "authorization_claimed": False,
            "production_manager_driver_installed": False,
            "production_executor_available": False,
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
        "execution plan",
    )
    if (
        plan.get("created_at") != manifest.get("created_at")
        or plan.get("expires_at") != manifest.get("expires_at")
    ):
        raise ManagerIdentityExecutionPreparationError(
            "execution plan freshness binding does not match"
        )
    fresh_now = (now or datetime.now(UTC)).astimezone(UTC) <= expires
    if require_fresh and not fresh_now:
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation fresh rollback has expired"
        )
    return {
        "schema": SCHEMA,
        "verified": True,
        "execution_preparation_name": root.name,
        "manifest_sha256": sha_path(manifest_path),
        "fresh_now": fresh_now,
        "expires_at": manifest["expires_at"],
        "fresh_rollback_verified": True,
        "execution_preparation_ready": True,
        "preclaim_candidate_probe_passed": True,
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
        "secret_values_included": False,
        "path_values_redacted": True,
    }
