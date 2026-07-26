#!/usr/bin/env python3
"""Create deterministic public-only Stage2D9R successor immutable firmware payloads."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-successor-immutable-clean-build/1"
PAYLOAD_SCHEMA = "gh.h3.n2.stage2d9r-successor-immutable-firmware-payload/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
UNLOCK_DIGEST = "727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
CANDIDATE_DIGEST = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
BROKER_DER_SHA256 = "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
BROKER_SPKI_SHA256 = "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
PARTITION_CSV_SHA256 = "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8"
FINAL_TARGET_SHA256 = "a7917c92f09a74a45c827cb7a47edec27cfb050dec074680c36bae39efaad85f"
BUILD_BINDING_FILE_SHA256 = "504836a63fa176d73d2f79499219c6534b3175a75b9a6659337d452c5b308b34"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
PUBLIC_PKI_BINDING_SHA256 = "0a38ef9648008cbd7a3966e5e558bb8a9b672f255fa6e390800508cd93555734"
SOURCE_LOCK_ACCEPTANCE_SHA256 = "0105210833023e1a181079d5c2feab1239f1433e09a4e512768872b21f55b6b4"
OFFSETS = {"bootloader": 0x0, "partition_table": 0x8000, "application": 0x10000}
MAX_APPLICATION_END = 0x400000
PAYLOAD_TAR_NAME = "stage2d9r-g3r-successor-immutable-payload-v1.tar"
FALSE_FLAGS = {
    "private_values_included": False,
    "private_paths_included": False,
    "secret_values_included": False,
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
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o600
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
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
        (args.python_environment_sha256, "Python environment digest"),
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

    parts = {
        "bootloader": locate(build_root, ("bootloader.bin",)).read_bytes(),
        "partition_table": locate(build_root, ("partitions.bin", "partition-table.bin")).read_bytes(),
        "application": locate(build_root, ("firmware.bin",)).read_bytes(),
    }
    for name, value in parts.items():
        require(value, f"{name} is empty")
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
    candidate_bindings = {
        "broker_host": "stage2d9r.local",
        "broker_tls_server_name": "stage2d9r.local",
        "ca_pem_sha256": CA_PEM_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST,
        "unlock_digest_sha256": UNLOCK_DIGEST,
        "broker_certificate_der_sha256": BROKER_DER_SHA256,
        "broker_spki_sha256": BROKER_SPKI_SHA256,
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
            "public_pki_export_binding_sha256": PUBLIC_PKI_BINDING_SHA256,
            "source_lock_acceptance_sha256": SOURCE_LOCK_ACCEPTANCE_SHA256,
            "partition_table_csv_sha256": PARTITION_CSV_SHA256,
        },
        "candidate_bindings": candidate_bindings,
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
    invariant_files["SHA256SUMS"] = "".join(
        f"{sha256_bytes(invariant_files[name])}  {name}\n" for name in sorted(invariant_files)
    ).encode()

    tar_path = output / PAYLOAD_TAR_NAME
    deterministic_tar(tar_path, invariant_files)
    payload_tar_sha = sha256_bytes(tar_path.read_bytes())

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
        "source_inputs": payload["source_inputs"],
        "firmware": firmware,
        "candidate_bindings": candidate_bindings,
        "partition": payload["partition"],
        **FALSE_FLAGS,
    }
    write_private(
        output / "build-record.json",
        json.dumps(record, indent=2, sort_keys=True).encode() + b"\n",
    )
    write_private(output / "payload-tar.sha256", (payload_tar_sha + "\n").encode())

    print("STAGE2D9R_SUCCESSOR_IMMUTABLE_CLEAN_BUILD=PASS")
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
