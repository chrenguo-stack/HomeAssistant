from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_production_transaction_adapter_contract import (
    ManagerIdentityProductionTransactionAdapterContractError,
    verify_manager_production_transaction_adapter_contract,
)

SCHEMA = "gh.m2.t1-manager-identity-production-driver-contract/1"
ADAPTER_CONTRACT_SCHEMA = (
    "gh.m2.t1-manager-identity-production-transaction-adapter-contract/1"
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")
AdapterVerifier = Callable[[dict[str, object]], dict[str, object]]

_BOUND_SHA_FIELDS = (
    "preparation_manifest_sha256",
    "manager_runtime_binding_sha256",
    "transaction_plan_sha256",
    "manager_env_sha256",
    "manager_password_sha256",
    "manager_fragment_sha256",
    "postactivation_manifest_sha256",
    "migration_stage_manifest_sha256",
)
_BOUND_FINGERPRINT_FIELDS = (
    "manager_runtime_fingerprint",
    "compose_binding_fingerprint",
    "compose_project_fingerprint",
    "compose_working_directory_fingerprint",
    "compose_config_set_fingerprint",
    "active_secret_root_fingerprint",
    "active_password_target_fingerprint",
    "manager_username_fingerprint",
    "manager_client_id_fingerprint",
)
_METHODS = (
    "claim_authorization",
    "revalidate_runtime",
    "verify_fresh_rollback",
    "install_manager_material",
    "recreate_manager",
    "verify_authenticated_identity",
    "verify_ingress_subscription",
    "verify_canonical_publication",
    "verify_discovery_publication",
    "verify_reconnect",
    "verify_existing_entities",
    "postactivation_audit",
    "rollback",
    "append_journal",
)
_REQUIRED_BLOCKERS = (
    "production_manager_driver_not_installed",
    "production_manager_runtime_binding_manifest_missing",
    "manager_live_runtime_mount_gate_pending",
    "fresh_manager_rollback_not_bound",
    "authorization_claim_disabled",
    "second_exact_operator_confirmation_missing",
    "real_node_credential_delivery_unverified",
)


class ManagerIdentityProductionDriverContractError(RuntimeError):
    pass


class ManagerIdentityProductionDriverDisabledError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_document(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManagerIdentityProductionDriverContractError(f"{label} is invalid")
    return value


def _require_fingerprint(value: object, label: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT.fullmatch(value) is None:
        raise ManagerIdentityProductionDriverContractError(f"{label} is invalid")
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityProductionDriverContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityProductionDriverContractError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityProductionDriverContractError(
            f"{label} must be a JSON object"
        )
    return document


def _must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityProductionDriverContractError(
                f"{label} safety flag failed: {field}"
            )


def _validate_adapter_contract(
    adapter: dict[str, object],
    verifier: AdapterVerifier,
) -> dict[str, str]:
    result = verifier(adapter)
    if result.get("verified") is not True:
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter contract verification is incomplete"
        )
    adapter_sha = _require_sha(
        result.get("adapter_contract_sha256"),
        "manager adapter contract SHA-256",
    )
    if adapter.get("adapter_contract_sha256") != adapter_sha:
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter contract binding does not match"
        )
    _must(
        adapter,
        {
            "schema": ADAPTER_CONTRACT_SCHEMA,
            "contract_review_complete": True,
            "production_transaction_adapter_contract_available": True,
            "production_transaction_adapters_installed": False,
            "authorization_claimed": False,
            "claim_enabled": False,
            "fresh_rollback_bound": False,
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
        },
        "manager adapter contract",
    )
    bindings = {"adapter_contract_sha256": adapter_sha}
    for field in _BOUND_SHA_FIELDS:
        bindings[field] = _require_sha(adapter.get(field), field)
    for field in _BOUND_FINGERPRINT_FIELDS:
        bindings[field] = _require_fingerprint(adapter.get(field), field)
    return bindings


def _validate_adapter_sections(adapter: Mapping[str, Any]) -> None:
    authorization = adapter.get("authorization_claim")
    filesystem = adapter.get("filesystem_transaction")
    controller = adapter.get("runtime_controller")
    postactivation = adapter.get("postactivation")
    rollback = adapter.get("rollback")
    if not all(
        isinstance(section, dict)
        for section in (authorization, filesystem, controller, postactivation, rollback)
    ):
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter contract sections are incomplete"
        )
    if authorization.get("claim_enabled") is not False:
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter authorization claim unexpectedly enabled"
        )
    if filesystem.get("allowed_mutations") != [
        "manager_password_atomic_write",
        "manager_auth_environment_atomic_write",
        "manager_compose_overlay_atomic_write",
    ]:
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter filesystem allowlist has drifted"
        )
    commands = controller.get("allowed_commands")
    if not isinstance(commands, list) or len(commands) != 2:
        raise ManagerIdentityProductionDriverContractError(
            "manager adapter command allowlist is incomplete"
        )
    if commands[0] != {
        "name": "inspect_greenhouse_manager",
        "argv": ["docker", "inspect", "greenhouse-manager"],
        "mutation": False,
    }:
        raise ManagerIdentityProductionDriverContractError(
            "manager inspect command has drifted"
        )
    recreate = commands[1]
    argv = recreate.get("argv_template") if isinstance(recreate, dict) else None
    if (
        not isinstance(recreate, dict)
        or recreate.get("name") != "compose_recreate_greenhouse_manager"
        or recreate.get("mutation") is not True
        or not isinstance(argv, list)
        or argv[-1:] != ["greenhouse-manager"]
        or "--no-deps" not in argv
        or "--force-recreate" not in argv
    ):
        raise ManagerIdentityProductionDriverContractError(
            "manager recreate command has drifted"
        )
    for field in (
        "mosquitto_target_allowed",
        "homeassistant_target_allowed",
        "node_target_allowed",
    ):
        if controller.get(field) is not False:
            raise ManagerIdentityProductionDriverContractError(
                f"manager adapter runtime scope drifted: {field}"
            )
    if postactivation.get("existing_homeassistant_entities_refresh_required") is not True:
        raise ManagerIdentityProductionDriverContractError(
            "manager postactivation entity continuity requirement is missing"
        )
    if rollback.get("rollback_failure_is_terminal") is not True:
        raise ManagerIdentityProductionDriverContractError(
            "manager rollback terminal policy is missing"
        )


def _method_inventory() -> dict[str, dict[str, object]]:
    return {
        name: {
            "installed": False,
            "callable": False,
            "host_path_access": False,
            "host_write_capability": False,
            "docker_mutation_capability": False,
            "mqtt_probe_capability": False,
            "authorization_claim_capability": False,
        }
        for name in _METHODS
    }


def _runtime_driver_contract(adapter: Mapping[str, Any]) -> dict[str, object]:
    controller = adapter["runtime_controller"]
    assert isinstance(controller, dict)
    return {
        "installed": False,
        "callable": False,
        "container": "greenhouse-manager",
        "allowed_commands": controller["allowed_commands"],
        "command_construction": {
            "project_source": "bound_compose_project",
            "working_directory_source": "bound_compose_working_directory",
            "config_files_source": "bound_compose_config_set",
            "auth_overlay_source": "transaction_private_overlay",
            "service_target": "greenhouse-manager",
            "shell_allowed": False,
            "string_command_allowed": False,
        },
        "successful_recreate_limit": 1,
        "rollback_recreate_may_be_required": True,
        "other_service_targets_allowed": False,
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
    }


def build_manager_production_driver_contract(
    adapter_contract_file: str | Path,
    *,
    adapter_verifier: AdapterVerifier = (
        verify_manager_production_transaction_adapter_contract
    ),
) -> dict[str, object]:
    path = Path(adapter_contract_file).expanduser().resolve()
    adapter = _read_private_json(path, "manager production adapter contract")
    bindings = _validate_adapter_contract(adapter, adapter_verifier)
    _validate_adapter_sections(adapter)
    filesystem = adapter["filesystem_transaction"]
    assert isinstance(filesystem, dict)
    result: dict[str, object] = {
        "schema": SCHEMA,
        **bindings,
        "methods": _method_inventory(),
        "authorization_claim_driver": {
            "installed": False,
            "callable": False,
            "schema_source": "bound_adapter_contract",
            "method": "same_filesystem_hardlink_then_unlink",
            "valid_unconsumed_authorization_required": True,
            "claim_before_first_write_required": True,
            "claim_enabled": False,
        },
        "runtime_driver": _runtime_driver_contract(adapter),
        "filesystem_driver": {
            "installed": False,
            "callable": False,
            "operations": filesystem["allowed_mutations"],
            "same_directory_temporary_file_required": True,
            "file_fsync_required": True,
            "atomic_replace_required": True,
            "parent_directory_fsync_required": True,
            "mode_0600_required": True,
            "symlink_targets_allowed": False,
            "host_paths_resolved": False,
        },
        "fresh_rollback_driver": {
            "installed": False,
            "callable": False,
            "freshness_max_seconds": 900,
            "complete_compose_and_secret_snapshot_required": True,
            "restore_rehearsal_required": True,
            "inventory_and_archive_hashes_required": True,
            "fresh_rollback_bound": False,
        },
        "verification_driver": {
            "installed": False,
            "callable": False,
            "checks": [
                "authenticated_manager_identity",
                "independent_manager_client_id",
                "ingress_subscription",
                "canonical_state_publication",
                "homeassistant_discovery_publication",
                "reconnect",
                "existing_homeassistant_entities_refresh",
                "manager_restart_count_zero",
                "broker_and_homeassistant_authentication_preserved",
                "anonymous_compatibility_preserved",
                "node_credentials_unchanged",
            ],
            "mqtt_probe_implementation_selected": False,
            "host_runtime_probe_implementation_selected": False,
        },
        "rollback_driver": {
            "installed": False,
            "callable": False,
            "trigger_on_any_post_claim_failure": True,
            "complete_snapshot_restore_required": True,
            "recreate_only_greenhouse_manager_required": True,
            "legacy_path_and_entity_refresh_verification_required": True,
            "exact_inventory_match_required": True,
            "rollback_failure_is_terminal": True,
        },
        "journal_driver": {
            "installed": False,
            "callable": False,
            "mode_required": "0600",
            "append_and_fsync_each_phase_required": True,
            "secret_values_forbidden": True,
            "raw_host_paths_forbidden": True,
        },
        "execution_interface": {
            "entrypoint_installed": False,
            "execute_subcommand_present": False,
            "claim_subcommand_present": False,
            "enable_flag_present": False,
            "apply_flag_present": False,
            "live_flag_present": False,
            "host_path_arguments_supported": False,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
        "driver_contract_review_complete": True,
        "production_manager_driver_contract_available": True,
        "production_manager_driver_installed": False,
        "authorization_claimed": False,
        "claim_enabled": False,
        "fresh_rollback_bound": False,
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
    result["driver_contract_sha256"] = _sha_document(result)
    return result


def verify_manager_production_driver_contract(
    contract: dict[str, object],
) -> dict[str, object]:
    if contract.get("schema") != SCHEMA:
        raise ManagerIdentityProductionDriverContractError(
            "manager production driver contract schema is invalid"
        )
    digest = _require_sha(
        contract.get("driver_contract_sha256"),
        "manager production driver contract SHA-256",
    )
    unsigned = dict(contract)
    unsigned.pop("driver_contract_sha256", None)
    if _sha_document(unsigned) != digest:
        raise ManagerIdentityProductionDriverContractError(
            "manager production driver contract fingerprint does not match"
        )
    _require_sha(contract.get("adapter_contract_sha256"), "adapter contract SHA-256")
    for field in _BOUND_SHA_FIELDS:
        _require_sha(contract.get(field), field)
    for field in _BOUND_FINGERPRINT_FIELDS:
        _require_fingerprint(contract.get(field), field)
    _must(
        contract,
        {
            "driver_contract_review_complete": True,
            "production_manager_driver_contract_available": True,
            "production_manager_driver_installed": False,
            "authorization_claimed": False,
            "claim_enabled": False,
            "fresh_rollback_bound": False,
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
        },
        "manager production driver contract",
    )
    methods = contract.get("methods")
    if not isinstance(methods, dict) or tuple(methods) != _METHODS:
        raise ManagerIdentityProductionDriverContractError(
            "manager production driver method inventory has drifted"
        )
    for name in _METHODS:
        method = methods.get(name)
        if not isinstance(method, dict) or any(
            value is not False for value in method.values()
        ):
            raise ManagerIdentityProductionDriverContractError(
                "manager production driver method unexpectedly exposes capability: "
                f"{name}"
            )
    runtime = contract.get("runtime_driver")
    if not isinstance(runtime, dict) or runtime.get("container") != "greenhouse-manager":
        raise ManagerIdentityProductionDriverContractError(
            "manager production runtime driver has drifted"
        )
    if runtime.get("mosquitto_target_allowed") is not False:
        raise ManagerIdentityProductionDriverContractError(
            "manager production driver unexpectedly targets Mosquitto"
        )
    if contract.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise ManagerIdentityProductionDriverContractError(
            "manager production driver blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "driver_contract_sha256": digest,
        "verified": True,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def execute_manager_production_driver_contract() -> None:
    raise ManagerIdentityProductionDriverDisabledError(
        "production greenhouse-manager driver is not installed"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a strict, default-disabled greenhouse-manager production driver "
            "contract without installing runtime capability."
        )
    )
    parser.add_argument("adapter_contract_file")
    args = parser.parse_args(argv)
    try:
        result = build_manager_production_driver_contract(args.adapter_contract_file)
        verify_manager_production_driver_contract(result)
    except (
        ManagerIdentityProductionTransactionAdapterContractError,
        ManagerIdentityProductionDriverContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager production driver contract failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
