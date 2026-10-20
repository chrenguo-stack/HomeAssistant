#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from n3w_t1_production_v2_contract import (
    RUN_MARKER_SCHEMA,
    canonical_json_bytes,
    validate_marker,
)

DEFAULT_MARKER_PATH = Path("/var/lib/n3w-production/run.json")
BINDING_KEYS = (
    "run_id",
    "release_id",
    "release_sha256",
    "source_head",
    "target_binding_sha256",
    "ssh_host_key_sha256",
    "plan_sha256",
)


class ProductionMarkerError(RuntimeError):
    pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _authority_root_metadata(path: Path) -> os.stat_result:
    if path.is_symlink() or not path.is_dir():
        raise ProductionMarkerError("marker_parent_invalid")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise ProductionMarkerError("marker_parent_owner_invalid")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ProductionMarkerError("marker_parent_mode_invalid")
    return metadata


def _ensure_parent(path: Path) -> None:
    parent = path.parent
    if parent.exists() or parent.is_symlink():
        _authority_root_metadata(parent)
        return
    grandparent = parent.parent
    if not grandparent.is_dir() or grandparent.is_symlink():
        raise ProductionMarkerError("marker_parent_base_invalid")
    parent.mkdir(mode=0o700)
    os.chmod(parent, 0o700, follow_symlinks=False)
    _fsync_directory(grandparent)
    _authority_root_metadata(parent)


def _marker_metadata(path: Path) -> os.stat_result:
    if path.is_symlink() or not path.is_file():
        raise ProductionMarkerError("marker_file_invalid")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ProductionMarkerError("marker_mode_invalid")
    if metadata.st_uid != os.geteuid():
        raise ProductionMarkerError("marker_owner_invalid")
    return metadata


def read_marker(path: Path = DEFAULT_MARKER_PATH) -> dict[str, Any]:
    _marker_metadata(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionMarkerError("marker_document_invalid") from error
    try:
        return validate_marker(document)
    except Exception as error:
        raise ProductionMarkerError("marker_contract_invalid") from error


def marker_sha256(path: Path = DEFAULT_MARKER_PATH) -> str:
    _marker_metadata(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_marker(path: Path = DEFAULT_MARKER_PATH) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {
            "schema": RUN_MARKER_SCHEMA,
            "status": "ABSENT",
            "path": str(path),
        }
    marker = read_marker(path)
    return {
        "schema": RUN_MARKER_SCHEMA,
        "status": "PRESENT",
        "state": marker["state"],
        "run_id": marker["run_id"],
        "release_id": marker["release_id"],
        "source_head": marker["source_head"],
        "target_binding_sha256": marker["target_binding_sha256"],
        "marker_sha256": marker_sha256(path),
        "replay_allowed": False,
        "T1_PRODUCTION_READY": marker.get("T1_PRODUCTION_READY", False),
    }


def _write_temp(parent: Path, payload: bytes) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=".run.", suffix=".tmp", dir=parent)
    temp = Path(raw_path)
    try:
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
    except Exception:
        os.close(descriptor)
        temp.unlink(missing_ok=True)
        raise
    os.close(descriptor)
    return temp


def _atomic_create(path: Path, payload: bytes) -> None:
    _ensure_parent(path)
    if path.exists() or path.is_symlink():
        raise ProductionMarkerError("marker_already_exists")
    temp = _write_temp(path.parent, payload)
    try:
        try:
            os.link(temp, path, follow_symlinks=False)
        except FileExistsError as error:
            raise ProductionMarkerError("marker_already_exists") from error
        os.chmod(path, 0o600, follow_symlinks=False)
        temp.unlink()
        _fsync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_replace(path: Path, payload: bytes) -> None:
    _marker_metadata(path)
    temp = _write_temp(path.parent, payload)
    try:
        os.replace(temp, path)
        os.chmod(path, 0o600, follow_symlinks=False)
        _fsync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def start_marker(
    path: Path,
    binding: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    if set(binding) != set(BINDING_KEYS):
        raise ProductionMarkerError("marker_binding_keys_invalid")
    marker = {
        "schema": RUN_MARKER_SCHEMA,
        **binding,
        "state": "STARTED",
        "replay_allowed": False,
        "created_at": created_at,
    }
    try:
        normalized = validate_marker(marker)
    except Exception as error:
        raise ProductionMarkerError("marker_start_contract_invalid") from error
    _atomic_create(path, canonical_json_bytes(normalized))
    return normalized


def accept_marker(
    path: Path,
    binding: dict[str, Any],
    *,
    acceptance_sha256: str,
    accepted_at: str,
) -> dict[str, Any]:
    if set(binding) != set(BINDING_KEYS):
        raise ProductionMarkerError("marker_binding_keys_invalid")
    current = read_marker(path)
    if current["state"] != "STARTED":
        raise ProductionMarkerError("marker_not_started")
    for key in BINDING_KEYS:
        if current[key] != binding[key]:
            raise ProductionMarkerError(f"marker_binding_mismatch:{key}")
    accepted = {
        **current,
        "state": "ACCEPTED",
        "acceptance_sha256": acceptance_sha256,
        "accepted_at": accepted_at,
        "T1_PRODUCTION_READY": True,
    }
    try:
        normalized = validate_marker(accepted)
    except Exception as error:
        raise ProductionMarkerError("marker_accept_contract_invalid") from error
    _atomic_replace(path, canonical_json_bytes(normalized))
    return normalized


def _add_binding_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--target-binding-sha256", required=True)
    parser.add_argument("--ssh-host-key-sha256", required=True)
    parser.add_argument("--plan-sha256", required=True)


def _binding(args: argparse.Namespace) -> dict[str, str]:
    return {key: getattr(args, key) for key in BINDING_KEYS}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--path", type=Path, default=DEFAULT_MARKER_PATH)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    start = commands.add_parser("start")
    _add_binding_arguments(start)
    start.add_argument("--created-at", required=True)
    accept = commands.add_parser("accept")
    _add_binding_arguments(accept)
    accept.add_argument("--acceptance-sha256", required=True)
    accept.add_argument("--accepted-at", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "inspect":
            result = inspect_marker(args.path)
        elif args.command == "start":
            result = start_marker(args.path, _binding(args), created_at=args.created_at)
        elif args.command == "accept":
            result = accept_marker(
                args.path,
                _binding(args),
                acceptance_sha256=args.acceptance_sha256,
                accepted_at=args.accepted_at,
            )
        else:
            raise ProductionMarkerError("marker_command_invalid")
    except ProductionMarkerError as error:
        print(json.dumps({"status": "STOP", "error_code": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
