#!/usr/bin/env python3
"""Prove the frozen Stage2D9 V68 PREPARE host-contract mismatch.

This gate is read-only. It inspects frozen source text and records the exact
validation chain that rejects the V68 candidate before persistence. It does not
access a board, serial port, Flash, eFuse, network or private execution data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


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
    executor_path = repo / (
        "firmware/esphome_rc/components/"
        "greenhouse_profile_isolated_device_g3_executor/"
        "stage2d9_g3_prepare_executor.cpp"
    )
    package_path = repo / (
        "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/"
        "isolated_acceptance_package.cpp"
    )
    driver_path = repo / (
        "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/"
        "isolated_device_driver.cpp"
    )
    credentials_path = repo / (
        "firmware/esphome_rc/components/greenhouse_pairing_client/"
        "pairing_ram_credentials.cpp"
    )
    core_path = repo / (
        "firmware/esphome_rc/components/greenhouse_pairing_client/"
        "pairing_client_core.cpp"
    )

    for path in (
        executor_path,
        package_path,
        driver_path,
        credentials_path,
        core_path,
    ):
        require(path.is_file(), f"source missing: {path}")

    executor = executor_path.read_text(encoding="utf-8")
    package = package_path.read_text(encoding="utf-8")
    driver = driver_path.read_text(encoding="utf-8")
    credentials = credentials_path.read_text(encoding="utf-8")
    core = core_path.read_text(encoding="utf-8")

    build_configuration = function_body(
        executor,
        "Stage2D9G3PrepareExecutor::build_configuration_",
        "bool Stage2D9G3PrepareExecutor::build_candidate_digest_",
    )
    execute_prepare = function_body(
        executor,
        "bool Stage2D9G3PrepareExecutor::execute_prepare_",
        "bool Stage2D9G3PrepareExecutor::execute_verify_",
    )
    package_prepare = function_body(
        package,
        "bool IsolatedAcceptancePackage::prepare_candidate()",
        "bool IsolatedAcceptancePackage::begin_validation()",
    )
    driver_prepare = function_body(
        driver,
        "bool IsolatedDeviceDriver::prepare_candidate(",
        "bool IsolatedDeviceDriver::begin_validation(",
    )
    driver_validation = function_body(
        driver,
        "bool IsolatedDeviceDriver::begin_validation(",
        "bool IsolatedDeviceDriver::poll_validation(",
    )
    bundle_valid = function_body(
        credentials,
        "bool RamCredentialBundle::valid() const",
        "bool RamCredentialBundle::present() const",
    )
    local_host_valid = function_body(
        core,
        "bool PairingClientCore::valid_local_host(",
        "bool PairingClientCore::same_candidate(",
    )

    require(
        build_configuration.count('"stage2d9.invalid"') == 2,
        "frozen V68 executor no longer has the expected two dot-invalid hosts",
    )
    require(
        "this->package_.load_test_configuration" in execute_prepare,
        "executor configuration load path missing",
    )
    require(
        "this->authorization_binder_.grant" in execute_prepare,
        "executor authorization path missing",
    )
    require(
        "this->package_.prepare_candidate()" in execute_prepare,
        "executor package PREPARE path missing",
    )
    require(
        "this->driver_->prepare_candidate" in package_prepare,
        "package-to-driver PREPARE path missing",
    )
    require(
        "RamCredentialBundle bundle = bundle_from_candidate_(candidate)" in driver_prepare,
        "candidate-to-credential conversion missing",
    )
    require(
        "if (!bundle.valid())" in driver_prepare
        and "IsolatedDeviceDriverFailure::INVALID_CONFIGURATION" in driver_prepare,
        "driver credential validation rejection path missing",
    )
    require(
        "PairingClientCore::valid_local_host(this->broker_host)" in bundle_valid,
        "broker host local-only validation missing",
    )
    require(
        "PairingClientCore::valid_local_host(this->broker_tls_server_name)"
        in bundle_valid,
        "TLS server name local-only validation missing",
    )
    require(
        'ends_with(normalized, ".local")' in local_host_valid,
        "dot-local host rule missing",
    )
    require(
        "this->mqtt_->configure" not in driver_prepare,
        "MQTT unexpectedly present in driver PREPARE path",
    )
    require(
        "this->mqtt_->configure" in driver_validation,
        "MQTT validation path missing",
    )

    def valid_local_host(value: str) -> bool:
        if not value or len(value) > 253 or any(character.isspace() for character in value):
            return False
        normalized = value[:-1] if value.endswith(".") else value
        if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", normalized):
            octets = [int(item) for item in normalized.split(".")]
            if any(item > 255 for item in octets):
                return False
            first, second = octets[:2]
            return (
                first == 10
                or (first == 172 and 16 <= second <= 31)
                or (first == 192 and second == 168)
                or first == 127
                or (first == 169 and second == 254)
            )
        return normalized.endswith(".local") and len(normalized) >= 7

    require(not valid_local_host("stage2d9.invalid"), "dot-invalid model accepted")
    require(valid_local_host("stage2d9.local"), "dot-local model rejected")

    report = {
        "schema": "gh.h3.n2.stage2d9-v68-prepare-root-cause/1",
        "status": "pass",
        "artifact_generation": "V68",
        "root_cause": "candidate_host_contract_mismatch",
        "frozen_executor_host": "stage2d9.invalid",
        "frozen_executor_tls_server_name": "stage2d9.invalid",
        "outer_candidate_configuration_accepts_nonempty_host": True,
        "credential_bundle_requires_local_host": True,
        "dot_invalid_accepted_by_credential_bundle": False,
        "dot_local_accepted_by_credential_bundle": True,
        "rejection_location": "IsolatedDeviceDriver::prepare_candidate bundle.valid",
        "driver_failure": "invalid_configuration",
        "package_failure": "prepare_failed",
        "executor_failure": "command_execution",
        "mqtt_in_prepare_call_path": False,
        "null_mqtt_failure_hypothesis": "disproved",
        "runner_serial_log_persistence_defect": "independent_confirmed_observability_defect",
        "required_source_fix": "use a valid local-only placeholder host and retain stage-specific failure evidence",
        "device_accessed": False,
        "network_operation_attempted": False,
        "production_environment_modified": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
