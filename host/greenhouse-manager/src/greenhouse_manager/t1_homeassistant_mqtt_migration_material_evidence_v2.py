from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .t1_homeassistant_mqtt_migration_material_evidence import (
    CandidateMaterial,
    CommandRunner,
    HomeAssistantMigrationMaterialEvidenceError,
    SubprocessRunner,
    _broker_config_and_state,
    _candidate_files,
    _canonical_json,
    _load_materials,
    _snapshot,
    _target_topology,
    _temporary_client,
    _validate_credentials,
    _validate_state_binding,
)

SCHEMA = "gh.m2.t1-homeassistant-mqtt-migration-material-evidence/2"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _credential_binding_fingerprint(material: CandidateMaterial) -> str:
    """Credential identity only; Broker target is verified independently."""
    value = "\0".join(
        (
            material.username,
            material.password,
            material.client_id,
            str(material.port),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _deduplicate_materials(
    materials: Sequence[CandidateMaterial],
) -> list[CandidateMaterial]:
    unique: dict[str, CandidateMaterial] = {}
    for material in materials:
        unique.setdefault(_credential_binding_fingerprint(material), material)
    return list(unique.values())


def _correct_identity_probe(
    runner: CommandRunner,
    material: CandidateMaterial,
    *,
    expected_retained_topic: str,
    node_id: str,
) -> bool:
    code, output = _temporary_client(
        runner,
        material,
        client_id=material.client_id,
        topic=expected_retained_topic,
    )
    if code != 0 or not output.strip():
        return False
    try:
        retained = json.loads(output)
    except json.JSONDecodeError:
        return False
    return isinstance(retained, Mapping) and retained.get("node_id") == node_id


def _select_live_material(
    runner: CommandRunner,
    materials: Sequence[CandidateMaterial],
    *,
    expected_username: str,
    expected_client_id: str,
    expected_retained_topic: str,
    node_id: str,
) -> tuple[CandidateMaterial, int, int]:
    unique = _deduplicate_materials(materials)
    exact = [
        material
        for material in unique
        if material.username == expected_username
        and material.client_id == expected_client_id
        and material.port == 1883
    ]
    if not exact:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "no exact Home Assistant credential binding candidate was found"
        )
    authenticated = [
        material
        for material in exact
        if _correct_identity_probe(
            runner,
            material,
            expected_retained_topic=expected_retained_topic,
            node_id=node_id,
        )
    ]
    if len(authenticated) != 1:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "exactly one live-authenticated Home Assistant credential binding is required"
        )
    return authenticated[0], len(unique), len(exact)


def build_homeassistant_mqtt_migration_material_evidence_v2(
    *,
    system_id: str,
    node_id: str,
    expected_retained_topic: str,
    search_roots: Sequence[str | Path] = (
        "/tmp",
        "/opt/HomeAssistant",
        "/opt/greenhouse-secrets",
    ),
    runner: CommandRunner | None = None,
    repository_sha: str | None = None,
    manager_source_version: str | None = None,
) -> dict[str, object]:
    expected_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    if (
        not system_id
        or not node_id
        or expected_retained_topic != expected_topic
        or not search_roots
    ):
        raise ValueError("Home Assistant migration material evidence inputs are invalid")
    if repository_sha is not None and _GIT_SHA.fullmatch(repository_sha) is None:
        raise ValueError(
            "repository SHA must be a 40-character lowercase Git SHA"
        )

    command_runner = runner or SubprocessRunner()
    before_runtime = _snapshot(command_runner)
    broker, state, before_config_sha, before_state_sha = _broker_config_and_state(
        command_runner
    )
    state_binding = _validate_state_binding(state, system_id=system_id)
    paths = _candidate_files(tuple(Path(item) for item in search_roots))
    materials, valid_file_count = _load_materials(paths)
    expected_username = f"ghs_{system_id}_homeassistant"
    expected_client_id = f"gh-homeassistant-{system_id}"
    selected, unique_count, exact_count = _select_live_material(
        command_runner,
        materials,
        expected_username=expected_username,
        expected_client_id=expected_client_id,
        expected_retained_topic=expected_retained_topic,
        node_id=node_id,
    )
    credentials = _validate_credentials(
        command_runner,
        selected,
        expected_username=expected_username,
        expected_client_id=expected_client_id,
        expected_retained_topic=expected_retained_topic,
        node_id=node_id,
    )
    credentials["credential_binding_fingerprint"] = (
        _credential_binding_fingerprint(selected)
    )
    topology = _target_topology(command_runner, port=selected.port)

    after_runtime = _snapshot(command_runner)
    _broker_after, _state_after, after_config_sha, after_state_sha = (
        _broker_config_and_state(command_runner)
    )
    if before_runtime != after_runtime:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "a protected service changed during material evidence collection"
        )
    if before_config_sha != after_config_sha or before_state_sha != after_state_sha:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Broker configuration or Dynamic Security state changed during evidence collection"
        )

    blockers = [
        "explicit_operator_decision_required",
        "homeassistant_official_mqtt_ui_config_flow_pending",
        "homeassistant_postchange_runtime_verification_pending",
        "real_node_credential_delivery_unverified",
        "authenticated_observation_window_pending",
        "anonymous_closure_not_authorized",
    ]
    report: dict[str, object] = {
        "schema": SCHEMA,
        "status": "homeassistant_mqtt_migration_material_evidence_verified",
        "read_only": True,
        "material_evidence_verified": True,
        "broker": broker,
        "state_binding": state_binding,
        "material": {
            "private_candidate_file_count": len(paths),
            "valid_candidate_file_count": valid_file_count,
            "unique_credential_binding_count": unique_count,
            "exact_candidate_binding_count": exact_count,
            "live_authenticated_binding_count": 1,
            "selected_schema": selected.schema,
            "selected_binding_fingerprint": _credential_binding_fingerprint(
                selected
            ),
            "historical_or_duplicate_material_tolerated": True,
            "broker_target_excluded_from_credential_deduplication": True,
            "secret_values_included": False,
            "source_paths_included": False,
        },
        "credential_probe": credentials,
        "target_topology": topology,
        "protected_services_stable": True,
        "broker_config_and_state_stable": True,
        "homeassistant_identity_provisioned": True,
        "homeassistant_identity_runtime_verified": False,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "activation_blockers": blockers,
        "operator_action_required": True,
        "operator_action_authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "apply_enabled": False,
        "execution_enabled": False,
        "current_services_modified": False,
        "ready_for_homeassistant_official_reconfigure_handoff": True,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "secret_values_included": False,
        "source_paths_included": False,
        "path_values_redacted": True,
        "container_ids_included": False,
        "image_ids_included": False,
    }
    serialized = _canonical_json(report)
    forbidden = (
        selected.username,
        selected.password,
        selected.client_id,
        selected.broker or "",
    )
    if any(value and value in serialized for value in forbidden):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "sanitized report contains credential or target material"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Select and verify the one live Home Assistant MQTT credential "
            "binding from private current or historical migration material."
        )
    )
    parser.add_argument("--system-id", default="greenhouse")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--search-root", action="append", default=None)
    parser.add_argument("--repository-sha")
    parser.add_argument("--manager-source-version")
    args = parser.parse_args(argv)
    roots = tuple(
        args.search_root
        or ("/tmp", "/opt/HomeAssistant", "/opt/greenhouse-secrets")
    )
    try:
        report = build_homeassistant_mqtt_migration_material_evidence_v2(
            system_id=args.system_id,
            node_id=args.node_id,
            expected_retained_topic=args.expected_retained_topic,
            search_roots=roots,
            repository_sha=args.repository_sha,
            manager_source_version=args.manager_source_version,
        )
    except (
        HomeAssistantMigrationMaterialEvidenceError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 Home Assistant MQTT migration material evidence failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(_canonical_json(report))
    return 0 if report["material_evidence_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
