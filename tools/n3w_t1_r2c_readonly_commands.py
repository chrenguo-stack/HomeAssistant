from __future__ import annotations

import os
import re
import selectors
import shutil
import stat
import subprocess
import time
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePosixPath

SAFE_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
SAFE_DIRS = ("/usr/sbin", "/usr/bin", "/sbin", "/bin")
MAX_COMMAND_OUTPUT_BYTES = 256 * 1024
COMMAND_TIMEOUT_SECONDS = 10.0
PACKAGE_QUERY_FORMAT = "${binary:Package}\\t${Version}\\t${Architecture}\\n"
PACKAGE_SET = ("systemd", "openssh-server", "network-manager", "netplan.io")
SYSTEMCTL_PROPERTIES = (
    "Id,Names,LoadState,FragmentPath,DropInPaths,UnitFileState,ActiveState,SubState,"
    "Before,After,Wants,Requires,ConditionResult,Conditions,ExecStart,ExecStartPre,"
    "ExecStartPost,TriggeredBy,Triggers,ActiveEnterTimestampMonotonic,"
    "InactiveExitTimestampMonotonic"
)
PACKAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]*(?::[A-Za-z0-9_-]+)?\Z")
UNIT_RE = re.compile(
    r"[A-Za-z0-9_.@:-]+\.(?:service|socket|target|mount|path|timer)\Z"
)


class ReadonlyCommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    executable: str
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes


def _approved_path(value: str, approved_paths: Collection[str]) -> str:
    path = PurePosixPath(value)
    if not value or not path.is_absolute() or str(path) != value or "\x00" in value:
        raise ReadonlyCommandError("invalid_approved_path")
    if value not in approved_paths:
        raise ReadonlyCommandError("unapproved_path")
    return value


def _approved_package(value: str, approved_packages: Collection[str]) -> str:
    if not PACKAGE_RE.fullmatch(value):
        raise ReadonlyCommandError("invalid_package")
    if value not in approved_packages:
        raise ReadonlyCommandError("unapproved_package")
    return value


def _approved_unit(value: str, approved_units: Collection[str]) -> str:
    if not UNIT_RE.fullmatch(value):
        raise ReadonlyCommandError("invalid_unit")
    if value not in approved_units:
        raise ReadonlyCommandError("unapproved_unit")
    return value


def build_contract_argv(
    command_id: str,
    *,
    value: str | None = None,
    approved_paths: Collection[str] = (),
    approved_packages: Collection[str] = (),
    approved_units: Collection[str] = (),
) -> tuple[str, ...]:
    fixed = {
        "C1_SYSTEMD": ("systemd", "--version"),
        "C1_ARCH": ("uname", "-m"),
        "C2_PYTHON": ("python3", "-B", "--version"),
        "C3_PACKAGES": (
            "dpkg-query",
            "-W",
            f"-f={PACKAGE_QUERY_FORMAT}",
            *PACKAGE_SET,
        ),
        "C5_MACHINE_ID_MOUNT": (
            "findmnt",
            "--noheadings",
            "--mountpoint",
            "/etc/machine-id",
            "--output",
            "TARGET,FSTYPE,OPTIONS",
        ),
        "C6_LISTEN": ("ss", "-H", "-ltn"),
    }
    if command_id in fixed:
        if value is not None:
            raise ReadonlyCommandError("unexpected_dynamic_value")
        return fixed[command_id]
    if value is None:
        raise ReadonlyCommandError("missing_dynamic_value")
    if command_id == "C3_OWNER":
        return ("dpkg-query", "-S", _approved_path(value, approved_paths))
    if command_id == "C3_LIST":
        return (
            "dpkg-query",
            "-L",
            _approved_package(value, approved_packages),
        )
    if command_id == "C4_UNIT":
        unit = _approved_unit(value, approved_units)
        return (
            "systemctl",
            "--no-pager",
            "show",
            unit,
            f"--property={SYSTEMCTL_PROPERTIES}",
        )
    raise ReadonlyCommandError("unknown_command_id")


def resolve_executable(name: str) -> str:
    if not name or "/" in name or "\x00" in name:
        raise ReadonlyCommandError("invalid_executable_name")
    found = shutil.which(name, path=SAFE_PATH)
    if found is None:
        raise ReadonlyCommandError("executable_not_found")
    resolved = os.path.realpath(found)
    if not any(
        resolved == root or resolved.startswith(root + "/") for root in SAFE_DIRS
    ):
        raise ReadonlyCommandError("executable_outside_safe_path")
    metadata = os.stat(resolved)
    if not stat.S_ISREG(metadata.st_mode) or not os.access(resolved, os.X_OK):
        raise ReadonlyCommandError("executable_not_regular")
    return resolved


def _kill(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
    process.wait()


def _run_bounded(
    executable: str,
    argv: tuple[str, ...],
    *,
    timeout_seconds: float,
    output_limit: int,
) -> CommandResult:
    if not (0 < timeout_seconds <= COMMAND_TIMEOUT_SECONDS):
        raise ReadonlyCommandError("invalid_timeout")
    if not (0 < output_limit <= MAX_COMMAND_OUTPUT_BYTES):
        raise ReadonlyCommandError("invalid_output_limit")
    environment = {
        "PATH": SAFE_PATH,
        "LANG": "C",
        "LC_ALL": "C",
        "SYSTEMD_COLORS": "0",
    }
    process = subprocess.Popen(
        (executable, *argv[1:]),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        close_fds=True,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    streams = {
        process.stdout.fileno(): "stdout",
        process.stderr.fileno(): "stderr",
    }
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill(process)
                raise ReadonlyCommandError("command_timeout")
            for key, _ in selector.select(min(0.1, remaining)):
                descriptor = key.fileobj.fileno()
                data = os.read(descriptor, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffers[streams[descriptor]].extend(data)
                if len(buffers["stdout"]) + len(buffers["stderr"]) > output_limit:
                    _kill(process)
                    raise ReadonlyCommandError("command_output_limit")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill(process)
            raise ReadonlyCommandError("command_timeout")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            _kill(process)
            raise ReadonlyCommandError("command_timeout") from error
    except BaseException:
        if process.poll() is None:
            _kill(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return CommandResult(
        executable=executable,
        argv=argv,
        returncode=returncode,
        stdout=bytes(buffers["stdout"]),
        stderr=bytes(buffers["stderr"]),
    )


def run_contract_command(
    command_id: str,
    *,
    value: str | None = None,
    approved_paths: Collection[str] = (),
    approved_packages: Collection[str] = (),
    approved_units: Collection[str] = (),
    timeout_seconds: float = COMMAND_TIMEOUT_SECONDS,
    output_limit: int = MAX_COMMAND_OUTPUT_BYTES,
) -> CommandResult:
    argv = build_contract_argv(
        command_id,
        value=value,
        approved_paths=approved_paths,
        approved_packages=approved_packages,
        approved_units=approved_units,
    )
    executable = resolve_executable(argv[0])
    return _run_bounded(
        executable,
        argv,
        timeout_seconds=timeout_seconds,
        output_limit=output_limit,
    )
