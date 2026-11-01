from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "gh.m2.t1-manager-identity-production-transaction-adapter-contract/1"
PREPARATION_SCHEMA = "gh.m2.t1-manager-identity-migration-preparation/1"
AUTHORIZATION_SCHEMA = "gh.m2.t1-manager-identity-migration-authorization/1"
RUNTIME_SCHEMA = "gh.m2.t1-manager-runtime-binding/1"
TRANSACTION_PLAN_SCHEMA = "gh.m2.t1-manager-identity-migration-transaction-plan/1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PREPARATION_PREFIX = "greenhouse-manager-migration-preparation-"
_EXPECTED_RECORDS = {
    "material/manager/manager.env": True,
    "material/manager/password": True,
    "material/manager/compose-secret-fragment.yaml": True,
    "manager-runtime-binding.json": True,
    "transaction-plan.json": False,
    "operator-runbook.txt": False,
}
_MANAGER_KEYS = {
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD_FILE",
    "GH_MQTT_CLIENT_ID",
}
_REQUIRED_SEQUENCE = [
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
]
_ADAPTER_NAMES = (
    "authorization_claim",
    "runtime_revalidation",
    "fresh_rollback_verification",
    "password_write",
    "environment_write",
    "overlay_write",
    "manager_recreate",
    "identity_check",
    "ingress_check",
    "canonical_check",
    "discovery_check",
    "reconnect_check",
    "existing_entities_check",
    "postactivation_audit",
    "rollback",
    "journal",
)
_PHASE_ORDER = (
    "authorization_claim",
    "runtime_revalidation",
    "fresh_rollback_verification",
    "password_write",
    "environment_write",
    "overlay_write",
    "manager_recreate",
    "identity_check",
    "ingress_check",
    "canonical_check",
    "discovery_check",
    "reconnect_check",
    "existing_entities_check",
    "postactivation_audit",
    "journal_commit",
)
_REQUIRED_BLOCKERS = (
    "production_transaction_adapters_not_installed",
    "production_executor_disabled",
    "authorization_claim_disabled",
    "live_apply_entrypoint_absent",
    "fresh_manager_rollback_not_captured",
    "manager_live_runtime_mount_gate_pending",
    "real_node_credential_delivery_unverified",
)
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


class ManagerIdentityProductionTransactionAdapterContractError(RuntimeError):
    pass


class ManagerIdentityProductionTransactionAdapterDisabledError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} fingerprint is invalid"
        )
    return value


def _fingerprint(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))[:16]


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} must be a JSON object"
        )
    return document


def _read_key_values(path: Path, label: str) -> dict[str, str]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeError as error:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is not UTF-8"
        ) from error
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"{label} contains invalid entries"
            )
        values[key] = value
    return values


def _must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"{label} safety flag failed: {field}"
            )


def _private_preparation_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if (
        not root.name.startswith(_PREPARATION_PREFIX)
        or not root.is_dir()
        or root.is_symlink()
        or root.stat().st_mode & 0o077
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager migration preparation directory is missing or unsafe"
        )
    return root


def _verify_records(root: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager preparation record inventory is missing"
        )
    observed: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager preparation record inventory is invalid"
            )
        raw = record.get("path")
        if not isinstance(raw, str):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager preparation record path is invalid"
            )
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts or raw in observed:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager preparation record path is unsafe"
            )
        if raw not in _EXPECTED_RECORDS:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager preparation record inventory is unexpected"
            )
        path = root.joinpath(*relative.parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"manager preparation record is unsafe: {raw}"
            )
        digest = _sha_path(path)
        if (
            path.stat().st_size != record.get("size")
            or digest != record.get("sha256")
            or record.get("contains_secret") is not _EXPECTED_RECORDS[raw]
        ):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"manager preparation record verification failed: {raw}"
            )
        observed[raw] = digest
    if set(observed) != set(_EXPECTED_RECORDS):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager preparation record inventory is incomplete"
        )
    return observed


def _absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is missing"
        )
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ManagerIdentityProductionTransactionAdapterContractError(
            f"{label} is unsafe"
        )
    return path.resolve()


def _validate_preparation(preparation_directory: str | Path) -> dict[str, object]:
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
        },
        "manager migration preparation manifest",
    )
    records = _verify_records(root, manifest)
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager preparation bindings are missing"
        )

    runtime = _read_private_json(
        root / "manager-runtime-binding.json",
        "manager runtime binding",
    )
    _must(
        runtime,
        {
            "schema": RUNTIME_SCHEMA,
            "read_only_capture": True,
            "current_services_modified": False,
        },
        "manager runtime binding",
    )
    container = runtime.get("container")
    compose = runtime.get("compose")
    if not isinstance(container, dict) or not isinstance(compose, dict):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager runtime or Compose binding is incomplete"
        )
    if (
        container.get("state") != "running"
        or container.get("restart_count") != 0
        or container.get("mqtt_username_present") is not False
        or container.get("mqtt_password_present") is not False
        or container.get("mqtt_password_file_present") is not False
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager runtime baseline is unsafe"
        )
    project = compose.get("project")
    working_dir = _absolute_path(
        compose.get("working_dir"),
        "manager Compose working directory",
    )
    config_files = compose.get("config_files")
    if (
        not isinstance(project, str)
        or not project
        or not isinstance(config_files, list)
        or not config_files
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager Compose binding is incomplete"
        )
    for record in config_files:
        if not isinstance(record, dict):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager Compose file binding is invalid"
            )
        _absolute_path(record.get("path"), "manager Compose file")
        _require_sha256(record.get("sha256"), "manager Compose file")
    environment = compose.get("environment")
    if environment is not None:
        if not isinstance(environment, dict):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager Compose environment binding is invalid"
            )
        _absolute_path(environment.get("path"), "manager Compose environment")
        _require_sha256(
            environment.get("sha256"),
            "manager Compose environment",
        )

    secret_root = _absolute_path(
        runtime.get("target_secret_root"),
        "manager secret root",
    )
    password_target = _absolute_path(
        runtime.get("target_password_file"),
        "manager password target",
    )
    if not password_target.is_relative_to(secret_root):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager password target escaped the secret root"
        )

    plan = _read_private_json(
        root / "transaction-plan.json",
        "manager transaction plan",
    )
    _must(
        plan,
        {
            "schema": TRANSACTION_PLAN_SCHEMA,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_apply": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "restart_scope": ["greenhouse-manager"],
            "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
            "required_sequence": _REQUIRED_SEQUENCE,
            "node_credentials_delivered": False,
        },
        "manager transaction plan",
    )

    values = _read_key_values(
        root / "material/manager/manager.env",
        "manager environment material",
    )
    if set(values) != _MANAGER_KEYS:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager environment material has an unexpected key set"
        )
    username = values["GH_MQTT_USERNAME"]
    client_id = values["GH_MQTT_CLIENT_ID"]
    if (
        bindings.get("manager_runtime_binding_sha256")
        != records["manager-runtime-binding.json"]
        or bindings.get("manager_runtime_fingerprint")
        != _fingerprint(_canonical_json(container))
        or bindings.get("compose_binding_fingerprint")
        != _fingerprint(_canonical_json(compose))
        or bindings.get("manager_username_fingerprint") != _fingerprint(username)
        or bindings.get("manager_client_id_fingerprint") != _fingerprint(client_id)
    ):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager preparation identity or runtime binding does not match"
        )

    return {
        "preparation_manifest_sha256": _sha_path(manifest_path),
        "manager_runtime_binding_sha256": records["manager-runtime-binding.json"],
        "transaction_plan_sha256": records["transaction-plan.json"],
        "manager_env_sha256": records["material/manager/manager.env"],
        "manager_password_sha256": records["material/manager/password"],
        "manager_fragment_sha256": records[
            "material/manager/compose-secret-fragment.yaml"
        ],
        "manager_runtime_fingerprint": bindings["manager_runtime_fingerprint"],
        "compose_binding_fingerprint": bindings["compose_binding_fingerprint"],
        "postactivation_manifest_sha256": _require_sha256(
            bindings.get("postactivation_manifest_sha256"),
            "postactivation manifest",
        ),
        "migration_stage_manifest_sha256": _require_sha256(
            bindings.get("migration_stage_manifest_sha256"),
            "migration stage manifest",
        ),
        "compose_project_fingerprint": _fingerprint(project),
        "compose_working_directory_fingerprint": _fingerprint(str(working_dir)),
        "compose_config_set_fingerprint": _fingerprint(
            _canonical_json(config_files)
        ),
        "active_secret_root_fingerprint": _fingerprint(str(secret_root)),
        "active_password_target_fingerprint": _fingerprint(str(password_target)),
        "manager_username_fingerprint": _fingerprint(username),
        "manager_client_id_fingerprint": _fingerprint(client_id),
    }


def _adapter_inventory() -> dict[str, dict[str, object]]:
    return {
        name: {
            "installed": False,
            "callable": False,
            "host_write_capability": False,
            "docker_mutation_capability": False,
            "mqtt_publish_capability": False,
            "authorization_claim_capability": False,
        }
        for name in _ADAPTER_NAMES
    }


def _authorization_claim_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "authorization_schema": AUTHORIZATION_SCHEMA,
        "required_bound_fields": list(_BOUND_FIELDS),
        "method": "same_filesystem_hardlink_then_unlink",
        "source_mode_required": "0600",
        "destination_mode_required": "0600",
        "same_filesystem_required": True,
        "claim_directory_private_required": True,
        "claim_name_unique_required": True,
        "source_unlink_after_link_required": True,
        "parent_directory_fsync_required": True,
        "claim_before_first_write_required": True,
        "authorization_must_be_valid_and_unconsumed": True,
        "claim_enabled": False,
    }


def _fresh_rollback_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "capture_before_authorization_creation_required": True,
        "freshness_max_seconds": 900,
        "complete_compose_tree_snapshot_required": True,
        "complete_manager_secret_tree_snapshot_required": True,
        "inventory_sha256_required": True,
        "archive_sha256_required": True,
        "mode_owner_and_type_inventory_required": True,
        "binds_preparation_manifest_required": True,
        "binds_runtime_and_compose_fingerprints_required": True,
        "binds_active_secret_and_password_target_required": True,
        "restore_rehearsal_required": True,
        "rollback_verification_required": True,
        "rollback_failure_is_terminal": True,
    }


def _filesystem_transaction_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "allowed_mutations": [
            "manager_password_atomic_write",
            "manager_auth_environment_atomic_write",
            "manager_compose_overlay_atomic_write",
        ],
        "same_directory_temporary_file_required": True,
        "file_fsync_required": True,
        "atomic_replace_required": True,
        "parent_directory_fsync_required": True,
        "mode_0600_required": True,
        "owner_preservation_required": True,
        "symlink_targets_allowed": False,
        "writes_outside_bound_targets_allowed": False,
        "complete_snapshot_before_first_write_required": True,
    }


def _runtime_controller_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "container": "greenhouse-manager",
        "allowed_commands": [
            {
                "name": "inspect_greenhouse_manager",
                "argv": ["docker", "inspect", "greenhouse-manager"],
                "mutation": False,
            },
            {
                "name": "compose_recreate_greenhouse_manager",
                "argv_template": [
                    "docker",
                    "compose",
                    "--project-name",
                    "<bound-project>",
                    "--project-directory",
                    "<bound-working-directory>",
                    "--file",
                    "<each-bound-config-file>",
                    "--file",
                    "<bound-manager-auth-overlay>",
                    "up",
                    "-d",
                    "--no-deps",
                    "--force-recreate",
                    "greenhouse-manager",
                ],
                "mutation": True,
            },
        ],
        "shell_allowed": False,
        "docker_exec_allowed": False,
        "docker_cp_allowed": False,
        "docker_restart_allowed": False,
        "docker_create_allowed": False,
        "docker_rm_allowed": False,
        "systemd_allowed": False,
        "ssh_allowed": False,
        "other_service_targets_allowed": False,
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
        "successful_recreate_limit": 1,
        "rollback_recreate_may_be_required": True,
    }


def _postactivation_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "manager_authenticated_username_required": True,
        "manager_independent_client_id_required": True,
        "ingress_subscription_required": True,
        "canonical_state_publication_required": True,
        "homeassistant_discovery_publication_required": True,
        "reconnect_required": True,
        "existing_homeassistant_entities_refresh_required": True,
        "manager_restart_count_zero_required": True,
        "broker_identity_activated_required": True,
        "homeassistant_authenticated_required": True,
        "anonymous_compatibility_preserved_required": True,
        "node_credentials_unchanged_required": True,
    }


def _rollback_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "trigger_on_any_post_claim_failure": True,
        "restore_complete_compose_and_secret_snapshot_required": True,
        "remove_manager_auth_mutation_state_required": True,
        "recreate_only_greenhouse_manager_required": True,
        "legacy_manager_path_verification_required": True,
        "existing_homeassistant_entities_refresh_required": True,
        "restored_inventory_exact_match_required": True,
        "rollback_journal_commit_required": True,
        "rollback_failure_is_terminal": True,
        "mosquitto_rollback_forbidden": True,
        "homeassistant_rollback_forbidden": True,
        "node_credential_rollback_forbidden": True,
    }


def build_manager_production_transaction_adapter_contract(
    preparation_directory: str | Path,
) -> dict[str, object]:
    bindings = _validate_preparation(preparation_directory)
    contract: dict[str, object] = {
        "schema": SCHEMA,
        **bindings,
        "phase_order": list(_PHASE_ORDER),
        "adapters": _adapter_inventory(),
        "authorization_claim": _authorization_claim_contract(),
        "fresh_rollback": _fresh_rollback_contract(),
        "filesystem_transaction": _filesystem_transaction_contract(),
        "runtime_controller": _runtime_controller_contract(),
        "postactivation": _postactivation_contract(),
        "rollback": _rollback_contract(),
        "journal": {
            "installed": False,
            "callable": False,
            "mode_required": "0600",
            "append_and_fsync_each_phase_required": True,
            "secret_values_forbidden": True,
            "raw_host_paths_forbidden": True,
        },
        "failure_policy": {
            "rollback_on_any_post_claim_failure": True,
            "rollback_failure_is_terminal": True,
            "postactivation_failure_requires_rollback": True,
            "authorization_claim_is_not_reversible": True,
            "mosquitto_not_part_of_transaction_scope": True,
            "homeassistant_not_part_of_transaction_scope": True,
            "node_credentials_not_part_of_transaction_scope": True,
        },
        "execution_interface": {
            "entrypoint_installed": False,
            "claim_subcommand_present": False,
            "execute_subcommand_present": False,
            "enable_flag_present": False,
            "apply_flag_present": False,
            "live_flag_present": False,
            "host_path_arguments_supported": False,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
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
    }
    contract["adapter_contract_sha256"] = _sha_bytes(
        _canonical_json(contract).encode("utf-8")
    )
    return contract


def verify_manager_production_transaction_adapter_contract(
    contract: dict[str, object],
) -> dict[str, object]:
    if contract.get("schema") != SCHEMA:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager production transaction adapter contract schema is invalid"
        )
    digest = _require_sha256(
        contract.get("adapter_contract_sha256"),
        "manager production transaction adapter contract",
    )
    unsigned = dict(contract)
    unsigned.pop("adapter_contract_sha256", None)
    if _sha_bytes(_canonical_json(unsigned).encode("utf-8")) != digest:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager production transaction adapter contract fingerprint does not match"
        )
    fingerprint_fields = (
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
    sha_fields = tuple(field for field in _BOUND_FIELDS if field not in fingerprint_fields)
    for field in sha_fields:
        _require_sha256(contract.get(field), field)
    for field in fingerprint_fields:
        value = contract.get(field)
        if not isinstance(value, str) or len(value) != 16:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"{field} fingerprint is invalid"
            )
    required = {
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
    }
    for field, expected in required.items():
        if contract.get(field) is not expected:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager production transaction adapter contract safety flag failed: "
                f"{field}"
            )
    if contract.get("phase_order") != list(_PHASE_ORDER):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager production transaction phase order has drifted"
        )
    adapters = contract.get("adapters")
    if not isinstance(adapters, dict) or tuple(adapters) != _ADAPTER_NAMES:
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager production transaction adapter inventory has drifted"
        )
    for name in _ADAPTER_NAMES:
        adapter = adapters.get(name)
        if not isinstance(adapter, dict) or any(
            adapter.get(field) is not False
            for field in (
                "installed",
                "callable",
                "host_write_capability",
                "docker_mutation_capability",
                "mqtt_publish_capability",
                "authorization_claim_capability",
            )
        ):
            raise ManagerIdentityProductionTransactionAdapterContractError(
                "manager production transaction adapter unexpectedly exposes capability: "
                f"{name}"
            )
    expected_sections = {
        "authorization_claim": _authorization_claim_contract(),
        "fresh_rollback": _fresh_rollback_contract(),
        "filesystem_transaction": _filesystem_transaction_contract(),
        "runtime_controller": _runtime_controller_contract(),
        "postactivation": _postactivation_contract(),
        "rollback": _rollback_contract(),
    }
    for name, expected in expected_sections.items():
        if contract.get(name) != expected:
            raise ManagerIdentityProductionTransactionAdapterContractError(
                f"manager production {name} contract has drifted"
            )
    if contract.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise ManagerIdentityProductionTransactionAdapterContractError(
            "manager production transaction adapter blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "adapter_contract_sha256": digest,
        "verified": True,
        "production_transaction_adapters_installed": False,
        "authorization_claimed": False,
        "claim_enabled": False,
        "fresh_rollback_bound": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def execute_manager_production_transaction_adapter_contract() -> None:
    raise ManagerIdentityProductionTransactionAdapterDisabledError(
        "manager production transaction adapters are not installed"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a strict, non-callable greenhouse-manager identity production "
            "transaction adapter contract from a private preparation package."
        )
    )
    parser.add_argument("preparation_directory")
    args = parser.parse_args(argv)
    try:
        result = build_manager_production_transaction_adapter_contract(
            args.preparation_directory
        )
        verify_manager_production_transaction_adapter_contract(result)
    except (
        ManagerIdentityProductionTransactionAdapterContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 manager production transaction adapter contract failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
