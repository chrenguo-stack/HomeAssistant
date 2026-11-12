from __future__ import annotations

from typing import Any

from n3w_t1_core_updater_ha_capacity import (
    InstallCapacityRevalidation,
    RecoveryAdmissionCapacity,
    validate_install_revalidation,
    validate_recovery_admission_capacity,
)
from n3w_t1_core_updater_ha_backup import (
    HaDataBackupRecord,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb_media import (
    USB_FILESYSTEM,
    USB_LABEL,
    FormatAuthorization,
    UsbCapacityReport,
    validate_filesystem_uuid,
)
from n3w_t1_core_updater_ha_usb_state import (
    PHASE_INDEX,
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
    compute_recovery_content_manifest_sha256,
    transition,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import (
    AUTHORIZATION_ID,
    SHA256,
    UpdaterV2Error,
    sha256_bytes,
)



def request_prepare(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U0:
        raise UpdaterV2Error("ha_usb_prepare_phase_invalid")
    return transition(current, U1)


def record_media_bound(
    document: dict[str, Any],
    *,
    format_authorization: FormatAuthorization,
    filesystem_uuid: str,
    measured_usable_bytes: int,
    capacity_report: UsbCapacityReport,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U1:
        raise UpdaterV2Error("ha_usb_media_bind_phase_invalid")
    if (
        format_authorization.confirmation_verified is not True
        or format_authorization.filesystem != USB_FILESYSTEM
        or format_authorization.label != USB_LABEL
        or format_authorization.public_fingerprint is None
    ):
        raise UpdaterV2Error("ha_usb_format_authorization_invalid")
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if capacity_report.measured_usable_bytes != measured_usable_bytes:
        raise UpdaterV2Error("ha_usb_measured_capacity_drift")
    return transition(
        current,
        U2,
        updates={
            "usb_device_identity_public_fingerprint": (
                format_authorization.public_fingerprint
            ),
            "usb_filesystem_uuid": filesystem_uuid,
            "usb_measured_usable_bytes": measured_usable_bytes,
            "usb_mount_authority": f"filesystem_uuid:{filesystem_uuid}",
            "usb_capacity_verified": True,
        },
    )


def record_compatible_media(
    document: dict[str, Any],
    *,
    public_fingerprint: str,
    filesystem_uuid: str,
    measured_usable_bytes: int,
    capacity_report: UsbCapacityReport,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U1:
        raise UpdaterV2Error("ha_usb_media_bind_phase_invalid")
    if (
        not isinstance(public_fingerprint, str)
        or SHA256.fullmatch(public_fingerprint) is None
    ):
        raise UpdaterV2Error("usb_public_fingerprint_invalid")
    validate_filesystem_uuid(filesystem_uuid)
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if capacity_report.measured_usable_bytes != measured_usable_bytes:
        raise UpdaterV2Error("ha_usb_measured_capacity_drift")
    return transition(
        current,
        U2,
        updates={
            "usb_device_identity_public_fingerprint": public_fingerprint,
            "usb_filesystem_uuid": filesystem_uuid,
            "usb_measured_usable_bytes": measured_usable_bytes,
            "usb_mount_authority": f"observed_filesystem_uuid:{filesystem_uuid}",
            "usb_capacity_verified": True,
        },
    )


def start_target_preparation(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U2:
        raise UpdaterV2Error("ha_usb_target_prepare_phase_invalid")
    return transition(current, U3)


def record_target_ready(
    document: dict[str, Any],
    *,
    target: ImageRecoveryRecord,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U3:
        raise UpdaterV2Error("ha_usb_target_ready_phase_invalid")
    validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    return transition(
        current,
        U4,
        updates={
            "target_artifact_verified": True,
            "target_artifact_identity": target.public(),
        },
    )


def start_predecessor_recovery(
    document: dict[str, Any],
    *,
    install_capacity: InstallCapacityRevalidation,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U5:
        raise UpdaterV2Error("ha_usb_predecessor_prepare_phase_invalid")
    validate_install_revalidation(
        install_capacity,
        expected_target_artifact_bytes=current["target_archive_size"],
    )
    return transition(current, U6)


def record_predecessor_recovery_and_ha_quiesced(
    document: dict[str, Any],
    *,
    predecessor: ImageRecoveryRecord,
    ha_quiesced: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U6:
        raise UpdaterV2Error("ha_usb_predecessor_ready_phase_invalid")
    validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    if ha_quiesced is not True:
        raise UpdaterV2Error("ha_usb_ha_not_quiesced")
    return transition(
        current,
        U7,
        updates={
            "predecessor_recovery_verified": True,
            "predecessor_recovery_identity": predecessor.public(),
        },
    )


def record_predecessor_capacity_released(
    document: dict[str, Any],
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U9 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_predecessor_release_not_allowed")
    return transition(current, U10)


def record_target_started(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U10 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_target_start_not_allowed")
    return transition(current, U11)


def record_target_accepted(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U11 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_target_accept_not_allowed")
    return transition(current, U12)


def record_commit(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U12 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_commit_not_allowed")
    return transition(current, U13A)


def record_rollback_complete(
    document: dict[str, Any],
    *,
    predecessor: ImageRecoveryRecord,
    backup: HaDataBackupRecord,
    observed_recovery_content_manifest_sha256: str,
    predecessor_image_restored: bool,
    ha_data_backup_restored: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] not in {U9, U10, U11, U12}:
        raise UpdaterV2Error("ha_usb_rollback_phase_invalid")
    expected_manifest = current["recovery_content_manifest_sha256"]
    if (
        observed_recovery_content_manifest_sha256 != expected_manifest
        or compute_recovery_content_manifest_sha256(current) != expected_manifest
    ):
        raise UpdaterV2Error("ha_usb_recovery_content_manifest_mismatch")
    validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    validate_backup_record(backup)
    if predecessor.public() != current["predecessor_recovery_identity"]:
        raise UpdaterV2Error("ha_usb_rollback_predecessor_identity_mismatch")
    if backup.public() != current["ha_data_backup_identity"]:
        raise UpdaterV2Error("ha_usb_rollback_backup_identity_mismatch")
    if predecessor_image_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_predecessor_not_restored")
    if ha_data_backup_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_data_not_restored")
    return transition(current, U13B)


def classify_power_loss_reentry(
    document: dict[str, Any],
    *,
    recovery_media_present: bool,
    exact_recovery_content_verified: bool,
) -> str:
    current = validate_transaction_document(document)
    if current["phase"] in {U13A, U13B}:
        return "TERMINAL"

    if PHASE_INDEX[current["phase"]] < PHASE_INDEX[U9]:
        return "PRE_U9_PREDECESSOR_AUTHORITY"

    if (
        recovery_media_present is not True
        or exact_recovery_content_verified is not True
    ):
        return "RECOVERY_MEDIA_REQUIRED"
    if current["phase"] == U12:
        return "FORWARD_COMMIT_ELIGIBLE"
    return "ROLLBACK_REQUIRED"


def request_target_reprepare(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U4:
        raise UpdaterV2Error("ha_usb_target_reprepare_phase_invalid")
    return transition(
        current,
        U3,
        updates={
            "target_artifact_verified": False,
            "target_artifact_identity": None,
        },
    )


def request_install(
    document: dict[str, Any],
    *,
    target: ImageRecoveryRecord,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U4:
        raise UpdaterV2Error("ha_usb_not_ready_to_install")
    validated_target = validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    if validated_target.archive_size_bytes != current["target_archive_size"]:
        raise UpdaterV2Error("ha_usb_target_archive_size_mismatch")
    result = transition(
        current,
        U5,
        updates={
            "target_artifact_verified": True,
            "target_artifact_identity": validated_target.public(),
        },
    )
    if (
        result["authorization_claimed"] is not False
        or result["authorization_consumed"] is not False
        or result["authorization_id_sha256"] is not None
    ):
        raise UpdaterV2Error("ha_usb_install_intent_consumed_authorization")
    return result


def record_recovery_admission(
    document: dict[str, Any],
    *,
    target: ImageRecoveryRecord,
    predecessor: ImageRecoveryRecord,
    backup: HaDataBackupRecord,
    capacity_report: UsbCapacityReport,
    recovery_capacity: RecoveryAdmissionCapacity,
    production_prestate_exact: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U7:
        raise UpdaterV2Error("ha_usb_recovery_admission_phase_invalid")
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if production_prestate_exact is not True:
        raise UpdaterV2Error("ha_usb_production_prestate_drift")

    validated_target = validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    validated_predecessor = validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    validated_backup = validate_backup_record(backup)
    if validated_target.public() != current["target_artifact_identity"]:
        raise UpdaterV2Error("ha_usb_target_identity_drift")
    if validated_predecessor.public() != current["predecessor_recovery_identity"]:
        raise UpdaterV2Error("ha_usb_predecessor_identity_drift")
    validate_recovery_admission_capacity(
        recovery_capacity,
        target_archive_bytes=target.archive_size_bytes,
        predecessor_archive_bytes=predecessor.archive_size_bytes,
        ha_backup_archive_bytes=backup.archive_size_bytes,
    )

    if current["target_artifact_verified"] is not True:
        raise UpdaterV2Error("ha_usb_target_not_verified")

    updates = {
        "predecessor_recovery_verified": True,
        "ha_data_backup_verified": True,
        "ha_data_backup_identity": validated_backup.public(),
        "production_prestate_verified": True,
        "usb_capacity_verified": True,
    }
    manifest_source = dict(current)
    manifest_source.update(updates)
    updates["recovery_content_manifest_sha256"] = (
        compute_recovery_content_manifest_sha256(manifest_source)
    )
    return transition(current, U8, updates=updates)


def claim_live_authorization(
    document: dict[str, Any],
    authorization_id: str,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U8:
        raise UpdaterV2Error("ha_usb_live_authorization_phase_invalid")
    if (
        current["authorization_claimed"] is not False
        or current["authorization_consumed"] is not False
        or current["authorization_id_sha256"] is not None
    ):
        raise UpdaterV2Error("ha_usb_live_authorization_already_claimed")
    if (
        not isinstance(authorization_id, str)
        or AUTHORIZATION_ID.fullmatch(authorization_id) is None
    ):
        raise UpdaterV2Error("ha_usb_live_authorization_id_invalid")

    return transition(
        current,
        U9,
        updates={
            "authorization_id_sha256": sha256_bytes(
                authorization_id.encode("utf-8")
            ),
            "authorization_claimed": True,
            "authorization_consumed": True,
        },
    )


def destructive_cutover_allowed(document: dict[str, Any]) -> bool:
    current = validate_transaction_document(document)
    return (
        current["status"] == "ACTIVE"
        and current["phase"] in {U9, U10, U11, U12}
        and current["authorization_claimed"] is True
        and current["authorization_consumed"] is True
        and current["target_artifact_verified"] is True
        and current["predecessor_recovery_verified"] is True
        and current["ha_data_backup_verified"] is True
        and current["production_prestate_verified"] is True
        and current["usb_capacity_verified"] is True
    )
