#!/usr/bin/env python3
"""N3W OTA Guard v0.2.2-review.

Recovery-only ESP32-C6 OTA safety helper for the current N3-W / KF-089 Board B
successor workflow.

Safety properties of this revision:
- Board B app0 is read-only: no app0 write primitive or fresh deployment workflow.
- app0 at 0x10000 is exact-bound by size + SHA-256 before any otadata mutation.
- read operations use explicit esptool 5.2.0 CLI reset/connection arguments.
- otadata mutation never calls esptool.cmds.write_flash / CLI write-flash because
  that high-level path can reconnect/retry the whole write operation.
- the only mutation primitive is a direct ROM write of one 32-byte
  esp_ota_select_entry_t at 0x9000 or 0xA000, with one connection attempt and one
  flash-block attempt.
- the mutation connection re-verifies BASE_MAC, app0 freshness, and the exact
  pre-read otadata snapshot before flash_begin. SHA-256 remains firmware authority;
  device-side MD5 is used only as a same-connection freshness check.
- OTA selection changes only ota_seq + CRC and preserves seq_label + ota_state.
- if mutation may have started and an exception occurs, the tool performs one
  bounded read-only otadata failure-state capture; it never retries mutation.
- post-write verification reads full 0x2000 otadata and requires the non-target
  sector to remain byte-identical.
- evidence is durable/private and rejected if placed inside a Git worktree.

REVIEW ONLY. This source does not itself authorize physical board access.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib
import json
import os
import re
import shlex
import struct
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Callable, Mapping, Sequence

TOOL_NAME = "N3W OTA Guard"
TOOL_VERSION = "0.2.2-review"
TOOL_MODE = "BOARD_B_RECOVERY_ONLY"

CHIP = "esp32c6"
BAUD = 115200
FLASH_SIZE = "8MB"
FLASH_SIZE_BYTES = 8 * 1024 * 1024
CONNECT_ATTEMPTS = 1

APP0_SLOT = 0
APP0_OFFSET = 0x10000
APP0_PARTITION_SIZE = 0x3C0000
APP0_PAYLOAD_SIZE = 1_115_648
APP0_EXPECTED_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"

OTADATA_OFFSET = 0x9000
OTADATA_SIZE = 0x2000
OTADATA_SECTOR_SIZE = 0x1000
OTADATA_COPY_OFFSETS = (0x0000, 0x1000)
OTADATA_ENTRY_FLASH_OFFSETS = (0x9000, 0xA000)
OTA_ENTRY_SIZE = 32
OTA_APP_COUNT = 2

UINT32_MAX = 0xFFFFFFFF

EXPECTED_ESPTOOL_VERSION = "5.2.0"
# Exact ESP-IDF v5.5.4 components/esptool_py/esptool/esptool.py delegate wrapper.
EXPECTED_ESPTOOL_WRAPPER_SHA256 = "a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be"
EXPECTED_FLASH_WRITE_SIZE = 0x400


class GuardError(RuntimeError):
    """Fail-closed guard violation."""


class OtaState(IntEnum):
    NEW = 0x0
    PENDING_VERIFY = 0x1
    VALID = 0x2
    INVALID = 0x3
    ABORTED = 0x4
    UNDEFINED = UINT32_MAX


KNOWN_OTA_STATES = {int(value) for value in OtaState}
SAFE_ACTIVE_STATES = {int(OtaState.VALID), int(OtaState.UNDEFINED)}
SAFE_TARGET_PRESERVE_STATES = {int(OtaState.VALID), int(OtaState.UNDEFINED)}


@dataclass(frozen=True)
class ToolchainBinding:
    python_executable: str
    esptool_path: str
    esptool_wrapper_sha256: str
    esptool_version: str
    esptool_module_path: str
    esptool_module_sha256: str
    loader_module_path: str
    loader_module_sha256: str
    cmds_module_path: str
    cmds_module_sha256: str
    esp32c6_module_path: str
    esp32c6_module_sha256: str
    package_root: str
    flash_sector_size: int
    flash_write_size: int
    write_block_attempts: int
    high_level_write_attempts: int

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class IdentityBinding:
    expected_base_mac: str
    observed_base_mac: str

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AppPayloadBinding:
    slot: int
    offset: int
    size: int
    sha256: str
    source_path: str

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["offset"] = f"0x{self.offset:x}"
        return data


@dataclass(frozen=True)
class OtaEntry:
    index: int
    raw: bytes
    seq: int
    seq_label: bytes
    ota_state: int
    crc: int
    expected_crc: int
    erased: bool
    crc_valid: bool
    state_known: bool
    idf_boot_valid: bool

    @property
    def slot(self) -> int | None:
        if not self.idf_boot_valid or self.seq in (0, UINT32_MAX):
            return None
        return (self.seq - 1) % OTA_APP_COUNT

    @property
    def state_name(self) -> str:
        try:
            return OtaState(self.ota_state).name
        except ValueError:
            return f"UNKNOWN_0x{self.ota_state:08x}"


@dataclass(frozen=True)
class OtaSnapshot:
    raw: bytes
    entries: tuple[OtaEntry, OtaEntry]
    active_index: int
    selected_slot: int


@dataclass(frozen=True)
class OtaSwitchPlan:
    target_slot: int
    current_slot: int
    active_index: int
    target_copy_index: int
    target_entry_flash_offset: int
    old_active_seq: int
    old_target_seq: int
    new_seq: int
    preserved_ota_state: int
    expected_crc: int
    before_target_sector_sha256: str
    expected_after_target_sector_sha256: str
    entry_image_sha256: str
    changed_entry_byte_ranges: tuple[tuple[int, int], ...]
    entry_image: bytes

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("entry_image", None)
        data["target_entry_flash_offset"] = f"0x{self.target_entry_flash_offset:x}"
        data["preserved_ota_state_name"] = OtaState(self.preserved_ota_state).name
        data["changed_entry_byte_ranges"] = [
            [f"0x{start:x}", f"0x{end:x}"]
            for start, end in self.changed_entry_byte_ranges
        ]
        return data


@dataclass(frozen=True)
class WorkflowResult:
    identity_binding: IdentityBinding
    app_binding: AppPayloadBinding
    ota_plan: OtaSwitchPlan
    evidence_dir: str


class EvidenceStore:
    """Durable private evidence directory for one physical workflow."""

    def __init__(self, root: os.PathLike[str] | str, *, create: bool = True):
        self.root = Path(root).expanduser().resolve(strict=False)
        self._reject_git_worktree_location()
        if create:
            if self.root.exists() and any(self.root.iterdir()):
                raise GuardError(f"evidence directory is not empty: {self.root}")
            self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise GuardError("evidence path is not a directory")
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def _reject_git_worktree_location(self) -> None:
        for parent in (self.root, *self.root.parents):
            if (parent / ".git").exists():
                raise GuardError("evidence directory must not be inside a Git worktree")

    def path(self, name: str) -> Path:
        if Path(name).name != name:
            raise GuardError("evidence filename must be a basename")
        return self.root / name

    @staticmethod
    def _protect_file(path: Path) -> None:
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def write_bytes(self, name: str, data: bytes) -> Path:
        path = self.path(name)
        path.write_bytes(data)
        self._protect_file(path)
        return path

    def write_text(self, name: str, text: str) -> Path:
        path = self.path(name)
        path.write_text(text, encoding="utf-8")
        self._protect_file(path)
        return path

    def write_json(self, name: str, obj: object) -> Path:
        return self.write_text(name, json.dumps(obj, indent=2, sort_keys=True) + "\n")

    def ensure_esptool_config(self) -> Path:
        path = self.path("esptool.cfg")
        content = (
            "[esptool]\n"
            "connect_attempts = 1\n"
            "write_block_attempts = 1\n"
            "open_port_attempts = 1\n"
        )
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise GuardError("existing esptool.cfg does not match guard retry contract")
        else:
            path.write_text(content, encoding="utf-8")
            self._protect_file(path)
        return path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: os.PathLike[str] | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def md5_file(path: os.PathLike[str] | str) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def esp_ota_crc(seq: int) -> int:
    """ESP-IDF v5.5.4: CRC32 over little-endian ota_seq only."""
    if not 0 <= seq <= UINT32_MAX:
        raise GuardError("ota_seq out of uint32 range")
    return binascii.crc32(struct.pack("<I", seq), UINT32_MAX) & UINT32_MAX


def _diff_ranges(before: bytes, after: bytes) -> tuple[tuple[int, int], ...]:
    if len(before) != len(after):
        raise GuardError("diff operands differ in length")
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, (left, right) in enumerate(zip(before, after)):
        if left != right and start is None:
            start = index
        elif left == right and start is not None:
            ranges.append((start, index))
            start = None
    if start is not None:
        ranges.append((start, len(before)))
    return tuple(ranges)


def _parse_entry(raw: bytes, index: int) -> OtaEntry:
    if len(raw) != OTA_ENTRY_SIZE:
        raise GuardError("OTA entry must be exactly 32 bytes")
    seq = struct.unpack_from("<I", raw, 0)[0]
    seq_label = raw[4:24]
    ota_state = struct.unpack_from("<I", raw, 24)[0]
    crc = struct.unpack_from("<I", raw, 28)[0]
    erased = raw == b"\xff" * OTA_ENTRY_SIZE
    expected_crc = esp_ota_crc(seq)
    crc_valid = crc == expected_crc
    state_known = ota_state in KNOWN_OTA_STATES
    idf_boot_valid = (
        seq != UINT32_MAX
        and ota_state not in (int(OtaState.INVALID), int(OtaState.ABORTED))
        and crc_valid
    )
    return OtaEntry(
        index=index,
        raw=raw,
        seq=seq,
        seq_label=seq_label,
        ota_state=ota_state,
        crc=crc,
        expected_crc=expected_crc,
        erased=erased,
        crc_valid=crc_valid,
        state_known=state_known,
        idf_boot_valid=idf_boot_valid,
    )


def parse_otadata(raw: bytes) -> OtaSnapshot:
    if len(raw) != OTADATA_SIZE:
        raise GuardError(f"otadata must be exactly 0x{OTADATA_SIZE:x} bytes")
    parsed = [
        _parse_entry(raw[rel : rel + OTA_ENTRY_SIZE], index)
        for index, rel in enumerate(OTADATA_COPY_OFFSETS)
    ]
    entries = (parsed[0], parsed[1])

    unknown = [entry.index for entry in entries if not entry.erased and not entry.state_known]
    if unknown:
        raise GuardError(f"unsupported/unknown ota_state in copies {unknown}")

    valid = [entry for entry in entries if entry.idf_boot_valid]
    if not valid:
        raise GuardError("no valid OTA-select copy")
    if len(valid) == 2 and valid[0].seq == valid[1].seq:
        raise GuardError("ambiguous OTA-select state: both valid copies have equal ota_seq")

    active = max(valid, key=lambda entry: entry.seq)
    if active.seq == 0:
        raise GuardError("active ota_seq=0 is unsupported")
    if active.ota_state not in SAFE_ACTIVE_STATES:
        raise GuardError(f"active ota_state {active.state_name} is unsafe for host slot switch")
    selected_slot = (active.seq - 1) % OTA_APP_COUNT
    return OtaSnapshot(raw, entries, active.index, selected_slot)


def _next_seq_for_target(active_seq: int, target_slot: int) -> int:
    """O(1) equivalent of ESP-IDF v5.5.4 esp_rewrite_ota_data sequence loop."""
    if not 0 < active_seq < UINT32_MAX:
        raise GuardError("active ota_seq is outside supported range")
    if target_slot not in (0, 1):
        raise GuardError("target slot must be 0 or 1")

    base = (target_slot + 1) % OTA_APP_COUNT
    if active_seq <= base:
        candidate = base
    else:
        delta = active_seq - base
        multiplier = (delta + OTA_APP_COUNT - 1) // OTA_APP_COUNT
        candidate = base + multiplier * OTA_APP_COUNT

    if candidate <= active_seq:
        raise GuardError("computed ota_seq is not newer than active ota_seq")
    if candidate >= UINT32_MAX:
        raise GuardError("computed ota_seq reaches overflow/erase marker")
    return candidate


def verify_app0_payload(
    path: os.PathLike[str] | str,
    expected_sha256: str = APP0_EXPECTED_SHA256,
) -> AppPayloadBinding:
    source = Path(path)
    size = source.stat().st_size
    if size != APP0_PAYLOAD_SIZE:
        raise GuardError(
            f"app0 payload size mismatch: got {size}, expected {APP0_PAYLOAD_SIZE}"
        )
    digest = sha256_file(source)
    if digest.lower() != expected_sha256.lower():
        raise GuardError("app0 SHA256 mismatch")
    return AppPayloadBinding(
        APP0_SLOT, APP0_OFFSET, APP0_PAYLOAD_SIZE, digest.lower(), str(source)
    )


def plan_ota_switch_to_app0(raw: bytes, app_binding: AppPayloadBinding) -> OtaSwitchPlan:
    if app_binding.slot != APP0_SLOT:
        raise GuardError("payload binding is not for app0")
    if app_binding.offset != APP0_OFFSET or app_binding.size != APP0_PAYLOAD_SIZE:
        raise GuardError("payload binding geometry does not match frozen app0 contract")
    if app_binding.sha256.lower() != APP0_EXPECTED_SHA256.lower():
        raise GuardError("payload binding does not match frozen firmware authority")

    snapshot = parse_otadata(raw)
    if snapshot.selected_slot == APP0_SLOT:
        raise GuardError("app0 is already selected; expected pre-switch app1")

    active = snapshot.entries[snapshot.active_index]
    target_copy = 1 - snapshot.active_index
    target_entry = snapshot.entries[target_copy]

    if target_entry.erased:
        preserved_state = int(OtaState.UNDEFINED)
    else:
        if not target_entry.state_known:
            raise GuardError("target OTA entry has unknown state")
        if target_entry.ota_state not in SAFE_TARGET_PRESERVE_STATES:
            raise GuardError(
                f"target ota_state {target_entry.state_name} cannot be safely preserved"
            )
        preserved_state = target_entry.ota_state

    new_seq = _next_seq_for_target(active.seq, APP0_SLOT)
    new_crc = esp_ota_crc(new_seq)
    entry_image = bytearray(target_entry.raw)
    struct.pack_into("<I", entry_image, 0, new_seq)
    struct.pack_into("<I", entry_image, 28, new_crc)

    if bytes(entry_image[4:24]) != target_entry.seq_label:
        raise GuardError("planner changed seq_label")
    if struct.unpack_from("<I", entry_image, 24)[0] != preserved_state:
        raise GuardError("planner changed ota_state")

    changed = _diff_ranges(target_entry.raw, bytes(entry_image))
    for start, end in changed:
        if not ((0 <= start and end <= 4) or (28 <= start and end <= 32)):
            raise GuardError("planner changed bytes outside ota_seq/crc")

    sector_rel = OTADATA_COPY_OFFSETS[target_copy]
    before_sector = raw[sector_rel : sector_rel + OTADATA_SECTOR_SIZE]
    expected_after_sector = bytes(entry_image) + b"\xff" * (
        OTADATA_SECTOR_SIZE - OTA_ENTRY_SIZE
    )
    return OtaSwitchPlan(
        target_slot=APP0_SLOT,
        current_slot=snapshot.selected_slot,
        active_index=snapshot.active_index,
        target_copy_index=target_copy,
        target_entry_flash_offset=OTADATA_OFFSET + sector_rel,
        old_active_seq=active.seq,
        old_target_seq=target_entry.seq,
        new_seq=new_seq,
        preserved_ota_state=preserved_state,
        expected_crc=new_crc,
        before_target_sector_sha256=sha256_bytes(before_sector),
        expected_after_target_sector_sha256=sha256_bytes(expected_after_sector),
        entry_image_sha256=sha256_bytes(bytes(entry_image)),
        changed_entry_byte_ranges=changed,
        entry_image=bytes(entry_image),
    )


def expected_post_otadata(pre: bytes, plan: OtaSwitchPlan) -> bytes:
    if len(pre) != OTADATA_SIZE:
        raise GuardError("prechange otadata must be exactly 0x2000 bytes")
    post = bytearray(pre)
    target_rel = OTADATA_COPY_OFFSETS[plan.target_copy_index]
    post[target_rel : target_rel + OTADATA_SECTOR_SIZE] = (
        plan.entry_image + b"\xff" * (OTADATA_SECTOR_SIZE - OTA_ENTRY_SIZE)
    )
    return bytes(post)


def verify_ota_switch(pre: bytes, post: bytes, plan: OtaSwitchPlan) -> None:
    if len(pre) != OTADATA_SIZE or len(post) != OTADATA_SIZE:
        raise GuardError("pre/post otadata must each be exactly 0x2000 bytes")
    target_rel = OTADATA_COPY_OFFSETS[plan.target_copy_index]
    other_rel = OTADATA_COPY_OFFSETS[1 - plan.target_copy_index]
    if post[other_rel : other_rel + OTADATA_SECTOR_SIZE] != pre[
        other_rel : other_rel + OTADATA_SECTOR_SIZE
    ]:
        raise GuardError("non-target otadata sector changed")
    if post != expected_post_otadata(pre, plan):
        raise GuardError("target otadata sector does not match erase+32-byte-write semantics")

    snapshot = parse_otadata(post)
    if snapshot.selected_slot != APP0_SLOT:
        raise GuardError("postwrite selected slot is not app0")
    if snapshot.active_index != plan.target_copy_index:
        raise GuardError("postwrite active otadata copy is not target copy")
    entry = snapshot.entries[plan.target_copy_index]
    if entry.seq != plan.new_seq:
        raise GuardError("postwrite ota_seq mismatch")
    if entry.crc != plan.expected_crc or not entry.crc_valid:
        raise GuardError("postwrite OTA CRC mismatch")
    if entry.ota_state != plan.preserved_ota_state:
        raise GuardError("postwrite ota_state was not preserved")
    if entry.seq_label != pre[target_rel + 4 : target_rel + 24]:
        raise GuardError("postwrite seq_label was not preserved")


# -------------------- Read-only esptool CLI contract --------------------

_ALLOWED_READ_SUBCOMMANDS = {"read-flash", "read-mac"}


def _base_esptool_argv(python_exe: str, esptool_path: str, port: str) -> list[str]:
    if not port:
        raise GuardError("serial port is required for a physical read command")
    return [
        python_exe,
        esptool_path,
        "--chip",
        CHIP,
        "--port",
        port,
        "--baud",
        str(BAUD),
        "--before",
        "no-reset",
        "--after",
        "no-reset",
        "--no-stub",
        "--connect-attempts",
        str(CONNECT_ATTEMPTS),
    ]


def validate_esptool_read_argv(argv: Sequence[str]) -> None:
    if len(argv) < 16:
        raise GuardError("esptool argv too short")
    sub_indexes = [
        index for index, token in enumerate(argv) if token in _ALLOWED_READ_SUBCOMMANDS
    ]
    if len(sub_indexes) != 1:
        raise GuardError("expected exactly one allowed read-only esptool subcommand")
    sub_index = sub_indexes[0]
    if sub_index != 15:
        raise GuardError("unexpected esptool global argument shape")
    prefix = list(argv[:sub_index])
    port = prefix[5]
    if prefix != _base_esptool_argv(prefix[0], prefix[1], port):
        raise GuardError("esptool global arguments are not the exact guard contract")
    if any(token in argv for token in ("write-flash", "erase-flash", "erase-region")):
        raise GuardError("mutation command is forbidden in read-only esptool CLI")

    subcommand = argv[sub_index]
    suffix = list(argv[sub_index + 1 :])
    if subcommand == "read-mac":
        if suffix:
            raise GuardError("read-mac must not have extra arguments")
        return

    if len(suffix) != 5 or suffix[:2] != ["--flash-size", FLASH_SIZE]:
        raise GuardError("read-flash arguments are not the exact guard contract")
    address, size, output = suffix[2], suffix[3], suffix[4]
    allowed_geometry = {
        (hex(APP0_OFFSET), str(APP0_PAYLOAD_SIZE)),
        (hex(OTADATA_OFFSET), str(OTADATA_SIZE)),
    }
    if (address, size) not in allowed_geometry:
        raise GuardError("read-flash geometry is outside the guard allowlist")
    if not output:
        raise GuardError("read-flash output path is empty")


def build_identity_read_command(
    python_exe: str, esptool_path: str, port: str
) -> list[str]:
    argv = _base_esptool_argv(python_exe, esptool_path, port) + ["read-mac"]
    validate_esptool_read_argv(argv)
    return argv


def build_app0_read_command(
    python_exe: str, esptool_path: str, port: str, output_path: str
) -> list[str]:
    argv = _base_esptool_argv(python_exe, esptool_path, port) + [
        "read-flash",
        "--flash-size",
        FLASH_SIZE,
        hex(APP0_OFFSET),
        str(APP0_PAYLOAD_SIZE),
        output_path,
    ]
    validate_esptool_read_argv(argv)
    return argv


def build_otadata_read_command(
    python_exe: str, esptool_path: str, port: str, output_path: str
) -> list[str]:
    argv = _base_esptool_argv(python_exe, esptool_path, port) + [
        "read-flash",
        "--flash-size",
        FLASH_SIZE,
        hex(OTADATA_OFFSET),
        str(OTADATA_SIZE),
        output_path,
    ]
    validate_esptool_read_argv(argv)
    return argv


def normalize_mac(value: str) -> str:
    normalized = value.strip().lower().replace("-", ":")
    if not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", normalized):
        raise GuardError("invalid MAC address format")
    return normalized


def _mac_to_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part, 16) for part in normalize_mac(value).split(":"))


def verify_identity_output(output: str, expected_base_mac: str) -> IdentityBinding:
    expected = normalize_mac(expected_base_mac)
    candidates = {
        normalize_mac(match)
        for match in re.findall(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", output)
    }
    if len(candidates) != 1:
        raise GuardError("ROM identity output does not contain exactly one BASE_MAC")
    observed = next(iter(candidates))
    if observed != expected:
        raise GuardError("ROM identity mismatch")
    return IdentityBinding(expected, observed)


# -------------------- Toolchain binding + direct no-retry mutation --------------------


def _safe_env(config_path: os.PathLike[str] | str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["ESPTOOL_OPEN_PORT_ATTEMPTS"] = "1"
    if config_path is not None:
        env["ESPTOOL_CFGFILE"] = str(config_path)
    return env


def _module_binding(module: object) -> tuple[str, str]:
    raw_path = getattr(module, "__file__", None)
    if not raw_path:
        raise GuardError("esptool runtime module has no file binding")
    path = Path(raw_path).resolve()
    return str(path), sha256_file(path)


def bind_toolchain_runtime(
    python_exe: str,
    esptool_path: str,
    *,
    config_path: os.PathLike[str] | str,
    expected_wrapper_sha256: str = EXPECTED_ESPTOOL_WRAPPER_SHA256,
    expected_version: str = EXPECTED_ESPTOOL_VERSION,
) -> tuple[ToolchainBinding, dict[str, object]]:
    """Bind the exact interpreter and the esptool runtime used for mutation.

    The frozen ESP-IDF wrapper is a 269-byte delegate which launches
    ``sys.executable -m esptool``. Therefore package modules are expected to live
    in the bound interpreter's site-packages, not under the wrapper directory.
    We require the exact wrapper hash, exact interpreter, package version, common
    package root, module hashes in evidence, and the reviewed runtime constants.
    """
    requested_python = Path(python_exe).resolve()
    actual_python = Path(sys.executable).resolve()
    if requested_python != actual_python:
        raise GuardError("physical recovery must run under the exact bound Python interpreter")

    wrapper = Path(esptool_path).resolve()
    if not wrapper.is_file():
        raise GuardError("esptool wrapper not found")
    wrapper_digest = sha256_file(wrapper)
    if wrapper_digest.lower() != expected_wrapper_sha256.lower():
        raise GuardError("esptool wrapper SHA256 mismatch")

    if any(name == "esptool" or name.startswith("esptool.") for name in sys.modules):
        raise GuardError("esptool was imported before guard retry contract was bound")

    config = Path(config_path).resolve()
    if not config.is_file():
        raise GuardError("guard esptool.cfg is missing")
    os.environ["ESPTOOL_CFGFILE"] = str(config)
    os.environ["ESPTOOL_OPEN_PORT_ATTEMPTS"] = "1"

    esptool = importlib.import_module("esptool")
    cmds = importlib.import_module("esptool.cmds")
    loader = importlib.import_module("esptool.loader")
    esp32c6 = importlib.import_module("esptool.targets.esp32c6")

    if getattr(esptool, "__version__", None) != expected_version:
        raise GuardError("unexpected esptool package version")
    esp_cls = esp32c6.ESP32C6ROM
    if esp_cls.CHIP_NAME != "ESP32-C6":
        raise GuardError("unexpected ESP32-C6 target binding")
    if esp_cls.FLASH_SECTOR_SIZE != OTADATA_SECTOR_SIZE:
        raise GuardError("unexpected esptool flash sector size")
    if esp_cls.FLASH_WRITE_SIZE != EXPECTED_FLASH_WRITE_SIZE:
        raise GuardError("unexpected esptool flash write block size")
    if loader.WRITE_BLOCK_ATTEMPTS != 1:
        raise GuardError("esptool flash-block retry count is not one")

    esptool_path_loaded, esptool_sha = _module_binding(esptool)
    loader_path, loader_sha = _module_binding(loader)
    cmds_path, cmds_sha = _module_binding(cmds)
    esp32c6_path, esp32c6_sha = _module_binding(esp32c6)
    package_root = Path(esptool_path_loaded).resolve().parent
    for module_path in (loader_path, cmds_path, esp32c6_path):
        try:
            Path(module_path).resolve().relative_to(package_root)
        except ValueError as exc:
            raise GuardError("esptool runtime modules do not share one package root") from exc

    binding = ToolchainBinding(
        python_executable=str(actual_python),
        esptool_path=str(wrapper),
        esptool_wrapper_sha256=wrapper_digest,
        esptool_version=expected_version,
        esptool_module_path=esptool_path_loaded,
        esptool_module_sha256=esptool_sha,
        loader_module_path=loader_path,
        loader_module_sha256=loader_sha,
        cmds_module_path=cmds_path,
        cmds_module_sha256=cmds_sha,
        esp32c6_module_path=esp32c6_path,
        esp32c6_module_sha256=esp32c6_sha,
        package_root=str(package_root),
        flash_sector_size=esp_cls.FLASH_SECTOR_SIZE,
        flash_write_size=esp_cls.FLASH_WRITE_SIZE,
        write_block_attempts=loader.WRITE_BLOCK_ATTEMPTS,
        high_level_write_attempts=loader.ESPLoader.WRITE_FLASH_ATTEMPTS,
    )
    runtime: dict[str, object] = {
        "ESP32C6ROM": esp_cls,
        "attach_flash": cmds.attach_flash,
        "flash_write_size": esp_cls.FLASH_WRITE_SIZE,
    }
    return binding, runtime


def _validate_authorization_id(authorization_id: str) -> str:
    normalized = authorization_id.strip()
    if not normalized:
        raise GuardError("physical recovery requires a non-empty authorization id")
    if len(normalized) > 256 or any(ord(char) < 0x20 for char in normalized):
        raise GuardError("authorization id has invalid format")
    return normalized


def _validate_direct_write_request(offset: int, entry_data: bytes) -> None:
    if offset not in OTADATA_ENTRY_FLASH_OFFSETS:
        raise GuardError("direct mutation offset is outside otadata copy starts")
    if len(entry_data) != OTA_ENTRY_SIZE:
        raise GuardError("direct mutation payload must be exactly 32 bytes")


def _write_mutation_phase(
    evidence: EvidenceStore,
    ordinal: int,
    phase: str,
    *,
    mutation_possible: bool,
    authorization_id: str,
) -> None:
    evidence.write_json(
        f"otadata-mutation-phase-{ordinal:02d}-{phase.lower().replace('_', '-')}.json",
        {
            "timestamp_utc": utc_now(),
            "phase": phase,
            "mutation_possible": mutation_possible,
            "authorization_id": authorization_id,
        },
    )


def _perform_direct_otadata_write_once(
    runtime: Mapping[str, object],
    *,
    port: str,
    expected_base_mac: str,
    authorization_id: str,
    app_binding: AppPayloadBinding,
    pre_otadata: bytes,
    offset: int,
    entry_data: bytes,
    evidence: EvidenceStore,
) -> None:
    """Perform exactly one low-level ESP32-C6 ROM otadata write attempt."""
    authorization_id = _validate_authorization_id(authorization_id)
    _validate_direct_write_request(offset, entry_data)
    if len(pre_otadata) != OTADATA_SIZE:
        raise GuardError("direct mutation requires exact 0x2000 prechange otadata")
    if app_binding.slot != APP0_SLOT or app_binding.offset != APP0_OFFSET:
        raise GuardError("direct mutation lacks an app0 binding")
    if app_binding.size != APP0_PAYLOAD_SIZE:
        raise GuardError("direct mutation app0 binding size mismatch")
    if app_binding.sha256.lower() != APP0_EXPECTED_SHA256.lower():
        raise GuardError("direct mutation lacks frozen app0 SHA256 authority")

    refreshed = verify_app0_payload(app_binding.source_path, APP0_EXPECTED_SHA256)
    if refreshed.sha256 != app_binding.sha256:
        raise GuardError("app0 evidence binding changed before mutation")
    expected_app0_md5 = md5_file(app_binding.source_path)
    expected_otadata_md5 = md5_bytes(pre_otadata)
    expected_mac_tuple = _mac_to_tuple(expected_base_mac)

    esp_cls = runtime["ESP32C6ROM"]
    attach_flash = runtime["attach_flash"]
    flash_write_size = int(runtime["flash_write_size"])
    if flash_write_size != EXPECTED_FLASH_WRITE_SIZE:
        raise GuardError("direct mutation runtime flash write size mismatch")

    evidence.write_json(
        "otadata-mutation-attempt.json",
        {
            "timestamp_utc": utc_now(),
            "authorization_id": authorization_id,
            "primitive": "DIRECT_ESPTOOL_ROM_SINGLE_ATTEMPT",
            "stock_esptool_write_flash_used": False,
            "target_offset": f"0x{offset:x}",
            "entry_size": len(entry_data),
            "entry_sha256": sha256_bytes(entry_data),
            "app0_authority_sha256": app_binding.sha256,
            "pre_otadata_sha256": sha256_bytes(pre_otadata),
            "workflow_retry": False,
            "connect_attempts": 1,
            "write_block_attempts": 1,
            "host_reset_requested": False,
        },
    )

    with esp_cls(port, BAUD) as esp:  # type: ignore[operator]
        esp.connect(mode="no-reset", attempts=1)
        if getattr(esp, "sync_stub_detected", False) or getattr(esp, "IS_STUB", False):
            raise GuardError("existing flasher stub detected; ROM-only mutation required")
        if getattr(esp, "secure_download_mode", False):
            raise GuardError("unexpected secure download mode")

        observed_mac = tuple(esp.read_mac("BASE_MAC"))
        if observed_mac != expected_mac_tuple:
            raise GuardError("mutation-time ROM identity mismatch")

        attach_flash(esp)  # type: ignore[operator]
        esp.flash_set_parameters(FLASH_SIZE_BYTES)
        observed_app0_md5 = str(
            esp.flash_md5sum(APP0_OFFSET, APP0_PAYLOAD_SIZE)
        ).lower()
        if observed_app0_md5 != expected_app0_md5.lower():
            raise GuardError("mutation-time app0 freshness check failed")
        observed_otadata_md5 = str(
            esp.flash_md5sum(OTADATA_OFFSET, OTADATA_SIZE)
        ).lower()
        if observed_otadata_md5 != expected_otadata_md5.lower():
            raise GuardError("mutation-time otadata preimage freshness check failed")

        evidence.write_json(
            "otadata-mutation-preclaim.json",
            {
                "timestamp_utc": utc_now(),
                "authorization_id": authorization_id,
                "identity_binding": "PASS",
                "app0_sha256_authority": "PASS",
                "app0_same_connection_md5_freshness": "PASS",
                "otadata_same_connection_md5_freshness": "PASS",
                "target_offset": f"0x{offset:x}",
                "entry_sha256": sha256_bytes(entry_data),
                "mutation_started": False,
            },
        )

        # flash_begin itself performs erase work. Once this boundary is entered,
        # persistent state may be uncertain even if the call raises.
        _write_mutation_phase(
            evidence,
            1,
            "FLASH_BEGIN_ENTERING",
            mutation_possible=True,
            authorization_id=authorization_id,
        )
        blocks = esp.flash_begin(OTA_ENTRY_SIZE, offset)
        _write_mutation_phase(
            evidence,
            2,
            "FLASH_BEGIN_COMPLETED",
            mutation_possible=True,
            authorization_id=authorization_id,
        )
        if blocks != 1:
            raise GuardError("unexpected flash_begin block count after mutation boundary")

        block = entry_data + b"\xff" * (flash_write_size - len(entry_data))
        _write_mutation_phase(
            evidence,
            3,
            "FLASH_BLOCK_ENTERING",
            mutation_possible=True,
            authorization_id=authorization_id,
        )
        esp.flash_block(block, 0)
        _write_mutation_phase(
            evidence,
            4,
            "FLASH_BLOCK_COMPLETED",
            mutation_possible=True,
            authorization_id=authorization_id,
        )
        esp.flash_finish(reboot=False)
        _write_mutation_phase(
            evidence,
            5,
            "FLASH_FINISH_COMPLETED",
            mutation_possible=True,
            authorization_id=authorization_id,
        )


# -------------------- Execution/evidence --------------------


def run_read_command(
    argv: Sequence[str], evidence: EvidenceStore, label: str
) -> subprocess.CompletedProcess[str]:
    validate_esptool_read_argv(argv)
    config_path = evidence.ensure_esptool_config()
    evidence.write_json(
        f"{label}.command.json",
        {
            "timestamp_utc": utc_now(),
            "label": label,
            "command_kind": "READ_ONLY_ESPTOOL_CLI",
            "argv": list(argv),
            "shell_rendering": shlex.join(argv),
            "env_overrides": {
                "ESPTOOL_OPEN_PORT_ATTEMPTS": "1",
                "ESPTOOL_CFGFILE": str(config_path),
            },
            "retry_contract": {
                "connect_attempts": 1,
                "open_port_attempts": 1,
                "mutation": False,
            },
        },
    )
    proc = subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        env=_safe_env(config_path),
    )
    evidence.write_text(f"{label}.stdout.txt", proc.stdout)
    evidence.write_text(f"{label}.stderr.txt", proc.stderr)
    evidence.write_json(
        f"{label}.result.json",
        {"timestamp_utc": utc_now(), "returncode": proc.returncode},
    )
    if proc.returncode != 0:
        raise GuardError(f"{label} failed with return code {proc.returncode}")
    return proc


ReadRunner = Callable[[Sequence[str], EvidenceStore, str], object]


def _load_exact(path: os.PathLike[str] | str, size: int, label: str) -> bytes:
    data = Path(path).read_bytes()
    if len(data) != size:
        raise GuardError(f"{label} must be exactly {size} bytes")
    return data


def _write_plan_evidence(store: EvidenceStore, plan: OtaSwitchPlan) -> Path:
    store.write_json("otadata-switch-plan.json", plan.public_dict())
    path = store.write_bytes("otadata-target-entry.bin", plan.entry_image)
    if path.stat().st_size != OTA_ENTRY_SIZE:
        raise GuardError("generated OTA entry image is not exactly 32 bytes")
    return path


def _verify_identity(
    python_exe: str,
    esptool_path: str,
    port: str,
    expected_base_mac: str,
    store: EvidenceStore,
    runner: ReadRunner,
) -> IdentityBinding:
    result = runner(
        build_identity_read_command(python_exe, esptool_path, port),
        store,
        "rom_identity_read",
    )
    output = getattr(result, "stdout", "")
    if not isinstance(output, str):
        raise GuardError("identity runner did not return textual stdout")
    binding = verify_identity_output(output, expected_base_mac)
    store.write_json("identity-binding.json", binding.public_dict())
    return binding


def _read_and_bind_app0(
    python_exe: str,
    esptool_path: str,
    port: str,
    store: EvidenceStore,
    runner: ReadRunner,
) -> AppPayloadBinding:
    output = store.path("app0-existing-readback.bin")
    runner(
        build_app0_read_command(python_exe, esptool_path, port, str(output)),
        store,
        "app0_existing_read",
    )
    binding = verify_app0_payload(output, APP0_EXPECTED_SHA256)
    store.write_json("app0_existing_read.binding.json", binding.public_dict())
    return binding


def _capture_failure_state(
    python_exe: str,
    esptool_path: str,
    port: str,
    store: EvidenceStore,
    runner: ReadRunner,
    pre: bytes,
    plan: OtaSwitchPlan,
    mutation_error: Exception,
) -> None:
    failure_path = store.path("otadata-failure-state.bin")
    record: dict[str, object] = {
        "timestamp_utc": utc_now(),
        "mutation_error_type": type(mutation_error).__name__,
        "mutation_retry": False,
        "capture_attempted": True,
    }
    try:
        runner(
            build_otadata_read_command(
                python_exe, esptool_path, port, str(failure_path)
            ),
            store,
            "otadata_failure_state_read",
        )
        observed = _load_exact(failure_path, OTADATA_SIZE, "failure-state otadata")
        expected_post = expected_post_otadata(pre, plan)
        if observed == pre:
            classification = "PRECHANGE_EXACT"
        elif observed == expected_post:
            classification = "EXPECTED_POSTCHANGE_EXACT"
        else:
            classification = "PARTIAL_OR_OTHER_STATE"
        record.update(
            {
                "capture_result": "PASS",
                "state_sha256": sha256_bytes(observed),
                "state_classification": classification,
                "equals_prechange": observed == pre,
                "equals_expected_postchange": observed == expected_post,
            }
        )
    except Exception as capture_error:  # evidence capture must never trigger mutation/retry
        record.update(
            {
                "capture_result": "FAIL",
                "capture_error_type": type(capture_error).__name__,
                "state_classification": "UNKNOWN",
            }
        )
    store.write_json("otadata-mutation-failure-state.json", record)


def _switch_to_app0_after_binding(
    python_exe: str,
    esptool_path: str,
    port: str,
    expected_base_mac: str,
    authorization_id: str,
    store: EvidenceStore,
    runner: ReadRunner,
    runtime: Mapping[str, object],
    app_binding: AppPayloadBinding,
) -> OtaSwitchPlan:
    pre_path = store.path("otadata-pre.bin")
    post_path = store.path("otadata-post.bin")
    runner(
        build_otadata_read_command(python_exe, esptool_path, port, str(pre_path)),
        store,
        "otadata_pre_read",
    )
    pre = _load_exact(pre_path, OTADATA_SIZE, "prechange otadata")
    plan = plan_ota_switch_to_app0(pre, app_binding)
    _write_plan_evidence(store, plan)

    try:
        _perform_direct_otadata_write_once(
            runtime,
            port=port,
            expected_base_mac=expected_base_mac,
            authorization_id=authorization_id,
            app_binding=app_binding,
            pre_otadata=pre,
            offset=plan.target_entry_flash_offset,
            entry_data=plan.entry_image,
            evidence=store,
        )
    except Exception as mutation_error:
        # If flash_begin was entered, persistent state may have changed. Capture one
        # bounded read-only snapshot, never retry the mutation, then re-raise.
        if store.path(
            "otadata-mutation-phase-01-flash-begin-entering.json"
        ).exists():
            _capture_failure_state(
                python_exe,
                esptool_path,
                port,
                store,
                runner,
                pre,
                plan,
                mutation_error,
            )
        raise

    runner(
        build_otadata_read_command(python_exe, esptool_path, port, str(post_path)),
        store,
        "otadata_post_read",
    )
    post = _load_exact(post_path, OTADATA_SIZE, "postchange otadata")
    verify_ota_switch(pre, post, plan)
    store.write_json(
        "otadata-post-verify.json",
        {
            "result": "PASS",
            "selected_slot": APP0_SLOT,
            "non_target_sector_byte_identical": True,
            "target_entry_sha256": plan.entry_image_sha256,
            "target_sector_expected_sha256": plan.expected_after_target_sector_sha256,
            "stock_esptool_write_flash_used": False,
            "mutation_retry": False,
            "same_connection_identity_recheck": True,
            "same_connection_app0_md5_freshness": True,
            "same_connection_otadata_md5_freshness": True,
        },
    )
    return plan


def execute_recovery_app0_to_slot0(
    python_exe: str,
    esptool_path: str,
    port: str,
    evidence_dir: os.PathLike[str] | str,
    *,
    expected_base_mac: str,
    authorization_id: str,
    runner: ReadRunner = run_read_command,
) -> WorkflowResult:
    """Current Board B recovery workflow. There is no app0 write path."""
    authorization_id = _validate_authorization_id(authorization_id)
    store = EvidenceStore(evidence_dir)
    config_path = store.ensure_esptool_config()
    store.write_json(
        "workflow.json",
        {
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "tool_mode": TOOL_MODE,
            "workflow": "RECOVERY_EXISTING_APP0_TO_SLOT0",
            "authorization_id": authorization_id,
            "authorization_replay_enforcement": "EXTERNAL_GATE_REQUIRED",
            "app0_write_allowed": False,
            "stock_esptool_write_flash_allowed": False,
            "started_utc": utc_now(),
        },
    )

    binding, runtime = bind_toolchain_runtime(
        python_exe, esptool_path, config_path=config_path
    )
    store.write_json("toolchain-binding.json", binding.public_dict())

    identity_binding = _verify_identity(
        python_exe, esptool_path, port, expected_base_mac, store, runner
    )
    app_binding = _read_and_bind_app0(
        python_exe, esptool_path, port, store, runner
    )
    plan = _switch_to_app0_after_binding(
        python_exe,
        esptool_path,
        port,
        expected_base_mac,
        authorization_id,
        store,
        runner,
        runtime,
        app_binding,
    )
    store.write_json(
        "workflow-result.json",
        {
            "result": "PASS",
            "authorization_id": authorization_id,
            "finished_utc": utc_now(),
        },
    )
    return WorkflowResult(identity_binding, app_binding, plan, str(store.root))


# -------------------- CLI --------------------


def _print_argv(label: str, argv: Sequence[str]) -> None:
    validate_esptool_read_argv(argv)
    print(f"{label}={shlex.join(argv)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-ota-guard")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--esptool", required=True, help="exact ESP-IDF v5.5.4 esptool.py wrapper"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-app0")
    verify.add_argument("--file", required=True)

    plan = sub.add_parser("plan-recovery")
    plan.add_argument("--port", required=True)
    plan.add_argument("--app0-readback", required=True)
    plan.add_argument("--otadata", required=True)

    recover = sub.add_parser("recover-app0-to-slot0")
    recover.add_argument("--port", required=True)
    recover.add_argument("--evidence-dir", required=True)
    recover.add_argument("--expected-base-mac", required=True)
    recover.add_argument("--authorization-id", required=True)

    tool = sub.add_parser("check-toolchain")
    tool.add_argument("--evidence-dir", required=True)
    tool.add_argument("--expected-version", default=EXPECTED_ESPTOOL_VERSION)
    tool.add_argument(
        "--expected-wrapper-sha256", default=EXPECTED_ESPTOOL_WRAPPER_SHA256
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-app0":
            binding = verify_app0_payload(args.file, APP0_EXPECTED_SHA256)
            print(json.dumps(binding.public_dict(), indent=2, sort_keys=True))
            print("APP0_BINDING=PASS")
            print("SECOND_FLASH_ALLOWED=false")
            return 0

        if args.command == "plan-recovery":
            app_binding = verify_app0_payload(
                args.app0_readback, APP0_EXPECTED_SHA256
            )
            raw = Path(args.otadata).read_bytes()
            if len(raw) != OTADATA_SIZE:
                raise GuardError("otadata must be exactly 0x2000 bytes")
            plan = plan_ota_switch_to_app0(raw, app_binding)
            print(json.dumps(plan.public_dict(), indent=2, sort_keys=True))
            _print_argv(
                "APP0_READ_ARGV",
                build_app0_read_command(
                    args.python, args.esptool, args.port, "<APP0_READBACK>"
                ),
            )
            _print_argv(
                "OTADATA_READ_ARGV",
                build_otadata_read_command(
                    args.python, args.esptool, args.port, "<OTADATA_READBACK>"
                ),
            )
            print("APP0_WRITE_ARGV=NOT_AVAILABLE")
            print("STOCK_WRITE_FLASH_MUTATION=FORBIDDEN")
            print("OTADATA_MUTATION=PROJECT_OWNED_DIRECT_ROM_SINGLE_ATTEMPT")
            return 0

        if args.command == "recover-app0-to-slot0":
            result = execute_recovery_app0_to_slot0(
                args.python,
                args.esptool,
                args.port,
                args.evidence_dir,
                expected_base_mac=args.expected_base_mac,
                authorization_id=args.authorization_id,
            )
            print(
                json.dumps(
                    {
                        "result": "PASS",
                        "identity_binding": result.identity_binding.public_dict(),
                        "app_binding": result.app_binding.public_dict(),
                        "ota_plan": result.ota_plan.public_dict(),
                        "evidence_dir": result.evidence_dir,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "check-toolchain":
            store = EvidenceStore(args.evidence_dir)
            config_path = store.ensure_esptool_config()
            binding, _runtime = bind_toolchain_runtime(
                args.python,
                args.esptool,
                config_path=config_path,
                expected_wrapper_sha256=args.expected_wrapper_sha256,
                expected_version=args.expected_version,
            )
            store.write_json("toolchain-binding.json", binding.public_dict())
            print(json.dumps(binding.public_dict(), indent=2, sort_keys=True))
            return 0

        raise GuardError("unknown command")
    except (GuardError, OSError, subprocess.SubprocessError, ImportError) as exc:
        print(f"N3W_OTA_GUARD_FAIL={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
