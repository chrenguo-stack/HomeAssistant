#!/usr/bin/env python3
"""Public contract for the payload-handoff repaired host-final preflight.

This module is source-only and inert. It freezes the repaired execution package,
the exact host-only preflight gate and an unauthorized future physical-D2 request.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1 as frozen

SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-contract/1"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-request/1"
STAGE = "H3/N2 Stage 2D-9R G3R payload-handoff repaired successor"
DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-HOST-FINAL-PREFLIGHT-20260728-01"
)
FUTURE_HOST_AUTHORIZATION_ID = (
    "H2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-HOST-FINAL-PREFLIGHT-20260728-01"
)
PHYSICAL_D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-02"
)
PHYSICAL_D2_MARKER_NAME = hashlib.sha256(
    PHYSICAL_D2_REQUEST_ID.encode("utf-8")
).hexdigest() + ".json"
PHYSICAL_D2_MARKER_NAME_SHA256 = hashlib.sha256(
    PHYSICAL_D2_MARKER_NAME.encode("utf-8")
).hexdigest()

BASE_PR = 190
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-physical-payload-handoff-repair-20260728-v1"
BASE_HEAD_SHA = "261f24dc7e01fe9eaaf0a607a2868cd4411286bf"
ACCEPTED_CURRENT_MAIN_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"

PAYLOAD_REPAIR_ARTIFACT_ID = 8682468219
PAYLOAD_REPAIR_ARTIFACT_SHA256 = (
    "418827f2d0f931ee459c1b2204c8396dd71b98d5731dd7c072fb9abaf3d2caa4"
)
PAYLOAD_REPAIR_REVIEW_BINDING_SHA256 = (
    "8f1e865d2bd43050e496a510509c31c5b19df1715e27f2f3adea444f03938908"
)
PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256 = (
    "d1e291f81602f8b9b538de00abc1ba93b1bf57b43e259a01c5049533e3e3db00"
)
PAYLOAD_REPAIR_WRAPPER_SHA256 = (
    "862597b51b137ee9ae3ef675f66ff578937036f35b06d6a47c8981a6d05fbc62"
)
PAYLOAD_REPAIR_LAUNCHER_SHA256 = (
    "a53465d8dd4b7a25015eceb7229b69bc32dfc3eb5f1c5685f69f8f198815224f"
)
PAYLOAD_HANDOFF_CONTRACT = "ORIGINAL_TAR_AND_EMPTY_EXTRACTION_ROOTS_SEPARATE"
PRECLAIM_FAILURE_CONTRACT = "AUTHORIZATION_CREATED_CONSUMED_FAILED_NO_REPLAY"

OLD_PHYSICAL_D2_ID = "D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01"
OLD_PHYSICAL_D2_STATUS = "CONSUMED_FAILED"
OLD_PHYSICAL_D2_FAILURE = "IMMUTABLE_PAYLOAD_INVALID"
OLD_PHYSICAL_D2_REPLAY_PERMITTED = False

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

FALSE_BOUNDARY = dict(frozen.FALSE_BOUNDARY)


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def source_contract(source_sha: str) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR190")
    return {
        "schema": SCHEMA,
        "state": "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "payload_repair_artifact_id": PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "payload_repair_review_binding_sha256": PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "payload_repair_execution_package_sha256": PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "payload_handoff_contract": PAYLOAD_HANDOFF_CONTRACT,
        "preclaim_failure_contract": PRECLAIM_FAILURE_CONTRACT,
        "old_physical_d2_id": OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": OLD_PHYSICAL_D2_REPLAY_PERMITTED,
        "next_gate": "EXACT_HOST_ONLY_FINAL_PREFLIGHT_AUTHORIZATION",
        "future_physical_gate": "NEW_EXACT_PHYSICAL_D2",
        **FALSE_BOUNDARY,
    }


def build_request_template(
    *,
    source_sha: str,
    review_binding_sha256: str,
    execution_package_sha256: str,
    execution_wrapper_sha256: str,
    execution_launcher_sha256: str,
    repaired_host_controller_sha256: str,
) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    for name, value in {
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "repaired_host_controller_sha256": repaired_host_controller_sha256,
    }.items():
        validate_sha256(value, name.upper() + "_INVALID")
    return {
        "schema": REQUEST_SCHEMA,
        "state": "AWAITING_PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_AND_EXACT_OPERATOR_DECISION",
        "stage": STAGE,
        "d2_request_id": PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "payload_handoff_repair_source_sha": BASE_HEAD_SHA,
        "payload_handoff_base_pr": BASE_PR,
        "payload_handoff_base_head_sha": BASE_HEAD_SHA,
        "main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "payload_repair_artifact_id": PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "payload_repair_review_binding_sha256": PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "payload_repair_execution_package_sha256": PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "payload_repair_wrapper_sha256": PAYLOAD_REPAIR_WRAPPER_SHA256,
        "payload_repair_launcher_sha256": PAYLOAD_REPAIR_LAUNCHER_SHA256,
        "payload_handoff_contract": PAYLOAD_HANDOFF_CONTRACT,
        "preclaim_failure_contract": PRECLAIM_FAILURE_CONTRACT,
        "old_physical_d2_id": OLD_PHYSICAL_D2_ID,
        "old_physical_d2_status": OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": OLD_PHYSICAL_D2_REPLAY_PERMITTED,
        # Frozen immutable, baseline, custody and command bindings remain unchanged.
        "immutable_source_sha": frozen.BASE_HEAD_SHA,
        "base_pr": frozen.BASE_PR,
        "base_head_sha": frozen.BASE_HEAD_SHA,
        "baseline_original_main_sha": frozen.BASELINE_ORIGINAL_MAIN_SHA,
        "immutable_artifact_id": frozen.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": frozen.IMMUTABLE_ARTIFACT_SHA256,
        "immutable_payload_tar_sha256": frozen.IMMUTABLE_PAYLOAD_SHA256,
        "immutable_merged_image_sha256": frozen.IMMUTABLE_MERGED_IMAGE_SHA256,
        "immutable_partition_table_sha256": frozen.IMMUTABLE_PARTITION_TABLE_SHA256,
        "recovery_artifact_id": frozen.IMMUTABLE_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": frozen.IMMUTABLE_ARTIFACT_SHA256,
        "recovery_payload_tar_sha256": frozen.RECOVERY_PAYLOAD_SHA256,
        "recovery_descriptor_sha256": frozen.RECOVERY_DESCRIPTOR_SHA256,
        "final_execution_binding": frozen.FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": frozen.FINAL_EXECUTION_BINDING_SHA256,
        "baseline_authorization_id": frozen.BASELINE_AUTHORIZATION_ID,
        "baseline_public_archive_sha256": frozen.BASELINE_PUBLIC_ARCHIVE_SHA256,
        "baseline_public_acceptance_sha256": frozen.BASELINE_PUBLIC_ACCEPTANCE_SHA256,
        "baseline_result_sha256": frozen.BASELINE_RESULT_SHA256,
        "board_identity_sha256": frozen.BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": frozen.SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": frozen.BASELINE_STATE_SHA256,
        "test_partition_sha256": frozen.ERASED_PARTITION_SHA256,
        "test_partition_size": frozen.TEST_PARTITION_SIZE,
        "private_package_sha256": frozen.PRIVATE_PACKAGE_SHA256,
        "public_descriptor_sha256": frozen.PUBLIC_DESCRIPTOR_SHA256,
        "private_descriptor_sha256": frozen.PRIVATE_DESCRIPTOR_SHA256,
        "prepare_command_sha256": frozen.PREPARE_COMMAND_SHA256,
        "verify_command_sha256": frozen.VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": frozen.CANDIDATE_DIGEST_SHA256,
        "unlock_digest_sha256": frozen.UNLOCK_DIGEST_SHA256,
        "ca_pem_sha256": frozen.CA_PEM_SHA256,
        "build_binding": frozen.BUILD_BINDING,
        "run_suffix": frozen.RUN_SUFFIX,
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_script_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "execution_marker_name_sha256": PHYSICAL_D2_MARKER_NAME_SHA256,
        "repaired_host_controller_sha256": repaired_host_controller_sha256,
        "host_preflight_result_sha256": None,
        "python_executable_sha256": None,
        "openssl_executable_sha256": None,
        "esptool_executable_sha256": None,
        "esptool_module_sha256": None,
        "pyserial_module_sha256": None,
        "mosquitto_executable_sha256": None,
        "request_issued_at": None,
        "request_expires_at": None,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
        **FALSE_BOUNDARY,
    }


def finalize_request(
    template: Mapping[str, object],
    *,
    host_preflight_result_sha256: str,
    toolchain: Mapping[str, str],
    issued_at: str,
    expires_at: str,
) -> dict[str, object]:
    require(template.get("schema") == REQUEST_SCHEMA, "REQUEST_SCHEMA_MISMATCH")
    validate_sha256(host_preflight_result_sha256, "HOST_PREFLIGHT_RESULT_INVALID")
    result = dict(template)
    result["state"] = (
        "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION"
    )
    result["host_preflight_result_sha256"] = host_preflight_result_sha256
    for key in (
        "python_executable_sha256",
        "openssl_executable_sha256",
        "esptool_executable_sha256",
        "esptool_module_sha256",
        "pyserial_module_sha256",
        "mosquitto_executable_sha256",
    ):
        result[key] = validate_sha256(toolchain.get(key), key.upper() + "_INVALID")
    require(isinstance(issued_at, str) and issued_at.endswith("Z"), "ISSUED_AT_INVALID")
    require(isinstance(expires_at, str) and expires_at.endswith("Z"), "EXPIRES_AT_INVALID")
    result["request_issued_at"] = issued_at
    result["request_expires_at"] = expires_at
    result["request_binding_sha256"] = canonical_json_sha256(result)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
