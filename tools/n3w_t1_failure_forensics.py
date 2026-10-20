#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from n3w_t1_production_v2_contract import FORENSIC_SCHEMA, canonical_json_bytes, canonical_sha256

FAILURE_SUMMARY = "failure-summary.json"
FORENSIC_SNAPSHOT = "forensic-snapshot.json"
EVIDENCE_MANIFEST = "evidence-manifest.json"


class FailureForensicsError(RuntimeError):
    pass


def _ensure_root(root: Path) -> Path:
    root = root.resolve()
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise FailureForensicsError("evidence_root_invalid")
    else:
        parent = root.parent
        if parent.is_symlink() or not parent.is_dir():
            raise FailureForensicsError("evidence_parent_invalid")
        root.mkdir(mode=0o700)
        _fsync_directory(parent)
    os.chmod(root, 0o700)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise FailureForensicsError("evidence_root_mode_invalid")
    return root


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, document: Any, *, refuse_existing: bool) -> None:
    root = _ensure_root(path.parent)
    if refuse_existing and (path.exists() or path.is_symlink()):
        raise FailureForensicsError(f"evidence_already_exists:{path.name}")
    payload = canonical_json_bytes(document)
    descriptor, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=root)
    temp = Path(raw_temp)
    try:
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if refuse_existing:
            try:
                os.link(temp, path, follow_symlinks=False)
            except FileExistsError as error:
                raise FailureForensicsError(f"evidence_already_exists:{path.name}") from error
            temp.unlink()
        else:
            os.replace(temp, path)
        os.chmod(path, 0o600, follow_symlinks=False)
        _fsync_directory(root)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temp.unlink(missing_ok=True)


def _load_private(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise FailureForensicsError(f"evidence_file_invalid:{path.name}")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise FailureForensicsError(f"evidence_mode_invalid:{path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FailureForensicsError(f"evidence_json_invalid:{path.name}") from error


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze_failure(root: Path, failure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(failure, Mapping) or not failure:
        raise FailureForensicsError("failure_summary_invalid")
    document = dict(failure)
    document["failure_frozen"] = True
    document["forensic_collector_target_mutation"] = False
    _atomic_private_write(root / FAILURE_SUMMARY, document, refuse_existing=True)
    return document


def collect_snapshot(
    root: Path,
    probes: Mapping[str, Callable[[], Any]],
) -> dict[str, Any]:
    if not (root / FAILURE_SUMMARY).is_file():
        raise FailureForensicsError("failure_must_be_frozen_first")
    if not isinstance(probes, Mapping) or not probes:
        raise FailureForensicsError("forensic_probes_invalid")
    records: dict[str, Any] = {}
    for name in sorted(probes):
        if not isinstance(name, str) or not name:
            raise FailureForensicsError("forensic_probe_name_invalid")
        probe = probes[name]
        if not callable(probe):
            raise FailureForensicsError(f"forensic_probe_invalid:{name}")
        try:
            value = probe()
            canonical_json_bytes(value)
            records[name] = {"status": "OBSERVED", "value": value}
        except Exception as error:
            records[name] = {
                "status": "UNAVAILABLE",
                "reason": type(error).__name__,
            }
    document = {
        "schema": FORENSIC_SCHEMA,
        "status": "COMPLETE",
        "probes": records,
        "read_only": True,
        "target_mutation": False,
    }
    _atomic_private_write(root / FORENSIC_SNAPSHOT, document, refuse_existing=True)
    return document


def build_manifest(root: Path) -> dict[str, Any]:
    failure_path = root / FAILURE_SUMMARY
    snapshot_path = root / FORENSIC_SNAPSHOT
    failure = _load_private(failure_path)
    snapshot = _load_private(snapshot_path)
    unavailable_count = sum(
        1
        for record in (snapshot.get("probes") or {}).values()
        if isinstance(record, dict) and record.get("status") == "UNAVAILABLE"
    )
    records = []
    for path in (failure_path, snapshot_path):
        records.append(
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha_file(path),
            }
        )
    manifest = {
        "schema": FORENSIC_SCHEMA,
        "FORENSIC_SNAPSHOT_COMPLETE": True,
        "NO_TARGET_MUTATION": True,
        "UNAVAILABLE_IS_EXPLICIT": True,
        "ORIGINAL_FAILURE_NOT_OVERWRITTEN": True,
        "BUNDLE_SHA256_PRESENT": True,
        "failure_frozen": failure.get("failure_frozen") is True,
        "unavailable_count": unavailable_count,
        "files": records,
        "bundle_sha256": canonical_sha256(records),
    }
    _atomic_private_write(root / EVIDENCE_MANIFEST, manifest, refuse_existing=True)
    return manifest


def verify_manifest(root: Path) -> dict[str, Any]:
    manifest = _load_private(root / EVIDENCE_MANIFEST)
    if manifest.get("schema") != FORENSIC_SCHEMA:
        raise FailureForensicsError("manifest_schema_invalid")
    if manifest.get("FORENSIC_SNAPSHOT_COMPLETE") is not True:
        raise FailureForensicsError("manifest_incomplete")
    if manifest.get("NO_TARGET_MUTATION") is not True:
        raise FailureForensicsError("manifest_target_mutation_invalid")
    if manifest.get("UNAVAILABLE_IS_EXPLICIT") is not True:
        raise FailureForensicsError("manifest_unavailable_semantics_invalid")
    if manifest.get("ORIGINAL_FAILURE_NOT_OVERWRITTEN") is not True:
        raise FailureForensicsError("manifest_failure_freeze_invalid")
    if manifest.get("BUNDLE_SHA256_PRESENT") is not True:
        raise FailureForensicsError("manifest_bundle_flag_invalid")
    if manifest.get("failure_frozen") is not True:
        raise FailureForensicsError("manifest_failure_not_frozen")

    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != 2:
        raise FailureForensicsError("manifest_files_invalid")
    for record in records:
        if not isinstance(record, dict) or set(record) != {"name", "size_bytes", "sha256"}:
            raise FailureForensicsError("manifest_record_invalid")
        if record["name"] not in {FAILURE_SUMMARY, FORENSIC_SNAPSHOT}:
            raise FailureForensicsError("manifest_record_name_invalid")
        path = root / record["name"]
        _load_private(path)
        if path.stat().st_size != record["size_bytes"] or _sha_file(path) != record["sha256"]:
            raise FailureForensicsError("manifest_file_binding_invalid")
    if canonical_sha256(records) != manifest.get("bundle_sha256"):
        raise FailureForensicsError("manifest_bundle_binding_invalid")

    snapshot = _load_private(root / FORENSIC_SNAPSHOT)
    if (
        snapshot.get("schema") != FORENSIC_SCHEMA
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("read_only") is not True
        or snapshot.get("target_mutation") is not False
    ):
        raise FailureForensicsError("snapshot_safety_contract_invalid")

    failure = _load_private(root / FAILURE_SUMMARY)
    if failure.get("failure_frozen") is not True:
        raise FailureForensicsError("failure_summary_not_frozen")
    if failure.get("forensic_collector_target_mutation") is not False:
        raise FailureForensicsError("failure_summary_collector_boundary_invalid")
    return manifest


def reflash_disposition(root: Path, session_close: Mapping[str, Any]) -> dict[str, Any]:
    manifest = verify_manifest(root)
    if session_close.get("session_closed") is not True:
        raise FailureForensicsError("reflash_before_session_close_forbidden")
    return {
        "TARGET_DISPOSITION": "REFLASH_REQUIRED",
        "REFLASH_ALLOWED": True,
        "FORENSIC_SNAPSHOT_COMPLETE": True,
        "SESSION_CLOSED": True,
        "bundle_sha256": manifest["bundle_sha256"],
    }
