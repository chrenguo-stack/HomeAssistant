#!/usr/bin/env python3
"""Deterministic source-only review package builder."""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_contract_20260729_v1 as contract

SOURCE_FILES = [
    ".github/workflows/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-repair-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-repair-contract-20260729-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_shell_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_packager_20260729_v1.py",
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contract.canonical_json_bytes(value) + b"\n")
    os.chmod(path, 0o600)


def add_tar_file(archive: tarfile.TarFile, root: Path, relative: str) -> None:
    data = (root / relative).read_bytes()
    info = tarfile.TarInfo(relative)
    info.size = len(data)
    info.mode = 0o600
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def recursive_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def verify_upstream(zip_path: Path) -> None:
    contract.require(zip_path.is_file(), "UPSTREAM_ARTIFACT_MISSING")
    contract.require(contract.sha256_file(zip_path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_SHA256_MISMATCH")
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        contract.require("PHYSICAL_EXECUTION_OVERLAY_BINDING_REPAIR_REVIEW.json" in names, "UPSTREAM_REVIEW_MISSING")
        review = json.loads(archive.read("PHYSICAL_EXECUTION_OVERLAY_BINDING_REPAIR_REVIEW.json"))
        contract.require(review.get("source_sha") == contract.BASE_HEAD_SHA, "UPSTREAM_SOURCE_SHA_MISMATCH")
        contract.require(review.get("review_binding_sha256") == contract.UPSTREAM_REVIEW_BINDING_SHA256, "UPSTREAM_REVIEW_BINDING_MISMATCH")
        contract.require("PHYSICAL_D2_REQUEST_06.json" in names, "UPSTREAM_REQUEST_06_MISSING")
        contract.require(not any("authorization" in name.lower() and "06" in name for name in names), "UPSTREAM_PHYSICAL_AUTHORIZATION_PRESENT")


def build(repository_root: Path, upstream_artifact_zip: Path, output_root: Path,
          source_sha: str, repository_head_sha: str) -> dict[str, Any]:
    source_sha = contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    repository_head_sha = contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    contract.require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR199")
    verify_upstream(upstream_artifact_zip)
    if output_root.exists():
        contract.require(not any(output_root.iterdir()), "OUTPUT_ROOT_MUST_BE_EMPTY")
    else:
        output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)

    for relative in SOURCE_FILES:
        source = repository_root / relative
        contract.require(source.is_file(), "SOURCE_FILE_MISSING")
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)

    shutil.copyfile(upstream_artifact_zip, output_root / contract.UPSTREAM_ZIP_FILE)
    os.chmod(output_root / contract.UPSTREAM_ZIP_FILE, 0o600)
    write_json(output_root / contract.DISPOSITION_FILE, contract.d2_terminal_disposition())
    write_json(output_root / contract.POLICY_FILE, contract.evidence_policy())

    provisional = {
        "schema": contract.REVIEW_SCHEMA,
        "state": contract.STATE,
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
        "d2_06_terminal_result_sha256": contract.D2_TERMINAL_RESULT_SHA256,
        "d2_06_status": contract.D2_STATUS,
        "d2_06_terminal_state": contract.D2_TERMINAL_STATE,
        "d2_06_failure_code": contract.D2_FAILURE_CODE,
        "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
        "immutable_payload_changed": False,
        "recovery_payload_changed": False,
        "new_physical_request_created": False,
        **contract.FALSE_BOUNDARY,
    }
    review = dict(provisional)
    review["review_binding_sha256"] = contract.canonical_json_sha256(provisional)
    write_json(output_root / contract.REVIEW_FILE, review)

    members = [name for name in recursive_files(output_root) if name not in {contract.ARCHIVE_FILE, contract.ROOT_SUMS_FILE}]
    with tarfile.open(output_root / contract.ARCHIVE_FILE, "w", format=tarfile.PAX_FORMAT) as archive:
        for relative in members:
            add_tar_file(archive, output_root, relative)
    os.chmod(output_root / contract.ARCHIVE_FILE, 0o600)

    sums = []
    for relative in recursive_files(output_root):
        if relative == contract.ROOT_SUMS_FILE:
            continue
        sums.append(f"{contract.sha256_file(output_root / relative)}  {relative}")
    (output_root / contract.ROOT_SUMS_FILE).write_text("\n".join(sums) + "\n", encoding="utf-8")
    os.chmod(output_root / contract.ROOT_SUMS_FILE, 0o600)

    return {
        "status": "PASS",
        "source_sha": source_sha,
        "review_binding_sha256": review["review_binding_sha256"],
        "archive_sha256": contract.sha256_file(output_root / contract.ARCHIVE_FILE),
        "d2_06_status": contract.D2_STATUS,
        "d2_06_failure_code": contract.D2_FAILURE_CODE,
        "new_physical_request_created": False,
        "physical_authorization_created": False,
        "file_count": len(recursive_files(output_root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--upstream-artifact-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repository-head-sha", required=True)
    args = parser.parse_args()
    result = build(
        args.repository_root.resolve(),
        args.upstream_artifact_zip.resolve(),
        args.output_root.resolve(),
        args.source_sha,
        args.repository_head_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
