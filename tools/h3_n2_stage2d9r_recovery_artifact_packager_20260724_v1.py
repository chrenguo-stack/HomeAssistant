#!/usr/bin/env python3
"""Build a deterministic, public-only locked Stage2D9R recovery payload."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-artifact/1"
BUILD_RECORD_SCHEMA = "gh.h3.n2.stage2d9r-locked-recovery-clean-build/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
STATE = "RECOVERY_ARTIFACT_LOCKED"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ERASED_SIZE = 65536
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
IMMUTABLE_SOURCE_SHA = "c9e8447c24b0f09f3eac3f56791f2346e8aa5d61"
IMMUTABLE_ARTIFACT_ID = 8585140964
IMMUTABLE_ARTIFACT_NAME = "stage2d9r-g3r-immutable-locked-v1"
IMMUTABLE_ARTIFACT_SHA256 = "5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3"
APPLICATION_SHA256 = "7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630"
MERGED_IMAGE_SHA256 = "ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f"
BUILD_BINDING = "b39f20c55b865ec87eb650d620fd1a82b930c1ad"
UNLOCK_DIGEST = "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3"
CA_PEM_SHA256 = "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963"
CANDIDATE_DIGEST = "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5"
PARTITION_TABLE_SHA256 = "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8"
FALSE_FLAGS = {
    "private_values_included": False,
    "private_paths_included": False,
    "authorization_record_included": False,
    "consumed_marker_included": False,
    "execution_authorized": False,
    "recovery_authorized": False,
    "board_operation_authorized": False,
    "serial_operation_authorized": False,
    "flash_operation_authorized": False,
    "physical_nvs_operation_authorized": False,
    "network_operation_authorized": False,
    "broker_operation_authorized": False,
    "firmware_flash_authorized": False,
    "prepare_authorized": False,
    "verify_authorized": False,
    "activate_authorized": False,
    "cleanup_authorized": False,
    "efuse_operation_authorized": False,
    "secure_boot_change_authorized": False,
    "flash_encryption_change_authorized": False,
    "production_operation_authorized": False,
    "ready_authorized": False,
    "merge_authorized": False,
    "release_authorized": False,
    "deployment_authorized": False,
}


class RecoveryPackagingError(RuntimeError):
    """Raised when a locked recovery package violates its reviewed boundary."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryPackagingError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, "output mode mismatch")


def canonical_json(data: object) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def deterministic_tar(path: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    os.chmod(path, 0o600)


def validate_immutable_manifest(data: dict[str, Any]) -> None:
    require(data.get("schema") == "gh.h3.n2.stage2d9r-immutable-build-manifest/1",
            "immutable manifest schema mismatch")
    require(data.get("state") == "BUILD_FROZEN",
            "immutable manifest is not frozen")
    require(data.get("source_sha") == IMMUTABLE_SOURCE_SHA,
            "immutable source SHA mismatch")
    require(data.get("build_binding") == BUILD_BINDING,
            "immutable build binding mismatch")
    artifact = data.get("artifact")
    require(isinstance(artifact, dict), "immutable artifact binding missing")
    require(artifact.get("artifact_id") == IMMUTABLE_ARTIFACT_ID,
            "immutable artifact id mismatch")
    require(artifact.get("artifact_name") == IMMUTABLE_ARTIFACT_NAME,
            "immutable artifact name mismatch")
    require(artifact.get("artifact_sha256") == IMMUTABLE_ARTIFACT_SHA256,
            "immutable artifact digest mismatch")
    firmware = data.get("firmware")
    require(isinstance(firmware, dict), "immutable firmware binding missing")
    require(firmware.get("application_sha256") == APPLICATION_SHA256,
            "application digest mismatch")
    require(firmware.get("merged_image_sha256") == MERGED_IMAGE_SHA256,
            "merged image digest mismatch")
    candidate = data.get("candidate_bindings")
    require(isinstance(candidate, dict), "candidate bindings missing")
    require(candidate.get("unlock_digest_sha256") == UNLOCK_DIGEST,
            "unlock digest mismatch")
    require(candidate.get("ca_pem_sha256") == CA_PEM_SHA256,
            "CA digest mismatch")
    require(candidate.get("candidate_digest_sha256") == CANDIDATE_DIGEST,
            "candidate digest mismatch")
    partition = data.get("partition")
    require(isinstance(partition, dict), "partition binding missing")
    require(partition.get("address") == 0x400000, "partition address mismatch")
    require(partition.get("size_bytes") == ERASED_SIZE, "partition size mismatch")
    require(partition.get("table_sha256") == PARTITION_TABLE_SHA256,
            "partition table digest mismatch")


def validate_locked_template(data: dict[str, Any]) -> None:
    require(data.get("schema") ==
            "gh.h3.n2.stage2d9r-test-partition-recovery-manifest/1",
            "recovery template schema mismatch")
    require(data.get("state") == "LOCKED_TEMPLATE",
            "recovery template is not locked")
    partition = data.get("partition")
    require(isinstance(partition, dict), "recovery partition missing")
    require(partition == {
        "label": "gh2d8_p2d9",
        "namespace": "gh2d8_s2d9",
        "address": 0x400000,
        "size_bytes": ERASED_SIZE,
        "expected_erased_byte": 0xFF,
        "expected_erased_sha256": ERASED_SHA256,
    }, "recovery partition contract mismatch")
    require(data.get("recovery_authorized") is False,
            "locked template authorizes recovery")
    require(data.get("board_operation_authorized") is False,
            "locked template authorizes board operation")
    require(data.get("serial_operation_authorized") is False,
            "locked template authorizes serial operation")
    require(data.get("flash_operation_authorized") is False,
            "locked template authorizes flash operation")
    serialized = json.dumps(data, sort_keys=True)
    require("<SOURCE_SHA40>" in serialized, "locked template lost placeholders")
    require("/dev/" not in serialized and "/Users/" not in serialized,
            "private host path leaked into template")


def build_payload(
    *,
    immutable_manifest_path: Path,
    recovery_template_path: Path,
    recovery_contract_path: Path,
    recovery_gate_path: Path,
    source_sha: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    require(HEX40.fullmatch(source_sha) is not None, "source SHA invalid")
    immutable_bytes = immutable_manifest_path.read_bytes()
    template_bytes = recovery_template_path.read_bytes()
    contract_bytes = recovery_contract_path.read_bytes()
    gate_bytes = recovery_gate_path.read_bytes()
    immutable = json.loads(immutable_bytes)
    template = json.loads(template_bytes)
    validate_immutable_manifest(immutable)
    validate_locked_template(template)
    contract_text = contract_bytes.decode("utf-8")
    require("This document is a source/review contract." in contract_text,
            "recovery contract boundary statement missing")
    gate_text = gate_bytes.decode("utf-8")
    for prohibited in ("subprocess", "import serial", "import socket"):
        require(prohibited not in gate_text,
                f"recovery gate contains executable operation: {prohibited}")

    erased = b"\xff" * ERASED_SIZE
    require(sha256_bytes(erased) == ERASED_SHA256,
            "erased recovery image digest mismatch")
    descriptor: dict[str, Any] = {
        "schema": SCHEMA,
        "stage": STAGE,
        "state": STATE,
        "source_sha": source_sha,
        "package_format": "deterministic-ustar-v1",
        "immutable_firmware_binding": {
            "source_sha": IMMUTABLE_SOURCE_SHA,
            "build_binding": BUILD_BINDING,
            "artifact_id": IMMUTABLE_ARTIFACT_ID,
            "artifact_name": IMMUTABLE_ARTIFACT_NAME,
            "artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
            "application_sha256": APPLICATION_SHA256,
            "merged_image_sha256": MERGED_IMAGE_SHA256,
        },
        "candidate_bindings": {
            "unlock_digest_sha256": UNLOCK_DIGEST,
            "ca_pem_sha256": CA_PEM_SHA256,
            "candidate_digest_sha256": CANDIDATE_DIGEST,
        },
        "recovery_partition": {
            "label": "gh2d8_p2d9",
            "namespace": "gh2d8_s2d9",
            "address": 0x400000,
            "size_bytes": ERASED_SIZE,
            "erased_byte": 0xFF,
            "erased_image_sha256": ERASED_SHA256,
            "partition_table_sha256": PARTITION_TABLE_SHA256,
        },
        "reviewed_inputs": {
            "immutable_manifest_sha256": sha256_bytes(immutable_bytes),
            "recovery_template_sha256": sha256_bytes(template_bytes),
            "recovery_contract_sha256": sha256_bytes(contract_bytes),
            "recovery_gate_sha256": sha256_bytes(gate_bytes),
        },
        "allowed_future_operation": "ERASE_EXACT_TEST_PARTITION_ONLY_UNDER_FUTURE_D2",
        "allowed_counts": {
            "pre_read": 1,
            "erase_region": 1,
            "post_read": 1,
            "firmware_flash": 0,
            "full_chip_erase": 0,
            "prepare_command": 0,
            "verify_command": 0,
            "activate_command": 0,
            "cleanup_command": 0,
        },
        **FALSE_FLAGS,
    }
    descriptor_bytes = json.dumps(
        descriptor, indent=2, sort_keys=True, ensure_ascii=False
    ).encode() + b"\n"
    files = {
        "RECOVERY_CONTRACT.md": contract_bytes,
        "recovery-artifact-descriptor.json": descriptor_bytes,
        "recovery-authorization-manifest.template.json": template_bytes,
        "test-partition-erased.bin": erased,
    }
    sums = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    ).encode()
    files["SHA256SUMS"] = sums
    return descriptor, files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--immutable-manifest", type=Path, required=True)
    parser.add_argument("--recovery-template", type=Path, required=True)
    parser.add_argument("--recovery-contract", type=Path, required=True)
    parser.add_argument("--recovery-gate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--lane", choices=("a", "b"), required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()

    require(args.run_id > 0, "run id invalid")
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "output directory already exists")
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)

    descriptor, files = build_payload(
        immutable_manifest_path=args.immutable_manifest.resolve(strict=True),
        recovery_template_path=args.recovery_template.resolve(strict=True),
        recovery_contract_path=args.recovery_contract.resolve(strict=True),
        recovery_gate_path=args.recovery_gate.resolve(strict=True),
        source_sha=args.source_sha,
    )
    tar_path = output / "stage2d9r-g3r-recovery-payload-v1.tar"
    deterministic_tar(tar_path, files)
    payload_sha = sha256_file(tar_path)
    record = {
        "schema": BUILD_RECORD_SCHEMA,
        "stage": STAGE,
        "lane": args.lane,
        "artifact_name": args.artifact_name,
        "source_sha": args.source_sha,
        "run_id": args.run_id,
        "payload_tar_sha256": payload_sha,
        "descriptor_sha256": sha256_bytes(files["recovery-artifact-descriptor.json"]),
        "erased_image_sha256": ERASED_SHA256,
        "immutable_firmware_artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "reviewed_inputs": descriptor["reviewed_inputs"],
        **FALSE_FLAGS,
    }
    record_bytes = json.dumps(record, indent=2, sort_keys=True).encode() + b"\n"
    write_private(output / "build-record.json", record_bytes)
    write_private(output / "payload-tar.sha256", (payload_sha + "\n").encode())

    print("STAGE2D9R_LOCKED_RECOVERY_CLEAN_BUILD=PASS")
    print(f"LANE={args.lane}")
    print(f"SOURCE_SHA={args.source_sha}")
    print(f"RUN_ID={args.run_id}")
    print(f"PAYLOAD_TAR_SHA256={payload_sha}")
    print(f"ERASED_IMAGE_SHA256={ERASED_SHA256}")
    print("RECOVERY_AUTHORIZED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
