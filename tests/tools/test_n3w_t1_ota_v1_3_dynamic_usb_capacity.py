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
from n3w_t1_core_updater_ha_usb_media import (
    USB_MEDIA_MIN_CAPACITY_BYTES,
    RemovableDeviceCandidate,
    classify_candidate,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


def test_v13_architecture_freezes_16gb_media_and_dynamic_per_operation_capacity() -> None:
    text = (
        REPO
        / "docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md"
    ).read_text(encoding="utf-8")
    assert "16,000,000,000 bytes" in text
    assert "每个实际写入动作" in text
    assert "前代镜像先测量，再备份" in text
    assert "受保护数据备份单独动态准入" in text
    assert "固定常量只能描述固定开销" in text


def test_16gb_physical_media_minimum_is_not_a_transaction_reserve() -> None:
    base = dict(
        public_fingerprint="a" * 64,
        newly_inserted=True,
        removable=True,
        mass_storage=True,
        read_only=False,
        is_root_device=False,
        backs_production_mount=False,
        display_identity_matches=True,
    )
    assert classify_candidate(
        RemovableDeviceCandidate(
            **base,
            capacity_bytes=USB_MEDIA_MIN_CAPACITY_BYTES,
        )
    ) == ()
    assert "below_minimum_capacity" in classify_candidate(
        RemovableDeviceCandidate(
            **base,
            capacity_bytes=USB_MEDIA_MIN_CAPACITY_BYTES - 1,
        )
    )


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
    try:
        with pytest.raises(UpdaterV2Error, match="ha_usb_predecessor_space_insufficient"):
            mounted_media._prepare_archive(
                fd,
                "predecessor",
                "local/n3w-homeassistant:test",
                source,
                expected_size=4,
            )
    finally:
        os.close(fd)

    assert source_opened is False


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

        @staticmethod
        def read():
            return {
                "transaction_id_sha256": txid,
                "usb_binding_mode": "existing_filesystem",
                "predecessor_start": {"launch_sha256": "d" * 64},
                "phase": "U7_RECOVERY_POINT",
                "status": "ACTIVE",
                "recovery_required": False,
            }

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
