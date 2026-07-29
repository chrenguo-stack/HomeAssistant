#!/usr/bin/env python3
"""Contract builders for corrected-baseline physical execution overlay."""
from h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_common_20260729_v1 import *
from h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_base_20260729_v1 import *

def build_physical_request(*, source_sha: str, review_binding_sha256: str,
                           package_root: Path, execution_package_sha256: str | None = None) -> dict[str, Any]:
    overlay = validate_execution_overlay(package_root)
    binding = overlay["binding"]
    manifest = overlay["manifest"]
    source_sha = validate_sha40(source_sha, "REQUEST_SOURCE_SHA_INVALID")
    validate_sha256(review_binding_sha256, "REQUEST_REVIEW_BINDING_INVALID")
    package_sha = execution_package_sha256 or canonical_package_digest(package_root)
    validate_sha256(package_sha, "REQUEST_PACKAGE_SHA_INVALID")
    provisional: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_06_ID,
        "state": "CORRECTED_BASELINE_OVERLAY_BOUND_PHYSICAL_D2_REQUEST_AWAITING_EXACT_AUTHORIZATION",
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_request_authorized": False,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "source_sha": source_sha,
        "review_binding_sha256": review_binding_sha256,
        "execution_overlay_sha256": manifest["execution_overlay_sha256"],
        "execution_overlay_role": "BLOCKING_CORRECTED_BASELINE",
        "execution_overlay_policy_version": 1,
        "execution_package_sha256": package_sha,
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "authorization_schema": AUTH_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "marker_schema": MARKER_SCHEMA,
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "corrected_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "chip_id_output_sha256": CHIP_ID_OUTPUT_SHA256,
        "flash_id_output_sha256": FLASH_ID_OUTPUT_SHA256,
        "test_partition_sha256": TEST_PARTITION_SHA256,
        "test_partition_size": TEST_PARTITION_SIZE,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "invalid_legacy_baseline_state": "INVALID_DERIVED_AGGREGATE_DIGEST_PERMANENTLY_REJECTED",
        "invalid_legacy_baseline_reuse_permitted": False,
        "h5_authorization_id": H5_AUTHORIZATION_ID,
        "h5_authorization_record_sha256": H5_AUTHORIZATION_RECORD_SHA256,
        "h5_result_sha256": H5_RESULT_SHA256,
        "h5_state": "CONSUMED_PASS",
        "predecessor_03_request_id": PREDECESSOR_03_ID,
        "predecessor_03_state": PREDECESSOR_03_STATE,
        "predecessor_03_failure_code": PREDECESSOR_03_FAILURE,
        "predecessor_03_replay_permitted": False,
        "predecessor_04_request_id": PREDECESSOR_04_ID,
        "predecessor_04_state": PREDECESSOR_04_STATE,
        "predecessor_04_reuse_permitted": False,
        "predecessor_05_request_id": REQUEST_05_ID,
        "predecessor_05_state": REQUEST_05_INVALID_STATE,
        "predecessor_05_request_binding_sha256": REQUEST_05_BINDING_SHA256,
        "predecessor_05_reuse_permitted": False,
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "upstream_execution_closure_sha256": UPSTREAM_EXECUTION_CLOSURE_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_operation_sequence": ["READ_TEST_PARTITION", "ERASE_TEST_PARTITION_REGION", "READ_TEST_PARTITION"],
        "recovery_write_flash_permitted": False,
        "whole_chip_recovery_erase_permitted": False,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        **FALSE_BOUNDARY,
    }
    provisional["physical_request_authorized"] = False
    provisional["request_binding_sha256"] = canonical_json_sha256(provisional)
    return provisional


def validate_physical_request(value: Mapping[str, Any], package_root: Path) -> dict[str, Any]:
    actual = dict(value)
    binding = actual.pop("request_binding_sha256", None)
    require(binding == canonical_json_sha256(actual), "PHYSICAL_REQUEST_BINDING_MISMATCH")
    actual["request_binding_sha256"] = binding
    overlay = validate_execution_overlay(package_root)
    expected = build_physical_request(
        source_sha=overlay["binding"]["source_sha"],
        review_binding_sha256=actual.get("review_binding_sha256"),
        package_root=package_root,
    )
    require(actual == expected, "PHYSICAL_REQUEST_CONTENT_MISMATCH")
    return actual


def authorization_contract_required(request: Mapping[str, Any], package_root: Path) -> dict[str, Any]:
    overlay = validate_execution_overlay(package_root)
    return {
        "schema": AUTH_SCHEMA,
        "stage": STAGE,
        "d2_request_id": REQUEST_06_ID,
        "request_binding_sha256": request["request_binding_sha256"],
        "execution_package_sha256": request["execution_package_sha256"],
        "execution_wrapper_sha256": request["execution_wrapper_sha256"],
        "execution_launcher_sha256": request["execution_launcher_sha256"],
        "execution_overlay_sha256": overlay["manifest"]["execution_overlay_sha256"],
        "execution_overlay_role": "BLOCKING_CORRECTED_BASELINE",
        "execution_overlay_policy_version": 1,
        "source_sha": request["source_sha"],
        "review_binding_sha256": request["review_binding_sha256"],
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "invalid_legacy_baseline_reuse_permitted": False,
        "h5_authorization_record_sha256": H5_AUTHORIZATION_RECORD_SHA256,
        "h5_result_sha256": H5_RESULT_SHA256,
        "predecessor_03_state": PREDECESSOR_03_STATE,
        "predecessor_03_failure_code": PREDECESSOR_03_FAILURE,
        "predecessor_04_state": PREDECESSOR_04_STATE,
        "predecessor_05_state": REQUEST_05_INVALID_STATE,
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
    }


def validate_authorization_contract(value: Mapping[str, Any], request: Mapping[str, Any],
                                    package_root: Path, now: datetime | None = None) -> dict[str, Any]:
    request_value = validate_physical_request(request, package_root)
    actual = dict(value)
    observed = actual.pop("authorization_record_sha256", None)
    require(observed == canonical_json_sha256(actual), "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    actual["authorization_record_sha256"] = observed
    for key, expected in authorization_contract_required(request_value, package_root).items():
        require(actual.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    require(actual.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(actual.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(actual.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_EXPANDED")
    require(actual.get("automatic_retry_permitted") is False, "AUTHORIZATION_RETRY_EXPANDED")
    issued = utc(actual.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = utc(actual.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require((expires - issued).total_seconds() <= 7200, "AUTHORIZATION_WINDOW_EXCEEDS_MAXIMUM")
    require(actual.get("locked_recovery_authorized") is True, "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED")
    require(actual.get("locked_recovery_max_count") == 1, "AUTHORIZATION_LOCKED_RECOVERY_COUNT_INVALID")
    require(actual.get("prepare_max_count") == 1 and actual.get("verify_max_count") == 1, "AUTHORIZATION_COMMAND_COUNT_INVALID")
    require(actual.get("activate_authorized") is False and actual.get("cleanup_authorized") is False, "AUTHORIZATION_PRODUCTION_BOUNDARY_EXPANDED")
    require(actual.get("production_operation_authorized") is False, "AUTHORIZATION_PRODUCTION_BOUNDARY_EXPANDED")
    return actual


def source_contract(source_sha: str) -> dict[str, Any]:
    return {
        "schema": REVIEW_SCHEMA,
        "state": "PHYSICAL_EXECUTION_OVERLAY_BINDING_REPAIR_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": validate_sha40(source_sha, "SOURCE_SHA_INVALID"),
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "request_05_state": REQUEST_05_INVALID_STATE,
        "future_physical_request_id": REQUEST_06_ID,
        "corrected_baseline_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_baseline_sha256": INVALID_BASELINE_SHA256,
        "immutable_payload_changed": False,
        "recovery_payload_changed": False,
        "physical_request_created": False,
        "physical_request_authorized": False,
        **FALSE_BOUNDARY,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
