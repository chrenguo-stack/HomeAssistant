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
from .t1_broker_identity_production_adapter_skeleton import (
    BrokerIdentityProductionAdapterSkeletonError,
    verify_production_adapter_skeleton,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)

SCHEMA = "gh.m2.t1-broker-identity-production-driver-contract/1"
LIVE_MOUNT_GATE_SCHEMA = "gh.m2.t1-broker-identity-live-mount-gate/1"
ContractVerifier = Callable[[dict[str, object]], dict[str, object]]
SkeletonVerifier = Callable[[dict[str, object]], dict[str, object]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_DOCKER_COMMANDS = (
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
)
_FORBIDDEN_COMMAND_TOKENS = {
    "compose",
    "cp",
    "create",
    "exec",
    "kill",
    "rm",
    "run",
    "start",
    "stop",
    "systemctl",
    "ssh",
}
_REQUIRED_BLOCKERS = (
    "production_driver_runtime_binding_manifest_missing",
    "production_driver_not_installed",
    "explicit_operator_authorization_not_claimed",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)


class BrokerIdentityProductionDriverContractError(RuntimeError):
    pass


class BrokerIdentityProductionDriverDisabledError(RuntimeError):
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


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionDriverContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionDriverContractError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionDriverContractError(
            f"{label} must be a JSON object"
        )
    return document


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityProductionDriverContractError(
            f"{label} fingerprint is invalid"
        )
    return value


def _validate_executor_contract(
    contract: dict[str, object],
    verifier: ContractVerifier,
) -> tuple[str, list[str]]:
    result = verifier(contract)
    if result.get("verified") is not True:
        raise BrokerIdentityProductionDriverContractError(
            "production executor contract verification is incomplete"
        )
    digest = _require_sha256(
        result.get("contract_sha256"),
        "production executor contract",
    )
    required = {
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if contract.get(field) is not expected:
            raise BrokerIdentityProductionDriverContractError(
                f"production executor contract safety flag failed: {field}"
            )
    scope = contract.get("mutation_scope")
    targets = scope.get("allowed_container_targets") if isinstance(scope, dict) else None
    if not isinstance(targets, list) or not targets or not all(
        isinstance(item, str) and item.startswith("/mosquitto/") for item in targets
    ):
        raise BrokerIdentityProductionDriverContractError(
            "production executor mutation target allowlist is invalid"
        )
    return digest, list(targets)


def _validate_skeleton(
    skeleton: dict[str, object],
    *,
    contract_sha256: str,
    verifier: SkeletonVerifier,
) -> tuple[str, str]:
    result = verifier(skeleton)
    if result.get("verified") is not True:
        raise BrokerIdentityProductionDriverContractError(
            "production adapter skeleton verification is incomplete"
        )
    digest = _require_sha256(
        result.get("skeleton_sha256"),
        "production adapter skeleton",
    )
    if skeleton.get("contract_sha256") != contract_sha256:
        raise BrokerIdentityProductionDriverContractError(
            "production adapter skeleton contract binding does not match"
        )
    mount_sha = _require_sha256(
        skeleton.get("mount_binding_sha256"),
        "production adapter skeleton mount binding",
    )
    required = {
        "production_adapter_skeleton_available": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if skeleton.get(field) is not expected:
            raise BrokerIdentityProductionDriverContractError(
                f"production adapter skeleton safety flag failed: {field}"
            )
    return digest, mount_sha


def _validate_live_mount_gate(
    gate: dict[str, object],
    *,
    contract_sha256: str,
    mount_binding_sha256: str,
) -> None:
    if gate.get("schema") != LIVE_MOUNT_GATE_SCHEMA:
        raise BrokerIdentityProductionDriverContractError(
            "live mount gate schema is invalid"
        )
    required = {
        "read_only": True,
        "mount_binding_ready": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if gate.get(field) is not expected:
            raise BrokerIdentityProductionDriverContractError(
                f"live mount gate safety flag failed: {field}"
            )
    if gate.get("contract_sha256") != contract_sha256:
        raise BrokerIdentityProductionDriverContractError(
            "live mount gate contract binding does not match"
        )
    if gate.get("mount_binding_sha256") != mount_binding_sha256:
        raise BrokerIdentityProductionDriverContractError(
            "live mount gate mount binding does not match"
        )
    checks = gate.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityProductionDriverContractError(
            "live mount gate checks are not all passing"
        )


def _runtime_controller_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "container": "mosquitto",
        "commands": [dict(item) for item in _DOCKER_COMMANDS],
        "shell_allowed": False,
        "docker_exec_allowed": False,
        "docker_cp_allowed": False,
        "compose_allowed": False,
        "systemd_allowed": False,
        "ssh_allowed": False,
        "other_service_restart_allowed": False,
        "secret_values_in_argv": False,
    }


def _mqtt_transport_contract() -> dict[str, object]:
    return {
        "installed": False,
        "callable": False,
        "implementation": "paho_mqtt_in_process",
        "control_topic": CONTROL_TOPIC,
        "response_topic": RESPONSE_TOPIC,
        "broker_target_source": "verified_preactivation_target",
        "credentials_source": "mode_0600_bound_handoff_files",
        "request_source": "sha256_bound_handoff_json",
        "request_payload_transport": "process_memory",
        "password_in_argv": False,
        "password_in_environment": False,
        "password_in_stdout": False,
        "shell_allowed": False,
        "external_mqtt_cli_allowed": False,
    }


def build_production_driver_contract(
    executor_contract_file: str | Path,
    adapter_skeleton_file: str | Path,
    live_mount_gate_file: str | Path,
    *,
    executor_verifier: ContractVerifier = verify_production_executor_contract,
    skeleton_verifier: SkeletonVerifier = verify_production_adapter_skeleton,
) -> dict[str, object]:
    executor_path = Path(executor_contract_file).expanduser().resolve()
    skeleton_path = Path(adapter_skeleton_file).expanduser().resolve()
    gate_path = Path(live_mount_gate_file).expanduser().resolve()
    executor = _read_private_json(executor_path, "production executor contract")
    skeleton = _read_private_json(skeleton_path, "production adapter skeleton")
    gate = _read_private_json(gate_path, "live mount gate")

    contract_sha, allowed_targets = _validate_executor_contract(
        executor,
        executor_verifier,
    )
    skeleton_sha, mount_sha = _validate_skeleton(
        skeleton,
        contract_sha256=contract_sha,
        verifier=skeleton_verifier,
    )
    _validate_live_mount_gate(
        gate,
        contract_sha256=contract_sha,
        mount_binding_sha256=mount_sha,
    )

    result: dict[str, object] = {
        "schema": SCHEMA,
        "contract_sha256": contract_sha,
        "skeleton_sha256": skeleton_sha,
        "mount_binding_sha256": mount_sha,
        "filesystem_transaction": {
            "installed": False,
            "callable": False,
            "host_paths_resolved": False,
            "allowed_container_targets": allowed_targets,
            "same_directory_atomic_replace_required": True,
            "file_fsync_required": True,
            "parent_directory_fsync_required": True,
            "complete_snapshot_rollback_required": True,
            "symlink_targets_allowed": False,
        },
        "runtime_controller": _runtime_controller_contract(),
        "mqtt_control_transport": _mqtt_transport_contract(),
        "dynamic_security_state_waiter": {
            "installed": False,
            "callable": False,
            "source": "private_runtime_binding_manifest",
            "polls_bound_data_path_directly": True,
            "shell_allowed": False,
            "docker_exec_allowed": False,
        },
        "execution_interface": {
            "entrypoint_installed": False,
            "execute_subcommand_present": False,
            "enable_flag_present": False,
            "apply_flag_present": False,
            "live_flag_present": False,
            "authorization_claim_supported": False,
            "host_path_arguments_supported": False,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
        "driver_contract_review_complete": True,
        "production_driver_contract_available": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    result["driver_contract_sha256"] = _sha256_document(result)
    return result


def verify_production_driver_contract(
    contract: dict[str, object],
) -> dict[str, object]:
    if contract.get("schema") != SCHEMA:
        raise BrokerIdentityProductionDriverContractError(
            "production driver contract schema is invalid"
        )
    digest = _require_sha256(
        contract.get("driver_contract_sha256"),
        "production driver contract",
    )
    unsigned = dict(contract)
    unsigned.pop("driver_contract_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityProductionDriverContractError(
            "production driver contract fingerprint does not match"
        )
    for field in ("contract_sha256", "skeleton_sha256", "mount_binding_sha256"):
        _require_sha256(contract.get(field), field)
    required = {
        "driver_contract_review_complete": True,
        "production_driver_contract_available": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if contract.get(field) is not expected:
            raise BrokerIdentityProductionDriverContractError(
                f"production driver contract safety flag failed: {field}"
            )

    controller = contract.get("runtime_controller")
    if not isinstance(controller, dict):
        raise BrokerIdentityProductionDriverContractError(
            "production driver runtime controller is missing"
        )
    if controller.get("commands") != [dict(item) for item in _DOCKER_COMMANDS]:
        raise BrokerIdentityProductionDriverContractError(
            "production driver command allowlist has drifted"
        )
    for item in _DOCKER_COMMANDS:
        argv = item["argv"]
        if any(token in _FORBIDDEN_COMMAND_TOKENS for token in argv[1:]):
            raise BrokerIdentityProductionDriverContractError(
                "production driver command allowlist contains a forbidden token"
            )
    controller_required = {
        "installed": False,
        "callable": False,
        "container": "mosquitto",
        "shell_allowed": False,
        "docker_exec_allowed": False,
        "docker_cp_allowed": False,
        "compose_allowed": False,
        "systemd_allowed": False,
        "ssh_allowed": False,
        "other_service_restart_allowed": False,
        "secret_values_in_argv": False,
    }
    for field, expected in controller_required.items():
        actual = controller.get(field)
        if isinstance(expected, bool):
            matches = actual is expected
        else:
            matches = actual == expected
        if not matches:
            raise BrokerIdentityProductionDriverContractError(
                f"production driver runtime controller has drifted: {field}"
            )

    transport = contract.get("mqtt_control_transport")
    if not isinstance(transport, dict) or transport != _mqtt_transport_contract():
        raise BrokerIdentityProductionDriverContractError(
            "production driver MQTT transport contract has drifted"
        )
    if contract.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityProductionDriverContractError(
            "production driver blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "driver_contract_sha256": digest,
        "verified": True,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def execute_production_driver_contract() -> None:
    raise BrokerIdentityProductionDriverDisabledError(
        "production Broker driver is not installed"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a strict, default-disabled production Broker driver command "
            "contract without installing any runtime capability."
        )
    )
    parser.add_argument("executor_contract_file")
    parser.add_argument("adapter_skeleton_file")
    parser.add_argument("live_mount_gate_file")
    args = parser.parse_args(argv)
    try:
        result = build_production_driver_contract(
            args.executor_contract_file,
            args.adapter_skeleton_file,
            args.live_mount_gate_file,
        )
        verify_production_driver_contract(result)
    except (
        BrokerIdentityProductionAdapterSkeletonError,
        BrokerIdentityProductionDriverContractError,
        BrokerIdentityProductionExecutorContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker production driver contract failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
