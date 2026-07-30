#!/usr/bin/env python3
"""Validate G07 consumed-failure closure and emit a secret-free result whitelist."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_DECISION = "D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01"
EXPECTED_D2 = "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17"
EXPECTED_TERMINAL_SHA256 = "e3ec66f159fa2e2c24c15df3896d7004e147ac97ab853015c8c4aa4475f55fb4"
EXPECTED_RESULT_SHA256 = "f50cb0bcb0422416f27ba89cf3e7712a7d98f86d0529e5a47ba1c1abc2dd5fcf"

TERMINAL_KEYS = (
    "schema", "status", "terminal_state", "failure_code", "decision_id", "d2_request_id",
    "authorization_claimed", "authorization_consumed", "authorization_record_sha256",
    "authorization_marker_sha256", "physical_result_sha256", "execution_identity_sha256",
    "board_operation", "usb_enumeration", "serial_operation", "esptool_operation",
    "physical_nvs_operation", "flash_operation", "broker_started", "prepare_executed",
    "verify_executed", "recovery_executed", "recovery_succeeded", "activate_executed",
    "cleanup_executed", "replay_permitted", "automatic_retry_permitted",
    "terminal_record_sha256",
)
RESULT_KEYS = (
    "schema", "stage", "status", "terminal_state", "failure_code", "failure_stage",
    "d2_request_id", "authorization_created", "authorization_claimed",
    "authorization_consumed", "authorization_record_sha256", "board_operation",
    "usb_enumeration", "serial_operation", "esptool_operation", "flash_operation",
    "physical_nvs_operation", "network_operation", "broker_started", "prepare_executed",
    "verify_executed", "recovery_attempted", "recovery_succeeded",
    "terminal_result_sha256", "replay_permitted", "automatic_retry_permitted",
)

class ForensicError(RuntimeError):
    pass

def require(ok: bool, code: str) -> None:
    if not ok:
        raise ForensicError(code)

def canonical(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def load_mapping(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ForensicError(code) from exc
    require(isinstance(value, dict), code)
    return value

def validate_terminal(value: dict[str, Any]) -> dict[str, Any]:
    digest = value.get("terminal_record_sha256")
    require(digest == EXPECTED_TERMINAL_SHA256, "TERMINAL_DIGEST_BINDING_DRIFT")
    semantic = dict(value)
    semantic.pop("terminal_record_sha256", None)
    require(canonical(semantic) == EXPECTED_TERMINAL_SHA256, "TERMINAL_SEMANTIC_DIGEST_DRIFT")
    require(value.get("decision_id") == EXPECTED_DECISION, "TERMINAL_DECISION_DRIFT")
    require(value.get("d2_request_id") == EXPECTED_D2, "TERMINAL_D2_DRIFT")
    require(value.get("status") == "FAIL", "TERMINAL_STATUS_DRIFT")
    require(value.get("failure_code") == "TypeError", "TERMINAL_FAILURE_CODE_DRIFT")
    require(value.get("authorization_consumed") is True, "AUTHORIZATION_NOT_CONSUMED")
    require(value.get("replay_permitted") is False, "REPLAY_BOUNDARY_DRIFT")
    require(value.get("automatic_retry_permitted") is False, "RETRY_BOUNDARY_DRIFT")
    for field in ("flash_operation", "broker_started", "prepare_executed", "verify_executed",
                  "recovery_executed", "activate_executed", "cleanup_executed"):
        require(value.get(field) is False, "UNEXPECTED_OPERATION:" + field)
    require(value.get("physical_result_sha256") == EXPECTED_RESULT_SHA256, "PHYSICAL_RESULT_BINDING_DRIFT")
    return {key: value.get(key) for key in TERMINAL_KEYS}

def result_whitelist(path: Path) -> dict[str, Any]:
    require(sha256_file(path) == EXPECTED_RESULT_SHA256, "PHYSICAL_RESULT_FILE_DIGEST_DRIFT")
    value = load_mapping(path, "PHYSICAL_RESULT_INVALID")
    return {key: value.get(key) for key in RESULT_KEYS}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--physical-result", type=Path)
    args = parser.parse_args()
    terminal = validate_terminal(load_mapping(args.terminal, "TERMINAL_INVALID"))
    output: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g07-consumed-typeerror-sanitized-forensic/1",
        "status": "PASS",
        "terminal": terminal,
        "physical_result": None,
        "secret_values_included": False,
        "local_paths_included": False,
        "payload_bytes_included": False,
    }
    if args.physical_result is not None:
        output["physical_result"] = result_whitelist(args.physical_result)
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
