#!/usr/bin/env python3
"""KF-089 ID17 Board A dual-slot read-only preclaim.

This executor performs no writes. It reads Board A silicon identity plus the
partition-table, otadata, and both OTA application-slot payload windows needed
to classify the smallest later Schema-v5 mutation.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
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
from typing import Any, Iterable

PACKAGE_SCHEMA_VERSION = 1
EXPECTED_ESPTOOL_VERSION = "5.3.1"
EXPECTED_BOARD_A_SUFFIX = "f3:50"

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
OTA_STATE_VALID = 0x2
OTA_STATE_INVALID = 0x3
OTA_STATE_ABORTED = 0x4
OTA_STATE_UNDEFINED = UINT32_MAX
SAFE_ACTIVE_STATES = {OTA_STATE_VALID, OTA_STATE_UNDEFINED}

BASE_MAC_RE = re.compile(
    r"(?im)^\s*BASE MAC:\s*([0-9a-f]{2}(?::[0-9a-f]{2}){5})\s*$"
)
VERSION_RE = re.compile(r"(?i)\bv?(\d+\.\d+\.\d+)\b")
WRITE_LIKE_TOKENS = {
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
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
    if value.get("gate_id") != "id17_board_a_slot_state_readonly":
        raise StopExecution("manifest gate id mismatch")
    return value


def assert_read_only_argv(argv: Iterable[str]) -> None:
    lowered = {str(item).strip().lower() for item in argv}
    forbidden = sorted(lowered & WRITE_LIKE_TOKENS)
    if forbidden:
        raise StopExecution(f"write-like esptool token forbidden: {forbidden}")


def esptool_base(port: str) -> list[str]:
    return [
        sys.executable, "-m", "esptool",
        "--chip", "esp32c6",
        "--port", port,
        "--before", "no-reset",
        "--after", "no-reset",
        "--no-stub",
    ]


def build_read_mac_command(port: str) -> list[str]:
    argv = [*esptool_base(port), "read-mac"]
    assert_read_only_argv(argv)
    return argv


def build_read_flash_command(port: str, offset: int, size: int, output: Path) -> list[str]:
    argv = [
        *esptool_base(port),
        "read-flash",
        "--flash-size", "8MB",
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
    parsed = [
        parse_ota_entry(raw[rel: rel + OTA_ENTRY_SIZE], index)
        for index, rel in enumerate(OTA_COPY_RELATIVE_OFFSETS)
    ]
    entries = (parsed[0], parsed[1])
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


def verify_host(root: Path, repo_root: Path, expected_commit: str, op_index: int) -> int:
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
    )
    for label, argv, expected in checks:
        result = run_recorded(root=root, index=op_index, label=label, argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        op_index += 1

    result = run_recorded(
        root=root,
        index=op_index,
        label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"],
        cwd=repo_root,
    )
    versions = VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    return op_index + 1


def verify_port_locator(root: Path, port: str) -> None:
    path = Path(port)
    info = path.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise StopExecution("Board A port locator is not a character device")
    write_json(root / "host_port_locator_preflight.json", {
        "serial_open": False,
        "usb_device_open": False,
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


def classify(*, ota: OtaSnapshot, app0_sha: str, app1_sha: str) -> dict[str, Any]:
    selected = ota.selected_slot
    inactive = 1 - selected
    slot_hashes = {0: app0_sha, 1: app1_sha}
    schema5_slots = [
        slot for slot, digest in slot_hashes.items()
        if digest == SCHEMA5_FIRMWARE_SHA256
    ]
    active_exact = selected in schema5_slots
    inactive_exact = inactive in schema5_slots

    if active_exact:
        route = "HOST_ADJUDICATE_ACTIVE_SCHEMA5_SELECTION_VS_SCHEMA3_RUNTIME_HISTORY"
    elif inactive_exact:
        route = "PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE"
    else:
        route = "PREPARE_BOARD_A_INACTIVE_SLOT_SCHEMA5_DEPLOYMENT_PACKAGE"

    return {
        "selected_slot": selected,
        "inactive_slot": inactive,
        "active_ota_seq": ota.active_seq,
        "active_ota_state": ota.active_state,
        "active_state_safe_for_future_mutation": ota.active_state in SAFE_ACTIVE_STATES,
        "schema5_exact_slots": schema5_slots,
        "active_slot_exact_schema5": active_exact,
        "inactive_slot_exact_schema5": inactive_exact,
        "next_route": route,
    }


def write_closure(
    root: Path, *, execution_id: str, package_commit: str,
    authorization_id: str, result: str, failed: str | None,
    stop_reason: str | None, target_access: bool | str,
    slot_state: dict[str, Any] | None,
) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    write_json(root / "closure.json", {
        "execution_id": execution_id,
        "execution_package_commit": package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False,
        "read_only_preclaim_result": result,
        "first_failed_operation": failed,
        "stop_reason": stop_reason,
        "target_access_occurred": target_access,
        "slot_state": slot_state,
        "next_route": (
            slot_state["next_route"]
            if result == "PASS" and slot_state is not None
            else "STOP_RETURN_TO_HIGH_LEVEL_MODEL"
        ),
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
        assert_read_only_argv(
            build_read_flash_command("/dev/example", offset, size, Path("/tmp/out.bin"))
        )
    if APP0_OFFSET + APP0_PARTITION_SIZE != APP1_OFFSET:
        raise StopExecution("app slot geometry is not contiguous as expected")
    if SCHEMA5_FIRMWARE_SIZE > min(APP0_PARTITION_SIZE, APP1_PARTITION_SIZE):
        raise StopExecution("Schema-v5 firmware does not fit OTA slots")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--board-a-port")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    package_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(package_dir)
    if args.self_check:
        self_check(package_dir)
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0

    required = (
        args.expected_package_commit,
        args.authorization_id,
        args.execution_id,
        args.board_a_port,
        args.evidence_root,
    )
    if any(value is None or value == "" for value in required):
        parser.error("all execution arguments are required")
    if sys.version_info[:2] != (3, 11):
        raise StopExecution("Python 3.11 is required")

    root = args.evidence_root.expanduser().resolve()
    if is_within(root, repo_root):
        raise StopExecution("private evidence root must be outside repository")
    if root.exists() and any(root.iterdir()):
        raise StopExecution("evidence root must be absent or empty")
    ensure_private_dir(root)
    write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    target_access: bool | str = False
    failed = "HOST_PREFLIGHT"
    slot_state: dict[str, Any] | None = None

    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit, op_index)
        verify_port_locator(root, args.board_a_port)
        write_authorization(root, args.authorization_id, args.execution_id, claimed=True)

        failed = "BOARD_A_READ_MAC"
        target_access = "UNKNOWN"
        identity = run_recorded(
            root=root,
            index=op_index,
            label="board_a_read_mac",
            argv=build_read_mac_command(args.board_a_port),
            cwd=repo_root,
            target_operation=True,
            extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"},
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
            ("partition_table", PARTITION_TABLE_OFFSET, PARTITION_TABLE_SIZE),
            ("otadata", OTADATA_OFFSET, OTADATA_SIZE),
            ("app0_schema5_payload_window", APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
            ("app1_schema5_payload_window", APP1_OFFSET, SCHEMA5_FIRMWARE_SIZE),
        )
        paths: dict[str, Path] = {}
        for label, offset, size in captures:
            failed = f"BOARD_A_{label.upper()}_READ"
            path = board_dir / f"{label}.bin"
            paths[label] = path
            result = run_recorded(
                root=root,
                index=op_index,
                label=f"board_a_read_{label}",
                argv=build_read_flash_command(args.board_a_port, offset, size, path),
                cwd=repo_root,
                target_operation=True,
                extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"},
            )
            op_index += 1
            if result.returncode != 0:
                raise StopExecution(f"board_a {label} read failed")
            if not path.is_file() or path.stat().st_size != size:
                raise StopExecution(f"board_a {label} output size/path mismatch")
            os.chmod(path, 0o600)

        failed = "HOST_SLOT_STATE_PARSE"
        partitions = parse_partition_table(paths["partition_table"].read_bytes())
        ota = parse_otadata(paths["otadata"].read_bytes())
        app0_sha = sha256_file(paths["app0_schema5_payload_window"])
        app1_sha = sha256_file(paths["app1_schema5_payload_window"])
        slot_state = classify(ota=ota, app0_sha=app0_sha, app1_sha=app1_sha)

        write_json(board_dir / "partition_contract.json", {
            label: {
                "type": entry.type,
                "subtype": entry.subtype,
                "offset": hex(entry.offset),
                "size": hex(entry.size),
                "flags": entry.flags,
            }
            for label, entry in sorted(partitions.items())
            if label in {"otadata", "app0", "app1"}
        })
        write_json(board_dir / "otadata_summary.json", {
            "selected_slot": ota.selected_slot,
            "active_index": ota.active_index,
            "active_seq": ota.active_seq,
            "active_state": ota.active_state,
            "entries": [
                {
                    "index": entry.index,
                    "seq": entry.seq,
                    "ota_state": entry.ota_state,
                    "crc_valid": entry.crc_valid,
                    "boot_valid": entry.boot_valid,
                    "slot": entry.slot,
                    "erased": entry.erased,
                }
                for entry in ota.entries
            ],
        })
        write_json(board_dir / "slot_hashes.json", {
            "schema5_source_commit": SCHEMA5_SOURCE_COMMIT,
            "schema5_expected_size": SCHEMA5_FIRMWARE_SIZE,
            "schema5_expected_sha256": SCHEMA5_FIRMWARE_SHA256,
            "app0_window_sha256": app0_sha,
            "app1_window_sha256": app1_sha,
            **slot_state,
        })

        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="PASS",
            failed=None,
            stop_reason=None,
            target_access=target_access,
            slot_state=slot_state,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="STOP",
            failed=failed,
            stop_reason=str(exc),
            target_access=target_access,
            slot_state=slot_state,
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["read_only_preclaim_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
