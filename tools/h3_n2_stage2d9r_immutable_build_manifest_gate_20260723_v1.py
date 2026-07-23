#!/usr/bin/env python3
"""Fail-closed gate for Stage 2D-9R immutable build manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-immutable-build-manifest/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
LOCKED = "LOCKED_SOURCE"
FROZEN = "BUILD_FROZEN"
ALLOWED_STATES = {LOCKED, FROZEN}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"<[^>]+>")

FALSE_FLAGS = (
    "private_values_included",
    "private_paths_included",
    "execution_authorized",
    "board_operation_authorized",
    "serial_operation_authorized",
    "flash_operation_authorized",
    "physical_nvs_operation_authorized",
    "network_operation_authorized",
    "broker_operation_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "production_operation_authorized",
    "ready_authorized",
    "merge_authorized",
    "release_authorized",
)


class BuildManifestError(RuntimeError):
    """Raised when an immutable build manifest violates the contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildManifestError(message)


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


def hash_field(data: dict[str, Any], key: str) -> None:
    require(HEX64.fullmatch(str(data.get(key))) is not None, f"{key} invalid")


def validate(data: dict[str, Any], expected_state: str | None = None) -> str:
    require(data.get("schema") == SCHEMA, "schema mismatch")
    require(data.get("stage") == STAGE, "stage mismatch")
    state = data.get("state")
    require(state in ALLOWED_STATES, "state is not allowed")
    if expected_state is not None:
        require(state == expected_state, "state does not match expected state")
    require(data.get("esphome_version") == "2026.4.3", "ESPHome version mismatch")
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"{key} must be false")

    candidate = object_at(data, "candidate_bindings")
    require(candidate.get("broker_host") == "stage2d9r.local",
            "broker host mismatch")
    require(candidate.get("broker_tls_server_name") == "stage2d9r.local",
            "TLS server name mismatch")

    partition = object_at(data, "partition")
    require(partition.get("label") == "gh2d8_p2d9", "partition label mismatch")
    require(partition.get("address") == 0x400000, "partition address mismatch")
    require(partition.get("size_bytes") == 0x10000, "partition size mismatch")

    firmware = object_at(data, "firmware")
    require(
        firmware.get("flash_offsets")
        == {"bootloader": 0, "partition_table": 0x8000, "application": 0x10000},
        "flash offsets mismatch",
    )
    reproducibility = object_at(data, "reproducibility")
    artifact = object_at(data, "artifact")
    require(artifact.get("artifact_name") == "stage2d9r-g3r-immutable-locked-v1",
            "artifact name mismatch")
    require(artifact.get("expired") is False, "artifact must not be expired")

    if state == LOCKED:
        require(has_placeholder(data), "locked manifest must retain placeholders")
        require(data.get("compile_run_ids") == [], "locked compile runs must be empty")
        require(firmware.get("merged_image_size") is None,
                "locked merged image size must be null")
        require(reproducibility.get("clean_build_count") == 0,
                "locked clean build count must be zero")
        require(reproducibility.get("all_firmware_hashes_identical") is False,
                "locked firmware reproducibility must be false")
        require(reproducibility.get("all_manifest_hashes_identical") is False,
                "locked manifest reproducibility must be false")
        require(artifact.get("artifact_id") is None,
                "locked artifact id must be null")
        return LOCKED

    require(not has_placeholder(data), "frozen manifest has placeholders")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None,
            "source_sha invalid")
    require(HEX40.fullmatch(str(data.get("build_binding"))) is not None,
            "build_binding invalid")
    hash_field(data, "python_environment_sha256")
    hash_field(data, "compile_workflow_sha256")
    runs = data.get("compile_run_ids")
    require(isinstance(runs, list) and len(runs) == 2 and
            all(isinstance(item, int) and item > 0 for item in runs) and
            runs[0] != runs[1],
            "compile_run_ids must contain two unique positive ids")

    for key in ("ca_pem_sha256", "candidate_digest_sha256", "unlock_digest_sha256"):
        hash_field(candidate, key)
    hash_field(partition, "table_sha256")
    for key in (
        "bootloader_sha256",
        "partition_table_bin_sha256",
        "application_sha256",
        "merged_image_sha256",
    ):
        hash_field(firmware, key)
    require(isinstance(firmware.get("merged_image_size"), int) and
            0 < firmware["merged_image_size"] <= 0x400000,
            "merged image size invalid")
    require(reproducibility.get("clean_build_count") == 2,
            "frozen clean build count must be two")
    require(reproducibility.get("all_firmware_hashes_identical") is True,
            "firmware hashes are not reproducible")
    require(reproducibility.get("all_manifest_hashes_identical") is True,
            "manifest hashes are not reproducible")
    require(isinstance(artifact.get("artifact_id"), int) and
            artifact["artifact_id"] > 0,
            "artifact id invalid")
    hash_field(artifact, "artifact_sha256")
    hash_field(artifact, "manifest_sha256")
    return FROZEN


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-state", choices=sorted(ALLOWED_STATES))
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        state = validate(data, args.expect_state)
    except Exception as exc:  # fail-closed CLI boundary
        print("STAGE2D9R_IMMUTABLE_BUILD_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_IMMUTABLE_BUILD_GATE=PASS")
    print(f"STATE={state}")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    print("READY_AUTHORIZED=false")
    print("MERGE_AUTHORIZED=false")
    print("RELEASE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
