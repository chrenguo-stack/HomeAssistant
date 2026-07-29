#!/usr/bin/env python3
"""Build the deterministic D2-11 unauthorized execution-binding review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as contract

REVIEW_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "execution-binding-review/1"
)
EXECUTION_DIR = (
    "d2-11-prepare-transport-pacing-physical-d2-execution-package"
)
UPSTREAM_EXECUTION_DIR = (
    "watchdog-repaired-payload-physical-d2-execution-package"
)
SOURCE_BINDING_FILE = "D2_11_PREPARE_TRANSPORT_PACING_EXECUTION_BINDING.json"
REVIEW_FILE = "D2_11_PREPARE_TRANSPORT_PACING_EXECUTION_BINDING_REVIEW.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_11.json"
PREDECESSOR_FILE = "D2_10_TERMINAL_DISPOSITION.json"
REVIEW_TAR = (
    "stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "execution-binding-review-v1.tar"
)

PR205_REVIEW_FILE = "WATCHDOG_REPAIRED_PAYLOAD_EXECUTION_BINDING_REVIEW.json"
PR205_REVIEW_TAR = (
    "stage2d9r-g3r-watchdog-repaired-payload-execution-binding-review-v1.tar"
)
PR206_REVIEW_FILE = "D2_10_FORENSIC_EXECUTOR_REPAIR_REVIEW.json"
PR206_REVIEW_TAR = "stage2d9r-g3r-d2-10-forensic-executor-repair-review-v1.tar"
PR207_REVIEW_FILE = "D2_10_PREPARE_TIMEOUT_ROOT_CAUSE_REVIEW.json"
PR207_REVIEW_TAR = (
    "stage2d9r-g3r-d2-10-prepare-timeout-root-cause-repair-review-v1.tar"
)

SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_packager_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-11-prepare-transport-pacing-execution-binding-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-11-prepare-transport-pacing-execution-binding-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-11-prepare-transport-pacing-execution-binding-ci-v1.yml",
)

TERMINALIZATION_SOURCE = (
    "source/tools/"
    "h3_n2_stage2d9r_g3r_executor_terminalization_repair_20260729_v1.py"
)
PACING_SOURCE = (
    "source/tools/"
    "h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1.py"
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


def write_sums(root: Path, *, recursive: bool = False) -> None:
    candidates = root.rglob("*") if recursive else root.iterdir()
    files = [
        path
        for path in sorted(candidates, key=lambda item: item.as_posix())
        if path.is_file()
        and not path.is_symlink()
        and path != root / contract.SUMS_FILE
    ]
    lines = [
        f"{contract.sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    target = root / contract.SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)


def safe_extract_zip(archive: Path, output: Path) -> None:
    with zipfile.ZipFile(archive) as handle:
        seen: set[str] = set()
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise RuntimeError("ARTIFACT_ZIP_MEMBER_UNSAFE")
            seen.add(info.filename)
        handle.extractall(output)


def safe_extract_tar(archive: Path, output: Path) -> None:
    with tarfile.open(archive, "r:") as handle:
        seen: set[str] = set()
        for info in handle.getmembers():
            pure = PurePosixPath(info.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or info.name in seen
                or not info.isfile()
            ):
                raise RuntimeError("ARTIFACT_TAR_MEMBER_UNSAFE")
            seen.add(info.name)
        handle.extractall(output, filter="data")


def verify_artifact_sums(root: Path) -> None:
    path = root / contract.SUMS_FILE
    expected: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        if (
            len(parts) != 2
            or contract.HEX64.fullmatch(parts[0]) is None
            or parts[1] in expected
        ):
            raise RuntimeError("ARTIFACT_SUMS_INVALID")
        pure = PurePosixPath(parts[1])
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise RuntimeError("ARTIFACT_SUMS_UNSAFE")
        expected[parts[1]] = parts[0]
    observed = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != path
    }
    if not set(expected).issubset(observed):
        raise RuntimeError("ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        target = root / name
        if target.is_symlink() or contract.sha256_file(target) != digest:
            raise RuntimeError("ARTIFACT_MEMBER_DIGEST_MISMATCH")


def verify_review(
    path: Path,
    *,
    expected_source: str,
    expected_binding: str,
) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("UPSTREAM_REVIEW_INVALID")
    supplied = value.get("review_binding_sha256")
    without = dict(value)
    without.pop("review_binding_sha256", None)
    if (
        supplied != expected_binding
        or contract.canonical_sha256(without) != supplied
        or value.get("source_sha") != expected_source
    ):
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_MISMATCH")
    return value


def extract_pr205(archive: Path, root: Path) -> Path:
    if contract.sha256_file(archive) != contract.PR205_ARTIFACT_SHA256:
        raise RuntimeError("PR205_ARTIFACT_DIGEST_MISMATCH")
    outer = root / "pr205"
    safe_extract_zip(archive, outer)
    verify_artifact_sums(outer)
    review = verify_review(
        outer / PR205_REVIEW_FILE,
        expected_source="0ca39a8a284fca70fc69474aadb13ca85492b10d",
        expected_binding=contract.PR205_REVIEW_BINDING_SHA256,
    )
    if (
        review.get("execution_package_sha256")
        != contract.PR205_EXECUTION_PACKAGE_SHA256
        or review.get("execution_closure_sha256")
        != contract.PR205_EXECUTION_CLOSURE_SHA256
        or review.get("physical_request_authorized") is not False
        or review.get("physical_authorization_created") is not False
    ):
        raise RuntimeError("PR205_REVIEW_STATE_MISMATCH")
    inner = root / "pr205-inner"
    safe_extract_tar(outer / PR205_REVIEW_TAR, inner)
    package = inner / UPSTREAM_EXECUTION_DIR
    if not package.is_dir() or package.is_symlink():
        raise RuntimeError("PR205_EXECUTION_PACKAGE_MISSING")
    verify_flat_package(package)
    binding = json.loads(
        (package / contract.PACKAGE_BINDING_FILE).read_text(encoding="utf-8")
    )
    closure = json.loads(
        (package / contract.CLOSURE_FILE).read_text(encoding="utf-8")
    )
    if (
        binding.get("execution_package_sha256")
        != contract.PR205_EXECUTION_PACKAGE_SHA256
        or closure.get("execution_closure_sha256")
        != contract.PR205_EXECUTION_CLOSURE_SHA256
    ):
        raise RuntimeError("PR205_EXECUTION_BINDING_MISMATCH")
    return package


def verify_flat_package(root: Path) -> None:
    for path in root.iterdir():
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("UPSTREAM_PACKAGE_MEMBER_INVALID")
    expected: dict[str, str] = {}
    for line in (root / contract.SUMS_FILE).read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, name = line.split("  ", 1)
        if (
            contract.HEX64.fullmatch(digest) is None
            or "/" in name
            or name in expected
        ):
            raise RuntimeError("UPSTREAM_PACKAGE_SUMS_INVALID")
        expected[name] = digest
    observed = {
        path.name
        for path in root.iterdir()
        if path.name != contract.SUMS_FILE
    }
    if set(expected) != observed:
        raise RuntimeError("UPSTREAM_PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        if contract.sha256_file(root / name) != digest:
            raise RuntimeError("UPSTREAM_PACKAGE_DIGEST_MISMATCH")


def extract_source_artifact(
    archive: Path,
    root: Path,
    *,
    label: str,
    expected_archive: str,
    review_file: str,
    review_tar: str,
    expected_source: str,
    expected_binding: str,
    source_member: str,
    expected_member_sha256: str,
) -> Path:
    if contract.sha256_file(archive) != expected_archive:
        raise RuntimeError(label + "_ARTIFACT_DIGEST_MISMATCH")
    outer = root / label.lower()
    safe_extract_zip(archive, outer)
    verify_artifact_sums(outer)
    review = verify_review(
        outer / review_file,
        expected_source=expected_source,
        expected_binding=expected_binding,
    )
    if (
        review.get("physical_request_created") is not False
        or review.get("physical_authorization_created") is not False
    ):
        raise RuntimeError(label + "_REVIEW_STATE_MISMATCH")
    inner = root / (label.lower() + "-inner")
    safe_extract_tar(outer / review_tar, inner)
    source = inner / source_member
    if contract.sha256_file(source) != expected_member_sha256:
        raise RuntimeError(label + "_SOURCE_DIGEST_MISMATCH")
    return source


def deterministic_tar(root: Path, target: Path) -> None:
    members = [
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
        and not path.is_symlink()
        and path != target
        and path != root / contract.SUMS_FILE
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
    output = args.output.resolve(strict=False)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise RuntimeError("OUTPUT_NOT_EMPTY")
    else:
        output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)

    with tempfile.TemporaryDirectory(prefix="d2-11-paced-binding-") as td:
        temp = Path(td)
        upstream_package = extract_pr205(args.pr205_artifact.resolve(strict=True), temp)
        terminal_source = extract_source_artifact(
            args.pr206_artifact.resolve(strict=True),
            temp,
            label="PR206",
            expected_archive=contract.PR206_ARTIFACT_SHA256,
            review_file=PR206_REVIEW_FILE,
            review_tar=PR206_REVIEW_TAR,
            expected_source="ebaa3a95fe32e6715568836f9ca28b58bfdd2e31",
            expected_binding=contract.PR206_REVIEW_BINDING_SHA256,
            source_member=TERMINALIZATION_SOURCE,
            expected_member_sha256=contract.TERMINALIZATION_REPAIR_SHA256,
        )
        pacing_source = extract_source_artifact(
            args.pr207_artifact.resolve(strict=True),
            temp,
            label="PR207",
            expected_archive=contract.PR207_ARTIFACT_SHA256,
            review_file=PR207_REVIEW_FILE,
            review_tar=PR207_REVIEW_TAR,
            expected_source=contract.BASE_HEAD_SHA,
            expected_binding=contract.PR207_REVIEW_BINDING_SHA256,
            source_member=PACING_SOURCE,
            expected_member_sha256=contract.PACING_REPAIR_SHA256,
        )

        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)
        excluded = {
            contract.CLOSURE_FILE,
            contract.PACKAGE_BINDING_FILE,
            contract.SUMS_FILE,
        }
        for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
            if (
                path.name not in excluded
                and not path.name.startswith("run_")
                and path.is_file()
            ):
                copy_file(path, execution / path.name)
        copy_file(
            upstream_package / contract.SUMS_FILE,
            execution / "UPSTREAM_PR205_EXECUTION_SHA256SUMS",
        )
        additions = {
            contract.CONTRACT_FILE: source_root / SOURCE_FILES[0],
            contract.WRAPPER_FILE: source_root / SOURCE_FILES[1],
            contract.LAUNCHER_FILE: source_root / SOURCE_FILES[2],
            contract.TERMINALIZATION_FILE: terminal_source,
            contract.PACING_FILE: pacing_source,
        }
        for name, source in additions.items():
            copy_file(
                source,
                execution / name,
                0o700 if name.endswith(".sh") or name == contract.WRAPPER_FILE else 0o600,
            )

        source_binding = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-"
                "pacing-execution-binding/1"
            ),
            "state": "FROZEN_UNAUTHORIZED_D2_11_EXECUTION_BINDING",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
            "source_sha": args.source_sha,
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "pr205_artifact_id": contract.PR205_ARTIFACT_ID,
            "pr205_artifact_sha256": contract.PR205_ARTIFACT_SHA256,
            "pr205_execution_package_reuse_permitted": False,
            "pr205_execution_closure_reuse_permitted": False,
            "pr206_artifact_id": contract.PR206_ARTIFACT_ID,
            "pr206_artifact_sha256": contract.PR206_ARTIFACT_SHA256,
            "terminalization_repair_sha256": (
                contract.TERMINALIZATION_REPAIR_SHA256
            ),
            "pr207_artifact_id": contract.PR207_ARTIFACT_ID,
            "pr207_artifact_sha256": contract.PR207_ARTIFACT_SHA256,
            "pacing_repair_sha256": contract.PACING_REPAIR_SHA256,
            "paced_chunk_bytes": contract.PACED_CHUNK_BYTES,
            "inter_chunk_delay_ms": contract.INTER_CHUNK_DELAY_MS,
            "d2_10_terminal_result_sha256": contract.D2_10_TERMINAL_RESULT_SHA256,
            "d2_10_terminal_marker_sha256": contract.D2_10_TERMINAL_MARKER_SHA256,
            "d2_10_request_reuse_permitted": False,
            "d2_10_authorization_reuse_permitted": False,
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
            "state": "FROZEN_UNAUTHORIZED_D2_11_PACED_TRANSPORT_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.D2_REQUEST_ID,
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
            "execution_closure_policy_version": 3,
            "execution_closure_sha256": closure["execution_closure_sha256"],
            "execution_package_sha256": contract.package_set_digest(execution),
            "execution_wrapper_sha256": contract.sha256_file(
                execution / contract.WRAPPER_FILE
            ),
            "execution_launcher_sha256": contract.sha256_file(
                execution / contract.LAUNCHER_FILE
            ),
            "execution_contract_sha256": contract.sha256_file(
                execution / contract.CONTRACT_FILE
            ),
            "pr205_artifact_id": contract.PR205_ARTIFACT_ID,
            "pr205_artifact_sha256": contract.PR205_ARTIFACT_SHA256,
            "pr205_execution_package_reuse_permitted": False,
            "pr205_execution_closure_reuse_permitted": False,
            "pr206_artifact_id": contract.PR206_ARTIFACT_ID,
            "pr206_artifact_sha256": contract.PR206_ARTIFACT_SHA256,
            "terminalization_repair_sha256": (
                contract.TERMINALIZATION_REPAIR_SHA256
            ),
            "pr207_artifact_id": contract.PR207_ARTIFACT_ID,
            "pr207_artifact_sha256": contract.PR207_ARTIFACT_SHA256,
            "pacing_repair_sha256": contract.PACING_REPAIR_SHA256,
            "paced_chunk_bytes": contract.PACED_CHUNK_BYTES,
            "inter_chunk_delay_ms": contract.INTER_CHUNK_DELAY_MS,
            "firmware_payload_bytes_unchanged": True,
            "immutable_payload_tar_sha256": (
                contract.IMMUTABLE_PAYLOAD_TAR_SHA256
            ),
            "recovery_payload_tar_sha256": (
                contract.RECOVERY_PAYLOAD_TAR_SHA256
            ),
            "final_execution_binding_sha256": (
                contract.FINAL_EXECUTION_BINDING_SHA256
            ),
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
        write_json(
            output / PREDECESSOR_FILE,
            {
                "schema": (
                    "gh.h3.n2.stage2d9r-g3r-d2-terminal-disposition/1"
                ),
                "d2_request_id": contract.D2_10_ID,
                "status": "CONSUMED_FAILED",
                "terminalization_state": "FORENSIC_TERMINAL_CLOSED",
                "primary_failure_code": "PREPARE_RESULT_TIMEOUT",
                "secondary_failure_code": "KeyError",
                "flash_completed": True,
                "prepare_count": 1,
                "verify_count": 0,
                "locked_recovery_attempted": True,
                "locked_recovery_outcome": "UNKNOWN",
                "locked_recovery_succeeded": None,
                "terminal_result_sha256": (
                    contract.D2_10_TERMINAL_RESULT_SHA256
                ),
                "terminal_marker_sha256": (
                    contract.D2_10_TERMINAL_MARKER_SHA256
                ),
                "terminal_result_file_sha256": (
                    contract.D2_10_TERMINAL_RESULT_FILE_SHA256
                ),
                "terminal_marker_file_sha256": (
                    contract.D2_10_TERMINAL_MARKER_FILE_SHA256
                ),
                "request_binding_sha256": (
                    contract.D2_10_REQUEST_BINDING_SHA256
                ),
                "authorization_record_sha256": (
                    contract.D2_10_AUTHORIZATION_RECORD_SHA256
                ),
                "authorization_file_sha256": (
                    contract.D2_10_AUTHORIZATION_FILE_SHA256
                ),
                "replay_permitted": False,
                "automatic_retry_permitted": False,
            },
        )
        for relative in SOURCE_FILES:
            copy_file(
                source_root / relative,
                output / "source" / relative,
                0o700 if relative.endswith(".sh") else 0o600,
            )

        review: dict[str, object] = {
            "schema": REVIEW_SCHEMA,
            "state": "D2_11_PACED_TRANSPORT_REQUEST_UNAUTHORIZED",
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
            "execution_closure_policy_version": 3,
            "execution_closure_sha256": (
                package["closure"]["execution_closure_sha256"]
            ),
            "execution_package_sha256": package["package_sha256"],
            "predecessor_request_id": contract.D2_10_ID,
            "predecessor_status": "CONSUMED_FAILED",
            "predecessor_terminalization_state": "FORENSIC_TERMINAL_CLOSED",
            "predecessor_locked_recovery_outcome": "UNKNOWN",
            "predecessor_terminal_result_sha256": (
                contract.D2_10_TERMINAL_RESULT_SHA256
            ),
            "predecessor_terminal_marker_sha256": (
                contract.D2_10_TERMINAL_MARKER_SHA256
            ),
            "predecessor_replay_permitted": False,
            "pr205_execution_package_reuse_permitted": False,
            "pr205_execution_closure_reuse_permitted": False,
            "terminalization_repair_sha256": (
                contract.TERMINALIZATION_REPAIR_SHA256
            ),
            "pacing_repair_sha256": contract.PACING_REPAIR_SHA256,
            "paced_chunk_bytes": contract.PACED_CHUNK_BYTES,
            "inter_chunk_delay_ms": contract.INTER_CHUNK_DELAY_MS,
            "short_write_evidence_persisted": True,
            "result_timeout_extension_used": False,
            "command_retry_added": False,
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
            "source_files": {
                relative: contract.sha256_file(source_root / relative)
                for relative in SOURCE_FILES
            },
        }
        review["review_binding_sha256"] = contract.canonical_sha256(review)
        write_json(output / REVIEW_FILE, review)
        deterministic_tar(output, output / REVIEW_TAR)
        write_sums(output, recursive=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pr205-artifact", type=Path, required=True)
    parser.add_argument("--pr206-artifact", type=Path, required=True)
    parser.add_argument("--pr207-artifact", type=Path, required=True)
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
                "status": "UNAUTHORIZED_D2_11_BINDING_REVIEW_BUILT",
                "d2_request_id": contract.D2_REQUEST_ID,
                "physical_request_created": True,
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
