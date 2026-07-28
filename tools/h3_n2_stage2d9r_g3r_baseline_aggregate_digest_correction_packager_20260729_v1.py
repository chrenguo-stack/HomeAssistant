#!/usr/bin/env python3
"""Deterministic public review packager for aggregate baseline digest correction."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import zipfile

import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_corrected_execution_closure_builder_20260729_v1 as closure_builder

REVIEW_FILE = "BASELINE_AGGREGATE_DIGEST_CORRECTION_REVIEW.json"
B2_DISPOSITION_FILE = "B2_CONSUMED_PASS_DISPOSITION.json"
INVALID_DIGEST_FILE = "INVALID_LEGACY_BASELINE_DIGEST_DISPOSITION.json"
CORRECTED_BASELINE_FILE = "CORRECTED_BASELINE_ACCEPTANCE_CANDIDATE.json"
MAC_POLICY_FILE = "CHIP_MAC_CANDIDATE_EVIDENCE_POLICY.json"
CLOSURE_FILE = "CORRECTED_BASELINE_EXECUTION_CLOSURE_DRAFT.json"
H5_REQUEST_FILE = "H5_CORRECTED_BASELINE_CLOSURE_REQUEST_DRAFT.json"
ARCHIVE_FILE = "stage2d9r-g3r-baseline-aggregate-digest-correction-review-v1.tar"
UPSTREAM_FILE = "stage2d9r-g3r-usb-identity-evidence-repair-review-v1.zip"

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-baseline-aggregate-digest-correction-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-baseline-aggregate-digest-correction-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-baseline-aggregate-digest-correction-contract-20260729-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_capture_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_corrected_execution_closure_builder_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_packager_20260729_v1.py",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def recursive_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


def verify_upstream_artifact(path: Path) -> dict:
    contract.require(path.is_file(), "UPSTREAM_ARTIFACT_MISSING")
    contract.require(contract.sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_SHA256_MISMATCH")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {
            "USB_IDENTITY_EVIDENCE_REPAIR_REVIEW.json",
            "SHA256SUMS",
            "stage2d9r-g3r-usb-identity-evidence-repair-review-v1.tar",
            ".github/workflows/h3-n2-stage2d9r-g3r-usb-identity-evidence-repair-review-ci-v1.yml",
        }
        contract.require(required <= names, "UPSTREAM_ARTIFACT_INVENTORY_MISMATCH")
        review = json.loads(archive.read("USB_IDENTITY_EVIDENCE_REPAIR_REVIEW.json"))
        contract.require(review["source_sha"] == contract.BASE_HEAD_SHA, "UPSTREAM_SOURCE_SHA_MISMATCH")
        contract.require(review["review_binding_sha256"] == contract.UPSTREAM_REVIEW_BINDING_SHA256, "UPSTREAM_REVIEW_BINDING_MISMATCH")
        inner_tar = archive.read("stage2d9r-g3r-usb-identity-evidence-repair-review-v1.tar")
        contract.require(contract.sha256_bytes(inner_tar) == contract.UPSTREAM_INNER_TAR_SHA256, "UPSTREAM_INNER_TAR_MISMATCH")
    return review


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


def build(repository_root: Path, upstream_artifact_zip: Path, output_root: Path,
          source_sha: str, repository_head_sha: str) -> dict:
    source_sha = contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    repository_head_sha = contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    contract.require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR197")
    verify_upstream_artifact(upstream_artifact_zip)
    contract.validate_b2_result(contract.expected_b2_result())

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

    shutil.copyfile(upstream_artifact_zip, output_root / UPSTREAM_FILE)
    os.chmod(output_root / UPSTREAM_FILE, 0o600)

    write_json(output_root / B2_DISPOSITION_FILE, contract.b2_disposition())
    write_json(output_root / INVALID_DIGEST_FILE, contract.invalid_legacy_digest_disposition())
    write_json(output_root / CORRECTED_BASELINE_FILE, contract.corrected_baseline_candidate())
    write_json(output_root / MAC_POLICY_FILE, contract.mac_candidate_policy())

    provisional_review = {
        "schema": contract.REVIEW_SCHEMA,
        "state": "BASELINE_AGGREGATE_DIGEST_CORRECTION_SOURCE_FROZEN_UNAUTHORIZED",
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
        "b2_authorization_id": contract.B2_AUTHORIZATION_ID,
        "b2_state": "CONSUMED_PASS",
        "b2_result_sha256": contract.B2_RESULT_SHA256,
        "invalid_legacy_baseline_sha256": contract.INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": contract.CORRECTED_LEGACY_BASELINE_SHA256,
        "corrected_path_neutral_baseline_sha256": contract.CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "mac_candidate_policy_version": 2,
        "future_h5_authorization_id": contract.H5_AUTHORIZATION_ID,
        "future_physical_request_id": contract.FUTURE_PHYSICAL_REQUEST_ID,
        "next_gate": "EXACT_HOST_ONLY_CORRECTED_BASELINE_CLOSURE_AUTHORIZATION",
        **contract.FALSE_BOUNDARY,
    }
    review_binding = contract.canonical_json_sha256(provisional_review)
    review = dict(provisional_review)
    review["review_binding_sha256"] = review_binding
    write_json(output_root / REVIEW_FILE, review)

    closure_bundle = closure_builder.build(source_sha, review_binding)
    write_json(output_root / CLOSURE_FILE, closure_bundle["corrected_execution_closure"])
    write_json(output_root / H5_REQUEST_FILE, closure_bundle["h5_request_draft"])

    archive_members = [name for name in recursive_files(output_root) if name not in {ARCHIVE_FILE, "SHA256SUMS"}]
    with tarfile.open(output_root / ARCHIVE_FILE, "w", format=tarfile.PAX_FORMAT) as archive:
        for relative in archive_members:
            add_tar_file(archive, output_root, relative)
    os.chmod(output_root / ARCHIVE_FILE, 0o600)

    checksum_lines = []
    for relative in recursive_files(output_root):
        if relative == "SHA256SUMS":
            continue
        checksum_lines.append(f"{contract.sha256_file(output_root / relative)}  {relative}")
    (output_root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    os.chmod(output_root / "SHA256SUMS", 0o600)

    return {
        "status": "PASS",
        "source_sha": source_sha,
        "review_binding_sha256": review_binding,
        "archive_sha256": contract.sha256_file(output_root / ARCHIVE_FILE),
        "corrected_legacy_baseline_sha256": contract.CORRECTED_LEGACY_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": contract.INVALID_LEGACY_BASELINE_SHA256,
        "b2_result_sha256": contract.B2_RESULT_SHA256,
        "h5_request_created": True,
        "h5_authorized": False,
        "physical_request_created": False,
        "physical_request_authorized": False,
        "authorized": False,
        "board_operation": False,
        "network_operation": False,
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
    result = build(args.repository_root.resolve(), args.upstream_artifact_zip.resolve(),
                   args.output_root.resolve(), args.source_sha, args.repository_head_sha)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
