from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from n3w_t1_core_updater_ha_backup import (
    BackupProgress,
    HaDataBackupProvider,
    HaDataBackupRecord,
    HaQuiesceEvidence,
)
from n3w_t1_core_updater_ha_capacity import (
    InstallCapacityRevalidation,
    validate_install_revalidation,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb import (
    clear_u7_backup_evidence_for_recreate,
    record_ha_data_backup_verified,
    record_predecessor_recovery_and_ha_quiesced,
    start_predecessor_recovery,
)
from n3w_t1_core_updater_ha_usb_state import (
    U5,
    U6,
    U7,
    HaUsbStateStore,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


class U6PredecessorBackend(Protocol):
    def resolve_transaction_media(
        self,
        transaction: dict[str, object],
        *,
        write_required: bool,
    ) -> PreparedUsbMedia | None:
        ...

    def verify_prepared_target(
        self,
        *,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        ...

    def install_capacity_revalidation(
        self,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> InstallCapacityRevalidation:
        ...

    def sync_transaction_metadata(
        self,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> None:
        ...

    def prepare_predecessor_recovery(
        self,
        *,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        ...

    def verify_prepared_predecessor(
        self,
        *,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        ...


@dataclass(frozen=True, slots=True)
class U6PredecessorPreparationResult:
    transaction: dict[str, object]
    predecessor: ImageRecoveryRecord
    resumed_from_u6: bool


class HaUsbU6PredecessorController:
    """Bound U5->U6 predecessor-recovery preparation.

    This controller never quiesces Home Assistant, never enters U7, and never
    claims the U9 live authorization. U6 is made durable before predecessor
    export so an interrupted export is resumed from an explicit U6 state.
    """

    def __init__(
        self,
        *,
        transaction_store: HaUsbStateStore,
        backend: U6PredecessorBackend,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend

    def _transaction(self) -> dict[str, object]:
        document = self.transaction_store.read()
        if document is None:
            raise UpdaterV2Error("ha_usb_transaction_missing")
        return validate_transaction_document(document)

    @staticmethod
    def _require_pre_u9_authorization_state(
        transaction: dict[str, object],
    ) -> None:
        if (
            transaction.get("authorization_claimed") is not False
            or transaction.get("authorization_consumed") is not False
            or transaction.get("authorization_id_sha256") is not None
        ):
            raise UpdaterV2Error("ha_usb_u6_authorization_state_invalid")

    def prepare_or_resume(self) -> U6PredecessorPreparationResult:
        current = self._transaction()
        if current["phase"] not in {U5, U6}:
            raise UpdaterV2Error("ha_usb_u6_prepare_phase_invalid")
        self._require_pre_u9_authorization_state(current)

        media = self.backend.resolve_transaction_media(
            current,
            write_required=True,
        )
        if media is None:
            raise UpdaterV2Error("usb_transaction_media_unavailable")

        target = validate_image_recovery_record(
            self.backend.verify_prepared_target(
                transaction=current,
                media=media,
            ),
            expected_kind="target",
            expected_image_ref=current["target_image_ref"],
            expected_archive_sha256=current["target_archive_sha256"],
        )
        if target.public() != current.get("target_artifact_identity"):
            raise UpdaterV2Error("ha_usb_target_identity_drift")

        install_capacity = self.backend.install_capacity_revalidation(
            current,
            media,
        )
        validate_install_revalidation(
            install_capacity,
            expected_target_artifact_bytes=current["target_archive_size"],
        )

        resumed = current["phase"] == U6
        if not resumed:
            current = start_predecessor_recovery(
                current,
                install_capacity=install_capacity,
            )
            self.backend.sync_transaction_metadata(current, media)
            self.transaction_store.write(current)

        predecessor = validate_image_recovery_record(
            self.backend.prepare_predecessor_recovery(
                transaction=current,
                media=media,
            ),
            expected_kind="predecessor",
            expected_image_ref=current["current_image_ref"],
        )
        verified = validate_image_recovery_record(
            self.backend.verify_prepared_predecessor(
                transaction=current,
                media=media,
            ),
            expected_kind="predecessor",
            expected_image_ref=current["current_image_ref"],
        )
        if verified.public() != predecessor.public():
            raise UpdaterV2Error("ha_usb_predecessor_identity_drift")

        return U6PredecessorPreparationResult(
            transaction=current,
            predecessor=verified,
            resumed_from_u6=resumed,
        )


class U7RuntimeOwner(Protocol):
    def quiesce_homeassistant_for_backup(
        self,
    ) -> HaQuiesceEvidence | Mapping[str, bool]:
        ...

    def resume_homeassistant_after_backup_failure(self) -> None:
        ...


@dataclass(frozen=True, slots=True)
class U7BackupPreparationResult:
    transaction: dict[str, object]
    backup: HaDataBackupRecord
    resumed_from_u7: bool
    services_left_quiesced: bool


class HaUsbU7BackupController:
    """Prepare a protected backup and stop durably in U7."""

    def __init__(
        self,
        *,
        transaction_store: HaUsbStateStore,
        backend: U6PredecessorBackend,
        runtime_owner: U7RuntimeOwner,
        backup_provider: HaDataBackupProvider,
        progress: BackupProgress | None = None,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend
        self.runtime_owner = runtime_owner
        self.backup_provider = backup_provider
        self.progress = progress

    def _report(self, phase: str, value: int = 0) -> None:
        if self.progress is not None:
            self.progress(phase, value)

    def _transaction(self) -> dict[str, object]:
        document = self.transaction_store.read()
        if document is None:
            raise UpdaterV2Error("ha_usb_transaction_missing")
        return validate_transaction_document(document)

    @staticmethod
    def _require_pre_u9_authorization_state(
        transaction: dict[str, object],
    ) -> None:
        if (
            transaction.get("authorization_claimed") is not False
            or transaction.get("authorization_consumed") is not False
            or transaction.get("authorization_id_sha256") is not None
        ):
            raise UpdaterV2Error(
                "ha_usb_u7_authorization_state_invalid"
            )

    @staticmethod
    def _quiesce_evidence(
        value: HaQuiesceEvidence | Mapping[str, bool],
    ) -> HaQuiesceEvidence:
        if isinstance(value, HaQuiesceEvidence):
            return value.validate()
        if not isinstance(value, Mapping):
            raise UpdaterV2Error("ha_backup_quiesce_evidence_invalid")
        expected = {
            "owner_inactive",
            "homeassistant_stopped",
            "manager_stopped",
            "broker_preserved",
        }
        if set(value) != expected:
            raise UpdaterV2Error("ha_backup_quiesce_evidence_invalid")
        try:
            evidence = HaQuiesceEvidence(
                owner_inactive=value["owner_inactive"],
                homeassistant_stopped=value["homeassistant_stopped"],
                manager_stopped=value["manager_stopped"],
                broker_preserved=value["broker_preserved"],
            )
        except (KeyError, TypeError) as error:
            raise UpdaterV2Error(
                "ha_backup_quiesce_evidence_invalid"
            ) from error
        return evidence.validate()

    def prepare_or_resume(self) -> U7BackupPreparationResult:
        current = self._transaction()
        if current["phase"] not in {U6, U7}:
            raise UpdaterV2Error("ha_usb_u7_prepare_phase_invalid")
        self._require_pre_u9_authorization_state(current)
        resumed = current["phase"] == U7

        self._report("u7_media_reopen")
        media = self.backend.resolve_transaction_media(
            current,
            write_required=True,
        )
        if media is None:
            raise UpdaterV2Error("usb_transaction_media_unavailable")

        target = validate_image_recovery_record(
            self.backend.verify_prepared_target(
                transaction=current,
                media=media,
            ),
            expected_kind="target",
            expected_image_ref=current["target_image_ref"],
            expected_archive_sha256=current["target_archive_sha256"],
        )
        if target.public() != current.get("target_artifact_identity"):
            raise UpdaterV2Error("ha_usb_target_identity_drift")

        predecessor = validate_image_recovery_record(
            self.backend.verify_prepared_predecessor(
                transaction=current,
                media=media,
            ),
            expected_kind="predecessor",
            expected_image_ref=current["current_image_ref"],
        )
        if resumed and predecessor.public() != current.get(
            "predecessor_recovery_identity"
        ):
            raise UpdaterV2Error("ha_usb_predecessor_identity_drift")

        if resumed and (
            current.get("ha_data_backup_verified") is True
            or current.get("ha_data_backup_identity") is not None
        ):
            self._report("u7_backup_evidence_invalidate")
            current = clear_u7_backup_evidence_for_recreate(current)
            self.backend.sync_transaction_metadata(current, media)
            self.transaction_store.write(current)

        self._report("u7_quiesce")
        try:
            evidence = self._quiesce_evidence(
                self.runtime_owner.quiesce_homeassistant_for_backup()
            )
            if not resumed:
                current = record_predecessor_recovery_and_ha_quiesced(
                    current,
                    predecessor=predecessor,
                    ha_quiesced=True,
                )
                self.backend.sync_transaction_metadata(current, media)
                self.transaction_store.write(current)
            elif current.get("predecessor_recovery_verified") is not True:
                raise UpdaterV2Error(
                    "ha_usb_predecessor_not_verified"
                )

            self._report("u7_backup_create")
            destination_root = (
                Path(media.mount_path) / "n3w-update" / "ha-data"
            )
            backup = self.backup_provider.create_consistent_backup(
                transaction_id_sha256=current["transaction_id_sha256"],
                destination_root=destination_root,
            )
            self._report("u7_backup_verify")
            verified = self.backup_provider.verify_backup(
                backup,
                transaction_id_sha256=current["transaction_id_sha256"],
                destination_root=destination_root,
            )
            if verified.public() != backup.public():
                raise UpdaterV2Error("ha_data_backup_identity_drift")

            current = record_ha_data_backup_verified(
                current,
                backup=verified,
            )
            self.backend.sync_transaction_metadata(current, media)
            self.transaction_store.write(current)
            self._report("u7_stop", verified.archive_size_bytes)
            return U7BackupPreparationResult(
                transaction=current,
                backup=verified,
                resumed_from_u7=resumed,
                services_left_quiesced=True,
            )
        except Exception as error:
            self._report("u7_failure_recovery")
            try:
                self.runtime_owner.resume_homeassistant_after_backup_failure()
            except Exception as recovery_error:
                raise UpdaterV2Error(
                    "ha_usb_u7_failure_recovery_failed"
                ) from recovery_error
            raise error
