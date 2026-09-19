#!/usr/bin/env python3
"""Read-only metadata probe for the consumed Stage 2D-9R U1-04 marker.

The probe reads only the one-shot authorization consumption marker, validates
safe metadata fields, and emits no private path or secret value. It performs no
network, Broker, board, serial, Flash, NVS, PREPARE, VERIFY, or production work.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Any

AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-04"
EXPECTED_RECORD_SHA256 = "f9d02e196fa884be7b72a18849bd59aa902512bc5cfac8f20b10ecd20fdf9ed8"
EXPECTED_RESULT_SHA256 = "d1cd5f72134a19f0748869990e4ff15f61ac0df02331b74ad57a603d35c617a7"
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class MarkerProbeError(RuntimeError):
    """Fail-closed metadata probe error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise MarkerProbeError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def parse_utc(value: object, field: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{field.upper()}_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MarkerProbeError(f"{field.upper()}_INVALID") from exc
    return parsed.astimezone(timezone.utc)


def marker_path(home: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", AUTHORIZATION_ID)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def probe(home: Path) -> dict[str, Any]:
    auth_dir = (home.resolve(strict=True) / AUTH_RELATIVE).resolve(strict=False)
    require(auth_dir.is_dir() and not auth_dir.is_symlink(), "AUTHORIZATION_DIRECTORY_INVALID")
    require(file_mode(auth_dir) == "0700", "AUTHORIZATION_DIRECTORY_MODE_MISMATCH")

    path = marker_path(home)
    require(path.is_file() and not path.is_symlink(), "U1_04_MARKER_MISSING")
    require(file_mode(path) == "0600", "U1_04_MARKER_MODE_MISMATCH")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), "U1_04_MARKER_TYPE_INVALID")
    require(
        value.get("schema")
        == "gh.h3.n2.stage2d9r-private-content-binding-u1-consumption/1",
        "U1_04_MARKER_SCHEMA_MISMATCH",
    )
    require(value.get("authorization_id") == AUTHORIZATION_ID, "U1_04_AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED", "U1_04_STATUS_MISMATCH")
    require(value.get("record_sha256") == EXPECTED_RECORD_SHA256, "U1_04_RECORD_MISMATCH")
    require(value.get("result_sha256") == EXPECTED_RESULT_SHA256, "U1_04_RESULT_MISMATCH")
    require(value.get("failure_code") is None, "U1_04_FAILURE_CODE_MISMATCH")
    require(value.get("one_shot") is True, "U1_04_ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "U1_04_REPLAY_MISMATCH")
    require(value.get("automatic_retry_permitted") is False, "U1_04_RETRY_MISMATCH")
    require(value.get("secret_values_included") is False, "U1_04_SECRET_FLAG_MISMATCH")
    claimed = parse_utc(value.get("claimed_at"), "claimed_at")
    consumed = parse_utc(value.get("consumed_at"), "consumed_at")
    require(consumed >= claimed, "U1_04_TIMESTAMP_ORDER_INVALID")
    digest = sha256_bytes(raw)
    require(HEX64.fullmatch(digest) is not None, "U1_04_MARKER_DIGEST_INVALID")

    return {
        "schema": "gh.h3.n2.stage2d9r-private-content-success-marker-probe/1",
        "stage": "H3/N2 Stage 2D-9R G3R",
        "authorization_id": AUTHORIZATION_ID,
        "status": "CONSUMED",
        "record_sha256": EXPECTED_RECORD_SHA256,
        "result_sha256": EXPECTED_RESULT_SHA256,
        "marker_sha256": digest,
        "failure_code": None,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "network_operation": False,
        "broker_started": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "marker_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    print("PRIVATE_CONTENT_BINDING_SUCCESS_MARKER_PROBE_V1_BEGIN")
    try:
        result = probe(args.home.expanduser())
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, MarkerProbeError) and exc.args else type(exc).__name__
        print("PRIVATE_CONTENT_SUCCESS_MARKER_PROBE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("PRIVATE_CONTENT_READ=false")
        print("MARKER_MODIFIED=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("BOARD_OPERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PRIVATE_CONTENT_BINDING_SUCCESS_MARKER_PROBE_V1_END")
        return 2
    print("PRIVATE_CONTENT_SUCCESS_MARKER_PROBE=PASS")
    print(json.dumps(result, sort_keys=True))
    print("PRIVATE_CONTENT_BINDING_SUCCESS_MARKER_PROBE_V1_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
