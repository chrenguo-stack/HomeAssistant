from __future__ import annotations

import argparse
import ipaddress
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
    try:
        user, host = value.split("@", 1)
        address = ipaddress.IPv4Address(host)
        if user != "root" or not address.is_private or address.is_loopback:
            reject("TARGET_INVALID")
    except (ValueError, AttributeError):
        reject("TARGET_INVALID")
    return value


def _command(target: str, container: str, *, importer: bool) -> list[str]:
    _target(target)
    if not CONTAINER.fullmatch(container):
        reject("MANAGER_CONTAINER_INVALID")
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-T", target,
        "docker", "exec", "-i" if importer else "--",
        container,
        "greenhouse-manager-pairing" if importer else "greenhouse-manager-registration",
        "import-payload" if importer else "p4-pending-readonly",
        "--payload-stdin" if importer else "",
    ] if importer else [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-T", target,
        "docker", "exec", container,
        "greenhouse-manager-registration", "p4-pending-readonly",
    ]


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
            os.write(fd, json.dumps(doc, sort_keys=True).encode("ascii"))
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
    _private_claim(claim_dir, binding.hardware_sha256, binding.pairing_sha256, clock())
    return _deliver(target, container, payload, runner)


def _confirm(suffix: str) -> bool:
    with open("/dev/tty", "r+", encoding="ascii") as tty:
        tty.write("确认本次唯一 Setup Secret 导入。请输入 IMPORT " + suffix + "：")
        tty.flush()
        return tty.readline(80).strip() == "IMPORT " + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="N3W P4 Terminal operator-once import")
    parser.add_argument("--target", required=True)
    parser.add_argument("--manager-container", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--claim-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = once(
            args.target, args.manager_container, args.baseline, args.baseline_sha256,
            args.claim_dir, confirm=_confirm,
        )
        print(result)
        return 0 if result == "IMPORT_ACCEPTED_NOT_COMMITTED" else 2
    except (GateStop, OSError, ValueError, UnicodeError):
        print("P4_TERMINAL_IMPORT=STOP")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
