#!/usr/bin/env python3
"""Source-only contract for the accepted main-drift successor rebind.

The contract preserves the consumed host-final-preflight result, permanently
invalidates the old unauthorized physical request after main drift, and defines
an inert host-only rebind gate for a new physical-D2 request identity.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-contract/1"
STALE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-stale-physical-request/1"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-request/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-marker/1"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-successor-rebind-authorization/1"

STAGE = "H3/N2 Stage 2D-9R G3R main-drift successor rebind"
DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-MAIN-DRIFT-SUCCESSOR-REBIND-20260728-01"
FUTURE_HOST_REBIND_AUTHORIZATION_ID = (
    "H3-H3N2-STAGE2D9R-G3R-MAIN-DRIFT-SUCCESSOR-REBIND-20260728-01"
)
NEW_PHYSICAL_D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03"
)
OLD_PHYSICAL_D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-02"
)
OLD_PHYSICAL_D2_REQUEST_STATE = "STALE_MAIN_DRIFT_BEFORE_AUTHORIZATION"

BASE_PR = 193
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-payload-handoff-host-final-preflight-20260728-v1"
BASE_HEAD_SHA = "bdfcda55ff248838f0d703abf6d2414f3f73eff7"
PREVIOUS_ACCEPTED_MAIN_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"
ACCEPTED_CURRENT_MAIN_SHA = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
MAIN_DRIFT_COMMIT_SHA = ACCEPTED_CURRENT_MAIN_SHA
MAIN_DRIFT_CHANGED_FILES = ("README.md",)
MAIN_DRIFT_COMMIT_COUNT = 1

UPSTREAM_ARTIFACT_ID = 8684033408
UPSTREAM_ARTIFACT_SHA256 = "1bdc1ec73946642b692e723c8b174fd082abf324274c9613350562d17854cd0b"
UPSTREAM_REVIEW_ARCHIVE_SHA256 = "ebac548d8fbec6cace3311ac772de3cfc85151e4b602a268ca81697ee3915e93"
UPSTREAM_REVIEW_BINDING_SHA256 = "ce1cc507ef9b7960a087a47e83b2f8124dc19f1d933e5812d893a1d059cae4cb"
UPSTREAM_EXECUTION_PACKAGE_SHA256 = "59f144525acc8715216cd29255f387be9d0f18dedf2ac963af805f8c62ff3d1b"
UPSTREAM_EXECUTION_WRAPPER_SHA256 = "b0eb6ef9ff50a7b8a0ea159048cb08219805c06e3dee9414e9eabc713b5cf51e"
UPSTREAM_EXECUTION_LAUNCHER_SHA256 = "8cfb67c42365115a25ee2d6c9dc09b075131d8b22afee251e8f31442c941dc49"
UPSTREAM_REPAIRED_HOST_CONTROLLER_SHA256 = "5e7ac5377e94c40fa0e2c536e4c95bffe15f99d5ac3dc91f3df4d9ddf80378ee"

H2_AUTHORIZATION_ID = "H2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-HOST-FINAL-PREFLIGHT-20260728-01"
H2_RESULT_RAW_SHA256 = "b76eda19f31df0dac0d03f8a0cef214f8f886637b71c0b59b8fd27634c025763"
H2_RESULT_CANONICAL_SHA256 = "4dd2fe9574244b85f65461b02412ec99fb254da6402f2b3b48f55b23198e02e0"
OLD_REQUEST_RAW_SHA256 = "0c3c2c3828626efb17838097643559b14d1ee2f03773108ad6f9076fb901df98"
OLD_REQUEST_BINDING_SHA256 = "a7f40ce2e2a236a6a0ae331505e60e6f9c7887e675151f5d3a6ff08eb1aca2c1"
NEW_PHYSICAL_D2_MARKER_NAME = hashlib.sha256(NEW_PHYSICAL_D2_REQUEST_ID.encode("utf-8")).hexdigest() + ".json"
NEW_PHYSICAL_D2_MARKER_NAME_SHA256 = hashlib.sha256(NEW_PHYSICAL_D2_MARKER_NAME.encode("utf-8")).hexdigest()

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

FALSE_BOUNDARY = {
    "authorized": False,
    "authorization_created": False,
    "authorization_claimed": False,
    "authorization_consumed": False,
    "board_operation": False,
    "usb_enumeration": False,
    "serial_operation": False,
    "esptool_operation": False,
    "flash_operation": False,
    "physical_nvs_operation": False,
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
    "private_values_included": False,
    "private_paths_included": False,
    "secret_values_included": False,
}


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def source_contract(source_sha: str) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR193")
    return {
        "schema": SCHEMA,
        "state": "MAIN_DRIFT_SUCCESSOR_REBIND_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "previous_accepted_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": MAIN_DRIFT_COMMIT_SHA,
        "main_drift_changed_files": list(MAIN_DRIFT_CHANGED_FILES),
        "main_drift_commit_count": MAIN_DRIFT_COMMIT_COUNT,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "h2_authorization_id": H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_automatic_retry_permitted": False,
        "h2_result_sha256": H2_RESULT_CANONICAL_SHA256,
        "old_request_id": OLD_PHYSICAL_D2_REQUEST_ID,
        "old_request_state": OLD_PHYSICAL_D2_REQUEST_STATE,
        "old_request_binding_sha256": OLD_REQUEST_BINDING_SHA256,
        "old_request_reuse_permitted": False,
        "future_host_rebind_authorization_id": FUTURE_HOST_REBIND_AUTHORIZATION_ID,
        "future_physical_d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
        "next_gate": "EXACT_HOST_ONLY_MAIN_DRIFT_REBIND_AUTHORIZATION",
        **FALSE_BOUNDARY,
    }


def stale_request_disposition() -> dict[str, object]:
    return {
        "schema": STALE_SCHEMA,
        "state": OLD_PHYSICAL_D2_REQUEST_STATE,
        "reason": "MAIN_SHA_DRIFT",
        "d2_request_id": OLD_PHYSICAL_D2_REQUEST_ID,
        "request_raw_sha256": OLD_REQUEST_RAW_SHA256,
        "request_binding_sha256": OLD_REQUEST_BINDING_SHA256,
        "bound_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "observed_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "request_reuse_permitted": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "physical_execution_occurred": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }


def validate_h2_result(value: Mapping[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-result/1", "H2_RESULT_SCHEMA_MISMATCH")
    exact = {
        "authorization_id": H2_AUTHORIZATION_ID,
        "status": "CONSUMED_PASS",
        "authorization_consumed": True,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "source_sha": BASE_HEAD_SHA,
        "accepted_current_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "review_archive_sha256": UPSTREAM_REVIEW_ARCHIVE_SHA256,
        "execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "execution_wrapper_sha256": UPSTREAM_EXECUTION_WRAPPER_SHA256,
        "execution_launcher_sha256": UPSTREAM_EXECUTION_LAUNCHER_SHA256,
        "repaired_host_controller_sha256": UPSTREAM_REPAIRED_HOST_CONTROLLER_SHA256,
        "preflight_result_sha256": H2_RESULT_CANONICAL_SHA256,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "H2_RESULT_" + key.upper() + "_MISMATCH")
    for key in (
        "board_operation", "usb_enumeration", "serial_operation", "esptool_operation",
        "flash_operation", "physical_nvs_operation", "network_operation", "broker_started",
        "prepare_executed", "verify_executed", "activate_executed", "cleanup_executed",
        "ready", "merge", "release", "tag", "deployment", "private_values_included",
        "private_paths_included", "secret_values_included",
    ):
        require(value.get(key) is False, "H2_RESULT_BOUNDARY_" + key.upper())
    without = dict(value)
    observed = without.pop("preflight_result_sha256", None)
    require(observed == canonical_json_sha256(without), "H2_RESULT_CANONICAL_DIGEST_MISMATCH")
    return dict(value)


def validate_old_request(value: Mapping[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-request/1", "OLD_REQUEST_SCHEMA_MISMATCH")
    exact = {
        "d2_request_id": OLD_PHYSICAL_D2_REQUEST_ID,
        "source_sha": BASE_HEAD_SHA,
        "host_final_preflight_source_sha": BASE_HEAD_SHA,
        "main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "host_preflight_result_sha256": H2_RESULT_CANONICAL_SHA256,
        "review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "execution_wrapper_sha256": UPSTREAM_EXECUTION_WRAPPER_SHA256,
        "execution_launcher_sha256": UPSTREAM_EXECUTION_LAUNCHER_SHA256,
        "request_binding_sha256": OLD_REQUEST_BINDING_SHA256,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "OLD_REQUEST_" + key.upper() + "_MISMATCH")
    for key in (
        "board_operation", "usb_enumeration", "serial_operation", "esptool_operation",
        "flash_operation", "physical_nvs_operation", "network_operation", "broker_started",
        "prepare_executed", "verify_executed", "activate_executed", "cleanup_executed",
        "ready", "merge", "release", "tag", "deployment", "private_values_included",
        "private_paths_included", "secret_values_included",
    ):
        require(value.get(key) is False, "OLD_REQUEST_BOUNDARY_" + key.upper())
    without = dict(value)
    observed = without.pop("request_binding_sha256", None)
    require(observed == canonical_json_sha256(without), "OLD_REQUEST_CANONICAL_DIGEST_MISMATCH")
    return dict(value)


def build_request_draft(
    *,
    source_sha: str,
    review_binding_sha256: str,
    execution_package_sha256: str,
    execution_wrapper_sha256: str,
    execution_launcher_sha256: str,
) -> dict[str, Any]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    for name, value in {
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
    }.items():
        validate_sha256(value, name.upper() + "_INVALID")
    return {
        "schema": REQUEST_SCHEMA,
        "state": "AWAITING_EXACT_HOST_MAIN_DRIFT_REBIND_AND_PHYSICAL_D2_DECISION",
        "stage": STAGE,
        "d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "main_drift_rebind_source_sha": source_sha,
        "physical_execution_source_sha": BASE_HEAD_SHA,
        "host_final_preflight_source_sha": BASE_HEAD_SHA,
        "previous_request_id": OLD_PHYSICAL_D2_REQUEST_ID,
        "previous_request_state": OLD_PHYSICAL_D2_REQUEST_STATE,
        "previous_request_binding_sha256": OLD_REQUEST_BINDING_SHA256,
        "previous_request_reuse_permitted": False,
        "previous_accepted_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": MAIN_DRIFT_COMMIT_SHA,
        "h2_authorization_id": H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_result_sha256": H2_RESULT_CANONICAL_SHA256,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_script_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "host_rebind_result_sha256": None,
        "request_issued_at": None,
        "request_expires_at": None,
        "request_binding_sha256": None,
        "locked_recovery_authorized": False,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_max_count": 1,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "production_operation_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        **FALSE_BOUNDARY,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }


def finalize_request(
    draft: Mapping[str, Any],
    *,
    host_rebind_result_sha256: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    validate_sha256(host_rebind_result_sha256, "HOST_REBIND_RESULT_SHA256_INVALID")
    issued = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    require(issued.tzinfo is not None and expires.tzinfo is not None, "REQUEST_WINDOW_TZ_INVALID")
    require(0 < (expires - issued).total_seconds() <= 7200, "REQUEST_WINDOW_INVALID")
    value = deepcopy(dict(draft))
    require(value.get("request_binding_sha256") is None, "REQUEST_ALREADY_FINALIZED")
    value["state"] = "MAIN_DRIFT_REBOUND_HOST_RECHECK_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION"
    value["host_rebind_result_sha256"] = host_rebind_result_sha256
    value["request_issued_at"] = issued.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    value["request_expires_at"] = expires.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    value["request_binding_sha256"] = canonical_json_sha256(value)
    return value



def build_rebound_request_from_old(
    old_request: Mapping[str, Any],
    *,
    source_sha: str,
    review_binding_sha256: str,
    execution_package_sha256: str,
    execution_wrapper_sha256: str,
    execution_launcher_sha256: str,
    host_rebind_result_sha256: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    validated = validate_old_request(old_request)
    for name, value in {
        "source_sha": source_sha,
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "host_rebind_result_sha256": host_rebind_result_sha256,
    }.items():
        (validate_sha40 if name == "source_sha" else validate_sha256)(value, name.upper() + "_INVALID")
    issued = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    require(issued.tzinfo is not None and expires.tzinfo is not None, "REQUEST_WINDOW_TZ_INVALID")
    require(0 < (expires - issued).total_seconds() <= 7200, "REQUEST_WINDOW_INVALID")
    value = deepcopy(validated)
    value.pop("request_binding_sha256", None)
    value.update({
        "schema": REQUEST_SCHEMA,
        "state": "MAIN_DRIFT_REBOUND_HOST_RECHECK_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION",
        "stage": STAGE,
        "d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "main_drift_rebind_source_sha": source_sha,
        "physical_execution_source_sha": source_sha,
        "upstream_host_final_preflight_source_sha": BASE_HEAD_SHA,
        "previous_request_id": OLD_PHYSICAL_D2_REQUEST_ID,
        "previous_request_state": OLD_PHYSICAL_D2_REQUEST_STATE,
        "previous_request_raw_sha256": OLD_REQUEST_RAW_SHA256,
        "previous_request_binding_sha256": OLD_REQUEST_BINDING_SHA256,
        "previous_request_reuse_permitted": False,
        "previous_accepted_main_sha": PREVIOUS_ACCEPTED_MAIN_SHA,
        "main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": MAIN_DRIFT_COMMIT_SHA,
        "main_drift_changed_files": list(MAIN_DRIFT_CHANGED_FILES),
        "h2_authorization_id": H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_automatic_retry_permitted": False,
        "h2_result_raw_sha256": H2_RESULT_RAW_SHA256,
        "h2_result_sha256": H2_RESULT_CANONICAL_SHA256,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_script_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "execution_marker_name_sha256": NEW_PHYSICAL_D2_MARKER_NAME_SHA256,
        "host_rebind_result_sha256": host_rebind_result_sha256,
        "request_issued_at": issued.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_expires_at": expires.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "locked_recovery_authorized": False,
        "production_operation_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    })
    for key, expected in FALSE_BOUNDARY.items():
        value[key] = expected
    value["request_binding_sha256"] = canonical_json_sha256(value)
    return value

def _main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
