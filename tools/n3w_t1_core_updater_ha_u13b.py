from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from n3w_t1_core_updater_ha_backup import (
    HaDataBackupProvider,
    HaDataBackupRecord,
    backup_record_from_document,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb import (
    record_rollback_complete,
    record_rollback_ha_data_restored,
    record_rollback_predecessor_image_restored,
    record_rollback_predecessor_runtime_started,
    record_rollback_target_cleanup,
    start_rollback,
)
from n3w_t1_core_updater_ha_usb_state import (
    U13A,
    U13B0,
    U13B1,
    U13B2,
    U13B3,
    U13B4,
    U13B,
    U13B_ENTRY_PHASES,
    U13B_PROGRESS_PHASES,
    HaUsbStateStore,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


@dataclass(frozen=True, slots=True)
class U13BTargetCleanupEvidence:
    services_quiesced: bool
    target_runtime_absent: bool
    target_image_absent: bool

    def validate(self) -> "U13BTargetCleanupEvidence":
        if any(
            value is not True
            for value in (
                self.services_quiesced,
                self.target_runtime_absent,
                self.target_image_absent,
            )
        ):
            raise UpdaterV2Error("u13b_target_cleanup_evidence_invalid")
        return self


@dataclass(frozen=True, slots=True)
class U13BPredecessorImageEvidence:
    predecessor_image_exact_present: bool

    def validate(self) -> "U13BPredecessorImageEvidence":
        if self.predecessor_image_exact_present is not True:
            raise UpdaterV2Error("u13b_predecessor_image_evidence_invalid")
        return self


@dataclass(frozen=True, slots=True)
class U13BRuntimeEvidence:
    predecessor_runtime_started: bool
    production_config_mounted: bool
    manager_running: bool
    broker_running: bool
    homeassistant_running: bool

    def validate(self) -> "U13BRuntimeEvidence":
        if any(
            value is not True
            for value in (
                self.predecessor_runtime_started,
                self.production_config_mounted,
                self.manager_running,
                self.broker_running,
                self.homeassistant_running,
            )
        ):
            raise UpdaterV2Error("u13b_runtime_evidence_invalid")
        return self


@dataclass(frozen=True, slots=True)
class U13BHealthEvidence:
    predecessor_health_verified: bool
    manager_mqtt_authenticated: bool
    homeassistant_mqtt_authenticated: bool
    homeassistant_http_ready: bool

    def validate(self) -> "U13BHealthEvidence":
        if any(
            value is not True
            for value in (
                self.predecessor_health_verified,
                self.manager_mqtt_authenticated,
                self.homeassistant_mqtt_authenticated,
                self.homeassistant_http_ready,
            )
        ):
            raise UpdaterV2Error("u13b_health_evidence_invalid")
        return self


class U13BBackend(Protocol):
    def resolve_transaction_media(
        self,
        transaction: Mapping[str, Any],
        *,
        write_required: bool,
    ) -> PreparedUsbMedia | None:
        ...

    def verify_recovery_target(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        ...

    def verify_recovery_predecessor(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        ...

    def sync_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> None:
        ...


class U13BRuntimeOwner(Protocol):
    def cleanup_failed_target(
        self,
        *,
        transaction: Mapping[str, Any],
        target: ImageRecoveryRecord,
    ) -> U13BTargetCleanupEvidence:
        ...

    def restore_predecessor_image(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
        predecessor: ImageRecoveryRecord,
    ) -> U13BPredecessorImageEvidence:
        ...

    def start_predecessor_runtime(
        self,
        *,
        transaction: Mapping[str, Any],
        predecessor: ImageRecoveryRecord,
    ) -> U13BRuntimeEvidence:
        ...

    def verify_predecessor_health(
        self,
        *,
        transaction: Mapping[str, Any],
        predecessor: ImageRecoveryRecord,
    ) -> U13BHealthEvidence:
        ...


@dataclass(frozen=True, slots=True)
class U13BRollbackResult:
    transaction: dict[str, Any]
    initial_phase: str
    completed: bool


class HaUsbU13BRollbackController:
    """U13B operation-resume controller; USB/host split-brain is Stage C."""

    def __init__(
        self,
        *,
        transaction_store: HaUsbStateStore,
        backend: U13BBackend,
        runtime_owner: U13BRuntimeOwner,
        backup_provider: HaDataBackupProvider,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend
        self.runtime_owner = runtime_owner
        self.backup_provider = backup_provider

    def _transaction(self) -> dict[str, Any]:
        document = self.transaction_store.read()
        if document is None:
            raise UpdaterV2Error("u13b_transaction_missing")
        return validate_transaction_document(document)

    def _persist(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> dict[str, Any]:
        validated = validate_transaction_document(transaction)
        self.backend.sync_transaction_metadata(validated, media)
        self.transaction_store.write(validated)
        return validated

    def _authorities(
        self,
        transaction: dict[str, Any],
        media: PreparedUsbMedia,
    ) -> tuple[ImageRecoveryRecord, ImageRecoveryRecord, HaDataBackupRecord]:
        target = validate_image_recovery_record(
            self.backend.verify_recovery_target(
                transaction=transaction,
                media=media,
            ),
            expected_kind="target",
            expected_image_ref=transaction["target_image_ref"],
            expected_archive_sha256=transaction["target_archive_sha256"],
        )
        if target.public() != transaction.get("target_artifact_identity"):
            raise UpdaterV2Error("u13b_target_recovery_identity_drift")

        predecessor = validate_image_recovery_record(
            self.backend.verify_recovery_predecessor(
                transaction=transaction,
                media=media,
            ),
            expected_kind="predecessor",
            expected_image_ref=transaction["current_image_ref"],
        )
        if predecessor.public() != transaction.get(
            "predecessor_recovery_identity"
        ):
            raise UpdaterV2Error("u13b_predecessor_recovery_identity_drift")

        backup = backup_record_from_document(
            transaction.get("ha_data_backup_identity")
        )
        source_root = Path(media.mount_path) / "n3w-update" / "ha-data"
        verified = self.backup_provider.verify_backup(
            backup,
            transaction_id_sha256=transaction["transaction_id_sha256"],
            destination_root=source_root,
        )
        if verified.public() != backup.public():
            raise UpdaterV2Error("u13b_backup_identity_drift")
        return target, predecessor, verified

    def rollback(self, *, failure_code: str) -> U13BRollbackResult:
        current = self._transaction()
        initial_phase = current["phase"]
        if current["phase"] == U13A:
            raise UpdaterV2Error("u13b_committed_transaction_terminal")
        if current["phase"] == U13B:
            return U13BRollbackResult(current, initial_phase, True)
        if (
            current["phase"] not in U13B_ENTRY_PHASES
            and current["phase"] not in U13B_PROGRESS_PHASES
        ):
            raise UpdaterV2Error("u13b_phase_invalid")

        media = self.backend.resolve_transaction_media(
            current,
            write_required=True,
        )
        if media is None:
            raise UpdaterV2Error("usb_transaction_media_unavailable")
        target, predecessor, backup = self._authorities(current, media)

        if current["phase"] in U13B_ENTRY_PHASES:
            current = self._persist(
                start_rollback(
                    current,
                    failure_code=failure_code,
                    target=target,
                    predecessor=predecessor,
                    backup=backup,
                ),
                media,
            )

        if current["phase"] == U13B0:
            evidence = self.runtime_owner.cleanup_failed_target(
                transaction=current,
                target=target,
            ).validate()
            current = self._persist(
                record_rollback_target_cleanup(
                    current,
                    services_quiesced=evidence.services_quiesced,
                    target_runtime_absent=evidence.target_runtime_absent,
                    target_image_absent=evidence.target_image_absent,
                ),
                media,
            )

        if current["phase"] == U13B1:
            evidence = self.runtime_owner.restore_predecessor_image(
                transaction=current,
                media=media,
                predecessor=predecessor,
            ).validate()
            current = self._persist(
                record_rollback_predecessor_image_restored(
                    current,
                    predecessor=predecessor,
                    predecessor_image_exact_present=(
                        evidence.predecessor_image_exact_present
                    ),
                ),
                media,
            )

        if current["phase"] == U13B2:
            source_root = Path(media.mount_path) / "n3w-update" / "ha-data"
            restored = self.backup_provider.restore_preupgrade_backup(
                backup,
                transaction_id_sha256=current["transaction_id_sha256"],
                source_root=source_root,
            )
            if restored.public() != backup.public():
                raise UpdaterV2Error("u13b_backup_restore_identity_drift")
            current = self._persist(
                record_rollback_ha_data_restored(
                    current,
                    backup=restored,
                    ha_data_backup_restored=True,
                ),
                media,
            )

        if current["phase"] == U13B3:
            evidence = self.runtime_owner.start_predecessor_runtime(
                transaction=current,
                predecessor=predecessor,
            ).validate()
            current = self._persist(
                record_rollback_predecessor_runtime_started(
                    current,
                    predecessor_runtime_started=(
                        evidence.predecessor_runtime_started
                    ),
                    production_config_mounted=(
                        evidence.production_config_mounted
                    ),
                    manager_running=evidence.manager_running,
                    broker_running=evidence.broker_running,
                    homeassistant_running=evidence.homeassistant_running,
                ),
                media,
            )

        if current["phase"] == U13B4:
            evidence = self.runtime_owner.verify_predecessor_health(
                transaction=current,
                predecessor=predecessor,
            ).validate()
            current = self._persist(
                record_rollback_complete(
                    current,
                    predecessor_health_verified=(
                        evidence.predecessor_health_verified
                    ),
                    manager_mqtt_authenticated=(
                        evidence.manager_mqtt_authenticated
                    ),
                    homeassistant_mqtt_authenticated=(
                        evidence.homeassistant_mqtt_authenticated
                    ),
                    homeassistant_http_ready=evidence.homeassistant_http_ready,
                ),
                media,
            )

        if current["phase"] != U13B:
            raise UpdaterV2Error("u13b_terminal_phase_not_reached")
        return U13BRollbackResult(current, initial_phase, True)
