#!/usr/bin/env python3
"""Read-only successor D2 preflight and exact request generator.

The tool consumes public repository/Artifact metadata, the already-reviewed
host/custody probe result, and U1-02 metadata files. It never reads secret
material files and never connects to a board, serial port, network service or
Broker.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_contract_20260727_v1.py"

def load_contract():
    spec = importlib.util.spec_from_file_location("stage2d9r_successor_d2_contract", CONTRACT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("CONTRACT_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CONTRACT = load_contract()
HEX64 = re.compile(r"^[0-9a-f]{64}$")
U1_02_RECORD_SHA256 = CONTRACT.PUBLIC_BINDINGS["u1_02_authorization_record_sha256"]
U1_02_RESULT_SHA256 = CONTRACT.PUBLIC_BINDINGS["u1_02_result_sha256"]
EXPECTED_CUSTODY_ROOT_DIGEST = CONTRACT.PUBLIC_BINDINGS["custody_root_digest_sha256"]
CUSTODY_RELATIVE = Path(".local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02")
FORBIDDEN_OUTPUT_KEYS = {
    "custody_root",
    "private_path",
    "serial_path",
    "raw_board_identifier",
    "raw_serial_identifier",
    "mqtt_password",
    "persistence_key",
    "unlock_token",
    "private_key",
    "password_database",
    "prepare_command",
    "verify_command",
}

class PreflightError(RuntimeError):
    pass

def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightError(code)

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"

def require_regular_metadata(path: Path, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == "0600", code)

def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "JSON_INPUT_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_INPUT_NOT_OBJECT")
    return value

def one_of(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None

def validate_repository_state(value: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == "gh.h3.n2.stage2d9r-successor-d2-repository-state/1",
            "REPOSITORY_STATE_SCHEMA_MISMATCH")
    require(value.get("repository") == CONTRACT.REPOSITORY, "REPOSITORY_MISMATCH")
    require(value.get("main_sha") == CONTRACT.EXPECTED_MAIN_SHA, "MAIN_SHA_MISMATCH")
    pr180 = value.get("pull_request_180")
    pr176 = value.get("pull_request_176")
    require(isinstance(pr180, dict) and isinstance(pr176, dict), "PR_STATE_MISSING")
    require(pr180.get("head_sha") == review.get("source_sha"), "PR180_HEAD_MISMATCH")
    require(pr180.get("base_sha") == CONTRACT.BASE_SOURCE_SHA, "PR180_BASE_MISMATCH")
    require(pr176.get("head_sha") == CONTRACT.BASE_SOURCE_SHA, "PR176_HEAD_MISMATCH")
    for name, pr in (("PR180", pr180), ("PR176", pr176)):
        require(pr.get("state") == "open", f"{name}_NOT_OPEN")
        require(pr.get("draft") is True, f"{name}_NOT_DRAFT")
        require(pr.get("merged") is False, f"{name}_MERGED")
        require(pr.get("mergeable") is True, f"{name}_NOT_MERGEABLE")
    ci = value.get("current_head_ci")
    require(isinstance(ci, dict), "CI_STATE_MISSING")
    require(isinstance(ci.get("total"), int) and ci["total"] > 0, "CI_TOTAL_INVALID")
    require(ci.get("completed_success") == ci.get("total"), "CI_NOT_ALL_SUCCESS")
    require(ci.get("pending") == 0 and ci.get("failed") == 0, "CI_NOT_TERMINAL_SUCCESS")
    return {
        "main_sha": value["main_sha"],
        "source_sha": pr180["head_sha"],
        "ci_total": ci["total"],
        "ci_completed_success": ci["completed_success"],
    }

def validate_artifact_state(
    value: dict[str, Any],
    *,
    expected_schema: str,
    expected_id: int,
    expected_digest: str,
    expected_source_sha: str,
) -> dict[str, Any]:
    require(value.get("schema") == expected_schema, "ARTIFACT_STATE_SCHEMA_MISMATCH")
    require(value.get("id") == expected_id, "ARTIFACT_ID_MISMATCH")
    require(value.get("digest_sha256") == expected_digest, "ARTIFACT_DIGEST_MISMATCH")
    require(value.get("source_sha") == expected_source_sha, "ARTIFACT_SOURCE_MISMATCH")
    require(value.get("expired") is False, "ARTIFACT_EXPIRED")
    require(value.get("accessible") is True, "ARTIFACT_NOT_ACCESSIBLE")
    return {
        "id": expected_id,
        "digest_sha256": expected_digest,
        "source_sha": expected_source_sha,
        "expired": False,
    }

def validate_host_probe(value: dict[str, Any], home: Path) -> dict[str, Any]:
    require(value.get("schema") == "gh.h3.n2.stage2d9r-successor-host-artifact-custody-preauth-probe/1",
            "HOST_PROBE_SCHEMA_MISMATCH")
    require(value.get("result") == "PASS_READ_ONLY_PREAUTH", "HOST_PROBE_NOT_PASS")
    require(
        value.get("python_executable_sha256")
        == CONTRACT.PUBLIC_BINDINGS["python_executable_sha256"],
        "HOST_PROBE_PYTHON_TOOLCHAIN_MISMATCH",
    )
    require(value.get("private_material_content_read") is False, "HOST_PROBE_PRIVATE_CONTENT_READ")
    for key in (
        "authorization_created",
        "authorization_claimed",
        "authorization_consumed_by_probe",
        "private_paths_included",
        "secret_values_included",
        "network_operation",
        "broker_started",
        "board_operation",
        "serial_operation",
        "flash_operation",
        "physical_nvs_operation",
        "prepare_executed",
        "verify_executed",
        "activate_executed",
        "cleanup_executed",
        "production_operation",
    ):
        require(value.get(key) is False, f"HOST_PROBE_BOUNDARY_EXPANDED_{key.upper()}")
    immutable = value.get("immutable_artifact")
    custody = value.get("successor_private_custody")
    require(isinstance(immutable, dict) and isinstance(custody, dict), "HOST_PROBE_BINDINGS_MISSING")
    expected_immutable = {
        "source_sha": CONTRACT.PUBLIC_BINDINGS["immutable_artifact_source_sha"],
        "build_binding": CONTRACT.PUBLIC_BINDINGS["immutable_build_binding"],
        "payload_tar_sha256": CONTRACT.PUBLIC_BINDINGS["immutable_payload_tar_sha256"],
        "application_sha256": CONTRACT.PUBLIC_BINDINGS["immutable_application_sha256"],
        "merged_image_sha256": CONTRACT.PUBLIC_BINDINGS["immutable_merged_image_sha256"],
        "candidate_digest_sha256": CONTRACT.PUBLIC_BINDINGS["candidate_digest_sha256"],
        "ca_pem_sha256": CONTRACT.PUBLIC_BINDINGS["ca_pem_sha256"],
    }
    for key, expected in expected_immutable.items():
        require(immutable.get(key) == expected, f"HOST_PROBE_IMMUTABLE_MISMATCH_{key.upper()}")
    expected_custody = {
        "authorization_status": "CONSUMED",
        "private_descriptor_sha256": CONTRACT.PUBLIC_BINDINGS["private_descriptor_sha256"],
        "private_package_sha256": CONTRACT.PUBLIC_BINDINGS["private_package_sha256"],
        "public_descriptor_sha256": CONTRACT.PUBLIC_BINDINGS["public_descriptor_sha256"],
        "candidate_digest_sha256": CONTRACT.PUBLIC_BINDINGS["candidate_digest_sha256"],
        "private_material_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "marker_modified": False,
    }
    for key, expected in expected_custody.items():
        require(custody.get(key) == expected, f"HOST_PROBE_CUSTODY_MISMATCH_{key.upper()}")
    resolved_home = home.expanduser().resolve(strict=True)
    root_digest = sha256_bytes(str((resolved_home / CUSTODY_RELATIVE).resolve(strict=False)).encode())
    require(root_digest == EXPECTED_CUSTODY_ROOT_DIGEST, "CUSTODY_ROOT_SELECTION_DRIFT")
    return {
        "host_probe_result_sha256": sha256_bytes(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ),
        "custody_root_digest_sha256": root_digest,
        "private_descriptor_sha256": custody["private_descriptor_sha256"],
        "private_package_sha256": custody["private_package_sha256"],
        "candidate_digest_sha256": custody["candidate_digest_sha256"],
        "private_material_content_read": False,
    }

def validate_u1_02(
    authorization_record: Path,
    result_path: Path,
    consumed_marker: Path,
) -> dict[str, Any]:
    for path in (authorization_record, result_path, consumed_marker):
        require_regular_metadata(path, "U1_02_METADATA_FILE_INVALID")
    require(sha256_file(authorization_record) == U1_02_RECORD_SHA256,
            "U1_02_AUTHORIZATION_RECORD_SHA_MISMATCH")
    require(sha256_file(result_path) == U1_02_RESULT_SHA256,
            "U1_02_RESULT_SHA_MISMATCH")
    marker_before = sha256_file(consumed_marker)
    marker = load_json(consumed_marker)
    require(marker.get("authorization_id") == CONTRACT.U1_02_ID, "U1_02_MARKER_ID_MISMATCH")
    require(marker.get("status") in ("CONSUMED", "CONSUMED_PASS"), "U1_02_MARKER_STATUS_MISMATCH")
    require(
        one_of(marker, "authorization_record_sha256", "record_sha256") == U1_02_RECORD_SHA256,
        "U1_02_MARKER_RECORD_MISMATCH",
    )
    require(one_of(marker, "result_sha256", "execution_result_sha256") == U1_02_RESULT_SHA256,
            "U1_02_MARKER_RESULT_MISMATCH")
    require(marker.get("replay_permitted") is False, "U1_02_MARKER_REPLAY_EXPANDED")
    require(marker.get("automatic_retry_permitted") is False, "U1_02_MARKER_RETRY_EXPANDED")
    if "one_shot" in marker:
        require(marker.get("one_shot") is True, "U1_02_MARKER_NOT_ONE_SHOT")
    for key in ("secret_values_included", "private_paths_included"):
        if key in marker:
            require(marker.get(key) is False, f"U1_02_MARKER_{key.upper()}")
    require(sha256_file(consumed_marker) == marker_before, "U1_02_MARKER_CHANGED_DURING_PREFLIGHT")
    return {
        "authorization_id": CONTRACT.U1_02_ID,
        "authorization_record_sha256": U1_02_RECORD_SHA256,
        "result_sha256": U1_02_RESULT_SHA256,
        "consumed_marker_sha256": marker_before,
        "status": "CONSUMED_PASS",
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "marker_modified": False,
    }

def validate_review_binding(value: dict[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == "gh.h3.n2.stage2d9r-successor-d2-review-binding/1",
            "REVIEW_BINDING_SCHEMA_MISMATCH")
    require(value.get("stage") == CONTRACT.STAGE, "REVIEW_STAGE_MISMATCH")
    require(value.get("d2_request_id") == CONTRACT.D2_REQUEST_ID, "REVIEW_D2_ID_MISMATCH")
    require(value.get("main_sha") == CONTRACT.EXPECTED_MAIN_SHA, "REVIEW_MAIN_MISMATCH")
    require(value.get("base_source_sha") == CONTRACT.BASE_SOURCE_SHA, "REVIEW_BASE_MISMATCH")
    require(value.get("exact_authorization_request_included") is False,
            "REVIEW_ALREADY_CONTAINS_EXACT_AUTHORIZATION")
    for key in (
        "authorization_record_included",
        "execution_launcher_included",
        "private_content_included",
        "board_operation",
        "serial_operation",
        "flash_operation",
        "physical_nvs_operation",
        "network_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "activate_executed",
        "cleanup_executed",
        "production_operation",
    ):
        require(value.get(key) is False, f"REVIEW_BOUNDARY_EXPANDED_{key.upper()}")
    return value

def write_json_exclusive(path: Path, value: object) -> None:
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)

def run(args: argparse.Namespace) -> dict[str, Any]:
    review = validate_review_binding(load_json(args.review_binding))
    repository = validate_repository_state(load_json(args.repository_state), review)
    review_artifact = validate_artifact_state(
        load_json(args.review_artifact_state),
        expected_schema="gh.h3.n2.stage2d9r-successor-d2-review-artifact-state/1",
        expected_id=args.review_artifact_id,
        expected_digest=args.review_artifact_digest_sha256,
        expected_source_sha=review["source_sha"],
    )
    public_preflight_artifact = validate_artifact_state(
        load_json(args.public_preflight_artifact_state),
        expected_schema="gh.h3.n2.stage2d9r-successor-d2-public-preflight-artifact-state/1",
        expected_id=args.public_preflight_artifact_id,
        expected_digest=args.public_preflight_artifact_digest_sha256,
        expected_source_sha=review["source_sha"],
    )
    host_probe_value = load_json(args.host_probe_result)
    host = validate_host_probe(host_probe_value, args.home)
    u1 = validate_u1_02(args.u1_02_authorization_record, args.u1_02_result, args.u1_02_consumed_marker)
    exact_digests = {
        "openssl_executable_sha256": args.openssl_executable_sha256,
        "board_identity_sha256": args.board_identity_sha256,
        "serial_identity_sha256": args.serial_identity_sha256,
        "baseline_state_sha256": args.baseline_state_sha256,
        "execution_package_sha256": args.execution_package_sha256,
        "execution_script_sha256": args.execution_script_sha256,
        "execution_launcher_sha256": args.execution_launcher_sha256,
        "execution_marker_name_sha256": args.execution_marker_name_sha256,
        "locked_recovery_package_sha256": args.locked_recovery_package_sha256,
    }
    for name, digest in exact_digests.items():
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            f"{name.upper()}_INVALID",
        )
    require(
        args.openssl_executable_sha256
        == CONTRACT.PUBLIC_BINDINGS["openssl_executable_sha256"],
        "OPENSSL_TOOLCHAIN_MISMATCH",
    )

    contract = CONTRACT.build_contract(review["source_sha"], review["main_sha"])
    require(contract["contract_binding_sha256"] == review["contract_binding_sha256"],
            "CONTRACT_REVIEW_BINDING_MISMATCH")
    preflight: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/1",
        "stage": CONTRACT.STAGE,
        "result": "PASS_READ_ONLY_D2_PREFLIGHT",
        "repository_state": repository,
        "review_artifact": review_artifact,
        "public_preflight_artifact": public_preflight_artifact,
        "review_binding_sha256": review["review_binding_sha256"],
        "contract_binding_sha256": contract["contract_binding_sha256"],
        "host_and_custody": host,
        "u1_02": u1,
        "python_executable_sha256": CONTRACT.PUBLIC_BINDINGS["python_executable_sha256"],
        "openssl_executable_sha256": args.openssl_executable_sha256,
        "board_identity_sha256": args.board_identity_sha256,
        "serial_identity_sha256": args.serial_identity_sha256,
        "baseline_state_sha256": args.baseline_state_sha256,
        "board_identity_source": "PREVIOUSLY_FROZEN_PRIVATE_METADATA_NO_LIVE_BOARD_ACCESS",
        "serial_identity_source": "PREVIOUSLY_FROZEN_PRIVATE_METADATA_NO_LIVE_SERIAL_ACCESS",
        "baseline_state_source": "PREVIOUSLY_FROZEN_PRIVATE_METADATA_NO_LIVE_BOARD_ACCESS",
        "execution_package_sha256": args.execution_package_sha256,
        "execution_script_sha256": args.execution_script_sha256,
        "execution_launcher_sha256": args.execution_launcher_sha256,
        "execution_marker_name_sha256": args.execution_marker_name_sha256,
        "locked_recovery_package_sha256": args.locked_recovery_package_sha256,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "private_material_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
    }
    preflight["preflight_result_sha256"] = sha256_bytes(
        json.dumps(preflight, sort_keys=True, separators=(",", ":")).encode()
    )
    exact_request = CONTRACT.build_exact_authorization_request(
        contract,
        review_artifact_id=args.review_artifact_id,
        review_artifact_digest_sha256=args.review_artifact_digest_sha256,
        review_binding_sha256=review["review_binding_sha256"],
        public_preflight_artifact_id=args.public_preflight_artifact_id,
        public_preflight_artifact_digest_sha256=args.public_preflight_artifact_digest_sha256,
        private_preflight_result_sha256=preflight["preflight_result_sha256"],
        u1_02_consumed_marker_sha256=u1["consumed_marker_sha256"],
        board_identity_sha256=args.board_identity_sha256,
        serial_identity_sha256=args.serial_identity_sha256,
        baseline_state_sha256=args.baseline_state_sha256,
        execution_package_sha256=args.execution_package_sha256,
        execution_script_sha256=args.execution_script_sha256,
        execution_launcher_sha256=args.execution_launcher_sha256,
        execution_marker_name_sha256=args.execution_marker_name_sha256,
        locked_recovery_package_sha256=args.locked_recovery_package_sha256,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
    )
    return {"preflight": preflight, "exact_request": exact_request}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-binding", type=Path, required=True)
    parser.add_argument("--repository-state", type=Path, required=True)
    parser.add_argument("--review-artifact-state", type=Path, required=True)
    parser.add_argument("--review-artifact-id", type=int, required=True)
    parser.add_argument("--review-artifact-digest-sha256", required=True)
    parser.add_argument("--public-preflight-artifact-state", type=Path, required=True)
    parser.add_argument("--public-preflight-artifact-id", type=int, required=True)
    parser.add_argument("--public-preflight-artifact-digest-sha256", required=True)
    parser.add_argument("--host-probe-result", type=Path, required=True)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--u1-02-authorization-record", type=Path, required=True)
    parser.add_argument("--u1-02-result", type=Path, required=True)
    parser.add_argument("--u1-02-consumed-marker", type=Path, required=True)
    parser.add_argument("--openssl-executable-sha256", required=True)
    parser.add_argument("--board-identity-sha256", required=True)
    parser.add_argument("--serial-identity-sha256", required=True)
    parser.add_argument("--baseline-state-sha256", required=True)
    parser.add_argument("--execution-package-sha256", required=True)
    parser.add_argument("--execution-script-sha256", required=True)
    parser.add_argument("--execution-launcher-sha256", required=True)
    parser.add_argument("--execution-marker-name-sha256", required=True)
    parser.add_argument("--locked-recovery-package-sha256", required=True)
    parser.add_argument("--issued-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--request-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args)
        write_json_exclusive(args.preflight_output, result["preflight"])
        write_json_exclusive(args.request_output, result["exact_request"])
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, PreflightError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "preflight_result_sha256": result["preflight"]["preflight_result_sha256"],
        "request_binding_sha256": result["exact_request"]["request_binding_sha256"],
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
