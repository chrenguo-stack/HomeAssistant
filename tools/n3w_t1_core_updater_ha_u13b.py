from __future__ import annotations

import copy

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
    USB_TX_CHECKSUM_SCHEMA,
    USB_TX_CONTENT_AUTHORITY_SCHEMA,
    USB_TX_MANIFEST_SCHEMA,
    USB_TX_PHASE_SCHEMA,
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
from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error


HOST_USB_EXACT = "HOST_USB_EXACT"
USB_ONE_PHASE_AHEAD_RECONCILABLE = "USB_ONE_PHASE_AHEAD_RECONCILABLE"
HOST_ONE_PHASE_AHEAD_STOP = "HOST_ONE_PHASE_AHEAD_STOP"
DIVERGENT_OR_UNKNOWN_STOP = "DIVERGENT_OR_UNKNOWN_STOP"

_U13B_USB_SUCCESSOR = {phase: U13B0 for phase in U13B_ENTRY_PHASES}
_U13B_USB_SUCCESSOR.update({
    U13B0: U13B1,
    U13B1: U13B2,
    U13B2: U13B3,
    U13B3: U13B4,
    U13B4: U13B,
})
_U13B_RECONCILIATION_PHASES = frozenset(
    set(U13B_ENTRY_PHASES) | set(U13B_PROGRESS_PHASES) | {U13B}
)


@dataclass(frozen=True, slots=True)
class U13BUsbMetadataSnapshot:
    manifest: Mapping[str, Any]
    phase: Mapping[str, Any]
    checksums: Mapping[str, Any]
    content_authority: Mapping[str, Any]
    host_transaction: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class U13BSplitReconciliation:
    classification: str
    host_phase: str
    usb_phase: str | None
    reason: str


def _metadata_shape(
    document: Mapping[str, Any],
    expected_keys: frozenset[str],
    schema: str,
) -> bool:
    return (
        isinstance(document, Mapping)
        and frozenset(document) == expected_keys
        and document.get("schema") == schema
    )





def _mirrored_successor_exact(
    host: Mapping[str, Any],
    mirrored_transaction: Mapping[str, Any],
) -> bool:
    try:
        mirror = validate_transaction_document(dict(mirrored_transaction))
    except UpdaterV2Error:
        return False

    host_phase = host["phase"]
    successor = _U13B_USB_SUCCESSOR.get(host_phase)
    if successor is None or mirror["phase"] != successor:
        return False
    if mirror["transaction_id_sha256"] != host["transaction_id_sha256"]:
        return False

    mirrored_updated_at = mirror.get("updated_at_unix")
    if (
        type(mirrored_updated_at) is not int
        or mirrored_updated_at < int(host["updated_at_unix"])
    ):
        return False

    expected = copy.deepcopy(dict(host))
    expected["phase"] = successor
    expected["updated_at_unix"] = mirrored_updated_at

    if successor == U13B0:
        expected["failure_code"] = mirror.get("failure_code")
        expected["recovery_required"] = True
        expected["rollback_origin_phase"] = host_phase
        expected["rollback_recovery_content_verified"] = True
    elif successor == U13B1:
        expected["rollback_target_cleanup_verified"] = True
    elif successor == U13B2:
        expected["rollback_predecessor_image_restored"] = True
    elif successor == U13B3:
        expected["rollback_ha_data_restored"] = True
    elif successor == U13B4:
        expected["rollback_predecessor_runtime_started"] = True
    elif successor == U13B:
        expected["rollback_health_verified"] = True
        expected["status"] = "ROLLED_BACK"
        expected["recovery_required"] = False
    else:
        return False

    return mirror == expected

def classify_u13b_usb_host_split(
    host_transaction: Mapping[str, Any],
    media: PreparedUsbMedia,
    snapshot: U13BUsbMetadataSnapshot,
) -> U13BSplitReconciliation:
    host = validate_transaction_document(dict(host_transaction))
    media.validate()
    host_phase = host["phase"]

    def stop(reason: str, usb_phase: str | None = None) -> U13BSplitReconciliation:
        return U13BSplitReconciliation(
            DIVERGENT_OR_UNKNOWN_STOP, host_phase, usb_phase, reason
        )

    if host_phase not in _U13B_RECONCILIATION_PHASES:
        return stop("u13b_host_phase_outside_reconciliation_domain")
    if media.filesystem_uuid != host.get("usb_filesystem_uuid"):
        return stop("u13b_usb_filesystem_uuid_drift")

    manifest = snapshot.manifest
    phase = snapshot.phase
    checksums = snapshot.checksums
    authority = snapshot.content_authority
    if not _metadata_shape(
        manifest,
        frozenset({
            "schema", "transaction_id_sha256", "release_identity",
            "target_image_ref", "target_archive_sha256",
            "target_archive_size_bytes", "usb_filesystem_uuid",
            "usb_device_identity_public_fingerprint",
        }),
        USB_TX_MANIFEST_SCHEMA,
    ):
        return stop("u13b_usb_manifest_invalid")
    if not _metadata_shape(
        phase,
        frozenset({
            "schema", "transaction_id_sha256", "phase",
            "target_artifact_verified", "usb_capacity_verified",
        }),
        USB_TX_PHASE_SCHEMA,
    ):
        return stop("u13b_usb_phase_metadata_invalid")
    if not _metadata_shape(
        checksums,
        frozenset({"schema", "target_archive_sha256", "target_archive_size_bytes"}),
        USB_TX_CHECKSUM_SCHEMA,
    ):
        return stop("u13b_usb_checksums_invalid")
    if not _metadata_shape(
        authority,
        frozenset({
            "schema", "transaction_id_sha256", "release_identity",
            "target_artifact_identity", "predecessor_recovery_identity",
            "ha_data_backup_identity", "recovery_content_manifest_sha256",
        }),
        USB_TX_CONTENT_AUTHORITY_SCHEMA,
    ):
        return stop("u13b_usb_content_authority_invalid")

    transaction_id = host["transaction_id_sha256"]
    release = host["target_manifest_identity"].get("release_identity")
    usb_phase = phase.get("phase")
    fingerprint = manifest.get("usb_device_identity_public_fingerprint")
    authority_matches = (
        manifest.get("transaction_id_sha256") == transaction_id
        and phase.get("transaction_id_sha256") == transaction_id
        and authority.get("transaction_id_sha256") == transaction_id
        and manifest.get("release_identity") == release
        and authority.get("release_identity") == release
        and manifest.get("target_image_ref") == host["target_image_ref"]
        and manifest.get("target_archive_sha256") == host["target_archive_sha256"]
        and manifest.get("target_archive_size_bytes") == host["target_archive_size"]
        and manifest.get("usb_filesystem_uuid") == host["usb_filesystem_uuid"]
        and isinstance(fingerprint, str)
        and SHA256.fullmatch(fingerprint) is not None
        and phase.get("target_artifact_verified") is host.get("target_artifact_verified")
        and phase.get("usb_capacity_verified") is host.get("usb_capacity_verified")
        and checksums.get("target_archive_sha256") == host["target_archive_sha256"]
        and checksums.get("target_archive_size_bytes") == host["target_archive_size"]
        and authority.get("target_artifact_identity") == host.get("target_artifact_identity")
        and authority.get("predecessor_recovery_identity") == host.get("predecessor_recovery_identity")
        and authority.get("ha_data_backup_identity") == host.get("ha_data_backup_identity")
        and authority.get("recovery_content_manifest_sha256") == host.get("recovery_content_manifest_sha256")
    )
    if not authority_matches:
        return stop(
            "u13b_usb_transaction_or_recovery_authority_drift",
            usb_phase if isinstance(usb_phase, str) else None,
        )
    if usb_phase not in _U13B_RECONCILIATION_PHASES:
        return stop(
            "u13b_usb_phase_outside_reconciliation_domain",
            usb_phase if isinstance(usb_phase, str) else None,
        )
    if usb_phase == host_phase:
        try:
            mirrored = validate_transaction_document(
                dict(snapshot.host_transaction)
            )
        except UpdaterV2Error:
            return stop("u13b_usb_host_transaction_mirror_invalid", usb_phase)
        if mirrored != host:
            return stop("u13b_usb_host_transaction_mirror_host_drift", usb_phase)
        return U13BSplitReconciliation(
            HOST_USB_EXACT, host_phase, usb_phase, "u13b_host_usb_exact"
        )
    if _U13B_USB_SUCCESSOR.get(host_phase) == usb_phase:
        if not _mirrored_successor_exact(host, snapshot.host_transaction):
            return stop(
                "u13b_usb_host_transaction_mirror_successor_invalid",
                usb_phase,
            )
        return U13BSplitReconciliation(
            USB_ONE_PHASE_AHEAD_RECONCILABLE,
            host_phase,
            usb_phase,
            "u13b_usb_one_phase_ahead",
        )
    if _U13B_USB_SUCCESSOR.get(usb_phase) == host_phase:
        return U13BSplitReconciliation(
            HOST_ONE_PHASE_AHEAD_STOP,
            host_phase,
            usb_phase,
            "u13b_host_one_phase_ahead",
        )
    return stop("u13b_host_usb_phase_divergent", usb_phase)


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
class U13BDataRestoreReadiness:
    services_quiesced: bool
    broker_preserved: bool

    def validate(self) -> "U13BDataRestoreReadiness":
        if self.services_quiesced is not True or self.broker_preserved is not True:
            raise UpdaterV2Error("u13b_data_restore_readiness_invalid")
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

    def read_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> U13BUsbMetadataSnapshot:
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

    def quiesce_for_data_restore(
        self,
        *,
        transaction: Mapping[str, Any],
    ) -> U13BDataRestoreReadiness:
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
        reconciliation = classify_u13b_usb_host_split(
            current,
            media,
            self.backend.read_transaction_metadata(current, media),
        )
        if reconciliation.classification == USB_ONE_PHASE_AHEAD_RECONCILABLE:
            raise UpdaterV2Error(
                "u13b_usb_one_phase_ahead_reconciliation_required"
            )
        if reconciliation.classification == HOST_ONE_PHASE_AHEAD_STOP:
            raise UpdaterV2Error("u13b_host_one_phase_ahead_stop")
        if reconciliation.classification != HOST_USB_EXACT:
            raise UpdaterV2Error("u13b_host_usb_reconciliation_stop")
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
            self.runtime_owner.quiesce_for_data_restore(
                transaction=current,
            ).validate()
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
