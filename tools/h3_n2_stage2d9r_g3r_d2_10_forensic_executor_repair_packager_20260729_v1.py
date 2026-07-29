#!/usr/bin/env python3
"""Build a deterministic, public, source-only D2-10 repair review."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

import h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_contract_20260729_v1 as contract

REVIEW_NAME = "D2_10_FORENSIC_EXECUTOR_REPAIR_REVIEW.json"
REVIEW_TAR = "stage2d9r-g3r-d2-10-forensic-executor-repair-review-v1.tar"
EXPECTED_SOURCE = (
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-10-forensic-executor-repair-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-10-forensic-terminal-closure-executor-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-10-forensic-terminal-closure-executor-repair-contract-20260729-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_executor_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_executor_repair_shell_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_d2_10_forensic_executor_repair_packager_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_executor_terminalization_repair_20260729_v1.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(path, 0o600)


def deterministic_tar(root: Path, target: Path) -> None:
    members = [
        path
        for path in root.rglob("*")
        if path.is_file() and path != target and path.name != "SHA256SUMS"
    ]
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(members, key=lambda value: value.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix()
            info = tarfile.TarInfo(relative)
            info.size = path.stat().st_size
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    os.chmod(target, 0o600)


def build(source_root: Path, source_sha: str, output: Path) -> dict[str, object]:
    contract.require(
        len(source_sha) == 40
        and all(character in "0123456789abcdef" for character in source_sha)
        and source_sha != contract.BASE_HEAD_SHA,
        "SOURCE_SHA_INVALID",
    )
    source_root = source_root.resolve(strict=True)
    output = output.resolve(strict=False)
    if output.exists():
        contract.require(
            output.is_dir() and not output.is_symlink() and not any(output.iterdir()),
            "OUTPUT_NOT_EMPTY",
        )
    else:
        output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    source_output = output / "source"
    source_output.mkdir(mode=0o700)
    files = []
    for name in EXPECTED_SOURCE:
        pure = PurePosixPath(name)
        contract.require(
            not pure.is_absolute() and ".." not in pure.parts, "SOURCE_PATH_INVALID"
        )
        source = source_root / name
        contract.require(
            source.is_file() and not source.is_symlink(), "SOURCE_FILE_MISSING"
        )
        target = source_output / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
        files.append({"name": name, "sha256": sha256_file(target)})
    review: dict[str, object] = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-10-forensic-executor-repair-review/1",
        "decision_id": contract.DECISION_ID,
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "source_sha": source_sha,
        "d2_request_id": contract.D2_REQUEST_ID,
        "d2_status": "CONSUMED_FAILED",
        "primary_failure_code": "PREPARE_RESULT_TIMEOUT",
        "secondary_failure_code": "KeyError",
        "flash_completed": True,
        "prepare_count": 1,
        "verify_count": 0,
        "locked_recovery_attempted": True,
        "locked_recovery_succeeded": None,
        "locked_recovery_outcome": "UNKNOWN",
        "load_bearing_artifact_physical_reuse_permitted": False,
        "stale_marker_sha256": contract.MARKER_FILE_SHA256,
        "forensic_source_transcript_sha256": (
            contract.SOURCE_FORENSIC_TRANSCRIPT_SHA256
        ),
        "executor_repair_source_only": True,
        "forensic_closure_tool_source_only": True,
        "forensic_closure_authorization_created": False,
        "forensic_closure_applied": False,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "source_files": files,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    review["review_binding_sha256"] = contract.canonical_sha256(review)
    write_json(output / REVIEW_NAME, review)
    deterministic_tar(output, output / REVIEW_TAR)
    sums = []
    for path in sorted(output.rglob("*"), key=lambda value: value.as_posix()):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    os.chmod(output / "SHA256SUMS", 0o600)
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review = build(args.source_root, args.source_sha, args.output)
    print(
        json.dumps(
            {
                "status": "PACKAGE_BUILT",
                "review_binding_sha256": review["review_binding_sha256"],
                "forensic_closure_authorization_created": False,
                "forensic_closure_applied": False,
                "physical_request_created": False,
                "board_operation": False,
                "network_operation": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
