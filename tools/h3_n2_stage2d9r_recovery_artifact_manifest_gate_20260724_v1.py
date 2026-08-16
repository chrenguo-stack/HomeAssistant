#!/usr/bin/env python3
"""Fail-closed validator for the frozen Stage2D9R locked recovery Artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-artifact-manifest/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
STATE = "RECOVERY_ARTIFACT_FROZEN"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
FALSE_KEYS = (
    "private_values_included", "private_paths_included",
    "authorization_record_included", "consumed_marker_included",
    "execution_authorized", "recovery_authorized",
    "board_operation_authorized", "serial_operation_authorized",
    "flash_operation_authorized", "physical_nvs_operation_authorized",
    "network_operation_authorized", "broker_operation_authorized",
    "firmware_flash_authorized", "prepare_authorized",
    "verify_authorized", "activate_authorized", "cleanup_authorized",
    "efuse_operation_authorized", "secure_boot_change_authorized",
    "flash_encryption_change_authorized", "production_operation_authorized",
    "ready_authorized", "merge_authorized", "release_authorized",
    "deployment_authorized",
)


class RecoveryArtifactGateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryArtifactGateError(message)


def object_at(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    require(isinstance(value, dict), f"{key} must be an object")
    return value


def validate(data: dict[str, Any]) -> None:
    require(data.get("schema") == SCHEMA, "schema mismatch")
    require(data.get("stage") == STAGE, "stage mismatch")
    require(data.get("state") == STATE, "state mismatch")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None,
            "source SHA invalid")

    runs = data.get("build_run_ids")
    require(isinstance(runs, list) and len(runs) == 2 and
            all(isinstance(item, int) and item > 0 for item in runs) and
            runs[0] != runs[1], "independent build run ids invalid")

    artifact = object_at(data, "artifact")
    require(isinstance(artifact.get("canonical_artifact_id"), int) and
            artifact["canonical_artifact_id"] > 0,
            "canonical artifact id invalid")
    require(isinstance(artifact.get("repro_artifact_id"), int) and
            artifact["repro_artifact_id"] > 0 and
            artifact["repro_artifact_id"] != artifact["canonical_artifact_id"],
            "repro artifact id invalid")
    require(artifact.get("canonical_artifact_name") ==
            "stage2d9r-g3r-recovery-locked-v1",
            "canonical artifact name mismatch")
    require(artifact.get("repro_artifact_name") ==
            "stage2d9r-g3r-recovery-repro-v1",
            "repro artifact name mismatch")
    for key in (
        "payload_tar_sha256", "descriptor_sha256",
        "erased_image_sha256", "manifest_sha256",
    ):
        require(HEX64.fullmatch(str(artifact.get(key))) is not None,
                f"{key} invalid")
    require(artifact.get("erased_image_sha256") == ERASED_SHA256,
            "erased image digest mismatch")
    require(artifact.get("manifest_digest_algorithm") ==
            "sha256-canonical-json-without-artifact.manifest_sha256-v1",
            "manifest digest algorithm mismatch")

    copy = json.loads(json.dumps(data))
    observed = copy["artifact"].pop("manifest_sha256")
    calculated = hashlib.sha256(json.dumps(
        copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    require(observed == calculated, "manifest digest mismatch")

    immutable = object_at(data, "immutable_firmware_binding")
    require(immutable == {
        "source_sha": "c9e8447c24b0f09f3eac3f56791f2346e8aa5d61",
        "build_binding": "b39f20c55b865ec87eb650d620fd1a82b930c1ad",
        "artifact_id": 8585140964,
        "artifact_name": "stage2d9r-g3r-immutable-locked-v1",
        "artifact_sha256":
            "5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3",
        "application_sha256":
            "7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630",
        "merged_image_sha256":
            "ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f",
    }, "immutable firmware binding mismatch")

    candidate = object_at(data, "candidate_bindings")
    require(candidate == {
        "unlock_digest_sha256":
            "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3",
        "ca_pem_sha256":
            "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963",
        "candidate_digest_sha256":
            "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5",
    }, "candidate binding mismatch")

    partition = object_at(data, "recovery_partition")
    require(partition == {
        "label": "gh2d8_p2d9",
        "namespace": "gh2d8_s2d9",
        "address": 0x400000,
        "size_bytes": 65536,
        "erased_byte": 0xFF,
        "erased_image_sha256": ERASED_SHA256,
        "partition_table_sha256":
            "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8",
    }, "recovery partition mismatch")

    reproducibility = object_at(data, "reproducibility")
    require(reproducibility == {
        "clean_build_count": 2,
        "payloads_byte_identical": True,
        "descriptor_digests_identical": True,
        "erased_image_digests_identical": True,
    }, "reproducibility proof mismatch")

    reviewed = object_at(data, "reviewed_inputs")
    require(set(reviewed) == {
        "immutable_manifest_sha256", "recovery_template_sha256",
        "recovery_contract_sha256", "recovery_gate_sha256",
    }, "reviewed input set mismatch")
    for key, value in reviewed.items():
        require(HEX64.fullmatch(str(value)) is not None, f"{key} invalid")

    for key in FALSE_KEYS:
        require(data.get(key) is False, f"{key} must be false")

    serialized = json.dumps(data, sort_keys=True)
    for prohibited in (
        "/dev/", "/Users/", "/private/tmp/", "BEGIN PRIVATE KEY",
        "unlock-token.hex", "mqtt_password",
    ):
        require(prohibited not in serialized, f"private material leaked: {prohibited}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate(data)
    except Exception as exc:
        print("STAGE2D9R_RECOVERY_ARTIFACT_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2
    print("STAGE2D9R_RECOVERY_ARTIFACT_GATE=PASS")
    print(f"STATE={STATE}")
    print("REPRODUCIBLE=true")
    print("RECOVERY_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
