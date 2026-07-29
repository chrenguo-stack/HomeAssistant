#!/usr/bin/env python3
"""Build a deterministic public, source-only bytecode-repair review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import stat
import tarfile
from typing import Any

import h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1 as contract

REVIEW_FILE = "D2_11_PYTHON_BYTECODE_SELF_CONTAMINATION_REPAIR_REVIEW.json"
REVIEW_TAR = (
    "stage2d9r-g3r-d2-11-python-bytecode-self-contamination-"
    "repair-review-v1.tar"
)
SUMS_FILE = "SHA256SUMS"
SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-11-python-bytecode-self-contamination-repair-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-11-python-bytecode-self-contamination-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-11-python-bytecode-self-contamination-repair-contract-20260729-v1.md",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_shell_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_packager_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_20260729_v1.sh",
)
EXECUTABLE_FILES = frozenset(
    {
        "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_shell_20260729_v1.sh",
        "tools/run_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_20260729_v1.sh",
    }
)


def _write_json(path: Path, value: object, mode: int = 0o644) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    path.chmod(mode)


def _copy_sources(source_root: Path, output: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in SOURCE_FILES:
        source = source_root / name
        contract.require(
            source.is_file() and not source.is_symlink(),
            "SOURCE_FILE_INVALID",
        )
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        mode = 0o755 if name in EXECUTABLE_FILES else 0o644
        target.chmod(mode)
        entries.append(
            {
                "path": name,
                "mode": f"{mode:o}",
                "sha256": contract.sha256_file(target),
            }
        )
    return entries


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    if info.isdir():
        info.mode = 0o755
    elif info.name.endswith(".sh"):
        info.mode = 0o755
    else:
        info.mode = 0o644
    return info


def _build_tar(output: Path) -> None:
    members = [output / REVIEW_FILE, output / "source"]
    with tarfile.open(output / REVIEW_TAR, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in members:
            if path.is_dir():
                for member in sorted(path.rglob("*")):
                    tar.add(
                        member,
                        arcname=str(member.relative_to(output)),
                        recursive=False,
                        filter=_tar_filter,
                    )
            else:
                tar.add(
                    path,
                    arcname=path.name,
                    recursive=False,
                    filter=_tar_filter,
                )


def build(source_root: Path, output: Path, source_sha: str) -> dict[str, Any]:
    contract.require(
        contract.HEX40.fullmatch(source_sha) is not None
        and source_sha != contract.BASE_HEAD_SHA,
        "SOURCE_SHA_INVALID",
    )
    contract.require(
        source_root.is_dir() and not source_root.is_symlink(),
        "SOURCE_ROOT_INVALID",
    )
    if output.exists():
        contract.require(
            output.is_dir()
            and not output.is_symlink()
            and not any(output.iterdir()),
            "OUTPUT_NOT_EMPTY",
        )
    else:
        output.mkdir(parents=True)
    source_contract = contract.validate_review_source(source_root)
    entries = _copy_sources(source_root, output)
    review: dict[str, Any] = {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-11-python-bytecode-"
            "self-contamination-repair-review/1"
        ),
        "status": "SOURCE_ONLY_D2_12_REBIND_REQUIRED",
        "decision_id": contract.DECISION_ID,
        "source_sha": source_sha,
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "main_sha_at_repair": contract.MAIN_SHA_AT_REPAIR,
        "pr208_artifact_id": contract.PR208_ARTIFACT_ID,
        "pr208_artifact_sha256": contract.PR208_ARTIFACT_SHA256,
        "pr208_review_binding_sha256": contract.PR208_REVIEW_BINDING_SHA256,
        "root_cause": contract.ROOT_CAUSE,
        "failed_d2_request_id": contract.FAILED_D2_REQUEST_ID,
        "failed_private_package_state": "PRECLAIM_CONTRACT_FAILED",
        "failed_authorization_claimed": False,
        "failed_authorization_consumed": False,
        "failed_authorization_reuse_permitted": False,
        "failed_package_replay_permitted": False,
        "d2_12_request_created": False,
        "d2_12_authorization_created": False,
        "d2_12_execution_package_created": False,
        "physical_execute_enabled": False,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "execution_package_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "source_contract": source_contract,
        "files": entries,
    }
    review["review_binding_sha256"] = contract.canonical_sha256(review)
    _write_json(output / REVIEW_FILE, review)
    _build_tar(output)
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != SUMS_FILE:
            sums.append(
                f"{contract.sha256_file(path)}  {path.relative_to(output)}"
            )
    (output / SUMS_FILE).write_text("\n".join(sums) + "\n", encoding="utf-8")
    (output / SUMS_FILE).chmod(0o644)
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review = build(
        args.source_root.resolve(strict=True),
        args.output.resolve(strict=False),
        args.source_sha,
    )
    print(
        json.dumps(
            {
                "status": review["status"],
                "source_sha": review["source_sha"],
                "d2_12_request_created": False,
                "d2_12_authorization_created": False,
                "d2_12_execution_package_created": False,
                "board_operation": False,
                "network_operation": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
