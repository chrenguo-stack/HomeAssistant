#!/usr/bin/env python3
"""Static host-only boundary gate for the Stage2D9 V69 correction chain."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ZERO64 = "0" * 64


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def function_body(text: str, signature: str, next_signature: str) -> str:
    start = text.find(signature)
    require(start >= 0, f"function missing: {signature}")
    end = text.find(next_signature, start + len(signature))
    require(end > start, f"next function missing: {next_signature}")
    return text[start:end]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    v68_cpp = repo / (
        "firmware/esphome_rc/components/"
        "greenhouse_profile_isolated_device_g3_executor/"
        "stage2d9_g3_prepare_executor.cpp"
    )
    v69_root = repo / (
        "firmware/esphome_rc/components/"
        "greenhouse_profile_isolated_device_g3_executor_v69"
    )
    v69_cpp = v69_root / "stage2d9_g3_prepare_executor_v69.cpp"
    v69_h = v69_root / "stage2d9_g3_prepare_executor_v69.h"
    v69_init = v69_root / "__init__.py"
    dedicated_yml = repo / (
        "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare/"
        "greenhouse_profile_isolated_device_g3_executor_v69_compile_20260723_v69.yml"
    )
    product_yml = repo / (
        "firmware/esphome_rc/f1_0_rc2/"
        "f1_0_rc2_h3_profile_isolated_device_g3_executor_v69_board_lab_20260723_v69.yml"
    )
    serial_model = repo / "tools/h3_n2_stage2d9_v69_serial_capture_model_20260723_v1.py"
    serial_test = repo / (
        "tests/h3_n2_stage2d9_prepare/"
        "test_stage2d9_v69_serial_capture_model_20260723_v1.py"
    )
    actual_chain_test = repo / (
        "tests/h3_n2_stage2d9_prepare/"
        "stage2d9_v69_actual_prepare_chain_20260723_v1.cpp"
    )

    for path in (
        v68_cpp,
        v69_cpp,
        v69_h,
        v69_init,
        dedicated_yml,
        product_yml,
        serial_model,
        serial_test,
        actual_chain_test,
    ):
        require(path.is_file(), f"missing V69 correction source: {path}")

    v68_text = v68_cpp.read_text(encoding="utf-8")
    require("GH2D9_PREPARE_V1" in v68_text, "frozen V68 PREPARE schema missing")
    require("GH2D9_VERIFY_V1" in v68_text, "frozen V68 VERIFY schema missing")
    require(v68_text.count('"stage2d9.invalid"') == 2,
            "frozen V68 candidate-host signature changed")

    cpp = v69_cpp.read_text(encoding="utf-8")
    header = v69_h.read_text(encoding="utf-8")
    init = v69_init.read_text(encoding="utf-8")
    dedicated = dedicated_yml.read_text(encoding="utf-8")
    product = product_yml.read_text(encoding="utf-8")
    model = serial_model.read_text(encoding="utf-8")
    model_test = serial_test.read_text(encoding="utf-8")
    chain_test = actual_chain_test.read_text(encoding="utf-8")

    require("stage2d9.invalid" not in cpp, "V69 retained invalid placeholder host")
    require(cpp.count("stage2d9.local") >= 1, "V69 local placeholder missing")
    require("GH2D9_PREPARE_V2" in cpp and "GH2D9_VERIFY_V2" in cpp,
            "V69 command schemas missing")
    require("GH2D9_PREPARE_V1" not in cpp and "GH2D9_VERIFY_V1" not in cpp,
            "V69 reused V68 command schemas")
    require("Stage2D9G3PrepareExecutorV69" in cpp and
            "Stage2D9G3PrepareExecutorV69" in header and
            "Stage2D9G3PrepareExecutorV69" in init,
            "V69 unique component identity missing")
    for marker in (
        "stage2d9_v69_failure",
        "driver_failure=%s",
        "package_failure=%s",
        "command_write_attempted=%s",
        "device_command_accepted=%s",
        "prepare_config_invalid",
        "prepare_authorization_grant",
        "prepare_transaction",
        "prepare_postcondition_persistence",
        "prepare_postcondition_recovered_candidate",
    ):
        require(marker in cpp, f"V69 observability marker missing: {marker}")

    execute_prepare = function_body(
        cpp,
        "bool Stage2D9G3PrepareExecutorV69::execute_prepare_",
        "bool Stage2D9G3PrepareExecutorV69::execute_verify_",
    )
    require("this->mqtt_." not in execute_prepare.replace(
        "this->mqtt_.operation_attempted()", ""),
        "V69 PREPARE contains an MQTT operation")
    for prohibited in (
        "package_.activate(",
        "package_.cleanup_test_state(",
        "driver_.activate(",
        "driver_.cleanup_test_state(",
        "esp_efuse",
    ):
        require(prohibited not in cpp, f"prohibited V69 path present: {prohibited}")

    prohibited_runtime = {"wifi", "api", "ota", "captive_portal", "mqtt", "web_server"}
    for label, text in (("dedicated", dedicated), ("product", product)):
        require(not (top_level_keys(text) & prohibited_runtime),
                f"{label} V69 config contains runtime network component")
        require(scalar(text, "unlock_digest") == ZERO64,
                f"{label} V69 compile target command surface enabled")
        require("greenhouse_profile_isolated_device_g3_executor_v69" in text,
                f"{label} V69 component missing")

    for marker in (
        "finally:",
        "atomic_write(log_path, payload)",
        "host_write_attempted",
        "device_command_accepted",
        "transaction_succeeded",
    ):
        require(marker in model, f"serial evidence model marker missing: {marker}")
    for case in (
        "test_fail_marker_is_persisted_before_exception",
        "test_timeout_preserves_partial_capture",
        "test_host_exception_preserves_prior_bytes",
        "test_pass_separates_acceptance_and_transaction_success",
    ):
        require(case in model_test, f"serial evidence test missing: {case}")
    require("stage2d9.invalid" in chain_test and "stage2d9.local" in chain_test,
            "actual PREPARE chain A/B test missing")
    require("package.prepare_candidate()" in chain_test,
            "actual package PREPARE call missing")
    require("prepare_call_count() == 0" in chain_test,
            "invalid host pre-persistence assertion missing")
    require("prepare_call_count() == 1" in chain_test,
            "valid host persistence assertion missing")

    report = {
        "schema": "gh.h3.n2.stage2d9-v69-source-boundary/1",
        "status": "pass",
        "artifact_generation": None,
        "source_stage": "host_only_correction",
        "v68_executor_structural_signature_present": True,
        "v68_executor_sha256": sha256(v68_cpp),
        "root_cause_fix": "valid_local_placeholder_host",
        "candidate_host": "stage2d9.local",
        "prepare_schema": "GH2D9_PREPARE_V2",
        "verify_schema": "GH2D9_VERIFY_V2",
        "command_surface_enabled": False,
        "actual_prepare_chain_test_present": True,
        "atomic_serial_evidence_model_present": True,
        "stage_specific_failure_markers_present": True,
        "activate_cleanup_paths_present": False,
        "network_runtime_present": False,
        "device_operation_authorized": False,
        "artifact_build_authorized": False,
        "private_material_present": False,
        "d2_request_present": False,
        "source_sha256": {
            "v69_cpp": sha256(v69_cpp),
            "v69_header": sha256(v69_h),
            "v69_component": sha256(v69_init),
            "serial_model": sha256(serial_model),
            "actual_prepare_chain_test": sha256(actual_chain_test),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
