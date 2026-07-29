#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import zipfile

import h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_support_20260729_v1 as support

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-review/1"
EXECUTION_DIR = "prepare-panic-timeline-reset-signature-physical-d2-execution-package"
UPSTREAM_EXECUTION_DIR = "prepare-evidence-controller-repair-physical-d2-execution-package"
PACKAGE_BINDING_FILE = contract.BINDING_FILE
REPAIR_BINDING_FILE = "PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_REPAIR.json"
SOURCE_FILES = (
    "tools/h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py",
    "tools/run_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_packager_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_20260729_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_shell_20260729_v1.sh",
    "docs/decisions/h3-n2-stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-contract-20260729-v1.md",
    ".github/workflows/h3-n2-stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-review-ci-v1.yml",
)


def package_set_digest(root: Path, names: list[str]) -> str:
    entries = [{"name": name, "sha256": support.sha256_file(root / name)} for name in sorted(names)]
    return support.canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-package-set/1",
        "files": entries,
    })


def extract_upstream(archive: Path, root: Path) -> tuple[Path, Path]:
    if support.sha256_file(archive) != contract.PR202_ARTIFACT_SHA256:
        raise RuntimeError("UPSTREAM_ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(archive) as outer:
        outer.extractall(root / "pr202")
    pr202 = root / "pr202"
    review = json.loads(
        (pr202 / "PREPARE_EVIDENCE_CONTROLLER_CONSTANT_BINDING_REPAIR_REVIEW.json").read_text(
            encoding="utf-8"
        )
    )
    observed = dict(review)
    binding = observed.pop("review_binding_sha256", None)
    if binding != contract.PR202_REVIEW_BINDING_SHA256:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_MISMATCH")
    if support.canonical_sha256(observed) != binding:
        raise RuntimeError("UPSTREAM_REVIEW_BINDING_INVALID")
    if review.get("source_sha") != contract.PR202_HEAD:
        raise RuntimeError("UPSTREAM_SOURCE_SHA_MISMATCH")
    embedded = pr202 / "UPSTREAM_PR201_REVIEW_ARTIFACT.zip"
    if support.sha256_file(embedded) != contract.PR201_ARTIFACT_SHA256:
        raise RuntimeError("EMBEDDED_PR201_ARTIFACT_DIGEST_MISMATCH")
    package = pr202 / UPSTREAM_EXECUTION_DIR
    if not package.is_dir() or package.is_symlink():
        raise RuntimeError("UPSTREAM_EXECUTION_PACKAGE_MISSING")
    return pr202, package


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

    with tempfile.TemporaryDirectory(prefix="prepare-panic-timeline-repair-") as td:
        temp = Path(td)
        _, upstream_package = extract_upstream(upstream, temp)
        execution = output / EXECUTION_DIR
        execution.mkdir(mode=0o700)

        for path in sorted(upstream_package.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name != "SHA256SUMS":
                support.copy_file(path, execution / path.name, 0o700 if path.suffix == ".sh" else 0o600)

        additions = {
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1.py": source_root / SOURCE_FILES[0],
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1.py": source_root / SOURCE_FILES[1],
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py": source_root / SOURCE_FILES[2],
            "run_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_20260729_v1.sh": source_root / SOURCE_FILES[3],
        }
        for name, source in additions.items():
            support.copy_file(
                source,
                execution / name,
                0o700 if name.endswith(".sh") or "wrapper" in name else 0o600,
            )

        repair_binding = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair/1",
            "state": "FROZEN_UNAUTHORIZED_PREPARE_PANIC_TIMELINE_REPAIR",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_09_ID,
            "predecessor_request_id": contract.D2_08_ID,
            "predecessor_status": contract.D2_08_STATUS,
            "predecessor_terminal_state": contract.D2_08_TERMINAL_STATE,
            "predecessor_failure_code": contract.D2_08_FAILURE_CODE,
            "predecessor_evidence_classification": contract.D2_08_CLASSIFICATION,
            "predecessor_terminal_result_sha256": contract.D2_08_TERMINAL_RESULT_SHA256,
            "realtime_byte_receipt_timestamps": True,
            "monotonic_timestamps": True,
            "capture_phase_partitioning": [
                "startup", "ready_wait", "ready_observed", "post_command", "late_window", "result"
            ],
            "one_reset_event_per_boot": True,
            "normalized_panic_fields": list(contract.NORMALIZED_PANIC_FIELDS),
            "local_private_normalized_panic_evidence": True,
            "real_board_evidence_in_public_artifact": False,
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
            "state": "FROZEN_UNAUTHORIZED_PREPARE_PANIC_TIMELINE_PACKAGE",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": contract.REQUEST_09_ID,
            "source_sha": args.source_sha,
            "base_pr": 202,
            "base_head_sha": contract.PR202_HEAD,
            "upstream_artifact_id": contract.PR202_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR202_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR202_REVIEW_BINDING_SHA256,
            "execution_package_sha256": package_digest,
            "execution_wrapper_sha256": support.sha256_file(
                execution / "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py"
            ),
            "execution_launcher_sha256": support.sha256_file(
                execution / "run_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_20260729_v1.sh"
            ),
            "panic_timeline_recorder_sha256": support.sha256_file(
                execution / "h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1.py"
            ),
            "evidence_contract_sha256": support.sha256_file(
                execution / "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1.py"
            ),
            "panic_timeline_repair_binding_sha256": support.sha256_file(execution / REPAIR_BINDING_FILE),
            "evidence_policy_version": contract.EVIDENCE_POLICY_VERSION,
            "realtime_byte_receipt_timestamps": True,
            "monotonic_timestamps": True,
            "one_reset_event_per_boot": True,
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
        support.write_json(output / "PHYSICAL_D2_REQUEST_09.json", request)
        support.write_json(output / "D2_08_TERMINAL_DISPOSITION.json", {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-terminal-disposition/1",
            "d2_request_id": contract.D2_08_ID,
            "status": contract.D2_08_STATUS,
            "terminal_state": contract.D2_08_TERMINAL_STATE,
            "failure_code": contract.D2_08_FAILURE_CODE,
            "evidence_classification": contract.D2_08_CLASSIFICATION,
            "authorization_record_sha256": contract.D2_08_AUTHORIZATION_SHA256,
            "terminal_result_sha256": contract.D2_08_TERMINAL_RESULT_SHA256,
            "prepare_serial_evidence_sha256": contract.D2_08_PREPARE_SERIAL_SHA256,
            "prepare_broker_evidence_sha256": contract.D2_08_PREPARE_BROKER_SHA256,
            "prepare_timeline_sha256": contract.D2_08_PREPARE_TIMELINE_SHA256,
            "prepare_count": 1,
            "verify_count": 0,
            "recovery_attempted": True,
            "recovery_succeeded": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        })
        support.copy_file(upstream, output / "UPSTREAM_PR202_REVIEW_ARTIFACT.zip")
        for relative in SOURCE_FILES:
            support.copy_file(
                source_root / relative,
                output / relative,
                0o700 if relative.endswith(".sh") else 0o600,
            )

        review = {
            "schema": REVIEW_SCHEMA,
            "state": "PREPARE_PANIC_TIMELINE_REPAIRED_REQUEST_09_UNAUTHORIZED",
            "decision_id": contract.DECISION_ID,
            "source_sha": args.source_sha,
            "base_pr": 202,
            "base_head_sha": contract.PR202_HEAD,
            "upstream_artifact_id": contract.PR202_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.PR202_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.PR202_REVIEW_BINDING_SHA256,
            "predecessor_request_id": contract.D2_08_ID,
            "predecessor_status": contract.D2_08_STATUS,
            "predecessor_failure_code": contract.D2_08_FAILURE_CODE,
            "predecessor_evidence_classification": contract.D2_08_CLASSIFICATION,
            "predecessor_terminal_result_sha256": contract.D2_08_TERMINAL_RESULT_SHA256,
            "d2_request_id": contract.REQUEST_09_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "execution_package_sha256": package_digest,
            "realtime_byte_receipt_timestamps": True,
            "monotonic_timestamps": True,
            "one_reset_event_per_boot": True,
            "normalized_panic_fields": list(contract.NORMALIZED_PANIC_FIELDS),
            "real_board_evidence_in_public_artifact": False,
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
        support.write_json(output / "PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_REPAIR_REVIEW.json", review)
        tar_path = output / "stage2d9r-g3r-prepare-panic-timeline-reset-signature-repair-review-v1.tar"
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
        "d2_request_id": contract.REQUEST_09_ID,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
