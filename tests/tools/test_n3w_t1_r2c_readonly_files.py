from __future__ import annotations

import os
from pathlib import Path

import pytest
from n3w_t1_r2c_readonly_files import (
    ReadonlyEvidenceError,
    inspect_metadata,
    read_bounded_text,
    read_symlink_target,
    scan_bounded,
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


def test_reads_symlink_target_without_following(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "target").write_text("data")
    (tmp_path / "etc" / "alias").symlink_to("target")
    assert read_symlink_target(str(tmp_path), "etc/alias") == "target"
    with pytest.raises(ReadonlyEvidenceError, match="not_symlink"):
        read_symlink_target(str(tmp_path), "etc/target")


def test_scan_bounded_does_not_follow_symlink_directories(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "nested").mkdir()
    (tmp_path / "state" / "nested" / "record").write_text("value")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "hidden").write_text("value")
    (tmp_path / "state" / "linked").symlink_to(
        tmp_path / "outside",
        target_is_directory=True,
    )
    records = scan_bounded(str(tmp_path), "state", max_depth=2)
    paths = {record["relative"]: record["kind"] for record in records}
    assert paths["state/nested"] == "directory"
    assert paths["state/nested/record"] == "regular"
    assert paths["state/linked"] == "symlink"
    assert "outside/hidden" not in paths


def test_scan_bounded_enforces_depth_and_entry_limits(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "a").write_text("a")
    (tmp_path / "state" / "b").write_text("b")
    with pytest.raises(ReadonlyEvidenceError, match="scan_entry_limit"):
        scan_bounded(str(tmp_path), "state", max_depth=1, max_entries=1)
    with pytest.raises(ReadonlyEvidenceError, match="invalid_scan_depth"):
        scan_bounded(str(tmp_path), "state", max_depth=4)
