from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_ha_recovery as recovery_mod
from n3w_t1_core_updater_ha_backup import (
    HaDataBackupRecord,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import (
    claim_live_authorization,
    destructive_cutover_allowed,
    record_recovery_admission,
    request_install,
)
from n3w_t1_core_updater_ha_usb_media import (
    FORMAT_CONFIRMATION,
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    RemovableDeviceCandidate,
    UsbCapacityInputs,
    assess_capacity,
    authorize_destructive_format,
    classify_candidate,
    require_same_filesystem_uuid,
    select_single_eligible_device,
)
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U2,
    U3,
    U4,
    U6,
    U7,
    U8,
    U10,
    U11,
    U12,
    U13A,
    HaUsbStateStore,
    new_transaction,
    transition,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import TX_SCHEMA_V2, UpdaterV2Error
from n3w_t1_core_updater_v2_state import V2StateStore


CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
TARGET_SHA = "1" * 64
TARGET_SIZE = 835_309_535
USB_UUID = "12345678-1234-5678-1234-567812345678"
FINGERPRINT = "a" * 64
AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_TEST_01"


def candidate(**overrides) -> RemovableDeviceCandidate:
    values = {
        "public_fingerprint": FINGERPRINT,
        "newly_inserted": True,
        "removable": True,
        "mass_storage": True,
        "read_only": False,
        "is_root_device": False,
        "backs_production_mount": False,
        "display_identity_matches": True,
    }
    values.update(overrides)
    return RemovableDeviceCandidate(**values)


def transaction():
    return new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={
            "portable_identity_sha256": "2" * 64,
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": "ha-2026.10.4",
            "manifest_sha256": "3" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=TARGET_SIZE,
        created_at_unix=1_800_000_000,
    )


def ready_to_install():
    tx = transition(transaction(), U1, updated_at_unix=1_800_000_001)
    tx = transition(
        tx,
        U2,
        updates={
            "usb_device_identity_public_fingerprint": FINGERPRINT,
            "usb_filesystem_uuid": USB_UUID,
            "usb_measured_usable_bytes": USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
            "usb_mount_authority": f"filesystem_uuid:{USB_UUID}",
            "usb_capacity_verified": True,
        },
        updated_at_unix=1_800_000_002,
    )
    tx = transition(tx, U3, updated_at_unix=1_800_000_003)
    return transition(
        tx,
        U4,
        updates={"target_artifact_verified": True},
        updated_at_unix=1_800_000_004,
    )


def target_record():
    return ImageRecoveryRecord(
        kind="target",
        image_ref=TARGET,
        archive_sha256=TARGET_SHA,
        archive_size_bytes=TARGET_SIZE,
        portable_identity_sha256="4" * 64,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


def predecessor_record():
    return ImageRecoveryRecord(
        kind="predecessor",
        image_ref=CURRENT,
        archive_sha256="5" * 64,
        archive_size_bytes=2_448_553_472,
        portable_identity_sha256="6" * 64,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


def backup_record(**overrides):
    values = {
        "archive_sha256": "7" * 64,
        "archive_size_bytes": 1_000_000,
        "manifest_sha256": "8" * 64,
        "verified": True,
        "fsynced": True,
        "consistent_preupgrade_point": True,
        "complete_production_config": True,
        "storage_integrity_verified": True,
        "ownership_metadata_present": True,
        "confidentiality_protected": True,
        "authenticity_protected": True,
        "unsupported_external_state": False,
    }
    values.update(overrides)
    return HaDataBackupRecord(**values)


def u7_transaction():
    tx = request_install(ready_to_install())
    tx = transition(tx, U6, updated_at_unix=1_800_000_006)
    return transition(
        tx,
        U7,
        updates={"predecessor_recovery_verified": True},
        updated_at_unix=1_800_000_007,
    )


def u8_transaction():
    return record_recovery_admission(
        u7_transaction(),
        target=target_record(),
        predecessor=predecessor_record(),
        backup=backup_record(),
        same_bound_usb_uuid=True,
        capacity_pass=True,
        production_prestate_exact=True,
    )


def test_root_disk_is_never_eligible_for_format():
    root = candidate(is_root_device=True)
    assert "root_device" in classify_candidate(root)
    with pytest.raises(UpdaterV2Error, match="usb_no_eligible_device"):
        select_single_eligible_device([root])


def test_multiple_eligible_usb_devices_fail_closed():
    second = candidate(public_fingerprint="b" * 64)
    with pytest.raises(UpdaterV2Error, match="usb_multiple_eligible_devices"):
        select_single_eligible_device([candidate(), second])


def test_read_only_usb_fails_closed():
    readonly = candidate(read_only=True)
    assert "read_only" in classify_candidate(readonly)
    with pytest.raises(UpdaterV2Error, match="usb_no_eligible_device"):
        select_single_eligible_device([readonly])


def test_explicit_destructive_confirmation_is_required():
    selected = select_single_eligible_device([candidate()])
    with pytest.raises(
        UpdaterV2Error,
        match="usb_destructive_confirmation_missing",
    ):
        authorize_destructive_format(selected, "wrong")
    authorization = authorize_destructive_format(
        selected,
        FORMAT_CONFIRMATION,
    )
    assert authorization.confirmation_verified is True
    assert authorization.filesystem == "ext4"


def test_exact_14_gib_measured_boundary_passes():
    inputs = UsbCapacityInputs(
        target_artifact_bytes=1 * 1024**3,
        predecessor_recovery_worst_case_bytes=2 * 1024**3,
        ha_data_backup_worst_case_bytes=3 * 1024**3,
        transaction_metadata_and_working_bytes=1 * 1024**3,
        removable_media_reserve_bytes=1 * 1024**3,
    )
    report = assess_capacity(
        USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        inputs,
    )
    assert report.measured_floor_pass is True
    assert report.transaction_formula_pass is True
    assert report.capacity_pass is True


def test_one_byte_below_14_gib_fails_even_when_formula_fits():
    inputs = UsbCapacityInputs(
        target_artifact_bytes=1,
        predecessor_recovery_worst_case_bytes=1,
        ha_data_backup_worst_case_bytes=1,
        transaction_metadata_and_working_bytes=0,
        removable_media_reserve_bytes=0,
    )
    report = assess_capacity(
        USB_MEASURED_USABLE_CAPACITY_MIN_BYTES - 1,
        inputs,
    )
    assert report.measured_floor_pass is False
    assert report.transaction_formula_pass is True
    assert report.capacity_pass is False


def test_full_transaction_formula_can_reject_media_above_floor():
    inputs = UsbCapacityInputs(
        target_artifact_bytes=5 * 1024**3,
        predecessor_recovery_worst_case_bytes=5 * 1024**3,
        ha_data_backup_worst_case_bytes=5 * 1024**3,
        transaction_metadata_and_working_bytes=1,
        removable_media_reserve_bytes=1,
    )
    report = assess_capacity(
        USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        inputs,
    )
    assert report.measured_floor_pass is True
    assert report.transaction_formula_pass is False
    assert report.capacity_pass is False


def test_bound_uuid_mismatch_fails_closed():
    with pytest.raises(UpdaterV2Error, match="usb_filesystem_uuid_mismatch"):
        require_same_filesystem_uuid(
            USB_UUID,
            "87654321-4321-8765-4321-876543218765",
        )


def test_install_intent_does_not_claim_or_consume_authorization():
    tx = request_install(ready_to_install())
    assert tx["authorization_claimed"] is False
    assert tx["authorization_consumed"] is False
    assert tx["authorization_id_sha256"] is None
    assert destructive_cutover_allowed(tx) is False


def test_u8_requires_backup_predecessor_and_target_recovery_authority():
    tx = u7_transaction()
    with pytest.raises(UpdaterV2Error, match="ha_data_backup_contract_incomplete"):
        record_recovery_admission(
            tx,
            target=target_record(),
            predecessor=predecessor_record(),
            backup=backup_record(verified=False),
            same_bound_usb_uuid=True,
            capacity_pass=True,
            production_prestate_exact=True,
        )
    with pytest.raises(UpdaterV2Error, match="usb_filesystem_uuid_mismatch"):
        record_recovery_admission(
            tx,
            target=target_record(),
            predecessor=predecessor_record(),
            backup=backup_record(),
            same_bound_usb_uuid=False,
            capacity_pass=True,
            production_prestate_exact=True,
        )


def test_u8_then_u9_claim_is_one_shot_and_enables_destructive_boundary():
    tx = u8_transaction()
    assert tx["phase"] == U8
    assert destructive_cutover_allowed(tx) is False

    claimed = claim_live_authorization(tx, AUTHORIZATION_ID)
    assert claimed["authorization_claimed"] is True
    assert claimed["authorization_consumed"] is True
    assert claimed["authorization_id_sha256"] != AUTHORIZATION_ID
    assert destructive_cutover_allowed(claimed) is True

    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_live_authorization_phase_invalid",
    ):
        claim_live_authorization(claimed, AUTHORIZATION_ID)


def test_raw_authorization_id_is_forbidden_in_transaction_state():
    tx = transaction()
    tx["authorization_id"] = AUTHORIZATION_ID
    with pytest.raises(
        UpdaterV2Error,
        match="ha_usb_transaction_sensitive_field_forbidden",
    ):
        validate_transaction_document(tx)


def test_backup_contract_rejects_external_state_and_plaintext_design():
    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_external_state_unsupported",
    ):
        validate_backup_record(
            backup_record(unsupported_external_state=True)
        )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_contract_incomplete",
    ):
        validate_backup_record(
            backup_record(confidentiality_protected=False)
        )


def test_ha_usb_store_blocks_nonterminal_generic_v2_transaction(tmp_path):
    root = tmp_path / "state"
    generic = V2StateStore(root)
    generic.write(
        {
            "schema": TX_SCHEMA_V2,
            "status": "APPLYING",
        }
    )
    store = HaUsbStateStore(root)
    with pytest.raises(UpdaterV2Error, match="upgrade_transaction_active"):
        store.prepare_new()


def test_ha_usb_store_reuses_generic_v2_process_lock(monkeypatch, tmp_path):
    sentinel = object()
    monkeypatch.setattr(V2StateStore, "lock", lambda self: sentinel)
    store = HaUsbStateStore(tmp_path / "state")
    assert store.lock() is sentinel


def test_terminal_ha_usb_transaction_is_archived_before_next(tmp_path):
    root = tmp_path / "state"
    store = HaUsbStateStore(root)
    tx = claim_live_authorization(u8_transaction(), AUTHORIZATION_ID)
    tx = transition(tx, U10, updated_at_unix=1_800_000_010)
    tx = transition(tx, U11, updated_at_unix=1_800_000_011)
    tx = transition(tx, U12, updated_at_unix=1_800_000_012)
    tx = transition(tx, U13A, updated_at_unix=1_800_000_013)
    store.write(tx)
    assert store.path.stat().st_mode & 0o777 == 0o600
    store.prepare_new()
    assert not store.path.exists()
    archived = list(store.history.glob("*-homeassistant-usb-*.json"))
    assert len(archived) == 1


def test_recovery_interface_contains_no_broad_prune_commands():
    source = inspect.getsource(recovery_mod)
    assert "docker system prune" not in source
    assert "docker image prune" not in source
    assert "prune -a" not in source
