from __future__ import annotations

import os
import stat
from collections import deque
from pathlib import PurePosixPath
from typing import Any

MAX_TEXT_BYTES = 1024 * 1024


class ReadonlyEvidenceError(RuntimeError):
    pass


def _parts(relative: str) -> tuple[str, ...]:
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or any(piece in ('', '.', '..') for piece in relative.split('/')):
        raise ReadonlyEvidenceError('invalid_relative_path')
    return path.parts


def _same(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns,
        before.st_ctime_ns,
    ) == (
        after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns,
        after.st_ctime_ns,
    )


def _open_parent(root: str, relative: str) -> tuple[int, str]:
    pieces = _parts(relative)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for piece in pieces[:-1]:
            nxt = os.open(piece, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd, pieces[-1]
    except BaseException:
        os.close(fd)
        raise


def inspect_metadata(root: str, relative: str) -> dict[str, Any]:
    parent, name = _open_parent(root, relative)
    try:
        try:
            value = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return {'status': 'ABSENT', 'kind': None, 'size': None}
        kind = 'regular' if stat.S_ISREG(value.st_mode) else 'symlink' if stat.S_ISLNK(value.st_mode) else 'directory' if stat.S_ISDIR(value.st_mode) else 'other'
        return {'status': 'OBSERVED', 'kind': kind, 'size': value.st_size if kind == 'regular' else None}
    finally:
        os.close(parent)


def read_bounded_text(root: str, relative: str, limit: int = MAX_TEXT_BYTES) -> bytes:
    if not isinstance(limit, int) or not (0 < limit <= MAX_TEXT_BYTES):
        raise ReadonlyEvidenceError('invalid_read_limit')
    parent, name = _open_parent(root, relative)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReadonlyEvidenceError('not_regular_file')
        if before.st_size > limit:
            raise ReadonlyEvidenceError('file_too_large')
        chunks = []
        remaining = limit + 1
        while remaining:
            block = os.read(descriptor, min(65536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        result = b''.join(chunks)
        after = os.fstat(descriptor)
        if len(result) > limit:
            raise ReadonlyEvidenceError('file_too_large')
        if not _same(before, after) or len(result) != before.st_size:
            raise ReadonlyEvidenceError('file_changed_during_read')
        return result
    finally:
        os.close(descriptor)


def read_symlink_target(root: str, relative: str) -> str:
    parent, name = _open_parent(root, relative)
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISLNK(metadata.st_mode):
            raise ReadonlyEvidenceError("not_symlink")
        return os.readlink(name, dir_fd=parent)
    finally:
        os.close(parent)


def scan_bounded(
    root: str,
    relative: str,
    *,
    max_depth: int,
    max_entries: int = 512,
) -> list[dict[str, Any]]:
    if not isinstance(max_depth, int) or not (0 <= max_depth <= 3):
        raise ReadonlyEvidenceError("invalid_scan_depth")
    if not isinstance(max_entries, int) or not (0 < max_entries <= 512):
        raise ReadonlyEvidenceError("invalid_scan_limit")

    start_parts = _parts(relative)
    root_fd = os.open(
        root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        current_fd = os.dup(root_fd)
        try:
            for piece in start_parts:
                next_fd = os.open(
                    piece,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=current_fd,
                )
                os.close(current_fd)
                current_fd = next_fd
            start_path = os.path.join(root, *start_parts)
        except BaseException:
            os.close(current_fd)
            raise
    finally:
        os.close(root_fd)

    result: list[dict[str, Any]] = []
    queue: deque[tuple[str, int, int]] = deque([(start_path, current_fd, 0)])
    try:
        while queue:
            current_path, directory_fd, depth = queue.popleft()
            try:
                with os.scandir(directory_fd) as entries:
                    ordered = sorted(entries, key=lambda item: item.name)
                for entry in ordered:
                    metadata = entry.stat(follow_symlinks=False)
                    mode = metadata.st_mode
                    kind = (
                        "regular"
                        if stat.S_ISREG(mode)
                        else "directory"
                        if stat.S_ISDIR(mode)
                        else "symlink"
                        if stat.S_ISLNK(mode)
                        else "other"
                    )
                    rel_path = os.path.relpath(
                        os.path.join(current_path, entry.name),
                        root,
                    )
                    result.append(
                        {
                            "relative": rel_path,
                            "kind": kind,
                            "mode": format(stat.S_IMODE(mode), "04o"),
                            "size": metadata.st_size if kind == "regular" else None,
                        }
                    )
                    if len(result) > max_entries:
                        raise ReadonlyEvidenceError("scan_entry_limit")
                    if kind == "directory" and depth < max_depth:
                        child_fd = os.open(
                            entry.name,
                            os.O_RDONLY
                            | os.O_DIRECTORY
                            | os.O_NOFOLLOW
                            | os.O_CLOEXEC,
                            dir_fd=directory_fd,
                        )
                        queue.append(
                            (
                                os.path.join(current_path, entry.name),
                                child_fd,
                                depth + 1,
                            )
                        )
            finally:
                os.close(directory_fd)
    except BaseException:
        while queue:
            _, fd, _ = queue.popleft()
            os.close(fd)
        raise
    return result
