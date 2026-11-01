from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)

SCHEMA = "gh.m2.t1-broker-identity-production-adapter-skeleton/1"
LIVE_MOUNT_GATE_SCHEMA = "gh.m2.t1-broker-identity-live-mount-gate/1"
ContractVerifier = Callable[[dict[str, object]], dict[str, object]]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_ADAPTER_NAMES = ("mutation", "postactivation", "rollback")
_REQUIRED_BLOCKERS = (
    "production_adapters_not_installed",
    "explicit_operator_authorization_not_claimed",
    "homeassistant_official_mqtt_ui_config_flow_pending",
    "real_node_credential_delivery_unverified",
)


class BrokerIdentityProductionAdapterSkeletonError(RuntimeError):
    pass


class BrokerIdentityProductionAdapterDisabledError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_document(document: dict[str, object]) -> str:
    payload = _canonical_json(document).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionAdapterSkeletonError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionAdapterSkeletonError(
            f"{label} is invalid"
        ) from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionAdapterSkeletonError(
            f"{label} must be a JSON object"
        )
    return document


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BrokerIdentityProductionAdapterSkeletonError(
            f"{label} fingerprint is invalid"
        )
    return value


def _validate_contract(
    contract: dict[str, object],
    verifier: ContractVerifier,
) -> str:
    verified = verifier(contract)
    if verified.get("verified") is not True:
        raise BrokerIdentityProductionAdapterSkeletonError(
            "production executor contract verification is incomplete"
        )
    digest = _require_sha256(
        verified.get("contract_sha256"),
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
            raise BrokerIdentityProductionAdapterSkeletonError(
                f"production executor contract safety flag failed: {field}"
            )
    return digest


def _validate_live_mount_gate(
    gate: dict[str, object],
    *,
    contract_sha256: str,
) -> str:
    if gate.get("schema") != LIVE_MOUNT_GATE_SCHEMA:
        raise BrokerIdentityProductionAdapterSkeletonError(
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
            raise BrokerIdentityProductionAdapterSkeletonError(
                f"live mount gate safety flag failed: {field}"
            )
    if gate.get("contract_sha256") != contract_sha256:
        raise BrokerIdentityProductionAdapterSkeletonError(
            "live mount gate contract binding does not match"
        )
    checks = gate.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityProductionAdapterSkeletonError(
            "live mount gate checks are not all passing"
        )
    return _require_sha256(
        gate.get("mount_binding_sha256"),
        "live mount gate",
    )


def _adapter_specs() -> dict[str, dict[str, object]]:
    return {
        "mutation": {
            "installed": False,
            "callable": False,
            "host_write_capability": False,
            "docker_mutation_capability": False,
            "authorization_claim_capability": False,
            "future_contract": "bound_atomic_mosquitto_mutation",
        },
        "postactivation": {
            "installed": False,
            "callable": False,
            "host_write_capability": False,
            "docker_mutation_capability": False,
            "authorization_claim_capability": False,
            "future_contract": "read_only_identity_and_anonymous_compatibility_audit",
        },
        "rollback": {
            "installed": False,
            "callable": False,
            "host_write_capability": False,
            "docker_mutation_capability": False,
            "authorization_claim_capability": False,
            "future_contract": "mandatory_complete_snapshot_restore",
        },
    }


def build_production_adapter_skeleton(
    contract_file: str | Path,
    live_mount_gate_file: str | Path,
    *,
    contract_verifier: ContractVerifier = verify_production_executor_contract,
) -> dict[str, object]:
    contract_path = Path(contract_file).expanduser().resolve()
    gate_path = Path(live_mount_gate_file).expanduser().resolve()
    contract = _read_private_json(contract_path, "production executor contract")
    gate = _read_private_json(gate_path, "live mount gate")

    contract_sha = _validate_contract(contract, contract_verifier)
    mount_sha = _validate_live_mount_gate(
        gate,
        contract_sha256=contract_sha,
    )

    skeleton: dict[str, object] = {
        "schema": SCHEMA,
        "contract_sha256": contract_sha,
        "mount_binding_sha256": mount_sha,
        "adapters": _adapter_specs(),
        "execution_interface": {
            "entrypoint_installed": False,
            "execute_subcommand_present": False,
            "enable_flag_present": False,
            "authorization_claim_supported": False,
            "host_path_arguments_supported": False,
            "runner_mutation_commands": [],
        },
        "safety_invariants": {
            "read_only_generation": True,
            "no_host_file_writes": True,
            "no_docker_mutation": True,
            "no_service_restart": True,
            "no_homeassistant_storage_write": True,
            "no_node_credential_write": True,
            "anonymous_compatibility_preserved": True,
            "rollback_remains_mandatory": True,
        },
        "blockers": list(_REQUIRED_BLOCKERS),
        "skeleton_review_complete": True,
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
    skeleton["skeleton_sha256"] = _sha256_document(skeleton)
    return skeleton


def verify_production_adapter_skeleton(
    skeleton: dict[str, object],
) -> dict[str, object]:
    if skeleton.get("schema") != SCHEMA:
        raise BrokerIdentityProductionAdapterSkeletonError(
            "production adapter skeleton schema is invalid"
        )
    digest = _require_sha256(
        skeleton.get("skeleton_sha256"),
        "production adapter skeleton",
    )
    unsigned = dict(skeleton)
    unsigned.pop("skeleton_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityProductionAdapterSkeletonError(
            "production adapter skeleton fingerprint does not match"
        )
    required = {
        "skeleton_review_complete": True,
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
            raise BrokerIdentityProductionAdapterSkeletonError(
                f"production adapter skeleton safety flag failed: {field}"
            )
    adapters = skeleton.get("adapters")
    if not isinstance(adapters, dict) or tuple(adapters) != _ADAPTER_NAMES:
        raise BrokerIdentityProductionAdapterSkeletonError(
            "production adapter skeleton inventory has drifted"
        )
    for name in _ADAPTER_NAMES:
        adapter = adapters.get(name)
        if not isinstance(adapter, dict):
            raise BrokerIdentityProductionAdapterSkeletonError(
                f"production adapter skeleton is missing: {name}"
            )
        for field in (
            "installed",
            "callable",
            "host_write_capability",
            "docker_mutation_capability",
            "authorization_claim_capability",
        ):
            if adapter.get(field) is not False:
                raise BrokerIdentityProductionAdapterSkeletonError(
                    f"production adapter unexpectedly exposes capability: {name}.{field}"
                )
    if skeleton.get("blockers") != list(_REQUIRED_BLOCKERS):
        raise BrokerIdentityProductionAdapterSkeletonError(
            "production adapter skeleton blockers have drifted"
        )
    return {
        "schema": SCHEMA,
        "skeleton_sha256": digest,
        "verified": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def execute_production_adapter_skeleton() -> None:
    raise BrokerIdentityProductionAdapterDisabledError(
        "production mutation, postactivation, and rollback adapters are not installed"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only, non-callable production adapter skeleton from a "
            "verified executor contract and passing live mount gate."
        )
    )
    parser.add_argument("contract_file")
    parser.add_argument("live_mount_gate_file")
    args = parser.parse_args(argv)
    try:
        result = build_production_adapter_skeleton(
            args.contract_file,
            args.live_mount_gate_file,
        )
        verify_production_adapter_skeleton(result)
    except (
        BrokerIdentityProductionAdapterSkeletonError,
        BrokerIdentityProductionExecutorContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker production adapter skeleton failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
