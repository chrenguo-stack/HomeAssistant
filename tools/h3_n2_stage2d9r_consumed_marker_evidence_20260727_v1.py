#!/usr/bin/env python3
"""Validate consumed U1 evidence from immutable files or a durable marker.

The validator is read-only. It never reconstructs an authorization record or
result from their public digests. When the original files have been retired, a
mode-0600 consumed marker is sufficient only when it binds both frozen digests
and keeps one-shot, non-replay and no-retry semantics.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from typing import Any

HEX64 = __import__("re").compile(r"^[0-9a-f]{64}$")


class ConsumedEvidenceError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ConsumedEvidenceError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def require_metadata_file(path: Path, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == "0600", code)


def load_json(path: Path, code: str) -> dict[str, Any]:
    require_metadata_file(path, code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code)
    return value


def one_of(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def validate_consumed_evidence(
    *,
    marker: Path,
    authorization_id: str,
    authorization_record_sha256: str,
    result_sha256: str,
    authorization_record: Path | None = None,
    result: Path | None = None,
) -> dict[str, Any]:
    require(HEX64.fullmatch(authorization_record_sha256) is not None,
            "EXPECTED_AUTHORIZATION_RECORD_SHA_INVALID")
    require(HEX64.fullmatch(result_sha256) is not None,
            "EXPECTED_RESULT_SHA_INVALID")

    marker_before = sha256_file(marker) if marker.is_file() else None
    marker_value = load_json(marker, "CONSUMED_MARKER_INVALID")
    require(marker_value.get("authorization_id") == authorization_id,
            "CONSUMED_MARKER_ID_MISMATCH")
    require(marker_value.get("status") in ("CONSUMED", "CONSUMED_PASS"),
            "CONSUMED_MARKER_STATUS_MISMATCH")
    require(
        one_of(marker_value, "authorization_record_sha256", "record_sha256")
        == authorization_record_sha256,
        "CONSUMED_MARKER_AUTHORIZATION_RECORD_MISMATCH",
    )
    require(
        one_of(marker_value, "result_sha256", "execution_result_sha256")
        == result_sha256,
        "CONSUMED_MARKER_RESULT_MISMATCH",
    )
    require(marker_value.get("replay_permitted") is False,
            "CONSUMED_MARKER_REPLAY_EXPANDED")
    require(marker_value.get("automatic_retry_permitted") is False,
            "CONSUMED_MARKER_RETRY_EXPANDED")
    if "one_shot" in marker_value:
        require(marker_value.get("one_shot") is True,
                "CONSUMED_MARKER_NOT_ONE_SHOT")
    for key in ("secret_values_included", "private_paths_included"):
        if key in marker_value:
            require(marker_value.get(key) is False,
                    f"CONSUMED_MARKER_{key.upper()}")

    supplied = (authorization_record is not None, result is not None)
    require(supplied in ((False, False), (True, True)),
            "PARTIAL_ORIGINAL_CONSUMED_EVIDENCE")

    evidence_mode = "CONSUMED_MARKER_ONLY"
    if authorization_record is not None and result is not None:
        require_metadata_file(
            authorization_record, "AUTHORIZATION_RECORD_METADATA_INVALID"
        )
        require_metadata_file(result, "RESULT_METADATA_INVALID")
        require(
            sha256_file(authorization_record) == authorization_record_sha256,
            "AUTHORIZATION_RECORD_SHA_MISMATCH",
        )
        require(sha256_file(result) == result_sha256, "RESULT_SHA_MISMATCH")
        evidence_mode = "ORIGINAL_FILES_AND_CONSUMED_MARKER"

    require(marker_before is not None and sha256_file(marker) == marker_before,
            "CONSUMED_MARKER_CHANGED_DURING_VALIDATION")
    return {
        "authorization_id": authorization_id,
        "authorization_record_sha256": authorization_record_sha256,
        "result_sha256": result_sha256,
        "consumed_marker_sha256": marker_before,
        "status": "CONSUMED_PASS",
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "marker_modified": False,
        "evidence_mode": evidence_mode,
        "original_authorization_record_present": authorization_record is not None,
        "original_result_present": result is not None,
        "authorization_replayed": False,
        "authorization_reconstructed": False,
    }
