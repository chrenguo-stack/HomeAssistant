from __future__ import annotations

import io
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import n3w_t1_core_updater_ha_mounted_media as mounted_media
import n3w_t1_core_updater_ha_recovery_startup as startup
from n3w_t1_core_updater_ha_usb import request_prepare, record_existing_media_bound, start_target_preparation
from n3w_t1_core_updater_ha_usb_state import U7, new_transaction, record_usb_capacity_event
from n3w_t1_core_updater_ha_usb_media import (
    USB_PRODUCT_MIN_CAPACITY_GB,
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    RemovableDeviceCandidate,
    UsbCapacityReport,
    classify_candidate,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


def test_v13_architecture_freezes_16gb_media_and_dynamic_per_operation_capacity() -> None:
    text = (
        REPO
        / "docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md"
    ).read_text(encoding="utf-8")
    assert "16GB 是产品最低介质规格" in text
    assert "运行时不信任营销标称容量" in text
    assert "每个实际写入动作" in text
    assert "前代镜像先测量，再备份" in text
    assert "受保护数据备份单独动态准入" in text
    assert "固定常量只能描述固定开销" in text


def test_16gb_product_minimum_is_separate_from_transaction_free_space() -> None:
    assert USB_PRODUCT_MIN_CAPACITY_GB == 16
    assert USB_MEASURED_USABLE_CAPACITY_MIN_BYTES == 14 * 1024**3
    candidate = RemovableDeviceCandidate(
        public_fingerprint="a" * 64,
        newly_inserted=True,
        removable=True,
        mass_storage=True,
        read_only=False,
        is_root_device=False,
        backs_production_mount=False,
        display_identity_matches=True,
    )
    assert classify_candidate(candidate) == ()


def test_prepare_authority_v2_does_not_accept_static_predecessor_or_reserve_budget() -> None:
    document = {"transaction_id_sha256": "a" * 64}
    grant = {
        "schema": startup.PREPARE_AUTHORITY_SCHEMA,
        "transaction_id_sha256": document["transaction_id_sha256"],
        "usb_filesystem_uuid": "12345678-1234-5678-1234-567812345678",
        "target_source": "/var/lib/n3w-t1-core-updater/ha-target-test.tar",
        "launch_sha256": "b" * 64,
        "expires_at_unix": 0x7FFFFFFF,
    }
    assert startup._validate_prepare_authority(dict(grant), document) == grant

    with pytest.raises(UpdaterV2Error, match="ha_usb_prepare_authority_invalid"):
        startup._validate_prepare_authority(
            {**grant, "max_predecessor_bytes": 1},
            document,
        )
    with pytest.raises(UpdaterV2Error, match="ha_usb_prepare_authority_invalid"):
        startup._validate_prepare_authority(
            {**grant, "usb_reserve_bytes": 1},
            document,
        )


def test_predecessor_archive_measurement_counts_the_actual_export_stream(monkeypatch) -> None:
    payload = b"predecessor-export" * 4096
    runtime = object.__new__(startup.LocalHaPredecessorRuntime)

    @contextmanager
    def export(_reference: str):
        yield io.BytesIO(payload)

    monkeypatch.setattr(runtime, "_export_predecessor", export)
    assert runtime._measure_predecessor_archive(
        "local/n3w-homeassistant:test"
    ) == len(payload)


def test_predecessor_write_is_rejected_before_source_read_when_current_free_space_is_short(
    tmp_path: Path, monkeypatch
) -> None:
    directory = tmp_path / "usb-transaction"
    directory.mkdir()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    source_opened = False

    @contextmanager
    def source():
        nonlocal source_opened
        source_opened = True
        yield io.BytesIO(b"1234")

    monkeypatch.setattr(
        mounted_media.os,
        "fstatvfs",
        lambda _fd: SimpleNamespace(f_frsize=1, f_bavail=3),
    )
    admissions = []
    try:
        with pytest.raises(UpdaterV2Error, match="ha_usb_predecessor_space_insufficient"):
            mounted_media._prepare_archive(
                fd,
                "predecessor",
                "local/n3w-homeassistant:test",
                source,
                expected_size=4,
                capacity_admit=lambda *args: admissions.append(args),
            )
    finally:
        os.close(fd)

    assert source_opened is False
    assert admissions == [("predecessor_archive", 5, 3, False)]


def test_capacity_events_persist_failed_retry_and_completed_write() -> None:
    tx = new_transaction(
        current_image_ref="local/n3w-homeassistant:2026.10.0-test",
        current_image_identity={"test": "predecessor"},
        target_manifest_identity={"release_identity": "homeassistant-test"},
        target_image_ref="local/n3w-homeassistant:2026.10.4-test",
        target_archive_sha256="a" * 64,
        target_archive_size=100,
    )
    tx = record_usb_capacity_event(
        tx,
        operation="target_archive",
        required_bytes=120,
        available_bytes_before=100,
        capacity_pass=False,
    )
    assert tx["usb_capacity_events"][-1]["capacity_pass"] is False

    tx = record_usb_capacity_event(
        tx,
        operation="target_archive",
        required_bytes=120,
        available_bytes_before=200,
        capacity_pass=True,
    )
    tx = record_usb_capacity_event(
        tx,
        operation="target_archive",
        required_bytes=120,
        available_bytes_before=200,
        capacity_pass=True,
        actual_written_bytes=100,
        available_bytes_after=90,
    )
    assert len(tx["usb_capacity_events"]) == 2
    completed = tx["usb_capacity_events"][-1]
    assert completed == {
        "operation": "target_archive",
        "required_bytes": 120,
        "available_bytes_before": 200,
        "capacity_pass": True,
        "actual_written_bytes": 100,
        "available_bytes_after": 90,
    }


def test_prepare_capacity_block_waits_without_repeating_write_until_space_recovers(
    tmp_path: Path, monkeypatch
) -> None:
    tx = new_transaction(
        current_image_ref="local/n3w-homeassistant:2026.10.0-test",
        current_image_identity={"test": "predecessor"},
        target_manifest_identity={"release_identity": "homeassistant-test"},
        target_image_ref="local/n3w-homeassistant:2026.10.4-test",
        target_archive_sha256="a" * 64,
        target_archive_size=100,
    )
    tx = request_prepare(tx)
    report = UsbCapacityReport(
        measured_usable_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        required_bytes=100,
        measured_floor_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        measured_floor_pass=True,
        transaction_formula_pass=True,
        capacity_pass=True,
    )
    tx = record_existing_media_bound(
        tx,
        filesystem_uuid="12345678-1234-5678-1234-567812345678",
        capacity_report=report,
    )
    tx = start_target_preparation(tx)
    tx = record_usb_capacity_event(
        tx,
        operation="target_archive",
        required_bytes=120,
        available_bytes_before=100,
        capacity_pass=False,
    )
    tx = {**tx, "failure_code": "ha_usb_target_space_insufficient"}

    class Store:
        root = tmp_path
        document = tx

        @classmethod
        def read(cls):
            return cls.document

        @classmethod
        def write(cls, document):
            cls.document = document

        @staticmethod
        @contextmanager
        def lock():
            yield

    class Runtime:
        prepare_calls = 0

        @staticmethod
        def _original_mountpoint(_uuid):
            return tmp_path

        @classmethod
        def prepare_requested(cls, _store):
            cls.prepare_calls += 1
            return "READY_TO_INSTALL"

    monkeypatch.setattr(
        startup,
        "measure_preparation_capacity",
        lambda *_args: UsbCapacityReport(
            measured_usable_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
            required_bytes=120,
            measured_floor_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
            measured_floor_pass=True,
            transaction_formula_pass=False,
            capacity_pass=False,
        ),
    )

    assert startup._dispatch_pending_candidate(Store(), Runtime()) == "PREPARE_WAITING_FOR_USB_SPACE"
    assert Runtime.prepare_calls == 0
    assert Store.document["failure_code"] == "ha_usb_target_space_insufficient"

    (tmp_path / startup.PREPARE_AUTHORITY_FILE).write_text("present", encoding="utf-8")
    monkeypatch.setattr(
        startup,
        "measure_preparation_capacity",
        lambda *_args: UsbCapacityReport(
            measured_usable_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
            required_bytes=120,
            measured_floor_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
            measured_floor_pass=True,
            transaction_formula_pass=True,
            capacity_pass=True,
        ),
    )

    assert startup._dispatch_pending_candidate(Store(), Runtime()) == "READY_TO_INSTALL"
    assert Runtime.prepare_calls == 1
    assert Store.document["failure_code"] is None


def test_quiesced_ha_backup_checks_current_usb_free_space_before_real_backup_write(
    tmp_path: Path, monkeypatch
) -> None:
    internal = tmp_path / "internal"
    internal.mkdir()
    work = internal / "work"
    work.mkdir(mode=0o700)
    usb = tmp_path / "usb"
    usb.mkdir()
    txid = "c" * 64

    class Store:
        root = internal
        document = {
            "transaction_id_sha256": txid,
            "usb_binding_mode": "existing_filesystem",
            "predecessor_start": {"launch_sha256": "d" * 64},
            "phase": U7,
            "status": "ACTIVE",
            "recovery_required": False,
        }

        @classmethod
        def read(cls):
            return cls.document

        @classmethod
        def write(cls, document):
            cls.document = document

    class Backup:
        work_root = work
        create_called = False

        @staticmethod
        def measure_archive_size(_transaction_id: str) -> int:
            return 1_000_000

        @classmethod
        def create(cls, _directory: int, _transaction_id: str):
            cls.create_called = True
            raise AssertionError("real backup write must not start")

    @contextmanager
    def transaction_directory(*_args, **_kwargs):
        fd = os.open(usb, os.O_RDONLY | os.O_DIRECTORY)
        try:
            yield None, fd
        finally:
            os.close(fd)

    monkeypatch.setattr(mounted_media, "_open_transaction_directory", transaction_directory)

    def fake_record(document, **event):
        event = {
            **event,
            "actual_written_bytes": event.get("actual_written_bytes"),
            "available_bytes_after": event.get("available_bytes_after"),
        }
        return {**document, "usb_capacity_events": [event]}

    monkeypatch.setattr(mounted_media, "record_usb_capacity_event", fake_record)
    monkeypatch.setattr(
        mounted_media.os,
        "fstatvfs",
        lambda _fd: SimpleNamespace(f_frsize=4096, f_bavail=1),
    )

    provider = mounted_media.HaMountedBackupProvider(
        store=Store(),
        mountpoint=usb,
        internal_storage=internal,
        backup=Backup(),
        verify_quiesced=lambda: True,
    )

    with pytest.raises(UpdaterV2Error, match="ha_data_backup_usb_space_insufficient"):
        provider.create_consistent_backup(transaction_id_sha256=txid)
    assert Backup.create_called is False
    event = Store.document["usb_capacity_events"][-1]
    assert event["operation"] == "protected_data_backup"
    assert event["capacity_pass"] is False
    assert event["actual_written_bytes"] is None
