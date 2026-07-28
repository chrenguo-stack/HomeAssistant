#!/usr/bin/env python3
"""Build deterministic public review package for USB identity evidence repair."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any
import zipfile

import h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_contract_20260728_v1 as contract

REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-usb-identity-evidence-repair-review-v1.tar"
UPSTREAM_ARTIFACT_NAME = "stage2d9r-g3r-baseline-mismatch-evidence-repair-review-v1.zip"
REVIEW_BINDING_FILE = "USB_IDENTITY_EVIDENCE_REPAIR_REVIEW.json"
B1_DISPOSITION_FILE = "B1_CONSUMED_FAILED_DISPOSITION.json"
OPERATOR_REPORT_FILE = "OPERATOR_USB_PORT_CHANGE_REPORT.json"
B2_REQUEST_FILE = "B2_USB_BASELINE_DIAGNOSTIC_REQUEST_DRAFT.json"
SUMS_FILE = "SHA256SUMS"

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-usb-identity-evidence-repair-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-usb-identity-evidence-repair-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-usb-identity-evidence-repair-contract-20260728-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_usb_identity_evidence_capture_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_usb_and_baseline_diagnostic_probe_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_packager_20260728_v1.py",
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
    write_file(target, source.read_bytes())


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
            current: list[str] = []
            for part in PurePosixPath(name).parts[:-1]:
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
    require(contract.sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "UPSTREAM_ARTIFACT_DUPLICATE_MEMBER")
        files = {}
        for name in names:
            safe_name(name)
            files[name] = archive.read(name)
    require(SUMS_FILE in files, "UPSTREAM_SUMS_MISSING")
    sums = parse_sums(files[SUMS_FILE])
    for name, digest in sums.items():
        require(name in files and contract.sha256_bytes(files[name]) == digest, "UPSTREAM_MEMBER_DIGEST_MISMATCH")
    binding_name = "BASELINE_MISMATCH_EVIDENCE_REPAIR_REVIEW.json"
    require(binding_name in files, "UPSTREAM_REVIEW_BINDING_MISSING")
    binding = json.loads(files[binding_name])
    exact = {
        "source_sha": contract.BASE_HEAD_SHA,
        "base_pr": 195,
        "review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
        "future_physical_request_created": False,
        "authorized": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "UPSTREAM_BINDING_" + key.upper() + "_MISMATCH")
    without = dict(binding)
    supplied = without.pop("review_binding_sha256", None)
    require(supplied == contract.canonical_json_sha256(without), "UPSTREAM_REVIEW_BINDING_DIGEST_MISMATCH")
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


def build(repository_root: Path, upstream_artifact_zip: Path, output_root: Path, source_sha: str, repository_head_sha: str) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    upstream_artifact_zip = upstream_artifact_zip.resolve(strict=True)
    contract.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    contract.validate_sha40(repository_head_sha, "REPOSITORY_HEAD_SHA_INVALID")
    require(source_sha != contract.BASE_HEAD_SHA, "SOURCE_NOT_LAYERED_FROM_PR196")
    require(not output_root.exists(), "OUTPUT_ALREADY_EXISTS")
    output_root.mkdir(parents=True, mode=0o700)
    os.chmod(output_root, 0o700)
    validate_upstream_artifact(upstream_artifact_zip)

    for relative in SOURCE_FILES:
        copy_public(repository_root / relative, output_root / relative)
    copy_public(upstream_artifact_zip, output_root / UPSTREAM_ARTIFACT_NAME)

    binding: dict[str, Any] = {
        "schema": contract.REVIEW_SCHEMA,
        "state": "USB_IDENTITY_EVIDENCE_REPAIR_SOURCE_FROZEN_UNAUTHORIZED",
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
        "b1_authorization_id": contract.B1_AUTHORIZATION_ID,
        "b1_state": "CONSUMED_FAILED",
        "b1_failure_code": contract.B1_FAILURE_CODE,
        "b1_authorization_record_sha256": contract.B1_AUTHORIZATION_RECORD_SHA256,
        "b1_result_sha256": contract.B1_RESULT_SHA256,
        "operator_report_id": contract.OPERATOR_REPORT_ID,
        "operator_reported_usb_port_changed": True,
        "operator_report_evidence_role": contract.OPERATOR_REPORT_EVIDENCE_ROLE,
        "transport_location_role": "AUDIT_ONLY",
        "stable_hardware_identity_status": "NOT_YET_ACCEPTED",
        "transport_evidence_policy_version": 2,
        "path_neutral_baseline_policy_version": 3,
        "future_b2_authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
        "future_physical_request_id": contract.FUTURE_PHYSICAL_REQUEST_ID,
        "future_physical_request_created": False,
        "next_gate": "EXACT_READONLY_USB_AND_BASELINE_DIAGNOSTIC_AUTHORIZATION",
        **contract.FALSE_BOUNDARY,
    }
    binding["review_binding_sha256"] = contract.canonical_json_sha256(binding)
    write_file(output_root / REVIEW_BINDING_FILE, pretty_bytes(binding))
    write_file(output_root / B1_DISPOSITION_FILE, pretty_bytes(contract.b1_disposition()))
    write_file(output_root / OPERATOR_REPORT_FILE, pretty_bytes(contract.operator_usb_port_change_report()))
    write_file(output_root / B2_REQUEST_FILE, pretty_bytes(contract.build_b2_request_draft(source_sha, binding["review_binding_sha256"])))
    write_file(output_root / "README.md", (
        "# USB identity evidence repair review package\n\n"
        "This package records the consumed B1 board-identity mismatch, the operator-reported USB-port change, "
        "and a future read-only B2 diagnostic draft. It contains no physical authorization and creates no -05 request.\n"
    ).encode("utf-8"))

    files_before_sums = recursive_files(output_root, {SUMS_FILE, REVIEW_ARCHIVE_NAME})
    sums = "".join(f"{contract.sha256_bytes(files_before_sums[name])}  {name}\n" for name in sorted(files_before_sums)).encode("utf-8")
    write_file(output_root / SUMS_FILE, sums)
    archive_files = dict(files_before_sums)
    archive_files[SUMS_FILE] = sums
    archive = deterministic_tar_bytes(archive_files)
    write_file(output_root / REVIEW_ARCHIVE_NAME, archive)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-usb-identity-evidence-repair-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "repository_head_sha": repository_head_sha,
        "archive_name": REVIEW_ARCHIVE_NAME,
        "archive_sha256": contract.sha256_bytes(archive),
        "review_binding_sha256": binding["review_binding_sha256"],
        "b1_result_sha256": contract.B1_RESULT_SHA256,
        "future_b2_authorization_id": contract.FUTURE_B2_AUTHORIZATION_ID,
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
        result = build(args.repository_root, args.upstream_artifact_zip, args.output_root, args.source_sha, args.repository_head_sha)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
