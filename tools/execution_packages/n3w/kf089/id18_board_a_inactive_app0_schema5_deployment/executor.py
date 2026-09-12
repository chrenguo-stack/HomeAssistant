#!/usr/bin/env python3
"""KF-089 ID18 Board A inactive-app0 Schema-v5 deployment.

One bounded mutation is permitted: write the exact frozen Schema-v5 firmware to
inactive app0 only. OTA selection remains on app1. No application boot occurs.
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
MUTATION_FORBIDDEN = {
    "erase-flash", "erase-region", "write-mem", "write-flash-status",
    "erase_flash", "erase_region", "write_mem", "write_flash_status",
    "switch_ota_partition", "erase_ota_partition",
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


def build_app0_write_command(port: str, firmware: Path) -> list[str]:
    argv = [
        *esptool_base(port),
        "write-flash", "--flash-size", "8MB",
        hex(APP0_OFFSET), str(firmware),
    ]
    lowered = {str(item).strip().lower() for item in argv}
    forbidden = sorted(lowered & MUTATION_FORBIDDEN)
    if forbidden:
        raise StopExecution(f"forbidden mutation token present: {forbidden}")
    if argv.count("write-flash") != 1:
        raise StopExecution("mutation command must contain exactly one write-flash")
    if hex(APP0_OFFSET) not in argv:
        raise StopExecution("mutation command is not bound to app0 offset")
    if hex(OTADATA_OFFSET) in argv or hex(APP1_OFFSET) in argv:
        raise StopExecution("mutation command references forbidden partition offset")
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
    entries = tuple(
        parse_ota_entry(raw[rel: rel + OTA_ENTRY_SIZE], index)
        for index, rel in enumerate(OTA_COPY_RELATIVE_OFFSETS)
    )
    valid = [entry for entry in entries if entry.boot_valid]
    if not valid:
        raise StopExecution("no valid OTA-select copy")
    if len(valid) == 2 and valid[0].seq == valid[1].seq:
        raise StopExecution("ambiguous OTA-select state: equal valid ota_seq")
    active = max(valid, key=lambda item: item.seq)
    slot = active.slot
    if slot not in (0, 1):
        raise StopExecution("selected OTA slot is invalid")
    return OtaSnapshot((entries[0], entries[1]), active.index, slot, active.ota_state, active.seq)


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
    target_operation: bool = False, mutation_operation: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if not mutation_operation:
        assert_read_only_argv(argv)
    op_dir = root / f"op_{index:02d}_{label}"
    ensure_private_dir(op_dir)
    write_json(op_dir / "command.json", {
        "argv": argv,
        "cwd": str(cwd),
        "label": label,
        "operation_index": index,
        "target_operation": target_operation,
        "mutation_operation": mutation_operation,
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
            "mutation_may_have_started": False,
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
        "mutation_may_have_started": bool(mutation_operation),
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
    target_access: bool | str, mutation_started: bool,
    prestate: dict[str, Any] | None, poststate: dict[str, Any] | None,
    next_route: str,
) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
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
        "mutation_command_started": mutation_started,
        "automatic_mutation_retry": False,
        "automatic_rollback": False,
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


def capture_failure_state(
    *, root: Path, repo_root: Path, port: str, cfg: Path, op_index: int,
) -> None:
    board_dir = root / "board_a"
    ensure_private_dir(board_dir)
    env = {"ESPTOOL_CFGFILE": str(cfg), "ESPTOOL_OPEN_PORT_ATTEMPTS": "1"}
    for label, offset, size in (
        ("failure_otadata", OTADATA_OFFSET, OTADATA_SIZE),
        ("failure_app0_window", APP0_OFFSET, SCHEMA5_FIRMWARE_SIZE),
    ):
        out = board_dir / f"{label}.bin"
        try:
            run_recorded(
                root=root, index=op_index, label=label,
                argv=build_read_flash_command(port, offset, size, out),
                cwd=repo_root, target_operation=True, extra_env=env,
            )
        except Exception:
            pass
        op_index += 1


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
    mutation = build_app0_write_command("/dev/example", Path("/tmp/firmware.bin"))
    if mutation.count("write-flash") != 1 or hex(APP0_OFFSET) not in mutation:
        raise StopExecution("app0 mutation self-check failed")
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
    mutation_started = False
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
                mutation_started=False, prestate=prestate, poststate=prestate,
                next_route=next_route,
            )
            closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
            print(json.dumps(closure, sort_keys=True))
            return 0

        failed = "BOARD_A_APP0_SCHEMA5_WRITE"
        mutation_started = True
        write_result = run_recorded(
            root=root, index=op_index, label="board_a_write_app0_schema5",
            argv=build_app0_write_command(args.board_a_port, firmware),
            cwd=repo_root, target_operation=True, mutation_operation=True,
            extra_env=env,
        )
        op_index += 1
        if write_result.returncode != 0:
            capture_failure_state(
                root=root, repo_root=repo_root, port=args.board_a_port,
                cfg=cfg, op_index=op_index,
            )
            raise StopExecution("board_a app0 Schema-v5 write failed; app0 persistent state uncertain")

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
            mutation_started=mutation_started, prestate=prestate,
            poststate=poststate, next_route=next_route,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root, execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id, result="STOP",
            failed=failed, stop_reason=str(exc), target_access=target_access,
            mutation_started=mutation_started, prestate=prestate,
            poststate=poststate, next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["deployment_result"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
