from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class TerminalRecordContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise TerminalRecordContractError(code)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "TERMINAL_FILE_INVALID")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalRecordContractError("TERMINAL_RECORD_INVALID") from exc
    require(isinstance(value, dict), "TERMINAL_RECORD_INVALID")
    return value


def terminal_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    require(
        isinstance(payload.get("terminal_record_sha256"), str),
        "TERMINAL_RECORD_DIGEST_MISSING",
    )
    payload.pop("terminal_record_sha256")
    return payload


def verify_terminal_record(
    path: Path,
    *,
    expected_record_sha256: str,
    required_fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify semantic content, never JSON presentation bytes.

    ``terminal_record_sha256`` is the canonical digest of the record with that
    field removed. It is deliberately independent of indentation, whitespace,
    newline and object-key presentation order.
    """

    record = load_json(path)
    embedded = record.get("terminal_record_sha256")
    require(embedded == expected_record_sha256, "TERMINAL_RECORD_DIGEST_BINDING_DRIFT")
    observed = canonical_sha256(terminal_payload(record))
    require(observed == expected_record_sha256, "TERMINAL_RECORD_DIGEST_DRIFT")
    for name, expected in required_fields.items():
        require(record.get(name) == expected, "TERMINAL_FIELD_DRIFT:" + name)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-terminal-record-semantic-verification/1",
        "status": "PASS",
        "terminal_record_sha256": expected_record_sha256,
        "terminal_file_sha256_observed": sha256_file(path),
        "presentation_bytes_bound": False,
        "semantic_record_bound": True,
    }


def reproduce_retired_g02_byte_digest_check(
    path: Path, *, mistaken_expected_file_sha256: str
) -> None:
    require(
        sha256_file(path) == mistaken_expected_file_sha256,
        "TERMINAL_FILE_DIGEST_DRIFT",
    )
