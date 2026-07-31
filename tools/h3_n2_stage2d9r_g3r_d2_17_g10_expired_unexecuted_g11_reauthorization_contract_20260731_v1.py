#!/usr/bin/env python3
"""Validate the public G10 expiry disposition and G11 pending gate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_DISPOSITION = Path("docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g10-expired-unexecuted-disposition-20260731-v1.json")
DEFAULT_PENDING = Path("docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g11-private-package-static-check-authorization-pending-20260731-v1.json")
EXPECTED_EXPIRY = "2026-07-31T06:43:11.473014Z"
EXPECTED_BASE_HEAD = "36181664b7ac1ad8753b0ca5e525437615aab6ac"
EXPECTED_NEXT_GATE = "D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01"
EXPECTED_DISPOSITION_BINDING = "eca6986ee9fba51bcd877969a924203fd10f3f5f2954e6be1d1fc2f669282b5b"
EXPECTED_PENDING_BINDING = "db404b7ca1367c2bd5bd6adf82d3060d8ac34c7056e5576907e0e8d77fae7281"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


def canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON_OBJECT_REQUIRED: {path}")
    return value


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def parse_utc(value: str) -> dt.datetime:
    require(value.endswith("Z"), "UTC_Z_SUFFIX_REQUIRED")
    return dt.datetime.fromisoformat(value[:-1] + "+00:00")


def require_sha(value: Any, code: str) -> None:
    require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, code)


def verify_binding(document: dict[str, Any], field: str, expected: str) -> None:
    observed = document.get(field)
    require(observed == expected, f"{field.upper()}_EXACT_MISMATCH")
    payload = dict(document)
    payload.pop(field, None)
    require(canonical_digest(payload) == expected, f"{field.upper()}_RECOMPUTE_MISMATCH")


def validate_disposition(document: dict[str, Any], now: dt.datetime) -> None:
    require(document.get("schema") == "gh.h3.n2.stage2d9r-g3r-d2-17-g10-expired-unexecuted-disposition/1", "DISPOSITION_SCHEMA_MISMATCH")
    require(document.get("state") == "EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY", "DISPOSITION_STATE_MISMATCH")
    require(document.get("package_generation") == "G10", "DISPOSITION_GENERATION_MISMATCH")
    require(document.get("source_pr") == 239, "DISPOSITION_SOURCE_PR_MISMATCH")
    require(document.get("source_head_sha") == EXPECTED_BASE_HEAD, "DISPOSITION_SOURCE_HEAD_MISMATCH")
    require(document.get("authorization_expires_at") == EXPECTED_EXPIRY, "DISPOSITION_EXPIRY_MISMATCH")
    require(now >= parse_utc(EXPECTED_EXPIRY), "AUTHORIZATION_NOT_YET_EXPIRED")
    require(document.get("authorization_created") is True, "AUTHORIZATION_CREATED_REQUIRED")
    require(document.get("authorization_claimed") is False, "AUTHORIZATION_CLAIMED_MUST_BE_FALSE")
    require(document.get("authorization_consumed") is False, "AUTHORIZATION_CONSUMED_MUST_BE_FALSE")
    require(document.get("physical_decision_created") is False, "PHYSICAL_DECISION_CREATED_MUST_BE_FALSE")
    require(document.get("physical_runtime_created") is False, "PHYSICAL_RUNTIME_CREATED_MUST_BE_FALSE")
    require(document.get("late_physical_authorization_not_executed") is True, "LATE_AUTHORIZATION_DISPOSITION_REQUIRED")
    require(document.get("physical_execution_not_started") is True, "PHYSICAL_EXECUTION_NOT_STARTED_REQUIRED")
    require(document.get("replay_permitted") is False, "REPLAY_MUST_BE_FALSE")
    require(document.get("automatic_retry_permitted") is False, "AUTOMATIC_RETRY_MUST_BE_FALSE")
    require(document.get("physical_execution_authorization_id") == "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PHYSICAL-EXECUTION-20260731-01", "PHYSICAL_AUTHORIZATION_ID_MISMATCH")
    for field in (
        "authorization_file_sha256",
        "authorization_record_sha256",
        "g10_acceptance_binding_sha256",
        "g10_physical_pending_binding_sha256",
        "g10_private_delivery_binding_sha256",
        "static_check_terminal_record_sha256",
    ):
        require_sha(document.get(field), f"{field.upper()}_INVALID")
    for field in (
        "board_operation",
        "broker_started",
        "esptool_operation",
        "flash_operation",
        "physical_nvs_operation",
        "prepare_executed",
        "recovery_executed",
        "serial_operation",
        "usb_enumeration",
        "verify_executed",
    ):
        require(document.get(field) is False, f"{field.upper()}_MUST_BE_FALSE")
    verify_binding(document, "disposition_binding_sha256", EXPECTED_DISPOSITION_BINDING)


def validate_pending(document: dict[str, Any]) -> None:
    require(document.get("schema") == "gh.h3.n2.stage2d9r-g3r-d2-17-g11-private-package-static-check-authorization-pending/1", "PENDING_SCHEMA_MISMATCH")
    require(document.get("state") == "G11_PRIVATE_PACKAGE_AND_STATIC_CHECK_EXPLICIT_AUTHORIZATION_PENDING", "PENDING_STATE_MISMATCH")
    require(document.get("base_pr") == 239, "PENDING_BASE_PR_MISMATCH")
    require(document.get("base_head_sha") == EXPECTED_BASE_HEAD, "PENDING_BASE_HEAD_MISMATCH")
    require(document.get("next_package_generation") == "G11", "PENDING_GENERATION_MISMATCH")
    require(document.get("next_gate") == EXPECTED_NEXT_GATE, "PENDING_NEXT_GATE_MISMATCH")
    require(document.get("g10_expired_disposition_binding_sha256") == EXPECTED_DISPOSITION_BINDING, "PENDING_DISPOSITION_BINDING_MISMATCH")
    for field in (
        "g10_authorization_reusable",
        "g10_operator_package_reusable",
        "g10_private_runtime_reusable",
        "g10_static_check_replay_permitted",
        "g11_authorization_created",
        "g11_physical_execution_authorized",
        "g11_private_package_created",
        "automatic_retry_permitted",
        "board_operation",
        "broker_started",
        "deployment",
        "esptool_operation",
        "flash_operation",
        "merge",
        "physical_nvs_operation",
        "prepare_executed",
        "ready",
        "recovery_executed",
        "release",
        "serial_operation",
        "tag",
        "usb_enumeration",
        "verify_executed",
    ):
        require(document.get(field) is False, f"{field.upper()}_MUST_BE_FALSE")
    verify_binding(document, "pending_binding_sha256", EXPECTED_PENDING_BINDING)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposition", type=Path, default=DEFAULT_DISPOSITION)
    parser.add_argument("--pending", type=Path, default=DEFAULT_PENDING)
    parser.add_argument("--now", help="UTC ISO-8601 test override")
    args = parser.parse_args()

    now = parse_utc(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    disposition = load_json(args.disposition)
    pending = load_json(args.pending)
    validate_disposition(disposition, now)
    validate_pending(pending)
    print(json.dumps({
        "disposition_binding_sha256": EXPECTED_DISPOSITION_BINDING,
        "g10_state": "EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY",
        "g11_private_material_created": False,
        "next_gate": EXPECTED_NEXT_GATE,
        "pending_binding_sha256": EXPECTED_PENDING_BINDING,
        "status": "PASS",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
