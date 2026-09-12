#!/usr/bin/env python3
"""KF-089 ID18 Board A inactive-app0 Schema-v5 deployment.

Exactly one bounded mutation primitive is permitted: a direct ESP32-C6 ROM write
of the exact frozen Schema-v5 payload to inactive app0. Stock esptool
``write-flash`` is deliberately not used because esptool v5.3.1 has an
independent whole-image reconnect/retry loop in that high-level path.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

PACKAGE_SCHEMA_VERSION = 1
EXPECTED_ESPTOOL_VERSION = "5.3.1"
EXPECTED_BOARD_A_SUFFIX = "f3:50"
BAUD = 115200
FLASH_SIZE_BYTES = 8 * 1024 * 1024
EXPECTED_FLASH_WRITE_SIZE = 0x400

PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0x1000
OTADATA_OFFSET = 0x9000
OTADATA_SIZE = 0x2000
APP0_OFFSET = 0x10000
APP0_PARTITION_SIZE = 0x3C0000
APP1_OFFSET = 0x3D0000
APP1_PARTITION_SIZE = 0x3C0000

SCHEMA5_SOURCE_COMMIT = "5d58727f5040281ee2beb9597f66a6a2da9bac57"
SCHEMA5_FIRMWARE_SIZE = 1_115_648
SCHEMA5_FIRMWARE_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"

EXPECTED_SELECTED_SLOT = 1
EXPECTED_INACTIVE_SLOT = 0
EXPECTED_ACTIVE_SEQ = 4
EXPECTED_ACTIVE_STATE = 2

PARTITION_MAGIC = 0x50AA
PARTITION_TYPE_APP = 0x00
PARTITION_TYPE_DATA = 0x01
PARTITION_SUBTYPE_OTA_DATA = 0x00
PARTITION_SUBTYPE_OTA0 = 0x10
PARTITION_SUBTYPE_OTA1 = 0x11

UINT32_MAX = 0xFFFFFFFF
OTA_ENTRY_SIZE = 32
OTA_COPY_RELATIVE_OFFSETS = (0x0000, 0x1000)
OTA_APP_COUNT = 2
OTA_STATE_INVALID = 0x3
OTA_STATE_ABORTED = 0x4

BASE_MAC_RE = re.compile(
    r"(?im)^\s*BASE MAC:\s*([0-9a-f]{2}(?::[0-9a-f]{2}){5})\s*$"
)
VERSION_RE = re.compile(r"(?i)\bv?(\d+\.\d+\.\d+)\b")
READ_ONLY_FORBIDDEN = {
    "write-flash", "erase-flash", "erase-region", "write-mem", "write-flash-status",
    "write_flash", "erase_flash", "erase_region", "write_mem", "write_flash_status",
}


class StopExecution(RuntimeError):
    pass


@dataclass(frozen=True)
class PartitionEntry:
    label: str
    type: int
    subtype: int
    offset: int
    size: int
    flags: int


@dataclass(frozen=True)
class OtaEntry:
    index: int
    seq: int
    ota_state: int
    crc: int
    expected_crc: int
    erased: bool
    crc_valid: bool
    boot_valid: bool

    @property
    def slot(self) -> int | None:
        if not self.boot_valid or self.seq in (0, UINT32_MAX):
            return None
        return (self.seq - 1) % OTA_APP_COUNT


@dataclass(frozen=True)
class OtaSnapshot:
    entries: tuple[OtaEntry, OtaEntry]
    active_index: int
    selected_slot: int
    active_state: int
    active_seq: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    os.chmod(path, 0o600)


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file():
            return candidate
    raise StopExecution("repository root could not be located")


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_manifest(package_dir: Path) -> dict[str, Any]:
    value = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    if value.get("package_schema_version") != PACKAGE_SCHEMA_VERSION:
        raise StopExecution("manifest package schema version mismatch")
    if value.get("gate_id") != "id18_board_a_inactive_app0_schema5_deployment":
        raise StopExecution("manifest gate id mismatch")
    return value


def esptool_base(port: str) -> list[str]:
    return [
        sys.executable, "-m", "esptool",
        "--chip", "esp32c6",
        "--port", port,
        "--before", "no-reset",
        "--after", "no-reset",
        "--no-stub",
    ]


def assert_read_only_argv(argv: Iterable[str]) -> None:
    lowered = {str(item).strip().lower() for item in argv}
    forbidden = sorted(lowered & READ_ONLY_FORBIDDEN)
    if forbidden:
        raise StopExecution(f"write-like token forbidden in read-only command: {forbidden}")


def build_read_mac_command(port: str) -> list[str]:
    argv = [*esptool_base(port), "read-mac"]
    assert_read_only_argv(argv)
    return argv


def build_read_flash_command(port: str, offset: int, size: int, output: Path) -> list[str]:
    argv = [
        *esptool_base(port),
        "read-flash", "--flash-size", "8MB",
        hex(offset), hex(size), str(output),
    ]
    assert_read_only_argv(argv)
    return argv


def parse_base_mac(stdout: str) -> str:
    matches = sorted(set(value.lower() for value in BASE_MAC_RE.findall(stdout)))
    if len(matches) != 1:
        raise StopExecution("expected exactly one complete BASE MAC line")
    return matches[0]


def mac_suffix(mac: str) -> str:
    parts = mac.split(":")
    if len(parts) != 6:
        raise StopExecution("normalized BASE MAC is invalid")
    return ":".join(parts[-2:]).lower()


def mac_tuple(mac: str) -> tuple[int, ...]:
    return tuple(int(part, 16) for part in mac.split(":"))


def parse_partition_table(raw: bytes) -> dict[str, PartitionEntry]:
    if len(raw) != PARTITION_TABLE_SIZE:
        raise StopExecution("partition table capture size mismatch")
    entries: dict[str, PartitionEntry] = {}
    for offset in range(0, len(raw), 32):
        chunk = raw[offset: offset + 32]
        magic = int.from_bytes(chunk[0:2], "little")
        if magic == 0xFFFF:
            break
        if magic == 0xEBEB:
            continue
        if magic != PARTITION_MAGIC:
            raise StopExecution(f"partition table entry magic mismatch at 0x{offset:x}")
        ptype = chunk[2]
        subtype = chunk[3]
        poffset = int.from_bytes(chunk[4:8], "little")
        psize = int.from_bytes(chunk[8:12], "little")
        label = chunk[12:28].split(b"\x00", 1)[0].decode("ascii", errors="strict")
        flags = int.from_bytes(chunk[28:32], "little")
        if label in entries:
            raise StopExecution(f"duplicate partition label: {label}")
        entries[label] = PartitionEntry(label, ptype, subtype, poffset, psize, flags)

    expected = {
        "otadata": (PARTITION_TYPE_DATA, PARTITION_SUBTYPE_OTA_DATA, OTADATA_OFFSET, OTADATA_SIZE),
        "app0": (PARTITION_TYPE_APP, PARTITION_SUBTYPE_OTA0, APP0_OFFSET, APP0_PARTITION_SIZE),
        "app1": (PARTITION_TYPE_APP, PARTITION_SUBTYPE_OTA1, APP1_OFFSET, APP1_PARTITION_SIZE),
    }
    for label, contract in expected.items():
        entry = entries.get(label)
        if entry is None:
            raise StopExecution(f"required partition missing: {label}")
        observed = (entry.type, entry.subtype, entry.offset, entry.size)
        if observed != contract:
            raise StopExecution(
                f"partition geometry mismatch for {label}: observed={observed!r} expected={contract!r}"
            )
    return entries


def ota_crc(seq: int) -> int:
    return binascii.crc32(struct.pack("<I", seq), UINT32_MAX) & UINT32_MAX


def parse_ota_entry(raw: bytes, index: int) -> OtaEntry:
    if len(raw) != OTA_ENTRY_SIZE:
        raise StopExecution("OTA entry size mismatch")
    seq = struct.unpack_from("<I", raw, 0)[0]
    ota_state = struct.unpack_from("<I", raw, 24)[0]
    crc = struct.unpack_from("<I", raw, 28)[0]
    erased = raw == b"\xff" * OTA_ENTRY_SIZE
    expected_crc = ota_crc(seq)
    crc_valid = crc == expected_crc
    boot_valid = (
        not erased
        and seq not in (0, UINT32_MAX)
        and ota_state not in (OTA_STATE_INVALID, OTA_STATE_ABORTED)
        and crc_valid
    )
    return OtaEntry(index, seq, ota_state, crc, expected_crc, erased, crc_valid, boot_valid)


def parse_otadata(raw: bytes) -> OtaSnapshot:
    if len(raw) != OTADATA_SIZE:
        raise StopExecution("otadata capture size mismatch")
    entries_list = [
        parse_ota_entry(raw[rel: rel + OTA_ENTRY_SIZE], index)
        for index, rel in enumerate(OTA_COPY_RELATIVE_OFFSETS)
    ]
    entries = (entries_list[0], entries_list[1])
    valid = [entry for entry in entries if entry.boot_valid]
    if not valid:
        raise StopExecution("no valid OTA-select copy")
    if len(valid) == 2 and valid[0].seq == valid[1].seq:
        raise StopExecution("ambiguous OTA-select state: equal valid ota_seq")
    active = max(valid, key=lambda item: item.seq)
    slot = active.slot
    if slot not in (0, 1):
        raise StopExecution("selected OTA slot is invalid")
    return OtaSnapshot(entries, active.index, slot, active.ota_state, active.seq)


def verify_expected_prestate(ota: OtaSnapshot) -> None:
    if ota.selected_slot != EXPECTED_SELECTED_SLOT:
        raise StopExecution("selected OTA slot drifted from ID17")
    if 1 - ota.selected_slot != EXPECTED_INACTIVE_SLOT:
        raise StopExecution("inactive OTA slot drifted from ID17")
    if ota.active_seq != EXPECTED_ACTIVE_SEQ:
        raise StopExecution("active OTA sequence drifted from ID17")
    if ota.active_state != EXPECTED_ACTIVE_STATE:
        raise StopExecution("active OTA state drifted from ID17")


def verify_firmware(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StopExecution("exact Schema-v5 firmware file does not exist")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != SCHEMA5_FIRMWARE_SIZE:
        raise StopExecution("Schema-v5 firmware size mismatch")
    if digest != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution("Schema-v5 firmware SHA256 mismatch")
    return {"size": size, "sha256": digest, "source_commit": SCHEMA5_SOURCE_COMMIT}


def make_esptool_cfg(root: Path) -> Path:
    path = root / "esptool.cfg"
    content = (
        "[esptool]\n"
        "connect_attempts = 1\n"
        "write_block_attempts = 1\n"
        "open_port_attempts = 1\n"
    )
    write_text(path, content)
    return path


def run_recorded(
    *, root: Path, index: int, label: str, argv: list[str], cwd: Path,
    target_operation: bool = False, extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    assert_read_only_argv(argv)
    op_dir = root / f"op_{index:02d}_{label}"
    ensure_private_dir(op_dir)
    write_json(op_dir / "command.json", {
        "argv": argv,
        "cwd": str(cwd),
        "label": label,
        "operation_index": index,
        "target_operation": target_operation,
        "mutation_operation": False,
        "utc_start": utc_now(),
        "environment_overrides": dict(sorted((extra_env or {}).items())),
    })
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        write_text(op_dir / "stdout.txt", "")
        write_text(op_dir / "stderr.txt", f"{type(exc).__name__}: {exc}\n")
        write_json(op_dir / "result.json", {
            "command_started": False,
            "returncode": None,
            "target_access_occurred": False if target_operation else None,
            "utc_end": utc_now(),
        })
        raise StopExecution(f"{label} process launch failed") from exc

    write_text(op_dir / "stdout.txt", completed.stdout or "")
    write_text(op_dir / "stderr.txt", completed.stderr or "")
    write_json(op_dir / "result.json", {
        "command_started": True,
        "returncode": completed.returncode,
        "target_access_occurred": (
            True if target_operation and completed.returncode == 0
            else "UNKNOWN" if target_operation else None
        ),
        "utc_end": utc_now(),
    })
    return completed


def verify_host(root: Path, repo_root: Path, expected_commit: str, firmware: Path) -> int:
    op_index = 1
    for label, argv, expected in (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
    ):
        result = run_recorded(root=root, index=op_index, label=label, argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        op_index += 1

    result = run_recorded(
        root=root, index=op_index, label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"], cwd=repo_root,
    )
    versions = VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    op_index += 1

    binding = verify_firmware(firmware)
    binding["path_sha256"] = hashlib.sha256(str(firmware).encode()).hexdigest()
    write_json(root / "firmware_binding_private.json", binding)
    return op_index


def verify_port_locator(root: Path, port: str) -> None:
    path = Path(port)
    info = path.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise StopExecution("Board A port locator is not a character device")
    write_json(root / "host_port_locator_preflight.json", {
        "serial_open": False,
        "board_a_locator": str(path),
        "resolved_locator": os.path.realpath(str(path)),
        "character_device": True,
        "checked_at": utc_now(),
    })


def write_authorization(root: Path, auth: str, execution_id: str, *, claimed: bool) -> None:
    value: dict[str, Any] = {
        "authorization_id": auth,
        "execution_id": execution_id,
        "claimed": claimed,
        "consumed": claimed,
        "replay_permitted": False,
    }
    if claimed:
        now = utc_now()
        value.update({
            "claim_boundary": "immediately_before_board_a_read_mac",
            "claimed_at": now,
            "consumed_at": now,
        })
    write_json(root / "authorization.json", value)


def module_binding(module: object) -> dict[str, str]:
    raw = getattr(module, "__file__", None)
    if not raw:
        raise StopExecution("esptool runtime module has no file binding")
    path = Path(raw).resolve()
    return {"path": str(path), "sha256": sha256_file(path)}


def bind_direct_rom_runtime(cfg: Path, evidence_root: Path) -> dict[str, Any]:
    if any(name == "esptool" or name.startswith("esptool.") for name in sys.modules):
        raise StopExecution("esptool imported before direct-ROM retry contract was bound")
    os.environ["ESPTOOL_CFGFILE"] = str(cfg.resolve())
    os.environ["ESPTOOL_OPEN_PORT_ATTEMPTS"] = "1"

    esptool = importlib.import_module("esptool")
    loader = importlib.import_module("esptool.loader")
    cmds = importlib.import_module("esptool.cmds")
    esp32c6 = importlib.import_module("esptool.targets.esp32c6")

    if getattr(esptool, "__version__", None) != EXPECTED_ESPTOOL_VERSION:
        raise StopExecution("unexpected esptool runtime version")
    if loader.WRITE_BLOCK_ATTEMPTS != 1:
        raise StopExecution("esptool block retry contract is not one attempt")
    esp_cls = esp32c6.ESP32C6ROM
    if esp_cls.CHIP_NAME != "ESP32-C6":
        raise StopExecution("unexpected direct-ROM target class")
    if esp_cls.FLASH_WRITE_SIZE != EXPECTED_FLASH_WRITE_SIZE:
        raise StopExecution("unexpected direct-ROM flash write block size")

    binding = {
        "esptool_version": getattr(esptool, "__version__", None),
        "loader_write_block_attempts": loader.WRITE_BLOCK_ATTEMPTS,
        "high_level_write_flash_attempts_not_used": loader.ESPLoader.WRITE_FLASH_ATTEMPTS,
        "stock_high_level_write_flash_used": False,
        "flash_finish_used": False,
        "esp32c6_flash_write_size": esp_cls.FLASH_WRITE_SIZE,
        "esptool_module": module_binding(esptool),
        "loader_module": module_binding(loader),
        "cmds_module": module_binding(cmds),
        "esp32c6_module": module_binding(esp32c6),
    }
    write_json(evidence_root / "direct_rom_runtime_binding_private.json", binding)
    return {
        "ESP32C6ROM": esp_cls,
        "attach_flash": cmds.attach_flash,
        "flash_write_size": esp_cls.FLASH_WRITE_SIZE,
        "binding": binding,
    }


def write_mutation_progress(root: Path, **values: Any) -> None:
    payload = {"utc": utc_now(), **values}
    write_json(root / "direct_rom_mutation_progress.json", payload)


def direct_write_app0_once(
    *, runtime: Mapping[str, Any], root: Path, port: str, expected_base_mac: str,
    firmware: Path, pre_app0: Path, pre_otadata: bytes, pre_app1: Path,
) -> None:
    data = firmware.read_bytes()
    if len(data) != SCHEMA5_FIRMWARE_SIZE or sha256_bytes(data) != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution("direct mutation firmware binding changed")
    if len(pre_otadata) != OTADATA_SIZE:
        raise StopExecution("direct mutation otadata preimage size mismatch")

    expected_mac = mac_tuple(expected_base_mac)
    expected_app0_md5 = md5_file(pre_app0)
    expected_otadata_md5 = md5_bytes(pre_otadata)
    expected_app1_md5 = md5_file(pre_app1)
    expected_firmware_md5 = md5_bytes(data)

    esp_cls = runtime["ESP32C6ROM"]
    attach_flash = runtime["attach_flash"]
    flash_write_size = int(runtime["flash_write_size"])
    if flash_write_size != EXPECTED_FLASH_WRITE_SIZE:
        raise StopExecution("direct mutation flash write size mismatch")

    write_json(root / "direct_rom_mutation_attempt.json", {
        "primitive": "DIRECT_ESP32C6_ROM_APP0_SINGLE_CONNECTION",
        "stock_high_level_write_flash_used": False,
        "flash_finish_used": False,
        "target_offset": hex(APP0_OFFSET),
        "firmware_size": len(data),
        "firmware_sha256": sha256_bytes(data),
        "connect_attempts": 1,
        "write_block_attempts": 1,
        "whole_image_retry": False,
        "automatic_rollback": False,
        "utc": utc_now(),
    })

    with esp_cls(port, BAUD) as esp:  # type: ignore[operator]
        esp.connect(mode="no-reset", attempts=1)
        if getattr(esp, "sync_stub_detected", False) or getattr(esp, "IS_STUB", False):
            raise StopExecution("existing flasher stub detected; ROM-only mutation required")
        if getattr(esp, "secure_download_mode", False):
            raise StopExecution("unexpected secure download mode")
        if tuple(esp.read_mac("BASE_MAC")) != expected_mac:
            raise StopExecution("mutation-time ROM identity mismatch")

        attach_flash(esp)  # type: ignore[operator]
        esp.flash_set_parameters(FLASH_SIZE_BYTES)
        if str(esp.flash_md5sum(APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE)).lower() != expected_app0_md5:
            raise StopExecution("mutation-time app0 freshness check failed")
        if str(esp.flash_md5sum(OTADATA_OFFSET, OTADATA_SIZE)).lower() != expected_otadata_md5:
            raise StopExecution("mutation-time otadata freshness check failed")
        if str(esp.flash_md5sum(APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE)).lower() != expected_app1_md5:
            raise StopExecution("mutation-time app1 freshness check failed")

        write_json(root / "direct_rom_mutation_preclaim.json", {
            "identity_binding": "PASS",
            "app0_same_connection_md5_freshness": "PASS",
            "otadata_same_connection_md5_freshness": "PASS",
            "app1_same_connection_md5_freshness": "PASS",
            "mutation_started": False,
            "utc": utc_now(),
        })

        expected_blocks = (len(data) + flash_write_size - 1) // flash_write_size
        write_json(root / "direct_rom_mutation_boundary_entered.json", {
            "phase": "FLASH_BEGIN_ENTERING",
            "persistent_app0_state_may_change_after_this_point": True,
            "target_offset": hex(APP0_OFFSET),
            "firmware_size": len(data),
            "expected_blocks": expected_blocks,
            "utc": utc_now(),
        })
        blocks = esp.flash_begin(len(data), APP0_OFFSET)
        if blocks != expected_blocks:
            raise StopExecution(
                f"direct ROM flash_begin block count mismatch: got {blocks}, expected {expected_blocks}"
            )
        write_mutation_progress(
            root, phase="FLASH_BEGIN_COMPLETED", expected_blocks=expected_blocks,
            last_completed_seq=-1, next_seq=0,
        )

        for seq in range(expected_blocks):
            start = seq * flash_write_size
            block = data[start: start + flash_write_size]
            if len(block) < flash_write_size:
                block = block + b"\xff" * (flash_write_size - len(block))
            write_mutation_progress(
                root, phase="FLASH_BLOCK_ENTERING", expected_blocks=expected_blocks,
                last_completed_seq=seq - 1, next_seq=seq,
            )
            esp.flash_block(block, seq)
            write_mutation_progress(
                root, phase="FLASH_BLOCK_COMPLETED", expected_blocks=expected_blocks,
                last_completed_seq=seq, next_seq=(seq + 1 if seq + 1 < expected_blocks else None),
            )

        observed_post_md5 = str(
            esp.flash_md5sum(APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE)
        ).lower()
        if observed_post_md5 != expected_firmware_md5:
            raise StopExecution("same-connection app0 postwrite MD5 verification failed")
        write_json(root / "direct_rom_mutation_completion.json", {
            "phase": "ALL_FLASH_BLOCKS_COMPLETED_AND_MD5_VERIFIED",
            "blocks_completed": expected_blocks,
            "firmware_md5": expected_firmware_md5,
            "flash_finish_used": False,
            "whole_image_retry": False,
            "utc": utc_now(),
        })


def evidence_manifest(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence_manifest.json":
            files.append({
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return files


def write_closure(
    root: Path, *, execution_id: str, package_commit: str, authorization_id: str,
    result: str, failed: str | None, stop_reason: str | None,
    target_access: bool | str, prestate: dict[str, Any] | None,
    poststate: dict[str, Any] | None, next_route: str,
) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    mutation_boundary_entered = (root / "direct_rom_mutation_boundary_entered.json").is_file()
    mutation_completed = (root / "direct_rom_mutation_completion.json").is_file()
    write_json(root / "closure.json", {
        "execution_id": execution_id,
        "execution_package_commit": package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False,
        "deployment_result": result,
        "first_failed_operation": failed,
        "stop_reason": stop_reason,
        "target_access_occurred": target_access,
        "mutation_boundary_entered": mutation_boundary_entered,
        "mutation_completed_and_same_connection_md5_verified": mutation_completed,
        "stock_high_level_write_flash_used": False,
        "whole_image_mutation_retry": False,
        "automatic_rollback": False,
        "flash_finish_used": False,
        "ota_slot_switch_executed": False,
        "prestate": prestate,
        "poststate": poststate,
        "next_route": next_route,
    })
    write_json(root / "evidence_manifest.json", {
        "schema_version": 1,
        "execution_id": execution_id,
        "authorization": authorization_id,
        "files": evidence_manifest(root),
    })


def self_check(package_dir: Path) -> None:
    load_manifest(package_dir)
    assert_read_only_argv(build_read_mac_command("/dev/example"))
    for offset, size in (
        (PARTITION_TABLE_OFFSET, PARTITION_TABLE_SIZE),
        (OTADATA_OFFSET, OTADATA_SIZE),
        (APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        (APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
    ):
        assert_read_only_argv(build_read_flash_command("/dev/example", offset, size, Path("/tmp/out.bin")))
    source = Path(__file__).read_text(encoding="utf-8")
    if "cmds.write_flash" in source:
        raise StopExecution("stock high-level esptool write_flash must not be used")
    if ".flash_finish(" in source:
        raise StopExecution("flash_finish must not be used in ID18 ROM mutation")
    if SCHEMA5_FIRMWARE_SIZE > APP0_PARTITION_SIZE:
        raise StopExecution("Schema-v5 image does not fit app0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--board-a-port")
    parser.add_argument("--firmware-bin", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    package_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(package_dir)
    if args.self_check:
        self_check(package_dir)
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0

    required = (
        args.expected_package_commit, args.authorization_id, args.execution_id,
        args.board_a_port, args.firmware_bin, args.evidence_root,
    )
    if any(value is None or value == "" for value in required):
        parser.error("all execution arguments are required")
    if sys.version_info[:2] != (3, 11):
        raise StopExecution("Python 3.11 is required")

    root = args.evidence_root.expanduser().resolve()
    firmware = args.firmware_bin.expanduser().resolve()
    if is_within(root, repo_root):
        raise StopExecution("private evidence root must be outside repository")
    if root.exists() and any(root.iterdir()):
        raise StopExecution("evidence root must be absent or empty")
    ensure_private_dir(root)
    cfg = make_esptool_cfg(root)
    write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    target_access: bool | str = False
    failed = "HOST_PREFLIGHT"
    prestate: dict[str, Any] | None = None
    poststate: dict[str, Any] | None = None
    next_route = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"

    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit, firmware)
        verify_port_locator(root, args.board_a_port)
        write_authorization(root, args.authorization_id, args.execution_id, claimed=True)
        env = {"ESPTOOL_CFGFILE": str(cfg), "ESPTOOL_OPEN_PORT_ATTEMPTS": "1"}

        failed = "BOARD_A_READ_MAC"
        target_access = "UNKNOWN"
        identity = run_recorded(
            root=root, index=op_index, label="board_a_read_mac",
            argv=build_read_mac_command(args.board_a_port), cwd=repo_root,
            target_operation=True, extra_env=env,
        )
        op_index += 1
        if identity.returncode != 0:
            raise StopExecution("board_a read-mac failed")
        target_access = True
        base_mac = parse_base_mac(identity.stdout or "")
        if mac_suffix(base_mac) != EXPECTED_BOARD_A_SUFFIX:
            raise StopExecution("board_a identity suffix mismatch")

        board_dir = root / "board_a"
        ensure_private_dir(board_dir)
        write_json(board_dir / "identity_private.json", {
            "base_mac": base_mac,
            "base_mac_sha256": hashlib.sha256(base_mac.encode()).hexdigest(),
            "observed_suffix": mac_suffix(base_mac),
            "identity_match": True,
        })

        captures = (
            ("pre_partition_table", PARTITION_TABLE_OFFSET, PARTITION_TABLE_SIZE),
            ("pre_otadata", OTADATA_OFFSET, OTADATA_SIZE),
            ("pre_app0_window", APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
            ("pre_app1_window", APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        )
        paths: dict[str, Path] = {}
        for label, offset, size in captures:
            failed = f"BOARD_A_{label.upper()}_READ"
            out = board_dir / f"{label}.bin"
            paths[label] = out
            result = run_recorded(
                root=root, index=op_index, label=f"board_a_read_{label}",
                argv=build_read_flash_command(args.board_a_port, offset, size, out),
                cwd=repo_root, target_operation=True, extra_env=env,
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"board_a {label} read failed")
            if not out.is_file() or out.stat().st_size != size:
                raise StopExecution(f"board_a {label} output size/path mismatch")
            os.chmod(out, 0o600)

        failed = "HOST_PREMUTATION_ADJUDICATION"
        parse_partition_table(paths["pre_partition_table"].read_bytes())
        pre_otadata_raw = paths["pre_otadata"].read_bytes()
        ota = parse_otadata(pre_otadata_raw)
        verify_expected_prestate(ota)
        app0_pre_sha = sha256_file(paths["pre_app0_window"])
        app1_pre_sha = sha256_file(paths["pre_app1_window"])
        prestate = {
            "selected_slot": ota.selected_slot,
            "inactive_slot": 1 - ota.selected_slot,
            "active_seq": ota.active_seq,
            "active_state": ota.active_state,
            "app0_window_sha256": app0_pre_sha,
            "app1_window_sha256": app1_pre_sha,
            "app0_exact_schema5": app0_pre_sha == SCHEMA5_FIRMWARE_SHA256,
            "app1_exact_schema5": app1_pre_sha == SCHEMA5_FIRMWARE_SHA256,
        }
        write_json(board_dir / "prestate_summary.json", prestate)

        if prestate["app0_exact_schema5"]:
            next_route = "PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE"
            write_closure(
                root, execution_id=args.execution_id,
                package_commit=args.expected_package_commit,
                authorization_id=args.authorization_id, result="PASS_NO_MUTATION_NEEDED",
                failed=None, stop_reason=None, target_access=target_access,
                prestate=prestate, poststate=prestate, next_route=next_route,
            )
            closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
            print(json.dumps(closure, sort_keys=True))
            return 0

        failed = "BOARD_A_DIRECT_ROM_APP0_SCHEMA5_WRITE"
        runtime = bind_direct_rom_runtime(cfg, root)
        direct_write_app0_once(
            runtime=runtime, root=root, port=args.board_a_port,
            expected_base_mac=base_mac, firmware=firmware,
            pre_app0=paths["pre_app0_window"], pre_otadata=pre_otadata_raw,
            pre_app1=paths["pre_app1_window"],
        )

        post_paths: dict[str, Path] = {}
        for label, offset, size in (
            ("post_app0_window", APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
            ("post_otadata", OTADATA_OFFSET, OTADATA_SIZE),
            ("post_app1_window", APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        ):
            failed = f"BOARD_A_{label.upper()}_READ"
            out = board_dir / f"{label}.bin"
            post_paths[label] = out
            result = run_recorded(
                root=root, index=op_index, label=f"board_a_read_{label}",
                argv=build_read_flash_command(args.board_a_port, offset, size, out),
                cwd=repo_root, target_operation=True, extra_env=env,
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"board_a {label} read failed")
            if not out.is_file() or out.stat().st_size != size:
                raise StopExecution(f"board_a {label} output size/path mismatch")
            os.chmod(out, 0o600)

        failed = "HOST_POSTMUTATION_VERIFICATION"
        app0_post_sha = sha256_file(post_paths["post_app0_window"])
        app1_post_sha = sha256_file(post_paths["post_app1_window"])
        post_otadata_raw = post_paths["post_otadata"].read_bytes()
        post_ota = parse_otadata(post_otadata_raw)
        verify_expected_prestate(post_ota)
        poststate = {
            "selected_slot": post_ota.selected_slot,
            "inactive_slot": 1 - post_ota.selected_slot,
            "active_seq": post_ota.active_seq,
            "active_state": post_ota.active_state,
            "app0_window_sha256": app0_post_sha,
            "app1_window_sha256": app1_post_sha,
            "app0_exact_schema5": app0_post_sha == SCHEMA5_FIRMWARE_SHA256,
            "otadata_byte_identical": post_otadata_raw == pre_otadata_raw,
            "app1_window_hash_identical": app1_post_sha == app1_pre_sha,
        }
        write_json(board_dir / "poststate_summary.json", poststate)
        if not poststate["app0_exact_schema5"]:
            raise StopExecution("app0 exact Schema-v5 readback verification failed")
        if not poststate["otadata_byte_identical"]:
            raise StopExecution("otadata changed during app0-only deployment")
        if not poststate["app1_window_hash_identical"]:
            raise StopExecution("app1 rollback payload window changed during app0-only deployment")

        next_route = "PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE"
        write_closure(
            root, execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id, result="PASS",
            failed=None, stop_reason=None, target_access=target_access,
            prestate=prestate, poststate=poststate, next_route=next_route,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root, execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id, result="STOP",
            failed=failed, stop_reason=str(exc), target_access=target_access,
            prestate=prestate, poststate=poststate,
            next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["deployment_result"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
