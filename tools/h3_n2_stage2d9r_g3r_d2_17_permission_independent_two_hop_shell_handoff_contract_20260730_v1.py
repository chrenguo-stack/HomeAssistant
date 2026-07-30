#!/usr/bin/env python3
"""Verified permission-independent two-hop POSIX shell handoff contract."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


class VerifiedTwoHopShellHandoffError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_regular_verified_file(path: Path, expected_sha256: str, *, label: str) -> Path:
    if path.is_symlink():
        raise VerifiedTwoHopShellHandoffError(f"{label}_NOT_REGULAR")
    path = path.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise VerifiedTwoHopShellHandoffError(f"{label}_NOT_REGULAR")
    if sha256_file(path) != expected_sha256:
        raise VerifiedTwoHopShellHandoffError(f"{label}_DIGEST_DRIFT")
    return path


def require_package_root(package_root: Path) -> Path:
    if package_root.is_symlink():
        raise VerifiedTwoHopShellHandoffError("PACKAGE_ROOT_NOT_DIRECTORY")
    package_root = package_root.resolve(strict=True)
    if not package_root.is_dir() or package_root.is_symlink():
        raise VerifiedTwoHopShellHandoffError("PACKAGE_ROOT_NOT_DIRECTORY")
    return package_root


def require_shell(shell: Path = Path("/bin/sh")) -> Path:
    shell = shell.resolve(strict=True)
    if not shell.is_file() or shell.is_symlink() or not os.access(shell, os.X_OK):
        raise VerifiedTwoHopShellHandoffError("POSIX_SHELL_INVALID")
    return shell


def build_environment(base_env: Mapping[str, str], *, package_root: Path, delivery_profile: str) -> dict[str, str]:
    package_root = require_package_root(package_root)
    env = dict(base_env)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GH_D2_17_OUTER_PACKAGE_ROOT"] = package_root.as_posix()
    env["GH_D2_17_DELIVERY_PROFILE"] = delivery_profile
    return env


def build_two_hop_command(
    *,
    package_root: Path,
    outer_name: str,
    outer_sha256: str,
    inner_name: str,
    inner_sha256: str,
    arguments: Sequence[str],
    shell: Path = Path("/bin/sh"),
) -> list[str]:
    package_root = require_package_root(package_root)
    outer = require_regular_verified_file(package_root / outer_name, outer_sha256, label="CANONICAL_OUTER")
    inner = require_regular_verified_file(package_root / inner_name, inner_sha256, label="INNER_LAUNCHER")
    if outer.parent != package_root or inner.parent != package_root:
        raise VerifiedTwoHopShellHandoffError("SHELL_HANDOFF_PATH_ESCAPE")
    verified_shell = require_shell(shell)
    return [str(verified_shell), str(inner), *[str(value) for value in arguments]]


def run_two_hop(
    *,
    package_root: Path,
    outer_name: str,
    outer_sha256: str,
    inner_name: str,
    inner_sha256: str,
    arguments: Sequence[str],
    delivery_profile: str,
    shell: Path = Path("/bin/sh"),
    env: Mapping[str, str] | None = None,
    stdin=None,
    stdout=None,
    stderr=None,
) -> subprocess.CompletedProcess[bytes]:
    command = build_two_hop_command(
        package_root=package_root,
        outer_name=outer_name,
        outer_sha256=outer_sha256,
        inner_name=inner_name,
        inner_sha256=inner_sha256,
        arguments=arguments,
        shell=shell,
    )
    effective_env = build_environment(
        os.environ if env is None else env,
        package_root=package_root,
        delivery_profile=delivery_profile,
    )
    return subprocess.run(command, env=effective_env, stdin=stdin, stdout=stdout, stderr=stderr, check=False)
