#!/usr/bin/env python3
"""Build the deterministic unauthorized D2-14 extraction-ownership review."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_contract_20260730_v1 as upstream_contract
import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1 as contract

EXECUTION_DIR = "d2-14-payload-extraction-ownership-repaired-physical-d2-execution-package"
UPSTREAM_EXECUTION_DIR = "d2-13-payload-handoff-repaired-physical-d2-execution-package"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_14.json"
REVIEW_FILE = "D2_14_PAYLOAD_EXTRACTION_OWNERSHIP_REPAIR_EXECUTION_BINDING_REVIEW.json"
FAILURE_FILE = "D2_13_PAYLOAD_EXTRACTION_OWNERSHIP_FAILURE_DISPOSITION.json"
SOURCE_BINDING_FILE = "D2_14_PAYLOAD_EXTRACTION_OWNERSHIP_REPAIR_EXECUTION_BINDING.json"
REVIEW_TAR_FILE = "stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-execution-binding-review-v1.tar"
PR212_REVIEW_FILE = "D2_13_PAYLOAD_HANDOFF_REPAIR_EXECUTION_BINDING_REVIEW.json"
SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_wrapper_20260730_v1.py",
    "tools/run_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_20260730_v1.sh",
)
PUBLIC_SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-20260730-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-contract-20260730-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_20260730_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_shell_20260730_v1.sh",
    *SOURCE_FILES,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def copy_file(source: Path, target: Path, mode: int = 0o600) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("SOURCE_FILE_INVALID")
    target.write_bytes(source.read_bytes())
    target.chmod(mode)


def write_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and not path.is_symlink() and path.name != contract.SUMS_FILE:
            lines.append(f"{contract.sha256_file(path)}  {path.name}")
    target = root / contract.SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)


def write_recursive_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and not path.is_symlink() and path != root / contract.SUMS_FILE:
            lines.append(f"{contract.sha256_file(path)}  {path.relative_to(root).as_posix()}")
    target = root / contract.SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)


def safe_extract_zip(source: Path, target: Path) -> None:
    target.mkdir(mode=0o700)
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if not info.filename or pure.is_absolute() or ".." in pure.parts or info.is_dir():
                raise RuntimeError("ARTIFACT_MEMBER_INVALID")
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode != stat.S_IFREG:
                raise RuntimeError("ARTIFACT_MEMBER_INVALID")
            destination = target.joinpath(*pure.parts)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(archive.read(info))
            destination.chmod(0o600)


def verify_recursive_sums(root: Path) -> None:
    sums = root / contract.SUMS_FILE
    if not sums.is_file() or sums.is_symlink():
        raise RuntimeError("ARTIFACT_SUMS_MISSING")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if name in expected:
            raise RuntimeError("ARTIFACT_SUMS_DUPLICATE")
        expected[name] = digest
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path != sums
    }
    if set(expected) != observed:
        raise RuntimeError("ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        if contract.sha256_file(root / name) != digest:
            raise RuntimeError("ARTIFACT_MEMBER_DIGEST_MISMATCH")


def extract_pr212(archive: Path, root: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR212_ARTIFACT_SHA256:
        raise RuntimeError("PR212_ARTIFACT_DIGEST_MISMATCH")
    outer = root / "pr212"
    safe_extract_zip(archive, outer)
    verify_recursive_sums(outer)
    review = json.loads((outer / PR212_REVIEW_FILE).read_text(encoding="utf-8"))
    supplied = review.get("review_binding_sha256")
    without = dict(review)
    without.pop("review_binding_sha256", None)
    if (
        supplied != contract.PR212_REVIEW_BINDING_SHA256
        or contract.canonical_sha256(without) != supplied
        or review.get("source_sha") != contract.BASE_HEAD_SHA
        or review.get("d2_request_id") != contract.D2_13_ID
        or review.get("request_binding_sha256") != contract.D2_13_REQUEST_BINDING_SHA256
        or review.get("execution_closure_sha256") != contract.D2_13_EXECUTION_CLOSURE_SHA256
        or review.get("execution_package_sha256") != contract.D2_13_EXECUTION_PACKAGE_SHA256
        or review.get("physical_request_authorized") is not False
        or review.get("physical_authorization_created") is not False
    ):
        raise RuntimeError("PR212_REVIEW_BINDING_MISMATCH")
    execution = outer / UPSTREAM_EXECUTION_DIR
    package = upstream_contract.validate_execution_package(execution)
    if package["package_sha256"] != contract.D2_13_EXECUTION_PACKAGE_SHA256:
        raise RuntimeError("PR212_EXECUTION_PACKAGE_MISMATCH")
    return execution


def deterministic_tar(root: Path, target: Path) -> None:
    members = [
        path for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file() and not path.is_symlink() and path != target and path != root / contract.SUMS_FILE
    ]
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            relative = path.relative_to(root).as_posix()
            info = archive.gettarinfo(str(path), arcname=relative)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o700 if relative.endswith(".sh") else 0o600
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    target.chmod(0o600)


def build(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if output.exists():
        if not output.is_dir() or output.is_symlink() or any(output.iterdir()):
            raise RuntimeError("OUTPUT_NOT_EMPTY")
    else:
        output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    contract.validate_decision(source_root / "docs/decisions" / contract.DECISION_FILE)

    with tempfile.TemporaryDirectory(prefix="d2-14-extraction-ownership-") as temporary:
        upstream_execution = extract_pr212(args.pr212_artifact.resolve(strict=True), Path(temporary))
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)
        excluded = {upstream_contract.CLOSURE_FILE, upstream_contract.PACKAGE_BINDING_FILE, upstream_contract.SUMS_FILE}
        for path in sorted(upstream_execution.iterdir(), key=lambda item: item.name):
            if path.name not in excluded and not path.name.startswith("run_") and path.is_file() and not path.is_symlink():
                copy_file(path, execution / path.name)
        copy_file(upstream_execution / upstream_contract.SUMS_FILE, execution / "UPSTREAM_D2_13_EXECUTION_SHA256SUMS")
        additions = {
            contract.CONTRACT_FILE: source_root / SOURCE_FILES[0],
            contract.WRAPPER_FILE: source_root / SOURCE_FILES[1],
            contract.LAUNCHER_FILE: source_root / SOURCE_FILES[2],
        }
        for name, source in additions.items():
            copy_file(source, execution / name, 0o600)

        source_binding = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-execution-binding/1",
            "state": "FROZEN_UNAUTHORIZED_D2_14_PAYLOAD_EXTRACTION_OWNERSHIP_REPAIR",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "pr212_artifact_id": contract.PR212_ARTIFACT_ID,
            "pr212_artifact_sha256": contract.PR212_ARTIFACT_SHA256,
            "pr212_review_binding_sha256": contract.PR212_REVIEW_BINDING_SHA256,
            "d2_13_terminal_state": contract.D2_13_TERMINAL_STATE,
            "d2_13_failure_code": contract.D2_13_FAILURE_CODE,
            "d2_13_authorization_claimed": False,
            "d2_13_authorization_consumed": True,
            "d2_13_board_operation": False,
            "d2_13_replay_permitted": False,
            "outer_payload_preextraction_prohibited": True,
            "inner_payload_extraction_single_owner": True,
            "payload_roots_empty_before_inner_start": True,
            "payload_tar_copy_inside_roots_prohibited": True,
            "real_shell_integration_required": True,
            "macos_path_normalization_required": True,
            "preclaim_failure_evidence_required": True,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        write_json(execution / SOURCE_BINDING_FILE, source_binding)

        closure = contract.build_execution_closure_manifest(execution)
        write_json(execution / contract.CLOSURE_FILE, closure)
        binding = {
            "schema": contract.PACKAGE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_D2_14_PAYLOAD_EXTRACTION_OWNERSHIP_REPAIRED_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_sha_at_package_build": contract.MAIN_SHA_AT_BINDING,
            "readme_blob_sha_at_package_build": contract.README_BLOB_SHA_AT_BINDING,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 6,
            "execution_closure_sha256": closure["execution_closure_sha256"],
            "execution_package_sha256": contract.package_set_digest(execution),
            "execution_wrapper_sha256": contract.sha256_file(execution / contract.WRAPPER_FILE),
            "execution_launcher_sha256": contract.sha256_file(execution / contract.LAUNCHER_FILE),
            "execution_contract_sha256": contract.sha256_file(execution / contract.CONTRACT_FILE),
            "pr212_artifact_id": contract.PR212_ARTIFACT_ID,
            "pr212_artifact_sha256": contract.PR212_ARTIFACT_SHA256,
            "pr212_review_binding_sha256": contract.PR212_REVIEW_BINDING_SHA256,
            "d2_13_request_binding_sha256": contract.D2_13_REQUEST_BINDING_SHA256,
            "d2_13_execution_closure_sha256": contract.D2_13_EXECUTION_CLOSURE_SHA256,
            "d2_13_execution_package_sha256": contract.D2_13_EXECUTION_PACKAGE_SHA256,
            "d2_13_terminal_state": contract.D2_13_TERMINAL_STATE,
            "d2_13_failure_code": contract.D2_13_FAILURE_CODE,
            "d2_13_terminal_result_sha256": contract.D2_13_TERMINAL_RESULT_SHA256,
            "d2_13_result_file_sha256": contract.D2_13_RESULT_FILE_SHA256,
            "d2_13_terminal_output_file_sha256": contract.D2_13_TERMINAL_OUTPUT_FILE_SHA256,
            "d2_13_request_reuse_permitted": False,
            "d2_13_authorization_reuse_permitted": False,
            "d2_13_execution_closure_reuse_permitted": False,
            "d2_13_execution_package_reuse_permitted": False,
            "outer_payload_preextraction_prohibited": True,
            "inner_payload_extraction_single_owner": True,
            "payload_roots_empty_before_inner_start": True,
            "payload_tar_copy_inside_roots_prohibited": True,
            "real_shell_integration_required": True,
            "macos_path_normalization_required": True,
            "preclaim_failure_evidence_required": True,
            "firmware_payload_bytes_unchanged": True,
            "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
            "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
            "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        write_json(execution / contract.PACKAGE_BINDING_FILE, binding)
        write_sums(execution)
        package = contract.validate_execution_package(execution)

        request = contract.request_template(execution, source_sha=args.source_sha)
        write_json(output / REQUEST_FILE, request)
        failure = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-extraction-ownership-failure-disposition/1",
            "d2_request_id": contract.D2_13_ID,
            "status": contract.D2_13_TERMINAL_STATE,
            "failure_code": contract.D2_13_FAILURE_CODE,
            "failure_stage": "PRECLAIM",
            "authorization_created": True,
            "authorization_claimed": False,
            "authorization_consumed": True,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
            "terminal_result_sha256": contract.D2_13_TERMINAL_RESULT_SHA256,
            "result_file_sha256": contract.D2_13_RESULT_FILE_SHA256,
            "terminal_output_file_sha256": contract.D2_13_TERMINAL_OUTPUT_FILE_SHA256,
            "root_cause": "PRIVATE_OUTER_PREEXTRACTED_PAYLOADS_BEFORE_INNER_SINGLE_OWNER_EXTRACTION",
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }
        write_json(output / FAILURE_FILE, failure)
        review: dict[str, object] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-execution-binding-review/1",
            "state": "REVIEWED_UNAUTHORIZED_D2_14_PAYLOAD_EXTRACTION_OWNERSHIP_REPAIR",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "pr212_artifact_id": contract.PR212_ARTIFACT_ID,
            "pr212_artifact_sha256": contract.PR212_ARTIFACT_SHA256,
            "pr212_review_binding_sha256": contract.PR212_REVIEW_BINDING_SHA256,
            "request_binding_sha256": request["request_binding_sha256"],
            "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
            "execution_package_sha256": package["package_sha256"],
            "d2_13_terminal_state": contract.D2_13_TERMINAL_STATE,
            "d2_13_failure_code": contract.D2_13_FAILURE_CODE,
            "d2_13_authorization_claimed": False,
            "d2_13_authorization_consumed": True,
            "d2_13_board_operation": False,
            "d2_13_replay_permitted": False,
            "outer_payload_preextraction_prohibited": True,
            "inner_payload_extraction_single_owner": True,
            "payload_roots_empty_before_inner_start": True,
            "payload_tar_copy_inside_roots_prohibited": True,
            "real_shell_integration_required": True,
            "macos_path_normalization_required": True,
            "preclaim_failure_evidence_required": True,
            "physical_request_created": True,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "source_files": list(PUBLIC_SOURCE_FILES),
        }
        review["review_binding_sha256"] = contract.canonical_sha256(review)
        write_json(output / REVIEW_FILE, review)

        source_copy = output / "source"
        for relative in PUBLIC_SOURCE_FILES:
            source = source_root / relative
            target = source_copy / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file(source, target, 0o700 if relative.endswith(".sh") else 0o600)
        deterministic_tar(output, output / REVIEW_TAR_FILE)
        write_recursive_sums(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pr212-artifact", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
