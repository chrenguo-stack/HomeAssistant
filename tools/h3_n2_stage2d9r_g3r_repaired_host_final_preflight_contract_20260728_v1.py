#!/usr/bin/env python3
"""Pure public contract for repaired Stage2D9R host-only final preflight.

This module does not access private custody, USB, serial, esptool, Flash/NVS,
network, Broker, or device commands. It only freezes public bindings and builds
an unauthorized physical-D2 request template.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-contract/1"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-physical-d2-request/1"
STAGE = "H3/N2 Stage 2D-9R G3R repaired successor"
CHAIN_DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-REPAIRED-SUCCESSOR-CHAIN-20260728-01"
MAIN_CORRECTION_DECISION_ID = "MAIN-ZERO-NET-CORRECTION-ACCEPTANCE-20260728-01"
FUTURE_HOST_AUTHORIZATION_ID = (
    "H2-H3N2-STAGE2D9R-G3R-REPAIRED-HOST-FINAL-PREFLIGHT-20260728-01"
)
PHYSICAL_D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01"
)
PHYSICAL_D2_MARKER_NAME = (
    hashlib.sha256(PHYSICAL_D2_REQUEST_ID.encode("utf-8")).hexdigest() + ".json"
)
PHYSICAL_D2_MARKER_NAME_SHA256 = hashlib.sha256(
    PHYSICAL_D2_MARKER_NAME.encode("utf-8")
).hexdigest()

BASE_PR = 188
BASE_HEAD_SHA = "8a6fdd7c74341448d275a4412e36b303d7c95e85"
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-repaired-immutable-recovery-freeze-20260728-v1"
BASELINE_ORIGINAL_MAIN_SHA = "c16da1a2d4d8300198b0603359eea349a034e2ea"
ACCEPTED_CURRENT_MAIN_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"
ACCIDENTAL_COMMIT_SHA = "61f8db5696c726137952b98825040c4f3a8efd5c"
CORRECTION_COMMIT_SHA = "0229002cc5037f83bc77426f439bdb9e6d63318c"

IMMUTABLE_ARTIFACT_ID = 8676269782
IMMUTABLE_ARTIFACT_SHA256 = (
    "83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8"
)
IMMUTABLE_PAYLOAD_SHA256 = (
    "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
)
IMMUTABLE_MERGED_IMAGE_SHA256 = (
    "67dc276c7ef69a1528d511c4043ec3eb58489eefb6864442f03e405f24611cb3"
)
IMMUTABLE_PARTITION_TABLE_SHA256 = (
    "b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268"
)
RECOVERY_PAYLOAD_SHA256 = (
    "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
)
RECOVERY_DESCRIPTOR_SHA256 = (
    "660b5419b65b2a417989ca8808bc434a4f83703fa90a72b4f306360879abbbd0"
)
FINAL_EXECUTION_BINDING = "387602804793c7ab110817d56aa4c26114632bde"
FINAL_EXECUTION_BINDING_SHA256 = (
    "387602804793c7ab110817d56aa4c26114632bde31050e95847833f98d83b6c1"
)

BASELINE_AUTHORIZATION_ID = (
    "D2-H3N2-STAGE2D9R-G3R-REPAIRED-BASELINE-READONLY-20260728-01"
)
BASELINE_PUBLIC_ARCHIVE_SHA256 = (
    "15849f8a42f0cfa4aa594512dc0928a8ac5e4e3479dc51dfa59390d28c67e0f9"
)
BASELINE_PUBLIC_ACCEPTANCE_SHA256 = (
    "aaa39a47cab327be8c2a06d466267185b3878ced5635b9c7706cfa58846ff8b2"
)
BASELINE_RESULT_SHA256 = (
    "f3522e98d5c0c8fdf4f5fa2b8486e6c782c7262ae4321e9525471bc0f12cacf4"
)
BOARD_IDENTITY_SHA256 = (
    "2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
)
SERIAL_IDENTITY_SHA256 = (
    "b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
)
BASELINE_STATE_SHA256 = (
    "0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
)
ERASED_PARTITION_SHA256 = (
    "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
)
TEST_PARTITION_ADDRESS = 0x400000
TEST_PARTITION_SIZE = 0x10000

PRIVATE_PACKAGE_SHA256 = (
    "d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f"
)
PUBLIC_DESCRIPTOR_SHA256 = (
    "4c72e3cd57cd16f0ed48793f7f1e106c6d56a6795324abaa09b9451eb843413e"
)
PRIVATE_DESCRIPTOR_SHA256 = (
    "5f5a039c8b14d5e533ade99fbb6594fbf2c640ccdcfc13bbc47d9277b653886c"
)
PREPARE_COMMAND_SHA256 = (
    "022577c2ee88c57ab45533f53a5630f7eb94e142985533cdc1a8166de0d3317f"
)
VERIFY_COMMAND_SHA256 = (
    "9d5aad5eb2eedd6ba8460df80af3653dc68c8e24cd12a6bcd69e5460436050d7"
)
CANDIDATE_DIGEST_SHA256 = (
    "73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15"
)
CA_PEM_SHA256 = (
    "e9abe88df80f21311ea9ea4977b78f531380a37564490c1108fabeae8cc5bc5a"
)
UNLOCK_DIGEST_SHA256 = (
    "f1fe3ccbda78f069e6cf1e47ee4c3340878372f42fc24a21126884eb0c22df98"
)
BROKER_CERTIFICATE_DER_SHA256 = (
    "19b599fdce443bf1ab59fac1c58b4da08d024c655502b4fda087151485ecce3c"
)
BROKER_SPKI_SHA256 = (
    "a3ff45e66c18953bccb2d558e4a002208eadcf5fff9a8c05f6b77512c07a953b"
)
BUILD_BINDING = "4051f5d541898cef742f35aeec757e7fc479f383"
RUN_SUFFIX = "tlsvalid03"

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
    "replay_permitted": False,
    "automatic_retry_permitted": False,
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
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR188")
    return {
        "schema": SCHEMA,
        "state": "HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "chain_decision_id": CHAIN_DECISION_ID,
        "main_correction_decision_id": MAIN_CORRECTION_DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "baseline_original_main_sha": BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "main_tree_zero_net_change": True,
        "accidental_commit_sha": ACCIDENTAL_COMMIT_SHA,
        "correction_commit_sha": CORRECTION_COMMIT_SHA,
        "baseline_authorization_id": BASELINE_AUTHORIZATION_ID,
        "baseline_status": "CONSUMED_PASS",
        "baseline_replay_permitted": False,
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "next_gate": "HOST_ONLY_FINAL_PREFLIGHT",
        "future_physical_gate": "PHYSICAL_D2",
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
        "execution_script_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "execution_marker_name_sha256": PHYSICAL_D2_MARKER_NAME_SHA256,
        "repaired_host_controller_sha256": repaired_host_controller_sha256,
    }.items():
        validate_sha256(value, name.upper() + "_INVALID")
    return {
        "schema": REQUEST_SCHEMA,
        "state": "AWAITING_HOST_FINAL_PREFLIGHT_AND_EXACT_OPERATOR_DECISION",
        "stage": STAGE,
        "d2_request_id": PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "immutable_source_sha": BASE_HEAD_SHA,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "baseline_original_main_sha": BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": ACCEPTED_CURRENT_MAIN_SHA,
        "main_tree_zero_net_change": True,
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_SHA256,
        "immutable_merged_image_sha256": IMMUTABLE_MERGED_IMAGE_SHA256,
        "immutable_partition_table_sha256": IMMUTABLE_PARTITION_TABLE_SHA256,
        "recovery_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": IMMUTABLE_ARTIFACT_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_SHA256,
        "recovery_descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "baseline_authorization_id": BASELINE_AUTHORIZATION_ID,
        "baseline_public_archive_sha256": BASELINE_PUBLIC_ARCHIVE_SHA256,
        "baseline_public_acceptance_sha256": BASELINE_PUBLIC_ACCEPTANCE_SHA256,
        "baseline_result_sha256": BASELINE_RESULT_SHA256,
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "baseline_state_sha256": BASELINE_STATE_SHA256,
        "test_partition_sha256": ERASED_PARTITION_SHA256,
        "test_partition_size": TEST_PARTITION_SIZE,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "private_descriptor_sha256": PRIVATE_DESCRIPTOR_SHA256,
        "prepare_command_sha256": PREPARE_COMMAND_SHA256,
        "verify_command_sha256": VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "unlock_digest_sha256": UNLOCK_DIGEST_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
        "build_binding": BUILD_BINDING,
        "run_suffix": RUN_SUFFIX,
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
    required = (
        "python_executable_sha256",
        "openssl_executable_sha256",
        "esptool_executable_sha256",
        "esptool_module_sha256",
        "pyserial_module_sha256",
        "mosquitto_executable_sha256",
    )
    result = dict(template)
    result["state"] = "HOST_FINAL_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION"
    result["host_preflight_result_sha256"] = host_preflight_result_sha256
    for key in required:
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
