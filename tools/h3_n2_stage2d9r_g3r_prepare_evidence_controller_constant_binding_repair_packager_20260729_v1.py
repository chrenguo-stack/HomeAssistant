#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_support_20260729_v1 as support

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair-review/1"
EXECUTION_DIR = "prepare-evidence-controller-repair-physical-d2-execution-package"
UPSTREAM_EXECUTION_DIR = "prepare-timeout-evidence-physical-d2-execution-package"
PACKAGE_BINDING_FILE = "PREPARE_EVIDENCE_CONTROLLER_REPAIR_EXECUTION_PACKAGE_BINDING.json"
REPAIR_BINDING_FILE = "PREPARE_EVIDENCE_CONTROLLER_CONSTANT_BINDING_REPAIR.json"
SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_packager_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair-review-ci-v1.yml",
)


def package_set_digest(root: Path, names: list[str]) -> str:
    entries = [{"name": name, "sha256": support.sha256_file(root / name)} for name in sorted(names)]
    return support.canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-package-set/1",
        "files": entries,
    })


def extract_upstream(archive: Path, root: Path) -> tuple[Path, Path]:
    if support.sha256_file(archive) != contract.PR201_ARTIFACT_SHA256:
        raise RuntimeError("UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(archive) as outer:
        outer.extractall(root / "pr201")
    pr201 = root / "pr201"
    review = json.loads((pr201 / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_BINDING_REVIEW.json").read_text(encoding="utf-8"))
    observed = dict(review)
    binding = observed.pop("review_binding_sha256", None)
    if binding != contract.PR201_REVIEW_BINDING_SHA256:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_MISMATCH")
    if support.canonical_sha256(observed) != binding:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_INVALID")
    if review.get("source_sha") != contract.PR201_HEAD:
        raise RuntimeError("UPSTREAM_SOURCE_SHA_MISMATCH")
    embedded = pr201 / "UPSTREAM_PR200_REVIEW_ARTIFACT.zip"
    if support.sha256_file(embedded) != contract.PR200_ARTIFACT_SHA256:
        raise RuntimeError("EMBEDDED_PR200_ARTIFACT_DIGEST_MISMATCH")
    package = pr201 / UPSTREAM_EXECUTION_DIR
    if not package.is_dir() or package.is_symlink():
        raise RuntimeError("UPSTREAM_EXECUTION_PACKAGE_MISSING")
    return pr201, package


def build(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve(strict=True)
    upstream = args.upstream_artifact.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise RuntimeError("OUTPUT_NOT_EMPTY")
    else:
        output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)

    with tempfile.TemporaryDirectory(prefix="prepare-controller-binding-repair-") as td:
        temp = Path(td)
        pr201, upstream_package = extract_upstream(upstream, temp)
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)

        for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name != "SHA256SUMS":
                support.copy_file(path, execution / path.name, 0o700 if path.suffix == ".sh" else 0o600)

        additions = {
            "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1.py": source_root / SOURCE_FILES[0],
            "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py": source_root / SOURCE_FILES[1],
            "run_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_20260729_v1.sh": source_root / SOURCE_FILES[2],
        }
        for name, source in additions.items():
            support.copy_file(
                source,
                execution / name,
                0o700 if name.endswith(".sh") or "wrapper" in name else 0o600,
            )

        repair_binding = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair/1",
            "state": "FROZEN_UNAUTHORIZED_CONTROLLER_CONSTANT_BINDING_REPAIR",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_08_ID,
            "predecessor_request_id": contract.D2_07_ID,
            "predecessor_status": contract.D2_07_STATUS,
            "predecessor_terminal_state": contract.D2_07_TERMINAL_STATE,
            "predecessor_failure_code": contract.D2_07_FAILURE_CODE,
            "predecessor_terminal_result_sha256": contract.D2_07_TERMINAL_RESULT_SHA256,
            "constant_owner_module": "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1",
            "forbidden_constant_owner": "frozen_core_executor_module",
            "bound_constants": [
                "RESULT_MARKERS",
                "DEVICE_FAILURE_MARKER",
                "READY_TIMEOUT_CODES",
                "RESULT_TIMEOUT_CODES",
            ],
            "stable_internal_error_codes": True,
            "raw_exception_messages_retained": False,
            "real_controller_integration_tests_required": True,
            "prepare_max_count": 1,
            "verify_max_count": 1,
            "locked_recovery_scope": "TEST_PARTITION_ONLY",
            "locked_recovery_max_count": 1,
            "physical_authorization_created": False,
            "physical_execution_started": False,
        }
        support.write_json(execution / REPAIR_BINDING_FILE, repair_binding)

        digest_names = sorted(
            path.name for path in execution.iterdir()
            if path.is_file() and path.name != PACKAGE_BINDING_FILE
        )
        package_digest = package_set_digest(execution, digest_names)
        package_binding = {
            "schema": contract.PACKAGE_BINDING_SCHEMA,
            "state": "FROZEN_UNAUTHORIZED_PREPARE_EVIDENCE_CONTROLLER_REPAIR_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_08_ID,
            "source_sha": args.source_sha,
            "base_pr": 201,
            "base_head_sha": contract.PR201_HEAD,
            "upstream_artifact_id": contract.PR201_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR201_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR201_REVIEW_BINDING_SHA256,
            "execution_package_sha256": package_digest,
            "execution_wrapper_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py"),
            "execution_launcher_sha256": support.sha256_file(execution / "run_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_20260729_v1.sh"),
            "evidence_recorder_sha256": support.sha256_file(
                execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py"
            ),
            "evidence_overlay_sha256": support.sha256_file(
                execution / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py"
            ),
            "evidence_contract_sha256": support.sha256_file(execution / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1.py"),
            "controller_repair_binding_sha256": support.sha256_file(execution / REPAIR_BINDING_FILE),
            "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
            "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
            "physical_request_authorized": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        support.write_json(execution / PACKAGE_BINDING_FILE, package_binding)
        support.write_sums(execution)
        contract.validate_execution_package(execution)

        request = contract.request_template(execution, source_sha=args.source_sha)
        support.write_json(output / "PHYSICAL_D2_REQUEST_08.json", request)
        support.write_json(output / "D2_07_TERMINAL_DISPOSITION.json", {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-terminal-disposition/1",
            "d2_request_id": contract.D2_07_ID,
            "status": contract.D2_07_STATUS,
            "terminal_state": contract.D2_07_TERMINAL_STATE,
            "failure_code": contract.D2_07_FAILURE_CODE,
            "authorization_record_sha256": contract.D2_07_AUTHORIZATION_SHA256,
            "terminal_result_sha256": contract.D2_07_TERMINAL_RESULT_SHA256,
            "prepare_serial_evidence_sha256": contract.D2_07_PREPARE_CAPTURE_SHA256,
            "prepare_broker_evidence_sha256": contract.D2_07_BROKER_LOG_SHA256,
            "prepare_count": 0,
            "verify_count": 0,
            "recovery_attempted": True,
            "recovery_succeeded": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        })
        support.copy_file(upstream, output / "UPSTREAM_PR201_REVIEW_ARTIFACT.zip")
        for relative in SOURCE_FILES:
            support.copy_file(
                source_root / relative,
                output / relative,
                0o700 if relative.endswith(".sh") else 0o600,
            )

        review = {
            "schema": REVIEW_SCHEMA,
            "state": "CONTROLLER_CONSTANT_BINDING_REPAIRED_REQUEST_08_UNAUTHORIZED",
            "decision_id": contract.DECISION_ID,
            "source_sha": args.source_sha,
            "base_pr": 201,
            "base_head_sha": contract.PR201_HEAD,
            "upstream_artifact_id": contract.PR201_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR201_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR201_REVIEW_BINDING_SHA256,
            "predecessor_request_id": contract.D2_07_ID,
            "predecessor_status": contract.D2_07_STATUS,
            "predecessor_failure_code": contract.D2_07_FAILURE_CODE,
            "predecessor_terminal_result_sha256": contract.D2_07_TERMINAL_RESULT_SHA256,
            "d2_request_id": contract.REQUEST_08_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "execution_package_sha256": package_digest,
            "controller_constant_binding_repaired": True,
            "stable_internal_error_codes": True,
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
        support.write_json(output / "PREPARE_EVIDENCE_CONTROLLER_CONSTANT_BINDING_REPAIR_REVIEW.json", review)
        tar_path = output / "stage2d9r-g3r-prepare-evidence-controller-constant-binding-repair-review-v1.tar"
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
        "d2_request_id": contract.REQUEST_08_ID,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
