from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import HaInstallMaterials
from n3w_t1_core_updater_ha_usb_media import (
    USB_FILESYSTEM,
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    UsbCapacityReport,
    require_same_filesystem_uuid,
)
from n3w_t1_core_updater_ha_usb_state import (
    prepared_image_materials,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


@dataclass(frozen=True, slots=True)
class HaInstallSpaceBudget:
    """Additional space still needed at the current step, excluding existing files."""

    usb_install_bytes: int
    usb_recovery_bytes: int
    internal_install_bytes: int
    internal_recovery_bytes: int


def _command_json(*argv: str) -> dict[str, Any]:
    try:
        result = subprocess.run(argv, capture_output=True, check=True, timeout=10)
        value = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise UpdaterV2Error("ha_usb_mount_identity_unavailable") from error
    if not isinstance(value, dict):
        raise UpdaterV2Error("ha_usb_mount_identity_unavailable")
    return value


def _usb_devices(
    rows: list[dict[str, Any]], *, usb_parent: bool = False, parent_disk: str | None = None
) -> Iterator[tuple[dict[str, Any], bool, str | None]]:
    for row in rows:
        if not isinstance(row, dict):
            raise UpdaterV2Error("ha_usb_device_inventory_invalid")
        is_usb = usb_parent or row.get("tran") == "usb"
        disk = row.get("maj:min") if row.get("type") == "disk" else parent_disk
        yield row, is_usb, disk
        children = row.get("children", [])
        if not isinstance(children, list):
            raise UpdaterV2Error("ha_usb_device_inventory_invalid")
        yield from _usb_devices(children, usb_parent=is_usb, parent_disk=disk)


def _device_number(value: int) -> str:
    return f"{os.major(value)}:{os.minor(value)}"


def _protected_devices(internal_storage: Path) -> set[str]:
    return {
        _device_number(os.stat("/").st_dev),
        _device_number(internal_storage.stat().st_dev),
    }


def _mount_device(mountpoint: Path, expected_uuid: str, protected: set[str]) -> str:
    mounts = _command_json(
        "findmnt", "--json", "--mountpoint", str(mountpoint),
        "--output", "TARGET,FSTYPE,OPTIONS,MAJ:MIN,FSROOT,UUID",
    ).get("filesystems")
    if not isinstance(mounts, list) or len(mounts) != 1 or not isinstance(mounts[0], dict):
        raise UpdaterV2Error("ha_usb_original_mount_not_unique")
    mount = mounts[0]
    options = mount.get("options")
    device = mount.get("maj:min")
    if (
        mount.get("target") != str(mountpoint)
        or mount.get("fstype") != USB_FILESYSTEM
        or mount.get("fsroot") != "/"
        or not isinstance(options, str)
        or "rw" not in options.split(",")
        or not isinstance(device, str)
    ):
        raise UpdaterV2Error("ha_usb_original_mount_not_writable")
    require_same_filesystem_uuid(expected_uuid, mount.get("uuid"))
    devices = _command_json(
        "lsblk", "--json", "--output", "NAME,TYPE,TRAN,MAJ:MIN,UUID"
    ).get("blockdevices")
    if not isinstance(devices, list):
        raise UpdaterV2Error("ha_usb_device_inventory_invalid")
    inventory = list(_usb_devices(devices))
    matching = [
        (row, is_usb, disk)
        for row, is_usb, disk in inventory
        if isinstance(row.get("uuid"), str) and row["uuid"].lower() == expected_uuid
    ]
    if len(matching) != 1:
        raise UpdaterV2Error("ha_usb_original_filesystem_not_unique")
    row, is_usb, disk = matching[0]
    if (
        not is_usb or row.get("type") not in {"disk", "part"}
        or row.get("maj:min") != device or not isinstance(disk, str)
        or device in protected
        or any(
            parent == disk and entry.get("maj:min") in protected
            for entry, _, parent in inventory
        )
    ):
        raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
    return device


def _verify_archive(directory: int, name: str, record: ImageRecoveryRecord) -> None:
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_dev != os.fstat(directory).st_dev
            or before.st_size != record.archive_size_bytes
        ):
            raise UpdaterV2Error("ha_usb_recovery_archive_file_invalid")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining > 0:
            block = os.read(fd, min(1024 * 1024, remaining))
            if not block:
                raise UpdaterV2Error("ha_usb_recovery_archive_file_changed")
            digest.update(block)
            remaining -= len(block)
        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if (
            not os.path.samestat(before, after)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise UpdaterV2Error("ha_usb_recovery_archive_file_changed")
        if digest.hexdigest() != record.archive_sha256:
            raise UpdaterV2Error("ha_usb_recovery_archive_digest_mismatch")
    finally:
        os.close(fd)


class HaMountedInstallMaterialVerifier:
    """Read-only verification of archives already materialized by host preparation."""

    def __init__(
        self,
        *,
        mountpoint: Path,
        internal_storage: Path,
        budget: Callable[[dict[str, Any]], HaInstallSpaceBudget],
        verify_prestate: Callable[[dict[str, Any]], bool],
    ) -> None:
        self.mountpoint = mountpoint
        self.internal_storage = internal_storage
        self.budget = budget
        self.verify_prestate = verify_prestate

    def verify_install_materials(self, transaction: dict[str, Any]) -> HaInstallMaterials:
        document = validate_transaction_document(transaction)
        if document.get("usb_binding_mode") != "existing_filesystem":
            raise UpdaterV2Error("ha_usb_existing_filesystem_binding_required")
        target, predecessor = prepared_image_materials(document)
        expected_uuid = document["usb_filesystem_uuid"].lower()
        try:
            protected = _protected_devices(self.internal_storage)
            device = _mount_device(self.mountpoint, expected_uuid, protected)
            with ExitStack() as stack:
                fd = os.open(self.mountpoint, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                stack.callback(os.close, fd)
                mount_stat = os.fstat(fd)
                if _device_number(mount_stat.st_dev) != device:
                    raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
                directory = fd
                opened_directories = []
                for name in ("N3W-OTA", document["transaction_id_sha256"]):
                    parent = directory
                    directory = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                    )
                    stack.callback(os.close, directory)
                    binding = os.fstat(directory)
                    if binding.st_dev != mount_stat.st_dev:
                        raise UpdaterV2Error("ha_usb_transaction_directory_off_device")
                    opened_directories.append((parent, name, binding))
                _verify_archive(directory, "target.tar", target)
                _verify_archive(directory, "predecessor.tar", predecessor)
                capacity = self._capacity(fd, self.budget(document))
                prestate = self.verify_prestate(document)
                for parent, name, binding in opened_directories:
                    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if not os.path.samestat(binding, current):
                        raise UpdaterV2Error("ha_usb_transaction_directory_changed")
                if (
                    _protected_devices(self.internal_storage) != protected
                    or _mount_device(self.mountpoint, expected_uuid, protected) != device
                    or not os.path.samestat(mount_stat, self.mountpoint.stat())
                ):
                    raise UpdaterV2Error("ha_usb_original_mount_changed")
        except OSError as error:
            raise UpdaterV2Error("ha_usb_original_material_unavailable") from error
        return HaInstallMaterials(expected_uuid, target, predecessor, capacity, prestate)

    def _capacity(self, fd: int, budget: HaInstallSpaceBudget) -> UsbCapacityReport:
        values = (
            budget.usb_install_bytes, budget.usb_recovery_bytes,
            budget.internal_install_bytes, budget.internal_recovery_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise UpdaterV2Error("ha_usb_install_space_budget_invalid")
        usb = os.fstatvfs(fd)
        internal = os.statvfs(self.internal_storage)
        usable = (usb.f_blocks - usb.f_bfree + usb.f_bavail) * usb.f_frsize
        required = max(values[:2])
        floor = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
        space_ok = (
            (usb.f_bavail * usb.f_frsize) >= required
            and (internal.f_bavail * internal.f_frsize) >= max(values[2:])
        )
        return UsbCapacityReport(
            measured_usable_bytes=usable,
            required_bytes=required,
            measured_floor_bytes=floor,
            measured_floor_pass=usable >= floor,
            transaction_formula_pass=space_ok,
            capacity_pass=usable >= floor and space_ok,
        )
