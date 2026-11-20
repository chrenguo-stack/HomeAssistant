from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

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
    require_same_filesystem_uuid,
)
from n3w_t1_core_updater_ha_usb_state import (
    HA_USB_TERMINAL_STATUSES,
    PHASE_INDEX,
    PRE_CUTOVER_RECOVERY_PHASES,
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
    HaUsbStateStore,
    transition,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import (
    AUTHORIZATION_ID,
    UpdaterV2Error,
    sha256_bytes,
)


class HaPredecessorRuntime(Protocol):
    def capture_start_binding(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Verify the running predecessor and bind its fixed local start configuration."""
        ...

    def quiesce_for_backup(self) -> None:
        """Stop application writers and verify they are quiescent."""
        ...

    def start_predecessor_if_needed(self, binding: dict[str, Any]) -> None:
        """Check the binding against the host, then start only missing services."""
        ...

    def verify_predecessor_health(self, binding: dict[str, Any]) -> None:
        """Verify the old combination and its affected functions have recovered."""
        ...


class HaPredecessorRecovery:
    """Host recovery point for interruptions before destructive HA cutover."""

    def __init__(self, store: HaUsbStateStore, runtime: HaPredecessorRuntime):
        self.store = store
        self.runtime = runtime

    @contextmanager
    def quiesced_for_backup(
        self, predecessor: ImageRecoveryRecord
    ) -> Iterator[dict[str, Any]]:
        """Keep the shared execution lock held while the caller backs up data."""
        with self.store.lock():
            current = self.store.read()
            if (
                current is None
                or current["phase"] != U6
                or current["status"] != "ACTIVE"
                or "predecessor_start" in current
                or current["recovery_required"]
            ):
                raise UpdaterV2Error("ha_usb_first_stop_not_admitted")
            validate_image_recovery_record(
                predecessor,
                expected_kind="predecessor",
                expected_image_ref=current["current_image_ref"],
            )
            source_identity = current["current_image_identity"].get(
                "portable_identity_sha256"
            )
            if (
                source_identity is not None
                and predecessor.portable_identity_sha256 != source_identity
            ):
                raise UpdaterV2Error("ha_usb_predecessor_archive_identity_drift")

            binding = self.runtime.capture_start_binding(current)
            current = validate_transaction_document(
                {
                    **current,
                    "predecessor_start": binding,
                    "updated_at_unix": max(current["updated_at_unix"], int(time.time())),
                }
            )
            self.store.write(current)
            try:
                self.runtime.quiesce_for_backup()
                result = record_predecessor_recovery_and_ha_quiesced(
                    current,
                    predecessor=predecessor,
                    ha_quiesced=True,
                )
                self.store.write(result)
                yield result
            except Exception:
                latest = self.store.read()
                if latest is not None and self._is_recoverable(latest):
                    self._restore(latest)
                raise

    def recover(self) -> bool:
        """Re-enter after an interruption, independently of USB and IPC."""
        with self.store.lock():
            current = self.store.read()
            if current is None or not self._is_recoverable(current):
                return False
            self._restore(current)
            return True

    @staticmethod
    def _is_recoverable(document: dict[str, Any]) -> bool:
        return (
            document["phase"] in PRE_CUTOVER_RECOVERY_PHASES
            and document["status"] not in HA_USB_TERMINAL_STATUSES
            and "predecessor_start" in document
        )

    def _restore(self, current: dict[str, Any]) -> None:
        if not current["recovery_required"]:
            current = {**current, "recovery_required": True}
            self.store.write(current)
        binding = current["predecessor_start"]
        self.runtime.start_predecessor_if_needed(binding)
        self.runtime.verify_predecessor_health(binding)
        self.store.write(
            {
                **current,
                "status": "ROLLED_BACK",
                "recovery_required": False,
                "pre_cutover_predecessor_restored": True,
                "failure_code": "ha_usb_pre_cutover_interrupted",
                "updated_at_unix": max(current["updated_at_unix"], int(time.time())),
            }
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
        updates={"target_artifact_verified": True},
    )


def start_predecessor_recovery(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U5:
        raise UpdaterV2Error("ha_usb_predecessor_prepare_phase_invalid")
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
        updates={"predecessor_recovery_verified": True},
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
    observed_usb_filesystem_uuid: str,
    predecessor_image_restored: bool,
    ha_data_backup_restored: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] not in {U9, U10, U11, U12}:
        raise UpdaterV2Error("ha_usb_rollback_phase_invalid")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if predecessor_image_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_predecessor_not_restored")
    if ha_data_backup_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_data_not_restored")
    return transition(current, U13B)


def classify_power_loss_reentry(
    document: dict[str, Any],
    *,
    usb_present: bool,
    observed_usb_filesystem_uuid: str | None,
) -> str:
    current = validate_transaction_document(document)
    if current["status"] in HA_USB_TERMINAL_STATUSES:
        return "TERMINAL"

    if (
        current["phase"] in PRE_CUTOVER_RECOVERY_PHASES
        and "predecessor_start" in current
    ):
        return "RESTORE_PREDECESSOR_BEFORE_CUTOVER"

    if PHASE_INDEX[current["phase"]] < PHASE_INDEX[U9]:
        return "PRE_U9_PREDECESSOR_AUTHORITY"

    if usb_present is not True:
        return "RECOVERY_MEDIA_REQUIRED"
    if observed_usb_filesystem_uuid is None:
        raise UpdaterV2Error("ha_usb_recovery_uuid_missing")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if current["phase"] == U12:
        return "FORWARD_COMMIT_ELIGIBLE"
    return "ROLLBACK_REQUIRED"


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
    observed_usb_filesystem_uuid: str,
    capacity_report: UsbCapacityReport,
    production_prestate_exact: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U7:
        raise UpdaterV2Error("ha_usb_recovery_admission_phase_invalid")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if (
        capacity_report.measured_usable_bytes
        != current["usb_measured_usable_bytes"]
    ):
        raise UpdaterV2Error("ha_usb_measured_capacity_drift")
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
