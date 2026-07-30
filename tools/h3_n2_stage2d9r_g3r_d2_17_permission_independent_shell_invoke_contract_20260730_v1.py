#!/usr/bin/env python3
"""Permission-independent verified POSIX-shell invocation contract."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


class VerifiedShellInvokeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_verified_script(script: Path, expected_sha256: str) -> Path:
    if script.is_symlink():
        raise VerifiedShellInvokeError("VERIFIED_SHELL_SCRIPT_NOT_REGULAR")
    script = script.resolve(strict=True)
    if not script.is_file() or script.is_symlink():
        raise VerifiedShellInvokeError("VERIFIED_SHELL_SCRIPT_NOT_REGULAR")
    if sha256_file(script) != expected_sha256:
        raise VerifiedShellInvokeError("VERIFIED_SHELL_SCRIPT_DIGEST_DRIFT")
    return script


def require_shell(shell: Path = Path("/bin/sh")) -> Path:
    shell = shell.resolve(strict=True)
    if not shell.is_file() or shell.is_symlink() or not os.access(shell, os.X_OK):
        raise VerifiedShellInvokeError("POSIX_SHELL_INVALID")
    return shell


def build_command(
    script: Path,
    expected_sha256: str,
    arguments: Sequence[str],
    *,
    shell: Path = Path("/bin/sh"),
) -> list[str]:
    verified_script = require_verified_script(script, expected_sha256)
    verified_shell = require_shell(shell)
    return [str(verified_shell), str(verified_script), *[str(value) for value in arguments]]


def run_verified_script(
    script: Path,
    expected_sha256: str,
    arguments: Sequence[str],
    *,
    shell: Path = Path("/bin/sh"),
    env: Mapping[str, str] | None = None,
    stdin=None,
    stdout=None,
    stderr=None,
) -> subprocess.CompletedProcess[bytes]:
    command = build_command(script, expected_sha256, arguments, shell=shell)
    return subprocess.run(
        command,
        env=None if env is None else dict(env),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        check=False,
    )
