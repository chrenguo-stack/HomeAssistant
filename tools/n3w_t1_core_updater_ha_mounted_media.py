from __future__ import annotations

import ctypes
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, ContextManager

from n3w_t1_core_updater_ha_backup import (
    HA_DATABASE_NAME, HaDataBackupRecord, ProtectedHaDataBackup, backup_record_from_document,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import HaInstallMaterials, HaInternalSpace
from n3w_t1_core_updater_ha_usb_media import (
    USB_FILESYSTEM,
    USB_MEASURED_USABLE_CAPACITY_MIN_BYTES,
    UsbCapacityReport,
    require_same_filesystem_uuid,
)
from n3w_t1_core_updater_ha_usb_state import (
    HA_DATA_RESTORE_PHASES,
    TARGET_WRITES_POSSIBLE,
    U10,
    U7,
    HaUsbStateStore,
    prepared_image_materials,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error, canonical, sha256_bytes
from n3w_t1_portable_image_identity import (
    MAX_ARCHIVE_BYTES, PortableImageIdentity, PortableImageIdentityError, parse_verified_load_archive,
)


DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
RENAME_EXCHANGE = 2
ARCHIVE_BLOCK_BYTES = 1024 * 1024


def _directory_identity(parent: int, name: str) -> tuple[int, int]:
    fd = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    try:
        entry = os.fstat(fd)
        if entry.st_dev != os.fstat(parent).st_dev:
            raise UpdaterV2Error("ha_data_restore_directory_off_filesystem")
        return os.fstatvfs(fd).f_fsid, entry.st_ino
    finally:
        os.close(fd)


def _exchange_directories(first_parent: int, first: str, second_parent: int, second: str) -> None:
    # Linux renameat2 leaves neither directory name missing during the swap.
    exchange = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if exchange is None:
        raise UpdaterV2Error("ha_data_restore_atomic_exchange_unavailable")
    exchange.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    exchange.restype = ctypes.c_int
    if exchange(first_parent, os.fsencode(first), second_parent, os.fsencode(second), RENAME_EXCHANGE):
        raise OSError(ctypes.get_errno(), "HA data directory exchange failed")


@dataclass(frozen=True, slots=True)
class HaInstallSpaceBudget:
    """Additional space still needed at the current step, excluding existing files."""

    usb_install_bytes: int
    usb_recovery_bytes: int
    internal_install_bytes: int
    # Recovery overhead is additional to the measured image layers and HA restore workspace.
    internal_recovery_overhead_bytes: int


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


def bound_usb_device(expected_uuid: str, internal_storage: Path) -> dict[str, Any] | None:
    return _bound_usb_device(expected_uuid, _protected_devices(internal_storage))


def _bound_usb_device(expected_uuid: str, protected: set[str]) -> dict[str, Any] | None:
    devices = _command_json(
        "lsblk", "--json", "--paths", "--output", "NAME,TYPE,TRAN,MAJ:MIN,UUID,FSTYPE"
    ).get("blockdevices")
    if not isinstance(devices, list):
        raise UpdaterV2Error("ha_usb_device_inventory_invalid")
    inventory = list(_usb_devices(devices))
    matching = [
        (row, is_usb, disk)
        for row, is_usb, disk in inventory
        if isinstance(row.get("uuid"), str) and row["uuid"].lower() == expected_uuid
    ]
    if not matching:
        return None
    if len(matching) != 1:
        raise UpdaterV2Error("ha_usb_original_filesystem_not_unique")
    row, is_usb, disk = matching[0]
    if (
        not is_usb or row.get("type") not in {"disk", "part"}
        or not isinstance(row.get("maj:min"), str) or not isinstance(disk, str)
        or row["maj:min"] in protected
        or any(parent == disk and entry.get("maj:min") in protected for entry, _, parent in inventory)
    ):
        raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
    return row


def _mount_device(
    mountpoint: Path, expected_uuid: str, protected: set[str], *, allow_read_only: bool,
) -> str:
    mounts = _command_json(
        "findmnt", "--json", "--mountpoint", str(mountpoint),
        "--output", "TARGET,FSTYPE,OPTIONS,MAJ:MIN,FSROOT,UUID",
    ).get("filesystems")
    if not isinstance(mounts, list) or len(mounts) != 1 or not isinstance(mounts[0], dict):
        raise UpdaterV2Error("ha_usb_original_mount_not_unique")
    mount = mounts[0]
    options = mount.get("options")
    device = mount.get("maj:min")
    access_modes = {"rw", "ro"} if allow_read_only else {"rw"}
    if (
        mount.get("target") != str(mountpoint)
        or mount.get("fstype") != USB_FILESYSTEM
        or mount.get("fsroot") != "/"
        or not isinstance(options, str)
        or access_modes.isdisjoint(options.split(","))
        or not isinstance(device, str)
    ):
        reason = "ha_usb_original_mount_not_readable" if allow_read_only else "ha_usb_original_mount_not_writable"
        raise UpdaterV2Error(reason)
    require_same_filesystem_uuid(expected_uuid, mount.get("uuid"))
    row = _bound_usb_device(expected_uuid, protected)
    if row is None:
        raise UpdaterV2Error("ha_usb_original_filesystem_not_unique")
    if row["maj:min"] != device:
        raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
    return device


def _require_same_archive(directory: int, name: str, before: os.stat_result) -> None:
    after = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if (
        not os.path.samestat(before, after) or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise UpdaterV2Error("ha_usb_recovery_archive_file_changed")


@contextmanager
def _verified_archive(
    directory: int, name: str, record: ImageRecoveryRecord, *, for_load: bool = False,
) -> Iterator[tuple[int, list[bytes]]]:
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_dev != os.fstat(directory).st_dev
            or before.st_size != record.archive_size_bytes
            or (for_load and before.st_size > MAX_ARCHIVE_BYTES)
        ):
            raise UpdaterV2Error("ha_usb_recovery_archive_file_invalid")
        digest = hashlib.sha256()
        blocks = []
        for offset in range(0, before.st_size, ARCHIVE_BLOCK_BYTES):
            size = min(ARCHIVE_BLOCK_BYTES, before.st_size - offset)
            block = os.pread(fd, size, offset)
            if len(block) != size:
                raise UpdaterV2Error("ha_usb_recovery_archive_file_changed")
            digest.update(block)
            if for_load:
                blocks.append(hashlib.sha256(block).digest())
        _require_same_archive(directory, name, before)
        if digest.hexdigest() != record.archive_sha256:
            raise UpdaterV2Error("ha_usb_recovery_archive_digest_mismatch")
        yield fd, blocks
        _require_same_archive(directory, name, before)
    finally:
        os.close(fd)


def _verify_archive(directory: int, name: str, record: ImageRecoveryRecord) -> None:
    with _verified_archive(directory, name, record):
        pass


class _AuthenticatedArchiveReader(io.RawIOBase):
    """Read the pinned archive without serving any block whose bytes changed."""

    def __init__(self, fd: int, size: int, blocks: list[bytes]) -> None:
        self.fd = fd
        self.size = size
        self.blocks = blocks
        self.position = 0
        self.cached_index = -1
        self.cached_block = b""

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_CUR:
            offset += self.position
        elif whence == os.SEEK_END:
            offset += self.size
        elif whence != os.SEEK_SET:
            raise ValueError("invalid seek mode")
        if offset < 0:
            raise ValueError("negative archive position")
        self.position = offset
        return offset

    def readinto(self, buffer: bytearray | memoryview) -> int:
        remaining = min(len(buffer), self.size - self.position)
        copied = 0
        while remaining > 0:
            index, offset = divmod(self.position, ARCHIVE_BLOCK_BYTES)
            if index != self.cached_index:
                start = index * ARCHIVE_BLOCK_BYTES
                size = min(ARCHIVE_BLOCK_BYTES, self.size - start)
                block = os.pread(self.fd, size, start)
                if len(block) != size or hashlib.sha256(block).digest() != self.blocks[index]:
                    raise UpdaterV2Error("ha_usb_recovery_archive_file_changed")
                self.cached_index, self.cached_block = index, block
            count = min(remaining, len(self.cached_block) - offset)
            buffer[copied:copied + count] = self.cached_block[offset:offset + count]
            self.position += count
            copied += count
            remaining -= count
        return copied


def _authenticate_image(
    fd: int, blocks: list[bytes], record: ImageRecoveryRecord,
) -> tuple[PortableImageIdentity, int]:
    sizes: list[int] = []
    try:
        with io.BufferedReader(_AuthenticatedArchiveReader(fd, record.archive_size_bytes, blocks)) as source:
            identity = parse_verified_load_archive(
                source, archive_sha256=record.archive_sha256, archive_size_bytes=record.archive_size_bytes,
                expected_tag=record.image_ref, unpacked_sizes=sizes,
            )
    except PortableImageIdentityError as error:
        raise UpdaterV2Error(f"ha_usb_{record.kind}_archive_identity_invalid") from error
    if sha256_bytes(canonical(identity.to_dict())) != record.portable_identity_sha256:
        raise UpdaterV2Error(f"ha_usb_{record.kind}_portable_identity_drift")
    return identity, sum(sizes)


def _ha_restore_workspace_bytes(root: Path, device: int, block_size: int) -> int:
    info = root.lstat()
    if info.st_dev != device or not stat.S_ISDIR(info.st_mode):
        raise UpdaterV2Error("ha_usb_recovery_workspace_not_on_budgeted_filesystem")
    total = block_size
    sqlite_files = {}
    family = {HA_DATABASE_NAME, *(HA_DATABASE_NAME + suffix for suffix in ("-wal", "-journal", "-shm"))}

    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, dirs, files in os.walk(root, onerror=raise_walk_error, followlinks=False):
        for name in dirs + files:
            entry = (Path(directory) / name).lstat()
            if entry.st_dev != device:
                raise UpdaterV2Error("ha_usb_recovery_workspace_not_on_budgeted_filesystem")
            if not (stat.S_ISREG(entry.st_mode) or stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode)):
                raise UpdaterV2Error("ha_usb_recovery_workspace_file_unsupported")
            rounded = max(block_size, ((entry.st_size + block_size - 1) // block_size) * block_size)
            total += rounded
            if Path(directory) == root and name in family:
                sqlite_files[name] = rounded
    # A database with a WAL or other sidecar is validated using a private copy.
    if sqlite_files.keys() - {HA_DATABASE_NAME}:
        total += sum(sqlite_files.values())
    return total


@contextmanager
def _open_transaction_directory(
    mountpoint: Path, internal_storage: Path, document: dict[str, Any],
    *, allow_read_only: bool = False, create: bool = False,
) -> Iterator[tuple[int, int]]:
    expected_uuid = document["usb_filesystem_uuid"].lower()
    try:
        protected = _protected_devices(internal_storage)
        device = _mount_device(mountpoint, expected_uuid, protected, allow_read_only=allow_read_only)
        with ExitStack() as stack:
            fd = os.open(mountpoint, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            mount_stat = os.fstat(fd)
            if _device_number(mount_stat.st_dev) != device:
                raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
            directory = fd
            opened_directories = []
            for name in ("N3W-OTA", document["transaction_id_sha256"]):
                parent = directory
                if create:
                    try:
                        os.mkdir(name, 0o700, dir_fd=parent)
                    except FileExistsError:
                        pass
                    os.fsync(parent)
                directory = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                )
                stack.callback(os.close, directory)
                binding = os.fstat(directory)
                if binding.st_dev != mount_stat.st_dev:
                    raise UpdaterV2Error("ha_usb_transaction_directory_off_device")
                if create and (binding.st_uid != os.geteuid() or binding.st_mode & 0o022):
                    raise UpdaterV2Error("ha_usb_transaction_directory_not_protected")
                opened_directories.append((parent, name, binding))
            yield fd, directory
            for parent, name, binding in opened_directories:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not os.path.samestat(binding, current):
                    raise UpdaterV2Error("ha_usb_transaction_directory_changed")
            if (
                _protected_devices(internal_storage) != protected
                or _mount_device(
                    mountpoint, expected_uuid, protected, allow_read_only=allow_read_only,
                ) != device
                or not os.path.samestat(mount_stat, mountpoint.stat())
            ):
                raise UpdaterV2Error("ha_usb_original_mount_changed")
    except OSError as error:
        raise UpdaterV2Error("ha_usb_original_material_unavailable") from error


@contextmanager
def _open_preparation_archive(directory: int, name: str, flags: int) -> Iterator[BinaryIO]:
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    with os.fdopen(fd, "r+b" if flags & os.O_RDWR else "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077 or metadata.st_nlink != 1
            or metadata.st_dev != os.fstat(directory).st_dev
        ):
            raise UpdaterV2Error("ha_usb_preparation_archive_file_invalid")
        yield stream


def _prepare_archive(
    directory: int, kind: str, image_ref: str, source: Callable[[], ContextManager[BinaryIO]],
    *, limit: int, reserve: int, expected_sha256: str | None = None,
    validate: Callable[[PortableImageIdentity], None] | None = None,
) -> ImageRecoveryRecord:
    final = f"{kind}.tar"
    partial = f".{final}.part"

    def inspect(name: str) -> ImageRecoveryRecord:
        with _open_preparation_archive(directory, name, os.O_RDONLY) as stream:
            fd = stream.fileno()
            metadata = os.fstat(fd)
            if not 0 < metadata.st_size <= limit:
                raise UpdaterV2Error("ha_usb_preparation_archive_size_invalid")
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if expected_sha256 is not None and (digest != expected_sha256 or metadata.st_size != limit):
                raise UpdaterV2Error("ha_usb_preparation_target_rejected")
            stream.seek(0)
            try:
                identity = parse_verified_load_archive(
                    stream, archive_sha256=digest, archive_size_bytes=metadata.st_size, expected_tag=image_ref,
                )
            except PortableImageIdentityError as error:
                raise UpdaterV2Error("ha_usb_preparation_archive_identity_invalid") from error
            if validate is not None:
                validate(identity)
            os.fsync(fd)
            _require_same_archive(directory, name, metadata)
            return ImageRecoveryRecord(
                kind, image_ref, digest, metadata.st_size, sha256_bytes(canonical(identity.to_dict())),
                "linux/arm64", True, True,
            )

    try:
        record = inspect(final)
    except FileNotFoundError:
        with _open_preparation_archive(directory, partial, os.O_RDWR | os.O_CREAT) as output:
            output.truncate(0)
            free = os.fstatvfs(directory)
            if free.f_frsize * free.f_bavail < limit + reserve:
                raise UpdaterV2Error("ha_usb_preparation_space_insufficient")
            with source() as reader:
                written = 0
                while block := reader.read(min(ARCHIVE_BLOCK_BYTES, limit - written + 1)):
                    written += len(block)
                    if written > limit:
                        raise UpdaterV2Error("ha_usb_preparation_archive_size_invalid")
                    output.write(block)
            output.flush()
            os.fsync(output.fileno())
        record = inspect(partial)
        os.rename(partial, final, src_dir_fd=directory, dst_dir_fd=directory)
    os.fsync(directory)
    return record


def prepare_mounted_archives(
    mountpoint: Path, internal_storage: Path, document: dict[str, Any],
    *, target_source: Callable[[], ContextManager[BinaryIO]],
    predecessor_source: Callable[[], ContextManager[BinaryIO]],
    verify_predecessor: Callable[[PortableImageIdentity], None],
    max_predecessor_bytes: int, reserve: int,
) -> tuple[ImageRecoveryRecord, ImageRecoveryRecord]:
    with _open_transaction_directory(mountpoint, internal_storage, document, create=True) as (_, directory):
        target = _prepare_archive(
            directory, "target", document["target_image_ref"], target_source,
            limit=document["target_archive_size"], reserve=max_predecessor_bytes + reserve,
            expected_sha256=document["target_archive_sha256"],
        )
        predecessor = _prepare_archive(
            directory, "predecessor", document["current_image_ref"], predecessor_source,
            limit=max_predecessor_bytes, reserve=reserve, validate=verify_predecessor,
        )
        free = os.fstatvfs(directory)
        if free.f_frsize * free.f_bavail < reserve:
            raise UpdaterV2Error("ha_usb_preparation_space_insufficient")
    return target, predecessor


def measure_preparation_capacity(
    mountpoint: Path, internal_storage: Path, expected_uuid: str, required: int,
) -> UsbCapacityReport:
    device = _mount_device(mountpoint, expected_uuid, _protected_devices(internal_storage), allow_read_only=False)
    fd = os.open(mountpoint, DIRECTORY_FLAGS)
    try:
        if _device_number(os.fstat(fd).st_dev) != device:
            raise UpdaterV2Error("ha_usb_original_mount_device_mismatch")
        info = os.fstatvfs(fd)
    finally:
        os.close(fd)
    usable = (info.f_blocks - info.f_bfree + info.f_bavail) * info.f_frsize
    floor = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
    enough = info.f_bavail * info.f_frsize >= required
    return UsbCapacityReport(usable, required, floor, usable >= floor, enough, usable >= floor and enough)


class HaMountedInstallMaterialVerifier:
    """Read-only verification of archives already materialized by host preparation."""

    def __init__(
        self,
        *,
        mountpoint: Path,
        internal_storage: Path,
        image_storage: Path,
        ha_data_root: Path,
        budget: Callable[[dict[str, Any]], HaInstallSpaceBudget],
        verify_prestate: Callable[[dict[str, Any]], bool],
    ) -> None:
        self.mountpoint = mountpoint
        self.internal_storage = internal_storage
        self.image_storage = image_storage
        self.ha_data_root = ha_data_root
        self.budget = budget
        self.verify_prestate = verify_prestate
        self._verified_images: dict[ImageRecoveryRecord, int] = {}

    def verify_install_materials(self, transaction: dict[str, Any]) -> HaInstallMaterials:
        document = validate_transaction_document(transaction)
        if document.get("usb_binding_mode") != "existing_filesystem":
            raise UpdaterV2Error("ha_usb_existing_filesystem_binding_required")
        target, predecessor = prepared_image_materials(document)
        with _open_transaction_directory(self.mountpoint, self.internal_storage, document) as (
            mount, directory,
        ):
            unpacked = {}
            for record in (target, predecessor):
                name = f"{record.kind}.tar"
                if record in self._verified_images:
                    _verify_archive(directory, name, record)
                    unpacked[record] = self._verified_images[record]
                else:
                    with _verified_archive(directory, name, record, for_load=True) as (fd, blocks):
                        _, unpacked[record] = _authenticate_image(fd, blocks, record)
            prestate = self.verify_prestate(document)
            capacity, internal = self._capacity(mount, self.budget(document), unpacked[target], unpacked[predecessor])
        self._verified_images = unpacked
        return HaInstallMaterials(
            document["usb_filesystem_uuid"].lower(), target, predecessor, capacity, prestate, internal,
        )

    def _capacity(
        self, fd: int, budget: HaInstallSpaceBudget, target_bytes: int, predecessor_bytes: int,
    ) -> tuple[UsbCapacityReport, HaInternalSpace]:
        values = (
            budget.usb_install_bytes, budget.usb_recovery_bytes,
            budget.internal_install_bytes, budget.internal_recovery_overhead_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise UpdaterV2Error("ha_usb_install_space_budget_invalid")
        usb = os.fstatvfs(fd)
        try:
            device = self.internal_storage.stat().st_dev
            if self.image_storage.stat().st_dev != device:
                raise UpdaterV2Error("ha_usb_image_storage_not_on_budgeted_filesystem")
            internal = os.statvfs(self.internal_storage)
            if internal.f_frsize <= 0:
                raise UpdaterV2Error("ha_usb_install_space_unavailable")
            workspace = _ha_restore_workspace_bytes(self.ha_data_root, device, internal.f_frsize)
        except OSError as error:
            raise UpdaterV2Error("ha_usb_install_space_unavailable") from error
        space = HaInternalSpace(
            available_bytes=internal.f_bavail * internal.f_frsize,
            install_required_bytes=max(budget.internal_install_bytes, target_bytes),
            recovery_required_bytes=predecessor_bytes + workspace + budget.internal_recovery_overhead_bytes,
        )
        usable = (usb.f_blocks - usb.f_bfree + usb.f_bavail) * usb.f_frsize
        required = max(values[:2])
        floor = USB_MEASURED_USABLE_CAPACITY_MIN_BYTES
        space_ok = (
            (usb.f_bavail * usb.f_frsize) >= required
            and space.available_bytes >= space.install_required_bytes + space.recovery_required_bytes
        )
        return UsbCapacityReport(
            measured_usable_bytes=usable,
            required_bytes=required,
            measured_floor_bytes=floor,
            measured_floor_pass=usable >= floor,
            transaction_formula_pass=space_ok,
            capacity_pass=usable >= floor and space_ok,
        ), space


class HaMountedBackupProvider:
    """Bind the protected backup to the stopped transaction and its original USB."""

    def __init__(
        self, *, store: HaUsbStateStore, mountpoint: Path, internal_storage: Path,
        backup: ProtectedHaDataBackup, verify_quiesced: Callable[[], bool],
    ) -> None:
        self.store = store
        self.mountpoint = mountpoint
        self.internal_storage = internal_storage
        self.backup = backup
        self.verify_quiesced = verify_quiesced

    def _document(self) -> dict[str, Any]:
        current = self.store.read()
        if (
            current is None or current.get("usb_binding_mode") != "existing_filesystem"
            or "predecessor_start" not in current
        ):
            raise UpdaterV2Error("ha_data_backup_transaction_unbound")
        return current

    def _require_stopped(self, current: dict[str, Any]) -> None:
        if (
            current["phase"] != U7 or current["status"] != "ACTIVE"
            or current["recovery_required"] or self.verify_quiesced() is not True
        ):
            raise UpdaterV2Error("ha_data_backup_writers_not_quiesced")

    def _internal_work_root(self) -> Path:
        try:
            entry = self.backup.work_root.lstat()
            work_root = self.backup.work_root.resolve(strict=True)
            internal = self.internal_storage.resolve(strict=True)
            if (
                not work_root.is_relative_to(internal)
                or entry.st_dev != internal.stat().st_dev
            ):
                raise UpdaterV2Error("ha_data_backup_work_directory_off_internal_storage")
            if (
                not stat.S_ISDIR(entry.st_mode) or entry.st_uid != os.geteuid()
                or stat.S_IMODE(entry.st_mode) & 0o077
            ):
                raise UpdaterV2Error("ha_data_backup_work_directory_invalid")
        except OSError as error:
            raise UpdaterV2Error("ha_data_backup_work_directory_invalid") from error
        return work_root

    @contextmanager
    def _backup_directory(
        self, current: dict[str, Any], *, create: bool = False, allow_read_only: bool = False,
    ) -> Iterator[int]:
        with _open_transaction_directory(
            self.mountpoint, self.internal_storage, current, allow_read_only=allow_read_only,
        ) as (_, parent):
            if create:
                try:
                    os.mkdir("ha-backup", mode=0o700, dir_fd=parent)
                except FileExistsError as error:
                    raise UpdaterV2Error("ha_data_backup_destination_occupied") from error
                os.fsync(parent)
            fd = os.open(
                "ha-backup", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
            try:
                before = os.fstat(fd)
                if (
                    before.st_dev != os.fstat(parent).st_dev
                    or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) != 0o700
                ):
                    raise UpdaterV2Error("ha_data_backup_directory_identity_invalid")
                yield fd
                after = os.stat("ha-backup", dir_fd=parent, follow_symlinks=False)
                if not os.path.samestat(before, after):
                    raise UpdaterV2Error("ha_data_backup_directory_changed")
            finally:
                os.close(fd)

    def create_consistent_backup(self, *, transaction_id_sha256: str) -> HaDataBackupRecord:
        current = self._document()
        if current["transaction_id_sha256"] != transaction_id_sha256:
            raise UpdaterV2Error("ha_data_backup_transaction_identity_drift")
        self._require_stopped(current)
        self._internal_work_root()
        with self._backup_directory(current, create=True) as directory:
            self._require_stopped(self._document())
            record = self.backup.create(directory, transaction_id_sha256)
            self._require_stopped(self._document())
        return record

    def verify_backup(self, record: HaDataBackupRecord) -> HaDataBackupRecord:
        current = self._document()
        if current["phase"] == U7:
            self._require_stopped(current)
        elif current.get("install_recovery_materials", {}).get("backup") != record.public():
            raise UpdaterV2Error("ha_data_backup_record_unbound")
        with self._backup_directory(current) as directory:
            return self.backup.verify(directory, current["transaction_id_sha256"], record)

    def load_predecessor_image(
        self, load: Callable[[BinaryIO, PortableImageIdentity], None],
    ) -> PortableImageIdentity:
        """Admit only the original, transaction-bound predecessor bytes into the local loader."""
        current = self._document()
        published = current.get("ha_data_restore", {}).get("step") == "PUBLISHED"
        release_only = (
            current["phase"] == U10 and current["recovery_required"]
            and current.get("predecessor_release_observed") is True and "ha_data_restore" not in current
            and current.get("target_activation") != TARGET_WRITES_POSSIBLE
        )
        if (
            current["phase"] not in HA_DATA_RESTORE_PHASES or current["status"] != "ACTIVE"
            or not (published or release_only)
        ):
            raise UpdaterV2Error("ha_usb_predecessor_image_restore_phase_invalid")
        _, record = prepared_image_materials(current)
        return self._load_bound_image(current, record, load)

    def load_target_image(self, load: Callable[[BinaryIO, PortableImageIdentity], None]) -> PortableImageIdentity:
        current = self._document()
        if (
            current["phase"] != U10 or current["status"] != "ACTIVE" or current["recovery_required"]
            or current.get("predecessor_release_observed") is not True or "target_load_identity" in current
        ):
            raise UpdaterV2Error("ha_usb_target_image_load_phase_invalid")
        target, _ = prepared_image_materials(current)
        return self._load_bound_image(current, target, load)

    def _load_bound_image(
        self, current: dict[str, Any], record: ImageRecoveryRecord,
        load: Callable[[BinaryIO, PortableImageIdentity], None],
    ) -> PortableImageIdentity:
        self._require_restore_quiesced()
        with _open_transaction_directory(
            self.mountpoint, self.internal_storage, current, allow_read_only=True,
        ) as (_, directory), _verified_archive(directory, f"{record.kind}.tar", record, for_load=True) as (fd, blocks):
            identity, unpacked = _authenticate_image(fd, blocks, record)
            if self._document() != current:
                raise UpdaterV2Error(f"ha_usb_{record.kind}_image_load_transaction_changed")
            self._require_restore_quiesced()
            if record.kind == "target":
                admission = current["predecessor_release_admission"]
                required = max(unpacked, admission["install_required_bytes"]) + admission["recovery_required_bytes"]
                storage = os.statvfs(self.internal_storage)
                if storage.f_bavail * storage.f_frsize < required:
                    raise UpdaterV2Error("ha_usb_target_image_recovery_space_insufficient")
            with io.BufferedReader(_AuthenticatedArchiveReader(fd, record.archive_size_bytes, blocks)) as source:
                load(source, identity)
            if record.kind == "target":
                storage = os.statvfs(self.internal_storage)
                if storage.f_bavail * storage.f_frsize < admission["recovery_required_bytes"]:
                    raise UpdaterV2Error("ha_usb_target_image_recovery_reserve_lost")
        return identity

    @contextmanager
    def stage_preupgrade_data(self) -> Iterator[Path]:
        """Supply a verified tree to the recovery caller while it holds the host lock."""
        current = self._document()
        if current["phase"] not in HA_DATA_RESTORE_PHASES or "ha_data_restore" in current:
            raise UpdaterV2Error("ha_data_restore_phase_invalid")
        self._require_restore_quiesced()
        work_root = self._restore_work_root()
        with tempfile.TemporaryDirectory(prefix=".ha-restore-", dir=work_root) as scratch:
            stage = Path(scratch) / "data"
            self._extract_restore(current, stage)
            yield stage

    def _require_restore_quiesced(self) -> None:
        if self.verify_quiesced() is not True:
            raise UpdaterV2Error("ha_data_restore_writers_not_quiesced")

    def _restore_work_root(self) -> Path:
        work_root = self._internal_work_root()
        live = self.backup.ha_data_root
        try:
            entry = live.lstat()
            if (
                not stat.S_ISDIR(entry.st_mode) or entry.st_dev != work_root.stat().st_dev
                or work_root.is_relative_to(live.resolve(strict=True))
            ):
                raise UpdaterV2Error("ha_data_restore_work_directory_unsafe")
        except OSError as error:
            raise UpdaterV2Error("ha_data_restore_target_unavailable") from error
        return work_root

    def _extract_restore(self, current: dict[str, Any], stage: Path) -> None:
        record = backup_record_from_document(current["install_recovery_materials"]["backup"])
        with self._backup_directory(current, allow_read_only=True) as directory:
            try:
                self.backup.restore_to_stage(directory, current["transaction_id_sha256"], record, stage)
            except OSError as error:
                raise UpdaterV2Error("ha_data_restore_stage_io_failed") from error
        if self._document() != current:
            raise UpdaterV2Error("ha_data_restore_transaction_changed")
        self._require_restore_quiesced()

    def _write_restore(self, current: dict[str, Any], journal: dict[str, Any]) -> dict[str, Any]:
        current = {**current, "ha_data_restore": journal, "recovery_required": True}
        self.store.write(current)
        return current

    def restore_preupgrade_data(self) -> None:
        """Publish or reconcile the verified HA tree under the caller's recovery lock."""
        current = self._document()
        if current["phase"] not in HA_DATA_RESTORE_PHASES or current["status"] != "ACTIVE":
            raise UpdaterV2Error("ha_data_restore_phase_invalid")
        work_root = self._restore_work_root()
        live = self.backup.ha_data_root
        workspace = work_root / f'.ha-restore-{current["transaction_id_sha256"]}'
        try:
            with ExitStack() as stack:
                parent = os.open(live.parent, DIRECTORY_FLAGS)
                stack.callback(os.close, parent)
                live_id = _directory_identity(parent, live.name)
                journal = current.get("ha_data_restore")
                if journal is None:
                    self._require_restore_quiesced()
                    if os.path.lexists(workspace):
                        raise UpdaterV2Error("ha_data_restore_workspace_occupied")
                    journal = {
                        "step": "STAGING", "filesystem_id": live_id[0], "original_inode": live_id[1],
                    }
                    current = self._write_restore(current, journal)
                if journal["step"] == "PUBLISHED":
                    if live_id != (journal["filesystem_id"], journal["staged_inode"]):
                        raise UpdaterV2Error("ha_data_restore_directory_identity_drift")
                    return
                work = os.open(work_root, DIRECTORY_FLAGS)
                stack.callback(os.close, work)
                if journal["step"] == "STAGING":
                    if live_id != (journal["filesystem_id"], journal["original_inode"]):
                        raise UpdaterV2Error("ha_data_restore_directory_identity_drift")
                    self._require_restore_quiesced()
                    try:
                        os.mkdir(workspace.name, 0o700, dir_fd=work)
                    except FileExistsError:
                        pass
                    os.fsync(work)
                scratch = os.open(workspace.name, DIRECTORY_FLAGS, dir_fd=work)
                stack.callback(os.close, scratch)
                entry = os.fstat(scratch)
                contents = set(os.listdir(scratch))
                if (
                    entry.st_dev != os.fstat(parent).st_dev or entry.st_uid != os.geteuid()
                    or stat.S_IMODE(entry.st_mode) != 0o700 or contents - {"data"}
                ):
                    raise UpdaterV2Error("ha_data_restore_workspace_invalid")
                if journal["step"] == "STAGING":
                    stage = workspace / "data"
                    if "data" in contents:
                        _directory_identity(scratch, "data")
                        shutil.rmtree(stage)
                    self._extract_restore(current, stage)
                    staged_id = _directory_identity(scratch, "data")
                    os.fsync(scratch)
                    journal = {**journal, "step": "EXCHANGE_PENDING", "staged_inode": staged_id[1]}
                    current = self._write_restore(current, journal)
                self._publish_restore(current, parent, live.name, scratch)
        except OSError as error:
            raise UpdaterV2Error("ha_data_restore_publication_io_failed") from error

    def _publish_restore(self, current: dict[str, Any], parent: int, name: str, scratch: int) -> None:
        journal = current["ha_data_restore"]
        original = (journal["filesystem_id"], journal["original_inode"])
        restored = (journal["filesystem_id"], journal["staged_inode"])
        observed = (_directory_identity(parent, name), _directory_identity(scratch, "data"))
        if observed == (original, restored):
            self._require_restore_quiesced()
            _exchange_directories(parent, name, scratch, "data")
            observed = (_directory_identity(parent, name), _directory_identity(scratch, "data"))
        if observed != (restored, original):
            raise UpdaterV2Error("ha_data_restore_directory_identity_drift")
        os.fsync(parent)
        os.fsync(scratch)
        self._write_restore(current, {**journal, "step": "PUBLISHED"})
