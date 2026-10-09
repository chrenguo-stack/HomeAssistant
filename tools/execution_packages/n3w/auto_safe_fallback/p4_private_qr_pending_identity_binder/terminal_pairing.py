from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from bridge_handoff import (
    GateStop,
    bind_terminal_projection,
    capture_private_qr,
    reject,
)
from validator import read_private_baseline

CONTAINER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}\Z")
RESULT_SCHEMA = "gh.pair.setup-secret-import-result/1"
Runner = Callable[..., subprocess.CompletedProcess]


def _target(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z0-9_-]{0,31}@)?[A-Za-z0-9][A-Za-z0-9_.-]{0,252}",
        value,
    ):
        reject("TARGET_INVALID")
    return value


def _command(target: str, container: str, *, importer: bool) -> list[str]:
    _target(target)
    if not CONTAINER.fullmatch(container):
        reject("MANAGER_CONTAINER_INVALID")
    common = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-T", target,
        "docker", "exec",
    ]
    if importer:
        return [
            *common, "-i", container, "greenhouse-manager-pairing",
            "import-payload", "--payload-stdin",
        ]
    return [*common, container, "greenhouse-manager-registration", "p4-pending-readonly"]

def _read_pending(target: str, container: str, runner: Runner) -> dict:
    try:
        completed = runner(
            _command(target, container, importer=False),
            capture_output=True,
            timeout=12,
            check=False,
        )
        if completed.returncode != 0 or len(completed.stdout) > 8192:
            reject("TERMINAL_PENDING_QUERY_FAILED")
        doc = json.loads(completed.stdout)
        if not isinstance(doc, dict):
            reject("TERMINAL_PENDING_INVALID")
        return doc
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError):
        reject("TERMINAL_PENDING_QUERY_FAILED")


AUTHORIZATION_SCHEMA = "n3w.p4.exact-attempt-authorization/1"


def _grant_path(directory: Path, pairing: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", pairing):
        reject("AUTHORIZATION_IDENTITY_INVALID")
    return directory / ("p4-authorization-" + pairing + ".json")


def _private_directory(directory: Path) -> None:
    try:
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid()
            or directory.is_symlink()
        ):
            reject("PRIVATE_AUTHORIZATION_DIR_INVALID")
    except OSError as error:
        raise GateStop("PRIVATE_AUTHORIZATION_DIR_INVALID") from error


def _write_authorization(
    directory: Path,
    binding: object,
    container: str,
    now: datetime,
) -> None:
    _private_directory(directory)
    if now.tzinfo is None:
        reject("AUTHORIZATION_TIME_INVALID")
    path = _grant_path(directory, binding.pairing_sha256)
    doc = {
        "schema": AUTHORIZATION_SCHEMA,
        "hardware_sha256": binding.hardware_sha256,
        "pairing_sha256": binding.pairing_sha256,
        "expires_at": binding.expires_at.astimezone(UTC).isoformat(),
        "manager_container": container,
        "authorized_at": now.astimezone(UTC).isoformat(),
        "state": "AUTHORIZED",
    }
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                reject("AUTHORIZATION_RECORD_INCOMPLETE")
            os.fsync(fd)
        finally:
            os.close(fd)
        directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise GateStop("AUTHORIZATION_RECORD_ALREADY_EXISTS_OR_FAILED") from error


def _require_authorization(
    directory: Path,
    binding: object,
    container: str,
    now: datetime,
) -> None:
    _private_directory(directory)
    try:
        path = _grant_path(directory, binding.pairing_sha256)
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.getuid()
                or info.st_size > 2048
            ):
                reject("AUTHORIZATION_RECORD_INVALID")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                document = json.loads(handle.read(2049))
        finally:
            os.close(fd)
        if not isinstance(document, dict) or set(document) != {
            "schema", "hardware_sha256", "pairing_sha256", "expires_at",
            "manager_container", "authorized_at", "state",
        }:
            reject("AUTHORIZATION_RECORD_INVALID")
        authorized = datetime.fromisoformat(document["authorized_at"])
        if authorized.tzinfo is None or now.tzinfo is None:
            reject("AUTHORIZATION_TIME_INVALID")
        elapsed = (now.astimezone(UTC) - authorized.astimezone(UTC)).total_seconds()
        if not 0 <= elapsed <= 120:
            reject("AUTHORIZATION_EXPIRED")
        if (
            document["schema"] != AUTHORIZATION_SCHEMA
            or document["state"] != "AUTHORIZED"
            or document["hardware_sha256"] != binding.hardware_sha256
            or document["pairing_sha256"] != binding.pairing_sha256
            or document["expires_at"] != binding.expires_at.astimezone(UTC).isoformat()
            or document["manager_container"] != container
        ):
            reject("AUTHORIZATION_MISMATCH")
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
        raise GateStop("AUTHORIZATION_MISSING_OR_INVALID") from error


def authorize(
    target: str,
    container: str,
    baseline_path: Path,
    baseline_sha256: str,
    authorization_dir: Path,
    *,
    runner: Runner = subprocess.run,
    read_qr: Callable[[], str] = capture_private_qr,
    confirm: Callable[[str], bool],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> str:
    _target(target)
    if not CONTAINER.fullmatch(container):
        reject("MANAGER_CONTAINER_INVALID")
    baseline = read_private_baseline(baseline_path, baseline_sha256)
    payload = read_qr()
    projection = _read_pending(target, container, runner)
    binding = bind_terminal_projection(payload, projection, baseline, clock())
    if not confirm(binding.pairing_sha256[:12]):
        reject("AUTHORIZATION_DECLINED")
    fresh = _read_pending(target, container, runner)
    confirmed = bind_terminal_projection(payload, fresh, baseline, clock())
    if confirmed != binding:
        reject("PENDING_CHANGED")
    _write_authorization(authorization_dir, binding, container, clock())
    return "AUTHORIZATION_RECORDED_NOT_IMPORTED"


def _private_claim(directory: Path, hardware: str, pairing: str, now: datetime) -> None:
    try:
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            reject("PRIVATE_CLAIM_DIR_INVALID")
        if info.st_uid != os.getuid() or directory.is_symlink():
            reject("PRIVATE_CLAIM_DIR_INVALID")
        if not re.fullmatch(r"[0-9a-f]{64}", pairing):
            reject("PRIVATE_CLAIM_INVALID")
        marker = directory / ("p4-attempt-" + pairing + ".json")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(marker, flags, 0o600)
        try:
            doc = {
                "schema": "n3w.p4.import-once-claim/1",
                "attempt_id": str(uuid.uuid4()),
                "hardware_sha256": hardware,
                "pairing_sha256": pairing,
                "claimed_at": now.astimezone(UTC).isoformat(),
                "state": "CLAIMED",
            }
            encoded = json.dumps(doc, sort_keys=True).encode("ascii")
            if os.write(fd, encoded) != len(encoded):
                reject("IMPORT_CLAIM_WRITE_INCOMPLETE")
            os.fsync(fd)
        finally:
            os.close(fd)
        dir_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except (OSError, ValueError) as error:
        raise GateStop("IMPORT_ALREADY_CLAIMED_OR_PRIVATE_IO_FAILED") from error


def _deliver(
    target: str,
    container: str,
    payload: str,
    runner: Runner,
) -> str:
    try:
        completed = runner(
            _command(target, container, importer=True),
            input=(payload + "\n").encode("ascii"),
            capture_output=True,
            timeout=12,
            check=False,
        )
        if completed.returncode not in (0, 2) or len(completed.stdout) > 4096:
            return "UNKNOWN_STOP"
        result = json.loads(completed.stdout)
        if not isinstance(result, dict) or result.get("schema") != RESULT_SCHEMA:
            return "UNKNOWN_STOP"
        if set(result) != {"accepted", "code", "schema"}:
            return "UNKNOWN_STOP"
        if completed.returncode == 0 and result["accepted"] is True and result["code"] == "accepted":
            return "IMPORT_ACCEPTED_NOT_COMMITTED"
        if completed.returncode == 2 and result["accepted"] is False:
            return "IMPORT_REJECTED_STOP"
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError):
        pass
    return "UNKNOWN_STOP"


def once(
    target: str,
    container: str,
    baseline_path: Path,
    baseline_sha256: str,
    claim_dir: Path,
    *,
    runner: Runner = subprocess.run,
    read_qr: Callable[[], str] = capture_private_qr,
    confirm: Callable[[str], bool],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> str:
    _target(target)
    if not CONTAINER.fullmatch(container):
        reject("MANAGER_CONTAINER_INVALID")
    baseline = read_private_baseline(baseline_path, baseline_sha256)
    payload = read_qr()
    if not isinstance(payload, str):
        reject("INVALID_QR")
    first = _read_pending(target, container, runner)
    binding = bind_terminal_projection(payload, first, baseline, clock())
    _require_authorization(claim_dir, binding, container, clock())
    if not confirm(binding.pairing_sha256[:12]):
        reject("OPERATOR_DID_NOT_CONFIRM")
    second = _read_pending(target, container, runner)
    again = bind_terminal_projection(payload, second, baseline, clock())
    if (
        again.hardware_sha256 != binding.hardware_sha256
        or again.pairing_sha256 != binding.pairing_sha256
        or again.expires_at != binding.expires_at
    ):
        reject("PENDING_CHANGED")
    _require_authorization(claim_dir, again, container, clock())
    _private_claim(claim_dir, binding.hardware_sha256, binding.pairing_sha256, clock())
    return _deliver(target, container, payload, runner)


def _authorize_confirm(suffix: str) -> bool:
    with open("/dev/tty", "r+", encoding="ascii") as tty:
        tty.write("单独授权这一次 P4 导入。请输入 AUTHORIZE " + suffix + "：")
        tty.flush()
        return tty.readline(80).strip() == "AUTHORIZE " + suffix


def _confirm(suffix: str) -> bool:
    with open("/dev/tty", "r+", encoding="ascii") as tty:
        tty.write("确认本次唯一 Setup Secret 导入。请输入 IMPORT " + suffix + "：")
        tty.flush()
        return tty.readline(80).strip() == "IMPORT " + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="N3W P4 Terminal operator-once import")
    parser.add_argument("--phase", choices=("authorize", "import"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--manager-container", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--claim-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.phase == "authorize":
            result = authorize(
                args.target, args.manager_container, args.baseline, args.baseline_sha256,
                args.claim_dir, confirm=_authorize_confirm,
            )
        else:
            result = once(
                args.target, args.manager_container, args.baseline, args.baseline_sha256,
                args.claim_dir, confirm=_confirm,
            )
        print(result)
        return 0 if result in {
            "AUTHORIZATION_RECORDED_NOT_IMPORTED",
            "IMPORT_ACCEPTED_NOT_COMMITTED",
        } else 2
    except (GateStop, OSError, ValueError, UnicodeError):
        print("P4_TERMINAL_IMPORT=STOP")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
