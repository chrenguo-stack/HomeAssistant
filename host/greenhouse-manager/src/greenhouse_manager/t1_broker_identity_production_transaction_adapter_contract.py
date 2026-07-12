from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .dynsec_api import CONTROL_TOPIC, RESPONSE_TOPIC
from .t1_broker_identity_activation_readiness_transaction_plan import (
    BrokerIdentityActivationReadinessTransactionPlanError,
    verify_activation_readiness_transaction_plan,
)

SCHEMA = "gh.m2.t1-broker-identity-production-transaction-adapter-contract/1"
PlanVerifier = Callable[[dict[str, object]], dict[str, object]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ADAPTER_NAMES = (
    "authorization_claim",
    "runtime_revalidation",
    "snapshot",
    "mutation",
    "broker_restart",
    "dynamic_security_state_wait",
    "dynamic_security_request",
    "postactivation_audit",
    "rollback",
    "journal",
)
_PHASE_ORDER = (
    "authorization_claim",
    "runtime_revalidation",
    "snapshot",
    "mutation",
    "broker_restart",
    "dynamic_security_state_wait",
    "dynamic_security_request",
    "postactivation_audit",
    "journal_commit",
)
_REQUIRED_BLOCKERS = (
    "production_transaction_adapters_not_installed",
    "production_executor_disabled",
    "authorization_claim_disabled",
    "live_apply_entrypoint_absent",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)


class BrokerIdentityProductionTransactionAdapterContractError(RuntimeError):
    pass


class BrokerIdentityProductionTransactionAdapterDisabledError(RuntimeError):
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
        raise BrokerIdentityProductionTransactionAdapterContractError(
            f"{label} fingerprint is invalid"
        )
    return value


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionTransactionAdapterContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionTransactionAdapterContractError(
            f"{label} must be a JSON object"
        )
    return document


def _validate_plan(
    plan: dict[str, object],
    verifier: PlanVerifier,
) -> str:
    result = verifier(plan)
    if result.get("verified") is not True:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "transaction plan verification is incomplete"
        )
    plan_sha = _require_sha256(result.get("plan_sha256"), "transaction plan")
    if plan.get("plan_sha256") != plan_sha:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "transaction plan binding does not match"
        )
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
            raise BrokerIdentityProductionTransactionAdapterContractError(
                f"transaction plan safety flag failed: {field}"
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
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "transaction plan contract has drifted"
        )
    return plan_sha


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


def _runtime_controller_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "container": "mosquitto",
        "allowed_commands": [
            {
                "name": "inspect_mosquitto",
                "argv": ["docker", "inspect", "mosquitto"],
                "mutation": False,
            },
            {
                "name": "restart_mosquitto",
                "argv": ["docker", "restart", "mosquitto"],
                "mutation": True,
            },
        ],
        "shell_allowed": False,
        "docker_exec_allowed": False,
        "docker_cp_allowed": False,
        "docker_create_allowed": False,
        "docker_rm_allowed": False,
        "compose_allowed": False,
        "systemd_allowed": False,
        "ssh_allowed": False,
        "other_service_restart_allowed": False,
        "successful_restart_limit": 1,
        "rollback_restart_may_be_required": True,
    }


def _authorization_claim_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "method": "same_filesystem_hardlink_then_unlink",
        "source_mode_required": "0600",
        "destination_mode_required": "0600",
        "same_filesystem_required": True,
        "claim_directory_private_required": True,
        "claim_name_unique_required": True,
        "source_unlink_after_link_required": True,
        "parent_directory_fsync_required": True,
        "claim_before_mutation_required": True,
        "claim_enabled": False,
    }


def _filesystem_transaction_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "same_directory_temporary_file_required": True,
        "file_fsync_required": True,
        "atomic_replace_required": True,
        "parent_directory_fsync_required": True,
        "mode_and_owner_preservation_required": True,
        "symlink_targets_allowed": False,
        "complete_snapshot_before_first_write_required": True,
        "complete_snapshot_rollback_required": True,
        "rollback_verification_required": True,
    }


def _mqtt_transport_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "implementation": "paho_mqtt_in_process",
        "control_topic": CONTROL_TOPIC,
        "response_topic": RESPONSE_TOPIC,
        "credentials_source": "mode_0600_bound_handoff_files",
        "request_source": "sha256_bound_handoff_json",
        "request_payload_transport": "process_memory",
        "password_in_argv": False,
        "password_in_environment": False,
        "password_in_stdout": False,
        "external_mqtt_cli_allowed": False,
        "shell_allowed": False,
    }


def build_production_transaction_adapter_contract(
    transaction_plan_file: str | Path,
    *,
    plan_verifier: PlanVerifier = verify_activation_readiness_transaction_plan,
) -> dict[str, object]:
    path = Path(transaction_plan_file).expanduser().resolve()
    plan = _read_private_json(path, "transaction plan")
    plan_sha = _validate_plan(plan, plan_verifier)
    bound_fields = {
        field: _require_sha256(plan.get(field), field)
        for field in (
            "authorization_document_sha256",
            "bundle_sha256",
            "driver_contract_sha256",
            "contract_sha256",
            "mount_binding_sha256",
            "runtime_binding_manifest_sha256",
            "production_driver_preflight_sha256",
            "homeassistant_target_gate_sha256",
        )
    }
    contract: dict[str, object] = {
        "schema": SCHEMA,
        "transaction_plan_sha256": plan_sha,
        **bound_fields,
        "phase_order": list(_PHASE_ORDER),
        "adapters": _adapter_inventory(),
        "authorization_claim": _authorization_claim_contract(),
        "filesystem_transaction": _filesystem_transaction_contract(),
        "runtime_controller": _runtime_controller_contract(),
        "mqtt_control_transport": _mqtt_transport_contract(),
        "dynamic_security_state_waiter": {
            "installed": False,
            "callable": False,
            "polls_bound_host_data_path": True,
            "docker_exec_allowed": False,
            "shell_allowed": False,
            "timeout_required": True,
        },
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
            "homeassistant_not_part_of_rollback_scope": True,
            "node_credentials_not_part_of_rollback_scope": True,
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
    contract["adapter_contract_sha256"] = _sha256_document(contract)
    return contract


def verify_production_transaction_adapter_contract(
    contract: dict[str, object],
) -> dict[str, object]:
    if contract.get("schema") != SCHEMA:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production transaction adapter contract schema is invalid"
        )
    digest = _require_sha256(
        contract.get("adapter_contract_sha256"),
        "production transaction adapter contract",
    )
    unsigned = dict(contract)
    unsigned.pop("adapter_contract_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production transaction adapter contract fingerprint does not match"
        )
    for field in (
        "transaction_plan_sha256",
        "authorization_document_sha256",
        "bundle_sha256",
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
        "production_driver_preflight_sha256",
        "homeassistant_target_gate_sha256",
    ):
        _require_sha256(contract.get(field), field)
    required = {
        "contract_review_complete": True,
        "production_transaction_adapter_contract_available": True,
        "production_transaction_adapters_installed": False,
        "authorization_claimed": False,
        "claim_enabled": False,
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
        if contract.get(field) is not expected:
            raise BrokerIdentityProductionTransactionAdapterContractError(
                f"production transaction adapter contract safety flag failed: {field}"
            )
    if contract.get("phase_order") != list(_PHASE_ORDER):
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production transaction phase order has drifted"
        )
    adapters = contract.get("adapters")
    if not isinstance(adapters, dict) or tuple(adapters) != _ADAPTER_NAMES:
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production transaction adapter inventory has drifted"
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
            raise BrokerIdentityProductionTransactionAdapterContractError(
                f"production transaction adapter unexpectedly exposes capability: {name}"
            )
    if contract.get("authorization_claim") != _authorization_claim_contract():
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production authorization claim contract has drifted"
        )
    if contract.get("filesystem_transaction") != _filesystem_transaction_contract():
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production filesystem transaction contract has drifted"
        )
    if contract.get("runtime_controller") != _runtime_controller_contract():
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production runtime controller contract has drifted"
        )
    if contract.get("mqtt_control_transport") != _mqtt_transport_contract():
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production MQTT transport contract has drifted"
        )
    if contract.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityProductionTransactionAdapterContractError(
            "production transaction adapter blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "adapter_contract_sha256": digest,
        "verified": True,
        "production_transaction_adapters_installed": False,
        "authorization_claimed": False,
        "claim_enabled": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def execute_production_transaction_adapter_contract() -> None:
    raise BrokerIdentityProductionTransactionAdapterDisabledError(
        "production transaction adapters are not installed"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a strict, non-callable production transaction adapter contract "
            "from a verified private transaction plan."
        )
    )
    parser.add_argument("transaction_plan_file")
    args = parser.parse_args(argv)
    try:
        result = build_production_transaction_adapter_contract(
            args.transaction_plan_file
        )
        verify_production_transaction_adapter_contract(result)
    except (
        BrokerIdentityActivationReadinessTransactionPlanError,
        BrokerIdentityProductionTransactionAdapterContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker production transaction adapter contract failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
