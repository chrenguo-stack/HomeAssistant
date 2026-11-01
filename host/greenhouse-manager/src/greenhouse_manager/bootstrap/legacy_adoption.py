from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap._portable_restore_format import REQUIRED_ROLES
from greenhouse_manager.bootstrap.persistence_migration import DEFAULT_ROLE_LAYOUT

CLASSIFICATION_SCHEMA = "gh.h0h1.t1-hidden-runtime-state-read-only-classification/1"
PLAN_SCHEMA = "gh.h0h1.legacy-system-id-adoption-plan/1"
CLASSIFICATION_DECISION_ID = (
    "D1-H0H1-PR260-EXACT-HEAD-T1-HIDDEN-RUNTIME-STATE-READ-ONLY-"
    "CLASSIFICATION-AUTHORIZATION-20260802-01"
)
ADOPTION_CONTRACT_DECISION_ID = (
    "D1-H0H1-PR260-LEGACY-SYSTEM-ID-ADOPTION-CONTRACT-AND-HOST-ONLY-"
    "MIGRATION-HARNESS-CREATION-20260802-01"
)
CLASSIFIED_SOURCE_PR = 260
CLASSIFIED_BASE_SHA = "ba6255cb3cb4067efd72b23f81f1a799c2c0026e"
CLASSIFIED_SOURCE_HEAD_SHA = "6a7e898cb7df50cd10545ef1795820ab8ac96e98"
CLASSIFIED_ARTIFACT_ID = 8832916787
CLASSIFIED_ARTIFACT_SHA256 = (
    "914d6ce19203096f45603487bf161a7841491701202ead3a917e2bd001c09780"
)
CLASSIFIED_BASELINE_RESULT_SHA256 = (
    "8408e29885fdce1efb0500c0b2a1783b0ea9751fdf156b1c177dd2695cf46d85"
)
CLASSIFIED_BASELINE_SCRIPT_SHA256 = (
    "1bbce3d90288072b39ae88b4f69d4dc650ff93c036890e6ede16a822df178c13"
)
CLASSIFICATION_RESULT_SHA256 = (
    "4e95fd661df371c9d124c17a4a892aca6db41e0fb7e202b4116bf804e425483a"
)
OBSERVED_MANAGER_VERSION = "0.4.64"
TARGET_MANAGER_VERSION = "0.4.98"
SYSTEM_ID_ENVIRONMENT_KEY = "GH_SYSTEM_ID"
SYSTEM_ID_FINGERPRINT_LENGTH = 24
TARGET_CONTAINER_ROOT = "/var/lib/greenhouse-manager"
TARGET_MANAGER_STATE_PATH = "manager/manager-state.sqlite3"

_MUTATION_FLAGS = frozenset(
    {
        "anonymous_closure_executed",
        "backup_created",
        "board_operation",
        "broker_modified",
        "candidate_root_created",
        "container_created",
        "container_modified",
        "container_restarted",
        "docker_cp_executed",
        "file_created_on_t1",
        "file_modified_on_t1",
        "flash_nvs_operation",
        "home_assistant_modified",
        "identity_generated",
        "manager_modified",
        "merge_executed",
        "network_probe_executed",
        "ready_executed",
        "release_tag_deployment",
        "restore_executed",
        "usb_serial_operation",
    }
)


class LegacyAdoptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyAdoptionPlan:
    schema: str
    status: str
    decision_id: str
    classification_result_sha256: str
    classified_binding: dict[str, object]
    source_system_id_fingerprint: str
    observed_manager_version: str
    target_manager_version: str
    adoption_contract: dict[str, object]
    candidate_mount: dict[str, object]
    role_inventory: dict[str, str]
    manager_state_contract: dict[str, object]
    rollback_contract: dict[str, object]
    stages: tuple[dict[str, object], ...]
    blocked_reasons: tuple[str, ...]
    gates: dict[str, bool]
    operation_flags: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def classification_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def system_id_fingerprint(system_id: str) -> str:
    return hashlib.sha256(system_id.encode("utf-8")).hexdigest()[:SYSTEM_ID_FINGERPRINT_LENGTH]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LegacyAdoptionError(f"{label} must be an object")
    return value


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise LegacyAdoptionError(f"{label} does not match the classified binding")


def _validate_binding(result: Mapping[str, Any]) -> dict[str, object]:
    binding = _mapping(result.get("binding"), "classification binding")
    expected: dict[str, object] = {
        "source_pr": CLASSIFIED_SOURCE_PR,
        "base_sha": CLASSIFIED_BASE_SHA,
        "source_head_sha": CLASSIFIED_SOURCE_HEAD_SHA,
        "artifact_id": CLASSIFIED_ARTIFACT_ID,
        "artifact_sha256": CLASSIFIED_ARTIFACT_SHA256,
        "baseline_result_sha256": CLASSIFIED_BASELINE_RESULT_SHA256,
        "baseline_script_sha256": CLASSIFIED_BASELINE_SCRIPT_SHA256,
    }
    for key, expected_value in expected.items():
        _require_equal(binding.get(key), expected_value, f"classification binding {key}")
    return expected


def _validate_read_only_flags(result: Mapping[str, Any]) -> None:
    flags = _mapping(result.get("operation_flags"), "classification operation flags")
    if flags.get("read_only") is not True:
        raise LegacyAdoptionError("classification result is not read-only")
    active = sorted(name for name in _MUTATION_FLAGS if flags.get(name) is not False)
    if active:
        raise LegacyAdoptionError(
            "classification contains non-false mutation flags: " + ",".join(active)
        )


def _validate_state_scan(evidence: Mapping[str, Any]) -> None:
    state_scan = _mapping(evidence.get("container_state_scan"), "container state scan")
    expected = {
        "available": True,
        "scan_complete": True,
        "candidate_count": 0,
        "identity_document_count": 0,
        "recognized_manager_row_count": 0,
        "scanned_file_count": 0,
        "errors": [],
        "open_state_fds": [],
    }
    for key, expected_value in expected.items():
        _require_equal(state_scan.get(key), expected_value, f"container state scan {key}")

    writable = _mapping(evidence.get("container_writable_layer"), "container writable layer")
    if writable.get("available") is not True or writable.get("truncated") is not False:
        raise LegacyAdoptionError("container writable-layer evidence is incomplete")
    if writable.get("state_related_entries") != []:
        raise LegacyAdoptionError("state-related writable-layer entries were observed")


def _validate_manager(evidence: Mapping[str, Any]) -> str:
    manager = _mapping(evidence.get("manager_container"), "manager container")
    if manager.get("running") is not True or manager.get("state") != "running":
        raise LegacyAdoptionError("manager container is not running")
    _require_equal(manager.get("version"), OBSERVED_MANAGER_VERSION, "manager version")
    mounts = manager.get("mounts")
    if not isinstance(mounts, list):
        raise LegacyAdoptionError("manager mount inventory is invalid")
    if any(
        isinstance(mount, Mapping) and mount.get("destination") == TARGET_CONTAINER_ROOT
        for mount in mounts
    ):
        raise LegacyAdoptionError("manager persistence mount appeared after classification")

    environment = _mapping(manager.get("environment"), "manager environment")
    if environment.get("secret_bearing_value_count") != 0:
        raise LegacyAdoptionError("classification contains secret-bearing environment values")
    state_keys = environment.get("state_related_keys")
    if not isinstance(state_keys, list) or SYSTEM_ID_ENVIRONMENT_KEY not in state_keys:
        raise LegacyAdoptionError("legacy SYSTEM_ID environment evidence is missing")
    values = _mapping(environment.get("non_secret_state_values"), "non-secret state values")
    system_id = _mapping(values.get(SYSTEM_ID_ENVIRONMENT_KEY), "legacy SYSTEM_ID evidence")
    if system_id.get("present") is not True:
        raise LegacyAdoptionError("legacy SYSTEM_ID is not present")
    fingerprint = system_id.get("fingerprint")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != SYSTEM_ID_FINGERPRINT_LENGTH
        or any(character not in "0123456789abcdef" for character in fingerprint)
    ):
        raise LegacyAdoptionError("legacy SYSTEM_ID fingerprint is invalid")
    return fingerprint


def _validate_log_continuity(evidence: Mapping[str, Any]) -> None:
    logs = _mapping(evidence.get("log_signals"), "manager log signals")
    counts = _mapping(logs.get("signal_counts"), "manager log signal counts")
    accepted = counts.get("accepted_telemetry")
    if not isinstance(accepted, int) or isinstance(accepted, bool) or accepted < 1:
        raise LegacyAdoptionError("legacy telemetry continuity was not observed")


def _validate_classification(result: Mapping[str, Any]) -> tuple[dict[str, object], str]:
    _require_equal(result.get("schema"), CLASSIFICATION_SCHEMA, "classification schema")
    _require_equal(result.get("status"), "PASS", "classification status")
    _require_equal(result.get("decision_id"), CLASSIFICATION_DECISION_ID, "classification decision")
    _require_equal(
        result.get("classification"),
        "LEGACY_RUNTIME_OR_CONFIGURATION_STATE_PRESENT",
        "classification",
    )
    if result.get("runtime_hidden_state_classified") is not True:
        raise LegacyAdoptionError("hidden runtime state was not classified")
    if result.get("legacy_import_or_adoption_required") is not True:
        raise LegacyAdoptionError("legacy adoption requirement is missing")
    for key in (
        "new_system_initialization_permitted_by_this_decision",
        "candidate_root_preparation_permitted_by_this_decision",
        "real_backup_permitted_by_this_decision",
        "restore_permitted_by_this_decision",
        "anonymous_closure_permitted_by_this_decision",
        "deployment_permitted_by_this_decision",
    ):
        if result.get(key) is not False:
            raise LegacyAdoptionError(f"classification unexpectedly permits {key}")
    if result.get("baseline_drift") != []:
        raise LegacyAdoptionError("classification baseline drift is not empty")
    blocked = result.get("blocked_reasons")
    if not isinstance(blocked, list) or "EXPLICIT_LEGACY_ADOPTION_OR_IMPORT_REQUIRED" not in blocked:
        raise LegacyAdoptionError("explicit legacy adoption requirement is missing")

    binding = _validate_binding(result)
    _validate_read_only_flags(result)
    evidence = _mapping(result.get("evidence"), "classification evidence")
    _validate_state_scan(evidence)
    fingerprint = _validate_manager(evidence)
    _validate_log_continuity(evidence)
    return binding, fingerprint


def _stages() -> tuple[dict[str, object], ...]:
    return (
        {
            "id": "A0_BINDING_REFRESH",
            "kind": "read_only",
            "purpose": "revalidate PR, source, Artifact, classification result, and T1 identity",
            "future_authorization_required": True,
        },
        {
            "id": "A1_PRIVATE_SYSTEM_ID_CAPTURE",
            "kind": "read_only_private",
            "purpose": "read GH_SYSTEM_ID privately and prove its fingerprint without publishing it",
            "future_authorization_required": True,
        },
        {
            "id": "A2_PRIVATE_CANDIDATE_ROOT",
            "kind": "candidate_write",
            "purpose": "create an absent 0700 candidate root with 0600 members",
            "future_authorization_required": True,
        },
        {
            "id": "A3_ADOPT_EXISTING_SYSTEM_ID",
            "kind": "candidate_write",
            "purpose": (
                "preserve the existing SYSTEM_ID while creating formal Manager identity, root key, "
                "and CA only inside the candidate"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "A4_EMPTY_FORMAL_MANAGER_STATE",
            "kind": "candidate_write",
            "purpose": (
                "materialize current registration, credential, and retirement schemas with zero "
                "business rows and explicit provenance"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "A5_BROKER_SNAPSHOT_ASSEMBLY",
            "kind": "candidate_copy",
            "purpose": "copy exact Broker Dynamic Security and persistence snapshots",
            "future_authorization_required": True,
        },
        {
            "id": "A6_PORTABLE_BACKUP_VALIDATION",
            "kind": "candidate_backup",
            "purpose": "verify all ten roles and an encrypted portable backup without live apply",
            "future_authorization_required": True,
        },
        {
            "id": "A7_SHADOW_AND_COMMIT_OR_ROLLBACK",
            "kind": "service_change",
            "purpose": "shadow-validate and later commit or restore the exact prior image and mounts",
            "future_authorization_required": True,
        },
    )


def build_legacy_adoption_plan(
    classification_result: Mapping[str, Any],
    *,
    source_sha256: str | None = None,
    require_exact_classified_file: bool = False,
) -> LegacyAdoptionPlan:
    binding, fingerprint = _validate_classification(classification_result)
    digest = source_sha256 or classification_digest(classification_result)
    if require_exact_classified_file and digest != CLASSIFICATION_RESULT_SHA256:
        raise LegacyAdoptionError("classification file SHA-256 does not match the accepted result")
    if set(DEFAULT_ROLE_LAYOUT) != REQUIRED_ROLES:
        raise LegacyAdoptionError("candidate role inventory is incomplete")

    return LegacyAdoptionPlan(
        schema=PLAN_SCHEMA,
        status="CONTRACT_COMPLETE_EXECUTION_BLOCKED",
        decision_id=ADOPTION_CONTRACT_DECISION_ID,
        classification_result_sha256=digest,
        classified_binding=binding,
        source_system_id_fingerprint=fingerprint,
        observed_manager_version=OBSERVED_MANAGER_VERSION,
        target_manager_version=TARGET_MANAGER_VERSION,
        adoption_contract={
            "source": f"manager_environment:{SYSTEM_ID_ENVIRONMENT_KEY}",
            "raw_system_id_must_remain_private": True,
            "preserve_existing_system_id": True,
            "generate_new_system_id": False,
            "generate_new_manager_id_in_candidate": True,
            "generate_new_system_root_key_in_candidate": True,
            "generate_new_system_ca_in_candidate": True,
            "structured_legacy_manager_state_imported": False,
            "anonymous_nodes_reconstructed": False,
            "existing_anonymous_continuity_must_be_preserved": True,
            "formal_node_enrollment_remains_separate": True,
        },
        candidate_mount={
            "container_path": TARGET_CONTAINER_ROOT,
            "type": "private_bind_mount",
            "host_path": "OPERATOR_BOUND_PRIVATE_PATH_REQUIRED",
            "root_mode": "0700",
            "member_mode": "0600",
            "must_be_absent_before_creation": True,
            "must_not_be_symlink": True,
            "must_not_overlay_live_manager_before_shadow_gate": True,
        },
        role_inventory=dict(sorted(DEFAULT_ROLE_LAYOUT.items())),
        manager_state_contract={
            "path": TARGET_MANAGER_STATE_PATH,
            "schema_source": "greenhouse-manager-0.4.98-runtime-stores",
            "business_rows_initial": 0,
            "legacy_rows_reconstructed_from_logs": False,
            "registration_rows_reconstructed": False,
            "credential_rows_reconstructed": False,
            "retirement_rows_reconstructed": False,
            "provenance_record_required": True,
            "legacy_unenrolled_nodes_remain_anonymous_until_explicit_enrollment": True,
        },
        rollback_contract={
            "prior_manager_version": OBSERVED_MANAGER_VERSION,
            "prior_image_tag_and_id_binding_required": True,
            "prior_mount_inventory_binding_required": True,
            "prior_environment_key_inventory_binding_required": True,
            "prior_system_id_fingerprint": fingerprint,
            "prior_anonymous_mode_evidence_required": True,
            "prior_broker_state_digest_binding_required": True,
            "candidate_root_preserved_for_forensics": True,
            "automatic_candidate_deletion": False,
            "rollback_authorization_required": True,
        },
        stages=_stages(),
        blocked_reasons=(
            "RAW_LEGACY_SYSTEM_ID_VALUE_NOT_PRIVATELY_BOUND",
            "PRIVATE_CANDIDATE_ROOT_NOT_PREPARED",
            "FORMAL_IDENTITY_NOT_MATERIALIZED",
            "EMPTY_FORMAL_MANAGER_STATE_NOT_MATERIALIZED",
            "BROKER_SNAPSHOT_NOT_MATERIALIZED",
            "PORTABLE_BACKUP_NOT_VERIFIED",
            "SERVICE_CHANGE_NOT_AUTHORIZED",
            "RESTORE_NOT_AUTHORIZED",
            "ANONYMOUS_CLOSURE_NOT_AUTHORIZED",
            "DEPLOYMENT_NOT_AUTHORIZED",
        ),
        gates={
            "classification_binding_valid": True,
            "runtime_hidden_state_classified": True,
            "legacy_configuration_adoption_required": True,
            "new_system_initialization_allowed": False,
            "raw_legacy_system_id_loaded": False,
            "candidate_root_prepared": False,
            "formal_identity_materialized": False,
            "empty_formal_manager_state_materialized": False,
            "broker_snapshot_materialized": False,
            "portable_backup_verified": False,
            "execution_authorized": False,
            "ready_for_restore": False,
            "ready_for_anonymous_closure": False,
            "ready_for_deployment": False,
        },
        operation_flags={
            "read_only_plan": True,
            "production_services_modified": False,
            "candidate_files_created": False,
            "identity_generated": False,
            "manager_state_created": False,
            "broker_snapshot_created": False,
            "backup_created": False,
            "restore_executed": False,
            "anonymous_closure_executed": False,
            "container_modified": False,
            "container_restarted": False,
            "network_operation": False,
            "board_operation": False,
            "ready_executed": False,
            "merge_executed": False,
            "release_tag_deployment": False,
            "sensitive_values_included": False,
        },
    )


def load_classification_result(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise LegacyAdoptionError("classification result must be a regular file")
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != CLASSIFICATION_RESULT_SHA256:
        raise LegacyAdoptionError("classification file SHA-256 does not match the accepted result")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LegacyAdoptionError("classification result JSON is invalid") from error
    if not isinstance(value, dict):
        raise LegacyAdoptionError("classification result JSON must be an object")
    return value, digest
