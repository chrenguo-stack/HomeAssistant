#!/usr/bin/env python3
"""Validate the public D2-10 PREPARE timeout root-cause decision."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1 as repair

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DECISION = (
    "docs/decisions/"
    "h3-n2-stage2d9r-g3r-d2-10-prepare-timeout-root-cause-"
    "successor-repair-20260729-v1.json"
)
EXPECTED_PARENT = "ebaa3a95fe32e6715568836f9ca28b58bfdd2e31"
EXPECTED_D2_OUTPUT = (
    "53eeb04fd5f128068bd947f1b60a896d2f0cb38ed68f7cadbda54f149f1d7e64"
)
EXPECTED_READY_LINE = (
    "38330e1c89362a2b79734a65512bc7d3eeb8500cdf7b4d52544ecbf2c7a36552"
)
EXPECTED_RESULT = (
    "715079d46d8f6f02b396b519d97fb2dd77322d8f293ba3749d8337e835d7fda6"
)
EXPECTED_MARKER = (
    "2bd46c499c9cbf1462c834cc8374990789aaa0f654e373ffde40304c8d818295"
)


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_sha256(value: object) -> str:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def validate(root: Path) -> dict[str, object]:
    path = root / DECISION
    require(path.is_file() and not path.is_symlink(), "DECISION_FILE_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "DECISION_NOT_MAPPING")
    binding = value.pop("decision_binding_sha256", None)
    require(
        isinstance(binding, str)
        and HEX64.fullmatch(binding) is not None
        and canonical_sha256(value) == binding,
        "DECISION_BINDING_MISMATCH",
    )
    exact = {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-10-prepare-timeout-"
            "root-cause-successor-repair/1"
        ),
        "status": "SOURCE_REPAIR_READY_NO_PHYSICAL_AUTHORIZATION",
        "base_pr": 206,
        "base_head_sha": EXPECTED_PARENT,
        "d2_10_forensic_output_sha256": EXPECTED_D2_OUTPUT,
        "repeated_prepare_ready_line_sha256": EXPECTED_READY_LINE,
        "terminal_result_sha256": EXPECTED_RESULT,
        "terminal_marker_sha256": EXPECTED_MARKER,
        "prepare_count": 1,
        "verify_count": 0,
        "post_command_reset_count": 0,
        "device_executor_pass_count": 0,
        "device_executor_fail_count": 0,
        "root_cause_code": repair.ROOT_CAUSE_CODE,
        "root_cause_confidence": "HIGH_CONVERGING_EVIDENCE",
        "firmware_command_line_max_bytes": repair.MAX_COMMAND_LINE_BYTES,
        "firmware_read_bytes_per_loop": repair.FIRMWARE_READ_BYTES_PER_LOOP,
        "usb_serial_jtag_default_rx_bytes": (
            repair.USB_SERIAL_JTAG_DEFAULT_RX_BYTES
        ),
        "minimum_prepare_command_bytes": 695,
        "legacy_host_write": "ONE_SHOT_FULL_COMMAND",
        "successor_host_write": "EXACT_PACED_64_BYTE_CHUNKS",
        "successor_inter_chunk_delay_ms": 100,
        "timeout_extension_used": False,
        "command_bytes_changed": False,
        "command_retry_added": False,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "DECISION_" + key.upper() + "_MISMATCH")
    require(HEX40.fullmatch(value["base_head_sha"]) is not None, "BASE_SHA_INVALID")
    value["decision_binding_sha256"] = binding
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        decision = validate(args.repo_root.resolve(strict=True))
        result = {
            **repair.source_status(),
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-10-prepare-timeout-"
                "root-cause-contract-check/1"
            ),
            "status": "PASS",
            "decision_binding_sha256": decision["decision_binding_sha256"],
        }
        rc = 0
    except Exception as exc:
        result = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-10-prepare-timeout-"
                "root-cause-contract-check/1"
            ),
            "status": "FAIL",
            "failure_code": str(exc.args[0]) if exc.args else type(exc).__name__,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        rc = 1
    args.result_output.parent.mkdir(parents=True, exist_ok=True)
    args.result_output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
