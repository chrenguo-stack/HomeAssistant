#!/usr/bin/env python3
"""Build deterministic public review packages for payload handoff repair."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import *
from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_execution_20260728_v1 import (
    read_tar_members,
    validate_immutable_zip,
)

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PHYSICAL-PAYLOAD-HANDOFF-REPAIR-20260728-01"
BASE_PR = 189
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-repaired-host-final-preflight-20260728-v1"
BASE_HEAD_SHA = "45c80baf43ccc3f917ae5964ee92a202a74cc2ba"
ACCEPTED_CURRENT_MAIN_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"
OLD_PHYSICAL_D2_ID = "D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01"
OLD_PHYSICAL_D2_FAILURE = "IMMUTABLE_PAYLOAD_INVALID"
IMMUTABLE_ARTIFACT_ID = 8676269782
IMMUTABLE_ARTIFACT_SHA256 = "83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8"
HOST_FINAL_ARTIFACT_ID = 8678117016
HOST_FINAL_ARTIFACT_SHA256 = "a11d5d30a868094381737ff66434e40556de5a6b69b4e785b6110e6e37b9df01"

WRAPPER_NAME = "h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1.py"
FROZEN_WRAPPER_NAME = "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
CORE_NAME = "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"
REPAIR_NAME = "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
LAUNCHER_NAME = "run_stage2d9r_g3r_physical_payload_handoff_repair_20260728_v1.sh"
EXECUTION_DIR = "physical-payload-handoff-repair-execution-package"
BINDING_FILE = "PAYLOAD_HANDOFF_REPAIR_REVIEW_BINDING.json"
REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-physical-payload-handoff-repair-review-v1.tar"
IMMUTABLE_ZIP_NAME = "stage2d9r-g3r-repaired-immutable-recovery-freeze-v3.zip"
REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-review/1"
EXECUTION_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-execution-package/1"

SOURCE_FILES = (
    "docs/decisions/h3-n2-stage2d9r-g3r-physical-payload-handoff-repair-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-physical-payload-handoff-repair-contract-20260728-v1.md",
    f"tools/{WRAPPER_NAME}",
    "tools/h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_packager_20260728_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_20260728_v1.py",
)


def launcher_bytes() -> bytes:
    return f"""#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <authorization.json> <result.json>" >&2
  exit 2
fi
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
AUTH="$1"
RESULT="$2"
WORK="$(mktemp -d "${{TMPDIR:-/tmp}}/stage2d9r-payload-handoff-repair.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PKG="$WORK/package"
IMM="$WORK/immutable-extracted"
REC="$WORK/recovery-extracted"
mkdir -m 700 "$PKG" "$IMM" "$REC"
find "$ROOT" -maxdepth 1 -type f -exec cp {{}} "$PKG/" \\;
chmod 600 "$PKG"/*
exec python3 "$PKG/{WRAPPER_NAME}" \
  --package-root "$PKG" \
  --authorization-record "$AUTH" \
  --immutable-payload-tar "$PKG/stage2d9r-g3r-repaired-immutable-payload-v1.tar" \
  --immutable-root "$IMM" \
  --recovery-payload-tar "$PKG/stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar" \
  --recovery-root "$REC" \
  --result-output "$RESULT"
""".encode("utf-8")


def recursive_files(root: Path, *, exclude: set[str] | None = None) -> dict[str, bytes]:
    ignored = exclude or set()
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name in ignored:
            continue
        safe_name(name)
        result[name] = path.read_bytes()
    return result


def canonical_execution_package_digest(root: Path) -> str:
    entries = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    return canonical_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-package-set/1",
            "files": entries,
        }
    )


def build_execution_package(
    repository_root: Path,
    output: Path,
    source_sha: str,
    immutable_files: Mapping[str, bytes],
) -> dict[str, Any]:
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    tool_root = repository_root / "tools"
    for name in (WRAPPER_NAME, FROZEN_WRAPPER_NAME, CORE_NAME, REPAIR_NAME):
        copy_public(tool_root / name, output / name)

    immutable_tar = immutable_files["stage2d9r-g3r-repaired-immutable-payload-v1.tar"]
    recovery_tar = immutable_files["stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"]
    immutable_members = read_tar_members(immutable_tar)
    recovery_members = read_tar_members(recovery_tar)
    expected_i = {
        "SHA256SUMS",
        "application.bin",
        "bootloader.bin",
        "firmware-payload.json",
        "merged-image.bin",
        "partition-table.bin",
    }
    expected_r = {
        "SHA256SUMS",
        "erased-test-partition.bin",
        "locked-recovery-descriptor.json",
        "locked-recovery-plan.json",
    }
    require(set(immutable_members) == expected_i, "IMMUTABLE_PAYLOAD_INVENTORY_MISMATCH")
    require(set(recovery_members) == expected_r, "RECOVERY_PAYLOAD_INVENTORY_MISMATCH")
    require(
        sha256_bytes(immutable_tar) == contract.IMMUTABLE_PAYLOAD_SHA256,
        "IMMUTABLE_PAYLOAD_DIGEST_MISMATCH",
    )
    require(
        sha256_bytes(recovery_tar) == contract.RECOVERY_PAYLOAD_SHA256,
        "RECOVERY_PAYLOAD_DIGEST_MISMATCH",
    )
    require(
        sha256_bytes(immutable_members["merged-image.bin"])
        == contract.IMMUTABLE_MERGED_IMAGE_SHA256,
        "MERGED_IMAGE_DIGEST_MISMATCH",
    )
    require(
        sha256_bytes(immutable_members["partition-table.bin"])
        == contract.IMMUTABLE_PARTITION_TABLE_SHA256,
        "PARTITION_TABLE_DIGEST_MISMATCH",
    )
    require(
        sha256_bytes(recovery_members["locked-recovery-descriptor.json"])
        == contract.RECOVERY_DESCRIPTOR_SHA256,
        "RECOVERY_DESCRIPTOR_DIGEST_MISMATCH",
    )
    require(
        sha256_bytes(recovery_members["erased-test-partition.bin"])
        == contract.ERASED_PARTITION_SHA256,
        "ERASED_PARTITION_DIGEST_MISMATCH",
    )

    for name, value in (
        ("stage2d9r-g3r-repaired-immutable-payload-v1.tar", immutable_tar),
        ("stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar", recovery_tar),
        ("final-execution-binding.json", immutable_files["final-execution-binding.json"]),
        (
            "immutable-recovery-freeze-manifest.json",
            immutable_files["immutable-recovery-freeze-manifest.json"],
        ),
        (LAUNCHER_NAME, launcher_bytes()),
    ):
        write_file(output / name, value, 0o600)

    wrapper_sha = sha256_file(output / WRAPPER_NAME)
    frozen_wrapper_sha = sha256_file(output / FROZEN_WRAPPER_NAME)
    launcher_sha = sha256_file(output / LAUNCHER_NAME)
    core_sha = sha256_file(output / CORE_NAME)
    repair_sha = sha256_file(output / REPAIR_NAME)
    binding = {
        "schema": EXECUTION_SCHEMA,
        "state": "PHYSICAL_PAYLOAD_HANDOFF_REPAIR_FROZEN_UNAUTHORIZED",
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_SHA256,
        "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_SHA256,
        "payload_handoff_contract": "ORIGINAL_TAR_AND_EMPTY_EXTRACTION_ROOTS_SEPARATE",
        "tar_digest_verified_before_extraction": True,
        "sha256sums_exact_coverage_required": True,
        "path_traversal_rejected": True,
        "symbolic_links_rejected": True,
        "macos_realpath_normalization_required": True,
        "authorization_created_preclaim_failure_consumed": True,
        "preclaim_failure_replay_permitted": False,
        "execution_wrapper_sha256": wrapper_sha,
        "frozen_execution_wrapper_sha256": frozen_wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "frozen_executor_core_sha256": core_sha,
        "repaired_host_controller_sha256": repair_sha,
        "locked_recovery_operation_sequence": [
            "READ_TEST_PARTITION",
            "ERASE_TEST_PARTITION_REGION",
            "READ_TEST_PARTITION",
        ],
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "whole_chip_recovery_erase_permitted": False,
        "recovery_write_flash_permitted": False,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
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
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    write_file(output / "EXECUTION_PACKAGE_BINDING.json", pretty_bytes(binding), 0o600)
    sums_entries = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != SUMS_FILE
    ]
    write_file(output / SUMS_FILE, ("\n".join(sums_entries) + "\n").encode(), 0o600)
    return {
        "execution_package_sha256": canonical_execution_package_digest(output),
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "frozen_executor_core_sha256": core_sha,
        "repaired_host_controller_sha256": repair_sha,
    }


def build(
    repository_root: Path,
    immutable_zip: Path,
    output_root: Path,
    source_sha: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    immutable_zip = immutable_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR189")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)

    immutable_files = validate_immutable_zip(immutable_zip)
    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(immutable_zip, output_root / IMMUTABLE_ZIP_NAME)
    execution = build_execution_package(
        repository_root,
        output_root / EXECUTION_DIR,
        source_sha,
        immutable_files,
    )

    binding: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "state": "PHYSICAL_PAYLOAD_HANDOFF_REPAIR_SOURCE_FROZEN_UNAUTHORIZED",
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "old_physical_d2_id": OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": "CONSUMED_FAILED",
        "old_physical_d2_failure_code": OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": False,
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "host_final_artifact_id": HOST_FINAL_ARTIFACT_ID,
        "host_final_artifact_sha256": HOST_FINAL_ARTIFACT_SHA256,
        "immutable_payload_content_changed": False,
        "recovery_payload_content_changed": False,
        "payload_handoff_contract": "ORIGINAL_TAR_AND_EMPTY_EXTRACTION_ROOTS_SEPARATE",
        "authorization_created_preclaim_failure_contract": "CONSUMED_FAILED_NO_REPLAY",
        "next_gate": "NEW_HOST_ONLY_FINAL_PREFLIGHT_REVIEW_AND_EXACT_AUTHORIZATION",
        **execution,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
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
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    binding_without = dict(binding)
    binding["review_binding_sha256"] = canonical_sha256(binding_without)
    write_file(output_root / BINDING_FILE, pretty_bytes(binding), 0o600)

    readme = f"""# Stage2D9R G3R physical payload handoff repair review

This package is layered from Draft PR #{BASE_PR} exact HEAD `{BASE_HEAD_SHA}`.
It changes only the public execution handoff layer: the original immutable and
recovery TAR files remain separate from their empty extraction roots. The TAR
and immutable/recovery payload bytes are unchanged.

The old physical D2 `{OLD_PHYSICAL_D2_ID}` remains permanently CONSUMED_FAILED
with replay prohibited. This review package creates no host or physical
authorization and performs no board, serial, esptool, Flash/NVS, Broker,
PREPARE, VERIFY, ACTIVATE, CLEANUP, Ready, merge, release, tag or deployment.
"""
    write_file(output_root / "README.md", readme.encode("utf-8"), 0o600)

    files_before_sums = recursive_files(
        output_root,
        exclude={SUMS_FILE, REVIEW_ARCHIVE_NAME},
    )
    sums = "".join(
        f"{sha256_bytes(files_before_sums[name])}  {name}\n"
        for name in sorted(files_before_sums)
    ).encode()
    write_file(output_root / SUMS_FILE, sums, 0o600)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive, 0o600)

    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "archive_name": REVIEW_ARCHIVE_NAME,
        "archive_sha256": sha256_bytes(archive),
        "review_binding_sha256": binding["review_binding_sha256"],
        **execution,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
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
        "activate_executed": False,
        "cleanup_executed": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--repository-root", type=Path, required=True)
    argument_parser.add_argument("--immutable-artifact-zip", type=Path, required=True)
    argument_parser.add_argument("--output-root", type=Path, required=True)
    argument_parser.add_argument("--source-sha", required=True)
    args = argument_parser.parse_args()
    try:
        result = build(
            args.repository_root,
            args.immutable_artifact_zip,
            args.output_root,
            args.source_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
