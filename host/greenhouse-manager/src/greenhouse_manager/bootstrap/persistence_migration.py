from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap._portable_restore_format import (
    REQUIRED_ROLES,
    ROLE_BROKER_DYNAMIC_SECURITY,
    ROLE_BROKER_PERSISTENCE,
    ROLE_MANAGER_CREDENTIAL_STATE,
    ROLE_MANAGER_IDENTITY,
    ROLE_MANAGER_REGISTRATION_STATE,
    ROLE_MANAGER_RETIREMENT_OUTBOX,
    ROLE_SYSTEM_CA_CERTIFICATE,
    ROLE_SYSTEM_CA_PRIVATE_KEY,
    ROLE_SYSTEM_IDENTITY,
    ROLE_SYSTEM_ROOT_KEY,
)
from greenhouse_manager.bootstrap.system_init import (
    MANAGER_IDENTITY_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
)

BASELINE_SCHEMA = "gh.h0h1.t1-read-only-baseline-audit/1"
PLAN_SCHEMA = "gh.h0h1.persistence-migration-plan/1"
AUDIT_DECISION_ID = (
    "D1-H0H1-PR260-EXACT-HEAD-T1-READ-ONLY-BASELINE-AUDIT-"
    "AUTHORIZATION-20260802-01"
)
REMEDIATION_DECISION_ID = (
    "D1-H0H1-PR260-T1-BASELINE-GAP-REMEDIATION-DESIGN-AND-HOST-ONLY-"
    "PERSISTENCE-MIGRATION-CONTRACT-CREATION-20260802-01"
)
AUDITED_SOURCE_PR = 260
AUDITED_BASE_SHA = "ba6255cb3cb4067efd72b23f81f1a799c2c0026e"
AUDITED_SOURCE_HEAD_SHA = "8efc47cabc01e274b62a0cec83448fbe4a56a56b"
AUDITED_ARTIFACT_ID = 8832112931
AUDITED_ARTIFACT_SHA256 = (
    "407ae7e08d82672df647c8ea25eb8cbe1af25e6d796c0a7d85eb1bded637daf4"
)
AUDITED_BASELINE_SHA256 = (
    "8408e29885fdce1efb0500c0b2a1783b0ea9751fdf156b1c177dd2695cf46d85"
)
TARGET_MANAGER_VERSION = "0.4.98"
TARGET_CONTAINER_ROOT = "/var/lib/greenhouse-manager"
TARGET_MANAGER_STATE_PATH = "manager/manager-state.sqlite3"

DEFAULT_ROLE_LAYOUT: dict[str, str] = {
    ROLE_SYSTEM_IDENTITY: SYSTEM_IDENTITY_NAME,
    ROLE_SYSTEM_ROOT_KEY: SYSTEM_ROOT_KEY_NAME,
    ROLE_SYSTEM_CA_CERTIFICATE: SYSTEM_CA_CERTIFICATE_NAME,
    ROLE_SYSTEM_CA_PRIVATE_KEY: SYSTEM_CA_PRIVATE_KEY_NAME,
    ROLE_MANAGER_IDENTITY: MANAGER_IDENTITY_NAME,
    ROLE_MANAGER_REGISTRATION_STATE: TARGET_MANAGER_STATE_PATH,
    ROLE_MANAGER_CREDENTIAL_STATE: TARGET_MANAGER_STATE_PATH,
    ROLE_MANAGER_RETIREMENT_OUTBOX: TARGET_MANAGER_STATE_PATH,
    ROLE_BROKER_DYNAMIC_SECURITY: "broker/dynamic-security.json",
    ROLE_BROKER_PERSISTENCE: "broker/mosquitto.db",
}

_MUTATION_FLAGS = frozenset(
    {
        "anonymous_closure_executed",
        "backup_created",
        "broker_modified",
        "container_created",
        "container_modified",
        "container_restarted",
        "docker_cp_executed",
        "file_created",
        "file_modified",
        "flash_nvs_operation",
        "home_assistant_modified",
        "manager_modified",
        "merge_executed",
        "network_probe_executed",
        "ready_executed",
        "release_tag_deployment",
        "restore_executed",
        "usb_serial_operation",
    }
)


class PersistenceMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistenceMigrationPlan:
    schema: str
    status: str
    remediation_decision_id: str
    baseline_sha256: str
    audited_binding: dict[str, object]
    observed_manager_version: str
    target_manager_version: str
    classification: str
    hidden_runtime_state_classification: str
    target_mount: dict[str, object]
    role_inventory: dict[str, str]
    broker_source_contract: dict[str, str]
    stages: tuple[dict[str, object], ...]
    rollback_contract: dict[str, object]
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


def baseline_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PersistenceMigrationError(f"{label} must be an object")
    return value


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise PersistenceMigrationError(f"{label} does not match the audited binding")


def _validate_binding(baseline: Mapping[str, Any]) -> dict[str, object]:
    _require_equal(baseline.get("schema"), BASELINE_SCHEMA, "baseline schema")
    _require_equal(baseline.get("status"), "PASS", "baseline status")
    _require_equal(baseline.get("decision_id"), AUDIT_DECISION_ID, "audit decision")
    binding = _mapping(baseline.get("binding"), "baseline binding")
    expected: dict[str, object] = {
        "source_pr": AUDITED_SOURCE_PR,
        "base_sha": AUDITED_BASE_SHA,
        "source_head_sha": AUDITED_SOURCE_HEAD_SHA,
        "artifact_id": AUDITED_ARTIFACT_ID,
        "artifact_sha256": AUDITED_ARTIFACT_SHA256,
    }
    for key, expected_value in expected.items():
        _require_equal(binding.get(key), expected_value, f"baseline binding {key}")
    return expected


def _validate_read_only_flags(baseline: Mapping[str, Any]) -> None:
    flags = _mapping(baseline.get("operation_flags"), "operation flags")
    if flags.get("read_only") is not True:
        raise PersistenceMigrationError("baseline is not marked read-only")
    active = sorted(name for name in _MUTATION_FLAGS if flags.get(name) is not False)
    if active:
        raise PersistenceMigrationError(
            "baseline contains non-false mutation flags: " + ",".join(active)
        )


def _manager_version(baseline: Mapping[str, Any]) -> str:
    containers = _mapping(baseline.get("containers"), "containers")
    versions = _mapping(containers.get("versions"), "container versions")
    version = versions.get("greenhouse-manager")
    if not isinstance(version, str) or not version:
        raise PersistenceMigrationError("manager version is unavailable")
    targets = _mapping(containers.get("targets"), "target containers")
    for name in ("greenhouse-manager", "homeassistant", "mosquitto"):
        target = _mapping(targets.get(name), f"target container {name}")
        if target.get("exists") is not True or target.get("running") is not True:
            raise PersistenceMigrationError(f"target container is not running: {name}")
    return version


def _validate_gap(baseline: Mapping[str, Any]) -> None:
    readiness = _mapping(baseline.get("readiness"), "readiness")
    if readiness.get("manager_data_mount_present") is not False:
        raise PersistenceMigrationError("audited manager persistence gap is no longer present")
    if readiness.get("portable_restore_role_inventory_complete") is not False:
        raise PersistenceMigrationError("portable role inventory is unexpectedly complete")
    if readiness.get("ready_for_real_backup") is not False:
        raise PersistenceMigrationError("baseline unexpectedly permits a real backup")
    if readiness.get("ready_for_restore") is not False:
        raise PersistenceMigrationError("baseline unexpectedly permits restore")
    if readiness.get("ready_for_anonymous_closure") is not False:
        raise PersistenceMigrationError("baseline unexpectedly permits anonymous closure")

    presence = _mapping(
        baseline.get("portable_restore_role_presence"),
        "portable role presence",
    )
    if presence.get(ROLE_BROKER_DYNAMIC_SECURITY) is not True:
        raise PersistenceMigrationError("broker Dynamic Security state was not observed")
    if presence.get(ROLE_BROKER_PERSISTENCE) is not True:
        raise PersistenceMigrationError("broker persistence state was not observed")
    manager_and_system_roles = REQUIRED_ROLES - {
        ROLE_BROKER_DYNAMIC_SECURITY,
        ROLE_BROKER_PERSISTENCE,
    }
    unexpected = sorted(
        role for role in manager_and_system_roles if presence.get(role) is not False
    )
    if unexpected:
        raise PersistenceMigrationError(
            "manager or system roles are not conclusively absent: " + ",".join(unexpected)
        )
    follow_up = baseline.get("follow_up_codes")
    if (
        not isinstance(follow_up, list)
        or "PORTABLE_RESTORE_ROLE_INVENTORY_INCOMPLETE" not in follow_up
    ):
        raise PersistenceMigrationError("baseline gap code is missing")


def _stages() -> tuple[dict[str, object], ...]:
    return (
        {
            "id": "P0_BINDING_REFRESH",
            "kind": "read_only",
            "purpose": "revalidate PR, exact source, Artifact, container identity, and mounts",
            "future_authorization_required": True,
        },
        {
            "id": "P1_HIDDEN_STATE_CLASSIFICATION",
            "kind": "read_only",
            "purpose": (
                "prove whether legacy runtime state exists outside the missing persistent mount; "
                "missing host mount alone is not proof of statelessness"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "P2_PRIVATE_CANDIDATE_ROOT",
            "kind": "candidate_write",
            "purpose": "prepare an isolated 0700 candidate root with 0600 members",
            "future_authorization_required": True,
        },
        {
            "id": "P3_IDENTITY_INITIALIZE_OR_IMPORT",
            "kind": "candidate_write",
            "purpose": (
                "initialize only after statelessness proof, or import through an explicit adapter "
                "when legacy identity or state exists"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "P4_MANAGER_STATE_ASSEMBLY",
            "kind": "candidate_write",
            "purpose": (
                "materialize registration, credential lifecycle, and retirement outbox semantics "
                "in the persistent manager state file"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "P5_COMPLETE_PORTABLE_INVENTORY",
            "kind": "candidate_copy",
            "purpose": "assemble all ten logical roles and verify the encrypted backup contract",
            "future_authorization_required": True,
        },
        {
            "id": "P6_MOUNT_AND_SHADOW_VALIDATION",
            "kind": "service_change",
            "purpose": (
                "bind the candidate root at /var/lib/greenhouse-manager and validate the target "
                "Manager without changing anonymous access"
            ),
            "future_authorization_required": True,
        },
        {
            "id": "P7_COMMIT_OR_ROLLBACK",
            "kind": "service_change",
            "purpose": (
                "commit only after continuity checks; otherwise restore the prior image and mount set"
            ),
            "future_authorization_required": True,
        },
    )


def build_persistence_migration_plan(
    baseline: Mapping[str, Any],
    *,
    source_sha256: str | None = None,
    require_exact_audited_file: bool = False,
) -> PersistenceMigrationPlan:
    audited_binding = _validate_binding(baseline)
    _validate_read_only_flags(baseline)
    observed_version = _manager_version(baseline)
    _validate_gap(baseline)

    digest = source_sha256 or baseline_digest(baseline)
    if require_exact_audited_file and digest != AUDITED_BASELINE_SHA256:
        raise PersistenceMigrationError("baseline file SHA-256 does not match the audited capture")
    if set(DEFAULT_ROLE_LAYOUT) != REQUIRED_ROLES:
        raise PersistenceMigrationError("default role layout is incomplete")

    operation_flags = {
        "read_only_plan": True,
        "production_services_modified": False,
        "candidate_files_created": False,
        "container_modified": False,
        "container_restarted": False,
        "backup_created": False,
        "restore_executed": False,
        "anonymous_closure_executed": False,
        "network_operation": False,
        "board_operation": False,
        "ready_executed": False,
        "merge_executed": False,
        "release_tag_deployment": False,
        "secret_values_included": False,
    }
    gates = {
        "baseline_binding_valid": True,
        "read_only_evidence_valid": True,
        "manager_persistence_gap_confirmed": True,
        "broker_roles_observed": True,
        "role_layout_complete": True,
        "runtime_hidden_state_classified": False,
        "candidate_root_prepared": False,
        "manager_state_materialized": False,
        "portable_backup_verified": False,
        "execution_authorized": False,
        "ready_for_real_backup": False,
        "ready_for_restore": False,
        "ready_for_anonymous_closure": False,
        "ready_for_deployment": False,
    }
    return PersistenceMigrationPlan(
        schema=PLAN_SCHEMA,
        status="DESIGN_COMPLETE_EXECUTION_BLOCKED",
        remediation_decision_id=REMEDIATION_DECISION_ID,
        baseline_sha256=digest,
        audited_binding=audited_binding,
        observed_manager_version=observed_version,
        target_manager_version=TARGET_MANAGER_VERSION,
        classification="LEGACY_MANAGER_WITHOUT_PERSISTENT_STATE_MOUNT",
        hidden_runtime_state_classification="NOT_PROVEN_ABSENT",
        target_mount={
            "container_path": TARGET_CONTAINER_ROOT,
            "type": "private_bind_mount",
            "read_only": False,
            "root_mode": "0700",
            "member_mode": "0600",
            "host_path": "OPERATOR_BOUND_PRIVATE_PATH_REQUIRED",
            "must_be_absent_before_candidate_creation": True,
            "must_not_be_symlink": True,
        },
        role_inventory=dict(sorted(DEFAULT_ROLE_LAYOUT.items())),
        broker_source_contract={
            ROLE_BROKER_DYNAMIC_SECURITY: "/mosquitto/data/dynamic-security.json",
            ROLE_BROKER_PERSISTENCE: "/mosquitto/data/mosquitto.db",
        },
        stages=_stages(),
        rollback_contract={
            "prior_manager_version": observed_version,
            "prior_manager_image_and_mount_binding_required": True,
            "prior_anonymous_mode_must_remain_unchanged": True,
            "candidate_root_preserved_for_forensics": True,
            "automatic_candidate_deletion": False,
            "rollback_authorization_required": True,
        },
        blocked_reasons=(
            "RUNTIME_HIDDEN_STATE_NOT_CLASSIFIED",
            "TARGET_MANAGER_PERSISTENCE_ROOT_NOT_MOUNTED",
            "TARGET_MANAGER_VERSION_NOT_DEPLOYED",
            "COMPLETE_PORTABLE_ROLE_INVENTORY_NOT_MATERIALIZED",
            "REAL_BACKUP_NOT_AUTHORIZED",
            "REAL_RESTORE_NOT_AUTHORIZED",
            "ANONYMOUS_CLOSURE_NOT_AUTHORIZED",
            "DEPLOYMENT_NOT_AUTHORIZED",
        ),
        gates=gates,
        operation_flags=operation_flags,
    )


def load_audited_baseline(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise PersistenceMigrationError("baseline must be a regular file")
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != AUDITED_BASELINE_SHA256:
        raise PersistenceMigrationError("baseline file SHA-256 does not match the audited capture")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PersistenceMigrationError("baseline JSON is invalid") from error
    if not isinstance(value, dict):
        raise PersistenceMigrationError("baseline JSON must be an object")
    return value, digest
