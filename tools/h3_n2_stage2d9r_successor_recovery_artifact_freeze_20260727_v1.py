#!/usr/bin/env python3
"""Compare two successor recovery builds and freeze a canonical public package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
from typing import Any

PAYLOAD_NAME = "stage2d9r-g3r-successor-recovery-payload-v1.tar"
EXPECTED_OUTER = {"build-record.json", "payload-tar.sha256", PAYLOAD_NAME}
EXPECTED_MEMBERS = {
    "RECOVERY_CONTRACT.md",
    "SHA256SUMS",
    "recovery-artifact-descriptor.json",
    "recovery-authorization-manifest.template.json",
    "test-partition-erased.bin",
}
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-artifact/1"
BUILD_SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-clean-build/1"
FREEZE_SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-freeze/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"


class FreezeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FreezeError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_sums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        require(len(digest) == 64 and name not in result, "SHA256SUMS_INVALID")
        result[name] = digest
    return result


def validate_build(root: Path) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    require(root.is_dir() and not root.is_symlink(), "BUILD_ROOT_INVALID")
    require({p.name for p in root.iterdir()} == EXPECTED_OUTER,
            "BUILD_OUTER_INVENTORY_MISMATCH")
    record_path = root / "build-record.json"
    digest_path = root / "payload-tar.sha256"
    tar_path = root / PAYLOAD_NAME
    for path in (record_path, digest_path, tar_path):
        require(path.is_file() and not path.is_symlink(), "BUILD_FILE_INVALID")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    require(isinstance(record, dict), "BUILD_RECORD_NOT_OBJECT")
    require(record.get("schema") == BUILD_SCHEMA, "BUILD_RECORD_SCHEMA_MISMATCH")
    require(record.get("stage") == STAGE, "BUILD_RECORD_STAGE_MISMATCH")
    require(record.get("state") == "CLEAN_BUILD_COMPLETE", "BUILD_RECORD_STATE_MISMATCH")
    for key in (
        "private_values_included", "private_paths_included", "secret_values_included",
        "authorization_created", "execution_authorized", "recovery_authorized",
        "board_operation_authorized", "serial_operation_authorized", "flash_operation_authorized",
    ):
        require(record.get(key) is False,
                f"BUILD_RECORD_BOUNDARY_EXPANDED_{key.upper()}")
    tar_bytes = tar_path.read_bytes()
    payload_sha = sha256_bytes(tar_bytes)
    require(digest_path.read_text().strip() == payload_sha,
            "PAYLOAD_DIGEST_TEXT_MISMATCH")
    require(record.get("payload_tar_sha256") == payload_sha,
            "BUILD_RECORD_PAYLOAD_DIGEST_MISMATCH")
    files: dict[str, bytes] = {}
    with tarfile.open(tar_path, "r") as archive:
        members = archive.getmembers()
        require({m.name for m in members} == EXPECTED_MEMBERS,
                "PAYLOAD_INVENTORY_MISMATCH")
        require(len(members) == len(EXPECTED_MEMBERS),
                "PAYLOAD_DUPLICATE_MEMBER")
        for member in members:
            require(
                member.isfile() and member.mode == 0o600 and member.uid == 0
                and member.gid == 0 and member.mtime == 0 and member.uname == ""
                and member.gname == "",
                "PAYLOAD_TAR_METADATA_MISMATCH",
            )
            handle = archive.extractfile(member)
            require(handle is not None, "PAYLOAD_MEMBER_UNREADABLE")
            files[member.name] = handle.read()
    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == EXPECTED_MEMBERS - {"SHA256SUMS"},
            "SHA256SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest,
                "PAYLOAD_MEMBER_DIGEST_MISMATCH")
    require(sha256_bytes(files["test-partition-erased.bin"]) == ERASED_SHA256,
            "ERASED_IMAGE_DIGEST_MISMATCH")
    descriptor = json.loads(files["recovery-artifact-descriptor.json"])
    require(descriptor.get("schema") == SCHEMA, "DESCRIPTOR_SCHEMA_MISMATCH")
    require(descriptor.get("stage") == STAGE, "DESCRIPTOR_STAGE_MISMATCH")
    require(descriptor.get("state") == "SUCCESSOR_RECOVERY_ARTIFACT_LOCKED",
            "DESCRIPTOR_STATE_MISMATCH")
    for key in (
        "private_values_included", "private_paths_included", "secret_values_included",
        "authorization_record_included", "consumed_marker_included", "execution_authorized",
        "recovery_authorized", "board_operation_authorized", "serial_operation_authorized",
        "flash_operation_authorized", "physical_nvs_operation_authorized",
        "network_operation_authorized", "broker_operation_authorized", "firmware_flash_authorized",
        "prepare_authorized", "verify_authorized", "activate_authorized", "cleanup_authorized",
        "efuse_operation_authorized", "secure_boot_change_authorized",
        "flash_encryption_change_authorized", "production_operation_authorized",
        "ready_authorized", "merge_authorized", "release_authorized", "tag_authorized",
        "deployment_authorized",
    ):
        require(descriptor.get(key) is False,
                f"DESCRIPTOR_BOUNDARY_EXPANDED_{key.upper()}")
    return record, tar_bytes, files


def freeze(build_a: Path, build_b: Path, output_dir: Path,
           source_sha: str) -> dict[str, Any]:
    require(not output_dir.exists(), "OUTPUT_ALREADY_EXISTS")
    record_a, tar_a, files_a = validate_build(build_a)
    record_b, tar_b, files_b = validate_build(build_b)
    require(record_a.get("source_sha") == source_sha == record_b.get("source_sha"),
            "SOURCE_SHA_MISMATCH")
    require(record_a.get("lane") == "a" and record_b.get("lane") == "b",
            "LANE_MISMATCH")
    require(record_a.get("run_id") != record_b.get("run_id"),
            "RUN_ID_NOT_INDEPENDENT")
    require(record_a.get("artifact_name") != record_b.get("artifact_name"),
            "ARTIFACT_NAME_NOT_INDEPENDENT")
    require(tar_a == tar_b, "PAYLOADS_NOT_BYTE_IDENTICAL")
    require(files_a == files_b, "PAYLOAD_MEMBERS_NOT_IDENTICAL")
    payload_sha = sha256_bytes(tar_a)
    descriptor_sha = sha256_bytes(files_a["recovery-artifact-descriptor.json"])
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    (output_dir / PAYLOAD_NAME).write_bytes(tar_a)
    (output_dir / "payload-tar.sha256").write_text(payload_sha + "\n", encoding="utf-8")
    (output_dir / "build-a-record.json").write_text(
        json.dumps(record_a, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "build-b-record.json").write_text(
        json.dumps(record_b, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema": FREEZE_SCHEMA,
        "stage": STAGE,
        "state": "SUCCESSOR_RECOVERY_ARTIFACT_REPRODUCIBLE_AND_FROZEN",
        "source_sha": source_sha,
        "payload_name": PAYLOAD_NAME,
        "payload_tar_sha256": payload_sha,
        "descriptor_sha256": descriptor_sha,
        "erased_image_sha256": ERASED_SHA256,
        "build_a": {
            "run_id": record_a["run_id"],
            "artifact_name": record_a["artifact_name"],
        },
        "build_b": {
            "run_id": record_b["run_id"],
            "artifact_name": record_b["artifact_name"],
        },
        "clean_build_count": 2,
        "payloads_byte_identical": True,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "authorization_created": False,
        "execution_authorized": False,
        "recovery_authorized": False,
        "board_operation_authorized": False,
        "serial_operation_authorized": False,
        "flash_operation_authorized": False,
        "physical_nvs_operation_authorized": False,
        "network_operation_authorized": False,
        "broker_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    (output_dir / "freeze-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    entries = []
    for path in sorted(output_dir.iterdir(), key=lambda p: p.name):
        if path.name != "SHA256SUMS":
            entries.append(f"{sha256_file(path)}  {path.name}")
        os.chmod(path, 0o600)
    (output_dir / "SHA256SUMS").write_text(
        "\n".join(entries) + "\n", encoding="utf-8"
    )
    os.chmod(output_dir / "SHA256SUMS", 0o600)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = freeze(
            args.build_a.resolve(strict=True),
            args.build_b.resolve(strict=True),
            args.output_dir.resolve(strict=False),
            args.source_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, FreezeError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
