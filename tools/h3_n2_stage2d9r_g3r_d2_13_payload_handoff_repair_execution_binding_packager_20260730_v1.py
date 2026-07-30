#!/usr/bin/env python3
"""Build the deterministic unauthorized D2-13 payload-handoff repair review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_execution_binding_contract_20260729_v1 as upstream_contract
import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_contract_20260730_v1 as contract

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-execution-binding-review/1"
EXECUTION_DIR = "d2-13-payload-handoff-repaired-physical-d2-execution-package"
UPSTREAM_EXECUTION_DIR = "d2-12-python-bytecode-repaired-physical-d2-execution-package"
SOURCE_BINDING_FILE = "D2_13_PAYLOAD_HANDOFF_REPAIR_EXECUTION_BINDING.json"
REVIEW_FILE = "D2_13_PAYLOAD_HANDOFF_REPAIR_EXECUTION_BINDING_REVIEW.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_13.json"
D2_12_DISPOSITION_FILE = "D2_12_PAYLOAD_HANDOFF_FAILURE_DISPOSITION.json"
REVIEW_TAR = "stage2d9r-g3r-d2-13-payload-handoff-repair-execution-binding-review-v1.tar"
PR210_REVIEW_FILE = "D2_12_PYTHON_BYTECODE_REPAIRED_EXECUTION_BINDING_REVIEW.json"

SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_contract_20260730_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_wrapper_20260730_v1.py",
    "tools/run_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_20260730_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_packager_20260730_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_20260730_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_shell_20260730_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-13-payload-handoff-repair-20260730-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-13-payload-handoff-repair-contract-20260730-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-13-payload-handoff-repair-ci-v1.yml",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def copy_file(source: Path, target: Path, mode: int = 0o600) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("SOURCE_FILE_INVALID")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode)


def write_sums(root: Path, *, recursive: bool = False) -> None:
    candidates = root.rglob("*") if recursive else root.iterdir()
    files = [
        path
        for path in sorted(candidates, key=lambda item: item.as_posix())
        if path.is_file() and not path.is_symlink() and path != root / contract.SUMS_FILE
    ]
    lines = [f"{contract.sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in files]
    target = root / contract.SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)


def safe_extract_zip(archive: Path, output: Path) -> None:
    with zipfile.ZipFile(archive) as handle:
        seen: set[str] = set()
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or info.filename in seen or stat.S_ISLNK(mode):
                raise RuntimeError("ARTIFACT_ZIP_MEMBER_UNSAFE")
            seen.add(info.filename)
        handle.extractall(output)


def verify_artifact_sums(root: Path) -> None:
    sums_path = root / contract.SUMS_FILE
    expected: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        pure = PurePosixPath(parts[1]) if len(parts) == 2 else PurePosixPath("/")
        if len(parts) != 2 or contract.HEX64.fullmatch(parts[0]) is None or pure.is_absolute() or ".." in pure.parts or not pure.parts or parts[1] in expected:
            raise RuntimeError("ARTIFACT_SUMS_INVALID")
        expected[parts[1]] = parts[0]
    observed = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path != sums_path}
    if set(expected) != observed:
        raise RuntimeError("ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or contract.sha256_file(path) != digest:
            raise RuntimeError("ARTIFACT_MEMBER_DIGEST_MISMATCH")


def extract_pr210(archive: Path, root: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR210_ARTIFACT_SHA256:
        raise RuntimeError("PR210_ARTIFACT_DIGEST_MISMATCH")
    outer = root / "pr210"
    safe_extract_zip(archive, outer)
    verify_artifact_sums(outer)
    review = json.loads((outer / PR210_REVIEW_FILE).read_text(encoding="utf-8"))
    supplied = review.get("review_binding_sha256")
    without = dict(review)
    without.pop("review_binding_sha256", None)
    if (
        supplied != contract.PR210_REVIEW_BINDING_SHA256
        or contract.canonical_sha256(without) != supplied
        or review.get("source_sha") != contract.BASE_HEAD_SHA
        or review.get("d2_request_id") != contract.D2_12_ID
        or review.get("request_binding_sha256") != contract.D2_12_REQUEST_BINDING_SHA256
        or review.get("execution_closure_sha256") != contract.D2_12_EXECUTION_CLOSURE_SHA256
        or review.get("execution_package_sha256") != contract.D2_12_EXECUTION_PACKAGE_SHA256
        or review.get("physical_request_authorized") is not False
        or review.get("physical_authorization_created") is not False
    ):
        raise RuntimeError("PR210_REVIEW_BINDING_MISMATCH")
    execution = outer / UPSTREAM_EXECUTION_DIR
    package = upstream_contract.validate_execution_package(execution)
    if package["package_sha256"] != contract.D2_12_EXECUTION_PACKAGE_SHA256:
        raise RuntimeError("PR210_EXECUTION_PACKAGE_MISMATCH")
    return execution


def deterministic_tar(root: Path, target: Path) -> None:
    members = [
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
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

    with tempfile.TemporaryDirectory(prefix="d2-13-payload-handoff-") as td:
        upstream_execution = extract_pr210(args.pr210_artifact.resolve(strict=True), Path(td))
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)
        excluded = {upstream_contract.CLOSURE_FILE, upstream_contract.PACKAGE_BINDING_FILE, upstream_contract.SUMS_FILE}
        for path in sorted(upstream_execution.iterdir(), key=lambda item: item.name):
            if path.name not in excluded and not path.name.startswith("run_") and path.is_file() and not path.is_symlink():
                copy_file(path, execution / path.name)
        copy_file(upstream_execution / upstream_contract.SUMS_FILE, execution / "UPSTREAM_D2_12_EXECUTION_SHA256SUMS")
        additions = {
            contract.CONTRACT_FILE: source_root / SOURCE_FILES[0],
            contract.WRAPPER_FILE: source_root / SOURCE_FILES[1],
            contract.LAUNCHER_FILE: source_root / SOURCE_FILES[2],
        }
        for name, source in additions.items():
            # The inherited physical executor verifies every package member as
            # mode 0600. The private outer runner must invoke the launcher via
            # /bin/sh rather than relying on an executable bit.
            copy_file(source, execution / name, 0o600)

        source_binding = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repair-execution-binding/1",
            "state": "FROZEN_UNAUTHORIZED_D2_13_PAYLOAD_HANDOFF_REPAIR",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "pr210_artifact_id": contract.PR210_ARTIFACT_ID,
            "pr210_artifact_sha256": contract.PR210_ARTIFACT_SHA256,
            "pr210_review_binding_sha256": contract.PR210_REVIEW_BINDING_SHA256,
            "d2_12_status": contract.D2_12_STATUS,
            "d2_12_failure_code": contract.D2_12_FAILURE_CODE,
            "d2_12_authorization_claimed": False,
            "d2_12_authorization_consumed": False,
            "d2_12_board_operation": False,
            "d2_12_replay_permitted": False,
            "shell_to_python_package_root_handoff_required": True,
            "payload_arguments_injected_before_upstream_parser": True,
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
        package_binding = {
            "schema": contract.PACKAGE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_D2_13_PAYLOAD_HANDOFF_REPAIRED_PACKAGE",
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
            "execution_closure_policy_version": 5,
            "execution_closure_sha256": closure["execution_closure_sha256"],
            "execution_package_sha256": contract.package_set_digest(execution),
            "execution_wrapper_sha256": contract.sha256_file(execution / contract.WRAPPER_FILE),
            "execution_launcher_sha256": contract.sha256_file(execution / contract.LAUNCHER_FILE),
            "execution_contract_sha256": contract.sha256_file(execution / contract.CONTRACT_FILE),
            "pr210_artifact_id": contract.PR210_ARTIFACT_ID,
            "pr210_artifact_sha256": contract.PR210_ARTIFACT_SHA256,
            "pr210_review_binding_sha256": contract.PR210_REVIEW_BINDING_SHA256,
            "d2_12_request_binding_sha256": contract.D2_12_REQUEST_BINDING_SHA256,
            "d2_12_execution_closure_sha256": contract.D2_12_EXECUTION_CLOSURE_SHA256,
            "d2_12_execution_package_sha256": contract.D2_12_EXECUTION_PACKAGE_SHA256,
            "d2_12_request_reuse_permitted": False,
            "d2_12_authorization_reuse_permitted": False,
            "d2_12_execution_closure_reuse_permitted": False,
            "d2_12_execution_package_reuse_permitted": False,
            "shell_to_python_package_root_handoff_required": True,
            "payload_arguments_injected_before_upstream_parser": True,
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
        write_json(execution / contract.PACKAGE_BINDING_FILE, package_binding)
        write_sums(execution)
        package = contract.validate_execution_package(execution)

        request = contract.request_template(execution, source_sha=args.source_sha)
        write_json(output / REQUEST_FILE, request)
        write_json(output / D2_12_DISPOSITION_FILE, {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-12-payload-handoff-failure-disposition/1",
            "d2_request_id": contract.D2_12_ID,
            "status": contract.D2_12_STATUS,
            "failure_code": contract.D2_12_FAILURE_CODE,
            "returncode": 2,
            "result_file_present": False,
            "authorization_marker_present": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "request_binding_sha256": contract.D2_12_REQUEST_BINDING_SHA256,
            "execution_closure_sha256": contract.D2_12_EXECUTION_CLOSURE_SHA256,
            "execution_package_sha256": contract.D2_12_EXECUTION_PACKAGE_SHA256,
            "request_reuse_permitted": False,
            "authorization_reuse_permitted": False,
            "execution_closure_reuse_permitted": False,
            "execution_package_reuse_permitted": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        })
        for relative in SOURCE_FILES:
            copy_file(source_root / relative, output / "source" / relative, 0o700 if relative.endswith(".sh") else 0o600)

        review: dict[str, object] = {
            "schema": REVIEW_SCHEMA,
            "state": "D2_13_PAYLOAD_HANDOFF_REPAIRED_REQUEST_UNAUTHORIZED",
            "decision_id": contract.DECISION_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_sha_at_binding": contract.MAIN_SHA_AT_BINDING,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "d2_request_id": contract.D2_REQUEST_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 5,
            "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
            "execution_package_sha256": package["package_sha256"],
            "predecessor_request_id": contract.D2_12_ID,
            "predecessor_status": contract.D2_12_STATUS,
            "predecessor_failure_code": contract.D2_12_FAILURE_CODE,
            "predecessor_authorization_claimed": False,
            "predecessor_authorization_consumed": False,
            "predecessor_board_operation": False,
            "predecessor_replay_permitted": False,
            "pr210_artifact_id": contract.PR210_ARTIFACT_ID,
            "pr210_artifact_sha256": contract.PR210_ARTIFACT_SHA256,
            "pr210_review_binding_sha256": contract.PR210_REVIEW_BINDING_SHA256,
            "shell_to_python_package_root_handoff_required": True,
            "payload_arguments_injected_before_upstream_parser": True,
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
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "recovery_executed": False,
            "ready": False,
            "merge": False,
            "release": False,
            "tag": False,
            "deployment": False,
            "source_files": {relative: contract.sha256_file(source_root / relative) for relative in SOURCE_FILES},
        }
        review["review_binding_sha256"] = contract.canonical_sha256(review)
        write_json(output / REVIEW_FILE, review)
        deterministic_tar(output, output / REVIEW_TAR)
        write_sums(output, recursive=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pr210-artifact", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if contract.HEX40.fullmatch(args.source_sha) is None or args.source_sha == contract.BASE_HEAD_SHA:
        raise SystemExit("SOURCE_SHA_INVALID")
    build(args)
    print(json.dumps({
        "status": "UNAUTHORIZED_D2_13_PAYLOAD_HANDOFF_REPAIR_REVIEW_BUILT",
        "d2_request_id": contract.D2_REQUEST_ID,
        "physical_request_created": True,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
