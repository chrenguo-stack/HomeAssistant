#!/usr/bin/env python3
"""N3W OTA Guard v0.2.

A narrow ESP32-C6 OTA deployment safety helper for the N3-W lab workflow.

This revision intentionally follows the *host deployment* semantics being repaired:
- exact app0 payload binding by SHA-256 before any slot switch;
- explicit esptool reset/connection arguments;
- no standalone physical app0 write primitive in the CLI;
- OTA selection changes only ``ota_seq`` + CRC, preserving ``seq_label`` and
  ``ota_state`` from the target OTA-select entry;
- one target 0x1000 otadata sector is erased implicitly by esptool write-flash,
  then only the 32-byte ``esp_ota_select_entry_t`` is written;
- the non-target otadata sector must remain byte-identical;
- physical evidence is durable and never stored only in a temporary directory.

The tool does *not* infer board identity from a serial port. Fresh silicon/role
binding remains an external execution gate.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
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
TOOL_VERSION = "0.2.0-review"

CHIP = "esp32c6"
BAUD = 115200
FLASH_SIZE = "8MB"
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
OTA_ENTRY_SIZE = 32
OTA_APP_COUNT = 2

UINT32_MAX = 0xFFFFFFFF

EXPECTED_ESPTOOL_VERSION = "5.2.0"
# Official ESP-IDF v5.5.4 components/esptool_py/esptool/esptool.py
EXPECTED_ESPTOOL_WRAPPER_SHA256 = "a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be"


class GuardError(RuntimeError):
    """Fail-closed guard violation."""


class OtaState(IntEnum):
    NEW = 0x0
    PENDING_VERIFY = 0x1
    VALID = 0x2
    INVALID = 0x3
    ABORTED = 0x4
    UNDEFINED = UINT32_MAX


KNOWN_OTA_STATES = {int(v) for v in OtaState}
SAFE_ACTIVE_STATES = {int(OtaState.VALID), int(OtaState.UNDEFINED)}
SAFE_TARGET_PRESERVE_STATES = {int(OtaState.VALID), int(OtaState.UNDEFINED)}


@dataclass(frozen=True)
class ToolchainBinding:
    python_executable: str
    esptool_path: str
    esptool_wrapper_sha256: str
    esptool_version: str

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
        d = asdict(self)
        d["offset"] = f"0x{self.offset:x}"
        return d


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
        d = asdict(self)
        d.pop("entry_image", None)
        d["target_entry_flash_offset"] = f"0x{self.target_entry_flash_offset:x}"
        d["preserved_ota_state_name"] = OtaState(self.preserved_ota_state).name
        d["changed_entry_byte_ranges"] = [
            [f"0x{a:x}", f"0x{b:x}"] for a, b in self.changed_entry_byte_ranges
        ]
        return d


@dataclass(frozen=True)
class WorkflowResult:
    identity_binding: IdentityBinding
    app_binding: AppPayloadBinding
    ota_plan: OtaSwitchPlan
    evidence_dir: str


class EvidenceStore:
    """Durable private evidence directory for one physical workflow."""

    def __init__(self, root: os.PathLike[str] | str, *, create: bool = True):
        self.root = Path(root)
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

    def path(self, name: str) -> Path:
        if Path(name).name != name:
            raise GuardError("evidence filename must be a basename")
        return self.root / name

    def _protect_file(self, p: Path) -> None:
        try:
            p.chmod(0o600)
        except OSError:
            pass

    def write_bytes(self, name: str, data: bytes) -> Path:
        p = self.path(name)
        p.write_bytes(data)
        self._protect_file(p)
        return p

    def write_text(self, name: str, text: str) -> Path:
        p = self.path(name)
        p.write_text(text, encoding="utf-8")
        self._protect_file(p)
        return p

    def ensure_esptool_config(self) -> Path:
        p = self.path("esptool.cfg")
        content = "[esptool]\nconnect_attempts = 1\nwrite_block_attempts = 1\n"
        if p.exists():
            if p.read_text(encoding="utf-8") != content:
                raise GuardError("existing esptool.cfg does not match guard retry contract")
        else:
            p.write_text(content, encoding="utf-8")
            self._protect_file(p)
        return p

    def write_json(self, name: str, obj: object) -> Path:
        return self.write_text(name, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: os.PathLike[str] | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b and start is None:
            start = i
        elif a == b and start is not None:
            ranges.append((start, i))
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
    entries = tuple(
        _parse_entry(raw[rel : rel + OTA_ENTRY_SIZE], idx)
        for idx, rel in enumerate(OTADATA_COPY_OFFSETS)
    )
    assert len(entries) == 2

    unknown = [e.index for e in entries if not e.erased and not e.state_known]
    if unknown:
        raise GuardError(f"unsupported/unknown ota_state in copies {unknown}")

    valid = [e for e in entries if e.idf_boot_valid]
    if not valid:
        raise GuardError("no valid OTA-select copy")
    if len(valid) == 2 and valid[0].seq == valid[1].seq:
        # IDF deterministically picks copy 0 on a tie, but the guard treats this
        # as unhealthy/ambiguous and refuses mutation.
        raise GuardError("ambiguous OTA-select state: both valid copies have equal ota_seq")

    active = max(valid, key=lambda e: e.seq)
    if active.seq == 0:
        raise GuardError("active ota_seq=0 is unsupported")
    if active.ota_state not in SAFE_ACTIVE_STATES:
        raise GuardError(f"active ota_state {active.state_name} is unsafe for host slot switch")
    selected_slot = (active.seq - 1) % OTA_APP_COUNT
    return OtaSnapshot(
        raw=raw,
        entries=(entries[0], entries[1]),
        active_index=active.index,
        selected_slot=selected_slot,
    )


def _next_seq_for_target(active_seq: int, target_slot: int) -> int:
    """Mirror ESP-IDF v5.5.4 esp_rewrite_ota_data sequence selection."""
    if target_slot not in (0, 1):
        raise GuardError("target slot must be 0 or 1")
    term = (target_slot + 1) % OTA_APP_COUNT
    i = 0
    while active_seq > term + i * OTA_APP_COUNT:
        i += 1
    new_seq = term + i * OTA_APP_COUNT
    if new_seq <= active_seq:
        raise GuardError("computed ota_seq is not newer than active ota_seq")
    if new_seq >= UINT32_MAX:
        raise GuardError("computed ota_seq would overflow/erase marker")
    return new_seq


def verify_app0_payload(
    path: os.PathLike[str] | str,
    expected_sha256: str = APP0_EXPECTED_SHA256,
) -> AppPayloadBinding:
    p = Path(path)
    size = p.stat().st_size
    if size != APP0_PAYLOAD_SIZE:
        raise GuardError(f"app0 payload size mismatch: got {size}, expected {APP0_PAYLOAD_SIZE}")
    digest = sha256_file(p)
    if digest.lower() != expected_sha256.lower():
        raise GuardError(f"app0 SHA256 mismatch: got {digest}")
    return AppPayloadBinding(
        slot=APP0_SLOT,
        offset=APP0_OFFSET,
        size=APP0_PAYLOAD_SIZE,
        sha256=digest.lower(),
        source_path=str(p),
    )


def verify_firmware_input(
    path: os.PathLike[str] | str,
    expected_sha256: str = APP0_EXPECTED_SHA256,
) -> AppPayloadBinding:
    return verify_app0_payload(path, expected_sha256)


def plan_ota_switch_to_app0(raw: bytes, app_binding: AppPayloadBinding) -> OtaSwitchPlan:
    """Plan the exact host-side slot switch after app0 payload binding.

    Host semantics deliberately preserve the target entry's seq_label + ota_state.
    Only ota_seq and CRC are changed. Physical write semantics are a 32-byte entry
    write at the target copy's sector start; esptool erases that affected 0x1000
    sector as part of write-flash.
    """
    if app_binding.slot != APP0_SLOT:
        raise GuardError("payload binding is not for app0")
    if app_binding.offset != APP0_OFFSET or app_binding.size != APP0_PAYLOAD_SIZE:
        raise GuardError("payload binding geometry does not match frozen app0 contract")
    if app_binding.sha256.lower() != APP0_EXPECTED_SHA256.lower():
        raise GuardError("payload binding does not match frozen firmware authority")

    snap = parse_otadata(raw)
    if snap.selected_slot == APP0_SLOT:
        raise GuardError("app0 is already selected; expected pre-switch app1")

    active = snap.entries[snap.active_index]
    target_copy = 1 - snap.active_index
    target_entry = snap.entries[target_copy]

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
    # If erased, raw already carries seq_label=FF and ota_state=UNDEFINED=FFFFFFFF.
    struct.pack_into("<I", entry_image, 0, new_seq)
    struct.pack_into("<I", entry_image, 28, new_crc)

    if bytes(entry_image[4:24]) != target_entry.seq_label:
        raise GuardError("planner changed seq_label")
    if struct.unpack_from("<I", entry_image, 24)[0] != preserved_state:
        raise GuardError("planner changed ota_state")

    changed = _diff_ranges(target_entry.raw, bytes(entry_image))
    for start, end in changed:
        if not ((start >= 0 and end <= 4) or (start >= 28 and end <= 32)):
            raise GuardError("planner changed bytes outside ota_seq/crc")

    sector_rel = OTADATA_COPY_OFFSETS[target_copy]
    before_sector = raw[sector_rel : sector_rel + OTADATA_SECTOR_SIZE]
    expected_after_sector = bytes(entry_image) + b"\xff" * (
        OTADATA_SECTOR_SIZE - OTA_ENTRY_SIZE
    )

    return OtaSwitchPlan(
        target_slot=APP0_SLOT,
        current_slot=snap.selected_slot,
        active_index=snap.active_index,
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


def verify_ota_switch(pre: bytes, post: bytes, plan: OtaSwitchPlan) -> None:
    if len(pre) != OTADATA_SIZE or len(post) != OTADATA_SIZE:
        raise GuardError("pre/post otadata must be each exactly 0x2000 bytes")

    target_rel = OTADATA_COPY_OFFSETS[plan.target_copy_index]
    other_idx = 1 - plan.target_copy_index
    other_rel = OTADATA_COPY_OFFSETS[other_idx]

    if post[other_rel : other_rel + OTADATA_SECTOR_SIZE] != pre[
        other_rel : other_rel + OTADATA_SECTOR_SIZE
    ]:
        raise GuardError("non-target otadata sector changed")

    expected_target_sector = plan.entry_image + b"\xff" * (
        OTADATA_SECTOR_SIZE - OTA_ENTRY_SIZE
    )
    actual_target_sector = post[target_rel : target_rel + OTADATA_SECTOR_SIZE]
    if actual_target_sector != expected_target_sector:
        raise GuardError("target otadata sector does not match erase+32-byte-write semantics")

    snap = parse_otadata(post)
    if snap.selected_slot != APP0_SLOT:
        raise GuardError("postwrite selected slot is not app0")
    if snap.active_index != plan.target_copy_index:
        raise GuardError("postwrite active otadata copy is not target copy")
    entry = snap.entries[plan.target_copy_index]
    if entry.seq != plan.new_seq:
        raise GuardError("postwrite ota_seq mismatch")
    if entry.crc != plan.expected_crc or not entry.crc_valid:
        raise GuardError("postwrite OTA CRC mismatch")
    if entry.ota_state != plan.preserved_ota_state:
        raise GuardError("postwrite ota_state was not preserved")
    if entry.seq_label != pre[target_rel + 4 : target_rel + 24]:
        raise GuardError("postwrite seq_label was not preserved")


_ALLOWED_SUBCOMMANDS = {"read-flash", "write-flash", "read-mac", "version"}


def _base_esptool_argv(python_exe: str, esptool_path: str, port: str) -> list[str]:
    if not port:
        raise GuardError("serial port is required for a physical command")
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


def validate_esptool_argv(argv: Sequence[str]) -> None:
    if len(argv) < 3:
        raise GuardError("esptool argv too short")
    sub_idxs = [i for i, token in enumerate(argv) if token in _ALLOWED_SUBCOMMANDS]
    if len(sub_idxs) != 1:
        raise GuardError("expected exactly one allowed esptool subcommand")
    sub_idx = sub_idxs[0]
    prefix = list(argv[:sub_idx])

    def exactly_one(flag: str, value: str | None = None) -> None:
        positions = [i for i, x in enumerate(prefix) if x == flag]
        if len(positions) != 1:
            raise GuardError(f"expected exactly one {flag} before subcommand")
        if value is not None:
            i = positions[0]
            if i + 1 >= len(prefix) or prefix[i + 1] != value:
                raise GuardError(f"{flag} must equal {value}")

    exactly_one("--chip", CHIP)
    exactly_one("--port")
    exactly_one("--baud", str(BAUD))
    exactly_one("--before", "no-reset")
    exactly_one("--after", "no-reset")
    exactly_one("--no-stub")
    exactly_one("--connect-attempts", str(CONNECT_ATTEMPTS))

    forbidden_reset_values = {
        "hard-reset",
        "soft-reset",
        "default-reset",
        "usb-reset",
        "no-reset-stub",
        "watchdog-reset",
    }
    if any(x in forbidden_reset_values for x in prefix):
        raise GuardError("forbidden/conflicting reset mode in esptool argv")

    suffix = list(argv[sub_idx + 1 :])
    if any(x in ("--before", "--after", "--no-stub", "--connect-attempts") for x in suffix):
        raise GuardError("global safety option appears after esptool subcommand")

    if argv[sub_idx] in {"read-flash", "write-flash"}:
        fs_positions = [i for i, x in enumerate(suffix) if x == "--flash-size"]
        if len(fs_positions) != 1:
            raise GuardError("physical flash command must set exactly one --flash-size")
        i = fs_positions[0]
        if i + 1 >= len(suffix) or suffix[i + 1] != FLASH_SIZE:
            raise GuardError(f"--flash-size must equal {FLASH_SIZE}")


def normalize_mac(value: str) -> str:
    v = value.strip().lower().replace("-", ":")
    if not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", v):
        raise GuardError(f"invalid MAC address: {value}")
    return v


def build_identity_read_command(
    python_exe: str, esptool_path: str, port: str
) -> list[str]:
    argv = _base_esptool_argv(python_exe, esptool_path, port) + ["read-mac"]
    validate_esptool_argv(argv)
    return argv


def verify_identity_output(output: str, expected_base_mac: str) -> IdentityBinding:
    expected = normalize_mac(expected_base_mac)
    candidates = {
        normalize_mac(x)
        for x in re.findall(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", output)
    }
    if expected not in candidates:
        raise GuardError(
            f"ROM identity mismatch: expected {expected}, observed {sorted(candidates) or ['NONE']}"
        )
    return IdentityBinding(expected_base_mac=expected, observed_base_mac=expected)


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
    validate_esptool_argv(argv)
    return argv


def _build_app0_write_command(
    python_exe: str, esptool_path: str, port: str, firmware_path: str
) -> list[str]:
    # Internal helper for the bounded *fresh deployment workflow only*.
    argv = _base_esptool_argv(python_exe, esptool_path, port) + [
        "write-flash",
        "--flash-size",
        FLASH_SIZE,
        hex(APP0_OFFSET),
        firmware_path,
    ]
    validate_esptool_argv(argv)
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
    validate_esptool_argv(argv)
    return argv


def build_otadata_entry_write_command(
    python_exe: str,
    esptool_path: str,
    port: str,
    plan: OtaSwitchPlan,
    entry_file: str,
) -> list[str]:
    if plan.target_entry_flash_offset not in (0x9000, 0xA000):
        raise GuardError("refusing otadata write outside fixed copy sectors")
    argv = _base_esptool_argv(python_exe, esptool_path, port) + [
        "write-flash",
        "--flash-size",
        FLASH_SIZE,
        hex(plan.target_entry_flash_offset),
        entry_file,
    ]
    validate_esptool_argv(argv)
    return argv


def _safe_env(config_path: os.PathLike[str] | str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    # Eliminate esptool's separate open-port loop. --connect-attempts=1 handles
    # the connection handshake loop; this controls repeated port opening.
    env["ESPTOOL_OPEN_PORT_ATTEMPTS"] = "1"
    if config_path is not None:
        env["ESPTOOL_CFGFILE"] = str(config_path)
    return env


def bind_toolchain(
    python_exe: str,
    esptool_path: str,
    *,
    expected_wrapper_sha256: str = EXPECTED_ESPTOOL_WRAPPER_SHA256,
    expected_version: str = EXPECTED_ESPTOOL_VERSION,
) -> ToolchainBinding:
    py = Path(python_exe)
    tool = Path(esptool_path)
    if not py.exists():
        raise GuardError(f"python executable not found: {py}")
    if not tool.is_file():
        raise GuardError(f"esptool wrapper not found: {tool}")
    digest = sha256_file(tool)
    if digest.lower() != expected_wrapper_sha256.lower():
        raise GuardError(f"esptool wrapper SHA256 mismatch: {digest}")

    proc = subprocess.run(
        [str(py), str(tool), "version"],
        check=False,
        capture_output=True,
        text=True,
        env=_safe_env(),
    )
    combined = f"{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        raise GuardError(f"esptool version query failed: rc={proc.returncode}")
    match = re.search(r"(?<!\d)(\d+\.\d+\.\d+)(?!\d)", combined)
    if not match or match.group(1) != expected_version:
        raise GuardError(f"unexpected esptool version output: {combined.strip()}")
    return ToolchainBinding(
        python_executable=str(py),
        esptool_path=str(tool),
        esptool_wrapper_sha256=digest,
        esptool_version=match.group(1),
    )


def run_esptool(
    argv: Sequence[str],
    evidence: EvidenceStore,
    label: str,
) -> subprocess.CompletedProcess[str]:
    validate_esptool_argv(argv)
    config_path = evidence.ensure_esptool_config()
    command_record = {
        "timestamp_utc": utc_now(),
        "label": label,
        "argv": list(argv),
        "shell_rendering": shlex.join(argv),
        "env_overrides": {
            "ESPTOOL_OPEN_PORT_ATTEMPTS": "1",
            "ESPTOOL_CFGFILE": str(config_path),
        },
        "retry_contract": {
            "connect_attempts": 1,
            "open_port_attempts": 1,
            "write_block_attempts": 1,
            "workflow_retry": False,
        },
    }
    evidence.write_json(f"{label}.command.json", command_record)
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


Runner = Callable[[Sequence[str], EvidenceStore, str], object]


def _load_exact(path: os.PathLike[str] | str, size: int, label: str) -> bytes:
    data = Path(path).read_bytes()
    if len(data) != size:
        raise GuardError(f"{label} must be exactly {size} bytes")
    return data


def _write_plan_evidence(store: EvidenceStore, plan: OtaSwitchPlan) -> Path:
    store.write_json("otadata-switch-plan.json", plan.public_dict())
    p = store.write_bytes("otadata-target-entry.bin", plan.entry_image)
    if p.stat().st_size != OTA_ENTRY_SIZE:
        raise GuardError("generated OTA entry image is not exactly 32 bytes")
    return p


def _verify_identity(
    python_exe: str,
    esptool_path: str,
    port: str,
    expected_base_mac: str,
    store: EvidenceStore,
    runner: Runner,
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
    runner: Runner,
    *,
    expected_sha256: str,
    filename: str,
    label: str,
) -> AppPayloadBinding:
    output = store.path(filename)
    runner(
        build_app0_read_command(python_exe, esptool_path, port, str(output)),
        store,
        label,
    )
    binding = verify_app0_payload(output, expected_sha256)
    store.write_json(f"{label}.binding.json", binding.public_dict())
    return binding


def _switch_to_app0_after_binding(
    python_exe: str,
    esptool_path: str,
    port: str,
    store: EvidenceStore,
    runner: Runner,
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
    entry_path = _write_plan_evidence(store, plan)

    runner(
        build_otadata_entry_write_command(
            python_exe, esptool_path, port, plan, str(entry_path)
        ),
        store,
        "otadata_entry_write",
    )

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
    runner: Runner = run_esptool,
    require_toolchain_binding: bool = True,
) -> WorkflowResult:
    """Recovery workflow: *never* writes app0.

    This is the correct workflow for the current Board B: read existing app0,
    bind exact SHA, then switch otadata only if the payload is already exact.
    """
    store = EvidenceStore(evidence_dir)
    store.write_json(
        "workflow.json",
        {
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "workflow": "RECOVERY_EXISTING_APP0_TO_SLOT0",
            "app0_write_allowed": False,
            "started_utc": utc_now(),
        },
    )
    if require_toolchain_binding:
        binding = bind_toolchain(python_exe, esptool_path)
        store.write_json("toolchain-binding.json", binding.public_dict())

    identity_binding = _verify_identity(
        python_exe, esptool_path, port, expected_base_mac, store, runner
    )
    app_binding = _read_and_bind_app0(
        python_exe,
        esptool_path,
        port,
        store,
        runner,
        expected_sha256=APP0_EXPECTED_SHA256,
        filename="app0-existing-readback.bin",
        label="app0_existing_read",
    )
    plan = _switch_to_app0_after_binding(
        python_exe, esptool_path, port, store, runner, app_binding
    )
    store.write_json("workflow-result.json", {"result": "PASS", "finished_utc": utc_now()})
    return WorkflowResult(identity_binding, app_binding, plan, str(store.root))


def execute_fresh_deploy_app0_to_slot0(
    python_exe: str,
    esptool_path: str,
    port: str,
    firmware_path: os.PathLike[str] | str,
    evidence_dir: os.PathLike[str] | str,
    *,
    expected_base_mac: str,
    write_authorization_id: str,
    runner: Runner = run_esptool,
    require_toolchain_binding: bool = True,
) -> WorkflowResult:
    """Fresh deployment workflow with one bounded app0 write opportunity.

    The workflow first reads app0. If the exact target payload is already present,
    it *skips* the write and proceeds from that binding. Otherwise a non-empty
    write authorization id is required, the firmware authority is verified, one
    app0 write is issued, and exact readback binding is mandatory before otadata.
    """
    if not write_authorization_id.strip():
        raise GuardError("fresh deployment requires a non-empty write authorization id")

    firmware_binding = verify_firmware_input(firmware_path, APP0_EXPECTED_SHA256)
    store = EvidenceStore(evidence_dir)
    store.write_json(
        "workflow.json",
        {
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "workflow": "FRESH_DEPLOY_APP0_TO_SLOT0",
            "write_authorization_id": write_authorization_id,
            "started_utc": utc_now(),
        },
    )
    store.write_json("firmware-binding.json", firmware_binding.public_dict())
    if require_toolchain_binding:
        binding = bind_toolchain(python_exe, esptool_path)
        store.write_json("toolchain-binding.json", binding.public_dict())

    identity_binding = _verify_identity(
        python_exe, esptool_path, port, expected_base_mac, store, runner
    )
    pre_path = store.path("app0-prewrite-readback.bin")
    runner(
        build_app0_read_command(python_exe, esptool_path, port, str(pre_path)),
        store,
        "app0_prewrite_read",
    )
    pre_data = _load_exact(pre_path, APP0_PAYLOAD_SIZE, "prewrite app0 readback")
    pre_digest = sha256_bytes(pre_data)
    store.write_json(
        "app0-prewrite-binding.json",
        {"size": len(pre_data), "sha256": pre_digest},
    )

    if pre_digest.lower() == APP0_EXPECTED_SHA256.lower():
        # Existing exact payload: fail-safe skip, never rewrite identical firmware.
        app_binding = verify_app0_payload(pre_path, APP0_EXPECTED_SHA256)
        store.write_json(
            "app0-write-decision.json",
            {"decision": "SKIP_ALREADY_EXACT", "app0_write_executed": False},
        )
    else:
        store.write_json(
            "app0-write-decision.json",
            {"decision": "WRITE_ONCE_AUTHORIZED", "app0_write_executed": True},
        )
        runner(
            _build_app0_write_command(
                python_exe, esptool_path, port, str(Path(firmware_path))
            ),
            store,
            "app0_write",
        )
        app_binding = _read_and_bind_app0(
            python_exe,
            esptool_path,
            port,
            store,
            runner,
            expected_sha256=APP0_EXPECTED_SHA256,
            filename="app0-postwrite-readback.bin",
            label="app0_postwrite_read",
        )

    plan = _switch_to_app0_after_binding(
        python_exe, esptool_path, port, store, runner, app_binding
    )
    store.write_json("workflow-result.json", {"result": "PASS", "finished_utc": utc_now()})
    return WorkflowResult(identity_binding, app_binding, plan, str(store.root))


def _print_argv(label: str, argv: Sequence[str]) -> None:
    validate_esptool_argv(argv)
    print(f"{label}={shlex.join(argv)}")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="n3w-ota-guard")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--esptool", required=True, help="exact ESP-IDF v5.5.4 esptool.py wrapper")
    sub = p.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-app0")
    verify.add_argument("--file", required=True)

    plan = sub.add_parser("plan-recovery")
    plan.add_argument("--port", required=True)
    plan.add_argument("--app0-readback", required=True)
    plan.add_argument("--otadata", required=True)
    plan.add_argument("--entry-file", default="<OTADATA_ENTRY_32B>")

    recover = sub.add_parser("recover-app0-to-slot0")
    recover.add_argument("--port", required=True)
    recover.add_argument("--evidence-dir", required=True)
    recover.add_argument("--expected-base-mac", required=True)

    fresh = sub.add_parser("fresh-deploy-app0-to-slot0")
    fresh.add_argument("--port", required=True)
    fresh.add_argument("--firmware", required=True)
    fresh.add_argument("--evidence-dir", required=True)
    fresh.add_argument("--expected-base-mac", required=True)
    fresh.add_argument("--write-authorization-id", required=True)

    tool = sub.add_parser("check-toolchain")
    tool.add_argument("--expected-version", default=EXPECTED_ESPTOOL_VERSION)
    tool.add_argument("--expected-wrapper-sha256", default=EXPECTED_ESPTOOL_WRAPPER_SHA256)
    return p


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
            app_binding = verify_app0_payload(args.app0_readback, APP0_EXPECTED_SHA256)
            raw = _load_exact(args.otadata, OTADATA_SIZE, "otadata")
            plan = plan_ota_switch_to_app0(raw, app_binding)
            print(json.dumps(plan.public_dict(), indent=2, sort_keys=True))
            _print_argv(
                "APP0_READ_ARGV",
                build_app0_read_command(args.python, args.esptool, args.port, "<APP0_READBACK>"),
            )
            _print_argv(
                "OTADATA_READ_ARGV",
                build_otadata_read_command(args.python, args.esptool, args.port, "<OTADATA_READBACK>"),
            )
            _print_argv(
                "OTADATA_ENTRY_WRITE_ARGV",
                build_otadata_entry_write_command(
                    args.python, args.esptool, args.port, plan, args.entry_file
                ),
            )
            print("APP0_WRITE_ARGV=NOT_AVAILABLE_IN_RECOVERY_WORKFLOW")
            return 0

        if args.command == "recover-app0-to-slot0":
            result = execute_recovery_app0_to_slot0(
                args.python,
                args.esptool,
                args.port,
                args.evidence_dir,
                expected_base_mac=args.expected_base_mac,
            )
            print(json.dumps({
                "result": "PASS",
                "identity_binding": result.identity_binding.public_dict(),
                "app_binding": result.app_binding.public_dict(),
                "ota_plan": result.ota_plan.public_dict(),
                "evidence_dir": result.evidence_dir,
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "fresh-deploy-app0-to-slot0":
            result = execute_fresh_deploy_app0_to_slot0(
                args.python,
                args.esptool,
                args.port,
                args.firmware,
                args.evidence_dir,
                expected_base_mac=args.expected_base_mac,
                write_authorization_id=args.write_authorization_id,
            )
            print(json.dumps({
                "result": "PASS",
                "identity_binding": result.identity_binding.public_dict(),
                "app_binding": result.app_binding.public_dict(),
                "ota_plan": result.ota_plan.public_dict(),
                "evidence_dir": result.evidence_dir,
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "check-toolchain":
            binding = bind_toolchain(
                args.python,
                args.esptool,
                expected_wrapper_sha256=args.expected_wrapper_sha256,
                expected_version=args.expected_version,
            )
            print(json.dumps(binding.public_dict(), indent=2, sort_keys=True))
            return 0

        raise GuardError("unknown command")
    except (GuardError, OSError) as exc:
        print(f"N3W_OTA_GUARD_FAIL={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
