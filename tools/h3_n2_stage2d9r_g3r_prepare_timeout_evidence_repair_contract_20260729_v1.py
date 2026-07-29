#!/usr/bin/env python3
"""Source-only contract for PREPARE timeout evidence retention repair."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PREPARE-RESULT-TIMEOUT-EVIDENCE-REPAIR-20260729-01"
STAGE = "H3/N2 Stage 2D-9R G3R PREPARE timeout evidence repair"
STATE = "PREPARE_TIMEOUT_EVIDENCE_REPAIR_SOURCE_FROZEN_UNAUTHORIZED"
BASE_PR = 199
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-physical-execution-overlay-binding-repair-20260729-v1"
BASE_HEAD_SHA = "79542efe3b3465d3381a797862e2f5362cc3cfe8"
UPSTREAM_ARTIFACT_ID = 8709137550
UPSTREAM_ARTIFACT_SHA256 = "60627828577a771a251b8ee00f96016e9c4f984c9532f455d406ec1135c84e8b"
UPSTREAM_REVIEW_BINDING_SHA256 = "ca359412cf01b932decd0271e19af3952f6cfe9fb2eef2368be5d931b9ba89cb"
UPSTREAM_INNER_TAR_SHA256 = "e7cd51a4413f4c295ee5d2334549266ef67f56eeda47dc7541168e1863fef6bf"

D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-06"
D2_STATUS = "CONSUMED_FAILED"
D2_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
D2_FAILURE_CODE = "PREPARE_RESULT_TIMEOUT"
D2_AUTHORIZATION_RECORD_SHA256 = "0fa8a1e3d5c2badfd7dfd61fce2d99f8eec57cfa179fac540508c6b35ace583d"
D2_AUTHORIZATION_FILE_SHA256 = "c4e79142786889068e0d1f427a6e33494030bff76b5c7ab685958f62a6e268f1"
D2_CONTRACT_CHECK_FILE_SHA256 = "ec5f2153f6f4e0e89ccf9917f07caba69c0f6218e7ce8d6bbda7eafee6781eff"
D2_RESULT_FILE_SHA256 = "cba353e7b2c4a7765b3ce03b40c76aeebe59cc971e45e68511ce7f22c5b8beba"
D2_TERMINAL_LOG_SHA256 = "9076c6c5bde7b8626c6f84d732931e3cf11b055fb0fa0b4d291cd2c5c34b3067"
D2_MARKER_FILE_SHA256 = "5c71d297b54b08d4e1ab5ac66b96f094cb34bc1a886d763100f137c4d68ddec1"
D2_TERMINAL_RESULT_SHA256 = "251090684c368eba59ef7b5c7ec5c158beba1905159bca864669e52ec946ba49"
D2_PREPARE_RESULT_SHA256 = "941d77833013132e03363014380d24cd79c72cb01e3ddbacc400b79e0157d320"
D2_BROKER_LOG_SHA256 = "1690016e60eed62523c89e35b505de3cba03f997f528916b70c0bdfbc9caa152"
D2_OBSERVED_BASELINE_SHA256 = "776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f"
D2_FLASH_SHA256 = "67dc276c7ef69a1528d511c4043ec3eb58489eefb6864442f03e405f24611cb3"
D2_REQUEST_BINDING_SHA256 = "effb7d5dc64a3deacab8740935c3f7ed016dfbd517a2d70f498917c986115a39"

IMMUTABLE_PAYLOAD_TAR_SHA256 = "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
RECOVERY_PAYLOAD_TAR_SHA256 = "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-repair-review/1"
DISPOSITION_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-06-terminal-disposition/1"
POLICY_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-policy/1"
ROOT_SUMS_FILE = "SHA256SUMS"
REVIEW_FILE = "PREPARE_TIMEOUT_EVIDENCE_REPAIR_REVIEW.json"
DISPOSITION_FILE = "D2_06_TERMINAL_DISPOSITION.json"
POLICY_FILE = "PREPARE_TIMEOUT_EVIDENCE_RETENTION_POLICY.json"
UPSTREAM_ZIP_FILE = "UPSTREAM_PR199_REVIEW_ARTIFACT.zip"
ARCHIVE_FILE = "stage2d9r-g3r-prepare-timeout-evidence-repair-review-v1.tar"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

FALSE_BOUNDARY = {
    "authorization_created": False,
    "authorization_claimed": False,
    "authorization_consumed": False,
    "physical_request_created": False,
    "physical_request_authorized": False,
    "board_operation": False,
    "usb_enumeration": False,
    "serial_operation": False,
    "esptool_operation": False,
    "flash_operation": False,
    "network_operation": False,
    "broker_started": False,
    "prepare_executed": False,
    "verify_executed": False,
    "activate_executed": False,
    "cleanup_executed": False,
    "ready": False,
    "merge": False,
    "release": False,
    "tag": False,
    "deployment": False,
}

class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha40(value: str, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha64(value: str, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def d2_terminal_disposition() -> dict[str, Any]:
    return {
        "schema": DISPOSITION_SCHEMA,
        "d2_request_id": D2_REQUEST_ID,
        "status": D2_STATUS,
        "terminal_state": D2_TERMINAL_STATE,
        "failure_code": D2_FAILURE_CODE,
        "authorization_record_sha256": D2_AUTHORIZATION_RECORD_SHA256,
        "authorization_file_sha256": D2_AUTHORIZATION_FILE_SHA256,
        "contract_check_file_sha256": D2_CONTRACT_CHECK_FILE_SHA256,
        "result_file_sha256": D2_RESULT_FILE_SHA256,
        "terminal_log_sha256": D2_TERMINAL_LOG_SHA256,
        "marker_file_sha256": D2_MARKER_FILE_SHA256,
        "terminal_result_sha256": D2_TERMINAL_RESULT_SHA256,
        "prepare_result_sha256": D2_PREPARE_RESULT_SHA256,
        "broker_log_sha256": D2_BROKER_LOG_SHA256,
        "request_binding_sha256": D2_REQUEST_BINDING_SHA256,
        "observed_baseline_sha256": D2_OBSERVED_BASELINE_SHA256,
        "flash_sha256": D2_FLASH_SHA256,
        "prepare_count": 1,
        "verify_count": 0,
        "recovery_attempted": True,
        "recovery_succeeded": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "raw_prepare_log_retained": False,
        "raw_broker_log_retained": False,
        "root_cause_resolved": False,
    }


def evidence_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "state": "SOURCE_ONLY_FUTURE_EXECUTOR_REQUIRES_NEW_EXACT_DECISION",
        "terminal_evidence_root_mode": "0700",
        "terminal_evidence_file_mode": "0600",
        "atomic_write_required": True,
        "persist_before_recovery": True,
        "persist_before_temporary_directory_cleanup": True,
        "serial_transcript_format": "redacted-jsonl",
        "broker_transcript_format": "redacted-jsonl",
        "timeline_format": "canonical-json",
        "raw_command_material_retained": False,
        "raw_mac_retained": False,
        "raw_ip_retained": False,
        "raw_usb_path_retained": False,
        "raw_private_path_retained": False,
        "unknown_line_policy": "HASH_ONLY",
        "classifications": [
            "NO_RESULT",
            "SERIAL_RESET",
            "BROKER_DISCONNECT",
            "LATE_RESULT",
            "UNRECOGNIZED_RESULT",
        ],
        "late_result_observation_window_seconds": 5,
        "new_physical_request_created": False,
        "physical_authorization_created": False,
    }


def source_contract(source_sha: str) -> dict[str, Any]:
    source_sha = validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR199")
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-repair-source-contract/1",
        "state": STATE,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "d2_06_status": D2_STATUS,
        "d2_06_terminal_state": D2_TERMINAL_STATE,
        "d2_06_failure_code": D2_FAILURE_CODE,
        "d2_06_terminal_result_sha256": D2_TERMINAL_RESULT_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "new_physical_request_created": False,
        **FALSE_BOUNDARY,
    }


def validate_disposition(value: dict[str, Any]) -> None:
    expected = d2_terminal_disposition()
    require(value == expected, "D2_06_DISPOSITION_MISMATCH")
    for key, item in value.items():
        if key.endswith("sha256"):
            validate_sha64(item, "D2_06_DISPOSITION_DIGEST_INVALID")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
