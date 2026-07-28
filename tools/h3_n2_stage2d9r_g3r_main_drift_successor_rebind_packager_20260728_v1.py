#!/usr/bin/env python3
"""Build deterministic review and execution packages for the accepted main drift."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
import zipfile

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import (
    PackageError, canonical_sha256, copy_public, deterministic_tar_bytes,
    parse_sums, pretty_bytes, require, safe_name, sha256_bytes, sha256_file,
    write_file,
)
import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1 as contract

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-review/1"
EXECUTION_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-final-physical-d2-package/1"
REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-main-drift-successor-rebind-review-v1.tar"
UPSTREAM_ARTIFACT_NAME = "stage2d9r-g3r-payload-handoff-host-final-preflight-review-v1.zip"
EXECUTION_DIR = "main-drift-rebound-final-physical-d2-execution-package"
BINDING_FILE = "MAIN_DRIFT_SUCCESSOR_REBIND_REVIEW_BINDING.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_DRAFT.json"
STALE_FILE = "STALE_PHYSICAL_D2_REQUEST_02.json"
SUMS_FILE = "SHA256SUMS"

NEW_CONTRACT = "h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1.py"
NEW_WRAPPER = "h3_n2_stage2d9r_g3r_main_drift_rebound_final_physical_d2_wrapper_20260728_v1.py"
NEW_LAUNCHER = "run_stage2d9r_g3r_main_drift_rebound_final_physical_d2_20260728_v1.sh"
HOST_PROBE = "h3_n2_stage2d9r_g3r_main_drift_successor_rebind_probe_20260728_v1.py"
UPSTREAM_EXECUTION_PREFIX = "payload-handoff-final-physical-d2-execution-package/"
IMMUTABLE_TAR = "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
RECOVERY_TAR = "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-main-drift-successor-rebind-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-main-drift-successor-rebind-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-main-drift-successor-rebind-contract-20260728-v1.md",
    f"tools/{NEW_CONTRACT}",
    f"tools/{NEW_WRAPPER}",
    "tools/h3_n2_stage2d9r_g3r_main_drift_successor_rebind_packager_20260728_v1.py",
    f"tools/{HOST_PROBE}",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_main_drift_successor_rebind_20260728_v1.py",
)


def _json(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_upstream_artifact(path: Path) -> dict[str, bytes]:
    require(path.is_file() and not path.is_symlink(), "UPSTREAM_ARTIFACT_INVALID")
    require(sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "UPSTREAM_ARTIFACT_DUPLICATE_MEMBER")
        for name in names:
            safe_name(name)
        files = {name: archive.read(name) for name in names}
    require("SHA256SUMS" in files, "UPSTREAM_SUMS_MISSING")
    sums = parse_sums(files["SHA256SUMS"])
    for name, digest in sums.items():
        require(name in files and sha256_bytes(files[name]) == digest, "UPSTREAM_MEMBER_DIGEST_MISMATCH")
    binding_name = "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_REVIEW_BINDING.json"
    binding = _json(files[binding_name], "UPSTREAM_BINDING_INVALID")
    supplied = binding.get("review_binding_sha256")
    without = dict(binding)
    without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "UPSTREAM_BINDING_DIGEST_MISMATCH")
    exact = {
        "source_sha": contract.BASE_HEAD_SHA,
        "accepted_current_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
        "review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "execution_wrapper_sha256": contract.UPSTREAM_EXECUTION_WRAPPER_SHA256,
        "execution_launcher_sha256": contract.UPSTREAM_EXECUTION_LAUNCHER_SHA256,
        "repaired_host_controller_sha256": contract.UPSTREAM_REPAIRED_HOST_CONTROLLER_SHA256,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "UPSTREAM_BINDING_" + key.upper() + "_MISMATCH")
    require(sha256_bytes(files["stage2d9r-g3r-payload-handoff-host-final-preflight-review-v1.tar"]) == contract.UPSTREAM_REVIEW_ARCHIVE_SHA256, "UPSTREAM_REVIEW_ARCHIVE_MISMATCH")

    exec_sums_name = UPSTREAM_EXECUTION_PREFIX + SUMS_FILE
    exec_sums = parse_sums(files[exec_sums_name])
    observed = {
        name[len(UPSTREAM_EXECUTION_PREFIX):]
        for name in files
        if name.startswith(UPSTREAM_EXECUTION_PREFIX) and name != exec_sums_name
    }
    require(set(exec_sums) == observed, "UPSTREAM_EXECUTION_SUMS_INVENTORY_MISMATCH")
    for name, digest in exec_sums.items():
        require(sha256_bytes(files[UPSTREAM_EXECUTION_PREFIX + name]) == digest, "UPSTREAM_EXECUTION_MEMBER_DIGEST_MISMATCH")
    require(sha256_bytes(files[UPSTREAM_EXECUTION_PREFIX + "h3_n2_stage2d9r_g3r_payload_handoff_final_physical_d2_wrapper_20260728_v1.py"]) == contract.UPSTREAM_EXECUTION_WRAPPER_SHA256, "UPSTREAM_EXECUTION_WRAPPER_MISMATCH")
    require(sha256_bytes(files[UPSTREAM_EXECUTION_PREFIX + "run_stage2d9r_g3r_payload_handoff_final_physical_d2_20260728_v1.sh"]) == contract.UPSTREAM_EXECUTION_LAUNCHER_SHA256, "UPSTREAM_EXECUTION_LAUNCHER_MISMATCH")
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
WORK="$(mktemp -d "${{TMPDIR:-/tmp}}/stage2d9r-main-drift-rebound.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PKG="$WORK/package"
IMM="$WORK/immutable-extracted"
REC="$WORK/recovery-extracted"
mkdir -m 700 "$PKG" "$IMM" "$REC"
find "$ROOT" -maxdepth 1 -type f -exec cp {{}} "$PKG/" \\;
chmod 600 "$PKG"/*
exec python3 "$PKG/{NEW_WRAPPER}" \\
  --package-root "$PKG" \\
  --authorization-record "$AUTH" \\
  --immutable-payload-tar "$PKG/{IMMUTABLE_TAR}" \\
  --immutable-root "$IMM" \\
  --recovery-payload-tar "$PKG/{RECOVERY_TAR}" \\
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
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": entries,
    })


def build_execution_package(repository_root: Path, output: Path, source_sha: str, upstream: dict[str, bytes]) -> dict[str, str]:
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    for full_name, data in sorted(upstream.items()):
        if not full_name.startswith(UPSTREAM_EXECUTION_PREFIX):
            continue
        name = full_name[len(UPSTREAM_EXECUTION_PREFIX):]
        if name in {SUMS_FILE, "EXECUTION_PACKAGE_BINDING.json"}:
            continue
        safe_name(name)
        write_file(output / name, data, 0o600)
    copy_public(repository_root / "tools" / NEW_CONTRACT, output / NEW_CONTRACT)
    copy_public(repository_root / "tools" / NEW_WRAPPER, output / NEW_WRAPPER)
    write_file(output / NEW_LAUNCHER, launcher_bytes(), 0o700)

    immutable_sha = sha256_file(output / IMMUTABLE_TAR)
    recovery_sha = sha256_file(output / RECOVERY_TAR)
    require(immutable_sha == "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea", "IMMUTABLE_PAYLOAD_CHANGED")
    require(recovery_sha == "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f", "RECOVERY_PAYLOAD_CHANGED")
    wrapper_sha = sha256_file(output / NEW_WRAPPER)
    launcher_sha = sha256_file(output / NEW_LAUNCHER)
    binding: dict[str, Any] = {
        "schema": EXECUTION_SCHEMA,
        "state": "MAIN_DRIFT_REBOUND_FINAL_PHYSICAL_D2_PACKAGE_FROZEN_UNAUTHORIZED",
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "main_drift_rebind_source_sha": source_sha,
        "upstream_host_final_preflight_source_sha": contract.BASE_HEAD_SHA,
        "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
        "previous_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
        "previous_request_state": contract.OLD_PHYSICAL_D2_REQUEST_STATE,
        "previous_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
        "previous_request_reuse_permitted": False,
        "future_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        "immutable_payload_tar_sha256": immutable_sha,
        "recovery_payload_tar_sha256": recovery_sha,
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_operation_sequence": ["READ_TEST_PARTITION", "ERASE_TEST_PARTITION_REGION", "READ_TEST_PARTITION"],
        "whole_chip_recovery_erase_permitted": False,
        "recovery_write_flash_permitted": False,
        **contract.FALSE_BOUNDARY,
        "production_operation": False,
    }
    write_file(output / "EXECUTION_PACKAGE_BINDING.json", pretty_bytes(binding), 0o600)
    entries = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != SUMS_FILE
    ]
    write_file(output / SUMS_FILE, ("\n".join(entries) + "\n").encode("utf-8"), 0o600)
    return {
        "execution_package_sha256": canonical_execution_package_digest(output),
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
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


def build(repository_root: Path, upstream_artifact_zip: Path, output_root: Path, source_sha: str) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    upstream_artifact_zip = upstream_artifact_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR193")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)
    upstream = validate_upstream_artifact(upstream_artifact_zip)
    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(upstream_artifact_zip, output_root / UPSTREAM_ARTIFACT_NAME)
    execution = build_execution_package(repository_root, output_root / EXECUTION_DIR, source_sha, upstream)

    binding: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "state": "MAIN_DRIFT_SUCCESSOR_REBIND_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
        "main_drift_changed_files": list(contract.MAIN_DRIFT_CHANGED_FILES),
        "main_drift_commit_count": contract.MAIN_DRIFT_COMMIT_COUNT,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
        "old_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
        "old_request_state": contract.OLD_PHYSICAL_D2_REQUEST_STATE,
        "old_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
        "old_request_reuse_permitted": False,
        "future_host_rebind_authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
        "future_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        **execution,
        "host_rebind_executed": False,
        **contract.FALSE_BOUNDARY,
    }
    binding["review_binding_sha256"] = canonical_sha256(binding)
    write_file(output_root / BINDING_FILE, pretty_bytes(binding), 0o600)
    request = contract.build_request_draft(
        source_sha=source_sha,
        review_binding_sha256=binding["review_binding_sha256"],
        **execution,
    )
    write_file(output_root / REQUEST_FILE, pretty_bytes(request), 0o600)
    write_file(output_root / STALE_FILE, pretty_bytes(contract.stale_request_disposition()), 0o600)
    write_file(output_root / "README.md", (
        "# Accepted main-drift successor rebind review package\n\n"
        "This public package preserves the consumed H2 result, permanently invalidates "
        "physical request -02 after main drift, and freezes an inert host-only rebind "
        "gate for request -03. It contains no physical authorization or private value.\n"
    ).encode("utf-8"), 0o600)
    files_before_sums = recursive_files(output_root, exclude={SUMS_FILE, REVIEW_ARCHIVE_NAME})
    sums = "".join(f"{sha256_bytes(files_before_sums[name])}  {name}\n" for name in sorted(files_before_sums)).encode("utf-8")
    write_file(output_root / SUMS_FILE, sums, 0o600)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive, 0o600)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "archive_name": REVIEW_ARCHIVE_NAME,
        "archive_sha256": sha256_bytes(archive),
        "review_binding_sha256": binding["review_binding_sha256"],
        **execution,
        **contract.FALSE_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--upstream-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = build(args.repository_root, args.upstream_artifact_zip, args.output_root, args.source_sha)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
