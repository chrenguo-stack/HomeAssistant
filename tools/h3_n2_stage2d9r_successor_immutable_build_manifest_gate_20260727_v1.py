#!/usr/bin/env python3
"""Fail-closed gate for Stage2D9R successor immutable build manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-successor-immutable-build-manifest/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
STATE = "BUILD_FROZEN"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
ARTIFACT_NAME = "stage2d9r-g3r-successor-immutable-locked-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FALSE_FLAGS = (
    "private_values_included",
    "private_paths_included",
    "secret_values_included",
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


class ManifestError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def object_at(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    require(isinstance(value, dict), f"{key} must be an object")
    return value


def hash_field(data: dict[str, Any], key: str) -> None:
    require(HEX64.fullmatch(str(data.get(key))) is not None, f"{key} invalid")


def manifest_digest(manifest: dict[str, Any]) -> str:
    copy = json.loads(json.dumps(manifest))
    copy["artifact"].pop("manifest_sha256", None)
    canonical = json.dumps(
        copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate(data: dict[str, Any]) -> None:
    require(data.get("schema") == SCHEMA, "schema mismatch")
    require(data.get("stage") == STAGE, "stage mismatch")
    require(data.get("state") == STATE, "state mismatch")
    require(data.get("esphome_version") == "2026.4.3", "ESPHome version mismatch")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None, "source_sha invalid")
    require(data.get("build_binding") == BUILD_BINDING, "build binding mismatch")
    hash_field(data, "python_environment_sha256")
    hash_field(data, "compile_workflow_sha256")
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"{key} must be false")

    runs = data.get("compile_run_ids")
    require(
        isinstance(runs, list)
        and len(runs) == 2
        and all(isinstance(item, int) and item > 0 for item in runs)
        and runs[0] != runs[1],
        "compile run ids invalid",
    )

    source_inputs = object_at(data, "source_inputs")
    for key in (
        "final_target_sha256",
        "build_binding_file_sha256",
        "public_descriptor_sha256",
        "public_pki_export_binding_sha256",
        "source_lock_acceptance_sha256",
        "partition_table_csv_sha256",
    ):
        hash_field(source_inputs, key)

    candidate = object_at(data, "candidate_bindings")
    require(candidate.get("broker_host") == "stage2d9r.local", "broker host mismatch")
    require(
        candidate.get("broker_tls_server_name") == "stage2d9r.local",
        "TLS server name mismatch",
    )
    for key in (
        "ca_pem_sha256",
        "candidate_digest_sha256",
        "unlock_digest_sha256",
        "broker_certificate_der_sha256",
        "broker_spki_sha256",
    ):
        hash_field(candidate, key)

    partition = object_at(data, "partition")
    require(partition.get("label") == "gh2d8_p2d9", "partition label mismatch")
    require(partition.get("address") == 0x400000, "partition address mismatch")
    require(partition.get("size_bytes") == 0x10000, "partition size mismatch")
    hash_field(partition, "table_sha256")

    firmware = object_at(data, "firmware")
    require(
        firmware.get("flash_offsets")
        == {"bootloader": 0, "partition_table": 0x8000, "application": 0x10000},
        "flash offsets mismatch",
    )
    for key in (
        "bootloader_sha256",
        "partition_table_bin_sha256",
        "application_sha256",
        "merged_image_sha256",
    ):
        hash_field(firmware, key)
    require(
        isinstance(firmware.get("merged_image_size"), int)
        and 0 < firmware["merged_image_size"] <= 0x400000,
        "merged image size invalid",
    )

    reproducibility = object_at(data, "reproducibility")
    require(reproducibility.get("clean_build_count") == 2, "clean build count mismatch")
    for key in (
        "all_firmware_hashes_identical",
        "all_manifest_hashes_identical",
        "all_payload_bytes_identical",
    ):
        require(reproducibility.get(key) is True, f"{key} must be true")

    artifact = object_at(data, "artifact")
    require(artifact.get("artifact_name") == ARTIFACT_NAME, "artifact name mismatch")
    require(
        isinstance(artifact.get("artifact_id"), int) and artifact["artifact_id"] > 0,
        "artifact id invalid",
    )
    require(artifact.get("expired") is False, "artifact must not be expired")
    hash_field(artifact, "artifact_sha256")
    hash_field(artifact, "manifest_sha256")
    require(
        artifact["manifest_sha256"] == manifest_digest(data),
        "manifest digest mismatch",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate(data)
    except Exception as exc:
        print("STAGE2D9R_SUCCESSOR_IMMUTABLE_BUILD_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_SUCCESSOR_IMMUTABLE_BUILD_GATE=PASS")
    print("STATE=BUILD_FROZEN")
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
