#!/usr/bin/env python3
"""N3W KF-089 ID13 dual-board read-only Schema-v5 recovery executor.

This executor is intentionally narrow:
- host preflight first;
- Board B identity -> one read-only NVS capture -> Schema-v5 decode;
- Board A identity -> one read-only NVS capture -> Schema-v5 decode;
- raw evidence is persisted before/after every external command;
- no application boot, reset retry, RF capture, flash/NVS/otadata write, or T1 access.

The physical authorization is claimed/consumed immediately before the first
deliberate board-targeted command. Any failure after that point is fail-closed.
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
EXPECTED_DIAG_PARSER_BLOB = "de6951daf6cfd20035243b85c32957eb6108308a"

EXPECTED_SUFFIX = {
    "board_b": "f4:5c",
    "board_a": "f3:50",
}

BOARD_REQUIRED_FIELDS = {
    "board_b": (
        "schema_version",
        "boot_session",
        "snapshot_uptime_ms",
        "path_state",
        "relay_active_count",
        "relay_telemetry_attempts",
        "relay_telemetry_success",
        "unicast_completion_count",
        "unicast_completion_success",
        "unicast_completion_failure",
    ),
    "board_a": (
        "schema_version",
        "boot_session",
        "snapshot_uptime_ms",
        "path_state",
        "compact_rx_count",
        "compact_state_reject_count",
        "compact_child_binding_failure",
        "compact_decode_success",
        "compact_decode_failure",
        "compact_wrap_failure",
        "compact_forward_attempts",
        "compact_forward_submit_success",
        "compact_forward_submit_failure",
    ),
}

BASE_MAC_RE = re.compile(
    r"(?im)^\s*BASE MAC:\s*([0-9a-f]{2}(?::[0-9a-f]{2}){5})\s*$"
)
VERSION_RE = re.compile(r"(?i)\bv?(\d+\.\d+\.\d+)\b")
WRITE_LIKE_TOKENS = {
    "write-flash",
    "erase-flash",
    "erase-region",
    "write-mem",
    "write-flash-status",
    "write_flash",
    "erase_flash",
    "erase_region",
    "write_mem",
    "write_flash_status",
}


class StopExecution(RuntimeError):
    """Fail-closed execution stop."""


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
        if (
            (candidate / "AGENTS.md").is_file()
            and (candidate / DIAG_PARSER_RELATIVE).is_file()
        ):
            return candidate
    raise StopExecution("repository root could not be located")


def load_manifest(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StopExecution(f"manifest load failed: {exc}") from exc
    if value.get("package_schema_version") != PACKAGE_SCHEMA_VERSION:
        raise StopExecution("manifest package schema version mismatch")
    if value.get("gate_id") != "id13_readonly_recovery":
        raise StopExecution("manifest gate id mismatch")
    return value


def assert_read_only_argv(argv: Iterable[str]) -> None:
    lowered = {str(item).strip().lower() for item in argv}
    forbidden = sorted(lowered & WRITE_LIKE_TOKENS)
    if forbidden:
        raise StopExecution(f"write-like esptool token forbidden: {forbidden}")


def esptool_base(port: str) -> list[str]:
    if not port or "\x00" in port:
        raise StopExecution("serial port locator is invalid")
    return [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--before",
        "no-reset",
        "--after",
        "no-reset",
        "--no-stub",
    ]


def build_read_mac_command(port: str) -> list[str]:
    argv = [*esptool_base(port), "read-mac"]
    assert_read_only_argv(argv)
    return argv


def build_read_nvs_command(port: str, output_path: Path) -> list[str]:
    argv = [
        *esptool_base(port),
        "read-flash",
        "--flash-size",
        FLASH_SIZE,
        hex(NVS_OFFSET),
        hex(NVS_SIZE),
        str(output_path),
    ]
    assert_read_only_argv(argv)
    return argv


def parse_base_mac(stdout: str) -> str:
    matches = [match.lower() for match in BASE_MAC_RE.findall(stdout)]
    distinct = sorted(set(matches))
    if not distinct:
        raise StopExecution("no complete BASE MAC line found")
    if len(distinct) != 1:
        raise StopExecution("multiple distinct BASE MAC values found")
    return distinct[0]


def mac_suffix(mac: str) -> str:
    parts = mac.lower().split(":")
    if len(parts) != 6:
        raise StopExecution("normalized base MAC is invalid")
    return ":".join(parts[-2:])


def validate_snapshot(board: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    if board not in BOARD_REQUIRED_FIELDS:
        raise StopExecution("unknown board role")
    if snapshot.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise StopExecution(
            f"{board} diagnostic schema mismatch: "
            f"{snapshot.get('schema_version')!r}"
        )
    missing = [
        field for field in BOARD_REQUIRED_FIELDS[board]
        if field not in snapshot
    ]
    if missing:
        raise StopExecution(f"{board} snapshot missing fields: {missing}")
    return {field: snapshot[field] for field in BOARD_REQUIRED_FIELDS[board]}


def operation_dir(evidence_root: Path, index: int, label: str) -> Path:
    op_dir = evidence_root / f"op_{index:02d}_{label}"
    ensure_private_dir(op_dir)
    return op_dir


def run_recorded(
    *,
    evidence_root: Path,
    index: int,
    label: str,
    argv: list[str],
    cwd: Path,
    target_operation: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Persist command evidence before process launch, then result evidence."""
    assert_read_only_argv(argv)
    op_dir = operation_dir(evidence_root, index, label)
    command_path = op_dir / "command.json"
    stdout_path = op_dir / "stdout.txt"
    stderr_path = op_dir / "stderr.txt"
    result_path = op_dir / "result.json"

    command = {
        "argv": argv,
        "cwd": str(cwd),
        "executable": argv[0] if argv else None,
        "label": label,
        "operation_index": index,
        "target_operation": target_operation,
        "utc_start": utc_now(),
    }
    if extra_env:
        command["environment_overrides"] = {
            key: extra_env[key] for key in sorted(extra_env)
        }
    write_json(command_path, command)

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    command_started = False
    try:
        command_started = True
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        write_text(stdout_path, "")
        write_text(stderr_path, f"{type(exc).__name__}: {exc}\n")
        write_json(
            result_path,
            {
                "command_started": False,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "returncode": None,
                "target_access_occurred": False if target_operation else None,
                "utc_end": utc_now(),
            },
        )
        raise StopExecution(f"{label} process launch failed") from exc

    write_text(stdout_path, completed.stdout or "")
    write_text(stderr_path, completed.stderr or "")
    write_json(
        result_path,
        {
            "command_started": command_started,
            "returncode": completed.returncode,
            "target_access_occurred": (
                True if target_operation and completed.returncode == 0
                else "UNKNOWN" if target_operation
                else None
            ),
            "utc_end": utc_now(),
        },
    )
    return completed


def verify_esptool_version(
    evidence_root: Path, repo_root: Path, op_index: int
) -> int:
    completed = run_recorded(
        evidence_root=evidence_root,
        index=op_index,
        label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"],
        cwd=repo_root,
    )
    if completed.returncode != 0:
        raise StopExecution("esptool version preflight failed")
    versions = VERSION_RE.findall((completed.stdout or "") + "\n" + (completed.stderr or ""))
    if EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution(
            f"esptool version mismatch; expected {EXPECTED_ESPTOOL_VERSION}"
        )
    return op_index + 1


def verify_git_bindings(
    *,
    evidence_root: Path,
    repo_root: Path,
    expected_package_commit: str,
    op_index: int,
) -> int:
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"]),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"]),
        (
            "host_diag_parser_blob",
            ["git", "hash-object", str(DIAG_PARSER_RELATIVE)],
        ),
    )
    outputs: dict[str, str] = {}
    for label, argv in checks:
        completed = run_recorded(
            evidence_root=evidence_root,
            index=op_index,
            label=label,
            argv=argv,
            cwd=repo_root,
        )
        if completed.returncode != 0:
            raise StopExecution(f"{label} failed")
        outputs[label] = (completed.stdout or "").strip()
        op_index += 1

    if outputs["host_git_head"] != expected_package_commit:
        raise StopExecution("execution package commit binding mismatch")
    if outputs["host_git_status"]:
        raise StopExecution("tracked worktree is not clean")
    if outputs["host_diag_parser_blob"] != EXPECTED_DIAG_PARSER_BLOB:
        raise StopExecution("diagnostic parser blob binding mismatch")
    return op_index


def verify_port_locators(
    evidence_root: Path,
    board_b_port: str,
    board_a_port: str,
) -> None:
    """Host-only locator preflight. This does not open either serial device."""
    paths = {
        "board_b": Path(board_b_port),
        "board_a": Path(board_a_port),
    }
    resolved = {name: os.path.realpath(str(path)) for name, path in paths.items()}
    if resolved["board_b"] == resolved["board_a"]:
        raise StopExecution("Board A and Board B resolve to the same port locator")

    report: dict[str, Any] = {
        "serial_open": False,
        "usb_device_open": False,
        "checked_at": utc_now(),
        "targets": {},
    }
    for name, path in paths.items():
        try:
            info = path.stat()
        except OSError as exc:
            raise StopExecution(f"{name} port locator is unavailable: {exc}") from exc
        if not stat.S_ISCHR(info.st_mode):
            raise StopExecution(f"{name} port locator is not a character device")
        report["targets"][name] = {
            "locator": str(path),
            "resolved_locator": resolved[name],
            "exists": True,
            "character_device": True,
        }
    write_json(evidence_root / "host_port_locator_preflight.json", report)


def claim_authorization(
    evidence_root: Path,
    authorization_id: str,
    execution_id: str,
) -> None:
    path = evidence_root / "authorization.json"
    write_json(
        path,
        {
            "authorization_id": authorization_id,
            "execution_id": execution_id,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "claim_boundary": "immediately_before_first_board_target_command",
            "claimed_at": utc_now(),
            "consumed_at": utc_now(),
        },
    )


def initial_authorization(
    evidence_root: Path,
    authorization_id: str,
    execution_id: str,
) -> None:
    write_json(
        evidence_root / "authorization.json",
        {
            "authorization_id": authorization_id,
            "execution_id": execution_id,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        },
    )


def read_snapshot(
    *,
    board: str,
    port: str,
    evidence_root: Path,
    repo_root: Path,
    op_index: int,
) -> tuple[int, dict[str, Any]]:
    board_dir = evidence_root / board
    ensure_private_dir(board_dir)

    identity_cmd = build_read_mac_command(port)
    identity_result = run_recorded(
        evidence_root=evidence_root,
        index=op_index,
        label=f"{board}_read_mac",
        argv=identity_cmd,
        cwd=repo_root,
        target_operation=True,
        extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"},
    )
    op_index += 1
    if identity_result.returncode != 0:
        raise StopExecution(f"{board} read-mac failed")

    base_mac = parse_base_mac(identity_result.stdout or "")
    suffix = mac_suffix(base_mac)
    expected = EXPECTED_SUFFIX[board]
    identity_private = {
        "board": board,
        "base_mac": base_mac,
        "base_mac_sha256": sha256_bytes(base_mac.encode("ascii")),
        "observed_suffix": suffix,
        "expected_suffix": expected,
        "identity_match": suffix == expected,
    }
    write_json(board_dir / "identity_private.json", identity_private)
    if suffix != expected:
        raise StopExecution(
            f"{board} identity mismatch: expected suffix {expected}, got {suffix}"
        )

    nvs_path = board_dir / "nvs_partition.bin"
    nvs_cmd = build_read_nvs_command(port, nvs_path)
    nvs_result = run_recorded(
        evidence_root=evidence_root,
        index=op_index,
        label=f"{board}_read_nvs",
        argv=nvs_cmd,
        cwd=repo_root,
        target_operation=True,
        extra_env={"ESPTOOL_OPEN_PORT_ATTEMPTS": "1"},
    )
    op_index += 1
    if nvs_result.returncode != 0:
        raise StopExecution(f"{board} NVS read failed")
    if not nvs_path.is_file():
        raise StopExecution(f"{board} NVS output file missing")
    os.chmod(nvs_path, 0o600)
    if nvs_path.stat().st_size != NVS_SIZE:
        raise StopExecution(f"{board} NVS output size mismatch")

    parser_cmd = [
        sys.executable,
        str(repo_root / DIAG_PARSER_RELATIVE),
        "--blob",
        str(nvs_path),
    ]
    parsed = run_recorded(
        evidence_root=evidence_root,
        index=op_index,
        label=f"{board}_decode_snapshot",
        argv=parser_cmd,
        cwd=repo_root,
    )
    op_index += 1
    if parsed.returncode != 0:
        raise StopExecution(f"{board} Schema-v5 decode failed")
    try:
        snapshot = json.loads(parsed.stdout)
    except json.JSONDecodeError as exc:
        raise StopExecution(f"{board} decoded snapshot is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        raise StopExecution(f"{board} decoded snapshot must be an object")

    selected = validate_snapshot(board, snapshot)
    write_json(board_dir / "snapshot_private.json", snapshot)
    write_json(board_dir / "selected_counters.json", selected)
    write_json(
        board_dir / "capture_manifest.json",
        {
            "board": board,
            "base_mac_sha256": identity_private["base_mac_sha256"],
            "observed_suffix": suffix,
            "identity_match": True,
            "nvs_offset": hex(NVS_OFFSET),
            "nvs_size": hex(NVS_SIZE),
            "nvs_sha256": sha256_file(nvs_path),
            "snapshot_schema_version": snapshot["schema_version"],
            "selected_counters_sha256": sha256_file(
                board_dir / "selected_counters.json"
            ),
        },
    )
    return op_index, selected


def evidence_file_manifest(evidence_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(evidence_root).as_posix()
        if relative == "evidence_manifest.json":
            continue
        items.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return items


def write_closure(
    *,
    evidence_root: Path,
    execution_id: str,
    expected_package_commit: str,
    authorization_id: str,
    result: str,
    first_failed_operation: str | None,
    target_access_occurred: bool | str,
    board_b: dict[str, Any] | None,
    board_a: dict[str, Any] | None,
    stop_reason: str | None,
) -> None:
    auth = json.loads(
        (evidence_root / "authorization.json").read_text(encoding="utf-8")
    )
    closure = {
        "execution_id": execution_id,
        "execution_package_commit": expected_package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False,
        "raw_evidence_complete": result == "PASS",
        "first_failed_operation": first_failed_operation,
        "target_access_occurred": target_access_occurred,
        "read_only_recovery_result": result,
        "board_b_selected_counters": board_b,
        "board_a_selected_counters": board_a,
        "next_route": (
            "HIGH_LEVEL_MODEL_SCHEMA_V5_COUNTER_ADJUDICATION"
            if result == "PASS"
            else "STOP_RETURN_TO_HIGH_LEVEL_MODEL"
        ),
        "stop_reason": stop_reason,
    }
    write_json(evidence_root / "closure.json", closure)
    manifest = {
        "schema_version": 1,
        "execution_id": execution_id,
        "authorization": authorization_id,
        "files": evidence_file_manifest(evidence_root),
    }
    write_json(evidence_root / "evidence_manifest.json", manifest)


def self_check(package_dir: Path) -> dict[str, Any]:
    manifest = load_manifest(package_dir)
    repo_root = find_repo_root(package_dir)
    try:
        import esptool
    except ImportError as exc:
        raise StopExecution("esptool module is not installed") from exc
    if getattr(esptool, "__version__", None) != EXPECTED_ESPTOOL_VERSION:
        raise StopExecution("esptool module version mismatch")
    parser = repo_root / DIAG_PARSER_RELATIVE
    if not parser.is_file():
        raise StopExecution("diagnostic parser is missing")
    read_mac = build_read_mac_command("/dev/example")
    read_nvs = build_read_nvs_command("/dev/example", Path("/tmp/nvs.bin"))
    for argv in (read_mac, read_nvs):
        assert_read_only_argv(argv)
    return {
        "package_schema_version": manifest["package_schema_version"],
        "gate_id": manifest["gate_id"],
        "diag_parser_path": str(DIAG_PARSER_RELATIVE),
        "expected_diag_parser_blob": EXPECTED_DIAG_PARSER_BLOB,
        "expected_esptool_version": EXPECTED_ESPTOOL_VERSION,
        "read_mac_uses_no_stub": "--no-stub" in read_mac,
        "read_nvs_uses_no_stub": "--no-stub" in read_nvs,
        "read_nvs_flash_size": FLASH_SIZE,
        "write_like_tokens_present": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--board-b-port")
    parser.add_argument("--board-a-port")
    parser.add_argument("--evidence-root", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    package_dir = Path(__file__).resolve().parent

    if args.self_check:
        print(json.dumps(self_check(package_dir), sort_keys=True))
        return 0

    required = {
        "expected-package-commit": args.expected_package_commit,
        "authorization-id": args.authorization_id,
        "execution-id": args.execution_id,
        "board-b-port": args.board_b_port,
        "board-a-port": args.board_a_port,
        "evidence-root": args.evidence_root,
    }
    missing = sorted(name for name, value in required.items() if not value)
    if missing:
        raise SystemExit(f"missing required execution arguments: {', '.join(missing)}")
    if args.board_b_port == args.board_a_port:
        raise SystemExit("Board A and Board B port locators must be distinct")

    evidence_root = args.evidence_root.resolve()
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise SystemExit("evidence root must be absent or empty")
    ensure_private_dir(evidence_root)

    repo_root = find_repo_root(package_dir)
    try:
        evidence_root.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise SystemExit("evidence root must be outside the repository")
    load_manifest(package_dir)
    initial_authorization(evidence_root, args.authorization_id, args.execution_id)

    op_index = 1
    board_b_selected: dict[str, Any] | None = None
    board_a_selected: dict[str, Any] | None = None
    first_failed: str | None = None
    target_access: bool | str = False

    write_json(
        evidence_root / "session.json",
        {
            "execution_id": args.execution_id,
            "expected_package_commit": args.expected_package_commit,
            "authorization_id": args.authorization_id,
            "created_at": utc_now(),
            "board_b_port_locator": args.board_b_port,
            "board_a_port_locator": args.board_a_port,
            "board_b_expected_suffix": EXPECTED_SUFFIX["board_b"],
            "board_a_expected_suffix": EXPECTED_SUFFIX["board_a"],
            "application_boot": False,
            "second_rf_capture": False,
            "flash_write": False,
            "nvs_write": False,
            "otadata_write": False,
            "t1_mutation": False,
            "auto_retry": False,
        },
    )

    try:
        op_index = verify_git_bindings(
            evidence_root=evidence_root,
            repo_root=repo_root,
            expected_package_commit=args.expected_package_commit,
            op_index=op_index,
        )
        op_index = verify_esptool_version(evidence_root, repo_root, op_index)
        verify_port_locators(
            evidence_root,
            args.board_b_port,
            args.board_a_port,
        )

        claim_authorization(
            evidence_root,
            args.authorization_id,
            args.execution_id,
        )

        try:
            op_index, board_b_selected = read_snapshot(
                board="board_b",
                port=args.board_b_port,
                evidence_root=evidence_root,
                repo_root=repo_root,
                op_index=op_index,
            )
            target_access = True
        except StopExecution:
            first_failed = "BOARD_B_READONLY_RECOVERY"
            target_access = "UNKNOWN"
            raise

        try:
            op_index, board_a_selected = read_snapshot(
                board="board_a",
                port=args.board_a_port,
                evidence_root=evidence_root,
                repo_root=repo_root,
                op_index=op_index,
            )
            target_access = True
        except StopExecution:
            first_failed = "BOARD_A_READONLY_RECOVERY"
            target_access = True
            raise

    except StopExecution as exc:
        if first_failed is None:
            first_failed = "HOST_PREFLIGHT"
            target_access = False
        write_closure(
            evidence_root=evidence_root,
            execution_id=args.execution_id,
            expected_package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="STOP",
            first_failed_operation=first_failed,
            target_access_occurred=target_access,
            board_b=board_b_selected,
            board_a=board_a_selected,
            stop_reason=str(exc),
        )
        print(json.dumps(json.loads(
            (evidence_root / "closure.json").read_text(encoding="utf-8")
        ), sort_keys=True))
        return 2

    write_closure(
        evidence_root=evidence_root,
        execution_id=args.execution_id,
        expected_package_commit=args.expected_package_commit,
        authorization_id=args.authorization_id,
        result="PASS",
        first_failed_operation=None,
        target_access_occurred=True,
        board_b=board_b_selected,
        board_a=board_a_selected,
        stop_reason=None,
    )
    print(json.dumps(json.loads(
        (evidence_root / "closure.json").read_text(encoding="utf-8")
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
