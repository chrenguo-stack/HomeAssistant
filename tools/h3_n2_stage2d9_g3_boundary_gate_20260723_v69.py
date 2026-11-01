#!/usr/bin/env python3
"""Static fail-closed boundary gate for the corrected Stage2D9 V69 source set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ZERO64 = "0" * 64
EXPECTED_UNLOCK_DIGEST = (
    "66ce4bd205e8c76159ad839e6f1115e990f18eab2e149427b243e9c5bd541e9e"
)
EXPECTED_BUILD_BINDING = "f39c3c4c621717a61e0b3cef8b4ec88e59ac13aa"
EXPECTED_EXECUTION_CONFIG = (
    "greenhouse_profile_isolated_device_g3_execution_20260723_v69.yml"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def top_level_keys(text: str) -> set[str]:
    return {
        line.split(":", 1)[0]
        for line in text.splitlines()
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line
    }


def scalar(text: str, key: str) -> str:
    matches = re.findall(rf"^\s+{re.escape(key)}:\s*([^#\s]+)\s*$", text, re.M)
    require(len(matches) == 1, f"expected one {key} scalar")
    value = matches[0]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--execution-config", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    execution_config = (repo / args.execution_config).resolve()
    output = Path(args.output).resolve()
    require(HEX40.fullmatch(args.source_commit) is not None, "invalid source commit")
    require(execution_config.is_file(), "execution config missing")
    require(execution_config.name == EXPECTED_EXECUTION_CONFIG,
            "unexpected V69 execution config")

    board = repo / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare"
    executor = repo / (
        "firmware/esphome_rc/components/"
        "greenhouse_profile_isolated_device_g3_executor_v69"
    )
    partition_csv = board / "stage2d9_g3_partitions_20260722_v65.csv"
    recovery_yml = board / "greenhouse_stage2d9_locked_recovery_20260722_v65.yml"
    compile_yml = board / (
        "greenhouse_profile_isolated_device_g3_executor_v69_compile_20260723_v69.yml"
    )
    source_gate = repo / "tools/h3_n2_stage2d9_v69_source_gate_20260723_v1.py"

    for path in (
        partition_csv,
        recovery_yml,
        compile_yml,
        executor / "stage2d9_g3_prepare_executor_v69.cpp",
        executor / "stage2d9_g3_prepare_executor_v69.h",
        executor / "__init__.py",
        source_gate,
    ):
        require(path.is_file(), f"missing boundary source: {path}")

    execution_text = execution_config.read_text(encoding="utf-8")
    compile_text = compile_yml.read_text(encoding="utf-8")
    recovery_text = recovery_yml.read_text(encoding="utf-8")
    executor_cpp = (executor / "stage2d9_g3_prepare_executor_v69.cpp").read_text(
        encoding="utf-8"
    )

    prohibited_runtime = {"wifi", "api", "ota", "captive_portal", "mqtt", "web_server"}
    require(not (top_level_keys(execution_text) & prohibited_runtime),
            "execution config contains a prohibited runtime component")
    require(not (top_level_keys(recovery_text) & prohibited_runtime),
            "recovery config contains a prohibited runtime component")
    require("external_components:" not in recovery_text,
            "recovery links Stage2D9 code")

    unlock_digest = scalar(execution_text, "unlock_digest")
    require(HEX64.fullmatch(unlock_digest) is not None,
            "unlock digest shape invalid")
    require(unlock_digest == EXPECTED_UNLOCK_DIGEST,
            "V69 unlock digest mismatch")
    require(unlock_digest != ZERO64,
            "V69 execution source command surface disabled unexpectedly")
    require(scalar(compile_text, "unlock_digest") == ZERO64,
            "V69 compile-only command surface enabled")

    source_binding = scalar(execution_text, "build_binding")
    require(source_binding == EXPECTED_BUILD_BINDING,
            "V69 implementation binding mismatch")
    require(scalar(compile_text, "build_binding") == EXPECTED_BUILD_BINDING,
            "V69 compile binding mismatch")

    row = next(
        (line for line in partition_csv.read_text(encoding="utf-8").splitlines()
         if line.strip().startswith("gh2d8_p2d9")),
        "",
    )
    fields = [field.strip() for field in row.split(",")]
    require(fields[:5] == ["gh2d8_p2d9", "data", "nvs", "0x400000", "0x10000"],
            "partition geometry mismatch")
    require(not any("readonly" in field.lower() for field in fields[5:]),
            "PREPARE partition is read-only")

    required_markers = (
        "stage2d9.local",
        "GH2D9_PREPARE_V2",
        "GH2D9_VERIFY_V2",
        "stage2d9_v69_failure",
        "prepare_config_invalid",
        "prepare_authorization_grant",
        "prepare_transaction",
        "prepare_postcondition_recovered_candidate",
        "command_write_attempted=%s",
        "device_command_accepted=%s",
        "package_.prepare_candidate",
        "verify_recovered_candidate_",
        "mqtt_operation_attempted",
        "esp_restart",
    )
    for marker in required_markers:
        require(marker in executor_cpp, f"V69 executor marker missing: {marker}")
    require("stage2d9.invalid" not in executor_cpp,
            "V69 retained invalid host")
    require("GH2D9_PREPARE_V1" not in executor_cpp,
            "V69 reused V68 PREPARE schema")
    require("GH2D9_VERIFY_V1" not in executor_cpp,
            "V69 reused V68 VERIFY schema")
    for prohibited in (
        "package_.activate(",
        "package_.cleanup_test_state(",
        "driver_.activate(",
        "driver_.cleanup_test_state(",
        "esp_efuse",
    ):
        require(prohibited not in executor_cpp,
                f"prohibited V69 executor path: {prohibited}")

    report = {
        "schema": "gh.h3.n2.stage2d9-g3-source-boundary/3",
        "artifact_generation": "V69",
        "status": "pass",
        "gate": "LOCKED",
        "source_commit": args.source_commit,
        "implementation_source_binding": source_binding,
        "root_cause_fix": "valid_local_placeholder_host",
        "candidate_host": "stage2d9.local",
        "prepare_schema": "GH2D9_PREPARE_V2",
        "verify_schema": "GH2D9_VERIFY_V2",
        "unlock_digest_sha256": unlock_digest,
        "unlock_preimage_in_repository": False,
        "private_custody_required_before_d2": True,
        "partition": {
            "label": "gh2d8_p2d9",
            "namespace": "gh2d8_s2d9",
            "offset": "0x400000",
            "size": "0x10000",
            "writable_capable": True,
        },
        "execution": {
            "flash_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "network_authorized": False,
            "efuse_authorized": False,
            "production_authorized": False,
        },
        "sources": {
            "execution_config_sha256": sha256(execution_config),
            "partition_csv_sha256": sha256(partition_csv),
            "executor_cpp_sha256": sha256(
                executor / "stage2d9_g3_prepare_executor_v69.cpp"
            ),
            "executor_header_sha256": sha256(
                executor / "stage2d9_g3_prepare_executor_v69.h"
            ),
            "recovery_config_sha256": sha256(recovery_yml),
            "source_gate_sha256": sha256(source_gate),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
