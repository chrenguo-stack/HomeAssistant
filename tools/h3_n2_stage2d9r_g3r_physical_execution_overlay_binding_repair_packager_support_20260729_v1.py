#!/usr/bin/env python3
"""Deterministic review and execution-package builder for request -06."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_contract_20260729_v1 as contract

REVIEW_FILE = "PHYSICAL_EXECUTION_OVERLAY_BINDING_REPAIR_REVIEW.json"
REQUEST_05_DISPOSITION_FILE = "INVALIDATED_PHYSICAL_D2_REQUEST_05.json"
REQUEST_06_FILE = contract.PHYSICAL_REQUEST_FILE
EXECUTION_PACKAGE_DIR = "corrected-baseline-physical-d2-execution-package"
ARCHIVE_FILE = "stage2d9r-g3r-physical-execution-overlay-binding-repair-review-v1.tar"
UPSTREAM_REFERENCE_FILE = "UPSTREAM_ARTIFACT_REFERENCE.json"

SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-physical-execution-overlay-binding-repair-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-physical-execution-overlay-binding-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-physical-execution-overlay-binding-repair-contract-20260729-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_physical_execution_overlay_shell_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_common_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_base_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_packager_support_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_packager_20260729_v1.py",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def recursive_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


def verify_root_sums(root: Path) -> None:
    contract.verify_sums(root)


def extract_zip_bytes(data: bytes, output: Path, expected_sha256: str, code: str) -> None:
    contract.require(contract.sha256_bytes(data) == expected_sha256, code + "_SHA256_MISMATCH")
    output.mkdir(parents=True, mode=0o700)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            name = info.filename
            contract.require(not name.startswith("/") and ".." not in Path(name).parts, code + "_PATH_INVALID")
            if info.is_dir():
                continue
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            os.chmod(target, 0o600)
    verify_root_sums(output)


def verify_upstream_artifact(path: Path, temp_root: Path) -> Path:
    contract.require(path.is_file(), "UPSTREAM_ARTIFACT_MISSING")
    contract.require(contract.sha256_file(path) == contract.UPSTREAM_ARTIFACT_SHA256, "UPSTREAM_ARTIFACT_SHA256_MISMATCH")
    pr198 = temp_root / "pr198"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {
            "BASELINE_AGGREGATE_DIGEST_CORRECTION_REVIEW.json",
            "SHA256SUMS",
            "stage2d9r-g3r-usb-identity-evidence-repair-review-v1.zip",
        }
        contract.require(required <= names, "UPSTREAM_ARTIFACT_INVENTORY_MISMATCH")
        for name in names:
            if name.endswith("/"):
                continue
            target = pr198 / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            os.chmod(target, 0o600)
    verify_root_sums(pr198)
    review = json.loads((pr198 / "BASELINE_AGGREGATE_DIGEST_CORRECTION_REVIEW.json").read_text())
    contract.require(review["source_sha"] == contract.BASE_HEAD_SHA, "UPSTREAM_SOURCE_SHA_MISMATCH")
    contract.require(review["review_binding_sha256"] == contract.UPSTREAM_REVIEW_BINDING_SHA256, "UPSTREAM_REVIEW_BINDING_MISMATCH")
    contract.require(contract.sha256_file(pr198 / "stage2d9r-g3r-baseline-aggregate-digest-correction-review-v1.tar") == contract.UPSTREAM_INNER_TAR_SHA256, "UPSTREAM_INNER_TAR_MISMATCH")

    pr197 = temp_root / "pr197"
    extract_zip_bytes(
        (pr198 / "stage2d9r-g3r-usb-identity-evidence-repair-review-v1.zip").read_bytes(),
        pr197,
        contract.NESTED_PR197_ZIP_SHA256,
        "NESTED_PR197",
    )
    pr196 = temp_root / "pr196"
    extract_zip_bytes(
        (pr197 / "stage2d9r-g3r-baseline-mismatch-evidence-repair-review-v1.zip").read_bytes(),
        pr196,
        contract.NESTED_PR196_ZIP_SHA256,
        "NESTED_PR196",
    )
    h4 = temp_root / "h4"
    extract_zip_bytes(
        (pr196 / "stage2d9r-g3r-execution-closure-binding-review-v1.zip").read_bytes(),
        h4,
        contract.NESTED_H4_ZIP_SHA256,
        "NESTED_H4",
    )
    package = h4 / "execution-closure-bound-final-physical-d2-execution-package"
    contract.require(package.is_dir(), "UPSTREAM_EXECUTION_PACKAGE_MISSING")
    verify_root_sums(package)
    contract.require(contract.canonical_package_digest(package) == contract.UPSTREAM_EXECUTION_PACKAGE_SHA256, "UPSTREAM_EXECUTION_PACKAGE_DIGEST_MISMATCH")
    return package


def write_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != contract.ROOT_SUMS_FILE:
            lines.append(f"{contract.sha256_file(path)}  {path.name}")
    (root / contract.ROOT_SUMS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(root / contract.ROOT_SUMS_FILE, 0o600)


