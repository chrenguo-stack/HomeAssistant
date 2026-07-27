#!/usr/bin/env python3
"""Build a deterministic, public-only successor locked-recovery payload.

The payload is reviewed input only. It cannot authorize or perform board, serial,
Flash, NVS, network, Broker, PREPARE, VERIFY, ACTIVATE or CLEANUP operations.
"""
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

SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-artifact/1"
BUILD_RECORD_SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-clean-build/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
STATE = "SUCCESSOR_RECOVERY_ARTIFACT_LOCKED"
PAYLOAD_NAME = "stage2d9r-g3r-successor-recovery-payload-v1.tar"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ERASED_SIZE = 65536
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
IMMUTABLE_ACCEPTANCE_SCHEMA = "gh.h3.n2.stage2d9r-successor-immutable-build-acceptance-l1/1"
IMMUTABLE_SOURCE_SHA = "ac1d2a7a92323988c9cd946a3e018e4f1ba9463b"
IMMUTABLE_ARTIFACT_ID = 8638796771
IMMUTABLE_ARTIFACT_NAME = "stage2d9r-g3r-successor-immutable-locked-v1"
IMMUTABLE_ARCHIVE_SHA256 = "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8"
IMMUTABLE_PAYLOAD_TAR_SHA256 = "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747"
APPLICATION_SHA256 = "a75e440c90aa5f050ac55086d1f1c614f113a7b66bd31ffc748fee95b9d26e1b"
MERGED_IMAGE_SHA256 = "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
UNLOCK_DIGEST = "727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
CANDIDATE_DIGEST = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
BROKER_DER_SHA256 = "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
BROKER_SPKI_SHA256 = "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
PARTITION_TABLE_SHA256 = "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8"
PARTITION_TABLE_BIN_SHA256 = "b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268"

FALSE_FLAGS = {
    "private_values_included": False,
    "private_paths_included": False,
    "secret_values_included": False,
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
    "tag_authorized": False,
    "deployment_authorized": False,
}


class RecoveryPackagingError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RecoveryPackagingError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_exclusive(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, mode)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, mode)
    require(stat.S_IMODE(path.stat().st_mode) == mode, "OUTPUT_MODE_MISMATCH")


def deterministic_tar(path: Path, files: dict[str, bytes]) -> None:
    require(not path.exists(), "PAYLOAD_ALREADY_EXISTS")
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


def validate_immutable_acceptance(value: dict[str, Any]) -> None:
    require(value.get("schema") == IMMUTABLE_ACCEPTANCE_SCHEMA,
            "IMMUTABLE_ACCEPTANCE_SCHEMA_MISMATCH")
    require(value.get("stage") == STAGE, "IMMUTABLE_STAGE_MISMATCH")
    require(value.get("state") == "IMMUTABLE_BUILD_REPRODUCIBLE_AND_FROZEN",
            "IMMUTABLE_STATE_MISMATCH")
    require(value.get("source_sha") == IMMUTABLE_SOURCE_SHA,
            "IMMUTABLE_SOURCE_MISMATCH")
    require(value.get("build_binding") == BUILD_BINDING,
            "IMMUTABLE_BUILD_BINDING_MISMATCH")
    canonical = value.get("canonical_artifact")
    firmware = value.get("firmware")
    candidate = value.get("candidate_bindings")
    disposition = value.get("disposition")
    protected = value.get("protected_boundaries")
    require(isinstance(canonical, dict), "IMMUTABLE_CANONICAL_MISSING")
    require(isinstance(firmware, dict), "IMMUTABLE_FIRMWARE_MISSING")
    require(isinstance(candidate, dict), "IMMUTABLE_CANDIDATE_MISSING")
    require(isinstance(disposition, dict), "IMMUTABLE_DISPOSITION_MISSING")
    require(isinstance(protected, dict), "IMMUTABLE_BOUNDARIES_MISSING")
    require(canonical.get("artifact_id") == IMMUTABLE_ARTIFACT_ID,
            "IMMUTABLE_ARTIFACT_ID_MISMATCH")
    require(canonical.get("name") == IMMUTABLE_ARTIFACT_NAME,
            "IMMUTABLE_ARTIFACT_NAME_MISMATCH")
    require(canonical.get("github_digest_sha256") == IMMUTABLE_ARCHIVE_SHA256,
            "IMMUTABLE_ARCHIVE_DIGEST_MISMATCH")
    require(canonical.get("payload_tar_sha256") == IMMUTABLE_PAYLOAD_TAR_SHA256,
            "IMMUTABLE_PAYLOAD_DIGEST_MISMATCH")
    require(firmware.get("application_sha256") == APPLICATION_SHA256,
            "IMMUTABLE_APPLICATION_DIGEST_MISMATCH")
    require(firmware.get("merged_image_sha256") == MERGED_IMAGE_SHA256,
            "IMMUTABLE_MERGED_DIGEST_MISMATCH")
    require(firmware.get("partition_table_bin_sha256") == PARTITION_TABLE_BIN_SHA256,
            "IMMUTABLE_PARTITION_BIN_DIGEST_MISMATCH")
    expected_candidate = {
        "unlock_digest_sha256": UNLOCK_DIGEST,
        "ca_pem_sha256": CA_PEM_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST,
        "broker_certificate_der_sha256": BROKER_DER_SHA256,
        "broker_spki_sha256": BROKER_SPKI_SHA256,
    }
    for key, expected in expected_candidate.items():
        require(candidate.get(key) == expected,
                f"IMMUTABLE_CANDIDATE_MISMATCH_{key.upper()}")
    require(disposition.get("immutable_build_accepted") is True,
            "IMMUTABLE_NOT_ACCEPTED")
    require(disposition.get("canonical_artifact_frozen") is True,
            "IMMUTABLE_NOT_FROZEN")
    require(disposition.get("d2_authorized") is False,
            "IMMUTABLE_D2_AUTHORIZED")
    require(disposition.get("physical_execution_authorized") is False,
            "IMMUTABLE_PHYSICAL_EXECUTION_AUTHORIZED")
    for key, observed in protected.items():
        require(observed is False, f"IMMUTABLE_BOUNDARY_EXPANDED_{key.upper()}")


def validate_recovery_template(value: dict[str, Any]) -> None:
    require(
        value.get("schema")
        == "gh.h3.n2.stage2d9r-test-partition-recovery-manifest/1",
        "RECOVERY_TEMPLATE_SCHEMA_MISMATCH",
    )
    require(value.get("state") == "LOCKED_TEMPLATE",
            "RECOVERY_TEMPLATE_STATE_MISMATCH")
    partition = value.get("partition")
    require(isinstance(partition, dict), "RECOVERY_TEMPLATE_PARTITION_MISSING")
    require(partition == {
        "label": "gh2d8_p2d9",
        "namespace": "gh2d8_s2d9",
        "address": 0x400000,
        "size_bytes": ERASED_SIZE,
        "expected_erased_byte": 0xFF,
        "expected_erased_sha256": ERASED_SHA256,
    }, "RECOVERY_TEMPLATE_PARTITION_MISMATCH")
    for key in (
        "recovery_authorized",
        "board_operation_authorized",
        "serial_operation_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
    ):
        require(value.get(key) is False,
                f"RECOVERY_TEMPLATE_BOUNDARY_EXPANDED_{key.upper()}")
    serialized = json.dumps(value, sort_keys=True)
    require("<SOURCE_SHA40>" in serialized, "RECOVERY_TEMPLATE_PLACEHOLDER_MISSING")
    for forbidden in ("/dev/", "/Users/", "BEGIN PRIVATE KEY"):
        require(forbidden not in serialized, "RECOVERY_TEMPLATE_PRIVATE_CONTENT")


def build_payload(
    *,
    immutable_acceptance_path: Path,
    recovery_template_path: Path,
    recovery_contract_path: Path,
    recovery_gate_path: Path,
    source_sha: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    immutable_bytes = immutable_acceptance_path.read_bytes()
    template_bytes = recovery_template_path.read_bytes()
    contract_bytes = recovery_contract_path.read_bytes()
    gate_bytes = recovery_gate_path.read_bytes()
    immutable = json.loads(immutable_bytes)
    template = json.loads(template_bytes)
    require(isinstance(immutable, dict), "IMMUTABLE_ACCEPTANCE_NOT_OBJECT")
    require(isinstance(template, dict), "RECOVERY_TEMPLATE_NOT_OBJECT")
    validate_immutable_acceptance(immutable)
    validate_recovery_template(template)
    contract_text = contract_bytes.decode("utf-8")
    require("source/review contract" in contract_text,
            "RECOVERY_CONTRACT_BOUNDARY_MISSING")
    gate_text = gate_bytes.decode("utf-8")
    for prohibited in ("import serial", "import socket", "subprocess.run", "os.system"):
        require(prohibited not in gate_text,
                f"RECOVERY_GATE_EXECUTABLE_OPERATION_{prohibited}")

    erased = b"\xff" * ERASED_SIZE
    require(sha256_bytes(erased) == ERASED_SHA256,
            "ERASED_IMAGE_DIGEST_MISMATCH")
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
            "artifact_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
            "payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
            "application_sha256": APPLICATION_SHA256,
            "merged_image_sha256": MERGED_IMAGE_SHA256,
        },
        "candidate_bindings": {
            "unlock_digest_sha256": UNLOCK_DIGEST,
            "ca_pem_sha256": CA_PEM_SHA256,
            "candidate_digest_sha256": CANDIDATE_DIGEST,
            "broker_certificate_der_sha256": BROKER_DER_SHA256,
            "broker_spki_sha256": BROKER_SPKI_SHA256,
        },
        "recovery_partition": {
            "label": "gh2d8_p2d9",
            "namespace": "gh2d8_s2d9",
            "address": 0x400000,
            "size_bytes": ERASED_SIZE,
            "erased_byte": 0xFF,
            "erased_image_sha256": ERASED_SHA256,
            "partition_table_sha256": PARTITION_TABLE_SHA256,
            "partition_table_bin_sha256": PARTITION_TABLE_BIN_SHA256,
        },
        "reviewed_inputs": {
            "immutable_acceptance_sha256": sha256_bytes(immutable_bytes),
            "recovery_template_sha256": sha256_bytes(template_bytes),
            "recovery_contract_sha256": sha256_bytes(contract_bytes),
            "recovery_gate_sha256": sha256_bytes(gate_bytes),
        },
        "allowed_future_operation": (
            "WRITE_EXACT_ERASED_IMAGE_TO_EXACT_TEST_PARTITION_ONLY_UNDER_EXACT_D2"
        ),
        "allowed_counts": {
            "pre_read": 1,
            "erase_or_write_erased_region": 1,
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
    ).encode("utf-8") + b"\n"
    files = {
        "RECOVERY_CONTRACT.md": contract_bytes,
        "recovery-artifact-descriptor.json": descriptor_bytes,
        "recovery-authorization-manifest.template.json": template_bytes,
        "test-partition-erased.bin": erased,
    }
    sums = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    ).encode("utf-8")
    files["SHA256SUMS"] = sums
    return descriptor, files


def package(
    *,
    immutable_acceptance_path: Path,
    recovery_template_path: Path,
    recovery_contract_path: Path,
    recovery_gate_path: Path,
    output_dir: Path,
    source_sha: str,
    lane: str,
    artifact_name: str,
    run_id: int,
) -> dict[str, Any]:
    require(lane in ("a", "b"), "LANE_INVALID")
    require(run_id > 0, "RUN_ID_INVALID")
    require(not output_dir.exists(), "OUTPUT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    descriptor, files = build_payload(
        immutable_acceptance_path=immutable_acceptance_path,
        recovery_template_path=recovery_template_path,
        recovery_contract_path=recovery_contract_path,
        recovery_gate_path=recovery_gate_path,
        source_sha=source_sha,
    )
    tar_path = output_dir / PAYLOAD_NAME
    deterministic_tar(tar_path, files)
    payload_sha = sha256_file(tar_path)
    descriptor_bytes = json.dumps(
        descriptor, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    record = {
        "schema": BUILD_RECORD_SCHEMA,
        "stage": STAGE,
        "state": "CLEAN_BUILD_COMPLETE",
        "source_sha": source_sha,
        "lane": lane,
        "run_id": run_id,
        "artifact_name": artifact_name,
        "payload_name": PAYLOAD_NAME,
        "payload_tar_sha256": payload_sha,
        "descriptor_sha256": sha256_bytes(descriptor_bytes),
        "erased_image_sha256": ERASED_SHA256,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "authorization_created": False,
        "execution_authorized": False,
        "recovery_authorized": False,
        "board_operation_authorized": False,
        "serial_operation_authorized": False,
        "flash_operation_authorized": False,
    }
    write_exclusive(
        output_dir / "build-record.json",
        json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    write_exclusive(output_dir / "payload-tar.sha256", (payload_sha + "\n").encode())
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--immutable-acceptance", type=Path, required=True)
    parser.add_argument("--recovery-template", type=Path, required=True)
    parser.add_argument("--recovery-contract", type=Path, required=True)
    parser.add_argument("--recovery-gate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--lane", choices=("a", "b"), required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    try:
        record = package(
            immutable_acceptance_path=args.immutable_acceptance.resolve(strict=True),
            recovery_template_path=args.recovery_template.resolve(strict=True),
            recovery_contract_path=args.recovery_contract.resolve(strict=True),
            recovery_gate_path=args.recovery_gate.resolve(strict=True),
            output_dir=args.output_dir.resolve(strict=False),
            source_sha=args.source_sha,
            lane=args.lane,
            artifact_name=args.artifact_name,
            run_id=args.run_id,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, RecoveryPackagingError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **record}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
