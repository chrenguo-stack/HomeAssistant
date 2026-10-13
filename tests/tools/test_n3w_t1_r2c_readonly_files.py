from __future__ import annotations

import os
from pathlib import Path

import pytest
from n3w_t1_r2c_readonly_files import (
    ReadonlyEvidenceError,
    inspect_metadata,
    read_bounded_text,
)


def test_reads_only_bounded_regular_file(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "os-release").write_bytes(b"ID=ubuntu\n")
    assert read_bounded_text(str(tmp_path), "etc/os-release") == b"ID=ubuntu\n"
    assert inspect_metadata(str(tmp_path), "etc/os-release")["kind"] == "regular"
    assert inspect_metadata(str(tmp_path), "etc/missing")["status"] == "ABSENT"


def test_blocks_traversal_and_absolute_path(tmp_path: Path) -> None:
    for target in (
        "../etc/passwd",
        "/etc/passwd",
        "etc/../passwd",
        "etc//passwd",
        "./etc/passwd",
    ):
        with pytest.raises(ReadonlyEvidenceError):
            read_bounded_text(str(tmp_path), target)


def test_blocks_file_and_parent_symlinks(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "target").write_text("private")
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    (tmp_path / "real" / "alias").symlink_to(tmp_path / "real" / "target")
    with pytest.raises(OSError):
        read_bounded_text(str(tmp_path), "link/target")
    with pytest.raises(OSError):
        read_bounded_text(str(tmp_path), "real/alias")
    assert inspect_metadata(str(tmp_path), "real/alias")["kind"] == "symlink"


def test_rejects_large_file_and_fifo(tmp_path: Path) -> None:
    (tmp_path / "large").write_bytes(b"x" * 16)
    with pytest.raises(ReadonlyEvidenceError, match="file_too_large"):
        read_bounded_text(str(tmp_path), "large", limit=4)
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(ReadonlyEvidenceError, match="not_regular_file"):
        read_bounded_text(str(tmp_path), "pipe")


def test_rejects_invalid_limit(tmp_path: Path) -> None:
    with pytest.raises(ReadonlyEvidenceError):
        read_bounded_text(str(tmp_path), "anything", 0)
