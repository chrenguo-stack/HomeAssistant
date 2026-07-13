from __future__ import annotations

import re

SCHEMA = "gh.m2.t1-manager-identity-execution-preparation/1"
ROLLBACK_SCHEMA = "gh.m2.t1-manager-identity-fresh-rollback/1"
PLAN_SCHEMA = "gh.m2.t1-manager-identity-execution-plan/1"
LIVE_GATE_SCHEMA = "gh.m2.t1-manager-identity-live-runtime-gate/1"
RUNTIME_SCHEMA = "gh.m2.t1-manager-runtime-binding/1"
PREPARATION_SCHEMA = "gh.m2.t1-manager-identity-migration-preparation/1"
OUTPUT_PREFIX = "greenhouse-m2-manager-execution-preparations"
PREPARATION_PREFIX = "greenhouse-manager-migration-preparation-"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PREPARATION_RECORDS = {
    "material/manager/manager.env": True,
    "material/manager/password": True,
    "material/manager/compose-secret-fragment.yaml": True,
    "manager-runtime-binding.json": True,
    "transaction-plan.json": False,
    "operator-runbook.txt": False,
}
EXECUTION_RECORDS = {
    "fresh-manager-rollback.tar.gz": True,
    "fresh-rollback-manifest.json": True,
    "live-runtime-gate.json": False,
    "execution-plan.json": False,
    "operator-runbook.txt": False,
}
GATE_FLAGS = {
    "schema": LIVE_GATE_SCHEMA,
    "read_only": True,
    "live_runtime_gate_ready": True,
    "ready_for_fresh_rollback_preparation": True,
    "production_manager_driver_installed": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "operator_action_authorized": False,
    "ready_for_manager_migration_apply": False,
    "manager_identity_migrated": False,
    "node_credentials_delivered": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
    "secret_values_included": False,
    "path_values_redacted": True,
}
GATE_CHECKS = {
    "driver_contract_verified",
    "adapter_contract_rebuilt_and_bound",
    "runtime_binding_hash_verified",
    "manager_running_zero_restart",
    "manager_runtime_identity_unchanged",
    "manager_authentication_not_active",
    "compose_project_unchanged",
    "compose_files_and_environment_unchanged",
    "runtime_security_profile_preserved",
    "read_only_rootfs",
    "not_privileged",
    "all_capabilities_dropped",
    "no_new_privileges",
    "active_secret_root_private_or_absent",
    "manager_password_target_absent",
    "manager_password_mount_absent",
    "single_read_only_docker_inspect_model",
}
REQUIRED_SEQUENCE = [
    "verify_execution_preparation_and_freshness",
    "create_short_lived_single_use_authorization_bound_to_execution_preparation",
    "claim_authorization",
    "revalidate_live_runtime_gate",
    "atomically_install_manager_password",
    "apply_exact_manager_compose_overlay",
    "recreate_only_greenhouse_manager",
    "verify_manager_authenticated_client_id",
    "verify_ingress_subscription",
    "verify_canonical_and_discovery_publication",
    "verify_reconnect_and_existing_entities",
    "rollback_from_fresh_archive_on_any_failure",
]


class ManagerIdentityExecutionPreparationError(RuntimeError):
    pass
