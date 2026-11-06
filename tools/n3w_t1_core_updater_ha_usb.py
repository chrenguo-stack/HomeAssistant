from __future__ import annotations

from typing import Any

from n3w_t1_core_updater_ha_backup import (
    HaDataBackupRecord,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb_state import (
    U4,
    U5,
    U7,
    U8,
    U9,
    U10,
    U11,
    U12,
    transition,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import (
    AUTHORIZATION_ID,
    UpdaterV2Error,
    sha256_bytes,
)


def request_install(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U4:
        raise UpdaterV2Error("ha_usb_not_ready_to_install")
    result = transition(current, U5)
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
    same_bound_usb_uuid: bool,
    capacity_pass: bool,
    production_prestate_exact: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U7:
        raise UpdaterV2Error("ha_usb_recovery_admission_phase_invalid")
    if same_bound_usb_uuid is not True:
        raise UpdaterV2Error("usb_filesystem_uuid_mismatch")
    if capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if production_prestate_exact is not True:
        raise UpdaterV2Error("ha_usb_production_prestate_drift")

    validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    validate_backup_record(backup)

    if current["target_artifact_verified"] is not True:
        raise UpdaterV2Error("ha_usb_target_not_verified")

    return transition(
        current,
        U8,
        updates={
            "predecessor_recovery_verified": True,
            "ha_data_backup_verified": True,
            "production_prestate_verified": True,
            "usb_capacity_verified": True,
        },
    )


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
