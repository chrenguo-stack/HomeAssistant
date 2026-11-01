from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA = "gh.m2.node-firmware-mqtt-capability-gate-plan/1"
SOURCE_EVIDENCE_SCHEMA = "gh.m2.t1-node-synchronized-reconnect-evidence/1"
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")


class NodeFirmwareMqttCapabilityGateError(ValueError):
    """Raised when the synchronized node evidence is not sufficient for design."""


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    system_id: str
    node_id: str
    username: str
    client_id: str
    role_name: str
    generation: int


@dataclass(frozen=True, slots=True)
class FirmwareCapabilityRequirement:
    requirement_id: str
    description: str
    isolated_test_required: bool
    real_board_test_required: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NodeFirmwareMqttCapabilityGateError(message)


def _require_mapping(value: object, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return value


def _require_true(document: Mapping[str, Any], key: str) -> None:
    _require(document.get(key) is True, f"{key} must be true")


def _require_false(document: Mapping[str, Any], key: str) -> None:
    _require(document.get(key) is False, f"{key} must be false")


def _validate_id(value: str, name: str) -> str:
    _require(bool(_ID.fullmatch(value)), f"{name} is invalid")
    return value


def build_candidate_identity(
    *,
    system_id: str,
    node_id: str,
    generation: int = 1,
) -> CandidateIdentity:
    system_id = _validate_id(system_id, "system_id")
    node_id = _validate_id(node_id, "node_id")
    _require(generation >= 1, "generation must be positive")
    return CandidateIdentity(
        system_id=system_id,
        node_id=node_id,
        username=f"ghn_{node_id}",
        client_id=node_id,
        role_name=f"gh-node-{system_id}-{node_id}",
        generation=generation,
    )


def firmware_capability_requirements() -> tuple[FirmwareCapabilityRequirement, ...]:
    return (
        FirmwareCapabilityRequirement(
            "explicit_authenticated_identity",
            "Candidate firmware sets the exact username and fixed client ID without emitting the password.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "private_candidate_and_fallback_slots",
            "Candidate and anonymous fallback connection profiles are stored "
            "separately from public configuration.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "bounded_authenticated_failure_fallback",
            "Repeated candidate authentication failures trigger bounded automatic fallback to anonymous.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "candidate_preserved_after_fallback",
            "Fallback does not erase the candidate profile and only exposes generation and fingerprints.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "local_operation_independent",
            "Sensor collection, LCD, RS485, power protection, and local alarms "
            "continue during MQTT failures.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "secret_redaction",
            "Passwords are absent from serial logs, API logs, diagnostics, crash "
            "output, and public artifacts.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "power_and_network_fault_recovery",
            "Power loss, Wi-Fi loss, Broker loss, and reboot cannot strand local "
            "operation or erase fallback.",
            True,
            True,
        ),
        FirmwareCapabilityRequirement(
            "retired_generation_erasure",
            "A retired credential generation can be securely erased after a committed migration.",
            True,
            True,
        ),
    )


def build_node_firmware_mqtt_capability_gate_plan(
    evidence: Mapping[str, Any],
    *,
    repository_sha: str | None = None,
    manager_source_version: str | None = None,
) -> dict[str, object]:
    _require(
        evidence.get("schema") == SOURCE_EVIDENCE_SCHEMA,
        "evidence schema is not synchronized V96",
    )
    _require(
        evidence.get("status") == "node_synchronized_reconnect_evidence_succeeded",
        "evidence did not succeed",
    )
    for key in (
        "read_only",
        "evidence_verified",
        "preserve_anonymous",
        "anonymous_enabled",
        "protected_services_stable",
        "broker_config_and_state_stable",
    ):
        _require_true(evidence, key)
    for key in (
        "anonymous_closure_enabled",
        "homeassistant_storage_read",
        "homeassistant_storage_written",
        "node_credentials_delivered",
        "production_execution_invoked",
        "production_manager_upgraded",
        "current_services_modified",
        "ready_for_live_apply",
        "ready_for_anonymous_closure",
    ):
        _require_false(evidence, key)

    system_id = evidence.get("system_id")
    node_id = evidence.get("node_id")
    generation = evidence.get("generation")
    _require(isinstance(system_id, str), "system_id is missing")
    _require(isinstance(node_id, str), "node_id is missing")
    _require(isinstance(generation, int), "generation is missing")
    identity = build_candidate_identity(
        system_id=system_id, node_id=node_id, generation=generation
    )

    broker = _require_mapping(evidence.get("broker"), "broker")
    _require_true(broker, "anonymous_enabled")
    _require_true(broker, "dynamic_security_configured")
    _require_true(broker, "state_private")
    _require_true(broker, "state_runtime_owner_bound")
    _require_true(broker, "state_single_hardlink")
    config_sha = broker.get("config_sha256")
    state_sha = broker.get("state_sha256")
    _require(
        isinstance(config_sha, str) and bool(_SHA256.fullmatch(config_sha)),
        "Broker config SHA is invalid",
    )
    _require(
        isinstance(state_sha, str) and bool(_SHA256.fullmatch(state_sha)),
        "Broker state SHA is invalid",
    )

    node_identity = _require_mapping(evidence.get("node_identity"), "node_identity")
    for key in (
        "identity_exact",
        "role_exact",
        "acl_exact",
        "default_access_exact",
        "identity_preconfigured",
        "credential_material_present",
    ):
        _require_true(node_identity, key)
    _require(node_identity.get("acl_count") == 10, "node ACL count is not 10")
    _require_false(node_identity, "identity_disabled")

    continuity = _require_mapping(evidence.get("continuity"), "continuity")
    for key in (
        "canonical_retained_continuous",
        "availability_retained_continuous",
        "discovery_retained_continuous",
        "existing_entity_identity_continuous",
        "fresh_ingress_observed",
        "fresh_ingress_after_synchronized_reconnect",
    ):
        _require_true(continuity, key)
    component_count = continuity.get("component_count")
    _require(
        isinstance(component_count, int) and component_count > 0,
        "component count is invalid",
    )

    runtime = _require_mapping(evidence.get("node_runtime"), "node_runtime")
    for key in (
        "observer_connection_log_visible",
        "synchronized_reconnect_observed",
        "runtime_connection_anonymous",
        "legacy_runtime_client_id_differs_from_target",
    ):
        _require_true(runtime, key)
    for key in (
        "authenticated_node_connection_observed",
        "observed_client_id_matches_target",
        "exact_client_id_connection_observed",
    ):
        _require_false(runtime, key)
    observed_fingerprint = runtime.get("observed_client_id_fingerprint")
    _require(
        isinstance(observed_fingerprint, str)
        and bool(_FINGERPRINT.fullmatch(observed_fingerprint)),
        "observed client ID fingerprint is invalid",
    )

    evidence_repository_sha = evidence.get("repository_sha")
    _require(
        isinstance(evidence_repository_sha, str)
        and re.fullmatch(r"[0-9a-f]{40}", evidence_repository_sha) is not None,
        "evidence repository SHA is invalid",
    )
    if repository_sha is not None:
        _require(
            repository_sha == evidence_repository_sha,
            "repository SHA binding has drifted",
        )
    evidence_manager_version = evidence.get("manager_source_version")
    _require(
        isinstance(evidence_manager_version, str) and evidence_manager_version,
        "manager source version is missing",
    )
    if manager_source_version is not None:
        _require(
            manager_source_version == evidence_manager_version,
            "manager source version binding has drifted",
        )

    requirements = firmware_capability_requirements()
    return {
        "schema": SCHEMA,
        "status": "node_firmware_mqtt_capability_gate_plan_created",
        "source_evidence_schema": SOURCE_EVIDENCE_SCHEMA,
        "source_evidence_status": evidence.get("status"),
        "source_repository_sha": evidence_repository_sha,
        "source_manager_version": evidence_manager_version,
        "candidate_identity": asdict(identity),
        "legacy_runtime": {
            "anonymous": True,
            "client_id_differs_from_target": True,
            "observed_client_id_fingerprint": observed_fingerprint,
            "raw_client_id_included": False,
        },
        "continuity_baseline": {
            "canonical_retained_continuous": True,
            "availability_retained_continuous": True,
            "discovery_retained_continuous": True,
            "fresh_ingress_observed": True,
            "component_count": component_count,
        },
        "broker_baseline": {
            "config_sha256": config_sha,
            "state_sha256": state_sha,
            "anonymous_enabled": True,
        },
        "requirements": [asdict(item) for item in requirements],
        "requirement_count": len(requirements),
        "candidate_firmware_must_replace_legacy_client_id": True,
        "candidate_firmware_must_preserve_anonymous_fallback": True,
        "node_password_generation_permitted": False,
        "node_credentials_delivered": False,
        "production_execution_invoked": False,
        "production_manager_upgraded": False,
        "homeassistant_storage_read": False,
        "anonymous_closure_enabled": False,
        "ready_for_candidate_firmware_design": True,
        "ready_for_candidate_firmware_build": False,
        "ready_for_isolated_capability_test": False,
        "ready_for_real_board_capability_test": False,
        "ready_for_node_credential_generation": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "activation_blockers": [
            "candidate_firmware_implementation_missing",
            "candidate_firmware_isolated_validation_pending",
            "candidate_firmware_real_board_validation_pending",
            "node_private_credential_delivery_path_unverified",
            "node_anonymous_fallback_rollback_unverified",
            "fresh_node_migration_authorization_not_created",
            "authenticated_node_observation_window_pending",
            "anonymous_closure_not_authorized",
        ],
        "secret_values_included": False,
        "source_paths_included": False,
    }


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the node firmware MQTT capability gate plan"
    )
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--repository-sha")
    parser.add_argument("--manager-source-version")
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if not isinstance(evidence, Mapping):
            raise NodeFirmwareMqttCapabilityGateError("evidence root must be an object")
        report = build_node_firmware_mqtt_capability_gate_plan(
            evidence,
            repository_sha=args.repository_sha,
            manager_source_version=args.manager_source_version,
        )
    except (
        NodeFirmwareMqttCapabilityGateError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        print(f"Node firmware MQTT capability gate failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
