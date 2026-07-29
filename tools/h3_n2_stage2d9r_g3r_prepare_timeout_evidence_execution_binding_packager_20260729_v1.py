#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_support_20260729_v1 as support

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-execution-binding-review/1"
EXECUTION_DIR = "prepare-timeout-evidence-physical-d2-execution-package"
SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_support_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-execution-binding-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-execution-binding-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-prepare-timeout-evidence-execution-binding-review-ci-v1.yml",
)


def module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_set_digest(root: Path, names: list[str]) -> str:
    entries = [{"name": name, "sha256": support.sha256_file(root / name)} for name in sorted(names)]
    return support.canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-execution-package-set/1",
        "files": entries,
    })


def extract_upstream(archive: Path, root: Path) -> tuple[Path, Path]:
    if support.sha256_file(archive) != contract.PR200_ARTIFACT_SHA256:
        raise RuntimeError("UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(archive) as outer:
        outer.extractall(root / "pr200")
    pr200 = root / "pr200"
    review = json.loads((pr200 / "PREPARE_TIMEOUT_EVIDENCE_REPAIR_REVIEW.json").read_text(encoding="utf-8"))
    observed = dict(review)
    binding = observed.pop("review_binding_sha256", None)
    if binding != contract.PR200_REVIEW_BINDING_SHA256 or support.canonical_sha256(observed) != binding:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_MISMATCH")
    if review.get("source_sha") != contract.PR200_HEAD:
        raise RuntimeError("UPSTREAM_SOURCE_SHA_MISMATCH")
    embedded = pr200 / "UPSTREAM_PR199_REVIEW_ARTIFACT.zip"
    if support.sha256_file(embedded) != contract.PR199_ARTIFACT_SHA256:
        raise RuntimeError("EMBEDDED_PR199_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(embedded) as nested:
        nested.extractall(root / "pr199")
    package = root / "pr199" / "corrected-baseline-physical-d2-execution-package"
    if not package.is_dir():
        raise RuntimeError("UPSTREAM_EXECUTION_PACKAGE_MISSING")
    return pr200, package


def build(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve(strict=True)
    upstream = args.upstream_artifact.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if output.exists():
        if any(output.iterdir()):
            raise RuntimeError("OUTPUT_NOT_EMPTY")
    else:
        output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)

    with tempfile.TemporaryDirectory(prefix="prepare-evidence-binding-") as td:
        temp = Path(td)
        pr200, upstream_package = extract_upstream(upstream, temp)
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)
        for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name != "SHA256SUMS":
                support.copy_file(path, execution / path.name)

        additions = {
            "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1.py": source_root / SOURCE_FILES[0],
            "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1.py": source_root / SOURCE_FILES[1],
            "run_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_20260729_v1.sh": source_root / SOURCE_FILES[2],
            "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py": pr200 / "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py",
            "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py": pr200 / "tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py",
        }
        for name, source in additions.items():
            support.copy_file(source, execution / name, 0o700 if name.endswith(".sh") or "wrapper" in name else 0o600)

        evidence_binding = {
            "schema": contract.EVIDENCE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_EVIDENCE_EXECUTION_BINDING",
            "policy_version": contract.EVIDENCE_POLICY_VERSION,
            "classifications": list(contract.CLASSIFICATIONS),
            "late_result_observation_window_seconds": contract.LATE_RESULT_OBSERVATION_WINDOW_SECONDS,
            "persist_before_recovery": True,
            "persist_before_temporary_cleanup": True,
            "serial_transcript_format": "redacted-jsonl",
            "broker_transcript_format": "redacted-jsonl",
            "timeline_format": "canonical-json",
            "unknown_line_policy": "HASH_ONLY",
            "terminal_evidence_root_mode": "0700",
            "terminal_evidence_file_mode": "0600",
            "raw_command_material_retained": False,
            "raw_private_values_retained": False,
            "physical_authorization_created": False,
            "physical_execution_started": False,
        }
        support.write_json(execution / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_BINDING.json", evidence_binding)

        digest_names = sorted(
            path.name for path in execution.iterdir()
            if path.is_file() and path.name != "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_PACKAGE_BINDING.json"
        )
        package_digest = package_set_digest(execution, digest_names)
        package_binding = {
            "schema": contract.PACKAGE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_PREPARE_TIMEOUT_EVIDENCE_EXECUTION_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_07_ID,
            "source_sha": args.source_sha,
            "base_pr": 200,
            "base_head_sha": contract.PR200_HEAD,
            "upstream_artifact_id": contract.PR200_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR200_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR200_REVIEW_BINDING_SHA256,
            "execution_package_sha256": package_digest,
            "execution_wrapper_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1.py"),
            "execution_launcher_sha256": support.sha256_file(execution / "run_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_20260729_v1.sh"),
            "evidence_recorder_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py"),
            "evidence_overlay_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py"),
            "evidence_contract_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1.py"),
            "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
            "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        support.write_json(execution / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_PACKAGE_BINDING.json", package_binding)
        support.write_sums(execution)
        contract.validate_execution_package(execution)

        request = contract.request_template(execution, source_sha=args.source_sha)
        support.write_json(output / "PHYSICAL_D2_REQUEST_07.json", request)
        support.copy_file(pr200 / "D2_06_TERMINAL_DISPOSITION.json", output / "D2_06_TERMINAL_DISPOSITION.json")
        support.copy_file(pr200 / "PREPARE_TIMEOUT_EVIDENCE_RETENTION_POLICY.json", output / "UPSTREAM_PREPARE_TIMEOUT_EVIDENCE_RETENTION_POLICY.json")
        support.copy_file(upstream, output / "UPSTREAM_PR200_REVIEW_ARTIFACT.zip")
        for relative in SOURCE_FILES:
            support.copy_file(source_root / relative, output / relative, 0o700 if relative.endswith(".sh") else 0o600)

        review = {
            "schema": REVIEW_SCHEMA,
            "state": "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_BOUND_REQUEST_07_UNAUTHORIZED",
            "decision_id": contract.DECISION_ID,
            "source_sha": args.source_sha,
            "base_pr": 200,
            "base_head_sha": contract.PR200_HEAD,
            "upstream_artifact_id": contract.PR200_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR200_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR200_REVIEW_BINDING_SHA256,
            "d2_request_id": contract.REQUEST_07_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "execution_package_sha256": package_digest,
            "evidence_policy_version": contract.EVIDENCE_POLICY_VERSION,
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
        review["review_binding_sha256"] = support.canonical_sha256(review)
        support.write_json(output / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_BINDING_REVIEW.json", review)
        tar_path = output / "stage2d9r-g3r-prepare-timeout-evidence-execution-binding-review-v1.tar"
        support.deterministic_tar(output, tar_path)
        support.write_sums(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--upstream-artifact", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if contract.HEX40.fullmatch(args.source_sha) is None:
        raise SystemExit("SOURCE_SHA_INVALID")
    build(args)
    print(json.dumps({
        "status": "PACKAGE_BUILT",
        "d2_request_id": contract.REQUEST_07_ID,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
