from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_backup import HaDataBackupRecord
from n3w_t1_core_updater_ha_capacity import (
    compute_install_revalidation,
    compute_recovery_admission_capacity,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_u13b import (
    HaUsbU13BRollbackController,
    U13BDataRestoreReadiness,
    U13BHealthEvidence,
    U13BPredecessorImageEvidence,
    U13BRuntimeEvidence,
    U13BTargetCleanupEvidence,
)
from n3w_t1_core_updater_ha_usb import (
    claim_live_authorization,
    record_ha_data_backup_verified,
    record_media_bound,
    record_predecessor_recovery_and_ha_quiesced,
    record_recovery_admission,
    record_target_ready,
    request_install,
    request_prepare,
    start_predecessor_recovery,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FormatAuthorization,
    UsbCapacityInputs,
    assess_capacity,
)
from n3w_t1_core_updater_ha_usb_state import U13B, new_transaction


CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
USB_UUID = "12345678-1234-5678-1234-567812345678"
FINGERPRINT = "2" * 64
TARGET_SIZE = 4096
TARGET_SHA = "3" * 64


def image_record(kind, image_ref, sha, size, portable):
    return ImageRecoveryRecord(
        kind=kind,
        image_ref=image_ref,
        archive_sha256=sha,
        archive_size_bytes=size,
        portable_identity_sha256=portable,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


TARGET_RECORD = image_record("target", TARGET, TARGET_SHA, TARGET_SIZE, "4" * 64)
PREDECESSOR_RECORD = image_record(
    "predecessor",
    CURRENT,
    "5" * 64,
    2048,
    "6" * 64,
)
BACKUP_RECORD = HaDataBackupRecord(
    archive_sha256="7" * 64,
    archive_size_bytes=1024,
    manifest_sha256="8" * 64,
    verified=True,
    fsynced=True,
    consistent_preupgrade_point=True,
    complete_production_config=True,
    storage_integrity_verified=True,
    ownership_metadata_present=True,
    confidentiality_protected=True,
    authenticity_protected=True,
    unsupported_external_state=False,
)


def u9_transaction():
    tx = new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={"runtime_id": "9" * 64},
        target_manifest_identity={"release_identity": "ha-2026.10.4"},
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=TARGET_SIZE,
        created_at_unix=100,
    )
    tx = request_prepare(tx)
    capacity = assess_capacity(
        20 * 1024**3,
        UsbCapacityInputs(
            target_artifact_bytes=TARGET_SIZE,
            predecessor_recovery_worst_case_bytes=2 * 1024**3,
            ha_data_backup_worst_case_bytes=2 * 1024**3,
            transaction_metadata_and_working_bytes=1024**3,
            removable_media_reserve_bytes=1024**3,
        ),
    )
    tx = record_media_bound(
        tx,
        format_authorization=FormatAuthorization(
            public_fingerprint=FINGERPRINT,
            confirmation_verified=True,
            filesystem="ext4",
            label="N3W-UPDATE",
        ),
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=20 * 1024**3,
        capacity_report=capacity,
    )
    tx = start_target_preparation(tx)
    tx = record_target_ready(tx, target=TARGET_RECORD)
    tx = request_install(tx, target=TARGET_RECORD)
    tx = start_predecessor_recovery(
        tx,
        install_capacity=compute_install_revalidation(
            target_artifact_bytes=TARGET_SIZE,
            predecessor_recovery_budget_bytes=2 * 1024**3,
            ha_data_measured_bytes=1024,
            observed_usb_free_bytes=18 * 1024**3,
        ),
    )
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=PREDECESSOR_RECORD,
        ha_quiesced=True,
    )
    tx = record_ha_data_backup_verified(tx, backup=BACKUP_RECORD)
    tx = record_recovery_admission(
        tx,
        target=TARGET_RECORD,
        predecessor=PREDECESSOR_RECORD,
        backup=BACKUP_RECORD,
        capacity_report=capacity,
        recovery_capacity=compute_recovery_admission_capacity(
            target_archive_bytes=TARGET_SIZE,
            predecessor_archive_bytes=PREDECESSOR_RECORD.archive_size_bytes,
            ha_backup_archive_bytes=BACKUP_RECORD.archive_size_bytes,
            transaction_working_budget_bytes=1024**3,
            observed_usb_free_bytes=16 * 1024**3,
        ),
        production_prestate_exact=True,
    )
    return claim_live_authorization(
        tx,
        "N3W_T1_CORE_UPDATER_TEST_U13B",
    )


class Store:
    def __init__(self, document):
        self.document = document
        self.writes = []

    def read(self):
        return self.document

    def write(self, document):
        self.document = document
        self.writes.append(document["phase"])


class Backend:
    def __init__(self, media):
        self.media = media
        self.syncs = []

    def resolve_transaction_media(self, transaction, *, write_required):
        assert write_required is True
        return self.media

    def verify_recovery_target(self, *, transaction, media):
        return TARGET_RECORD

    def verify_recovery_predecessor(self, *, transaction, media):
        return PREDECESSOR_RECORD

    def sync_transaction_metadata(self, transaction, media):
        self.syncs.append(transaction["phase"])


class Backup:
    def __init__(self):
        self.restores = 0

    def verify_backup(
        self,
        record,
        *,
        transaction_id_sha256,
        destination_root,
    ):
        return record

    def restore_preupgrade_backup(
        self,
        record,
        *,
        transaction_id_sha256,
        source_root,
    ):
        self.restores += 1
        return record


class Runtime:
    def __init__(self):
        self.steps = []

    def cleanup_failed_target(self, *, transaction, target):
        self.steps.append("cleanup")
        return U13BTargetCleanupEvidence(True, True, True)

    def restore_predecessor_image(self, *, transaction, media, predecessor):
        self.steps.append("image")
        return U13BPredecessorImageEvidence(True)

    def quiesce_for_data_restore(self, *, transaction):
        self.steps.append("data_quiesce")
        return U13BDataRestoreReadiness(True, True)

    def start_predecessor_runtime(self, *, transaction, predecessor):
        self.steps.append("runtime")
        return U13BRuntimeEvidence(True, True, True, True, True)

    def verify_predecessor_health(self, *, transaction, predecessor):
        self.steps.append("health")
        return U13BHealthEvidence(True, True, True, True)


def media(tmp_path):
    root = tmp_path / "usb"
    root.mkdir(mode=0o700)
    return PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint=FINGERPRINT,
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=20 * 1024**3,
        mount_path=str(root),
    ).validate()


def test_u13b_controller_persists_usb_before_host_for_every_subphase(tmp_path):
    store = Store(u9_transaction())
    backend = Backend(media(tmp_path))
    runtime = Runtime()
    backup = Backup()
    result = HaUsbU13BRollbackController(
        transaction_store=store,
        backend=backend,
        runtime_owner=runtime,
        backup_provider=backup,
    ).rollback(failure_code="target_health_acceptance_failed")

    assert result.completed is True
    assert result.transaction["phase"] == U13B
    assert result.transaction["status"] == "ROLLED_BACK"
    assert backend.syncs == store.writes == [
        "U13B0_ROLLBACK_IN_PROGRESS",
        "U13B1_TARGET_CLEANUP_COMPLETE",
        "U13B2_PREDECESSOR_IMAGE_RESTORED",
        "U13B3_HA_DATA_RESTORED",
        "U13B4_PREDECESSOR_RUNTIME_STARTED",
        "U13B_ROLLED_BACK",
    ]
    assert runtime.steps == [
        "cleanup",
        "image",
        "data_quiesce",
        "runtime",
        "health",
    ]
    assert backup.restores == 1


def test_u13b_controller_resumes_after_operation_level_interruption(tmp_path):
    store = Store(u9_transaction())
    backend = Backend(media(tmp_path))
    runtime = Runtime()
    backup = Backup()
    controller = HaUsbU13BRollbackController(
        transaction_store=store,
        backend=backend,
        runtime_owner=runtime,
        backup_provider=backup,
    )
    original = runtime.start_predecessor_runtime

    def fail_once(*, transaction, predecessor):
        runtime.start_predecessor_runtime = original
        raise RuntimeError("synthetic_power_loss")

    runtime.start_predecessor_runtime = fail_once
    try:
        controller.rollback(failure_code="target_health_acceptance_failed")
    except RuntimeError as error:
        assert str(error) == "synthetic_power_loss"
    else:
        raise AssertionError("synthetic failure expected")

    assert store.document["phase"] == "U13B3_HA_DATA_RESTORED"
    assert backup.restores == 1

    result = controller.rollback(failure_code="ignored_on_resume")
    assert result.transaction["phase"] == U13B
    assert backup.restores == 1
    assert runtime.steps[-2:] == ["runtime", "health"]
    assert runtime.steps.count("data_quiesce") == 1
