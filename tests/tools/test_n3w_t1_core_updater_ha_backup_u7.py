from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_backup import (
    BACKUP_ARCHIVE_NAME,
    BACKUP_METADATA_NAME,
    HaDataBackupRecord,
    HaQuiesceEvidence,
    ProtectedHaDataBackupProvider,
)
from n3w_t1_core_updater_ha_capacity import compute_install_revalidation
from n3w_t1_core_updater_ha_install import HaUsbU7BackupController
from n3w_t1_core_updater_host import BROKER_UNIT, SERVICES_UNIT, LocalHost
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import (
    record_compatible_media,
    record_ha_data_backup_verified,
    record_predecessor_recovery_and_ha_quiesced,
    record_target_ready,
    request_install,
    request_prepare,
    start_predecessor_recovery,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    UsbCapacityInputs,
    assess_capacity,
)
from n3w_t1_core_updater_ha_usb_state import U7, new_transaction
from n3w_t1_core_updater_v2_common import UpdaterV2Error


CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
TARGET_SIZE = 4096
TARGET_SHA = "1" * 64
USB_UUID = "12345678-1234-5678-1234-567812345678"
FINGERPRINT = "2" * 64


def image_record(
    kind: str,
    image_ref: str,
    *,
    archive_sha256: str,
    archive_size_bytes: int,
    portable: str,
) -> ImageRecoveryRecord:
    return ImageRecoveryRecord(
        kind=kind,
        image_ref=image_ref,
        archive_sha256=archive_sha256,
        archive_size_bytes=archive_size_bytes,
        portable_identity_sha256=portable,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


TARGET_RECORD = image_record(
    "target",
    TARGET,
    archive_sha256=TARGET_SHA,
    archive_size_bytes=TARGET_SIZE,
    portable="3" * 64,
)
PREDECESSOR_RECORD = image_record(
    "predecessor",
    CURRENT,
    archive_sha256="4" * 64,
    archive_size_bytes=2048,
    portable="5" * 64,
)


def build_u6() -> dict[str, object]:
    tx = new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={"runtime_id": "6" * 64},
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
    tx = record_compatible_media(
        tx,
        public_fingerprint=FINGERPRINT,
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=20 * 1024**3,
        capacity_report=capacity,
    )
    tx = start_target_preparation(tx)
    tx = record_target_ready(tx, target=TARGET_RECORD)
    tx = request_install(tx, target=TARGET_RECORD)
    install_capacity = compute_install_revalidation(
        target_artifact_bytes=TARGET_SIZE,
        predecessor_recovery_budget_bytes=2 * 1024**3,
        ha_data_measured_bytes=1024,
        observed_usb_free_bytes=18 * 1024**3,
    )
    return start_predecessor_recovery(
        tx,
        install_capacity=install_capacity,
    )


class MemoryStore:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document
        self.writes: list[dict[str, object]] = []

    def read(self):
        return self.document

    def write(self, document):
        self.document = document
        self.writes.append(document)


class FakeBackend:
    def __init__(self, media: PreparedUsbMedia) -> None:
        self.media = media
        self.synced: list[dict[str, object]] = []

    def resolve_transaction_media(self, transaction, *, write_required):
        assert write_required is True
        return self.media

    def verify_prepared_target(self, *, transaction, media):
        assert media == self.media
        return TARGET_RECORD

    def verify_prepared_predecessor(self, *, transaction, media):
        assert media == self.media
        return PREDECESSOR_RECORD

    def sync_transaction_metadata(self, transaction, media):
        assert media == self.media
        self.synced.append(transaction)


class FakeRuntime:
    def __init__(self) -> None:
        self.quiesce_count = 0
        self.resume_count = 0

    def quiesce_homeassistant_for_backup(self):
        self.quiesce_count += 1
        return HaQuiesceEvidence(
            owner_inactive=True,
            homeassistant_stopped=True,
            manager_stopped=True,
            broker_preserved=True,
        )

    def resume_homeassistant_after_backup_failure(self):
        self.resume_count += 1


class FakeBackup:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.record = HaDataBackupRecord(
            archive_sha256="7" * 64,
            archive_size_bytes=1234,
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

    def create_consistent_backup(
        self,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ):
        assert len(transaction_id_sha256) == 64
        if self.fail:
            raise UpdaterV2Error("synthetic_backup_failure")
        return self.record

    def verify_backup(
        self,
        record,
        *,
        transaction_id_sha256: str,
        destination_root: Path,
    ):
        assert record == self.record
        return record

    def restore_preupgrade_backup(self, record):
        raise AssertionError("U7 must never restore")


def prepared_media(tmp_path: Path) -> PreparedUsbMedia:
    mount = tmp_path / "media"
    mount.mkdir(mode=0o700)
    return PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint=FINGERPRINT,
        filesystem_uuid=USB_UUID,
        measured_usable_bytes=20 * 1024**3,
        mount_path=str(mount),
    ).validate()


def test_u7_controller_stops_in_u7_without_authorization_or_u8(
    tmp_path: Path,
) -> None:
    store = MemoryStore(build_u6())
    backend = FakeBackend(prepared_media(tmp_path))
    runtime = FakeRuntime()
    backup = FakeBackup()
    progress: list[tuple[str, int]] = []

    result = HaUsbU7BackupController(
        transaction_store=store,
        backend=backend,
        runtime_owner=runtime,
        backup_provider=backup,
        progress=lambda phase, value: progress.append((phase, value)),
    ).prepare_or_resume()

    assert result.transaction["phase"] == U7
    assert result.transaction["ha_data_backup_verified"] is True
    assert result.transaction["ha_data_backup_identity"] == backup.record.public()
    assert result.transaction["authorization_claimed"] is False
    assert result.transaction["authorization_consumed"] is False
    assert result.transaction["authorization_id_sha256"] is None
    assert result.services_left_quiesced is True
    assert runtime.quiesce_count == 1
    assert runtime.resume_count == 0
    assert len(backend.synced) == 2
    assert len(store.writes) == 2
    assert progress[-1] == ("u7_stop", 1234)


def test_u7_backup_failure_resumes_application_owner(
    tmp_path: Path,
) -> None:
    store = MemoryStore(build_u6())
    runtime = FakeRuntime()

    with pytest.raises(UpdaterV2Error, match="synthetic_backup_failure"):
        HaUsbU7BackupController(
            transaction_store=store,
            backend=FakeBackend(prepared_media(tmp_path)),
            runtime_owner=runtime,
            backup_provider=FakeBackup(fail=True),
        ).prepare_or_resume()

    assert store.document["phase"] == U7
    assert store.document["authorization_claimed"] is False
    assert store.document["ha_data_backup_verified"] is False
    assert runtime.quiesce_count == 1
    assert runtime.resume_count == 1


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl unavailable")
def test_protected_backup_encrypts_authenticates_and_verifies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / ".storage").mkdir(mode=0o700)
    (source / ".storage" / "core.config_entries").write_text(
        '{"secret":"not-plaintext-on-usb"}',
        encoding="utf-8",
    )
    (source / "secrets.yaml").write_text(
        "mqtt_password: not-plaintext-on-usb\n",
        encoding="utf-8",
    )
    database = sqlite3.connect(source / "home-assistant_v2.db")
    database.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, value TEXT)")
    database.execute("INSERT INTO events(value) VALUES ('ok')")
    database.commit()
    database.close()

    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    product_config = tmp_path / "configuration.yaml"
    product_config.write_text("default_config:\n", encoding="utf-8")
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)

    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=product_config,
    )
    transaction_id = "a" * 64
    record = provider.create_consistent_backup(
        transaction_id_sha256=transaction_id,
        destination_root=destination,
    )

    assert provider.verify_backup(
        record,
        transaction_id_sha256=transaction_id,
        destination_root=destination,
    ) == record
    encrypted = (destination / BACKUP_ARCHIVE_NAME).read_bytes()
    metadata = (destination / BACKUP_METADATA_NAME).read_bytes()
    assert b"not-plaintext-on-usb" not in encrypted
    assert root_key.read_bytes() not in encrypted
    assert root_key.read_bytes() not in metadata


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl unavailable")
def test_protected_backup_tamper_fails_hash(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / "configuration.yaml").write_text(
        "default_config:\n",
        encoding="utf-8",
    )
    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)
    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=source / "configuration.yaml",
    )
    record = provider.create_consistent_backup(
        transaction_id_sha256="b" * 64,
        destination_root=destination,
    )
    archive = destination / BACKUP_ARCHIVE_NAME
    payload = bytearray(archive.read_bytes())
    payload[-1] ^= 0x01
    archive.write_bytes(payload)

    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_archive_hash_mismatch",
    ):
        provider.verify_backup(
            record,
            transaction_id_sha256="b" * 64,
            destination_root=destination,
        )


def test_protected_backup_external_recorder_fails_closed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    product_config = tmp_path / "configuration.yaml"
    product_config.write_text(
        "recorder:\n  db_url: !secret external_db\n",
        encoding="utf-8",
    )
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)
    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=product_config,
    )

    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_external_state_unsupported",
    ):
        provider.create_consistent_backup(
            transaction_id_sha256="c" * 64,
            destination_root=destination,
        )

    assert not (destination / BACKUP_ARCHIVE_NAME).exists()


def test_production_owner_quiesce_requires_broker_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = LocalHost()
    monkeypatch.setattr(host, "stop_services", lambda: None)
    broker_ids = iter(("broker-1", "broker-1"))
    monkeypatch.setattr(
        host,
        "_container_id",
        lambda service: (
            next(broker_ids)
            if service == "broker"
            else "unexpected"
        ),
    )
    monkeypatch.setattr(
        host,
        "_systemctl",
        lambda action, unit: (
            "inactive"
            if action == "is-active" and unit == SERVICES_UNIT
            else "active"
            if action == "is-active" and unit == BROKER_UNIT
            else "unexpected"
        ),
    )
    monkeypatch.setattr(
        host,
        "_running_count",
        lambda service: 1 if service == "broker" else 0,
    )

    evidence = host.quiesce_homeassistant_for_backup()

    assert evidence == {
        "owner_inactive": True,
        "homeassistant_stopped": True,
        "manager_stopped": True,
        "broker_preserved": True,
    }


class FailingQuiesceRuntime(FakeRuntime):
    def quiesce_homeassistant_for_backup(self):
        self.quiesce_count += 1
        raise UpdaterV2Error("synthetic_quiesce_proof_failure")


def test_quiesce_proof_failure_still_resumes_application_owner(
    tmp_path: Path,
) -> None:
    store = MemoryStore(build_u6())
    runtime = FailingQuiesceRuntime()

    with pytest.raises(
        UpdaterV2Error,
        match="synthetic_quiesce_proof_failure",
    ):
        HaUsbU7BackupController(
            transaction_store=store,
            backend=FakeBackend(prepared_media(tmp_path)),
            runtime_owner=runtime,
            backup_provider=FakeBackup(),
        ).prepare_or_resume()

    assert store.document["phase"] != U7
    assert runtime.quiesce_count == 1
    assert runtime.resume_count == 1


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl unavailable")
def test_protected_backup_wrong_system_root_key_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / "configuration.yaml").write_text(
        "default_config:\n",
        encoding="utf-8",
    )
    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)
    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=source / "configuration.yaml",
    )
    transaction_id = "d" * 64
    record = provider.create_consistent_backup(
        transaction_id_sha256=transaction_id,
        destination_root=destination,
    )

    wrong_key = tmp_path / "wrong-system-root.key"
    wrong_key.write_bytes(os.urandom(32))
    wrong_key.chmod(0o600)
    wrong_provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=wrong_key,
        product_config=source / "configuration.yaml",
    )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_authentication_failed",
    ):
        wrong_provider.verify_backup(
            record,
            transaction_id_sha256=transaction_id,
            destination_root=destination,
        )


def test_protected_backup_corrupt_sqlite_fails_closed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / "home-assistant_v2.db").write_bytes(
        b"not-a-sqlite-database"
    )
    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)
    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=source / "configuration.yaml",
    )

    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_sqlite_check_failed",
    ):
        provider.create_consistent_backup(
            transaction_id_sha256="e" * 64,
            destination_root=destination,
        )
    assert not (destination / BACKUP_ARCHIVE_NAME).exists()


def test_u7_provider_restore_is_separately_gated() -> None:
    provider = ProtectedHaDataBackupProvider()
    record = HaDataBackupRecord(
        archive_sha256="9" * 64,
        archive_size_bytes=1,
        manifest_sha256="a" * 64,
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
    with pytest.raises(
        UpdaterV2Error,
        match="ha_data_backup_restore_requires_separate_gate",
    ):
        provider.restore_preupgrade_backup(record)


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl unavailable")
def test_protected_backup_emits_bounded_progress_phases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / "configuration.yaml").write_text(
        "default_config:\n",
        encoding="utf-8",
    )
    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)
    progress: list[tuple[str, int]] = []
    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=source / "configuration.yaml",
        progress=lambda phase, value: progress.append((phase, value)),
    )
    record = provider.create_consistent_backup(
        transaction_id_sha256="f" * 64,
        destination_root=destination,
    )

    phases = [phase for phase, _ in progress]
    for required in (
        "source_validation",
        "archive_encrypt",
        "source_compare",
        "verify_ciphertext",
        "verify_plaintext",
        "verified",
    ):
        assert required in phases
    assert progress[-1] == ("verified", record.archive_size_bytes)


def test_u7_reentry_invalidates_old_backup_before_recreate(
    tmp_path: Path,
) -> None:
    tx = build_u6()
    tx = record_predecessor_recovery_and_ha_quiesced(
        tx,
        predecessor=PREDECESSOR_RECORD,
        ha_quiesced=True,
    )
    old_backup = FakeBackup().record
    tx = record_ha_data_backup_verified(tx, backup=old_backup)
    assert tx["ha_data_backup_verified"] is True

    store = MemoryStore(tx)
    runtime = FakeRuntime()
    backend = FakeBackend(prepared_media(tmp_path))

    with pytest.raises(UpdaterV2Error, match="synthetic_backup_failure"):
        HaUsbU7BackupController(
            transaction_store=store,
            backend=backend,
            runtime_owner=runtime,
            backup_provider=FakeBackup(fail=True),
        ).prepare_or_resume()

    assert store.document["phase"] == U7
    assert store.document["ha_data_backup_verified"] is False
    assert store.document["ha_data_backup_identity"] is None
    assert backend.synced[0]["ha_data_backup_verified"] is False
    assert runtime.resume_count == 1
