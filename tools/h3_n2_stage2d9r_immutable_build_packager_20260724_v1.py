#!/usr/bin/env python3
"""Create deterministic public-only Stage2D9R immutable firmware payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-immutable-clean-build/1"
PAYLOAD_SCHEMA = "gh.h3.n2.stage2d9r-immutable-firmware-payload/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
BUILD_BINDING = "b39f20c55b865ec87eb650d620fd1a82b930c1ad"
UNLOCK_DIGEST = "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3"
CA_PEM_SHA256 = "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963"
CANDIDATE_DIGEST = "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5"
PARTITION_CSV_SHA256 = "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8"
FINAL_TARGET_SHA256 = "a6c9868e2a82e2feccbaaf9c5d331e2d7eb9306ffa555cd5594173830286c037"
BUILD_BINDING_FILE_SHA256 = "ff5d93654b87075fd9764ad0aceb00c5cf9e94136162b1e5dbe4b78f18989f99"
PUBLIC_DESCRIPTOR_SHA256 = "91c10168174438fc30b3dce087a6b75e24375b87b4262bafddb5b2822ee16d23"
OFFSETS = {"bootloader": 0x0, "partition_table": 0x8000, "application": 0x10000}
MAX_APPLICATION_END = 0x400000
FALSE_FLAGS = {
    "private_values_included": False,
    "private_paths_included": False,
    "execution_authorized": False,
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
    "ready_authorized": False,
    "merge_authorized": False,
    "release_authorized": False,
}


class PackagingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PackagingError(message)


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


def locate(build_root: Path, names: tuple[str, ...]) -> Path:
    matches: list[Path] = []
    for name in names:
        matches.extend(path for path in build_root.rglob(name) if path.is_file())
    unique = sorted({path.resolve() for path in matches})
    require(len(unique) == 1, f"expected exactly one build output for {names}, got {len(unique)}")
    return unique[0]


def build_merged(parts: dict[str, bytes]) -> bytes:
    application_end = OFFSETS["application"] + len(parts["application"])
    require(application_end <= MAX_APPLICATION_END, "application overlaps test partition")
    merged_end = max(OFFSETS[name] + len(value) for name, value in parts.items())
    merged = bytearray(b"\xff" * merged_end)
    for name, value in parts.items():
        offset = OFFSETS[name]
        merged[offset : offset + len(value)] = value
    return bytes(merged)


def deterministic_tar(path: Path, files: dict[str, bytes]) -> None:
    import io

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--lane", choices=("a", "b"), required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--python-environment-sha256", required=True)
    parser.add_argument("--compile-workflow-sha256", required=True)
    args = parser.parse_args()

    require(len(args.source_sha) == 40 and all(c in "0123456789abcdef" for c in args.source_sha),
            "source SHA invalid")
    for value, label in (
        (args.python_environment_sha256, "python environment digest"),
        (args.compile_workflow_sha256, "compile workflow digest"),
    ):
        require(len(value) == 64 and all(c in "0123456789abcdef" for c in value),
                f"{label} invalid")
    require(args.run_id > 0, "run id invalid")
    build_root = args.build_root.resolve(strict=True)
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "output directory already exists")
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)

    bootloader_path = locate(build_root, ("bootloader.bin",))
    partition_path = locate(build_root, ("partitions.bin", "partition-table.bin"))
    application_path = locate(build_root, ("firmware.bin",))
    parts = {
        "bootloader": bootloader_path.read_bytes(),
        "partition_table": partition_path.read_bytes(),
        "application": application_path.read_bytes(),
    }
    for name, value in parts.items():
        require(len(value) > 0, f"{name} is empty")
    merged = build_merged(parts)

    invariant_files = {
        "bootloader.bin": parts["bootloader"],
        "partition-table.bin": parts["partition_table"],
        "application.bin": parts["application"],
        "merged-image.bin": merged,
    }
    firmware = {
        "bootloader_sha256": sha256_bytes(parts["bootloader"]),
        "bootloader_size": len(parts["bootloader"]),
        "partition_table_bin_sha256": sha256_bytes(parts["partition_table"]),
        "partition_table_bin_size": len(parts["partition_table"]),
        "application_sha256": sha256_bytes(parts["application"]),
        "application_size": len(parts["application"]),
        "merged_image_sha256": sha256_bytes(merged),
        "merged_image_size": len(merged),
        "flash_offsets": OFFSETS,
    }
    payload: dict[str, Any] = {
        "schema": PAYLOAD_SCHEMA,
        "stage": STAGE,
        "source_sha": args.source_sha,
        "build_binding": BUILD_BINDING,
        "esphome_version": "2026.4.3",
        "python_environment_sha256": args.python_environment_sha256,
        "compile_workflow_sha256": args.compile_workflow_sha256,
        "source_inputs": {
            "final_target_sha256": FINAL_TARGET_SHA256,
            "build_binding_file_sha256": BUILD_BINDING_FILE_SHA256,
            "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
            "partition_table_csv_sha256": PARTITION_CSV_SHA256,
        },
        "candidate_bindings": {
            "broker_host": "stage2d9r.local",
            "broker_tls_server_name": "stage2d9r.local",
            "ca_pem_sha256": CA_PEM_SHA256,
            "candidate_digest_sha256": CANDIDATE_DIGEST,
            "unlock_digest_sha256": UNLOCK_DIGEST,
        },
        "partition": {
            "label": "gh2d8_p2d9",
            "address": 0x400000,
            "size_bytes": 0x10000,
            "table_sha256": PARTITION_CSV_SHA256,
        },
        "firmware": firmware,
        **FALSE_FLAGS,
    }
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    invariant_files["firmware-payload.json"] = payload_bytes
    sums = "".join(
        f"{sha256_bytes(invariant_files[name])}  {name}\n" for name in sorted(invariant_files)
    ).encode()
    invariant_files["SHA256SUMS"] = sums

    tar_path = output / "stage2d9r-g3r-immutable-payload-v1.tar"
    deterministic_tar(tar_path, invariant_files)
    payload_tar_sha = sha256_file(tar_path)

    record = {
        "schema": SCHEMA,
        "stage": STAGE,
        "lane": args.lane,
        "artifact_name": args.artifact_name,
        "source_sha": args.source_sha,
        "run_id": args.run_id,
        "payload_tar_sha256": payload_tar_sha,
        "payload_manifest_sha256": sha256_bytes(payload_bytes),
        "build_binding": BUILD_BINDING,
        "python_environment_sha256": args.python_environment_sha256,
        "compile_workflow_sha256": args.compile_workflow_sha256,
        "firmware": firmware,
        "candidate_bindings": payload["candidate_bindings"],
        "partition": payload["partition"],
        **FALSE_FLAGS,
    }
    record_bytes = json.dumps(record, indent=2, sort_keys=True).encode() + b"\n"
    write_private(output / "build-record.json", record_bytes)
    write_private(output / "payload-tar.sha256", (payload_tar_sha + "\n").encode())

    print("STAGE2D9R_IMMUTABLE_CLEAN_BUILD=PASS")
    print(f"LANE={args.lane}")
    print(f"SOURCE_SHA={args.source_sha}")
    print(f"RUN_ID={args.run_id}")
    print(f"PAYLOAD_TAR_SHA256={payload_tar_sha}")
    print(f"APPLICATION_SHA256={firmware['application_sha256']}")
    print(f"MERGED_IMAGE_SHA256={firmware['merged_image_sha256']}")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
