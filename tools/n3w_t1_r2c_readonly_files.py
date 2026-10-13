from __future__ import annotations

import os
import stat
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
