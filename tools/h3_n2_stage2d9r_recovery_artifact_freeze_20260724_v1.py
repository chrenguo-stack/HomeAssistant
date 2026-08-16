#!/usr/bin/env python3
"""Compare two clean locked recovery builds and freeze their public manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R"
MANIFEST_SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-artifact-manifest/1"
BUILD_RECORD_SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-clean-build/1"
DESCRIPTOR_SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-artifact/1"
STATE = "RECOVERY_ARTIFACT_FROZEN"
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
IMMUTABLE_SOURCE_SHA = "c9e8447c24b0f09f3eac3f56791f2346e8aa5d61"
IMMUTABLE_ARTIFACT_ID = 8585140964
IMMUTABLE_ARTIFACT_SHA256 = "5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3"
APPLICATION_SHA256 = "7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630"
MERGED_IMAGE_SHA256 = "ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f"
FALSE_KEYS = (
    "private_values_included",
    "private_paths_included",
    "authorization_record_included",
    "consumed_marker_included",
    "execution_authorized",
    "recovery_authorized",
    "board_operation_authorized",
    "serial_operation_authorized",
    "flash_operation_authorized",
    "physical_nvs_operation_authorized",
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
    "ready_authorized",
    "merge_authorized",
    "release_authorized",
    "deployment_authorized",
)


class RecoveryFreezeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryFreezeError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, "output mode mismatch")


def locate(root: Path, name: str) -> Path:
    matches = sorted(path.resolve() for path in root.rglob(name) if path.is_file())
    require(len(matches) == 1, f"expected exactly one {name}, got {len(matches)}")
    return matches[0]


def read_record(root: Path) -> tuple[dict[str, Any], Path]:
    path = locate(root, "build-record.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("schema") == BUILD_RECORD_SCHEMA, "build record schema mismatch")
    return value, path


def inspect_payload(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    with tarfile.open(path, "r") as archive:
        members = archive.getmembers()
        expected = {
            "RECOVERY_CONTRACT.md",
            "SHA256SUMS",
            "recovery-artifact-descriptor.json",
            "recovery-authorization-manifest.template.json",
            "test-partition-erased.bin",
        }
        require({member.name for member in members} == expected,
                "recovery payload member set mismatch")
        for member in members:
            require(member.isfile(), "recovery payload contains non-file member")
            require(member.mode == 0o600, "recovery payload member mode mismatch")
            require(member.uid == 0 and member.gid == 0,
                    "recovery payload ownership metadata mismatch")
            require(member.mtime == 0, "recovery payload timestamp is not deterministic")
        extracted: dict[str, bytes] = {}
        for member in members:
            handle = archive.extractfile(member)
            require(handle is not None, "cannot read recovery payload member")
            extracted[member.name] = handle.read()

    descriptor = json.loads(extracted["recovery-artifact-descriptor.json"])
    require(descriptor.get("schema") == DESCRIPTOR_SCHEMA,
            "recovery descriptor schema mismatch")
    require(descriptor.get("state") == "RECOVERY_ARTIFACT_LOCKED",
            "recovery descriptor state mismatch")
    require(
        sha256_bytes(extracted["test-partition-erased.bin"]) == ERASED_SHA256,
        "erased image digest mismatch",
    )
    require(extracted["test-partition-erased.bin"] == b"\xff" * 65536,
            "erased image is not all 0xff")
    sums: dict[str, str] = {}
    for line in extracted["SHA256SUMS"].decode("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        require(name in extracted and name != "SHA256SUMS",
                "SHA256SUMS references unexpected member")
        require(sha256_bytes(extracted[name]) == digest,
                f"SHA256SUMS mismatch for {name}")
        sums[name] = digest
    require(set(sums) == set(extracted) - {"SHA256SUMS"},
            "SHA256SUMS member coverage mismatch")
    for key in FALSE_KEYS:
        require(descriptor.get(key) is False, f"{key} must be false")
    serialized = json.dumps(descriptor, sort_keys=True)
    for prohibited in (
        "/dev/", "/Users/", "/private/tmp/", "BEGIN PRIVATE KEY",
        "unlock-token.hex", "mqtt_password",
    ):
        require(prohibited not in serialized,
                f"private or executable material leaked: {prohibited}")
    return descriptor, sums


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--run-a", type=int, required=True)
    parser.add_argument("--run-b", type=int, required=True)
    parser.add_argument("--artifact-a-id", type=int, required=True)
    parser.add_argument("--artifact-b-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    require(args.run_a > 0 and args.run_b > 0 and args.run_a != args.run_b,
            "independent run ids invalid")
    require(args.artifact_a_id > 0 and args.artifact_b_id > 0 and
            args.artifact_a_id != args.artifact_b_id,
            "independent artifact ids invalid")
    require(len(args.source_sha) == 40 and
            all(char in "0123456789abcdef" for char in args.source_sha),
            "source SHA invalid")

    a_root = args.build_a.resolve(strict=True)
    b_root = args.build_b.resolve(strict=True)
    a_tar = locate(a_root, "stage2d9r-g3r-recovery-payload-v1.tar")
    b_tar = locate(b_root, "stage2d9r-g3r-recovery-payload-v1.tar")
    a_bytes = a_tar.read_bytes()
    b_bytes = b_tar.read_bytes()
    require(a_bytes == b_bytes, "independent recovery payloads are not byte-identical")
    payload_sha = sha256_bytes(a_bytes)

    a_record, a_record_path = read_record(a_root)
    b_record, b_record_path = read_record(b_root)
    require(a_record.get("lane") == "a" and b_record.get("lane") == "b",
            "build lanes are not independent")
    require(a_record.get("run_id") == args.run_a, "build A run binding mismatch")
    require(b_record.get("run_id") == args.run_b, "build B run binding mismatch")
    require(a_record.get("source_sha") == args.source_sha and
            b_record.get("source_sha") == args.source_sha,
            "recovery build source SHA mismatch")
    require(a_record.get("payload_tar_sha256") == payload_sha and
            b_record.get("payload_tar_sha256") == payload_sha,
            "recovery payload digest binding mismatch")
    require(a_record.get("artifact_name") ==
            "stage2d9r-g3r-recovery-locked-v1",
            "canonical recovery artifact name mismatch")
    require(b_record.get("artifact_name") ==
            "stage2d9r-g3r-recovery-repro-v1",
            "repro recovery artifact name mismatch")
    for record in (a_record, b_record):
        for key in FALSE_KEYS:
            require(record.get(key) is False, f"{key} must be false in build record")

    descriptor, sums = inspect_payload(a_tar)
    require(descriptor.get("source_sha") == args.source_sha,
            "descriptor source SHA mismatch")
    immutable = descriptor.get("immutable_firmware_binding")
    require(isinstance(immutable, dict), "immutable firmware binding missing")
    require(immutable == {
        "source_sha": IMMUTABLE_SOURCE_SHA,
        "build_binding": "b39f20c55b865ec87eb650d620fd1a82b930c1ad",
        "artifact_id": IMMUTABLE_ARTIFACT_ID,
        "artifact_name": "stage2d9r-g3r-immutable-locked-v1",
        "artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "application_sha256": APPLICATION_SHA256,
        "merged_image_sha256": MERGED_IMAGE_SHA256,
    }, "immutable firmware binding mismatch")

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "stage": STAGE,
        "state": STATE,
        "source_sha": args.source_sha,
        "build_run_ids": [args.run_a, args.run_b],
        "artifact": {
            "canonical_artifact_id": args.artifact_a_id,
            "canonical_artifact_name": "stage2d9r-g3r-recovery-locked-v1",
            "repro_artifact_id": args.artifact_b_id,
            "repro_artifact_name": "stage2d9r-g3r-recovery-repro-v1",
            "payload_tar_sha256": payload_sha,
            "descriptor_sha256": sums["recovery-artifact-descriptor.json"],
            "erased_image_sha256": ERASED_SHA256,
            "manifest_digest_algorithm":
                "sha256-canonical-json-without-artifact.manifest_sha256-v1",
        },
        "immutable_firmware_binding": immutable,
        "candidate_bindings": descriptor["candidate_bindings"],
        "recovery_partition": descriptor["recovery_partition"],
        "reviewed_inputs": descriptor["reviewed_inputs"],
        "reproducibility": {
            "clean_build_count": 2,
            "payloads_byte_identical": True,
            "descriptor_digests_identical": True,
            "erased_image_digests_identical": True,
        },
        **{key: False for key in FALSE_KEYS},
    }
    canonical = json.loads(json.dumps(manifest))
    manifest_sha = sha256_bytes(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode())
    manifest["artifact"]["manifest_sha256"] = manifest_sha
    manifest_bytes = json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=False
    ).encode() + b"\n"

    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "output directory already exists")
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)
    write_private(
        output / "stage2d9r_recovery_artifact_manifest_20260724_v1.json",
        manifest_bytes,
    )
    write_private(output / "stage2d9r-g3r-recovery-payload-v1.tar", a_bytes)
    write_private(output / "build-a-record.json", a_record_path.read_bytes())
    write_private(output / "build-b-record.json", b_record_path.read_bytes())
    files = sorted(path for path in output.iterdir() if path.is_file())
    sums_bytes = "".join(
        f"{sha256_file(path)}  {path.name}\n" for path in files
    ).encode()
    write_private(output / "SHA256SUMS", sums_bytes)

    print("STAGE2D9R_LOCKED_RECOVERY_FREEZE=PASS")
    print(f"SOURCE_SHA={args.source_sha}")
    print(f"RUN_A={args.run_a}")
    print(f"RUN_B={args.run_b}")
    print(f"CANONICAL_ARTIFACT_ID={args.artifact_a_id}")
    print(f"REPRO_ARTIFACT_ID={args.artifact_b_id}")
    print(f"PAYLOAD_TAR_SHA256={payload_sha}")
    print(f"MANIFEST_SHA256={manifest_sha}")
    print("REPRODUCIBLE=true")
    print("RECOVERY_AUTHORIZED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
