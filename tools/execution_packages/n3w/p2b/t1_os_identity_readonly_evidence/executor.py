#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[5]
PROBE_RELATIVE = "tools/n3w_t1_os_identity_readonly_probe.py"
PROBE_SOURCE = REPO_ROOT / PROBE_RELATIVE
PROBE_SOURCE_COMMIT = "a43c5750a8051946a9f08e3b3b2af3c5d7b9de69"
EXPECTED_PROBE_BLOB_SHA = "26a2f47c9c83fef5637f551ea75ba6b5d5ba3866"
CONFIRMATION = "READONLY TARGET ARMBIAN EVIDENCE: YES"
SCHEMA = "gh.n3w.t1-os-identity-readonly-evidence-execution/1"
REMOTE_COMMAND = "sudo -n python3 -B - --root /"
PLACEHOLDERS = (
    "placeholder",
    "example",
    "<",
    ">",
    "t1_ssh_target",
)
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 600


class StopExecution(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_target(target: str) -> None:
    if not target or target.strip() != target or any(ch.isspace() for ch in target):
        raise StopExecution("t1_ssh_target_invalid")
    if target.startswith("-"):
        raise StopExecution("t1_ssh_target_invalid")
    try:
        target.encode("ascii")
    except UnicodeEncodeError as error:
        raise StopExecution("t1_ssh_target_invalid") from error
    folded = target.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDERS):
        raise StopExecution("t1_ssh_target_placeholder")


def validate_timeout(timeout_seconds: int) -> None:
    if (
        isinstance(timeout_seconds, bool)
        or timeout_seconds < MIN_TIMEOUT_SECONDS
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        raise StopExecution("timeout_seconds_invalid")


def _git_text(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ("git", "-C", str(REPO_ROOT), *arguments),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StopExecution("local_git_unavailable") from error
    if completed.returncode != 0:
        raise StopExecution("local_git_failed")
    return completed.stdout.strip()


def validate_local_source_authority(expected_source_head: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_source_head) is None:
        raise StopExecution("expected_source_head_invalid")
    observed_head = _git_text("rev-parse", "HEAD")
    if observed_head != expected_source_head:
        raise StopExecution("local_source_head_mismatch")
    if _git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("local_tracked_worktree_dirty")
    probe_blob = _git_text(
        "rev-parse",
        f"{expected_source_head}:{PROBE_RELATIVE}",
    )
    if probe_blob != EXPECTED_PROBE_BLOB_SHA:
        raise StopExecution("authorized_probe_blob_mismatch")
    return {
        "expected_source_head": expected_source_head,
        "observed_source_head": observed_head,
        "tracked_worktree_clean": True,
        "authorized_probe_blob_sha": probe_blob,
    }


def validate_evidence_root(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise StopExecution("evidence_root_symlink_forbidden")
    try:
        resolved = expanded.resolve()
        repo = REPO_ROOT.resolve()
        if resolved == repo or repo in resolved.parents:
            raise StopExecution("evidence_root_inside_repository")
        if resolved.exists():
            if not resolved.is_dir():
                raise StopExecution("evidence_root_not_directory")
            metadata = resolved.stat()
            if metadata.st_uid != os.geteuid():
                raise StopExecution("evidence_root_owner_invalid")
            if stat.S_IMODE(metadata.st_mode) != 0o700:
                raise StopExecution("evidence_root_mode_invalid")
            if any(resolved.iterdir()):
                raise StopExecution("evidence_root_not_empty")
        else:
            resolved.mkdir(parents=True, mode=0o700)
        metadata = resolved.stat()
        if metadata.st_uid != os.geteuid():
            raise StopExecution("evidence_root_owner_invalid")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise StopExecution("evidence_root_mode_invalid")
        return resolved
    except StopExecution:
        raise
    except OSError as error:
        raise StopExecution("evidence_root_access_failed") from error


def write_private(path: Path, data: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise StopExecution("local_evidence_write_failed") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise StopExecution("local_evidence_file_metadata_invalid")
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ssh_argv(target: str) -> list[str]:
    validate_target(target)
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        target,
        REMOTE_COMMAND,
    ]


def load_probe_source() -> bytes:
    if not PROBE_SOURCE.is_file() or PROBE_SOURCE.is_symlink():
        raise StopExecution("probe_source_missing")
    data = PROBE_SOURCE.read_bytes()
    if git_blob_sha(data) != EXPECTED_PROBE_BLOB_SHA:
        raise StopExecution("probe_source_binding_invalid")
    return data


def validate_report(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StopExecution("probe_report_invalid")
    expected = {
        "schema": "gh.n3w.t1-os-identity-readonly-probe/1",
        "status": "PASS",
        "secret_values_included": False,
        "mutation": False,
        "production_service_start": False,
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_evidence_required": True,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise StopExecution(f"probe_report_binding_invalid:{key}")
    return document


def _stop_result(
    *,
    error_code: str,
    stdout: bytes,
    stderr: bytes,
    returncode: int | None,
    timed_out: bool,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "STOP",
        "error_code": error_code,
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "read_only": True,
        "t1_file_write": False,
        "live_runtime_mutation": False,
        "systemd_live_mutation": False,
        "production_service_start": False,
    }


def _persist_result(root: Path, document: dict[str, object]) -> None:
    write_private(
        root / "result.json",
        (json.dumps(document, indent=2, sort_keys=True) + "\n").encode(),
    )


def execute(
    *,
    target: str,
    evidence_root: Path,
    confirmation: str,
    expected_source_head: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_target(target)
    validate_timeout(timeout_seconds)
    authority = validate_local_source_authority(expected_source_head)
    probe = load_probe_source()
    root = validate_evidence_root(evidence_root)
    argv = ssh_argv(target)
    command_record = {
        "schema": SCHEMA,
        "probe_source_commit": PROBE_SOURCE_COMMIT,
        "probe_blob_sha": EXPECTED_PROBE_BLOB_SHA,
        "probe_sha256": sha256_bytes(probe),
        "expected_source_head": expected_source_head,
        "observed_source_head": authority["observed_source_head"],
        "tracked_worktree_clean": authority["tracked_worktree_clean"],
        "target_sha256": hashlib.sha256(target.encode()).hexdigest(),
        "remote_command": REMOTE_COMMAND,
        "python_bytecode_write_disabled": True,
        "read_only": True,
        "t1_file_write": False,
        "production_service_start": False,
    }
    write_private(
        root / "command.json",
        (json.dumps(command_record, indent=2, sort_keys=True) + "\n").encode(),
    )
    try:
        completed = subprocess.run(
            argv,
            input=probe,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        write_private(root / "stdout.bin", stdout)
        write_private(root / "stderr.bin", stderr)
        _persist_result(
            root,
            _stop_result(
                error_code="readonly_probe_timeout",
                stdout=stdout,
                stderr=stderr,
                returncode=None,
                timed_out=True,
            ),
        )
        raise StopExecution("readonly_probe_timeout") from error
    except OSError as error:
        stdout = b""
        stderr = b""
        write_private(root / "stdout.bin", stdout)
        write_private(root / "stderr.bin", stderr)
        _persist_result(
            root,
            _stop_result(
                error_code="ssh_transport_error",
                stdout=stdout,
                stderr=stderr,
                returncode=None,
                timed_out=False,
            ),
        )
        raise StopExecution("ssh_transport_error") from error

    write_private(root / "stdout.bin", completed.stdout)
    write_private(root / "stderr.bin", completed.stderr)
    if completed.returncode != 0:
        _persist_result(
            root,
            _stop_result(
                error_code="readonly_probe_failed",
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
                timed_out=False,
            ),
        )
        raise StopExecution(f"readonly_probe_failed:{completed.returncode}")
    try:
        document = json.loads(completed.stdout.decode("utf-8"))
        report = validate_report(document)
    except (UnicodeDecodeError, json.JSONDecodeError, StopExecution) as error:
        _persist_result(
            root,
            _stop_result(
                error_code="probe_report_invalid",
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
                timed_out=False,
            ),
        )
        raise StopExecution("probe_report_invalid") from error
    write_private(
        root / "report.json",
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
    )
    result = {
        "schema": SCHEMA,
        "status": "PASS",
        "probe_source_commit": PROBE_SOURCE_COMMIT,
        "probe_blob_sha": EXPECTED_PROBE_BLOB_SHA,
        "expected_source_head": expected_source_head,
        "observed_source_head": authority["observed_source_head"],
        "probe_output_sha256": sha256_bytes(completed.stdout),
        "probe_output_bytes": len(completed.stdout),
        "target_sha256": hashlib.sha256(target.encode()).hexdigest(),
        "python_bytecode_write_disabled": True,
        "read_only": True,
        "t1_file_write": False,
        "live_runtime_mutation": False,
        "systemd_live_mutation": False,
        "production_service_start": False,
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_evidence_required": True,
    }
    _persist_result(root, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--target")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-source-head")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": "execute_required",
                }
            )
        )
        return 2
    if (
        args.target is None
        or args.evidence_root is None
        or args.expected_source_head is None
    ):
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": "execution_argument_missing",
                }
            )
        )
        return 2
    try:
        result = execute(
            target=args.target,
            evidence_root=args.evidence_root,
            confirmation=args.confirm,
            expected_source_head=args.expected_source_head,
            timeout_seconds=args.timeout_seconds,
        )
    except StopExecution as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error),
                }
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
