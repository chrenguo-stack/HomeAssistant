from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .t1_manager_identity_migration_execution_preparation_constants import (
    SHA256,
    ManagerIdentityExecutionPreparationError,
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ManagerIdentityExecutionPreparationError(f"{label} SHA-256 is invalid")
    return value


def private_dir(path: Path, label: str, *, create: bool = False) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ManagerIdentityExecutionPreparationError(
            f"{label} is missing, unsafe, or not private"
        )
    return path.resolve()


def private_file(path: Path, label: str) -> Path:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise ManagerIdentityExecutionPreparationError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    return path.resolve()


def read_json(path: Path, label: str) -> dict[str, Any]:
    private_file(path, label)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityExecutionPreparationError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityExecutionPreparationError(f"{label} must be an object")
    return document


def must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise ManagerIdentityExecutionPreparationError(
                f"{label} verification failed: {field}"
            )


def safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ManagerIdentityExecutionPreparationError(f"{label} path is invalid")
    relative = PurePosixPath(value)
    if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
        raise ManagerIdentityExecutionPreparationError(f"{label} path is unsafe")
    return relative


def fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_private(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        fsync_dir(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    write_private(path, (canonical(value) + "\n").encode())


def record(path: Path, root: Path, *, contains_secret: bool) -> dict[str, object]:
    private_file(path, "execution preparation record")
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha_path(path),
        "size": path.stat().st_size,
        "mode": "0600",
        "contains_secret": contains_secret,
    }


def parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ManagerIdentityExecutionPreparationError(f"{label} is invalid")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ManagerIdentityExecutionPreparationError(f"{label} is invalid") from error
