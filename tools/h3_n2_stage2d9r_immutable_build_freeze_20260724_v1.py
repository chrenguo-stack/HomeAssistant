#!/usr/bin/env python3
"""Compare two clean Stage2D9R builds and freeze a public immutable manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R"
BUILD_BINDING = "b39f20c55b865ec87eb650d620fd1a82b930c1ad"
CA_PEM_SHA256 = "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963"
CANDIDATE_DIGEST = "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5"
UNLOCK_DIGEST = "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3"
PARTITION_TABLE_SHA256 = "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8"
CANONICAL_ARTIFACT_NAME = "stage2d9r-g3r-immutable-locked-v1"
REPRO_ARTIFACT_NAME = "stage2d9r-g3r-immutable-repro-v1"
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


class FreezeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FreezeError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def locate(root: Path, name: str) -> Path:
    matches = sorted(path for path in root.rglob(name) if path.is_file())
    require(len(matches) == 1, f"expected exactly one {name} below {root}")
    return matches[0]


def load_build(root: Path, lane: str, run_id: int, artifact_name: str) -> tuple[dict[str, Any], Path]:
    record_path = locate(root, "build-record.json")
    tar_path = locate(root, "stage2d9r-g3r-immutable-payload-v1.tar")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    require(record.get("schema") == "gh.h3.n2.stage2d9r-immutable-clean-build/1",
            "clean build schema mismatch")
    require(record.get("stage") == STAGE, "clean build stage mismatch")
    require(record.get("lane") == lane, "clean build lane mismatch")
    require(record.get("run_id") == run_id, "clean build run id mismatch")
    require(record.get("artifact_name") == artifact_name, "artifact name mismatch")
    require(record.get("payload_tar_sha256") == sha256_file(tar_path),
            "payload tar digest mismatch")
    require(record.get("build_binding") == BUILD_BINDING, "build binding mismatch")
    for key in FALSE_FLAGS:
        require(record.get(key) is False, f"{key} must be false")
    return record, tar_path


def inspect_tar(path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    expected = {
        "SHA256SUMS",
        "application.bin",
        "bootloader.bin",
        "firmware-payload.json",
        "merged-image.bin",
        "partition-table.bin",
    }
    files: dict[str, bytes] = {}
    with tarfile.open(path, "r") as archive:
        members = archive.getmembers()
        require({member.name for member in members} == expected, "payload member set mismatch")
        for member in members:
            require(member.isfile(), "payload contains non-file member")
            require(member.mode == 0o600, "payload member mode mismatch")
            require(member.uid == 0 and member.gid == 0 and member.mtime == 0,
                    "payload metadata is not deterministic")
            handle = archive.extractfile(member)
            require(handle is not None, "payload member cannot be read")
            files[member.name] = handle.read()
    sums: dict[str, str] = {}
    for line in files["SHA256SUMS"].decode().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    for name, data in files.items():
        if name == "SHA256SUMS":
            continue
        require(sums.get(name) == sha256_bytes(data), f"payload digest mismatch for {name}")
    payload = json.loads(files["firmware-payload.json"])
    require(payload.get("schema") == "gh.h3.n2.stage2d9r-immutable-firmware-payload/1",
            "payload schema mismatch")
    require(payload.get("stage") == STAGE, "payload stage mismatch")
    require(payload.get("build_binding") == BUILD_BINDING, "payload build binding mismatch")
    require(payload["candidate_bindings"] == {
        "broker_host": "stage2d9r.local",
        "broker_tls_server_name": "stage2d9r.local",
        "ca_pem_sha256": CA_PEM_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST,
        "unlock_digest_sha256": UNLOCK_DIGEST,
    }, "payload candidate binding mismatch")
    require(payload["partition"] == {
        "label": "gh2d8_p2d9",
        "address": 0x400000,
        "size_bytes": 0x10000,
        "table_sha256": PARTITION_TABLE_SHA256,
    }, "payload partition binding mismatch")
    for key in FALSE_FLAGS:
        require(payload.get(key) is False, f"payload {key} must be false")
    return files, payload


def manifest_digest(manifest: dict[str, Any]) -> str:
    copy = json.loads(json.dumps(manifest))
    copy["artifact"].pop("manifest_sha256", None)
    return sha256_bytes(canonical_json(copy))


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, "output mode mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--run-a", type=int, required=True)
    parser.add_argument("--run-b", type=int, required=True)
    parser.add_argument("--artifact-a-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    require(args.run_a > 0 and args.run_b > 0 and args.run_a != args.run_b,
            "compile run ids invalid")
    require(args.artifact_a_id > 0, "canonical artifact id invalid")
    require(len(args.source_sha) == 40 and all(c in "0123456789abcdef" for c in args.source_sha),
            "source SHA invalid")

    record_a, tar_a = load_build(
        args.build_a.resolve(strict=True), "a", args.run_a, CANONICAL_ARTIFACT_NAME
    )
    record_b, tar_b = load_build(
        args.build_b.resolve(strict=True), "b", args.run_b, REPRO_ARTIFACT_NAME
    )
    require(record_a["source_sha"] == record_b["source_sha"] == args.source_sha,
            "build source SHA mismatch")
    require(record_a["payload_tar_sha256"] == record_b["payload_tar_sha256"],
            "clean build payload archives differ")
    require(record_a["python_environment_sha256"] == record_b["python_environment_sha256"],
            "Python environments differ")
    require(record_a["compile_workflow_sha256"] == record_b["compile_workflow_sha256"],
            "compile workflow digests differ")
    require(record_a["firmware"] == record_b["firmware"], "firmware records differ")
    require(record_a["candidate_bindings"] == record_b["candidate_bindings"],
            "candidate bindings differ")
    require(record_a["partition"] == record_b["partition"], "partition bindings differ")

    files_a, payload_a = inspect_tar(tar_a)
    files_b, payload_b = inspect_tar(tar_b)
    require(files_a == files_b, "clean build payload bytes differ")
    require(payload_a == payload_b, "clean build payload manifests differ")
    require(payload_a["source_sha"] == args.source_sha, "payload source SHA mismatch")

    firmware = payload_a["firmware"]
    manifest: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-immutable-build-manifest/1",
        "stage": STAGE,
        "state": "BUILD_FROZEN",
        "source_sha": args.source_sha,
        "build_binding": BUILD_BINDING,
        "esphome_version": "2026.4.3",
        "python_environment_sha256": record_a["python_environment_sha256"],
        "compile_workflow_sha256": record_a["compile_workflow_sha256"],
        "compile_run_ids": [args.run_a, args.run_b],
        "candidate_bindings": record_a["candidate_bindings"],
        "partition": record_a["partition"],
        "firmware": {
            "bootloader_sha256": firmware["bootloader_sha256"],
            "partition_table_bin_sha256": firmware["partition_table_bin_sha256"],
            "application_sha256": firmware["application_sha256"],
            "merged_image_sha256": firmware["merged_image_sha256"],
            "merged_image_size": firmware["merged_image_size"],
            "flash_offsets": firmware["flash_offsets"],
        },
        "reproducibility": {
            "clean_build_count": 2,
            "all_firmware_hashes_identical": True,
            "all_manifest_hashes_identical": True,
        },
        "artifact": {
            "artifact_id": args.artifact_a_id,
            "artifact_name": CANONICAL_ARTIFACT_NAME,
            "artifact_sha256": record_a["payload_tar_sha256"],
            "manifest_digest_algorithm": (
                "sha256-canonical-json-without-artifact.manifest_sha256-v1"
            ),
            "manifest_sha256": "0" * 64,
            "expired": False,
        },
        **{key: False for key in FALSE_FLAGS},
    }
    manifest["artifact"]["manifest_sha256"] = manifest_digest(manifest)
    require(manifest_digest(manifest) == manifest["artifact"]["manifest_sha256"],
            "manifest digest is unstable")

    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "output directory already exists")
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    write_private(
        output / "stage2d9r_immutable_build_manifest_20260724_v1.json",
        manifest_bytes,
    )
    shutil.copy2(tar_a, output / tar_a.name)
    os.chmod(output / tar_a.name, 0o600)
    write_private(
        output / "build-a-record.json",
        json.dumps(record_a, indent=2, sort_keys=True).encode() + b"\n",
    )
    write_private(
        output / "build-b-record.json",
        json.dumps(record_b, indent=2, sort_keys=True).encode() + b"\n",
    )
    sums = "".join(
        f"{sha256_file(path)}  {path.name}\n"
        for path in sorted(output.iterdir())
        if path.is_file()
    ).encode()
    write_private(output / "SHA256SUMS", sums)

    print("STAGE2D9R_IMMUTABLE_BUILD_FREEZE=PASS")
    print(f"SOURCE_SHA={args.source_sha}")
    print(f"BUILD_A_RUN_ID={args.run_a}")
    print(f"BUILD_B_RUN_ID={args.run_b}")
    print(f"CANONICAL_ARTIFACT_ID={args.artifact_a_id}")
    print(f"ARTIFACT_SHA256={manifest['artifact']['artifact_sha256']}")
    print(f"MANIFEST_SHA256={manifest['artifact']['manifest_sha256']}")
    print(f"APPLICATION_SHA256={firmware['application_sha256']}")
    print(f"MERGED_IMAGE_SHA256={firmware['merged_image_sha256']}")
    print("REPRODUCIBLE=true")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
