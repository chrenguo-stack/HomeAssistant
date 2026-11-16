from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb import record_target_started
from n3w_t1_core_updater_ha_usb_state import (
    U10,
    HaUsbStateStore,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


TARGET_ARCHIVE_RELATIVE = (
    Path("n3w-update")
    / "target"
    / "homeassistant-arm64.tar.gz"
)


class U11Backend(Protocol):
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

    def sync_transaction_metadata(
        self,
        transaction: dict[str, object],
        media: PreparedUsbMedia,
    ) -> None:
        ...


@dataclass(frozen=True, slots=True)
class U11RuntimeEvidence:
    owner_active: bool
    manager_running: bool
    broker_running: bool
    homeassistant_running: bool
    target_image_ref: str
    target_runtime_image_id: str
    production_config_mounted: bool

    def validate(
        self,
        *,
        expected_target_image_ref: str,
        expected_target_runtime_image_id: str,
    ) -> "U11RuntimeEvidence":
        if (
            self.owner_active is not True
            or self.manager_running is not True
            or self.broker_running is not True
            or self.homeassistant_running is not True
            or self.production_config_mounted is not True
        ):
            raise UpdaterV2Error("ha_usb_u11_runtime_not_started")
        if self.target_image_ref != expected_target_image_ref:
            raise UpdaterV2Error("ha_usb_u11_target_runtime_ref_drift")
        if self.target_runtime_image_id != expected_target_runtime_image_id:
            raise UpdaterV2Error("ha_usb_u11_target_runtime_id_drift")
        return self


class U11RuntimeOwner(Protocol):
    def target_image_id(self, image_ref: str) -> str | None:
        ...

    def homeassistant_binding(self) -> str:
        ...

    def load_target_archive(self, archive: Path) -> None:
        ...

    def verify_loaded_target(
        self,
        *,
        image_ref: str,
        archive: Path,
        expected_archive_sha256: str,
    ) -> str:
        ...

    def publish_homeassistant_target_binding(
        self,
        *,
        expected_predecessor: str,
        target: str,
    ) -> None:
        ...

    def start_target_owner(
        self,
        *,
        target_image_ref: str,
        target_runtime_image_id: str,
    ) -> U11RuntimeEvidence:
        ...


@dataclass(frozen=True, slots=True)
class U11TargetInstallResult:
    transaction: dict[str, object]
    target_runtime_image_id: str
    runtime: U11RuntimeEvidence
    target_archive: Path


class U11PartialMutationError(UpdaterV2Error):
    def __init__(self, stage: str, cause: BaseException) -> None:
        super().__init__(
            "ha_usb_u11_partial_mutation_requires_recovery:"
            + stage
            + ":"
            + type(cause).__name__
        )
        self.stage = stage


class HaUsbU11TargetInstallController:
    """Install/start the exact USB target and durably enter U11.

    This controller owns only U10 -> U11. It intentionally does not perform
    U12 health acceptance and it never retries after a mutation has begun.
    """

    def __init__(
        self,
        *,
        transaction_store: HaUsbStateStore,
        backend: U11Backend,
        runtime_owner: U11RuntimeOwner,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend
        self.runtime_owner = runtime_owner

    def _transaction(self) -> dict[str, object]:
        document = self.transaction_store.read()
        if document is None:
            raise UpdaterV2Error("ha_usb_transaction_missing")
        current = validate_transaction_document(document)
        if current["phase"] != U10:
            raise UpdaterV2Error("ha_usb_u11_install_phase_invalid")
        if (
            current.get("authorization_claimed") is not True
            or current.get("authorization_consumed") is not True
        ):
            raise UpdaterV2Error("ha_usb_u11_authorization_state_invalid")
        return current

    @staticmethod
    def _target_archive(media: PreparedUsbMedia) -> Path:
        root = Path(media.mount_path)
        if root.is_symlink() or not root.is_dir():
            raise UpdaterV2Error("ha_usb_u11_mount_invalid")
        archive = root / TARGET_ARCHIVE_RELATIVE
        if archive.is_symlink() or not archive.is_file():
            raise UpdaterV2Error("ha_usb_u11_target_archive_invalid")
        return archive

    def install(self) -> U11TargetInstallResult:
        current = self._transaction()

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
            expected_image_ref=str(current["target_image_ref"]),
            expected_archive_sha256=str(current["target_archive_sha256"]),
        )
        if target.public() != current.get("target_artifact_identity"):
            raise UpdaterV2Error("ha_usb_u11_target_identity_drift")

        target_ref = str(current["target_image_ref"])
        predecessor_ref = str(current["current_image_ref"])
        if self.runtime_owner.target_image_id(target_ref) is not None:
            raise UpdaterV2Error("ha_usb_u11_target_preexisting")
        if self.runtime_owner.homeassistant_binding() != predecessor_ref:
            raise UpdaterV2Error("ha_usb_u11_binding_prestate_drift")

        archive = self._target_archive(media)
        mutation_stage: str | None = None
        try:
            mutation_stage = "target_load"
            self.runtime_owner.load_target_archive(archive)

            runtime_id = self.runtime_owner.verify_loaded_target(
                image_ref=target_ref,
                archive=archive,
                expected_archive_sha256=target.archive_sha256,
            )

            mutation_stage = "binding_publish"
            self.runtime_owner.publish_homeassistant_target_binding(
                expected_predecessor=predecessor_ref,
                target=target_ref,
            )
            if self.runtime_owner.homeassistant_binding() != target_ref:
                raise UpdaterV2Error("ha_usb_u11_binding_publish_drift")

            mutation_stage = "target_owner_start"
            runtime = self.runtime_owner.start_target_owner(
                target_image_ref=target_ref,
                target_runtime_image_id=runtime_id,
            ).validate(
                expected_target_image_ref=target_ref,
                expected_target_runtime_image_id=runtime_id,
            )

            next_transaction = record_target_started(current)

            mutation_stage = "usb_u11_persist"
            self.backend.sync_transaction_metadata(
                next_transaction,
                media,
            )

            mutation_stage = "host_u11_persist"
            self.transaction_store.write(next_transaction)

            return U11TargetInstallResult(
                transaction=next_transaction,
                target_runtime_image_id=runtime_id,
                runtime=runtime,
                target_archive=archive,
            )
        except Exception as error:
            if mutation_stage is None:
                raise
            raise U11PartialMutationError(
                mutation_stage,
                error,
            ) from error
