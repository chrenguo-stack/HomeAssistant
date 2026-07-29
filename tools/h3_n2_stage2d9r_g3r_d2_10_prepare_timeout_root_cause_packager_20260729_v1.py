#!/usr/bin/env python3
"""Create a deterministic public review artifact for the D2-10 repair."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

import h3_n2_stage2d9r_g3r_d2_10_prepare_timeout_root_cause_contract_20260729_v1 as contract

REVIEW_FILE = "D2_10_PREPARE_TIMEOUT_ROOT_CAUSE_REVIEW.json"
REVIEW_TAR = "stage2d9r-g3r-d2-10-prepare-timeout-root-cause-repair-review-v1.tar"
SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_10_prepare_timeout_root_cause_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_10_prepare_timeout_root_cause_packager_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_10_prepare_transport_pacing_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_10_prepare_transport_pacing_repair_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-10-prepare-timeout-root-cause-successor-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-10-prepare-timeout-root-cause-successor-repair-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-10-prepare-timeout-root-cause-repair-ci-v1.yml",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def deterministic_tar(root: Path, target: Path) -> None:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path == target:
                continue
            relative = path.relative_to(root).as_posix()
            info = archive.gettarinfo(str(path), arcname=relative)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o700 if path.suffix == ".sh" else 0o600
            with path.open("rb") as handle:
                archive.addfile(info, handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    if contract.HEX40.fullmatch(args.source_sha) is None:
        raise RuntimeError("SOURCE_SHA_INVALID")
    decision = contract.validate(root)
    output = args.output_root.resolve(strict=False)
    if output.exists():
        raise RuntimeError("OUTPUT_ROOT_EXISTS")
    source = output / "source"
    for name in SOURCE_FILES:
        origin = root / name
        if not origin.is_file() or origin.is_symlink():
            raise RuntimeError("SOURCE_FILE_INVALID:" + name)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        target.chmod(0o700 if target.suffix == ".sh" else 0o600)
    file_digests = {
        name: sha256_file(source / name)
        for name in SOURCE_FILES
    }
    review = {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-10-prepare-timeout-"
            "root-cause-repair-review/1"
        ),
        "status": "SOURCE_REPAIR_READY_NO_PHYSICAL_AUTHORIZATION",
        "source_sha": args.source_sha,
        "base_head_sha": contract.EXPECTED_PARENT,
        "decision_binding_sha256": decision["decision_binding_sha256"],
        "root_cause_code": decision["root_cause_code"],
        "root_cause_confidence": decision["root_cause_confidence"],
        "source_files": file_digests,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }
    review["review_binding_sha256"] = canonical_sha256(review)
    output.mkdir(parents=True, exist_ok=True)
    review_path = output / REVIEW_FILE
    review_path.write_text(
        json.dumps(review, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    review_path.chmod(0o600)
    deterministic_tar(output, output / REVIEW_TAR)
    members = [
        path
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in members),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
