from __future__ import annotations

from pathlib import Path

import pytest

from n3w_t1_core_updater_ha_prepare import (
    HaUsbPrepareController,
    HostUsbCandidate,
    PreparedUsbMedia,
    PrepareStateStore,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import record_media_bound, request_prepare
from n3w_t1_core_updater_ha_usb_media import (
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    FormatAuthorization,
    UsbCapacityInputs,
    UsbCapacityReport,
)
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U4,
    HaUsbStateStore,
    new_transaction,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error

CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
RELEASE = "homeassistant-2026.10.4"
TARGET_SHA = "1" * 64
UUID = "12345678-1234-5678-1234-567812345678"


def candidate(
    fingerprint: str,
    *,
    locator: str = "/dev/sdz",
    model: str = "Synthetic USB",
    capacity: int = 16 * 1024**3,
    root: bool = False,
    mounted: bool = False,
    read_only: bool = False,
) -> HostUsbCandidate:
    return HostUsbCandidate(
        locator=locator,
        public_fingerprint=fingerprint,
        display_model=model,
        display_capacity_bytes=capacity,
        newly_inserted=True,
        removable=True,
        mass_storage=True,
        read_only=read_only,
        is_root_device=root,
        backs_production_mount=mounted,
    )


class FakeBackend:
    def __init__(self, tmp_path: Path) -> None:
        self.items: tuple[HostUsbCandidate, ...] = ()
        self.formatted = 0
        self.prepared = 0
        self.aborted = 0
        self.reopened = 0
        self.metadata_syncs: list[str] = []
        self.fail_prepare_once = False
        self.media_available = True
        self.last_media: PreparedUsbMedia | None = None
        self.measured = 16 * 1024**3
        self.capacity = UsbCapacityInputs(
            target_artifact_bytes=1 * 1024**3,
            predecessor_recovery_worst_case_bytes=2 * 1024**3,
            ha_data_backup_worst_case_bytes=3 * 1024**3,
            transaction_metadata_and_working_bytes=1 * 1024**3,
            removable_media_reserve_bytes=1 * 1024**3,
        )
        self.mount = tmp_path / "media"

    def inventory(self) -> tuple[HostUsbCandidate, ...]:
        return self.items

    def capacity_inputs(self, transaction):
        return self.capacity

    def format_and_mount(
        self,
        *,
        candidate: HostUsbCandidate,
        transaction_id_sha256: str,
    ) -> PreparedUsbMedia:
        self.formatted += 1
        self.mount.mkdir(exist_ok=True)
        self.last_media = PreparedUsbMedia(
            locator=candidate.locator,
            public_fingerprint=candidate.public_fingerprint,
            filesystem_uuid=UUID,
            measured_usable_bytes=self.measured,
            mount_path=str(self.mount),
        )
        return self.last_media

    def reopen_bound_media(self, transaction):
        self.reopened += 1
        if not self.media_available:
            return None
        return self.last_media

    def sync_transaction_metadata(self, transaction, media) -> None:
        self.metadata_syncs.append(transaction["phase"])

    def prepare_target(
        self,
        *,
        transaction,
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        self.prepared += 1
        if self.fail_prepare_once:
            self.fail_prepare_once = False
            raise UpdaterV2Error("synthetic_prepare_interrupted")
        return ImageRecoveryRecord(
            kind="target",
            image_ref=TARGET,
            archive_sha256=TARGET_SHA,
            archive_size_bytes=4096,
            portable_identity_sha256="2" * 64,
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        )

    def abort_prepared_media(self, media: PreparedUsbMedia) -> None:
        self.aborted += 1


def transaction_store(tmp_path: Path) -> HaUsbStateStore:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    store = HaUsbStateStore(root)
    document = new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={"runtime_image_id": "sha256:" + "a" * 64},
        target_manifest_identity={
            "release_identity": RELEASE,
            "target_manifest_sha256": "b" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=4096,
        created_at_unix=1_800_000_000,
    )
    store.write(request_prepare(document))
    return store


def controller(tmp_path: Path):
    store = transaction_store(tmp_path)
    backend = FakeBackend(tmp_path)
    prepare = PrepareStateStore(store.root)
    value = HaUsbPrepareController(
        transaction_store=store,
        prepare_store=prepare,
        backend=backend,
    )
    document = store.read()
    assert document is not None
    assert document["phase"] == U1
    return value, backend, store, document


def test_prepare_records_inserted_baseline_and_requires_new_usb(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    old = candidate("a" * 64, locator="/dev/sdy")
    backend.items = (old,)

    value.begin(document)
    assert value.refresh_candidate() == {
        "phase": "USB_REQUIRED",
        "progress_percent": None,
        "error_code": None,
        "usb_candidate": None,
        "usb_confirmation_required": False,
    }
    assert backend.formatted == 0

    new = candidate("b" * 64)
    backend.items = (old, new)
    status = value.refresh_candidate()
    assert status["phase"] == "USB_REQUIRED_CONFIRMATION"
    assert status["usb_confirmation_required"] is True
    assert status["usb_candidate"] == {
        "public_fingerprint": "b" * 64,
        "display_model": "Synthetic USB",
        "display_capacity_bytes": 16 * 1024**3,
    }
    assert backend.formatted == 0


def test_multiple_new_usb_devices_fail_closed_before_format(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate("b" * 64, locator="/dev/sdy"),
        candidate("c" * 64, locator="/dev/sdz"),
    )

    status = value.refresh_candidate()
    assert status["phase"] == "ERROR"
    assert status["error_code"] == "usb_multiple_eligible_devices"
    assert backend.formatted == 0


def test_root_or_mounted_device_never_becomes_confirmation_candidate(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate("b" * 64, root=True),
        candidate("c" * 64, locator="/dev/sdy", mounted=True),
    )

    status = value.refresh_candidate()
    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_confirmation_reenumerates_and_rejects_identity_drift(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    assert value.refresh_candidate()["usb_confirmation_required"] is True

    backend.items = (candidate("c" * 64),)
    with pytest.raises(
        UpdaterV2Error,
        match="usb_confirmation_candidate_drift",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0


def test_confirmation_success_advances_exactly_to_u4(tmp_path: Path) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()

    status = value.confirm_and_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert final["authorization_claimed"] is False
    assert final["authorization_consumed"] is False
    assert final["target_artifact_verified"] is True
    assert final["usb_capacity_verified"] is True
    assert final["usb_device_identity_public_fingerprint"] == "b" * 64
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 1
    assert backend.prepared == 1
    assert backend.aborted == 0
    assert backend.metadata_syncs == [
        "U2_USB_QUALIFIED_FORMATTED_BOUND",
        "U3_TARGET_DOWNLOADING_VERIFYING",
        "U4_READY_TO_INSTALL",
    ]


def test_capacity_formula_failure_aborts_media_and_never_enters_u2(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.measured = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
    backend.capacity = UsbCapacityInputs(
        target_artifact_bytes=4 * 1024**3,
        predecessor_recovery_worst_case_bytes=4 * 1024**3,
        ha_data_backup_worst_case_bytes=4 * 1024**3,
        transaction_metadata_and_working_bytes=2 * 1024**3,
        removable_media_reserve_bytes=1 * 1024**3,
    )

    with pytest.raises(UpdaterV2Error, match="ha_usb_capacity_not_verified"):
        value.confirm_and_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U1
    assert backend.formatted == 1
    assert backend.prepared == 0
    assert backend.aborted == 1
    next_status = value.refresh_candidate()
    assert next_status["phase"] == "USB_REQUIRED"
    assert next_status["usb_candidate"] is None


def test_confirmation_without_published_candidate_does_not_format(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)

    with pytest.raises(
        UpdaterV2Error,
        match="usb_destructive_confirmation_not_ready",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0


def test_u3_resume_reopens_same_bound_media_without_reformat(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.fail_prepare_once = True

    with pytest.raises(UpdaterV2Error, match="synthetic_prepare_interrupted"):
        value.confirm_and_prepare()

    interrupted = store.read()
    assert interrupted is not None
    assert interrupted["phase"] == "U3_TARGET_DOWNLOADING_VERIFYING"
    assert backend.formatted == 1

    status = value.resume_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 1
    assert backend.reopened == 1
    assert backend.prepared == 2


def test_resume_waits_for_same_bound_media_instead_of_formatting_another(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.fail_prepare_once = True

    with pytest.raises(UpdaterV2Error):
        value.confirm_and_prepare()
    backend.media_available = False
    backend.items = (candidate("c" * 64, locator="/dev/sdy"),)

    with pytest.raises(UpdaterV2Error, match="usb_bound_media_unavailable"):
        value.resume_prepare()

    interrupted = store.read()
    assert interrupted is not None
    assert interrupted["phase"] == "U3_TARGET_DOWNLOADING_VERIFYING"
    assert backend.formatted == 1
    assert backend.reopened == 1


def test_preexisting_mounted_usb_cannot_become_fresh_by_unmount_only(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    preexisting = candidate(
        "d" * 64,
        locator="/dev/sdy",
        mounted=True,
    )
    backend.items = (preexisting,)
    value.begin(document)

    backend.items = (
        candidate(
            "d" * 64,
            locator="/dev/sdy",
            mounted=False,
        ),
    )
    status = value.refresh_candidate()

    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_raw_capacity_below_floor_never_formats_media(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate(
            "e" * 64,
            capacity=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES - 1,
        ),
    )
    status = value.refresh_candidate()
    assert status["usb_confirmation_required"] is True

    with pytest.raises(
        UpdaterV2Error,
        match="usb_raw_capacity_below_floor",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0
    next_status = value.refresh_candidate()
    assert next_status["phase"] == "USB_REQUIRED"
    assert next_status["usb_candidate"] is None


def test_read_only_usb_never_becomes_confirmation_candidate(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("f" * 64, read_only=True),)

    status = value.refresh_candidate()

    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_u2_resume_uses_bound_media_without_reformat(tmp_path: Path) -> None:
    value, backend, store, document = controller(tmp_path)
    backend.last_media = PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint="b" * 64,
        filesystem_uuid=UUID,
        measured_usable_bytes=16 * 1024**3,
        mount_path=str(backend.mount),
    )
    authorization = FormatAuthorization(
        public_fingerprint="b" * 64,
        confirmation_verified=True,
        filesystem="ext4",
        label="N3W-UPDATE",
    )
    capacity = UsbCapacityReport(
        measured_usable_bytes=16 * 1024**3,
        required_bytes=8 * 1024**3,
        measured_floor_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        measured_floor_pass=True,
        transaction_formula_pass=True,
        capacity_pass=True,
    )
    u2 = record_media_bound(
        document,
        format_authorization=authorization,
        filesystem_uuid=UUID,
        measured_usable_bytes=capacity.measured_usable_bytes,
        capacity_report=capacity,
    )
    store.write(u2)

    status = value.resume_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 0
    assert backend.reopened == 1
    assert backend.metadata_syncs == [
        "U2_USB_QUALIFIED_FORMATTED_BOUND",
        "U3_TARGET_DOWNLOADING_VERIFYING",
        "U4_READY_TO_INSTALL",
    ]

rom __future__ import annotations

from pathlib import Path

import pytest

from n3w_t1_core_updater_ha_prepare import (
    HaUsbPrepareController,
    HostUsbCandidate,
    PreparedUsbMedia,
    PrepareStateStore,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import record_media_bound, request_prepare
from n3w_t1_core_updater_ha_usb_media import (
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    FormatAuthorization,
    UsbCapacityInputs,
    UsbCapacityReport,
)
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U4,
    HaUsbStateStore,
    new_transaction,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error

CURRENT = "local/n3w-homeassistant:2026.10.0-aaaaaaaa"
TARGET = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
RELEASE = "homeassistant-2026.10.4"
TARGET_SHA = "1" * 64
UUID = "12345678-1234-5678-1234-567812345678"


def candidate(
    fingerprint: str,
    *,
    locator: str = "/dev/sdz",
    model: str = "Synthetic USB",
    capacity: int = 16 * 1024**3,
    root: bool = False,
    mounted: bool = False,
    read_only: bool = False,
) -> HostUsbCandidate:
    return HostUsbCandidate(
        locator=locator,
        public_fingerprint=fingerprint,
        display_model=model,
        display_capacity_bytes=capacity,
        newly_inserted=True,
        removable=True,
        mass_storage=True,
        read_only=read_only,
        is_root_device=root,
        backs_production_mount=mounted,
    )


class FakeBackend:
    def __init__(self, tmp_path: Path) -> None:
        self.items: tuple[HostUsbCandidate, ...] = ()
        self.formatted = 0
        self.prepared = 0
        self.aborted = 0
        self.reopened = 0
        self.metadata_syncs: list[str] = []
        self.fail_prepare_once = False
        self.media_available = True
        self.last_media: PreparedUsbMedia | None = None
        self.measured = 16 * 1024**3
        self.capacity = UsbCapacityInputs(
            target_artifact_bytes=1 * 1024**3,
            predecessor_recovery_worst_case_bytes=2 * 1024**3,
            ha_data_backup_worst_case_bytes=3 * 1024**3,
            transaction_metadata_and_working_bytes=1 * 1024**3,
            removable_media_reserve_bytes=1 * 1024**3,
        )
        self.mount = tmp_path / "media"

    def inventory(self) -> tuple[HostUsbCandidate, ...]:
        return self.items

    def capacity_inputs(self, transaction):
        return self.capacity

    def format_and_mount(
        self,
        *,
        candidate: HostUsbCandidate,
        transaction_id_sha256: str,
    ) -> PreparedUsbMedia:
        self.formatted += 1
        self.mount.mkdir(exist_ok=True)
        self.last_media = PreparedUsbMedia(
            locator=candidate.locator,
            public_fingerprint=candidate.public_fingerprint,
            filesystem_uuid=UUID,
            measured_usable_bytes=self.measured,
            mount_path=str(self.mount),
        )
        return self.last_media

    def reopen_bound_media(self, transaction):
        self.reopened += 1
        if not self.media_available:
            return None
        return self.last_media

    def sync_transaction_metadata(self, transaction, media) -> None:
        self.metadata_syncs.append(transaction["phase"])

    def prepare_target(
        self,
        *,
        transaction,
        media: PreparedUsbMedia,
    ) -> ImageRecoveryRecord:
        self.prepared += 1
        if self.fail_prepare_once:
            self.fail_prepare_once = False
            raise UpdaterV2Error("synthetic_prepare_interrupted")
        return ImageRecoveryRecord(
            kind="target",
            image_ref=TARGET,
            archive_sha256=TARGET_SHA,
            archive_size_bytes=4096,
            portable_identity_sha256="2" * 64,
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        )

    def abort_prepared_media(self, media: PreparedUsbMedia) -> None:
        self.aborted += 1


def transaction_store(tmp_path: Path) -> HaUsbStateStore:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    store = HaUsbStateStore(root)
    document = new_transaction(
        current_image_ref=CURRENT,
        current_image_identity={"runtime_image_id": "sha256:" + "a" * 64},
        target_manifest_identity={
            "release_identity": RELEASE,
            "target_manifest_sha256": "b" * 64,
        },
        target_image_ref=TARGET,
        target_archive_sha256=TARGET_SHA,
        target_archive_size=4096,
        created_at_unix=1_800_000_000,
    )
    store.write(request_prepare(document))
    return store


def controller(tmp_path: Path):
    store = transaction_store(tmp_path)
    backend = FakeBackend(tmp_path)
    prepare = PrepareStateStore(store.root)
    value = HaUsbPrepareController(
        transaction_store=store,
        prepare_store=prepare,
        backend=backend,
    )
    document = store.read()
    assert document is not None
    assert document["phase"] == U1
    return value, backend, store, document


def test_prepare_records_inserted_baseline_and_requires_new_usb(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    old = candidate("a" * 64, locator="/dev/sdy")
    backend.items = (old,)

    value.begin(document)
    assert value.refresh_candidate() == {
        "phase": "USB_REQUIRED",
        "progress_percent": None,
        "error_code": None,
        "usb_candidate": None,
        "usb_confirmation_required": False,
    }
    assert backend.formatted == 0

    new = candidate("b" * 64)
    backend.items = (old, new)
    status = value.refresh_candidate()
    assert status["phase"] == "USB_REQUIRED_CONFIRMATION"
    assert status["usb_confirmation_required"] is True
    assert status["usb_candidate"] == {
        "public_fingerprint": "b" * 64,
        "display_model": "Synthetic USB",
        "display_capacity_bytes": 16 * 1024**3,
    }
    assert backend.formatted == 0


def test_multiple_new_usb_devices_fail_closed_before_format(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate("b" * 64, locator="/dev/sdy"),
        candidate("c" * 64, locator="/dev/sdz"),
    )

    status = value.refresh_candidate()
    assert status["phase"] == "ERROR"
    assert status["error_code"] == "usb_multiple_eligible_devices"
    assert backend.formatted == 0


def test_root_or_mounted_device_never_becomes_confirmation_candidate(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate("b" * 64, root=True),
        candidate("c" * 64, locator="/dev/sdy", mounted=True),
    )

    status = value.refresh_candidate()
    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_confirmation_reenumerates_and_rejects_identity_drift(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    assert value.refresh_candidate()["usb_confirmation_required"] is True

    backend.items = (candidate("c" * 64),)
    with pytest.raises(
        UpdaterV2Error,
        match="usb_confirmation_candidate_drift",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0


def test_confirmation_success_advances_exactly_to_u4(tmp_path: Path) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()

    status = value.confirm_and_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert final["authorization_claimed"] is False
    assert final["authorization_consumed"] is False
    assert final["target_artifact_verified"] is True
    assert final["usb_capacity_verified"] is True
    assert final["usb_device_identity_public_fingerprint"] == "b" * 64
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 1
    assert backend.prepared == 1
    assert backend.aborted == 0
    assert backend.metadata_syncs == [
        "U2_USB_QUALIFIED_FORMATTED_BOUND",
        "U3_TARGET_DOWNLOADING_VERIFYING",
        "U4_READY_TO_INSTALL",
    ]


def test_capacity_formula_failure_aborts_media_and_never_enters_u2(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.measured = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
    backend.capacity = UsbCapacityInputs(
        target_artifact_bytes=4 * 1024**3,
        predecessor_recovery_worst_case_bytes=4 * 1024**3,
        ha_data_backup_worst_case_bytes=4 * 1024**3,
        transaction_metadata_and_working_bytes=2 * 1024**3,
        removable_media_reserve_bytes=1 * 1024**3,
    )

    with pytest.raises(UpdaterV2Error, match="ha_usb_capacity_not_verified"):
        value.confirm_and_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U1
    assert backend.formatted == 1
    assert backend.prepared == 0
    assert backend.aborted == 1


def test_confirmation_without_published_candidate_does_not_format(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)

    with pytest.raises(
        UpdaterV2Error,
        match="usb_destructive_confirmation_not_ready",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0


def test_u3_resume_reopens_same_bound_media_without_reformat(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.fail_prepare_once = True

    with pytest.raises(UpdaterV2Error, match="synthetic_prepare_interrupted"):
        value.confirm_and_prepare()

    interrupted = store.read()
    assert interrupted is not None
    assert interrupted["phase"] == "U3_TARGET_DOWNLOADING_VERIFYING"
    assert backend.formatted == 1

    status = value.resume_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 1
    assert backend.reopened == 1
    assert backend.prepared == 2


def test_resume_waits_for_same_bound_media_instead_of_formatting_another(
    tmp_path: Path,
) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()
    backend.fail_prepare_once = True

    with pytest.raises(UpdaterV2Error):
        value.confirm_and_prepare()
    backend.media_available = False
    backend.items = (candidate("c" * 64, locator="/dev/sdy"),)

    with pytest.raises(UpdaterV2Error, match="usb_bound_media_unavailable"):
        value.resume_prepare()

    interrupted = store.read()
    assert interrupted is not None
    assert interrupted["phase"] == "U3_TARGET_DOWNLOADING_VERIFYING"
    assert backend.formatted == 1
    assert backend.reopened == 1


def test_preexisting_mounted_usb_cannot_become_fresh_by_unmount_only(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    preexisting = candidate(
        "d" * 64,
        locator="/dev/sdy",
        mounted=True,
    )
    backend.items = (preexisting,)
    value.begin(document)

    backend.items = (
        candidate(
            "d" * 64,
            locator="/dev/sdy",
            mounted=False,
        ),
    )
    status = value.refresh_candidate()

    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_raw_capacity_below_floor_never_formats_media(tmp_path: Path) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (
        candidate(
            "e" * 64,
            capacity=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES - 1,
        ),
    )
    status = value.refresh_candidate()
    assert status["usb_confirmation_required"] is True

    with pytest.raises(
        UpdaterV2Error,
        match="usb_raw_capacity_below_floor",
    ):
        value.confirm_and_prepare()
    assert backend.formatted == 0


def test_read_only_usb_never_becomes_confirmation_candidate(
    tmp_path: Path,
) -> None:
    value, backend, _, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("f" * 64, read_only=True),)

    status = value.refresh_candidate()

    assert status["phase"] == "USB_REQUIRED"
    assert status["usb_candidate"] is None
    assert backend.formatted == 0


def test_u2_resume_uses_bound_media_without_reformat(tmp_path: Path) -> None:
    value, backend, store, document = controller(tmp_path)
    value.begin(document)
    backend.items = (candidate("b" * 64),)
    value.refresh_candidate()

    original_prepare = backend.prepare_target

    def fail_before_target(*, transaction, media):
        raise UpdaterV2Error("synthetic_stop_after_u2")

    backend.prepare_target = fail_before_target
    with pytest.raises(UpdaterV2Error, match="synthetic_stop_after_u2"):
        value.confirm_and_prepare()

    interrupted = store.read()
    assert interrupted is not None
    assert interrupted["phase"] == "U3_TARGET_DOWNLOADING_VERIFYING"
    assert backend.formatted == 1

    backend.prepare_target = original_prepare
    status = value.resume_prepare()

    final = store.read()
    assert final is not None
    assert final["phase"] == U4
    assert status["phase"] == "READY_TO_INSTALL"
    assert backend.formatted == 1
    assert backend.reopened == 1
