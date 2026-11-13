from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from n3w_t1_core_updater_ha_capacity import (
    InstallCapacityRevalidation,
    validate_install_revalidation,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb import start_predecessor_recovery
from n3w_t1_core_updater_ha_usb_state import (
    U5,
    U6,
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
