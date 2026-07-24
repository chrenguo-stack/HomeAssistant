#!/usr/bin/env python3
"""Fail-closed gate for Stage 2D-9R dedicated test-partition recovery."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-test-partition-recovery-manifest/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
LOCKED = "LOCKED_TEMPLATE"
AUTHORIZED = "RECOVERY_AUTHORIZED"
ALLOWED_STATES = {LOCKED, AUTHORIZED}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"<[^>]+>")
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"

EXPECTED_PRE = {
    "active_generation": 0,
    "candidate_generation": 1,
    "candidate_state": "PREPARED",
    "candidate_digest_match": True,
}
EXPECTED_PARTITION = {
    "label": "gh2d8_p2d9",
    "namespace": "gh2d8_s2d9",
    "address": 0x400000,
    "size_bytes": 0x10000,
    "expected_erased_byte": 0xFF,
    "expected_erased_sha256": ERASED_SHA256,
}
EXPECTED_COUNTS = {
    "pre_read": 1,
    "erase_region": 1,
    "post_read": 1,
    "firmware_flash": 0,
    "full_chip_erase": 0,
    "prepare_command": 0,
    "verify_command": 0,
    "activate_command": 0,
    "cleanup_command": 0,
    "physical_reset": 0,
    "physical_boot_button": 0,
}
EXPECTED_POST = {
    "partition_erased": True,
    "readback_all_ff": True,
    "partition_sha256": ERASED_SHA256,
    "namespace_present": False,
    "active_generation": 0,
    "candidate_generation": 0,
    "candidate_state": "EMPTY",
}
ALWAYS_FALSE = (
    "network_operation_authorized",
    "broker_operation_authorized",
    "firmware_flash_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "efuse_operation_authorized",
    "secure_boot_change_authorized",
    "flash_encryption_change_authorized",
    "production_operation_authorized",
)


class RecoveryError(RuntimeError):
    """Raised when a recovery manifest violates the frozen contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def object_at(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    require(isinstance(value, dict), f"{key} must be an object")
    return value


def has_placeholder(value: object) -> bool:
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return PLACEHOLDER.search(str(value)) is not None


def absolute_path(value: object) -> bool:
    text = str(value)
    path = PurePosixPath(text)
    return path.is_absolute() and PLACEHOLDER.search(text) is None and ".." not in path.parts


def parse_utc(value: object, key: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"),
            f"{key} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RecoveryError(f"{key} invalid") from exc
    require(parsed.tzinfo == timezone.utc, f"{key} must use UTC")
    return parsed


def validate(data: dict[str, Any], expected_state: str | None = None) -> str:
    require(data.get("schema") == SCHEMA, "schema mismatch")
    require(data.get("stage") == STAGE, "stage mismatch")
    state = data.get("state")
    require(state in ALLOWED_STATES, "state is not allowed")
    if expected_state is not None:
        require(state == expected_state, "state does not match expected state")

    require(object_at(data, "expected_pre_state") == EXPECTED_PRE,
            "expected pre-state mismatch")
    require(object_at(data, "partition") == EXPECTED_PARTITION,
            "partition contract mismatch")
    require(object_at(data, "allowed_counts") == EXPECTED_COUNTS,
            "allowed counts mismatch")
    require(object_at(data, "expected_post_state") == EXPECTED_POST,
            "expected post-state mismatch")
    for key in ALWAYS_FALSE:
        require(data.get(key) is False, f"{key} must be false")

    authorization = object_at(data, "authorization")
    require(authorization.get("operation") == "ERASE_TEST_PARTITION",
            "authorization operation mismatch")
    require(authorization.get("one_shot") is True,
            "authorization must be one-shot")
    require(authorization.get("replay_permitted") is False,
            "authorization replay must be false")

    if state == LOCKED:
        require(has_placeholder(data), "locked template must retain placeholders")
        for key in (
            "recovery_authorized",
            "board_operation_authorized",
            "serial_operation_authorized",
            "flash_operation_authorized",
        ):
            require(data.get(key) is False, f"{key} must be false while locked")
        require(authorization.get("authorization_id") is None,
                "locked authorization id must be null")
        require(authorization.get("authorized") is False,
                "locked template must not be authorized")
        require(authorization.get("consumed") is False,
                "locked template must not be consumed")
        for key in ("issued_at", "expires_at", "record_sha256"):
            require(authorization.get(key) is None,
                    f"locked {key} must be null")
        return LOCKED

    require(not has_placeholder(data), "authorized manifest has placeholders")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None,
            "source_sha invalid")
    for key in (
        "recovery_tool_sha256",
        "python_environment_sha256",
        "board_binding_sha256",
        "current_firmware_artifact_sha256",
        "current_candidate_digest_sha256",
        "current_partition_sha256",
    ):
        require(HEX64.fullmatch(str(data.get(key))) is not None, f"{key} invalid")
    require(absolute_path(data.get("serial_path")),
            "serial_path must be absolute")
    for key in (
        "recovery_authorized",
        "board_operation_authorized",
        "serial_operation_authorized",
        "flash_operation_authorized",
    ):
        require(data.get(key) is True, f"{key} must be true when authorized")

    require(isinstance(authorization.get("authorization_id"), str) and
            str(authorization.get("authorization_id")).startswith("D2-"),
            "authorization id invalid")
    require(authorization.get("authorized") is True,
            "authorization must be true")
    require(authorization.get("consumed") is False,
            "pre-execution manifest must not be consumed")
    require(HEX64.fullmatch(str(authorization.get("record_sha256"))) is not None,
            "authorization record digest invalid")
    issued = parse_utc(authorization.get("issued_at"), "issued_at")
    expires = parse_utc(authorization.get("expires_at"), "expires_at")
    require(issued < expires, "authorization interval invalid")
    require((expires - issued).total_seconds() <= 7200,
            "authorization interval exceeds two hours")
    return AUTHORIZED


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-state", choices=sorted(ALLOWED_STATES))
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        state = validate(data, args.expect_state)
    except Exception as exc:  # fail-closed CLI boundary
        print("STAGE2D9R_TEST_PARTITION_RECOVERY_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_TEST_PARTITION_RECOVERY_GATE=PASS")
    print(f"STATE={state}")
    print("PARTITION_ADDRESS=0x00400000")
    print("PARTITION_SIZE=65536")
    print("FULL_CHIP_ERASE_AUTHORIZED=false")
    print("FIRMWARE_FLASH_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    print("PREPARE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
