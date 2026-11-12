from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error


USB_MEASURED_USABLE_CAPACITY_MIN_BYTES = 14 * 1024**3
USB_FILESYSTEM = "ext4"
USB_LABEL = "N3W-UPDATE"
FORMAT_CONFIRMATION = "T1_HOMEASSISTANT_USB_FORMAT_ALL_DATA"


@dataclass(frozen=True)
class RemovableDeviceCandidate:
    public_fingerprint: str
    newly_inserted: bool
    removable: bool
    mass_storage: bool
    read_only: bool
    is_root_device: bool
    backs_production_mount: bool
    display_identity_matches: bool


@dataclass(frozen=True)
class FormatAuthorization:
    public_fingerprint: str
    confirmation_verified: bool
    filesystem: str = USB_FILESYSTEM
    label: str = USB_LABEL


@dataclass(frozen=True)
class UsbCapacityInputs:
    target_artifact_bytes: int
    predecessor_recovery_worst_case_bytes: int
    ha_data_backup_worst_case_bytes: int
    transaction_metadata_and_working_bytes: int
    removable_media_reserve_bytes: int

    def required_bytes(self) -> int:
        values = (
            self.target_artifact_bytes,
            self.predecessor_recovery_worst_case_bytes,
            self.ha_data_backup_worst_case_bytes,
            self.transaction_metadata_and_working_bytes,
            self.removable_media_reserve_bytes,
        )
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            for value in values
        ):
            raise UpdaterV2Error("usb_capacity_input_invalid")
        if (
            self.target_artifact_bytes <= 0
            or self.predecessor_recovery_worst_case_bytes <= 0
            or self.ha_data_backup_worst_case_bytes <= 0
        ):
            raise UpdaterV2Error("usb_capacity_primary_asset_invalid")
        return sum(values)


@dataclass(frozen=True)
class UsbCapacityReport:
    measured_usable_bytes: int
    required_bytes: int
    measured_floor_bytes: int
    measured_floor_pass: bool
    transaction_formula_pass: bool
    capacity_pass: bool

    def public(self) -> dict[str, int | bool]:
        return {
            "measured_usable_bytes": self.measured_usable_bytes,
            "required_bytes": self.required_bytes,
            "measured_floor_bytes": self.measured_floor_bytes,
            "measured_floor_pass": self.measured_floor_pass,
            "transaction_formula_pass": self.transaction_formula_pass,
            "capacity_pass": self.capacity_pass,
        }


def _validate_public_fingerprint(value: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise UpdaterV2Error("usb_public_fingerprint_invalid")
    return value


def classify_candidate(candidate: RemovableDeviceCandidate) -> tuple[str, ...]:
    _validate_public_fingerprint(candidate.public_fingerprint)
    reasons: list[str] = []
    if candidate.removable is not True:
        reasons.append("not_removable")
    if candidate.mass_storage is not True:
        reasons.append("not_mass_storage")
    if candidate.read_only is True:
        reasons.append("read_only")
    if candidate.is_root_device is True:
        reasons.append("root_device")
    if candidate.backs_production_mount is True:
        reasons.append("production_mount")
    if candidate.display_identity_matches is not True:
        reasons.append("display_identity_mismatch")
    return tuple(reasons)


def select_single_eligible_device(
    candidates: Iterable[RemovableDeviceCandidate],
) -> RemovableDeviceCandidate:
    items = tuple(candidates)
    if not items:
        raise UpdaterV2Error("usb_device_absent")
    eligible = [item for item in items if not classify_candidate(item)]
    if not eligible:
        raise UpdaterV2Error("usb_no_eligible_device")
    if len(eligible) != 1:
        raise UpdaterV2Error("usb_multiple_eligible_devices")
    return eligible[0]


def authorize_destructive_format(
    candidate: RemovableDeviceCandidate,
    confirmation: str,
) -> FormatAuthorization:
    if classify_candidate(candidate):
        raise UpdaterV2Error("usb_format_target_not_eligible")
    if confirmation != FORMAT_CONFIRMATION:
        raise UpdaterV2Error("usb_destructive_confirmation_missing")
    return FormatAuthorization(
        public_fingerprint=candidate.public_fingerprint,
        confirmation_verified=True,
    )


def assess_capacity(
    measured_usable_bytes: int,
    inputs: UsbCapacityInputs,
) -> UsbCapacityReport:
    if (
        not isinstance(measured_usable_bytes, int)
        or isinstance(measured_usable_bytes, bool)
        or measured_usable_bytes <= 0
    ):
        raise UpdaterV2Error("usb_measured_usable_bytes_invalid")
    required = inputs.required_bytes()
    floor_pass = (
        measured_usable_bytes >= USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
    )
    formula_pass = measured_usable_bytes >= required
    return UsbCapacityReport(
        measured_usable_bytes=measured_usable_bytes,
        required_bytes=required,
        measured_floor_bytes=USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
        measured_floor_pass=floor_pass,
        transaction_formula_pass=formula_pass,
        capacity_pass=floor_pass and formula_pass,
    )


def validate_filesystem_uuid(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpdaterV2Error("usb_filesystem_uuid_invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise UpdaterV2Error("usb_filesystem_uuid_invalid") from error
    canonical = str(parsed)
    if canonical != value.lower():
        raise UpdaterV2Error("usb_filesystem_uuid_not_canonical")
    return canonical


def require_same_filesystem_uuid(expected: str, observed: str) -> None:
    expected_uuid = validate_filesystem_uuid(expected)
    observed_uuid = validate_filesystem_uuid(observed)
    if expected_uuid != observed_uuid:
        raise UpdaterV2Error("usb_filesystem_uuid_mismatch")
