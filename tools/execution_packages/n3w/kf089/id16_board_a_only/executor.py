#!/usr/bin/env python3
"""KF-089 ID16: reuse frozen ID15 Board B evidence and read only Board A.

The executor is fail-closed. Host-only validation of the saved Board B NVS image
happens before the physical authorization claim. After claim, only Board A may
be accessed: one read-mac, one read-only NVS read, then offline Schema-v5 decode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PACKAGE_SCHEMA_VERSION = 1
EXPECTED_ESPTOOL_VERSION = "5.3.1"
EXPECTED_SCHEMA_VERSION = 5
NVS_OFFSET = 0x790000
NVS_SIZE = 0x70000
FLASH_SIZE = "8MB"
DIAG_PARSER_RELATIVE = Path("tools/n3w_read_diag_snapshot.py")
EXPECTED_DIAG_PARSER_BLOB = "af78ed4cb14c38579f56e6ba3019e2debdb21d9e"
EXPECTED_BOARD_A_SUFFIX = "f3:50"
EXPECTED_BOARD_B_NVS_SHA256 = "dce0587cd47676de068c3e23b77cb8df05b11d6acf55799583f54e2d2340b422"

BOARD_B_REQUIRED_FIELDS = (
    "schema_version", "boot_session", "snapshot_uptime_ms", "path_state",
    "relay_active_count", "relay_telemetry_attempts", "relay_telemetry_success",
    "unicast_completion_count", "unicast_completion_success", "unicast_completion_failure",
)
BOARD_A_REQUIRED_FIELDS = (
    "schema_version", "boot_session", "snapshot_uptime_ms", "path_state",
    "compact_rx_count", "compact_state_reject_count", "compact_child_binding_failure",
    "compact_decode_success", "compact_decode_failure", "compact_wrap_failure",
    "compact_forward_attempts", "compact_forward_submit_success",
    "compact_forward_submit_failure",
)
BASE_MAC_RE = re.compile(r"(?im)^\s*BASE MAC:\s*([0-9a-f]{2}(?::[0-9a-f]{2}){5})\s*$")
VERSION_RE = re.compile(r"(?i)\bv?(\d+\.\d+\.\d+)\b")
WRITE_LIKE_TOKENS = {
    "write-flash", "erase-flash", "erase-region", "write-mem", "write-flash-status",
    "write_flash", "erase_flash", "erase_region", "write_mem", "write_flash_status",
}


class StopExecution(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

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
        if (candidate / "AGENTS.md").is_file() and (candidate / DIAG_PARSER_RELATIVE).is_file():
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
    if value.get("gate_id") != "id16_board_a_only":
        raise StopExecution("manifest gate id mismatch")
    return value

def assert_read_only_argv(argv: Iterable[str]) -> None:
    lowered = {str(item).strip().lower() for item in argv}
    forbidden = sorted(lowered & WRITE_LIKE_TOKENS)
    if forbidden:
        raise StopExecution(f"write-like esptool token forbidden: {forbidden}")

def esptool_base(port: str) -> list[str]:
    return [sys.executable, "-m", "esptool", "--chip", "esp32c6", "--port", port,
            "--before", "no-reset", "--after", "no-reset", "--no-stub"]

def build_read_mac_command(port: str) -> list[str]:
    argv = [*esptool_base(port), "read-mac"]
    assert_read_only_argv(argv)
    return argv

def build_read_nvs_command(port: str, output_path: Path) -> list[str]:
    argv = [*esptool_base(port), "read-flash", "--flash-size", FLASH_SIZE,
            hex(NVS_OFFSET), hex(NVS_SIZE), str(output_path)]
    assert_read_only_argv(argv)
    return argv

def build_decode_command(repo_root: Path, nvs_path: Path) -> list[str]:
    return [sys.executable, str(repo_root / DIAG_PARSER_RELATIVE), "--nvs-image", str(nvs_path)]

def parse_base_mac(stdout: str) -> str:
    matches = sorted(set(m.lower() for m in BASE_MAC_RE.findall(stdout)))
    if len(matches) != 1:
        raise StopExecution("expected exactly one complete BASE MAC line")
    return matches[0]

def mac_suffix(mac: str) -> str:
    parts = mac.split(":")
    if len(parts) != 6:
        raise StopExecution("normalized BASE MAC is invalid")
    return ":".join(parts[-2:]).lower()

def validate_snapshot(snapshot: dict[str, Any], fields: tuple[str, ...], board: str) -> dict[str, Any]:
    if snapshot.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise StopExecution(f"{board} diagnostic schema mismatch: {snapshot.get('schema_version')!r}")
    missing = [field for field in fields if field not in snapshot]
    if missing:
        raise StopExecution(f"{board} snapshot missing fields: {missing}")
    return {field: snapshot[field] for field in fields}

def run_recorded(*, evidence_root: Path, index: int, label: str, argv: list[str],
                 cwd: Path, target_operation: bool = False,
                 extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    assert_read_only_argv(argv)
    op_dir = evidence_root / f"op_{index:02d}_{label}"
    ensure_private_dir(op_dir)
    write_json(op_dir / "command.json", {
        "argv": argv, "cwd": str(cwd), "label": label, "operation_index": index,
        "target_operation": target_operation, "utc_start": utc_now(),
        "environment_overrides": dict(sorted((extra_env or {}).items())),
    })
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                   text=True, check=False)
    except OSError as exc:
        write_text(op_dir / "stdout.txt", "")
        write_text(op_dir / "stderr.txt", f"{type(exc).__name__}: {exc}\n")
        write_json(op_dir / "result.json", {
            "command_started": False, "returncode": None,
            "target_access_occurred": False if target_operation else None,
            "utc_end": utc_now(),
        })
        raise StopExecution(f"{label} process launch failed") from exc
    write_text(op_dir / "stdout.txt", completed.stdout or "")
    write_text(op_dir / "stderr.txt", completed.stderr or "")
    write_json(op_dir / "result.json", {
        "command_started": True, "returncode": completed.returncode,
        "target_access_occurred": (True if target_operation and completed.returncode == 0
                                   else "UNKNOWN" if target_operation else None),
        "utc_end": utc_now(),
    })
    return completed

def verify_git_and_tools(evidence_root: Path, repo_root: Path,
                         expected_package_commit: str, op_index: int) -> int:
    for label, argv, expected in (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_package_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
        ("host_diag_parser_blob", ["git", "hash-object", str(DIAG_PARSER_RELATIVE)], EXPECTED_DIAG_PARSER_BLOB),
    ):
        result = run_recorded(evidence_root=evidence_root, index=op_index, label=label,
                              argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        op_index += 1
    result = run_recorded(evidence_root=evidence_root, index=op_index,
                          label="host_esptool_version",
                          argv=[sys.executable, "-m", "esptool", "version"], cwd=repo_root)
    versions = VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    return op_index + 1

def verify_board_a_locator(evidence_root: Path, port: str) -> None:
    path = Path(port)
    info = path.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise StopExecution("Board A port locator is not a character device")
    write_json(evidence_root / "host_port_locator_preflight.json", {
        "serial_open": False, "usb_device_open": False,
        "board_a_locator": str(path), "resolved_locator": os.path.realpath(str(path)),
        "character_device": True, "checked_at": utc_now(),
    })
def initial_authorization(root: Path, auth: str, execution_id: str) -> None:
    write_json(root / "authorization.json", {"authorization_id": auth,
        "execution_id": execution_id, "claimed": False, "consumed": False,
        "replay_permitted": False})
def claim_authorization(root: Path, auth: str, execution_id: str) -> None:
    now = utc_now()
    write_json(root / "authorization.json", {"authorization_id": auth,
        "execution_id": execution_id, "claimed": True, "consumed": True,
        "replay_permitted": False,
        "claim_boundary": "immediately_before_board_a_read_mac",
        "claimed_at": now, "consumed_at": now})
def evidence_manifest(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence_manifest.json":
            items.append({"path": path.relative_to(root).as_posix(),
                          "size": path.stat().st_size, "sha256": sha256_file(path)})
    return items

def write_closure(root: Path, *, execution_id: str, package_commit: str,
                  authorization_id: str, result: str, failed: str | None,
                  stop_reason: str | None, target_access: bool,
                  board_b: dict[str, Any] | None, board_a: dict[str, Any] | None) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    write_json(root / "closure.json", {
        "execution_id": execution_id, "execution_package_commit": package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False, "read_only_recovery_result": result,
        "raw_evidence_complete": result == "PASS", "first_failed_operation": failed,
        "target_access_occurred": target_access,
        "board_b_selected_counters": board_b, "board_a_selected_counters": board_a,
        "next_route": ("HIGH_LEVEL_MODEL_SCHEMA_V5_COUNTER_ADJUDICATION" if result == "PASS"
                       else "STOP_RETURN_TO_HIGH_LEVEL_MODEL"),
        "stop_reason": stop_reason,
    })
    write_json(root / "evidence_manifest.json", {"schema_version": 1,
        "execution_id": execution_id, "authorization": authorization_id,
        "files": evidence_manifest(root)})

def decode_nvs(*, root: Path, repo_root: Path, nvs_path: Path, op_index: int,
               label: str, fields: tuple[str, ...], board: str) -> tuple[int, dict[str, Any]]:
    result = run_recorded(evidence_root=root, index=op_index, label=label,
                          argv=build_decode_command(repo_root, nvs_path), cwd=repo_root)
    if result.returncode != 0:
        raise StopExecution(f"{board} Schema-v5 decode failed")
    try:
        snapshot = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise StopExecution(f"{board} decoded snapshot is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        raise StopExecution(f"{board} decoded snapshot must be an object")
    return op_index + 1, validate_snapshot(snapshot, fields, board)

def self_check(package_dir: Path, repo_root: Path) -> None:
    load_manifest(package_dir)
    parser_blob = subprocess.run(["git", "hash-object", str(DIAG_PARSER_RELATIVE)],
                                 cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
    if parser_blob != EXPECTED_DIAG_PARSER_BLOB:
        raise StopExecution("diagnostic parser blob binding mismatch")
    assert_read_only_argv(build_read_mac_command("/dev/example"))
    assert_read_only_argv(build_read_nvs_command("/dev/example", Path("/tmp/nvs.bin")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--board-a-port")
    parser.add_argument("--board-b-nvs-evidence", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    package_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(package_dir)
    if args.self_check:
        self_check(package_dir, repo_root)
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0
    required = (args.expected_package_commit, args.authorization_id, args.execution_id,
                args.board_a_port, args.board_b_nvs_evidence, args.evidence_root)
    if any(value is None or value == "" for value in required):
        parser.error("all execution arguments are required")
    if sys.version_info[:2] != (3, 11):
        raise StopExecution("Python 3.11 is required")
    evidence_root = args.evidence_root.expanduser().resolve()
    board_b_nvs = args.board_b_nvs_evidence.expanduser().resolve()
    if is_within(evidence_root, repo_root) or is_within(board_b_nvs, repo_root):
        raise StopExecution("private evidence paths must be outside repository")
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise StopExecution("evidence root must be absent or empty")
    if not board_b_nvs.is_file() or board_b_nvs.stat().st_size != NVS_SIZE:
        raise StopExecution("ID15 Board B NVS evidence size/path mismatch")
    if sha256_file(board_b_nvs) != EXPECTED_BOARD_B_NVS_SHA256:
        raise StopExecution("ID15 Board B NVS evidence SHA256 mismatch")
    ensure_private_dir(evidence_root)
    initial_authorization(evidence_root, args.authorization_id, args.execution_id)
    op_index = 1
    board_b = None
    board_a = None
    target_access = False
    failed = "HOST_PREFLIGHT"
    try:
        op_index = verify_git_and_tools(evidence_root, repo_root,
                                        args.expected_package_commit, op_index)
        verify_board_a_locator(evidence_root, args.board_a_port)
        write_json(evidence_root / "board_b_source_evidence.json", {
            "source_execution": "N3W_KF089_ID15_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_15",
            "nvs_size": NVS_SIZE, "nvs_sha256": EXPECTED_BOARD_B_NVS_SHA256,
            "board_access": False,
        })
        failed = "BOARD_B_EXISTING_EVIDENCE_DECODE"
        op_index, board_b = decode_nvs(root=evidence_root, repo_root=repo_root,
            nvs_path=board_b_nvs, op_index=op_index, label="board_b_existing_nvs_decode",
            fields=BOARD_B_REQUIRED_FIELDS, board="board_b")
        write_json(evidence_root / "board_b_selected_counters.json", board_b)
        claim_authorization(evidence_root, args.authorization_id, args.execution_id)
        failed = "BOARD_A_READ_MAC"
        identity = run_recorded(evidence_root=evidence_root, index=op_index,
            label="board_a_read_mac", argv=build_read_mac_command(args.board_a_port),
            cwd=repo_root, target_operation=True,
            extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"})
        op_index += 1
        if identity.returncode != 0:
            raise StopExecution("board_a read-mac failed")
        target_access = True
        base_mac = parse_base_mac(identity.stdout or "")
        if mac_suffix(base_mac) != EXPECTED_BOARD_A_SUFFIX:
            raise StopExecution("board_a identity suffix mismatch")
        board_a_dir = evidence_root / "board_a"
        ensure_private_dir(board_a_dir)
        write_json(board_a_dir / "identity_private.json", {
            "base_mac": base_mac, "base_mac_sha256": hashlib.sha256(base_mac.encode()).hexdigest(),
            "observed_suffix": mac_suffix(base_mac), "identity_match": True,
        })
        failed = "BOARD_A_NVS_READ"
        nvs_path = board_a_dir / "nvs_partition.bin"
        nvs = run_recorded(evidence_root=evidence_root, index=op_index,
            label="board_a_read_nvs", argv=build_read_nvs_command(args.board_a_port, nvs_path),
            cwd=repo_root, target_operation=True,
            extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"})
        op_index += 1
        if nvs.returncode != 0:
            raise StopExecution("board_a NVS read failed")
        target_access = True
        if not nvs_path.is_file() or nvs_path.stat().st_size != NVS_SIZE:
            raise StopExecution("board_a NVS output size/path mismatch")
        os.chmod(nvs_path, 0o600)
        failed = "BOARD_A_SCHEMA_V5_DECODE"
        op_index, board_a = decode_nvs(root=evidence_root, repo_root=repo_root,
            nvs_path=nvs_path, op_index=op_index, label="board_a_decode_snapshot",
            fields=BOARD_A_REQUIRED_FIELDS, board="board_a")
        write_json(board_a_dir / "selected_counters.json", board_a)
        write_json(board_a_dir / "capture_manifest.json", {
            "nvs_offset": hex(NVS_OFFSET), "nvs_size": hex(NVS_SIZE),
            "nvs_sha256": sha256_file(nvs_path), "snapshot_schema_version": EXPECTED_SCHEMA_VERSION,
        })
        write_closure(evidence_root, execution_id=args.execution_id,
            package_commit=args.expected_package_commit, authorization_id=args.authorization_id,
            result="PASS", failed=None, stop_reason=None, target_access=target_access,
            board_b=board_b, board_a=board_a)
    except (StopExecution, OSError, json.JSONDecodeError) as exc:
        write_closure(evidence_root, execution_id=args.execution_id,
            package_commit=args.expected_package_commit, authorization_id=args.authorization_id,
            result="STOP", failed=failed, stop_reason=str(exc), target_access=target_access,
            board_b=board_b, board_a=board_a)
    closure = json.loads((evidence_root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["read_only_recovery_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
