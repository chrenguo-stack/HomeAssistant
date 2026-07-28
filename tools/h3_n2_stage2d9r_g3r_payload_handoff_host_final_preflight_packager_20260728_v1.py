#!/usr/bin/env python3
"""Build deterministic public review packages for repaired host-final preflight."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
import zipfile

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import *
import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1 as frozen

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-review/1"
EXECUTION_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-final-physical-d2-package/1"
REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-payload-handoff-host-final-preflight-review-v1.tar"
REPAIR_ARTIFACT_NAME = "stage2d9r-g3r-physical-payload-handoff-repair-review-v1.zip"
EXECUTION_DIR = "payload-handoff-final-physical-d2-execution-package"
BINDING_FILE = "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_REVIEW_BINDING.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_DRAFT.json"
SUMS_FILE = "SHA256SUMS"

FINAL_WRAPPER = "h3_n2_stage2d9r_g3r_payload_handoff_final_physical_d2_wrapper_20260728_v1.py"
FINAL_LAUNCHER = "run_stage2d9r_g3r_payload_handoff_final_physical_d2_20260728_v1.sh"
CONTRACT_FILE = "h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_contract_20260728_v1.py"
HOST_PROBE = "h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_probe_20260728_v1.py"
HANDOFF_WRAPPER = "h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1.py"
FROZEN_WRAPPER = "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
CORE = "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"
SERIAL_REPAIR = "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
OLD_LAUNCHER = "run_stage2d9r_g3r_physical_payload_handoff_repair_20260728_v1.sh"

SOURCE_FILES = (
    "docs/decisions/h3-n2-stage2d9r-g3r-payload-handoff-host-final-preflight-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-payload-handoff-host-final-preflight-contract-20260728-v1.md",
    f"tools/{CONTRACT_FILE}",
    f"tools/{FINAL_WRAPPER}",
    "tools/h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_packager_20260728_v1.py",
    f"tools/{HOST_PROBE}",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_common_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_validation_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_execution_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_20260728_v1.py",
)

REPAIR_ZIP_MEMBERS = {
    "PAYLOAD_HANDOFF_REPAIR_REVIEW_BINDING.json",
    "README.md",
    "SHA256SUMS",
    "docs/decisions/h3-n2-stage2d9r-g3r-physical-payload-handoff-repair-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-physical-payload-handoff-repair-contract-20260728-v1.md",
    "physical-payload-handoff-repair-execution-package/EXECUTION_PACKAGE_BINDING.json",
    "physical-payload-handoff-repair-execution-package/SHA256SUMS",
    "physical-payload-handoff-repair-execution-package/final-execution-binding.json",
    "physical-payload-handoff-repair-execution-package/h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1.py",
    "physical-payload-handoff-repair-execution-package/h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py",
    "physical-payload-handoff-repair-execution-package/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py",
    "physical-payload-handoff-repair-execution-package/h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
    "physical-payload-handoff-repair-execution-package/immutable-recovery-freeze-manifest.json",
    "physical-payload-handoff-repair-execution-package/run_stage2d9r_g3r_physical_payload_handoff_repair_20260728_v1.sh",
    "physical-payload-handoff-repair-execution-package/stage2d9r-g3r-repaired-immutable-payload-v1.tar",
    "physical-payload-handoff-repair-execution-package/stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar",
    "stage2d9r-g3r-physical-payload-handoff-repair-review-v1.tar",
    "stage2d9r-g3r-repaired-immutable-recovery-freeze-v3.zip",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_packager_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1.py",
}


def _json(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_repair_artifact(path: Path) -> dict[str, bytes]:
    require(path.is_file() and not path.is_symlink(), "REPAIR_ARTIFACT_INVALID")
    require(sha256_file(path) == contract.PAYLOAD_REPAIR_ARTIFACT_SHA256, "REPAIR_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "REPAIR_ARTIFACT_DUPLICATE_MEMBER")
        require(set(names) == REPAIR_ZIP_MEMBERS, "REPAIR_ARTIFACT_INVENTORY_MISMATCH")
        files = {name: archive.read(name) for name in names}
    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == REPAIR_ZIP_MEMBERS - {"SHA256SUMS", "stage2d9r-g3r-physical-payload-handoff-repair-review-v1.tar"}, "REPAIR_SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest, "REPAIR_MEMBER_DIGEST_MISMATCH")

    binding = _json(files["PAYLOAD_HANDOFF_REPAIR_REVIEW_BINDING.json"], "REPAIR_BINDING_INVALID")
    supplied = binding.get("review_binding_sha256")
    without = dict(binding)
    without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "REPAIR_BINDING_DIGEST_MISMATCH")
    exact = {
        "source_sha": contract.BASE_HEAD_SHA,
        "base_pr": 189,
        "base_head_sha": "45c80baf43ccc3f917ae5964ee92a202a74cc2ba",
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "review_binding_sha256": contract.PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "execution_package_sha256": contract.PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "execution_wrapper_sha256": contract.PAYLOAD_REPAIR_WRAPPER_SHA256,
        "execution_launcher_sha256": contract.PAYLOAD_REPAIR_LAUNCHER_SHA256,
        "payload_handoff_contract": contract.PAYLOAD_HANDOFF_CONTRACT,
        "old_physical_d2_id": contract.OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "REPAIR_BINDING_" + key.upper() + "_MISMATCH")
    for key in ("authorized", "authorization_created", "authorization_claimed", "authorization_consumed", "board_operation", "usb_enumeration", "serial_operation", "esptool_operation", "flash_operation", "physical_nvs_operation", "network_operation", "broker_started", "prepare_executed", "verify_executed"):
        require(binding.get(key) is False, "REPAIR_BINDING_BOUNDARY_" + key.upper())

    prefix = "physical-payload-handoff-repair-execution-package/"
    exec_sums = parse_sums(files[prefix + "SHA256SUMS"])
    observed = {
        name[len(prefix):]
        for name in files
        if name.startswith(prefix) and name != prefix + "SHA256SUMS"
    }
    require(set(exec_sums) == observed, "REPAIR_EXECUTION_SUMS_INVENTORY_MISMATCH")
    for name, digest in exec_sums.items():
        require(sha256_bytes(files[prefix + name]) == digest, "REPAIR_EXECUTION_MEMBER_DIGEST_MISMATCH")
    execution = _json(files[prefix + "EXECUTION_PACKAGE_BINDING.json"], "REPAIR_EXECUTION_BINDING_INVALID")
    require(execution.get("execution_wrapper_sha256") == contract.PAYLOAD_REPAIR_WRAPPER_SHA256, "REPAIR_EXECUTION_WRAPPER_MISMATCH")
    require(execution.get("execution_launcher_sha256") == contract.PAYLOAD_REPAIR_LAUNCHER_SHA256, "REPAIR_EXECUTION_LAUNCHER_MISMATCH")
    require(execution.get("payload_handoff_contract") == contract.PAYLOAD_HANDOFF_CONTRACT, "REPAIR_EXECUTION_HANDOFF_MISMATCH")
    require(execution.get("authorization_created_preclaim_failure_consumed") is True, "REPAIR_PRECLAIM_CONTRACT_MISSING")
    require(execution.get("preclaim_failure_replay_permitted") is False, "REPAIR_PRECLAIM_REPLAY_EXPANDED")
    require(files[prefix + "stage2d9r-g3r-repaired-immutable-payload-v1.tar"] and sha256_bytes(files[prefix + "stage2d9r-g3r-repaired-immutable-payload-v1.tar"]) == frozen.IMMUTABLE_PAYLOAD_SHA256, "IMMUTABLE_PAYLOAD_CHANGED")
    require(files[prefix + "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"] and sha256_bytes(files[prefix + "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"]) == frozen.RECOVERY_PAYLOAD_SHA256, "RECOVERY_PAYLOAD_CHANGED")
    require(sha256_bytes(files["stage2d9r-g3r-repaired-immutable-recovery-freeze-v3.zip"]) == frozen.IMMUTABLE_ARTIFACT_SHA256, "EMBEDDED_IMMUTABLE_ARTIFACT_MISMATCH")
    return files


def launcher_bytes() -> bytes:
    return f'''#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <authorization.json> <result.json>" >&2
  exit 2
fi
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
AUTH="$1"
RESULT="$2"
WORK="$(mktemp -d "${{TMPDIR:-/tmp}}/stage2d9r-payload-handoff-final.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PKG="$WORK/package"
IMM="$WORK/immutable-extracted"
REC="$WORK/recovery-extracted"
mkdir -m 700 "$PKG" "$IMM" "$REC"
find "$ROOT" -maxdepth 1 -type f -exec cp {{}} "$PKG/" \\;
chmod 600 "$PKG"/*
exec python3 "$PKG/{FINAL_WRAPPER}" \\
  --package-root "$PKG" \\
  --authorization-record "$AUTH" \\
  --immutable-payload-tar "$PKG/stage2d9r-g3r-repaired-immutable-payload-v1.tar" \\
  --immutable-root "$IMM" \\
  --recovery-payload-tar "$PKG/stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar" \\
  --recovery-root "$REC" \\
  --result-output "$RESULT"
'''.encode("utf-8")


def canonical_execution_package_digest(root: Path) -> str:
    entries = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-payload-handoff-final-package-set/1",
        "files": entries,
    })


def build_execution_package(repository_root: Path, output: Path, source_sha: str, repair_files: Mapping[str, bytes]) -> dict[str, str]:
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    prefix = "physical-payload-handoff-repair-execution-package/"
    for name in (HANDOFF_WRAPPER, FROZEN_WRAPPER, CORE, SERIAL_REPAIR, OLD_LAUNCHER, "final-execution-binding.json", "immutable-recovery-freeze-manifest.json", "stage2d9r-g3r-repaired-immutable-payload-v1.tar", "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"):
        write_file(output / name, repair_files[prefix + name], 0o600)
    copy_public(repository_root / "tools" / CONTRACT_FILE, output / CONTRACT_FILE)
    copy_public(repository_root / "tools" / FINAL_WRAPPER, output / FINAL_WRAPPER)
    write_file(output / FINAL_LAUNCHER, launcher_bytes(), 0o600)

    wrapper_sha = sha256_file(output / FINAL_WRAPPER)
    launcher_sha = sha256_file(output / FINAL_LAUNCHER)
    handoff_sha = sha256_file(output / HANDOFF_WRAPPER)
    core_sha = sha256_file(output / CORE)
    repaired_sha = sha256_file(output / SERIAL_REPAIR)
    require(handoff_sha == contract.PAYLOAD_REPAIR_WRAPPER_SHA256, "HANDOFF_WRAPPER_DIGEST_MISMATCH")

    binding: dict[str, Any] = {
        "schema": EXECUTION_SCHEMA,
        "state": "PAYLOAD_HANDOFF_FINAL_PHYSICAL_D2_PACKAGE_FROZEN_UNAUTHORIZED",
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "payload_handoff_repair_source_sha": contract.BASE_HEAD_SHA,
        "payload_handoff_base_pr": contract.BASE_PR,
        "payload_handoff_base_head_sha": contract.BASE_HEAD_SHA,
        "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "payload_repair_review_binding_sha256": contract.PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "payload_repair_execution_package_sha256": contract.PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "payload_handoff_contract": contract.PAYLOAD_HANDOFF_CONTRACT,
        "preclaim_failure_contract": contract.PRECLAIM_FAILURE_CONTRACT,
        "old_physical_d2_id": contract.OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": False,
        "immutable_artifact_id": frozen.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": frozen.IMMUTABLE_ARTIFACT_SHA256,
        "immutable_payload_tar_sha256": frozen.IMMUTABLE_PAYLOAD_SHA256,
        "recovery_payload_tar_sha256": frozen.RECOVERY_PAYLOAD_SHA256,
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "payload_handoff_wrapper_sha256": handoff_sha,
        "frozen_executor_core_sha256": core_sha,
        "repaired_host_controller_sha256": repaired_sha,
        "locked_recovery_operation_sequence": ["READ_TEST_PARTITION", "ERASE_TEST_PARTITION_REGION", "READ_TEST_PARTITION"],
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
    entries = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != SUMS_FILE
    ]
    write_file(output / SUMS_FILE, ("\n".join(entries) + "\n").encode(), 0o600)
    return {
        "execution_package_sha256": canonical_execution_package_digest(output),
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "payload_handoff_wrapper_sha256": handoff_sha,
        "frozen_executor_core_sha256": core_sha,
        "repaired_host_controller_sha256": repaired_sha,
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


def build(repository_root: Path, repair_artifact_zip: Path, output_root: Path, source_sha: str) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    repair_artifact_zip = repair_artifact_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR190")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)
    repair_files = validate_repair_artifact(repair_artifact_zip)
    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(repair_artifact_zip, output_root / REPAIR_ARTIFACT_NAME)
    execution = build_execution_package(repository_root, output_root / EXECUTION_DIR, source_sha, repair_files)

    binding: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "state": "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "payload_repair_review_binding_sha256": contract.PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "payload_repair_execution_package_sha256": contract.PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "payload_handoff_contract": contract.PAYLOAD_HANDOFF_CONTRACT,
        "preclaim_failure_contract": contract.PRECLAIM_FAILURE_CONTRACT,
        "old_physical_d2_id": contract.OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": False,
        **execution,
        "future_host_authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
        "future_physical_d2_request_id": contract.PHYSICAL_D2_REQUEST_ID,
        "host_preflight_executed": False,
        **contract.FALSE_BOUNDARY,
    }
    without = dict(binding)
    binding["review_binding_sha256"] = canonical_sha256(without)
    write_file(output_root / BINDING_FILE, pretty_bytes(binding), 0o600)
    request = contract.build_request_template(
        source_sha=source_sha,
        review_binding_sha256=binding["review_binding_sha256"],
        execution_package_sha256=execution["execution_package_sha256"],
        execution_wrapper_sha256=execution["execution_wrapper_sha256"],
        execution_launcher_sha256=execution["execution_launcher_sha256"],
        repaired_host_controller_sha256=execution["repaired_host_controller_sha256"],
    )
    write_file(output_root / REQUEST_FILE, pretty_bytes(request), 0o600)
    write_file(output_root / "README.md", (
        "# Payload-handoff repaired host-final preflight review package\n\n"
        "This public package is layered from Draft PR #190 and the exact repair Artifact. "
        "It remains unauthorized and contains no private custody values or physical authorization.\n"
    ).encode(), 0o600)
    files_before_sums = recursive_files(output_root, exclude={SUMS_FILE, REVIEW_ARCHIVE_NAME})
    sums = "".join(f"{sha256_bytes(files_before_sums[name])}  {name}\n" for name in sorted(files_before_sums)).encode()
    write_file(output_root / SUMS_FILE, sums, 0o600)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive, 0o600)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-package-result/1",
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--repair-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = build(args.repository_root, args.repair_artifact_zip, args.output_root, args.source_sha)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
