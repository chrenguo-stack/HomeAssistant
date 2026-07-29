#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Iterable

FIXED_MTIME = 1785283200


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)


def write_json(path: Path, value: object) -> None:
    write_bytes(path, canonical_bytes(value) + b"\n")


def safe_name(name: str) -> str:
    pure = PurePosixPath(name)
    if not name or pure.is_absolute() or ".." in pure.parts:
        raise RuntimeError("UNSAFE_ARCHIVE_MEMBER")
    return pure.as_posix()


def copy_file(source: Path, target: Path, mode: int = 0o600) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("SOURCE_FILE_INVALID")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    os.chmod(target, mode)


def write_sums(root: Path, *, exclude: Iterable[str] = ("SHA256SUMS",)) -> None:
    excluded = set(exclude)
    names = sorted(path.name for path in root.iterdir() if path.is_file() and path.name not in excluded)
    data = "".join(f"{sha256_file(root / name)}  {name}\n" for name in names).encode("utf-8")
    write_bytes(root / "SHA256SUMS", data)


def deterministic_tar(root: Path, output: Path) -> int:
    files = sorted(path for path in root.rglob("*") if path.is_file() and path != output)
    with tarfile.open(output, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = archive.gettarinfo(str(path), arcname=relative)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = FIXED_MTIME
            info.mode = 0o700 if path.suffix == ".sh" or path.name.endswith("wrapper_20260729_v1.py") else 0o600
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    os.chmod(output, 0o600)
    return len(files)
