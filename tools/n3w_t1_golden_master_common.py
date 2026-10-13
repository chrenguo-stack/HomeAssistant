from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

AUTHORIZATION_LEDGER_SCHEMA = "gh.n3w.t1-golden-master-authorization/1"
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")


class GoldenMasterCommonError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def public_tree_sha256(root: Path, *, excluded: frozenset[str] = frozenset()) -> str:
    if root.is_symlink() or not root.is_dir():
        raise GoldenMasterCommonError("public_tree_invalid")
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            raise GoldenMasterCommonError(f"public_tree_symlink_forbidden:{relative}")
        if not path.is_file():
            continue
        metadata = path.stat()
        records.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size": metadata.st_size,
                "mode": stat.S_IMODE(metadata.st_mode),
            }
        )
    return canonical_sha256(records)


def _validate_ledger_root(root: Path) -> None:
    if not root.is_absolute():
        raise GoldenMasterCommonError("authorization_ledger_root_not_absolute")
    if root.is_symlink():
        raise GoldenMasterCommonError("authorization_ledger_root_invalid")
    if not root.exists():
        return
    metadata = root.stat()
    if (
        not root.is_dir()
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise GoldenMasterCommonError("authorization_ledger_root_invalid")


def authorization_record_path(root: Path, authorization_id: str) -> Path:
    digest = hashlib.sha256(authorization_id.encode()).hexdigest()
    return root / f"{digest}.json"


def load_authorization_record(
    root: Path,
    authorization_id: str,
) -> dict[str, Any] | None:
    _validate_ledger_root(root)
    path = authorization_record_path(root, authorization_id)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise GoldenMasterCommonError("authorization_record_invalid")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise GoldenMasterCommonError("authorization_record_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GoldenMasterCommonError("authorization_record_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != AUTHORIZATION_LEDGER_SCHEMA
        or document.get("authorization_id") != authorization_id
        or document.get("operation") not in {"BUILD", "SEAL"}
        or _SHA40.fullmatch(str(document.get("source_head"))) is None
        or _SHA64.fullmatch(str(document.get("payload_manifest_sha256"))) is None
        or not isinstance(document.get("release_id"), str)
        or not document["release_id"]
    ):
        raise GoldenMasterCommonError("authorization_record_invalid")
    return document


def claim_authorization(
    root: Path,
    *,
    authorization_id: str,
    operation: str,
    source_head: str,
    payload_manifest_sha256: str,
    release_id: str,
) -> dict[str, Any]:
    if operation not in {"BUILD", "SEAL"}:
        raise GoldenMasterCommonError("authorization_operation_invalid")
    if _SHA40.fullmatch(source_head) is None:
        raise GoldenMasterCommonError("authorization_source_head_invalid")
    if _SHA64.fullmatch(payload_manifest_sha256) is None:
        raise GoldenMasterCommonError("authorization_payload_manifest_invalid")
    if not release_id:
        raise GoldenMasterCommonError("authorization_release_id_invalid")

    _validate_ledger_root(root)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    root.chmod(0o700)
    _validate_ledger_root(root)
    if load_authorization_record(root, authorization_id) is not None:
        raise GoldenMasterCommonError("authorization_already_consumed")

    document = {
        "schema": AUTHORIZATION_LEDGER_SCHEMA,
        "authorization_id": authorization_id,
        "operation": operation,
        "source_head": source_head,
        "payload_manifest_sha256": payload_manifest_sha256,
        "release_id": release_id,
    }
    payload = (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    path = authorization_record_path(root, authorization_id)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise GoldenMasterCommonError("authorization_already_consumed") from error
    try:
        os.fchmod(descriptor, 0o600)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise GoldenMasterCommonError("authorization_record_invalid")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    return document
