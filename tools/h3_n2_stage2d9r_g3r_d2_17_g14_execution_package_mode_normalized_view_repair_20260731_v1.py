#!/usr/bin/env python3
"""Host-only G14 repair for the inherited execution-package file-mode contract."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any


class RepairError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RepairError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def parse_flat_sums(root: Path) -> dict[str, str]:
    sums = root / "SHA256SUMS"
    require(sums.is_file() and not sums.is_symlink(), "G14_PACKAGE_SUMS_INVALID")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        require(len(parts) == 2, "G14_PACKAGE_SUMS_INVALID")
        digest, name = parts
        require(
            len(digest) == 64
            and all(ch in "0123456789abcdef" for ch in digest)
            and name not in expected
            and "/" not in name
            and name not in {"", "SHA256SUMS"},
            "G14_PACKAGE_SUMS_INVALID",
        )
        expected[name] = digest
    return expected


def inspect_exact_mode_contract(
    canonical_builder_source: str, inherited_successor_source: str
) -> dict[str, Any]:
    builder_shell_mode = (
        "448 if name.endswith('.sh') else 384" in canonical_builder_source
        or '448 if name.endswith(".sh") else 384' in canonical_builder_source
    )
    inherited_all_files_0600 = (
        'regular(path, "0600", "PACKAGE_FILE_INVALID")'
        in inherited_successor_source
        or "regular(path, '0600', 'PACKAGE_FILE_INVALID')"
        in inherited_successor_source
    )
    require(builder_shell_mode, "G14_CANONICAL_BUILDER_SHELL_MODE_CONTRACT_NOT_FOUND")
    require(
        inherited_all_files_0600,
        "G14_INHERITED_PRECLAIM_ALL_FILES_0600_CONTRACT_NOT_FOUND",
    )
    return {
        "conflict_confirmed": True,
        "canonical_builder_shell_mode": "0700",
        "inherited_preclaim_required_mode": "0600",
        "failure_code": "PACKAGE_FILE_INVALID",
        "conflicting_files": [
            "run_d2_17_canonical_delivery_outer_20260730_v1.sh",
            "run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh",
        ],
        "physical_operation": False,
    }


def _copy_regular_0600(source: Path, target: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "G14_SOURCE_MEMBER_INVALID")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with source.open("rb") as input_handle, os.fdopen(
            fd, "wb", closefd=False
        ) as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
            output_handle.flush()
            os.fsync(output_handle.fileno())
    finally:
        os.close(fd)
    os.chmod(target, 0o600)


def validate_content_equivalence(source: Path, view: Path) -> dict[str, Any]:
    source_files = sorted(path.name for path in source.iterdir())
    view_files = sorted(path.name for path in view.iterdir())
    require(source_files == view_files, "G14_EXECUTION_VIEW_INVENTORY_DRIFT")
    for name in source_files:
        left = source / name
        right = view / name
        require(
            left.is_file()
            and not left.is_symlink()
            and right.is_file()
            and not right.is_symlink(),
            "G14_EXECUTION_VIEW_MEMBER_INVALID",
        )
        require(
            sha256_file(left) == sha256_file(right),
            "G14_EXECUTION_VIEW_CONTENT_DRIFT:" + name,
        )
        require(file_mode(right) == "0600", "G14_EXECUTION_VIEW_MODE_DRIFT:" + name)
    return {
        "content_equivalent": True,
        "all_view_files_mode_0600": True,
        "file_count": len(source_files),
        "physical_operation": False,
    }


def create_mode_normalized_execution_view(source: Path, target: Path) -> dict[str, Any]:
    source = source.expanduser().resolve(strict=True)
    require(source.is_dir() and not source.is_symlink(), "G14_SOURCE_ROOT_INVALID")
    require(not target.exists() and not target.is_symlink(), "G14_TARGET_ROOT_ALREADY_EXISTS")
    members = sorted(source.iterdir(), key=lambda path: path.name)
    require(bool(members), "G14_SOURCE_ROOT_EMPTY")
    require(
        all(path.is_file() and not path.is_symlink() for path in members),
        "G14_SOURCE_MEMBER_INVALID",
    )
    expected = parse_flat_sums(source)
    observed = {path.name for path in members if path.name != "SHA256SUMS"}
    require(set(expected) == observed, "G14_PACKAGE_SUMS_COVERAGE_DRIFT")
    for name, digest in expected.items():
        require(
            sha256_file(source / name) == digest,
            "G14_SOURCE_MEMBER_DIGEST_DRIFT:" + name,
        )

    target.mkdir(parents=True, mode=0o700)
    os.chmod(target, 0o700)
    try:
        for member in members:
            _copy_regular_0600(member, target / member.name)
        report = validate_content_equivalence(source, target)
        parsed_view = parse_flat_sums(target)
        require(parsed_view == expected, "G14_EXECUTION_VIEW_SUMS_DRIFT")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    shell_modes_before = {
        name: file_mode(source / name)
        for name in (
            "run_d2_17_canonical_delivery_outer_20260730_v1.sh",
            "run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh",
        )
        if (source / name).exists()
    }
    report.update(
        {
            "ready_for_inherited_preclaim": True,
            "canonical_source_mutated": False,
            "view_root_mode": "0700",
            "shell_modes_before": shell_modes_before,
            "shell_modes_in_view": {name: "0600" for name in shell_modes_before},
            "replay_permitted": False,
        }
    )
    return report
