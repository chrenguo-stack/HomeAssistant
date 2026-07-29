#!/usr/bin/env python3
"""Build the deterministic public review and unauthorized request -10."""
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

import h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_contract_20260729_v1 as contract

REVIEW_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-"
    "execution-binding-review/1"
)
EXECUTION_DIR = "watchdog-repaired-payload-physical-d2-execution-package"
UPSTREAM_EXECUTION_DIR = (
    "prepare-panic-timeline-reset-signature-physical-d2-execution-package"
)
SOURCE_BINDING_FILE = "WATCHDOG_REPAIRED_PAYLOAD_EXECUTION_BINDING.json"
REVIEW_FILE = "WATCHDOG_REPAIRED_PAYLOAD_EXECUTION_BINDING_REVIEW.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_10.json"
PREDECESSOR_FILE = "D2_09_TERMINAL_DISPOSITION.json"
REVIEW_TAR = "stage2d9r-g3r-watchdog-repaired-payload-execution-binding-review-v1.tar"

SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_watchdog_repaired_payload_physical_d2_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_watchdog_repaired_payload_physical_d2_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_packager_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_watchdog_repaired_payload_execution_binding_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-watchdog-repaired-payload-execution-binding-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-watchdog-repaired-payload-execution-binding-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-watchdog-repaired-payload-execution-binding-review-ci-v1.yml",
)

UPSTREAM_REVIEW_FILE = (
    "PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_REPAIR_REVIEW.json"
)
WATCHDOG_REVIEW_FILE = "PREPARE_LOOPTASK_WATCHDOG_REPAIR_REVIEW.json"
UPSTREAM_EXCLUDED = frozenset(
    {
        contract.SUMS_FILE,
        contract.CLOSURE_MANIFEST_FILE,
        contract.PACKAGE_BINDING_FILE,
        contract.FINAL_BINDING_FILE,
        contract.RECOVERY_MANIFEST_FILE,
        contract.IMMUTABLE_TAR_FILE,
        contract.RECOVERY_TAR_FILE,
    }
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def copy_file(source: Path, target: Path, mode: int = 0o600) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("SOURCE_FILE_INVALID")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode)


def write_sums(root: Path) -> None:
    lines = [
        f"{contract.sha256_file(path)}  {path.name}"
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != contract.SUMS_FILE
    ]
    target = root / contract.SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)


def safe_extract_zip(archive: Path, output: Path) -> None:
    with zipfile.ZipFile(archive) as handle:
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or stat.S_ISLNK((info.external_attr >> 16) & 0o170000)
            ):
                raise RuntimeError("ARTIFACT_ZIP_MEMBER_UNSAFE")
        handle.extractall(output)


def verify_artifact_sums(root: Path) -> None:
    sums_path = root / contract.SUMS_FILE
    lines = sums_path.read_text(encoding="utf-8").splitlines()
    expected: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or contract.HEX64.fullmatch(parts[0]) is None:
            raise RuntimeError("ARTIFACT_SUMS_INVALID")
        name = parts[1]
        pure = PurePosixPath(name)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or not pure.parts
            or name in expected
            or name == contract.SUMS_FILE
        ):
            raise RuntimeError("ARTIFACT_SUMS_UNSAFE")
        expected[name] = parts[0]
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != sums_path
    }
    if not set(expected).issubset(observed):
        raise RuntimeError("ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        if contract.sha256_file(root / name) != digest:
            raise RuntimeError("ARTIFACT_MEMBER_DIGEST_MISMATCH")


def safe_extract_tar(archive: Path, output: Path) -> None:
    with tarfile.open(archive, "r:") as handle:
        for info in handle.getmembers():
            pure = PurePosixPath(info.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or not info.isfile()
            ):
                raise RuntimeError("ARTIFACT_TAR_MEMBER_UNSAFE")
        handle.extractall(output, filter="data")


def verify_review_binding(
    path: Path, *, expected_source: str, expected_binding: str
) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("UPSTREAM_REVIEW_INVALID")
    supplied = value.get("review_binding_sha256")
    without = dict(value)
    without.pop("review_binding_sha256", None)
    if supplied != expected_binding or contract.canonical_sha256(without) != supplied:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_MISMATCH")
    if value.get("source_sha") != expected_source:
        raise RuntimeError("UPSTREAM_REVIEW_SOURCE_MISMATCH")
    return value


def extract_pr203(archive: Path, root: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR203_ARTIFACT_SHA256:
        raise RuntimeError("PR203_ARTIFACT_DIGEST_MISMATCH")
    target = root / "pr203"
    safe_extract_zip(archive, target)
    verify_artifact_sums(target)
    verify_review_binding(
        target / UPSTREAM_REVIEW_FILE,
        expected_source=contract.PR203_HEAD,
        expected_binding=contract.PR203_REVIEW_BINDING_SHA256,
    )
    inner = root / "pr203-inner"
    safe_extract_tar(
        target
        / "stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-review-v1.tar",
        inner,
    )
    package = inner / UPSTREAM_EXECUTION_DIR
    if not package.is_dir() or package.is_symlink():
        raise RuntimeError("PR203_EXECUTION_PACKAGE_MISSING")
    upstream_binding = json.loads(
        (
            package
            / "PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_EXECUTION_PACKAGE_BINDING.json"
        ).read_text(encoding="utf-8")
    )
    if (
        upstream_binding.get("execution_package_sha256")
        != contract.PR203_EXECUTION_PACKAGE_SHA256
    ):
        raise RuntimeError("PR203_EXECUTION_PACKAGE_BINDING_MISMATCH")
    return package


def extract_pr204(archive: Path, root: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR204_ARTIFACT_SHA256:
        raise RuntimeError("PR204_ARTIFACT_DIGEST_MISMATCH")
    target = root / "pr204"
    safe_extract_zip(archive, target)
    verify_artifact_sums(target)
    review = verify_review_binding(
        target / WATCHDOG_REVIEW_FILE,
        expected_source=contract.BASE_HEAD_SHA,
        expected_binding=contract.PR204_REVIEW_BINDING_SHA256,
    )
    exact = {
        "new_application_sha256": contract.APPLICATION_SHA256,
        "new_immutable_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "new_recovery_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
        "new_final_execution_binding": contract.FINAL_EXECUTION_BINDING,
        "new_final_execution_binding_sha256": (
            contract.FINAL_EXECUTION_BINDING_SHA256
        ),
        "old_immutable_tar_sha256": (
            contract.OLD_IMMUTABLE_PAYLOAD_TAR_SHA256
        ),
        "old_recovery_tar_sha256": contract.OLD_RECOVERY_PAYLOAD_TAR_SHA256,
        "old_payloads_reused": False,
        "physical_request_created": False,
        "physical_authorization_created": False,
    }
    for key, expected in exact.items():
        if review.get(key) != expected:
            raise RuntimeError("PR204_REVIEW_" + key.upper() + "_MISMATCH")
    freeze = target / "repaired-freeze"
    expected_files = {
        contract.FINAL_BINDING_FILE: contract.FINAL_EXECUTION_BINDING_FILE_SHA256,
        contract.IMMUTABLE_MANIFEST_FILE: (
            contract.IMMUTABLE_FREEZE_MANIFEST_SHA256
        ),
        contract.RECOVERY_MANIFEST_FILE: (
            contract.RECOVERY_FREEZE_MANIFEST_SHA256
        ),
        contract.IMMUTABLE_TAR_FILE: contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        contract.RECOVERY_TAR_FILE: contract.RECOVERY_PAYLOAD_TAR_SHA256,
    }
    for name, expected in expected_files.items():
        path = freeze / name
        if contract.sha256_file(path) != expected:
            raise RuntimeError("PR204_FREEZE_MEMBER_DIGEST_MISMATCH")
    contract.validate_final_execution_binding(
        freeze / contract.FINAL_BINDING_FILE
    )
    return freeze


def deterministic_tar(root: Path, target: Path) -> None:
    members = [
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file() and path != target
    ]
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            relative = path.relative_to(root).as_posix()
            info = archive.gettarinfo(str(path), arcname=relative)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o700 if relative.endswith(".sh") else 0o600
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    target.chmod(0o600)


def build(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve(strict=True)
    upstream_artifact = args.upstream_artifact.resolve(strict=True)
    watchdog_artifact = args.watchdog_artifact.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise RuntimeError("OUTPUT_NOT_EMPTY")
    else:
        output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)

    with tempfile.TemporaryDirectory(prefix="watchdog-payload-binding-") as td:
        temp = Path(td)
        upstream_package = extract_pr203(upstream_artifact, temp)
        freeze = extract_pr204(watchdog_artifact, temp)
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)

        for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name not in UPSTREAM_EXCLUDED:
                copy_file(
                    path,
                    execution / path.name,
                    0o700 if path.suffix == ".sh" else 0o600,
                )
        copy_file(
            upstream_package / contract.SUMS_FILE,
            execution / "UPSTREAM_PR203_EXECUTION_SHA256SUMS",
        )
        for name in (
            contract.FINAL_BINDING_FILE,
            contract.IMMUTABLE_MANIFEST_FILE,
            contract.RECOVERY_MANIFEST_FILE,
            contract.IMMUTABLE_TAR_FILE,
            contract.RECOVERY_TAR_FILE,
        ):
            copy_file(freeze / name, execution / name)

        additions = {
            (
                "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                "execution_binding_contract_20260729_v1.py"
            ): source_root / SOURCE_FILES[0],
            (
                "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                "physical_d2_wrapper_20260729_v1.py"
            ): source_root / SOURCE_FILES[1],
            (
                "run_stage2d9r_g3r_watchdog_repaired_payload_"
                "physical_d2_20260729_v1.sh"
            ): source_root / SOURCE_FILES[2],
        }
        for name, source in additions.items():
            copy_file(
                source,
                execution / name,
                0o700 if name.endswith(".sh") or "wrapper" in name else 0o600,
            )

        source_binding = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-"
                "execution-binding/1"
            ),
            "state": "FROZEN_UNAUTHORIZED_NEW_PAYLOAD_EXECUTION_BINDING",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_10_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_sha_at_binding": contract.MAIN_SHA_AT_BINDING,
            "readme_blob_sha_at_binding": (
                contract.README_BLOB_SHA_AT_BINDING
            ),
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_role": "BLOCKING",
            "watchdog_repair_artifact_id": contract.PR204_ARTIFACT_ID,
            "watchdog_repair_artifact_sha256": (
                contract.PR204_ARTIFACT_SHA256
            ),
            "watchdog_repair_review_binding_sha256": (
                contract.PR204_REVIEW_BINDING_SHA256
            ),
            "immutable_build_binding": contract.IMMUTABLE_BUILD_BINDING,
            "application_sha256": contract.APPLICATION_SHA256,
            "immutable_payload_tar_sha256": (
                contract.IMMUTABLE_PAYLOAD_TAR_SHA256
            ),
            "recovery_payload_tar_sha256": (
                contract.RECOVERY_PAYLOAD_TAR_SHA256
            ),
            "final_execution_binding_sha256": (
                contract.FINAL_EXECUTION_BINDING_SHA256
            ),
            "old_payload_reuse_permitted": False,
            "upstream_execution_closure_reuse_permitted": False,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        write_json(execution / SOURCE_BINDING_FILE, source_binding)

        closure = contract.build_execution_closure_manifest(execution)
        write_json(execution / contract.CLOSURE_MANIFEST_FILE, closure)
        package_digest = contract.package_set_digest(execution)
        package_binding = {
            "schema": contract.PACKAGE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_WATCHDOG_REPAIRED_PAYLOAD_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_10_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_sha_at_package_build": (
                contract.MAIN_SHA_AT_BINDING
            ),
            "readme_blob_sha_at_package_build": (
                contract.README_BLOB_SHA_AT_BINDING
            ),
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 2,
            "execution_closure_sha256": closure["execution_closure_sha256"],
            "execution_package_sha256": package_digest,
            "execution_wrapper_sha256": contract.sha256_file(
                execution
                / (
                    "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                    "physical_d2_wrapper_20260729_v1.py"
                )
            ),
            "execution_launcher_sha256": contract.sha256_file(
                execution
                / (
                    "run_stage2d9r_g3r_watchdog_repaired_payload_"
                    "physical_d2_20260729_v1.sh"
                )
            ),
            "execution_contract_sha256": contract.sha256_file(
                execution
                / (
                    "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                    "execution_binding_contract_20260729_v1.py"
                )
            ),
            "upstream_pr203_artifact_id": contract.PR203_ARTIFACT_ID,
            "upstream_pr203_artifact_sha256": (
                contract.PR203_ARTIFACT_SHA256
            ),
            "upstream_pr203_review_binding_sha256": (
                contract.PR203_REVIEW_BINDING_SHA256
            ),
            "upstream_pr203_execution_package_sha256": (
                contract.PR203_EXECUTION_PACKAGE_SHA256
            ),
            "watchdog_repair_artifact_id": contract.PR204_ARTIFACT_ID,
            "watchdog_repair_artifact_sha256": (
                contract.PR204_ARTIFACT_SHA256
            ),
            "watchdog_repair_review_binding_sha256": (
                contract.PR204_REVIEW_BINDING_SHA256
            ),
            "immutable_build_binding": contract.IMMUTABLE_BUILD_BINDING,
            "application_sha256": contract.APPLICATION_SHA256,
            "immutable_payload_tar_sha256": (
                contract.IMMUTABLE_PAYLOAD_TAR_SHA256
            ),
            "recovery_payload_tar_sha256": (
                contract.RECOVERY_PAYLOAD_TAR_SHA256
            ),
            "final_execution_binding": contract.FINAL_EXECUTION_BINDING,
            "final_execution_binding_sha256": (
                contract.FINAL_EXECUTION_BINDING_SHA256
            ),
            "upstream_execution_closure_sha256": (
                contract.PR203_EXECUTION_CLOSURE_SHA256
            ),
            "upstream_execution_closure_reuse_permitted": False,
            "old_payload_reuse_permitted": False,
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

        request = contract.request_template(
            execution, source_sha=args.source_sha
        )
        write_json(output / REQUEST_FILE, request)
        write_json(
            output / PREDECESSOR_FILE,
            {
                "schema": (
                    "gh.h3.n2.stage2d9r-g3r-d2-terminal-disposition/1"
                ),
                "d2_request_id": contract.D2_09_ID,
                "status": contract.D2_09_STATUS,
                "terminal_state": contract.D2_09_TERMINAL_STATE,
                "failure_code": contract.D2_09_FAILURE_CODE,
                "authorization_record_sha256": (
                    contract.D2_09_AUTHORIZATION_SHA256
                ),
                "terminal_result_sha256": (
                    contract.D2_09_TERMINAL_RESULT_SHA256
                ),
                "realtime_serial_sha256": (
                    contract.D2_09_REALTIME_SERIAL_SHA256
                ),
                "reset_signatures_sha256": (
                    contract.D2_09_RESET_SIGNATURES_SHA256
                ),
                "realtime_timeline_sha256": (
                    contract.D2_09_REALTIME_TIMELINE_SHA256
                ),
                "prepare_count": 1,
                "verify_count": 0,
                "recovery_attempted": True,
                "recovery_succeeded": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
            },
        )
        for relative in SOURCE_FILES:
            copy_file(
                source_root / relative,
                output / relative,
                0o700 if relative.endswith(".sh") else 0o600,
            )

        review: dict[str, object] = {
            "schema": REVIEW_SCHEMA,
            "state": "WATCHDOG_REPAIRED_PAYLOAD_REQUEST_10_UNAUTHORIZED",
            "decision_id": contract.DECISION_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_sha_at_binding": contract.MAIN_SHA_AT_BINDING,
            "readme_blob_sha_at_binding": (
                contract.README_BLOB_SHA_AT_BINDING
            ),
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 2,
            "execution_closure_sha256": (
                package["closure"]["execution_closure_sha256"]
            ),
            "execution_package_sha256": package["package_sha256"],
            "d2_request_id": contract.REQUEST_10_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "predecessor_request_id": contract.D2_09_ID,
            "predecessor_status": contract.D2_09_STATUS,
            "predecessor_failure_code": contract.D2_09_FAILURE_CODE,
            "predecessor_terminal_result_sha256": (
                contract.D2_09_TERMINAL_RESULT_SHA256
            ),
            "watchdog_repair_artifact_id": contract.PR204_ARTIFACT_ID,
            "watchdog_repair_artifact_sha256": (
                contract.PR204_ARTIFACT_SHA256
            ),
            "watchdog_repair_review_binding_sha256": (
                contract.PR204_REVIEW_BINDING_SHA256
            ),
            "immutable_build_binding": contract.IMMUTABLE_BUILD_BINDING,
            "application_sha256": contract.APPLICATION_SHA256,
            "immutable_payload_tar_sha256": (
                contract.IMMUTABLE_PAYLOAD_TAR_SHA256
            ),
            "recovery_payload_tar_sha256": (
                contract.RECOVERY_PAYLOAD_TAR_SHA256
            ),
            "final_execution_binding_sha256": (
                contract.FINAL_EXECUTION_BINDING_SHA256
            ),
            "old_payload_reuse_permitted": False,
            "old_execution_closure_reuse_permitted": False,
            "physical_request_created": True,
            "physical_request_authorized": False,
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
            "ready": False,
            "merge": False,
            "release": False,
            "tag": False,
            "deployment": False,
        }
        review["review_binding_sha256"] = contract.canonical_sha256(review)
        write_json(output / REVIEW_FILE, review)
        deterministic_tar(output, output / REVIEW_TAR)
        write_sums(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--upstream-artifact", type=Path, required=True)
    parser.add_argument("--watchdog-artifact", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (
        contract.HEX40.fullmatch(args.source_sha) is None
        or args.source_sha == contract.BASE_HEAD_SHA
    ):
        raise SystemExit("SOURCE_SHA_INVALID")
    build(args)
    print(
        json.dumps(
            {
                "status": "PACKAGE_BUILT",
                "d2_request_id": contract.REQUEST_10_ID,
                "physical_request_authorized": False,
                "physical_authorization_created": False,
                "board_operation": False,
                "network_operation": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
