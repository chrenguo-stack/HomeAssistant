from __future__ import annotations

import copy
import fcntl
import json
import os
import stat
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_common import IMAGE_ID
from n3w_t1_core_updater_ha_acceptance import (
    HA_ACCEPTANCE_ATTEMPTS, HA_ACCEPTANCE_RULE, MONITORING_METHODS, NATURAL_MONITORING_METHOD,
    expected_target_images, valid_evidence_set,
)
from n3w_t1_core_updater_ha_backup import backup_record_from_document
from n3w_t1_core_updater_ha_data_evidence import valid_data_sample
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord, validate_image_recovery_record
from n3w_t1_core_updater_ha_usb_media import (
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    validate_filesystem_uuid,
)
from n3w_t1_core_updater_v2_common import (
    COMPONENTS,
    IMAGE_PREFIXES,
    SHA256,
    TERMINAL_TX_V2,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)
from n3w_t1_core_updater_v2_state import STATE_ROOT_V2, V2StateStore
from n3w_t1_portable_image_identity import PortableImageIdentityError, identity_from_dict


HA_USB_TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
HA_USB_ACTIVE_FILE = "homeassistant-usb-upgrade.json"
HA_USB_TERMINAL_STATUSES = frozenset({"COMMITTED", "ROLLED_BACK"})
HA_USB_STATUSES = frozenset(
    {"ACTIVE", "COMMITTED", "ROLLED_BACK", "FAILED_EMERGENCY"}
)

U0 = "U0_READONLY_ADMISSION"
U1 = "U1_PREPARE_REQUESTED"
U2 = "U2_USB_QUALIFIED_FORMATTED_BOUND"
U3 = "U3_TARGET_DOWNLOADING_VERIFYING"
U4 = "U4_READY_TO_INSTALL"
U5 = "U5_INSTALL_REQUESTED_REVALIDATING"
U6 = "U6_PREDECESSOR_RECOVERY_PREPARING"
U7 = "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
U8 = "U8_RECOVERY_ADMISSION_COMPLETE"
U9 = "U9_LIVE_AUTHORIZATION_CLAIMED"
U10 = "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
U11 = "U11_TARGET_INSTALLED_STARTED"
U12 = "U12_TARGET_ACCEPTANCE"
U13A = "U13A_COMMITTED"
U13B = "U13B_ROLLED_BACK"
PRE_CUTOVER_RECOVERY_PHASES = frozenset({U6, U7, U8})
HA_DATA_RESTORE_PHASES = frozenset({U10, U11, U12})
TARGET_BINDING = "BINDING"
TARGET_WRITES_POSSIBLE = "WRITES_POSSIBLE"

PHASES = (
    U0,
    U1,
    U2,
    U3,
    U4,
    U5,
    U6,
    U7,
    U8,
    U9,
    U10,
    U11,
    U12,
    U13A,
    U13B,
)
PHASE_INDEX = {phase: index for index, phase in enumerate(PHASES)}
USB_CAPACITY_OPERATIONS = frozenset({"target_archive", "predecessor_archive", "protected_data_backup"})
PREPARE_CAPACITY_FAILURES = frozenset({
    "ha_usb_target_space_insufficient",
    "ha_usb_predecessor_space_insufficient",
})
PRE_CUTOVER_TERMINAL_FAILURES = frozenset({
    "ha_usb_predecessor_acceptance_baseline_unavailable",
    "ha_usb_install_revalidation_failed",
})

_ALLOWED_TRANSITIONS = {
    U0: frozenset({U1}),
    U1: frozenset({U2}),
    U2: frozenset({U3}),
    U3: frozenset({U4}),
    U4: frozenset({U5}),
    U5: frozenset({U4, U6}),
    U6: frozenset({U4, U7}),
    U7: frozenset({U8}),
    U8: frozenset({U9}),
    U9: frozenset({U10, U13B}),
    U10: frozenset({U11, U13B}),
    U11: frozenset({U12, U13B}),
    U12: frozenset({U13A, U13B}),
    U13A: frozenset(),
    U13B: frozenset(),
}

_FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "secret",
    "private_key",
    "raw_serial",
)


def _reject_sensitive_fields(value: Any) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            if key == "authorization_id" or any(
                fragment in key for fragment in _FORBIDDEN_KEY_FRAGMENTS
            ):
                raise UpdaterV2Error("ha_usb_transaction_sensitive_field_forbidden")
            _reject_sensitive_fields(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_sensitive_fields(nested)


def _nonempty_string(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpdaterV2Error(reason)
    return value


def _positive_int(value: Any, reason: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise UpdaterV2Error(reason)
    return value


def _bool(value: Any, reason: str) -> bool:
    if not isinstance(value, bool):
        raise UpdaterV2Error(reason)
    return value


def _phase_at_or_after(phase: str, threshold: str) -> bool:
    return PHASE_INDEX[phase] >= PHASE_INDEX[threshold]


def _nonnegative_int(value: Any, reason: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise UpdaterV2Error(reason)
    return value


def _validate_usb_capacity_events(document: dict[str, Any]) -> None:
    events = document.get("usb_capacity_events", [])
    reason = "ha_usb_capacity_event_invalid"
    if not isinstance(events, list) or len(events) > 32:
        raise UpdaterV2Error(reason)
    for event in events:
        if (
            not isinstance(event, dict)
            or set(event) != {
                "operation", "required_bytes", "available_bytes_before", "capacity_pass",
                "actual_written_bytes", "available_bytes_after",
            }
            or event["operation"] not in USB_CAPACITY_OPERATIONS
        ):
            raise UpdaterV2Error(reason)
        required = _positive_int(event["required_bytes"], reason)
        available = _nonnegative_int(event["available_bytes_before"], reason)
        passed = _bool(event["capacity_pass"], reason)
        if passed != (available >= required):
            raise UpdaterV2Error(reason)
        actual = event["actual_written_bytes"]
        after = event["available_bytes_after"]
        if (actual is None) != (after is None):
            raise UpdaterV2Error(reason)
        if actual is not None:
            actual = _positive_int(actual, reason)
            _nonnegative_int(after, reason)
            if not passed or actual > required:
                raise UpdaterV2Error(reason)


def record_usb_capacity_event(
    document: dict[str, Any],
    *,
    operation: str,
    required_bytes: int,
    available_bytes_before: int,
    capacity_pass: bool,
    actual_written_bytes: int | None = None,
    available_bytes_after: int | None = None,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    event = {
        "operation": operation,
        "required_bytes": required_bytes,
        "available_bytes_before": available_bytes_before,
        "capacity_pass": capacity_pass,
        "actual_written_bytes": actual_written_bytes,
        "available_bytes_after": available_bytes_after,
    }
    probe = {**current, "usb_capacity_events": [*current.get("usb_capacity_events", []), event]}
    _validate_usb_capacity_events(probe)
    events = list(current.get("usb_capacity_events", []))
    if actual_written_bytes is None:
        if (
            events
            and events[-1]["operation"] == operation
            and events[-1]["capacity_pass"] is True
            and events[-1]["actual_written_bytes"] is None
        ):
            events[-1] = event
        else:
            events.append(event)
    else:
        if not (
            events
            and events[-1]["operation"] == operation
            and events[-1]["capacity_pass"] is True
            and events[-1]["actual_written_bytes"] is None
            and events[-1]["required_bytes"] == required_bytes
            and events[-1]["available_bytes_before"] == available_bytes_before
        ):
            raise UpdaterV2Error("ha_usb_capacity_event_completion_without_admission")
        events[-1] = event
    result = {
        **current,
        "usb_capacity_events": events,
        "updated_at_unix": max(current["updated_at_unix"], int(time.time())),
    }
    _validate_usb_capacity_events(result)
    return result


def replaceable_capacity_blocked_preparation(document: dict[str, Any]) -> bool:
    current = validate_transaction_document(document)
    return (
        current["status"] == "ACTIVE"
        and current["phase"] == U3
        and current.get("failure_code") in PREPARE_CAPACITY_FAILURES
        and current["recovery_required"] is False
        and current["authorization_claimed"] is False
        and current["authorization_consumed"] is False
        and "predecessor_start" not in current
    )


def _validate_predecessor_start(document: dict[str, Any]) -> None:
    binding = document["predecessor_start"]
    if not isinstance(binding, dict) or set(binding) != {"launch_sha256", "images"}:
        raise UpdaterV2Error("ha_usb_predecessor_start_binding_invalid")
    digest = binding["launch_sha256"]
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise UpdaterV2Error("ha_usb_predecessor_launch_identity_invalid")
    images = binding["images"]
    if not isinstance(images, dict) or set(images) != set(COMPONENTS):
        raise UpdaterV2Error("ha_usb_predecessor_image_set_invalid")
    for component, image in images.items():
        if not isinstance(image, dict) or set(image) != {"reference", "runtime_id"}:
            raise UpdaterV2Error("ha_usb_predecessor_image_binding_invalid")
        reference, runtime_id = image["reference"], image["runtime_id"]
        if (
            not isinstance(reference, str)
            or not reference.startswith(IMAGE_PREFIXES[component])
            or not isinstance(runtime_id, str)
            or IMAGE_ID.fullmatch(runtime_id) is None
        ):
            raise UpdaterV2Error("ha_usb_predecessor_image_binding_invalid")
    if images["homeassistant"]["reference"] != document["current_image_ref"]:
        raise UpdaterV2Error("ha_usb_predecessor_homeassistant_image_drift")


def _validated_image_materials(
    document: dict[str, Any], materials: dict[str, Any]
) -> tuple[ImageRecoveryRecord, ImageRecoveryRecord]:
    try:
        target = ImageRecoveryRecord(**materials["target"])
        predecessor = ImageRecoveryRecord(**materials["predecessor"])
    except TypeError as error:
        raise UpdaterV2Error("ha_usb_install_recovery_materials_invalid") from error
    validate_image_recovery_record(
        target, expected_kind="target",
        expected_image_ref=document["target_image_ref"],
        expected_archive_sha256=document["target_archive_sha256"],
    )
    validate_image_recovery_record(
        predecessor, expected_kind="predecessor",
        expected_image_ref=document["current_image_ref"],
    )
    if target.archive_size_bytes != document["target_archive_size"]:
        raise UpdaterV2Error("ha_usb_install_target_size_drift")
    return target, predecessor


def prepared_image_materials(
    document: dict[str, Any],
) -> tuple[ImageRecoveryRecord, ImageRecoveryRecord]:
    materials = document.get("prepared_image_materials")
    if not isinstance(materials, dict) or set(materials) != {"target", "predecessor"}:
        raise UpdaterV2Error("ha_usb_prepared_image_materials_invalid")
    target, predecessor = _validated_image_materials(document, materials)
    source_identity = document["current_image_identity"].get(
        "portable_identity_sha256"
    )
    if (
        source_identity is not None
        and source_identity != predecessor.portable_identity_sha256
    ):
        raise UpdaterV2Error("ha_usb_predecessor_archive_identity_drift")
    return target, predecessor


def _validate_recovery_materials(document: dict[str, Any]) -> None:
    materials = document.get("install_recovery_materials")
    if not isinstance(materials, dict) or set(materials) != {"target", "predecessor", "backup"}:
        raise UpdaterV2Error("ha_usb_install_recovery_materials_invalid")
    records = _validated_image_materials(document, materials)
    if document.get("usb_binding_mode") == "existing_filesystem" and (
        records != prepared_image_materials(document)
    ):
        raise UpdaterV2Error("ha_usb_install_recovery_material_identity_drift")
    backup_record_from_document(materials["backup"])


def _validate_bound_load_identity(value: Any, record: ImageRecoveryRecord, reason: str) -> None:
    try:
        identity = identity_from_dict(value)
    except (PortableImageIdentityError, TypeError) as error:
        raise UpdaterV2Error(reason) from error
    if (
        (identity.os, identity.architecture) != ("linux", "arm64")
        or sha256_bytes(canonical(identity.to_dict())) != record.portable_identity_sha256
        or identity.archive_sha256 != record.archive_sha256
        or identity.archive_size_bytes != record.archive_size_bytes
    ):
        raise UpdaterV2Error(reason)


def _validate_data_restore(document: dict[str, Any]) -> None:
    journal = document["ha_data_restore"]
    reason = "ha_usb_data_restore_journal_invalid"
    if (
        document.get("usb_binding_mode") != "existing_filesystem"
        or "predecessor_start" not in document
        or not isinstance(journal, dict)
        or journal.get("step") not in ("STAGING", "EXCHANGE_PENDING", "PUBLISHED")
    ):
        raise UpdaterV2Error(reason)
    step = journal["step"]
    expected = {"step", "filesystem_id", "original_inode"}
    if step != "STAGING":
        expected.add("staged_inode")
    if step == "PUBLISHED" and "predecessor_load_identity" in journal:
        expected.add("predecessor_load_identity")
        _, predecessor = prepared_image_materials(document)
        _validate_bound_load_identity(journal["predecessor_load_identity"], predecessor, reason)
    if set(journal) != expected or type(journal["filesystem_id"]) is not int:
        raise UpdaterV2Error(reason)
    original = _positive_int(journal["original_inode"], reason)
    if step != "STAGING" and _positive_int(journal["staged_inode"], reason) == original:
        raise UpdaterV2Error(reason)
    if document["phase"] == U13B and step == "PUBLISHED" and document["recovery_required"] is False:
        return
    if document["phase"] not in HA_DATA_RESTORE_PHASES or document["recovery_required"] is not True:
        raise UpdaterV2Error(reason)


def _validate_target_acceptance(document: dict[str, Any]) -> None:
    state = document["target_acceptance"]
    phase = document["phase"]
    reason = "ha_usb_target_acceptance_invalid"
    fields = {
        "rule", "baseline", "attempts", "receipt", "data_sample", "monitoring_method",
        "monitoring_fallback_sha256", "last_attempt_verdicts", "retry_after_unix",
    }
    if (
        not isinstance(state, dict) or set(state) - fields
        or state.get("rule") != HA_ACCEPTANCE_RULE or not valid_evidence_set(state.get("baseline"))
        or type(state.get("attempts")) is not int or not 0 <= state["attempts"] <= HA_ACCEPTANCE_ATTEMPTS
        or not _phase_at_or_after(phase, U6)
        or (state["attempts"] > 0 and not _phase_at_or_after(phase, U11))
    ):
        raise UpdaterV2Error(reason)
    if "monitoring_method" in state and (
        state["monitoring_method"] not in MONITORING_METHODS or "data_sample" not in state
    ):
        raise UpdaterV2Error(reason)
    if "monitoring_fallback_sha256" in state and (
        state.get("monitoring_method") != NATURAL_MONITORING_METHOD
        or not isinstance(state["monitoring_fallback_sha256"], str)
        or SHA256.fullmatch(state["monitoring_fallback_sha256"]) is None
    ):
        raise UpdaterV2Error(reason)
    if "data_sample" in state and (
        not valid_data_sample(state["data_sample"])
        or state["baseline"]["protected_data"] != sha256_bytes(canonical(state["data_sample"]))
    ):
        raise UpdaterV2Error(reason)
    if "last_attempt_verdicts" in state:
        verdicts = state["last_attempt_verdicts"]
        if (
            state["attempts"] == 0 or not isinstance(verdicts, dict)
            or set(verdicts) != set(HA_ACCEPTANCE_CHECKS)
            or any(
                verdict not in {"PASS", "PROVEN_FAIL", "EVIDENCE_UNAVAILABLE"}
                for verdict in verdicts.values()
            )
        ):
            raise UpdaterV2Error(reason)
    if "retry_after_unix" in state and (
        type(state["retry_after_unix"]) is not int or state["retry_after_unix"] <= 0
        or state["attempts"] <= 0 or state["attempts"] >= HA_ACCEPTANCE_ATTEMPTS
        or phase != U11 or document.get("status") != "ACTIVE"
        or document.get("recovery_required") is not False or "receipt" in state
    ):
        raise UpdaterV2Error(reason)
    if "receipt" in state:
        receipt = state["receipt"]
        if (
            phase not in {U12, U13A, U13B} or state["attempts"] == 0
            or document.get("target_activation") != TARGET_WRITES_POSSIBLE
            or "predecessor_start" not in document or "target_loaded_image_id" not in document
            or not isinstance(receipt, dict) or set(receipt) != {"runtime_sha256", "images", "observations"}
            or not isinstance(receipt["runtime_sha256"], str) or not SHA256.fullmatch(receipt["runtime_sha256"])
            or receipt["images"] != expected_target_images(document)
            or not valid_evidence_set(receipt["observations"])
            or (
                "data_sample" in state
                and receipt["observations"]["protected_data"] != state["baseline"]["protected_data"]
            )
        ):
            raise UpdaterV2Error(reason)
    elif phase in {U12, U13A}:
        raise UpdaterV2Error(reason)


def validate_transaction_document(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema") != HA_USB_TX_SCHEMA:
        raise UpdaterV2Error("ha_usb_transaction_schema_invalid")
    _reject_sensitive_fields(document)

    if document.get("component") != "homeassistant":
        raise UpdaterV2Error("ha_usb_transaction_component_invalid")

    transaction_id = document.get("transaction_id_sha256")
    if not isinstance(transaction_id, str) or SHA256.fullmatch(transaction_id) is None:
        raise UpdaterV2Error("ha_usb_transaction_id_invalid")

    phase = document.get("phase")
    if phase not in PHASE_INDEX:
        raise UpdaterV2Error("ha_usb_transaction_phase_invalid")
    status = document.get("status")
    if status not in HA_USB_STATUSES:
        raise UpdaterV2Error("ha_usb_transaction_status_invalid")

    current_ref = _nonempty_string(
        document.get("current_image_ref"),
        "ha_usb_current_image_ref_invalid",
    )
    target_ref = _nonempty_string(
        document.get("target_image_ref"),
        "ha_usb_target_image_ref_invalid",
    )
    if (
        not current_ref.startswith("local/n3w-homeassistant:")
        or not target_ref.startswith("local/n3w-homeassistant:")
        or current_ref == target_ref
    ):
        raise UpdaterV2Error("ha_usb_image_namespace_invalid")

    for key in ("current_image_identity", "target_manifest_identity"):
        value = document.get(key)
        if not isinstance(value, dict) or not value:
            raise UpdaterV2Error(f"ha_usb_{key}_invalid")
    manifest = document["target_manifest_identity"]
    if "predecessor_binding_sha256" in manifest:
        binding_sha = manifest["predecessor_binding_sha256"]
        if not isinstance(binding_sha, str) or SHA256.fullmatch(binding_sha) is None:
            raise UpdaterV2Error("ha_usb_signed_predecessor_binding_invalid")

    target_sha = document.get("target_archive_sha256")
    if not isinstance(target_sha, str) or SHA256.fullmatch(target_sha) is None:
        raise UpdaterV2Error("ha_usb_target_archive_sha256_invalid")
    _positive_int(
        document.get("target_archive_size"),
        "ha_usb_target_archive_size_invalid",
    )

    created = _positive_int(
        document.get("created_at_unix"),
        "ha_usb_created_at_invalid",
    )
    updated = _positive_int(
        document.get("updated_at_unix"),
        "ha_usb_updated_at_invalid",
    )
    if updated < created:
        raise UpdaterV2Error("ha_usb_updated_before_created")

    target_verified = _bool(
        document.get("target_artifact_verified"),
        "ha_usb_target_verified_invalid",
    )
    predecessor_verified = _bool(
        document.get("predecessor_recovery_verified"),
        "ha_usb_predecessor_verified_invalid",
    )
    backup_verified = _bool(
        document.get("ha_data_backup_verified"),
        "ha_usb_backup_verified_invalid",
    )
    capacity_verified = _bool(
        document.get("usb_capacity_verified"),
        "ha_usb_capacity_verified_invalid",
    )
    prestate_verified = _bool(
        document.get("production_prestate_verified"),
        "ha_usb_prestate_verified_invalid",
    )
    claimed = _bool(
        document.get("authorization_claimed"),
        "ha_usb_authorization_claimed_invalid",
    )
    consumed = _bool(
        document.get("authorization_consumed"),
        "ha_usb_authorization_consumed_invalid",
    )
    if claimed != consumed:
        raise UpdaterV2Error("ha_usb_authorization_state_inconsistent")

    recovery_required = _bool(
        document.get("recovery_required"),
        "ha_usb_recovery_required_invalid",
    )
    has_start_binding = "predecessor_start" in document
    restored_before_cutover = document.get("pre_cutover_predecessor_restored", False)
    _bool(restored_before_cutover, "ha_usb_pre_cutover_restoration_invalid")
    if has_start_binding:
        if not _phase_at_or_after(phase, U6):
            raise UpdaterV2Error("ha_usb_predecessor_start_too_early")
        _validate_predecessor_start(document)
        if _phase_at_or_after(phase, U8):
            _validate_recovery_materials(document)
    if restored_before_cutover and (
        not has_start_binding
        or phase not in PRE_CUTOVER_RECOVERY_PHASES
        or status != "ROLLED_BACK"
        or recovery_required
    ):
        raise UpdaterV2Error("ha_usb_pre_cutover_restoration_invalid")
    _validate_usb_capacity_events(document)

    failure_code = document.get("failure_code")
    if failure_code is not None and (
        not isinstance(failure_code, str)
        or not failure_code
        or len(failure_code) > 200
        or any(ch in failure_code for ch in ("/", "\\", "@"))
    ):
        raise UpdaterV2Error("ha_usb_failure_code_invalid")

    if _phase_at_or_after(phase, U2):
        fingerprint = document.get("usb_device_identity_public_fingerprint")
        if not isinstance(fingerprint, str) or SHA256.fullmatch(fingerprint) is None:
            raise UpdaterV2Error("ha_usb_public_fingerprint_invalid")
        validate_filesystem_uuid(
            _nonempty_string(
                document.get("usb_filesystem_uuid"),
                "ha_usb_filesystem_uuid_invalid",
            )
        )
        _nonempty_string(
            document.get("usb_mount_authority"),
            "ha_usb_mount_authority_invalid",
        )
        measured = _positive_int(
            document.get("usb_measured_usable_bytes"),
            "ha_usb_measured_usable_bytes_invalid",
        )
        if measured < USB_MEASURED_USABLE_CAPACITY_MIN_BYTES:
            raise UpdaterV2Error("ha_usb_measured_capacity_below_floor")
        if capacity_verified is not True:
            raise UpdaterV2Error("ha_usb_capacity_not_verified")
    else:
        if any(
            document.get(key) not in (None, 0, False)
            for key in (
                "usb_device_identity_public_fingerprint",
                "usb_filesystem_uuid",
                "usb_mount_authority",
                "usb_measured_usable_bytes",
                "usb_capacity_verified",
            )
        ):
            raise UpdaterV2Error("ha_usb_media_bound_too_early")

    if _phase_at_or_after(phase, U4) and target_verified is not True:
        raise UpdaterV2Error("ha_usb_target_not_verified")
    if "usb_binding_mode" in document:
        if document["usb_binding_mode"] != "existing_filesystem" or not _phase_at_or_after(phase, U2):
            raise UpdaterV2Error("ha_usb_binding_mode_invalid")
        if _phase_at_or_after(phase, U4):
            prepared_image_materials(document)
    if _phase_at_or_after(phase, U7) and predecessor_verified is not True:
        raise UpdaterV2Error("ha_usb_predecessor_not_verified")
    if _phase_at_or_after(phase, U8):
        if backup_verified is not True:
            raise UpdaterV2Error("ha_usb_backup_not_verified")
        if prestate_verified is not True:
            raise UpdaterV2Error("ha_usb_prestate_not_verified")

    auth_sha = document.get("authorization_id_sha256")
    if _phase_at_or_after(phase, U9):
        if (
            claimed is not True
            or consumed is not True
            or not isinstance(auth_sha, str)
            or SHA256.fullmatch(auth_sha) is None
        ):
            raise UpdaterV2Error("ha_usb_live_authorization_missing")
    elif claimed or consumed or auth_sha is not None:
        raise UpdaterV2Error("ha_usb_live_authorization_claimed_too_early")

    if phase == U13A and status != "COMMITTED":
        raise UpdaterV2Error("ha_usb_commit_status_invalid")
    if phase == U13B and status != "ROLLED_BACK":
        raise UpdaterV2Error("ha_usb_rollback_status_invalid")
    pre_cutover_failed_without_mutation = (
        status == "ROLLED_BACK"
        and phase == U4
        and not has_start_binding
        and recovery_required is False
        and claimed is False
        and consumed is False
        and auth_sha is None
        and failure_code in PRE_CUTOVER_TERMINAL_FAILURES
    )
    if (
        phase not in {U13A, U13B}
        and status in HA_USB_TERMINAL_STATUSES
        and not restored_before_cutover
        and not pre_cutover_failed_without_mutation
    ):
        raise UpdaterV2Error("ha_usb_terminal_status_phase_mismatch")
    if status == "FAILED_EMERGENCY" and recovery_required is not True:
        raise UpdaterV2Error("ha_usb_failed_emergency_without_recovery")
    if "ha_data_restore" in document:
        _validate_data_restore(document)
    single_image = False
    if "predecessor_release_admission" in document:
        admission = document["predecessor_release_admission"]
        fields = {"internal_available_bytes", "install_required_bytes", "recovery_required_bytes"}
        reason = "ha_usb_predecessor_release_admission_invalid"
        if (
            not _phase_at_or_after(phase, U9) or document.get("usb_binding_mode") != "existing_filesystem"
            or not isinstance(admission, dict)
            or set(admission) not in (fields, fields | {"recovery_workspace_bytes"})
        ):
            raise UpdaterV2Error(reason)
        available = _positive_int(admission["internal_available_bytes"], reason)
        if any(available < _positive_int(admission[key], reason) for key in fields - {"internal_available_bytes"}):
            raise UpdaterV2Error(reason)
        single_image = "recovery_workspace_bytes" in admission
        if single_image and _positive_int(admission["recovery_workspace_bytes"], reason) >= admission["recovery_required_bytes"]:
            raise UpdaterV2Error(reason)
    if "predecessor_release_intent" in document:
        intent = document["predecessor_release_intent"]
        if (
            "predecessor_release_admission" not in document or "predecessor_start" not in document
            or not isinstance(intent, dict) or set(intent) != {"container_id"}
        ):
            raise UpdaterV2Error("ha_usb_predecessor_release_intent_invalid")
        container = intent["container_id"]
        if container is not None and (not isinstance(container, str) or SHA256.fullmatch(container) is None):
            raise UpdaterV2Error("ha_usb_predecessor_release_container_invalid")
        if phase in {U10, U11, U12, U13A} and document.get("predecessor_release_observed") is not True:
            raise UpdaterV2Error("ha_usb_predecessor_release_not_observed")
    if "predecessor_release_observed" in document and (
        "predecessor_release_intent" not in document or not _phase_at_or_after(phase, U10)
        or document["predecessor_release_observed"] is not True
    ):
        raise UpdaterV2Error("ha_usb_predecessor_release_observation_invalid")
    if "target_load_identity" in document or "predecessor_reload_identity" in document:
        reason = "ha_usb_image_load_intent_invalid"
        if document.get("predecessor_release_observed") is not True:
            raise UpdaterV2Error(reason)
        target, predecessor = prepared_image_materials(document)
        if "target_load_identity" in document:
            _validate_bound_load_identity(document["target_load_identity"], target, reason)
        if "predecessor_reload_identity" in document:
            if phase not in {U10, U13B} or "ha_data_restore" in document or (phase == U10 and not recovery_required):
                raise UpdaterV2Error(reason)
            _validate_bound_load_identity(document["predecessor_reload_identity"], predecessor, reason)
    if "target_loaded_image_id" in document:
        loaded = document["target_loaded_image_id"]
        if "target_load_identity" not in document or not isinstance(loaded, str) or IMAGE_ID.fullmatch(loaded) is None:
            raise UpdaterV2Error("ha_usb_target_loaded_image_invalid")
    target_release = document.get("target_release_step")
    release_image_id = document.get("target_release_image_id")
    if ("target_release_image_id" in document) != ("target_release_step" in document) or (
        release_image_id is not None and (
            not isinstance(release_image_id, str) or IMAGE_ID.fullmatch(release_image_id) is None
            or "target_load_identity" not in document
            or document.get("target_loaded_image_id", release_image_id) != release_image_id
        )
    ):
        raise UpdaterV2Error("ha_usb_rollback_target_release_identity_invalid")
    if "target_release_step" in document and (
        not single_image or target_release not in ("INTENT", "RELEASED")
        or document.get("predecessor_release_observed") is not True
        or (phase == U13B and target_release != "RELEASED")
        or (phase != U13B and (phase not in HA_DATA_RESTORE_PHASES or not recovery_required))
    ):
        raise UpdaterV2Error("ha_usb_rollback_target_release_invalid")
    if single_image and target_release != "RELEASED" and (
        "predecessor_reload_identity" in document or "ha_data_restore" in document
        or (phase == U13B and document.get("predecessor_release_observed") is True)
    ):
        raise UpdaterV2Error("ha_usb_rollback_target_release_not_observed")
    if "target_activation" in document:
        activation = document["target_activation"]
        if (
            activation not in (TARGET_BINDING, TARGET_WRITES_POSSIBLE)
            or "target_loaded_image_id" not in document
            or phase not in {U10, U11, U12, U13A, U13B}
            or (activation == TARGET_BINDING and (phase not in {U10, U13B} or "ha_data_restore" in document))
            or (activation == TARGET_WRITES_POSSIBLE and "predecessor_reload_identity" in document)
            or (activation == TARGET_WRITES_POSSIBLE and phase == U13B and "ha_data_restore" not in document)
        ):
            raise UpdaterV2Error("ha_usb_target_activation_state_invalid")
    if "target_acceptance" in document:
        _validate_target_acceptance(document)
    return copy.deepcopy(document)


def new_transaction(
    *,
    current_image_ref: str,
    current_image_identity: dict[str, Any],
    target_manifest_identity: dict[str, Any],
    target_image_ref: str,
    target_archive_sha256: str,
    target_archive_size: int,
    created_at_unix: int | None = None,
) -> dict[str, Any]:
    created = int(time.time()) if created_at_unix is None else created_at_unix
    authority = {
        "component": "homeassistant",
        "current_image_ref": current_image_ref,
        "current_image_identity": copy.deepcopy(current_image_identity),
        "target_manifest_identity": copy.deepcopy(target_manifest_identity),
        "target_image_ref": target_image_ref,
        "target_archive_sha256": target_archive_sha256,
        "target_archive_size": target_archive_size,
        "created_at_unix": created,
    }
    document = {
        "schema": HA_USB_TX_SCHEMA,
        "transaction_id_sha256": sha256_bytes(canonical(authority)),
        "phase": U0,
        "status": "ACTIVE",
        **authority,
        "usb_device_identity_public_fingerprint": None,
        "usb_filesystem_uuid": None,
        "usb_measured_usable_bytes": 0,
        "usb_mount_authority": None,
        "usb_capacity_verified": False,
        "target_artifact_verified": False,
        "predecessor_recovery_verified": False,
        "ha_data_backup_verified": False,
        "production_prestate_verified": False,
        "authorization_id_sha256": None,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "failure_code": None,
        "recovery_required": False,
        "updated_at_unix": created,
    }
    return validate_transaction_document(document)


def transition(
    document: dict[str, Any],
    next_phase: str,
    *,
    updates: dict[str, Any] | None = None,
    updated_at_unix: int | None = None,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    current_phase = current["phase"]
    if current["status"] != "ACTIVE":
        raise UpdaterV2Error("ha_usb_transaction_not_active")
    if (
        current_phase in PRE_CUTOVER_RECOVERY_PHASES
        and "predecessor_start" in current
        and current["recovery_required"]
    ):
        raise UpdaterV2Error("ha_usb_pre_cutover_recovery_in_progress")
    if next_phase not in _ALLOWED_TRANSITIONS[current_phase]:
        raise UpdaterV2Error("ha_usb_phase_transition_invalid")
    if "ha_data_restore" in current and next_phase != U13B:
        raise UpdaterV2Error("ha_usb_data_restore_in_progress")
    if (
        "predecessor_release_intent" in current and next_phase in {U11, U12, U13A}
        and current.get("target_activation") != TARGET_WRITES_POSSIBLE
    ):
        raise UpdaterV2Error("ha_usb_target_write_intent_missing")
    if "predecessor_release_intent" in current and next_phase in {U12, U13A}:
        acceptance = (updates or {}).get("target_acceptance", current.get("target_acceptance"))
        if not isinstance(acceptance, dict) or "receipt" not in acceptance:
            raise UpdaterV2Error("ha_usb_target_acceptance_receipt_required")
    if current.get("usb_binding_mode") == "existing_filesystem":
        if next_phase == U9 and "predecessor_release_admission" not in (updates or {}):
            raise UpdaterV2Error("ha_usb_predecessor_release_admission_missing")
        if current_phase == U9 and next_phase == U10 and "predecessor_release_admission" not in current:
            raise UpdaterV2Error("ha_usb_predecessor_release_admission_missing")
    if next_phase == U4 and current_phase in {U5, U6} and "predecessor_start" in current:
        raise UpdaterV2Error("ha_usb_install_cannot_defer_after_first_stop")

    result = copy.deepcopy(current)
    result["phase"] = next_phase
    if next_phase == U4:
        result.pop("target_acceptance", None)
    if updates:
        for key, value in updates.items():
            if key in {
                "schema",
                "transaction_id_sha256",
                "component",
                "created_at_unix",
                "predecessor_start",
                "pre_cutover_predecessor_restored",
                "ha_data_restore",
                "target_load_identity",
                "target_loaded_image_id",
                "target_activation",
                "target_release_step",
                "target_release_image_id",
                "predecessor_reload_identity",
            }:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key == "install_recovery_materials" and next_phase != U8:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key == "prepared_image_materials" and not (current_phase == U3 and next_phase == U4):
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key == "usb_binding_mode" and next_phase != U2:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key in {"predecessor_release_admission", "predecessor_release_intent"} and next_phase != U9:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key == "predecessor_release_observed" and next_phase != U10:
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            if key == "target_acceptance" and (
                current_phase != U11 or next_phase != U12 or not isinstance(value, dict)
                or {k: v for k, v in value.items() if k != "receipt"} != current.get(key)
            ):
                raise UpdaterV2Error("ha_usb_immutable_field_update_forbidden")
            result[key] = copy.deepcopy(value)

    if next_phase == U13A:
        result["status"] = "COMMITTED"
        result["recovery_required"] = False
    elif next_phase == U13B:
        result["status"] = "ROLLED_BACK"
        result["recovery_required"] = False

    now = int(time.time()) if updated_at_unix is None else updated_at_unix
    result["updated_at_unix"] = max(int(result["created_at_unix"]), now)
    return validate_transaction_document(result)


def mark_failed_emergency(
    document: dict[str, Any],
    *,
    failure_code: str,
    updated_at_unix: int | None = None,
) -> dict[str, Any]:
    result = validate_transaction_document(document)
    if result["status"] in HA_USB_TERMINAL_STATUSES:
        raise UpdaterV2Error("ha_usb_terminal_transaction_cannot_fail")
    result["status"] = "FAILED_EMERGENCY"
    result["failure_code"] = failure_code
    result["recovery_required"] = True
    now = int(time.time()) if updated_at_unix is None else updated_at_unix
    result["updated_at_unix"] = max(int(result["created_at_unix"]), now)
    return validate_transaction_document(result)


class HaUsbStateStore:
    def __init__(self, root: Path = STATE_ROOT_V2) -> None:
        self.root = root
        self.path = root / HA_USB_ACTIVE_FILE
        self.history = root / "history"

    def lock(self):
        return V2StateStore(self.root).lock()

    @contextmanager
    def _activation_descriptor(self, path: Path, flags: int) -> Iterator[int]:
        # The private inode is stable across transaction record replacements.
        descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid():
                raise UpdaterV2Error("ha_usb_target_start_permit_invalid")
            yield descriptor
        finally:
            os.close(descriptor)

    @contextmanager
    def allow_target_start(self, transaction_id: str) -> Iterator[None]:
        path = self.root / f".ha-target-start-{transaction_id}"
        with self._activation_descriptor(path, os.O_RDWR | os.O_CREAT) as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                path.unlink(missing_ok=True)

    def take_target_start_permit(self, transaction_id: str) -> bool:
        # Process exit and reboot release the permit without replaying a pending start.
        path = self.root / f".ha-target-start-{transaction_id}"
        try:
            with self._activation_descriptor(path, os.O_RDONLY) as descriptor:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    # Only one systemd start condition may use this live permit.
                    path.unlink()
                    return True
        except FileNotFoundError:
            pass
        return False

    def _validate_private_dir(self, path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise UpdaterV2Error("transaction_directory_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UpdaterV2Error("transaction_directory_not_private")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("transaction_directory_owner_invalid")

    def _existing_root(self) -> bool:
        if self.root.is_symlink():
            raise UpdaterV2Error("transaction_root_symlink")
        if not self.root.exists():
            return False
        self._validate_private_dir(self.root)
        return True

    def _ensure_root(self) -> None:
        if not self._existing_root():
            self.root.mkdir(parents=True, mode=0o700)
        self._validate_private_dir(self.root)

    def _ensure_history(self) -> None:
        self._ensure_root()
        if self.history.is_symlink():
            raise UpdaterV2Error("transaction_history_symlink")
        if not self.history.exists():
            self.history.mkdir(mode=0o700)
        self._validate_private_dir(self.history)

    def read(self) -> dict[str, Any] | None:
        if not self._existing_root() or not self.path.exists():
            return None
        return self._read_record(self.path)

    @staticmethod
    def _read_record(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("ha_usb_transaction_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise UpdaterV2Error("ha_usb_transaction_metadata_invalid")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("ha_usb_transaction_owner_invalid")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("ha_usb_transaction_invalid") from error
        return validate_transaction_document(document)

    def was_authorization_consumed(self, authorization_sha256: str) -> bool:
        if not self.history.exists() and not self.history.is_symlink():
            return False
        self._validate_private_dir(self.history)
        for path in self.history.glob("*-homeassistant-usb-*.json"):
            recorded = self._read_record(path)
            if recorded["authorization_consumed"] and recorded["authorization_id_sha256"] == authorization_sha256:
                return True
        return False

    def _archive_current(self, document: dict[str, Any], *, retain_current: bool) -> None:
        self._ensure_history()
        digest = sha256_bytes(canonical(document))[:16]
        timestamp = document["updated_at_unix"] if retain_current else int(time.time())
        destination = self.history / f"{timestamp}-homeassistant-usb-{digest}.json"
        if retain_current:
            # Keep a readable terminal record until the next transaction is durable.
            try:
                os.link(self.path, destination)
            except FileExistsError:
                if self._read_record(destination) != document:
                    raise UpdaterV2Error("transaction_history_collision")
        else:
            if destination.exists() or destination.is_symlink():
                raise UpdaterV2Error("transaction_history_collision")
            os.replace(self.path, destination)
            os.chmod(destination, 0o600)
        for path in (self.history, self.root):
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def prepare_new(self, *, replacement: dict[str, Any] | None = None) -> None:
        self._ensure_root()
        generic = V2StateStore(self.root)
        current_generic = generic.read()
        legacy = generic.read_legacy()
        if (
            current_generic is not None
            and current_generic.get("status") not in TERMINAL_TX_V2
        ):
            raise UpdaterV2Error("upgrade_transaction_active")
        if (
            legacy is not None
            and legacy.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise UpdaterV2Error("legacy_transaction_reconciliation_required")

        current = self.read()
        replaceable_block = (
            current is not None
            and replacement is not None
            and replaceable_capacity_blocked_preparation(current)
        )
        if (
            current is not None
            and current["status"] not in HA_USB_TERMINAL_STATUSES
            and not replaceable_block
        ):
            raise UpdaterV2Error("ha_usb_transaction_active")
        if replacement is not None:
            replacement = validate_transaction_document(replacement)
            if replacement["phase"] not in {U0, U1}:
                raise UpdaterV2Error("ha_usb_replacement_phase_invalid")
            if replaceable_block and replacement["transaction_id_sha256"] == current["transaction_id_sha256"]:
                raise UpdaterV2Error("ha_usb_replacement_transaction_reused")
        if current is not None:
            self._archive_current(current, retain_current=replacement is not None)
        if replacement is not None:
            self.write(replacement)

    def write(self, document: dict[str, Any]) -> None:
        validated = validate_transaction_document(document)
        self._ensure_root()
        payload = json.dumps(validated, sort_keys=True, indent=2) + "\n"
        fd, raw = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.root)
        temporary = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            descriptor = os.open(
                self.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
