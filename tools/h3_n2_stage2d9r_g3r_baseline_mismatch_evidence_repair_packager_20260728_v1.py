#!/usr/bin/env python3
"""Build a deterministic public review package for baseline evidence repair."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any
import zipfile

import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_contract_20260728_v1 as contract

REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-baseline-mismatch-evidence-repair-review-v1.tar"
UPSTREAM_ARTIFACT_NAME = "stage2d9r-g3r-execution-closure-binding-review-v1.zip"
REVIEW_BINDING_FILE = "BASELINE_MISMATCH_EVIDENCE_REPAIR_REVIEW.json"
PREDECESSOR_DISPOSITION_FILE = "PREDECESSOR_03_CONSUMED_FAILED_DISPOSITION.json"
INVALIDATED_REQUEST_FILE = "INVALIDATED_PHYSICAL_D2_REQUEST_04.json"
DIAGNOSTIC_REQUEST_FILE = "BASELINE_DIAGNOSTIC_REQUEST_DRAFT.json"
SUMS_FILE = "SHA256SUMS"

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-baseline-mismatch-evidence-repair-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-baseline-mismatch-evidence-repair-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-baseline-mismatch-evidence-repair-contract-20260728-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_capture_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_evidence_diagnostic_probe_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_packager_20260728_v1.py",
)


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def safe_name(name: str) -> None:
    pure = PurePosixPath(name)
    require(bool(name) and not pure.is_absolute() and ".." not in pure.parts, "UNSAFE_PATH")


def pretty_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def write_file(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(data)
    os.chmod(path, mode)


def copy_public(source: Path, target: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "SOURCE_FILE_INVALID")
    write_file(target, source.read_bytes(), 0o600)


def parse_sums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PackageError("SUMS_INVALID") from exc
    for line in lines:
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SUMS_INVALID")
        digest, name = parts
        contract.validate_sha256(digest, "SUMS_DIGEST_INVALID")
        safe_name(name)
        require(name not in result, "SUMS_DUPLICATE")
        result[name] = digest
    return result


def deterministic_tar_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        directories: set[str] = set()
        for name in files:
            parts = PurePosixPath(name).parts[:-1]
            current: list[str] = []
            for part in parts:
                current.append(part)
                directories.add("/".join(current))
        for directory in sorted(directories):
            info = tarfile.TarInfo(directory + "/")
            info.type = tarfile.DIRTYPE
            info.mode = 0o700
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info)
        for name in sorted(files):
            safe_name(name)
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def validate_upstream_artifact(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "UPSTREAM_ARTIFACT_INVALID")
    require(contract.sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256,
            "UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "UPSTREAM_ARTIFACT_DUPLICATE_MEMBER")
        for name in names:
            safe_name(name)
        files = {name: archive.read(name) for name in names}
    require(SUMS_FILE in files, "UPSTREAM_SUMS_MISSING")
    sums = parse_sums(files[SUMS_FILE])
    for name, digest in sums.items():
        require(name in files and contract.sha256_bytes(files[name]) == digest,
                "UPSTREAM_MEMBER_DIGEST_MISMATCH")
    binding_name = "EXECUTION_CLOSURE_BINDING_REVIEW.json"
    require(binding_name in files, "UPSTREAM_REVIEW_BINDING_MISSING")
    binding = json.loads(files[binding_name])
    require(isinstance(binding, dict), "UPSTREAM_REVIEW_BINDING_INVALID")
    exact = {
        "source_sha": contract.BASE_HEAD_SHA,
        "base_pr": 194,
        "review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "execution_closure_sha256": contract.UPSTREAM_EXECUTION_CLOSURE_SHA256,
        "execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "future_physical_d2_request_id": contract.INVALIDATED_REQUEST_ID,
        "authorized": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "UPSTREAM_BINDING_" + key.upper() + "_MISMATCH")
    without = dict(binding)
    supplied = without.pop("review_binding_sha256", None)
    require(supplied == contract.canonical_json_sha256(without),
            "UPSTREAM_REVIEW_BINDING_DIGEST_MISMATCH")
    draft_name = "PHYSICAL_D2_REQUEST_DRAFT_04.json"
    require(draft_name in files, "UPSTREAM_REQUEST04_DRAFT_MISSING")
    draft = json.loads(files[draft_name])
    require(isinstance(draft, dict), "UPSTREAM_REQUEST04_DRAFT_INVALID")
    require(draft.get("d2_request_id") == contract.INVALIDATED_REQUEST_ID,
            "UPSTREAM_REQUEST04_ID_MISMATCH")
    require(draft.get("authorized") is False and draft.get("authorization_created") is False,
            "UPSTREAM_REQUEST04_NOT_DRAFT")
    return binding


def recursive_files(root: Path, excluded: set[str] | None = None) -> dict[str, bytes]:
    ignored = excluded or set()
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
    repository_root: Path,
    upstream_artifact_zip: Path,
    output_root: Path,
    source_sha: str,
    repository_head_sha: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    upstream_artifact_zip = upstream_artifact_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR195")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)
    validate_upstream_artifact(upstream_artifact_zip)

    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(upstream_artifact_zip, output_root / UPSTREAM_ARTIFACT_NAME)

    binding: dict[str, Any] = {
        "schema": contract.REVIEW_SCHEMA,
        "state": "BASELINE_MISMATCH_EVIDENCE_REPAIR_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": contract.STAGE,
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_branch": contract.BASE_BRANCH,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "predecessor_request_id": contract.PREDECESSOR_REQUEST_ID,
        "predecessor_state": "CONSUMED_FAILED",
        "predecessor_failure_code": "BASELINE_STATE_MISMATCH",
        "predecessor_authorization_record_sha256": contract.PREDECESSOR_AUTHORIZATION_RECORD_SHA256,
        "predecessor_terminal_result_sha256": contract.PREDECESSOR_TERMINAL_RESULT_SHA256,
        "invalidated_request_id": contract.INVALIDATED_REQUEST_ID,
        "invalidated_request_binding_sha256": contract.INVALIDATED_REQUEST_BINDING_SHA256,
        "invalidated_request_state": contract.INVALIDATED_REQUEST_STATE,
        "h4_authorization_id": contract.H4_AUTHORIZATION_ID,
        "h4_result_sha256": contract.H4_RESULT_SHA256,
        "baseline_evidence_policy_version": 2,
        "observed_baseline_required_on_mismatch": True,
        "future_diagnostic_authorization_id": contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,
        "future_physical_request_id": contract.FUTURE_PHYSICAL_REQUEST_ID,
        "future_physical_request_created": False,
        "next_gate": "EXACT_READONLY_BASELINE_DIAGNOSTIC_AUTHORIZATION",
        **contract.FALSE_BOUNDARY,
    }
    binding["review_binding_sha256"] = contract.canonical_json_sha256(binding)
    write_file(output_root / REVIEW_BINDING_FILE, pretty_bytes(binding))
    write_file(output_root / PREDECESSOR_DISPOSITION_FILE,
               pretty_bytes(contract.predecessor_disposition()))
    write_file(output_root / INVALIDATED_REQUEST_FILE,
               pretty_bytes(contract.invalidated_request_04_disposition()))
    write_file(
        output_root / DIAGNOSTIC_REQUEST_FILE,
        pretty_bytes(contract.build_diagnostic_request_draft(
            source_sha, binding["review_binding_sha256"]
        )),
    )
    write_file(output_root / "README.md", (
        "# Baseline-mismatch evidence repair review package\n\n"
        "This package records the actual consumed failure of physical request -03, "
        "invalidates request -04 before physical authorization, and defines only a future "
        "one-shot read-only baseline diagnostic. It contains no board or physical authorization.\n"
    ).encode("utf-8"))

    files_before_sums = recursive_files(output_root, {SUMS_FILE, REVIEW_ARCHIVE_NAME})
    sums = "".join(
        f"{contract.sha256_bytes(files_before_sums[name])}  {name}\n"
        for name in sorted(files_before_sums)
    ).encode("utf-8")
    write_file(output_root / SUMS_FILE, sums)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-baseline-mismatch-evidence-repair-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "repository_head_sha": repository_head_sha,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "archive_name": REVIEW_ARCHIVE_NAME,
        "archive_sha256": contract.sha256_bytes(archive),
        "review_binding_sha256": binding["review_binding_sha256"],
        "predecessor_terminal_result_sha256": contract.PREDECESSOR_TERMINAL_RESULT_SHA256,
        "invalidated_request_binding_sha256": contract.INVALIDATED_REQUEST_BINDING_SHA256,
        "future_diagnostic_authorization_id": contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,
        "future_physical_request_created": False,
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
            args.repository_root,
            args.upstream_artifact_zip,
            args.output_root,
            args.source_sha,
            args.repository_head_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
