from __future__ import annotations

import hashlib
import io
import re
import shlex
import subprocess
import sys
import tarfile
import urllib.request

SOURCE_HEAD = "fd98c06d02037cba4f18043afeac62cd75893108"
REPO = "chrenguo-stack/HomeAssistant"
DIRECTORY = "tools/execution_packages/n3w/p4_manager_cold_backup"
EXPECTED = {
    "cold_snapshot.py": "8d779dbde033a2f2630a4fdec67570e35aeffc01",
    "business_snapshot.py": "b25940257ce4bdca6612085c71a5b1a1c9307bdc",
    "controlled_window.py": "dc9e9b4658d8cf4d265b31c27a90ff9d143d77de",
    "cutover_contract.py": "810f785378dbe4f928ab84aa1a18d3b754dabcac",
    "fresh_state_contract.py": "f05e54644b954087544e99c15e030d3aefea7b8f",
    "fresh_manager_deploy.py": "d07e119f83ed6c76789f6c4de277e33b65b80dad",
    "fresh_manager_recovery.py": "28426a313ed53d4a3fa6cc9f4bbd5fa618e08ab3",
    "fresh_manager_operator.py": "97232c7df5fe14c61ffed8facfe522ad4a3d802c",
    "fresh_manager_systemd_unit.py": "4a7a5950aff578382db09846f41cecbc0262a5cb",
}
MAX_REMOTE_SECONDS = 600

REMOTE_CODE = r"""
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

EXPECTED = __EXPECTED__
NEEDED = {
    "manager-inspect-private.json",
    "broker-inspect-private.json",
    "old-manager-image.tar",
    "old-manager-image.tar.sha256",
    "cold-snapshot-manifest-private.json",
    "p4-business-restore-evidence-private.json",
}
STAGE_NAME = "p4-fresh-manager-deploy-r2"
AUTH = "N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY"

def stop(code):
    print("T1_FRESH_MANAGER=STOP:" + code, flush=True)
    sys.exit(1)

def git_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def locate_private():
    matches = []
    visited = 0
    for root, directories, files in os.walk("/root", topdown=True, followlinks=False):
        visited += 1
        if visited > 6000:
            stop("R5_PRIVATE_DISCOVERY_LIMIT")
        depth = len(Path(root).parts) - len(Path("/root").parts)
        if depth > 7:
            directories[:] = []
            continue
        directories[:] = [
            d for d in directories
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", "venv")
            and not (Path(root) / d).is_symlink()
        ]
        if not NEEDED.issubset(set(files)):
            continue
        p = Path(root)
        if p.is_symlink() or stat.S_IMODE(p.stat().st_mode) != 0o700:
            continue
        if not re.fullmatch(r"/[A-Za-z0-9_./+-]+", str(p)):
            continue
        for name in NEEDED:
            q = p / name
            if not q.is_file() or q.is_symlink() or stat.S_IMODE(q.stat().st_mode) != 0o600:
                break
        else:
            matches.append(p)
    if len(matches) != 1:
        stop("R5_PRIVATE_AUTHORITY_NOT_UNIQUE")
    return matches[0]

def run_operator(script, private, args, seconds):
    command = [sys.executable, "-B", str(script), *args, "--private-root", str(private)]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        stop("OPERATOR_TIMEOUT_STATE_UNKNOWN_NO_RETRY")
    if result.returncode != 0:
        found = re.findall(r"P4_FRESH_MANAGER_OPERATOR=STOP:([A-Z0-9_]+)", result.stderr)
        stop(found[-1] if found else "OPERATOR_ERROR_CHECK_ROOT_PRIVATE_STATUS_NO_RETRY")
    return result.stdout

def main():
    if os.geteuid() != 0:
        stop("ROOT_REQUIRED")
    received = {}
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as stream:
            for member in stream:
                if member.name not in EXPECTED or member.name in received or not member.isfile():
                    stop("UNEXPECTED_STAGE_MEMBER")
                if member.size > 150000:
                    stop("OVERSIZED_STAGE_MEMBER")
                data = stream.extractfile(member).read()
                if len(data) != member.size or git_sha(data) != EXPECTED[member.name]:
                    stop("STAGE_BLOB_MISMATCH")
                received[member.name] = data
    except (OSError, ValueError, tarfile.TarError):
        stop("STAGE_ARCHIVE_INVALID")
    if set(received) != set(EXPECTED):
        stop("STAGE_FILE_SET_INCOMPLETE")
    private = locate_private()
    stage = private / STAGE_NAME
    if stage.exists() or stage.is_symlink():
        stop("STAGE_ALREADY_EXISTS_NO_RETRY")
    os.umask(0o077)
    stage.mkdir(mode=0o700)
    for name, data in received.items():
        target = stage / name
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    directory_fd = os.open(stage, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    operator = stage / "fresh_manager_operator.py"
    preflight = run_operator(operator, private, ["preflight"], 120)
    if "FRESH_MANAGER_PRECHECKS=PASS" not in preflight or "LIVE_MANAGER_REPLACEMENT_NOT_STARTED=true" not in preflight:
        stop("PREFLIGHT_RESULT_INCOMPLETE")
    outcome = run_operator(
        operator, private,
        ["execute", "--authorization-id", AUTH, "--permit-live-manager-replacement"],
        530,
    )
    if "FRESH_MANAGER_ONE_SHOT_DEPLOYMENT=PASS" not in outcome:
        stop("EXECUTION_PASS_NOT_PROVEN")
    if "FRESH_MANAGER_PREBOOT_BASELINE=0_0_0_AND_EMPTY_RELAY_KEYS" not in outcome:
        stop("FRESH_ZERO_BASELINE_NOT_PROVEN")
    print("T1_FRESH_MANAGER=PASS", flush=True)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        stop("STAGING_OR_REMOTE_EXECUTION_ERROR")
"""

def git_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fetch_scripts() -> dict[str, bytes]:
    result = {}
    for name, expected in EXPECTED.items():
        url = (
            "https://raw.githubusercontent.com/"
            + REPO + "/" + SOURCE_HEAD + "/" + DIRECTORY + "/" + name
        )
        with urllib.request.urlopen(url, timeout=25) as response:
            data = response.read(150001)
        if len(data) > 150000 or git_sha(data) != expected:
            raise RuntimeError("SOURCE_BLOB_MISMATCH")
        result[name] = data
    return result


def pack_files(files: dict[str, bytes]) -> bytes:
    if set(files) != set(EXPECTED):
        raise RuntimeError("SOURCE_SET_MISMATCH")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as out:
        for name in sorted(EXPECTED):
            data = files[name]
            if git_sha(data) != EXPECTED[name]:
                raise RuntimeError("SOURCE_BLOB_MISMATCH")
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            member.uid = 0
            member.gid = 0
            member.mtime = 0
            out.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


def validate_target(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.@:-]{1,180}", value):
        raise RuntimeError("SSH_TARGET_INVALID")
    if value.startswith("-") or value.count("@") > 1 or value.endswith("@"):
        raise RuntimeError("SSH_TARGET_INVALID")
    return value


def execute(target: str, archive: bytes) -> str:
    program = REMOTE_CODE.replace("__EXPECTED__", repr(EXPECTED))
    command = [
        "ssh", "-o", "ConnectTimeout=12", "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        target, "sudo -n python3 -c " + shlex.quote(program),
    ]
    try:
        result = subprocess.run(
            command, input=archive, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=MAX_REMOTE_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        return "T1_FRESH_MANAGER=STOP:SSH_TIMEOUT_STATE_UNKNOWN_NO_RETRY"
    output = result.stdout.decode("utf-8", errors="replace")
    match = re.findall(r"T1_FRESH_MANAGER=(?:PASS|STOP:[A-Z0-9_]+)", output)
    if result.returncode == 0 and match and match[-1] == "T1_FRESH_MANAGER=PASS":
        return "T1_FRESH_MANAGER=PASS"
    if match:
        return match[-1]
    return "T1_FRESH_MANAGER=STOP:SSH_OR_SUDO_FAILED_NO_RETRY"


def main() -> None:
    try:
        if len(sys.argv) > 2:
            raise RuntimeError("ARGUMENT_COUNT_INVALID")
        target = validate_target(
            sys.argv[1] if len(sys.argv) == 2 else input("T1 SSH 目标 (user@host 或已配置的别名): ").strip()
        )
        archive = pack_files(fetch_scripts())
        print("SOURCE_EXACT_NINE_FILES=PASS", flush=True)
        print("R5_PRIVATE_AND_LIVE_PREFLIGHT=AUTOMATED", flush=True)
        outcome = execute(target, archive)
        print(outcome, flush=True)
        if outcome != "T1_FRESH_MANAGER=PASS":
            raise SystemExit(1)
    except (RuntimeError, OSError, ValueError, urllib.error.URLError):
        print("T1_FRESH_MANAGER=STOP:MAC_SOURCE_OR_TARGET_PREFLIGHT_FAILED", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
