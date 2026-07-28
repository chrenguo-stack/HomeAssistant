#!/usr/bin/env python3
"""Immutable and execution-package helpers for repaired host final preflight."""
from __future__ import annotations

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import *

def validate_immutable_zip(path: Path) -> dict[str, bytes]:
    require(path.is_file() and not path.is_symlink(), "IMMUTABLE_ZIP_INVALID")
    require(
        sha256_file(path) == contract.IMMUTABLE_ARTIFACT_SHA256,
        "IMMUTABLE_ZIP_DIGEST_MISMATCH",
    )
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "IMMUTABLE_ZIP_DUPLICATE_MEMBER")
        require(set(names) == IMMUTABLE_MEMBERS, "IMMUTABLE_ZIP_INVENTORY_MISMATCH")
        files = {name: archive.read(name) for name in names}
    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == IMMUTABLE_MEMBERS - {"SHA256SUMS"}, "IMMUTABLE_SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest, "IMMUTABLE_MEMBER_DIGEST_MISMATCH")
    require(
        sha256_bytes(files["stage2d9r-g3r-repaired-immutable-payload-v1.tar"])
        == contract.IMMUTABLE_PAYLOAD_SHA256,
        "IMMUTABLE_PAYLOAD_MISMATCH",
    )
    require(
        sha256_bytes(files["stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"])
        == contract.RECOVERY_PAYLOAD_SHA256,
        "RECOVERY_PAYLOAD_MISMATCH",
    )
    binding = json.loads(files["final-execution-binding.json"])
    freeze = json.loads(files["immutable-recovery-freeze-manifest.json"])
    require(
        binding.get("final_execution_binding") == contract.FINAL_EXECUTION_BINDING,
        "FINAL_BINDING_SHORT_MISMATCH",
    )
    require(
        binding.get("final_execution_binding_sha256")
        == contract.FINAL_EXECUTION_BINDING_SHA256,
        "FINAL_BINDING_FULL_MISMATCH",
    )
    require(
        freeze.get("state")
        == "REPAIRED_IMMUTABLE_RECOVERY_FROZEN_FINAL_BINDING_READY",
        "FINAL_FREEZE_STATE_MISMATCH",
    )
    require(freeze.get("execution_authorized") is False, "FINAL_FREEZE_EXECUTION_EXPANDED")
    return files


def launcher_bytes() -> bytes:
    return """#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <authorization.json> <result.json>" >&2
  exit 2
fi
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
AUTH="$1"
RESULT="$2"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/stage2d9r-repaired-physical-d2.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PKG="$WORK/package"
IMM="$WORK/immutable"
REC="$WORK/recovery"
mkdir -m 700 "$PKG" "$IMM" "$REC"
find "$ROOT" -maxdepth 1 -type f -exec cp {} "$PKG/" \;
chmod 600 "$PKG"/*
python3 - "$PKG" "$IMM" "$REC" <<'PY'
from pathlib import Path
import os, sys, tarfile
pkg, imm, rec = map(Path, sys.argv[1:])
for tar_name, out in (
    ("stage2d9r-g3r-repaired-immutable-payload-v1.tar", imm),
    ("stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar", rec),
):
    with tarfile.open(pkg / tar_name, "r") as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise SystemExit("unsafe payload member")
            handle = archive.extractfile(member)
            if handle is None:
                raise SystemExit("unreadable payload member")
            target = out / member.name
            target.write_bytes(handle.read())
            os.chmod(target, 0o600)
PY
exec python3 "$PKG/h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py" \
  --package-root "$PKG" \
  --authorization-record "$AUTH" \
  --immutable-root "$IMM" \
  --recovery-root "$REC" \
  --result-output "$RESULT"
""".encode("utf-8")


def canonical_execution_package_digest(root: Path) -> str:
    entries = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file():
            entries.append({"name": path.name, "sha256": sha256_file(path)})
    return canonical_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
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
    for name in EXECUTION_SOURCE_NAMES:
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
        ("merged-image.bin", immutable_members["merged-image.bin"]),
        ("erased-test-partition.bin", recovery_members["erased-test-partition.bin"]),
        ("locked-recovery-descriptor.json", recovery_members["locked-recovery-descriptor.json"]),
        ("final-execution-binding.json", immutable_files["final-execution-binding.json"]),
        ("immutable-recovery-freeze-manifest.json", immutable_files["immutable-recovery-freeze-manifest.json"]),
        ("run_stage2d9r_g3r_repaired_physical_d2_20260728_v1.sh", launcher_bytes()),
    ):
        write_file(output / name, value, 0o600)

    wrapper_sha = sha256_file(
        output / "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
    )
    launcher_sha = sha256_file(
        output / "run_stage2d9r_g3r_repaired_physical_d2_20260728_v1.sh"
    )
    repaired_sha = sha256_file(
        output / "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
    )
    final_binding = json.loads(immutable_files["final-execution-binding.json"])
    final_payload = final_binding.get("payload")
    require(isinstance(final_payload, dict), "FINAL_BINDING_PAYLOAD_INVALID")
    final_bindings = final_payload.get("bindings")
    require(isinstance(final_bindings, dict), "FINAL_BINDING_DIGESTS_INVALID")
    require(
        final_bindings.get("repaired_host_controller_sha256") == repaired_sha,
        "REPAIRED_HOST_CONTROLLER_FINAL_BINDING_MISMATCH",
    )
    core_sha = sha256_file(
        output / "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"
    )
    binding = {
        "schema": EXECUTION_SCHEMA,
        "state": "PHYSICAL_D2_EXECUTION_PACKAGE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "d2_request_id": contract.PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "immutable_source_sha": contract.BASE_HEAD_SHA,
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "baseline_original_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": contract.IMMUTABLE_ARTIFACT_SHA256,
        "final_execution_binding": contract.FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
        "baseline_result_sha256": contract.BASELINE_RESULT_SHA256,
        "board_identity_sha256": contract.BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": contract.SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": contract.BASELINE_STATE_SHA256,
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "frozen_executor_core_sha256": core_sha,
        "repaired_host_controller_sha256": repaired_sha,
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
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    write_file(output / "EXECUTION_PACKAGE_BINDING.json", pretty_bytes(binding), 0o600)

    sums_entries = []
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != SUMS_FILE:
            sums_entries.append(f"{sha256_file(path)}  {path.name}")
    write_file(output / SUMS_FILE, ("\n".join(sums_entries) + "\n").encode(), 0o600)
    package_sha = canonical_execution_package_digest(output)
    return {
        "execution_package_sha256": package_sha,
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "repaired_host_controller_sha256": repaired_sha,
        "frozen_executor_core_sha256": core_sha,
    }


def recursive_files(root: Path, *, exclude: set[str] | None = None) -> dict[str, bytes]:
    ignored = exclude or set()
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if name in ignored:
                continue
            safe_name(name)
            result[name] = path.read_bytes()
    return result
