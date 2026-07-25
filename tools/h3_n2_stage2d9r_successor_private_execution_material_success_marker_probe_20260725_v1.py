#!/usr/bin/env python3
"""Read-only probe for the consumed successor private execution material U1 marker.

The probe reads only the one-shot authorization marker metadata. It does not read
successor private execution material, print a private path, modify the marker,
or perform board, serial, Flash, NVS, network, Broker, PREPARE, or VERIFY work.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-successor-private-execution-material-success-marker-probe/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-u1-consumption/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01"
RECORD_SHA256 = "99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_utc(value: Any, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProbeError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed


def default_marker(home: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", AUTHORIZATION_ID)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def validate_marker(marker: Path) -> dict[str, object]:
    require(marker.is_file() and not marker.is_symlink(), "MARKER_MISSING_OR_INVALID")
    before_sha = sha256_file(marker)
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("MARKER_JSON_INVALID") from exc
    require(isinstance(value, dict), "MARKER_JSON_INVALID")
    require(value.get("schema") == MARKER_SCHEMA, "MARKER_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED", "MARKER_STATUS_MISMATCH")
    require(value.get("record_sha256") == RECORD_SHA256, "RECORD_SHA256_MISMATCH")
    require(
        value.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256,
        "PUBLIC_DESCRIPTOR_SHA256_MISMATCH",
    )
    require(value.get("failure_code") is None, "MARKER_FAILURE_CODE_PRESENT")
    require(value.get("one_shot") is True, "ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "REPLAY_BOUNDARY_MISMATCH")
    require(
        value.get("automatic_retry_permitted") is False,
        "AUTOMATIC_RETRY_BOUNDARY_MISMATCH",
    )
    require(value.get("secret_values_included") is False, "SECRET_VALUE_FLAG_MISMATCH")
    claimed = parse_utc(value.get("claimed_at"), "CLAIMED_AT_INVALID")
    consumed = parse_utc(value.get("consumed_at"), "CONSUMED_AT_INVALID")
    require(consumed >= claimed, "MARKER_TIMESTAMP_ORDER_INVALID")
    after_sha = sha256_file(marker)
    require(after_sha == before_sha, "MARKER_CHANGED_DURING_PROBE")
    require(HEX64.fullmatch(before_sha) is not None, "MARKER_SHA256_INVALID")
    return {
        "schema": SCHEMA,
        "stage": STAGE,
        "authorization_id": AUTHORIZATION_ID,
        "status": "CONSUMED",
        "record_sha256": RECORD_SHA256,
        "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "marker_sha256": before_sha,
        "failure_code": None,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "marker_modified": False,
        "private_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path)
    args = parser.parse_args()
    try:
        expected = default_marker(Path.home())
        marker = expected if args.marker is None else args.marker.expanduser().resolve(strict=False)
        require(marker == expected, "MARKER_SELECTION_RULE_MISMATCH")
        result = validate_marker(marker)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        print("STAGE2D9R_SUCCESSOR_PRIVATE_EXECUTION_MATERIAL_SUCCESS_MARKER_PROBE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("MARKER_MODIFIED=false")
        print("PRIVATE_CONTENT_READ=false")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PHYSICAL_NVS_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("PREPARE_EXECUTED=false")
        print("VERIFY_EXECUTED=false")
        return 2
    print("STAGE2D9R_SUCCESSOR_PRIVATE_EXECUTION_MATERIAL_SUCCESS_MARKER_PROBE=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
