#!/usr/bin/env python3
"""Repaired physical-D2 wrapper around the frozen successor executor.

This source is inert by default. The future physical D2 may invoke it only with
an exact current authorization. It rebinds the frozen executor to tlsvalid03,
installs the repaired serial-first handshake, and replaces the retired
write-image recovery with partition-only read/erase/read recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import h3_n2_stage2d9r_successor_d2_execute_20260727_v1 as core
import h3_n2_stage2d9r_serial_handshake_repair_20260727_v1 as repair

STAGE = "H3/N2 Stage 2D-9R G3R repaired successor"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-physical-d2-consumed-marker/1"

BASE_PR = 188
BASE_HEAD_SHA = "8a6fdd7c74341448d275a4412e36b303d7c95e85"
BASELINE_ORIGINAL_MAIN_SHA = "c16da1a2d4d8300198b0603359eea349a034e2ea"
ACCEPTED_CURRENT_MAIN_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"
FINAL_EXECUTION_BINDING = "387602804793c7ab110817d56aa4c26114632bde"
FINAL_EXECUTION_BINDING_SHA256 = (
    "387602804793c7ab110817d56aa4c26114632bde31050e95847833f98d83b6c1"
)
BASELINE_RESULT_SHA256 = (
    "f3522e98d5c0c8fdf4f5fa2b8486e6c782c7262ae4321e9525471bc0f12cacf4"
)

IMMUTABLE_ARTIFACT_ID = 8676269782
IMMUTABLE_ARCHIVE_SHA256 = (
    "83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8"
)
IMMUTABLE_PAYLOAD_TAR_SHA256 = (
    "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
)
IMMUTABLE_MERGED_SHA256 = (
    "67dc276c7ef69a1528d511c4043ec3eb58489eefb6864442f03e405f24611cb3"
)
RECOVERY_PAYLOAD_TAR_SHA256 = (
    "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
)
RECOVERY_DESCRIPTOR_SHA256 = (
    "660b5419b65b2a417989ca8808bc434a4f83703fa90a72b4f306360879abbbd0"
)
PRIVATE_PACKAGE_SHA256 = (
    "d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f"
)
PREPARE_COMMAND_SHA256 = (
    "022577c2ee88c57ab45533f53a5630f7eb94e142985533cdc1a8166de0d3317f"
)
VERIFY_COMMAND_SHA256 = (
    "9d5aad5eb2eedd6ba8460df80af3653dc68c8e24cd12a6bcd69e5460436050d7"
)
CANDIDATE_DIGEST_SHA256 = (
    "73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15"
)
CA_PEM_SHA256 = (
    "e9abe88df80f21311ea9ea4977b78f531380a37564490c1108fabeae8cc5bc5a"
)
BUILD_BINDING = "4051f5d541898cef742f35aeec757e7fc479f383"
CUSTODY_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/"
    "repaired-successor-private-execution-material-tlsvalid03"
)
TEST_PARTITION_ADDRESS = 0x400000
TEST_PARTITION_SIZE = 0x10000
ERASED_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_public_inputs(immutable_root: Path, recovery_root: Path) -> tuple[Path, Path]:
    core.require(
        immutable_root.is_dir() and not immutable_root.is_symlink(),
        "IMMUTABLE_ROOT_INVALID",
    )
    core.require(
        recovery_root.is_dir() and not recovery_root.is_symlink(),
        "RECOVERY_ROOT_INVALID",
    )
    immutable_tar = immutable_root / "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
    recovery_tar = recovery_root / "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
    core.regular(immutable_tar, "0600", "IMMUTABLE_PAYLOAD_INVALID")
    core.regular(recovery_tar, "0600", "RECOVERY_PAYLOAD_INVALID")
    core.require(
        sha256_file(immutable_tar) == IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE_PAYLOAD_DIGEST_MISMATCH",
    )
    core.require(
        sha256_file(recovery_tar) == RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY_PAYLOAD_DIGEST_MISMATCH",
    )
    merged = immutable_root / "merged-image.bin"
    erased = recovery_root / "erased-test-partition.bin"
    descriptor = recovery_root / "locked-recovery-descriptor.json"
    core.regular(merged, "0600", "IMMUTABLE_MERGED_IMAGE_INVALID")
    core.regular(erased, "0600", "RECOVERY_ERASED_IMAGE_INVALID")
    core.regular(descriptor, "0600", "RECOVERY_DESCRIPTOR_INVALID")
    core.require(
        sha256_file(merged) == IMMUTABLE_MERGED_SHA256,
        "IMMUTABLE_MERGED_IMAGE_DIGEST_MISMATCH",
    )
    core.require(
        erased.stat().st_size == TEST_PARTITION_SIZE,
        "RECOVERY_ERASED_IMAGE_SIZE_MISMATCH",
    )
    core.require(sha256_file(erased) == ERASED_SHA256, "RECOVERY_ERASED_IMAGE_DIGEST_MISMATCH")
    core.require(
        sha256_file(descriptor) == RECOVERY_DESCRIPTOR_SHA256,
        "RECOVERY_DESCRIPTOR_DIGEST_MISMATCH",
    )
    return merged, erased


def locked_recovery(
    selected: Any,
    esptool_path: Path,
    erased: Path,
    work: Path,
) -> bool:
    # The erased reference is validated by validate_public_inputs. Recovery uses
    # no write_flash and is limited to read -> erase_region -> read.
    core.require(
        erased.stat().st_size == TEST_PARTITION_SIZE
        and sha256_file(erased) == ERASED_SHA256,
        "LOCKED_RECOVERY_REFERENCE_INVALID",
    )
    pre = work / "locked-recovery-pre-read.bin"
    post = work / "locked-recovery-post-read.bin"
    core.run_process(
        core.esptool_command(
            esptool_path,
            selected.device,
            "--before",
            "default_reset",
            "--after",
            "no_reset",
            "read_flash",
            hex(TEST_PARTITION_ADDRESS),
            hex(TEST_PARTITION_SIZE),
            str(pre),
        ),
        timeout=60,
        code="LOCKED_RECOVERY_PRE_READ_FAILED",
    )
    core.require(
        pre.is_file() and pre.stat().st_size == TEST_PARTITION_SIZE,
        "LOCKED_RECOVERY_PRE_READ_SIZE_MISMATCH",
    )
    core.run_process(
        core.esptool_command(
            esptool_path,
            selected.device,
            "--before",
            "no_reset",
            "--after",
            "no_reset",
            "erase_region",
            hex(TEST_PARTITION_ADDRESS),
            hex(TEST_PARTITION_SIZE),
        ),
        timeout=60,
        code="LOCKED_RECOVERY_REGION_ERASE_FAILED",
    )
    core.run_process(
        core.esptool_command(
            esptool_path,
            selected.device,
            "--before",
            "no_reset",
            "--after",
            "hard_reset",
            "read_flash",
            hex(TEST_PARTITION_ADDRESS),
            hex(TEST_PARTITION_SIZE),
            str(post),
        ),
        timeout=60,
        code="LOCKED_RECOVERY_POST_READ_FAILED",
    )
    core.require(
        post.is_file() and post.stat().st_size == TEST_PARTITION_SIZE,
        "LOCKED_RECOVERY_POST_READ_SIZE_MISMATCH",
    )
    core.require(
        sha256_file(post) == ERASED_SHA256,
        "LOCKED_RECOVERY_POST_READ_DIGEST_MISMATCH",
    )
    return True


def configure_core() -> Any:
    bindings = {
        "STAGE": STAGE,
        "D2_REQUEST_ID": D2_REQUEST_ID,
        "AUTH_SCHEMA": AUTH_SCHEMA,
        "RESULT_SCHEMA": RESULT_SCHEMA,
        "MARKER_SCHEMA": MARKER_SCHEMA,
        "IMMUTABLE_ARTIFACT_ID": IMMUTABLE_ARTIFACT_ID,
        "IMMUTABLE_ARCHIVE_SHA256": IMMUTABLE_ARCHIVE_SHA256,
        "IMMUTABLE_PAYLOAD_TAR_SHA256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE_MERGED_SHA256": IMMUTABLE_MERGED_SHA256,
        "RECOVERY_ARTIFACT_ID": IMMUTABLE_ARTIFACT_ID,
        "RECOVERY_ARCHIVE_SHA256": IMMUTABLE_ARCHIVE_SHA256,
        "RECOVERY_PAYLOAD_TAR_SHA256": RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY_DESCRIPTOR_SHA256": RECOVERY_DESCRIPTOR_SHA256,
        "PRIVATE_PACKAGE_SHA256": PRIVATE_PACKAGE_SHA256,
        "PREPARE_COMMAND_SHA256": PREPARE_COMMAND_SHA256,
        "VERIFY_COMMAND_SHA256": VERIFY_COMMAND_SHA256,
        "CANDIDATE_DIGEST_SHA256": CANDIDATE_DIGEST_SHA256,
        "CA_PEM_SHA256": CA_PEM_SHA256,
        "BUILD_BINDING": BUILD_BINDING,
        "CUSTODY_RELATIVE": CUSTODY_RELATIVE,
        "TEST_PARTITION_ADDRESS": TEST_PARTITION_ADDRESS,
        "TEST_PARTITION_SIZE": TEST_PARTITION_SIZE,
        "ERASED_SHA256": ERASED_SHA256,
        "validate_public_inputs": validate_public_inputs,
        "locked_recovery": locked_recovery,
    }
    for key, value in bindings.items():
        setattr(core, key, value)

    original_validate = core.validate_authorization

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = original_validate(*args, **kwargs)
        required = {
            "main_sha": ACCEPTED_CURRENT_MAIN_SHA,
            "baseline_original_main_sha": BASELINE_ORIGINAL_MAIN_SHA,
            "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
            "immutable_source_sha": BASE_HEAD_SHA,
            "base_pr": BASE_PR,
            "base_head_sha": BASE_HEAD_SHA,
            "final_execution_binding": FINAL_EXECUTION_BINDING,
            "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
            "baseline_result_sha256": BASELINE_RESULT_SHA256,
            "locked_recovery_scope": "TEST_PARTITION_ONLY",
        }
        for key, expected in required.items():
            core.require(
                value.get(key) == expected,
                f"AUTHORIZATION_{key.upper()}_MISMATCH",
            )
        core.require(
            value.get("host_final_preflight_source_sha") == value.get("source_sha")
            and isinstance(value.get("source_sha"), str)
            and core.HEX40.fullmatch(value["source_sha"]) is not None
            and value["source_sha"] != BASE_HEAD_SHA,
            "AUTHORIZATION_HOST_FINAL_PREFLIGHT_SOURCE_MISMATCH",
        )
        core.require(
            value.get("locked_recovery_authorized") is True,
            "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED",
        )
        return value

    core.validate_authorization = validate_authorization
    # The exact executable script bound by authorization is this wrapper.
    core.__file__ = __file__
    repair.install_repaired_handshake(core)
    return core


def main() -> int:
    if len(sys.argv) == 1:
        print(
            json.dumps(
                {
                    "status": "SOURCE_ONLY_REQUIRES_EXACT_PHYSICAL_D2_AUTHORIZATION",
                    "d2_request_id": D2_REQUEST_ID,
                    "board_operation": False,
                    "usb_enumeration": False,
                    "serial_operation": False,
                    "esptool_operation": False,
                    "flash_operation": False,
                    "physical_nvs_operation": False,
                    "network_operation": False,
                    "broker_started": False,
                    "prepare_executed": False,
                    "verify_executed": False,
                    "replay_permitted": False,
                    "automatic_retry_permitted": False,
                },
                sort_keys=True,
            )
        )
        return 0
    configured = configure_core()
    return configured.main()


if __name__ == "__main__":
    raise SystemExit(main())
