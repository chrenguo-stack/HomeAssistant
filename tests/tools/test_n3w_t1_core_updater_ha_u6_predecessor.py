from __future__ import annotations

import copy
import inspect
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import n3w_t1_core_updater_ha_capacity as capacity
import n3w_t1_core_updater_ha_prepare_host as host
from n3w_t1_core_updater_ha_install import HaUsbU6PredecessorController
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import request_install
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U2,
    U3,
    U4,
    U5,
    U6,
    new_transaction,
    transition,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


CURRENT = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
TARGET_SHA = "1" * 64
TARGET_SIZE = 835_309_535
FINGERPRINT = "a" * 64
USB_UUID = "12345678-1234-5678-1234-567812345678"


def target_record() -> ImageRecoveryRecord:
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


def predecessor_record() -> ImageRecoveryRecord:
    return ImageRecoveryRecord(
        kind="predecessor",
        image_ref=CURRENT,
        archive_sha256="5" * 64,
        archive_size_bytes=600_000_000,
        portable_identity_sha256="6" * 64,
        platform="linux/arm64",
        verified=True,
        fsynced=True,
    )


def u5_transaction() -> dict[str, object]:
    tx = new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={
            "portable_identity_sha256": "2" * 64,
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": "ha-2026.10.4-u6-test",
            "manifest_sha256": "3" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=TARGET_SIZE,
        created_at_unix=1_800_200_000,
    )
    tx = transition(tx, U1, updated_at_unix=1_800_200_001)
    tx = transition(
        tx,
        U2,
        updates={
            "usb_device_identity_public_fingerprint": FINGERPRINT,
            "usb_filesystem_uuid": USB_UUID,
            "usb_measured_usable_bytes": 16 * 1024**3,
            "usb_mount_authority": f"observed_filesystem_uuid:{USB_UUID}",
            "usb_capacity_verified": True,
        },
        updated_at_unix=1_800_200_002,
    )
    tx = transition(tx, U3, updated_at_unix=1_800_200_003)
    tx = transition(
        tx,
        U4,
        updates={"target_artifact_verified": True},
        updated_at_unix=1_800_200_004,
    )
    return request_install(tx, target=target_record())


class MemoryStore:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = copy.deepcopy(document)
        self.writes: list[dict[str, object]] = []

    def read(self):
        return copy.deepcopy(self.document)

    def write(self, document):
        self.document = copy.deepcopy(document)
        self.writes.append(copy.deepcopy(document))


class FakeBackend:
    def __init__(self, *, fail_export: bool = False) -> None:
        self.media = PreparedUsbMedia(
            locator="/dev/sdz",
            public_fingerprint=FINGERPRINT,
            filesystem_uuid=USB_UUID,
            measured_usable_bytes=16 * 1024**3,
            mount_path="/run/n3w-t1-ota/media/test",
        )
        self.fail_export = fail_export
        self.synced_phases: list[str] = []
        self.export_seen_phase: str | None = None
        self.prepare_calls = 0

    def resolve_transaction_media(self, transaction, *, write_required):
        assert write_required is True
        return self.media

    def verify_prepared_target(self, *, transaction, media):
        assert media is self.media
        return target_record()

    def install_capacity_revalidation(self, transaction, media):
        return capacity.compute_install_revalidation(
            target_artifact_bytes=TARGET_SIZE,
            predecessor_recovery_budget_bytes=2 * 1024**3,
            ha_data_measured_bytes=512 * 1024**2,
            observed_usb_free_bytes=8 * 1024**3,
        )

    def sync_transaction_metadata(self, transaction, media):
        self.synced_phases.append(str(transaction["phase"]))

    def prepare_predecessor_recovery(self, *, transaction, media):
        self.prepare_calls += 1
        self.export_seen_phase = str(transaction["phase"])
        if self.fail_export:
            raise UpdaterV2Error("synthetic_export_failed")
        return predecessor_record()

    def verify_prepared_predecessor(self, *, transaction, media):
        return predecessor_record()


def test_u6_controller_durably_enters_u6_before_export_and_never_enters_u7():
    store = MemoryStore(u5_transaction())
    backend = FakeBackend()
    result = HaUsbU6PredecessorController(
        transaction_store=store,
        backend=backend,
    ).prepare_or_resume()

    assert result.transaction["phase"] == U6
    assert result.resumed_from_u6 is False
    assert result.predecessor == predecessor_record()
    assert backend.synced_phases == [U6]
    assert backend.export_seen_phase == U6
    assert store.document["phase"] == U6
    assert store.document["authorization_claimed"] is False
    assert store.document["authorization_consumed"] is False
    assert store.document["predecessor_recovery_verified"] is False
    assert store.document["predecessor_recovery_identity"] is None


def test_u6_export_failure_leaves_explicit_resumable_u6_state():
    store = MemoryStore(u5_transaction())
    backend = FakeBackend(fail_export=True)

    with pytest.raises(UpdaterV2Error, match="synthetic_export_failed"):
        HaUsbU6PredecessorController(
            transaction_store=store,
            backend=backend,
        ).prepare_or_resume()

    assert store.document["phase"] == U6
    assert backend.synced_phases == [U6]
    assert store.document["authorization_claimed"] is False
    assert store.document["authorization_consumed"] is False


def test_u6_resume_does_not_repeat_phase_transition():
    transaction = transition(
        u5_transaction(),
        U6,
        updated_at_unix=1_800_200_006,
    )
    store = MemoryStore(transaction)
    backend = FakeBackend()

    result = HaUsbU6PredecessorController(
        transaction_store=store,
        backend=backend,
    ).prepare_or_resume()

    assert result.resumed_from_u6 is True
    assert result.transaction["phase"] == U6
    assert backend.synced_phases == []
    assert backend.prepare_calls == 1
    assert store.writes == []


def test_u6_controller_rejects_any_pre_u9_authorization_claim():
    transaction = u5_transaction()
    transaction["authorization_claimed"] = True
    transaction["authorization_consumed"] = True
    transaction["authorization_id_sha256"] = "9" * 64
    store = MemoryStore(transaction)

    with pytest.raises(UpdaterV2Error, match="authorization_state_invalid"):
        HaUsbU6PredecessorController(
            transaction_store=store,
            backend=FakeBackend(),
        ).prepare_or_resume()


def test_predecessor_stream_pipeline_uses_fixed_argv_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    class Pipe:
        def close(self):
            return None

    class Process:
        def __init__(self, argv, **kwargs):
            calls.append(tuple(argv))
            self.stdout = Pipe() if argv[0] == "docker" else None
            self.returncode = 0
            if argv[0] == "gzip":
                kwargs["stdout"].write(b"synthetic-compressed-archive")

        def wait(self, timeout=None):
            return self.returncode

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(host.subprocess, "Popen", Process)
    destination = tmp_path / "predecessor.tar.gz"

    host.SubprocessPrepareBackend._stream_predecessor_archive(
        CURRENT,
        destination,
    )

    assert destination.read_bytes() == b"synthetic-compressed-archive"
    assert calls == [
        ("docker", "image", "save", CURRENT),
        ("gzip", "-n", "-c"),
    ]
    source = inspect.getsource(
        host.SubprocessPrepareBackend._stream_predecessor_archive
    )
    assert "shell=True" not in source
    assert "docker system prune" not in source
    assert "docker image prune" not in source


def test_u6_source_slice_has_no_ha_stop_u7_or_u9_transition() -> None:
    source = inspect.getsource(HaUsbU6PredecessorController)
    assert "systemctl" not in source
    assert "U7" not in source
    assert "U9" not in source
    assert "authorization_claimed" in source
    assert "authorization_consumed" in source
