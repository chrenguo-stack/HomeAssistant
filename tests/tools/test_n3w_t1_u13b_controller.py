from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_v2_common import UpdaterV2Error

from n3w_t1_core_updater_ha_backup import HaDataBackupRecord
from n3w_t1_core_updater_ha_capacity import (
    compute_install_revalidation,
    compute_recovery_admission_capacity,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_u13b import (
    DIVERGENT_OR_UNKNOWN_STOP,
    HOST_ONE_PHASE_AHEAD_STOP,
    HOST_USB_EXACT,
    USB_ONE_PHASE_AHEAD_RECONCILABLE,
    HaUsbU13BRollbackController,
    U13BDataRestoreReadiness,
    U13BHealthEvidence,
    U13BPredecessorImageEvidence,
    U13BRuntimeEvidence,
    U13BTargetCleanupEvidence,
    U13BUsbMetadataSnapshot,
    classify_u13b_usb_host_split,
)
from n3w_t1_core_updater_ha_usb import (
    claim_live_authorization,
    record_ha_data_backup_verified,
    record_predecessor_capacity_released,
    record_media_bound,
    record_predecessor_recovery_and_ha_quiesced,
    record_recovery_admission,
    record_target_accepted,
    record_target_ready,
    record_target_started,
    record_rollback_target_cleanup,
    request_install,
    request_prepare,
    start_predecessor_recovery,
    start_rollback,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FormatAuthorization,
    UsbCapacityInputs,
    assess_capacity,
)
from n3w_t1_core_updater_ha_usb_state import (
    USB_TX_CHECKSUM_SCHEMA,
    USB_TX_CONTENT_AUTHORITY_SCHEMA,
    USB_TX_MANIFEST_SCHEMA,
    USB_TX_PHASE_SCHEMA,
    U9,
    U10,
    U11,
    U12,
    U13B,
    new_transaction,
)


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


def origin_transaction(phase):
    tx = u9_transaction()
    if phase == U9:
        return tx
    tx = record_predecessor_capacity_released(
        tx,
        predecessor_runtime_released=True,
        predecessor_image_released=True,
        target_internal_image_absent=True,
    )
    if phase == U10:
        return tx
    tx = record_target_started(tx)
    if phase == U11:
        return tx
    tx = record_target_accepted(tx)
    if phase == U12:
        return tx
    raise AssertionError("unsupported origin")


def usb_snapshot(transaction, *, phase=None, authority_override=None):
    authority = {
        "schema": USB_TX_CONTENT_AUTHORITY_SCHEMA,
        "transaction_id_sha256": transaction["transaction_id_sha256"],
        "release_identity": transaction["target_manifest_identity"]["release_identity"],
        "target_artifact_identity": transaction["target_artifact_identity"],
        "predecessor_recovery_identity": transaction["predecessor_recovery_identity"],
        "ha_data_backup_identity": transaction["ha_data_backup_identity"],
        "recovery_content_manifest_sha256": transaction["recovery_content_manifest_sha256"],
    }
    if authority_override:
        authority.update(authority_override)
    return U13BUsbMetadataSnapshot(
        manifest={
            "schema": USB_TX_MANIFEST_SCHEMA,
            "transaction_id_sha256": transaction["transaction_id_sha256"],
            "release_identity": transaction["target_manifest_identity"]["release_identity"],
            "target_image_ref": transaction["target_image_ref"],
            "target_archive_sha256": transaction["target_archive_sha256"],
            "target_archive_size_bytes": transaction["target_archive_size"],
            "usb_filesystem_uuid": transaction["usb_filesystem_uuid"],
            "usb_device_identity_public_fingerprint": FINGERPRINT,
        },
        phase={
            "schema": USB_TX_PHASE_SCHEMA,
            "transaction_id_sha256": transaction["transaction_id_sha256"],
            "phase": phase or transaction["phase"],
            "target_artifact_verified": transaction["target_artifact_verified"],
            "usb_capacity_verified": transaction["usb_capacity_verified"],
        },
        checksums={
            "schema": USB_TX_CHECKSUM_SCHEMA,
            "target_archive_sha256": transaction["target_archive_sha256"],
            "target_archive_size_bytes": transaction["target_archive_size"],
        },
        content_authority=authority,
    )


class Store:
    def __init__(self, document):
        self.document = document
        self.writes = []
        self.fail_next_write = False

    def read(self):
        return self.document

    def write(self, document):
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("synthetic_host_persist_loss")
        self.document = document
        self.writes.append(document["phase"])


class Backend:
    def __init__(self, media):
        self.media = media
        self.syncs = []
        self.snapshot = None

    def resolve_transaction_media(self, transaction, *, write_required):
        assert write_required is True
        return self.media

    def read_transaction_metadata(self, transaction, media):
        return self.snapshot or usb_snapshot(transaction)

    def verify_recovery_target(self, *, transaction, media):
        return TARGET_RECORD

    def verify_recovery_predecessor(self, *, transaction, media):
        return PREDECESSOR_RECORD

    def sync_transaction_metadata(self, transaction, media):
        self.syncs.append(transaction["phase"])
        self.snapshot = usb_snapshot(transaction)


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


@pytest.mark.parametrize("origin_phase", [U9, U10, U11, U12])
def test_u13b_controller_persists_usb_before_host_for_every_subphase(
    tmp_path,
    origin_phase,
):
    store = Store(origin_transaction(origin_phase))
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


@pytest.mark.parametrize(
    ("step", "durable_phase"),
    [
        ("cleanup", "U13B0_ROLLBACK_IN_PROGRESS"),
        ("image", "U13B1_TARGET_CLEANUP_COMPLETE"),
        ("data_quiesce", "U13B2_PREDECESSOR_IMAGE_RESTORED"),
        ("data_restore", "U13B2_PREDECESSOR_IMAGE_RESTORED"),
        ("runtime", "U13B3_HA_DATA_RESTORED"),
        ("health", "U13B4_PREDECESSOR_RUNTIME_STARTED"),
    ],
)
def test_u13b_controller_resumes_from_each_operation_level_interruption(
    tmp_path,
    step,
    durable_phase,
):
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

    if step == "cleanup":
        original = runtime.cleanup_failed_target
        def fail_once(**kwargs):
            runtime.cleanup_failed_target = original
            raise RuntimeError("synthetic_power_loss")
        runtime.cleanup_failed_target = fail_once
    elif step == "image":
        original = runtime.restore_predecessor_image
        def fail_once(**kwargs):
            runtime.restore_predecessor_image = original
            raise RuntimeError("synthetic_power_loss")
        runtime.restore_predecessor_image = fail_once
    elif step == "data_quiesce":
        original = runtime.quiesce_for_data_restore
        def fail_once(**kwargs):
            runtime.quiesce_for_data_restore = original
            raise RuntimeError("synthetic_power_loss")
        runtime.quiesce_for_data_restore = fail_once
    elif step == "data_restore":
        original = backup.restore_preupgrade_backup
        def fail_once(*args, **kwargs):
            backup.restore_preupgrade_backup = original
            raise RuntimeError("synthetic_power_loss")
        backup.restore_preupgrade_backup = fail_once
    elif step == "runtime":
        original = runtime.start_predecessor_runtime
        def fail_once(**kwargs):
            runtime.start_predecessor_runtime = original
            raise RuntimeError("synthetic_power_loss")
        runtime.start_predecessor_runtime = fail_once
    else:
        original = runtime.verify_predecessor_health
        def fail_once(**kwargs):
            runtime.verify_predecessor_health = original
            raise RuntimeError("synthetic_power_loss")
        runtime.verify_predecessor_health = fail_once

    with pytest.raises(RuntimeError, match="synthetic_power_loss"):
        controller.rollback(
            failure_code="target_health_acceptance_failed",
        )
    assert store.document["phase"] == durable_phase

    result = controller.rollback(failure_code="resume")
    assert result.transaction["phase"] == U13B



def test_u13b_split_classifier_exact_and_usb_ahead(tmp_path):
    host = origin_transaction(U9)
    observed_media = media(tmp_path)
    exact = classify_u13b_usb_host_split(host, observed_media, usb_snapshot(host))
    assert exact.classification == HOST_USB_EXACT

    ahead = classify_u13b_usb_host_split(
        host,
        observed_media,
        usb_snapshot(host, phase="U13B0_ROLLBACK_IN_PROGRESS"),
    )
    assert ahead.classification == USB_ONE_PHASE_AHEAD_RECONCILABLE


def test_u13b_split_classifier_host_ahead_and_divergent(tmp_path):
    host_u9 = origin_transaction(U9)
    b0 = start_rollback(
        host_u9,
        failure_code="target_health_acceptance_failed",
        target=TARGET_RECORD,
        predecessor=PREDECESSOR_RECORD,
        backup=BACKUP_RECORD,
    )
    b1 = record_rollback_target_cleanup(
        b0,
        services_quiesced=True,
        target_runtime_absent=True,
        target_image_absent=True,
    )
    observed_media = media(tmp_path)

    host_ahead = classify_u13b_usb_host_split(
        b1,
        observed_media,
        usb_snapshot(b1, phase=b0["phase"]),
    )
    assert host_ahead.classification == HOST_ONE_PHASE_AHEAD_STOP

    divergent = classify_u13b_usb_host_split(
        b0,
        observed_media,
        usb_snapshot(b0, phase="U13B3_HA_DATA_RESTORED"),
    )
    assert divergent.classification == DIVERGENT_OR_UNKNOWN_STOP


def test_u13b_split_classifier_rejects_recovery_authority_drift(tmp_path):
    host = origin_transaction(U9)
    observed = usb_snapshot(
        host,
        authority_override={"recovery_content_manifest_sha256": "f" * 64},
    )
    result = classify_u13b_usb_host_split(host, media(tmp_path), observed)
    assert result.classification == DIVERGENT_OR_UNKNOWN_STOP
    assert result.reason == "u13b_usb_transaction_or_recovery_authority_drift"


def test_u13b_controller_stops_usb_ahead_before_blind_replay(tmp_path):
    store = Store(origin_transaction(U9))
    backend = Backend(media(tmp_path))
    runtime = Runtime()
    backup = Backup()
    controller = HaUsbU13BRollbackController(
        transaction_store=store,
        backend=backend,
        runtime_owner=runtime,
        backup_provider=backup,
    )
    store.fail_next_write = True
    with pytest.raises(RuntimeError, match="synthetic_host_persist_loss"):
        controller.rollback(failure_code="target_health_acceptance_failed")

    assert store.document["phase"] == U9
    assert backend.snapshot.phase["phase"] == "U13B0_ROLLBACK_IN_PROGRESS"
    assert runtime.steps == []

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_usb_one_phase_ahead_reconciliation_required",
    ):
        controller.rollback(failure_code="resume")
    assert store.document["phase"] == U9
    assert runtime.steps == []
