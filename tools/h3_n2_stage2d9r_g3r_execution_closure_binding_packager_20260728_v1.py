#!/usr/bin/env python3
"""Build deterministic review and execution packages for closure binding."""
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
import h3_n2_stage2d9r_g3r_execution_closure_binding_contract_20260728_v1 as contract

REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-execution-closure-binding-review-v1.tar"
UPSTREAM_ARTIFACT_NAME = "stage2d9r-g3r-main-drift-successor-rebind-review-v1.zip"
EXECUTION_DIR = "execution-closure-bound-final-physical-d2-execution-package"
REVIEW_BINDING_FILE = "EXECUTION_CLOSURE_BINDING_REVIEW.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_DRAFT_04.json"
PREVIOUS_DISPOSITION_FILE = "SUPERSEDED_PHYSICAL_D2_REQUEST_03.json"
SUMS_FILE = contract.SUMS_FILE

NEW_CONTRACT = "h3_n2_stage2d9r_g3r_execution_closure_binding_contract_20260728_v1.py"
NEW_WRAPPER = "h3_n2_stage2d9r_g3r_execution_closure_bound_final_physical_d2_wrapper_20260728_v1.py"
NEW_LAUNCHER = "run_stage2d9r_g3r_execution_closure_bound_final_physical_d2_20260728_v1.sh"
HOST_PROBE = "h3_n2_stage2d9r_g3r_execution_closure_binding_probe_20260728_v1.py"
UPSTREAM_EXECUTION_PREFIX = "main-drift-rebound-final-physical-d2-execution-package/"
IMMUTABLE_TAR = "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
RECOVERY_TAR = "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
UPSTREAM_REVIEW_BINDING_FILE = "MAIN_DRIFT_SUCCESSOR_REBIND_REVIEW_BINDING.json"
UPSTREAM_REQUEST_FILE = "PHYSICAL_D2_REQUEST_DRAFT.json"
UPSTREAM_REVIEW_ARCHIVE = "stage2d9r-g3r-main-drift-successor-rebind-review-v1.tar"
UPSTREAM_OLD_RUNTIME_FILES = frozenset({
    "h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1.py",
    "h3_n2_stage2d9r_g3r_main_drift_rebound_final_physical_d2_wrapper_20260728_v1.py",
    "run_stage2d9r_g3r_main_drift_rebound_final_physical_d2_20260728_v1.sh",
})

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-execution-closure-binding-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-execution-closure-binding-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-execution-closure-binding-contract-20260728-v1.md",
    f"tools/{NEW_CONTRACT}",
    f"tools/{NEW_WRAPPER}",
    "tools/h3_n2_stage2d9r_g3r_execution_closure_binding_packager_20260728_v1.py",
    f"tools/{HOST_PROBE}",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_execution_closure_binding_20260728_v1.py",
)


def _json(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(code) from exc
    require(isinstance(value, dict), code)
    return value


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


def canonical_execution_package_digest_from_bytes(files: dict[str, bytes]) -> str:
    entries = [
        {"name": name, "sha256": sha256_bytes(files[name])}
        for name in sorted(files)
    ]
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": entries,
    })


def validate_upstream_artifact(path: Path) -> tuple[dict[str, bytes], str]:
    require(path.is_file() and not path.is_symlink(), "UPSTREAM_ARTIFACT_INVALID")
    require(sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "UPSTREAM_ARTIFACT_DUPLICATE_MEMBER")
        for name in names:
            safe_name(name)
        files = {name: archive.read(name) for name in names}
    require(SUMS_FILE in files, "UPSTREAM_SUMS_MISSING")
    sums = parse_sums(files[SUMS_FILE])
    for name, digest in sums.items():
        require(name in files and sha256_bytes(files[name]) == digest, "UPSTREAM_MEMBER_DIGEST_MISMATCH")

    binding = _json(files[UPSTREAM_REVIEW_BINDING_FILE], "UPSTREAM_BINDING_INVALID")
    supplied = binding.get("review_binding_sha256")
    without = dict(binding)
    without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "UPSTREAM_BINDING_DIGEST_MISMATCH")
    exact = {
        "source_sha": contract.BASE_HEAD_SHA,
        "accepted_current_main_sha": contract.REPOSITORY_HEAD_AT_POLICY_FREEZE,
        "review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "execution_wrapper_sha256": contract.UPSTREAM_EXECUTION_WRAPPER_SHA256,
        "execution_launcher_sha256": contract.UPSTREAM_EXECUTION_LAUNCHER_SHA256,
        "future_physical_d2_request_id": contract.PREVIOUS_REQUEST_ID,
        "host_rebind_executed": False,
        "authorized": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "UPSTREAM_BINDING_" + key.upper() + "_MISMATCH")
    require(sha256_bytes(files[UPSTREAM_REVIEW_ARCHIVE]) == contract.UPSTREAM_REVIEW_ARCHIVE_SHA256,
            "UPSTREAM_REVIEW_ARCHIVE_MISMATCH")

    exec_sums_name = UPSTREAM_EXECUTION_PREFIX + SUMS_FILE
    exec_sums = parse_sums(files[exec_sums_name])
    observed = {
        name[len(UPSTREAM_EXECUTION_PREFIX):]
        for name in files
        if name.startswith(UPSTREAM_EXECUTION_PREFIX) and name != exec_sums_name
    }
    require(set(exec_sums) == observed, "UPSTREAM_EXECUTION_SUMS_INVENTORY_MISMATCH")
    execution_files: dict[str, bytes] = {}
    for name, digest in exec_sums.items():
        full_name = UPSTREAM_EXECUTION_PREFIX + name
        require(sha256_bytes(files[full_name]) == digest, "UPSTREAM_EXECUTION_MEMBER_DIGEST_MISMATCH")
        execution_files[name] = files[full_name]
    require(canonical_execution_package_digest_from_bytes({**execution_files, SUMS_FILE: files[exec_sums_name]})
            == contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
            "UPSTREAM_EXECUTION_PACKAGE_DIGEST_MISMATCH")
    require(sha256_bytes(execution_files[
        "h3_n2_stage2d9r_g3r_main_drift_rebound_final_physical_d2_wrapper_20260728_v1.py"
    ]) == contract.UPSTREAM_EXECUTION_WRAPPER_SHA256, "UPSTREAM_EXECUTION_WRAPPER_MISMATCH")
    require(sha256_bytes(execution_files[
        "run_stage2d9r_g3r_main_drift_rebound_final_physical_d2_20260728_v1.sh"
    ]) == contract.UPSTREAM_EXECUTION_LAUNCHER_SHA256, "UPSTREAM_EXECUTION_LAUNCHER_MISMATCH")

    previous_request_bytes = files[UPSTREAM_REQUEST_FILE]
    previous_request = _json(previous_request_bytes, "UPSTREAM_REQUEST_INVALID")
    require(previous_request.get("d2_request_id") == contract.PREVIOUS_REQUEST_ID,
            "UPSTREAM_REQUEST_ID_MISMATCH")
    require(previous_request.get("authorized") is False, "UPSTREAM_REQUEST_ALREADY_AUTHORIZED")
    require(previous_request.get("authorization_created") is False, "UPSTREAM_REQUEST_AUTH_CREATED")
    require(previous_request.get("request_binding_sha256") is None, "UPSTREAM_REQUEST_ALREADY_FINALIZED")
    return files, sha256_bytes(previous_request_bytes)


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
WORK="$(mktemp -d "${{TMPDIR:-/tmp}}/stage2d9r-execution-closure.XXXXXX")"
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


def build_execution_package(
    repository_root: Path, output: Path, source_sha: str,
    upstream: dict[str, bytes], repository_head_sha: str,
) -> dict[str, str]:
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    for full_name, data in sorted(upstream.items()):
        if not full_name.startswith(UPSTREAM_EXECUTION_PREFIX):
            continue
        name = full_name[len(UPSTREAM_EXECUTION_PREFIX):]
        if name in {SUMS_FILE, contract.EXECUTION_BINDING_FILE} or name in UPSTREAM_OLD_RUNTIME_FILES:
            continue
        safe_name(name)
        write_file(output / name, data, 0o600)
    copy_public(repository_root / "tools" / NEW_CONTRACT, output / NEW_CONTRACT)
    copy_public(repository_root / "tools" / NEW_WRAPPER, output / NEW_WRAPPER)
    write_file(output / NEW_LAUNCHER, launcher_bytes(), 0o700)

    immutable_sha = sha256_file(output / IMMUTABLE_TAR)
    recovery_sha = sha256_file(output / RECOVERY_TAR)
    require(immutable_sha == "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea",
            "IMMUTABLE_PAYLOAD_CHANGED")
    require(recovery_sha == "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f",
            "RECOVERY_PAYLOAD_CHANGED")
    wrapper_sha = sha256_file(output / NEW_WRAPPER)
    launcher_sha = sha256_file(output / NEW_LAUNCHER)

    closure_manifest = contract.build_execution_closure_manifest(output)
    closure_sha = closure_manifest["execution_closure_sha256"]
    write_file(output / contract.CLOSURE_MANIFEST_FILE, pretty_bytes(closure_manifest), 0o600)
    binding: dict[str, Any] = {
        "schema": contract.EXECUTION_BINDING_SCHEMA,
        "state": "EXECUTION_CLOSURE_BOUND_FINAL_PHYSICAL_D2_PACKAGE_FROZEN_UNAUTHORIZED",
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "decision_id": contract.DECISION_ID,
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_sha256": closure_sha,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 1,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "previous_request_id": contract.PREVIOUS_REQUEST_ID,
        "previous_request_state": contract.PREVIOUS_REQUEST_STATE,
        "previous_request_reuse_permitted": False,
        "future_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        "immutable_payload_tar_sha256": immutable_sha,
        "recovery_payload_tar_sha256": recovery_sha,
        "execution_wrapper_sha256": wrapper_sha,
        "execution_launcher_sha256": launcher_sha,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_operation_sequence": [
            "READ_TEST_PARTITION", "ERASE_TEST_PARTITION_REGION", "READ_TEST_PARTITION"
        ],
        "whole_chip_recovery_erase_permitted": False,
        "recovery_write_flash_permitted": False,
        **contract.FALSE_BOUNDARY,
        "production_operation": False,
    }
    write_file(output / contract.EXECUTION_BINDING_FILE, pretty_bytes(binding), 0o600)
    entries = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != SUMS_FILE
    ]
    write_file(output / SUMS_FILE, ("\n".join(entries) + "\n").encode("utf-8"), 0o600)
    contract.validate_execution_closure(output)
    return {
        "execution_package_sha256": canonical_execution_package_digest(output),
        "execution_closure_sha256": closure_sha,
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


def build(
    repository_root: Path, upstream_artifact_zip: Path, output_root: Path,
    source_sha: str, repository_head_sha: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    upstream_artifact_zip = upstream_artifact_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR194")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)
    upstream, previous_request_raw_sha256 = validate_upstream_artifact(upstream_artifact_zip)
    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(upstream_artifact_zip, output_root / UPSTREAM_ARTIFACT_NAME)
    execution = build_execution_package(
        repository_root, output_root / EXECUTION_DIR, source_sha, upstream, repository_head_sha
    )

    binding: dict[str, Any] = {
        "schema": contract.REVIEW_SCHEMA,
        "state": "EXECUTION_CLOSURE_BINDING_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 1,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "previous_host_authorization_id": contract.PREVIOUS_HOST_AUTHORIZATION_ID,
        "previous_host_authorization_created": False,
        "previous_request_id": contract.PREVIOUS_REQUEST_ID,
        "previous_request_state": contract.PREVIOUS_REQUEST_STATE,
        "previous_request_raw_sha256": previous_request_raw_sha256,
        "previous_request_reuse_permitted": False,
        "future_host_authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
        "future_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        **execution,
        "host_preflight_executed": False,
        **contract.FALSE_BOUNDARY,
    }
    binding["review_binding_sha256"] = canonical_sha256(binding)
    write_file(output_root / REVIEW_BINDING_FILE, pretty_bytes(binding), 0o600)
    request = contract.build_request_draft(
        source_sha=source_sha,
        review_binding_sha256=binding["review_binding_sha256"],
        previous_request_raw_sha256=previous_request_raw_sha256,
        **execution,
    )
    write_file(output_root / REQUEST_FILE, pretty_bytes(request), 0o600)
    write_file(
        output_root / PREVIOUS_DISPOSITION_FILE,
        pretty_bytes(contract.previous_request_disposition(previous_request_raw_sha256)),
        0o600,
    )
    write_file(output_root / "README.md", (
        "# Execution-closure binding review package\n\n"
        "Repository HEAD is audit-only. Physical execution remains blocked by the exact "
        "execution closure, execution package, payload, toolchain and one-shot authorization. "
        "This package contains no physical authorization or private value.\n"
    ).encode("utf-8"), 0o600)
    files_before_sums = recursive_files(output_root, exclude={SUMS_FILE, REVIEW_ARCHIVE_NAME})
    sums = "".join(
        f"{sha256_bytes(files_before_sums[name])}  {name}\n" for name in sorted(files_before_sums)
    ).encode("utf-8")
    write_file(output_root / SUMS_FILE, sums, 0o600)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive, 0o600)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-execution-closure-binding-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "repository_head_sha": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
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
    parser.add_argument("--repository-head-sha", required=True)
    args = parser.parse_args()
    try:
        result = build(
            args.repository_root, args.upstream_artifact_zip, args.output_root,
            args.source_sha, args.repository_head_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
