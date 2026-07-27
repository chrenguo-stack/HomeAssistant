#!/usr/bin/env python3
"""Public-only contract, state machine and failure matrix for successor D2.

This module cannot claim authorization or perform execution. It contains no
board, serial, network, Broker, Flash, NVS, PREPARE, VERIFY, ACTIVATE or CLEANUP
implementation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

STAGE = "H3/N2 Stage 2D-9R G3R successor"
REPOSITORY = "chrenguo-stack/HomeAssistant"
BRANCH = "fix/h3-n2-stage2d9r-g3r-private-execution-material-20260725-v1"
PULL_REQUEST = 180
BASE_PULL_REQUEST = 176
BASE_SOURCE_SHA = "cf841f3e5a8cf04c5df9875c499b91ad4e4289cb"
EXPECTED_MAIN_SHA = "43aa37b0cc343efdd2024f369517e55c5b6461f1"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01"
U1_02_ID = "U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-02"
MAX_AUTHORIZATION_SECONDS = 7200
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

PUBLIC_BINDINGS = {
    "u1_02_authorization_record_sha256": "88314a56bc5d7dd3e175278e2b01409cde611562f1bea11690adb9ff3f71f348",
    "u1_02_result_sha256": "9ad24d630640ab485e055e7cb8f08c1320f19b6ca37d43e36303ce44d62d0b08",
    "immutable_artifact_id": 8638796771,
    "immutable_artifact_source_sha": "ac1d2a7a92323988c9cd946a3e018e4f1ba9463b",
    "immutable_artifact_archive_sha256": "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8",
    "immutable_payload_tar_sha256": "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747",
    "immutable_application_sha256": "a75e440c90aa5f050ac55086d1f1c614f113a7b66bd31ffc748fee95b9d26e1b",
    "immutable_merged_image_sha256": "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf",
    "immutable_build_binding": "742f663333837366a42da92b984a3b05c643f571",
    "custody_root_digest_sha256": "b608f7fbb669ffeb1ae20699a0c556feb41bebd6813cbc07fc98f5845e00879d",
    "private_descriptor_sha256": "49236148741cccac301bbe45c900912e472e72ab8da8cb894645fb3916852fc8",
    "public_descriptor_sha256": "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6",
    "private_package_sha256": "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb",
    "candidate_digest_sha256": "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2",
    "ca_pem_sha256": "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096",
    "broker_certificate_der_sha256": "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9",
    "broker_spki_sha256": "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e",
    "unlock_digest_sha256": "727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9",
    "persistence_key_file_sha256": "661a5cf28173d481ddb8bc4e239fb5aced6e67ec574a79c774f238dbb4d0b882",
    "prepare_command_sha256": "294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f",
    "verify_command_sha256": "53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347",
    "python_executable_sha256": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
    "openssl_executable_sha256": "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
}

STATES = (
    "D2_REVIEWED",
    "D2_AUTHORIZED",
    "AUTHORIZATION_CLAIMED",
    "BOARD_BOUND",
    "BASELINE_VERIFIED",
    "FLASH_ERASED",
    "FLASH_WRITTEN_AND_VERIFIED",
    "AUTO_RESET_COMPLETED",
    "ISOLATED_BROKER_STARTED",
    "PREPARE_EXECUTED_ONCE",
    "AUTO_RESTART_OBSERVED",
    "VERIFY_EXECUTED_ONCE",
    "PREPARED_VERIFIED",
    "ISOLATED_BROKER_STOPPED",
    "CONSUMED_PASS",
    "INVALIDATED_BEFORE_CLAIM",
    "LOCKED_RECOVERY_ENTERED",
    "LOCKED_RECOVERY_COMPLETED",
    "CONSUMED_FAILED",
)

ALLOWED_TRANSITIONS = {
    "D2_REVIEWED": ("D2_AUTHORIZED", "INVALIDATED_BEFORE_CLAIM"),
    "D2_AUTHORIZED": ("AUTHORIZATION_CLAIMED", "INVALIDATED_BEFORE_CLAIM"),
    "AUTHORIZATION_CLAIMED": ("BOARD_BOUND", "CONSUMED_FAILED"),
    "BOARD_BOUND": ("BASELINE_VERIFIED", "CONSUMED_FAILED"),
    "BASELINE_VERIFIED": ("FLASH_ERASED", "CONSUMED_FAILED"),
    "FLASH_ERASED": ("FLASH_WRITTEN_AND_VERIFIED", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "FLASH_WRITTEN_AND_VERIFIED": ("AUTO_RESET_COMPLETED", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "AUTO_RESET_COMPLETED": ("ISOLATED_BROKER_STARTED", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "ISOLATED_BROKER_STARTED": ("PREPARE_EXECUTED_ONCE", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "PREPARE_EXECUTED_ONCE": ("AUTO_RESTART_OBSERVED", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "AUTO_RESTART_OBSERVED": ("VERIFY_EXECUTED_ONCE", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "VERIFY_EXECUTED_ONCE": ("PREPARED_VERIFIED", "LOCKED_RECOVERY_ENTERED", "CONSUMED_FAILED"),
    "PREPARED_VERIFIED": ("ISOLATED_BROKER_STOPPED", "CONSUMED_FAILED"),
    "ISOLATED_BROKER_STOPPED": ("CONSUMED_PASS", "CONSUMED_FAILED"),
    "LOCKED_RECOVERY_ENTERED": ("LOCKED_RECOVERY_COMPLETED", "CONSUMED_FAILED"),
    "LOCKED_RECOVERY_COMPLETED": ("CONSUMED_FAILED",),
    "CONSUMED_PASS": (),
    "INVALIDATED_BEFORE_CLAIM": (),
    "CONSUMED_FAILED": (),
}
TERMINAL_STATES = ("CONSUMED_PASS", "INVALIDATED_BEFORE_CLAIM", "CONSUMED_FAILED")

ALLOWED_OPERATIONS = (
    "RECHECK_FROZEN_PUBLIC_AND_PRIVATE_METADATA",
    "CLAIM_EXACT_D2_ONCE",
    "BIND_ONE_TARGET_BOARD",
    "BIND_ONE_SERIAL_CANDIDATE",
    "READ_ONLY_BOARD_BASELINE",
    "ERASE_FLASH_ONCE",
    "WRITE_FROZEN_IMMUTABLE_FIRMWARE_ONCE",
    "VERIFY_FLASH_ONCE",
    "AUTOMATIC_HARD_RESET",
    "START_EXACT_ISOLATED_TLS_BROKER_ONCE",
    "GH2D9R_PREPARE_V1_ONCE",
    "OBSERVE_AUTOMATIC_RESTART",
    "GH2D9R_VERIFY_V1_READ_ONLY_ONCE",
    "STOP_EXACT_ISOLATED_TLS_BROKER_ONCE",
    "WRITE_D2_CONSUMED_MARKER_ONCE",
    "LOCKED_RECOVERY_AT_MOST_ONCE_WHEN_ELIGIBLE",
)
PROHIBITED_OPERATIONS = (
    "SECOND_BOARD",
    "SECOND_SERIAL_CANDIDATE",
    "SECOND_BROKER_START",
    "SECOND_PREPARE",
    "SECOND_VERIFY",
    "AUTOMATIC_RETRY",
    "AUTHORIZATION_REPLAY",
    "ALTERNATE_ARTIFACT",
    "ALTERNATE_CUSTODY_ROOT",
    "ALTERNATE_PREPARE_OR_VERIFY_COMMAND",
    "ALTERNATE_EXECUTION_PACKAGE",
    "ACTIVATE",
    "CLEANUP",
    "PRODUCTION_BROKER",
    "HOME_ASSISTANT",
    "GREENHOUSE_MANAGER",
    "M401A",
    "T1",
    "EFUSE",
    "SECURE_BOOT",
    "FLASH_ENCRYPTION",
    "READY",
    "MERGE",
    "RELEASE",
    "TAG",
    "DEPLOYMENT",
)

FAILURE_MATRIX = (
    {
        "code": "PRECLAIM_REPOSITORY_OR_PR_DRIFT",
        "phase": "BEFORE_CLAIM",
        "terminal_state": "INVALIDATED_BEFORE_CLAIM",
        "authorization_consumed": False,
        "locked_recovery_eligible": False,
    },
    {
        "code": "PRECLAIM_CI_OR_ARTIFACT_DRIFT",
        "phase": "BEFORE_CLAIM",
        "terminal_state": "INVALIDATED_BEFORE_CLAIM",
        "authorization_consumed": False,
        "locked_recovery_eligible": False,
    },
    {
        "code": "PRECLAIM_U1_MARKER_CUSTODY_OR_TOOLCHAIN_DRIFT",
        "phase": "BEFORE_CLAIM",
        "terminal_state": "INVALIDATED_BEFORE_CLAIM",
        "authorization_consumed": False,
        "locked_recovery_eligible": False,
    },
    {
        "code": "PRECLAIM_BOARD_SERIAL_BASELINE_OR_EXECUTION_BINDING_DRIFT",
        "phase": "BEFORE_CLAIM",
        "terminal_state": "INVALIDATED_BEFORE_CLAIM",
        "authorization_consumed": False,
        "locked_recovery_eligible": False,
    },
    {
        "code": "PREEXISTING_D2_CLAIM_OR_EXECUTION_MARKER",
        "phase": "BEFORE_CLAIM",
        "terminal_state": "INVALIDATED_BEFORE_CLAIM",
        "authorization_consumed": False,
        "locked_recovery_eligible": False,
    },
    {
        "code": "BOARD_OR_SERIAL_CANDIDATE_NOT_UNIQUE",
        "phase": "AFTER_CLAIM_BEFORE_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": False,
    },
    {
        "code": "BASELINE_STATE_NOT_ALLOWED_OR_IDENTITY_MISMATCH",
        "phase": "AFTER_CLAIM_BEFORE_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": False,
    },
    {
        "code": "FLASH_ERASE_WRITE_OR_VERIFY_FAILED",
        "phase": "AFTER_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": True,
    },
    {
        "code": "AUTO_RESET_OR_BOOT_OBSERVATION_FAILED",
        "phase": "AFTER_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": True,
    },
    {
        "code": "ISOLATED_BROKER_START_TLS_OR_STOP_FAILED",
        "phase": "AFTER_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": True,
    },
    {
        "code": "PREPARE_FAILED_OR_RESTART_NOT_OBSERVED",
        "phase": "AFTER_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": True,
    },
    {
        "code": "VERIFY_OR_TLS_PREPARED_BINDING_FAILED",
        "phase": "AFTER_DESTRUCTIVE_BOUNDARY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": True,
    },
    {
        "code": "D2_CONSUMED_MARKER_WRITE_OR_PUBLIC_RESULT_FAILED",
        "phase": "AFTER_CLAIM",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": False,
    },
    {
        "code": "REPLAY_SECOND_OPERATION_OR_PROHIBITED_OPERATION",
        "phase": "ANY_AFTER_CLAIM",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": False,
    },
    {
        "code": "LOCKED_RECOVERY_FAILED_OR_EXHAUSTED",
        "phase": "LOCKED_RECOVERY",
        "terminal_state": "CONSUMED_FAILED",
        "authorization_consumed": True,
        "locked_recovery_eligible": False,
    },
)


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_utc(value: str, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError(code) from exc
    require(observed.tzinfo is not None, code)
    return observed.astimezone(timezone.utc)


def validate_transition(current: str, target: str) -> None:
    require(current in ALLOWED_TRANSITIONS, "CURRENT_STATE_INVALID")
    require(target in STATES, "TARGET_STATE_INVALID")
    require(target in ALLOWED_TRANSITIONS[current], "STATE_TRANSITION_NOT_ALLOWED")


def failure_policy(code: str) -> Mapping[str, Any]:
    matches = [entry for entry in FAILURE_MATRIX if entry["code"] == code]
    require(len(matches) == 1, "FAILURE_CODE_NOT_UNIQUE_OR_UNKNOWN")
    return matches[0]


def build_contract(source_sha: str, main_sha: str = EXPECTED_MAIN_SHA) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    require(main_sha == EXPECTED_MAIN_SHA, "MAIN_SHA_MISMATCH")
    for key, value in PUBLIC_BINDINGS.items():
        if key.endswith("_sha256"):
            require(
                isinstance(value, str) and HEX64.fullmatch(value) is not None,
                f"PUBLIC_BINDING_INVALID_{key.upper()}",
            )
    contract: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-contract/1",
        "stage": STAGE,
        "state": "D2_REVIEWED",
        "d2_request_id": D2_REQUEST_ID,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "pull_request": PULL_REQUEST,
        "base_pull_request": BASE_PULL_REQUEST,
        "base_source_sha": BASE_SOURCE_SHA,
        "main_sha": main_sha,
        "source_sha": source_sha,
        "required_pull_request_state": {
            "state": "open",
            "draft": True,
            "merged": False,
            "mergeable": True,
        },
        "required_base_pull_request_state": {
            "state": "open",
            "draft": True,
            "merged": False,
            "mergeable": True,
        },
        "u1_02_authorization_id": U1_02_ID,
        "u1_02_required_status": "CONSUMED_PASS",
        "u1_02_replay_permitted": False,
        "u1_02_consumed_marker_live_sha256_required": True,
        "public_bindings": dict(PUBLIC_BINDINGS),
        "state_machine": {
            "states": list(STATES),
            "allowed_transitions": {
                key: list(value) for key, value in ALLOWED_TRANSITIONS.items()
            },
            "terminal_states": list(TERMINAL_STATES),
            "destructive_boundary_state": "FLASH_ERASED",
            "prepare_max_count": 1,
            "verify_max_count": 1,
            "isolated_broker_start_max_count": 1,
            "locked_recovery_max_count": 1,
        },
        "failure_matrix": [dict(entry) for entry in FAILURE_MATRIX],
        "allowed_operations": list(ALLOWED_OPERATIONS),
        "prohibited_operations": list(PROHIBITED_OPERATIONS),
        "authorization_validity_seconds_max": MAX_AUTHORIZATION_SECONDS,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "success_or_failure_after_claim_consumes": True,
        "actuate_stage2d10_after_return_only": True,
        "authorization_record_included": False,
        "execution_launcher_included": False,
        "private_content_included": False,
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
    contract["contract_binding_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def build_exact_authorization_request(
    contract: Mapping[str, Any],
    *,
    review_artifact_id: int,
    review_artifact_digest_sha256: str,
    review_binding_sha256: str,
    public_preflight_artifact_id: int,
    public_preflight_artifact_digest_sha256: str,
    private_preflight_result_sha256: str,
    u1_02_consumed_marker_sha256: str,
    board_identity_sha256: str,
    serial_identity_sha256: str,
    baseline_state_sha256: str,
    execution_package_sha256: str,
    execution_script_sha256: str,
    execution_launcher_sha256: str,
    execution_marker_name_sha256: str,
    locked_recovery_package_sha256: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    exact_bindings = {
        "review_artifact_digest_sha256": review_artifact_digest_sha256,
        "review_binding_sha256": review_binding_sha256,
        "public_preflight_artifact_digest_sha256": public_preflight_artifact_digest_sha256,
        "private_preflight_result_sha256": private_preflight_result_sha256,
        "u1_02_consumed_marker_sha256": u1_02_consumed_marker_sha256,
        "board_identity_sha256": board_identity_sha256,
        "serial_identity_sha256": serial_identity_sha256,
        "baseline_state_sha256": baseline_state_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_script_sha256": execution_script_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "execution_marker_name_sha256": execution_marker_name_sha256,
        "locked_recovery_package_sha256": locked_recovery_package_sha256,
    }
    for name, digest in exact_bindings.items():
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            f"EXACT_BINDING_INVALID_{name.upper()}",
        )
    require(
        isinstance(review_artifact_id, int) and review_artifact_id > 0,
        "REVIEW_ARTIFACT_ID_INVALID",
    )
    require(
        isinstance(public_preflight_artifact_id, int)
        and public_preflight_artifact_id > 0,
        "PUBLIC_PREFLIGHT_ARTIFACT_ID_INVALID",
    )
    require(
        contract.get("schema") == "gh.h3.n2.stage2d9r-successor-d2-contract/1",
        "CONTRACT_SCHEMA_MISMATCH",
    )
    issued = parse_utc(issued_at, "ISSUED_AT_INVALID")
    expires = parse_utc(expires_at, "EXPIRES_AT_INVALID")
    validity_seconds = int((expires - issued).total_seconds())
    require(validity_seconds > 0, "AUTHORIZATION_WINDOW_NOT_POSITIVE")
    require(
        validity_seconds <= MAX_AUTHORIZATION_SECONDS,
        "AUTHORIZATION_WINDOW_EXCEEDS_MAXIMUM",
    )
    request: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-exact-d2-authorization-request/1",
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "authorization_validity_seconds": validity_seconds,
        "repository": contract["repository"],
        "branch": contract["branch"],
        "pull_request": contract["pull_request"],
        "base_pull_request": contract["base_pull_request"],
        "base_source_sha": contract["base_source_sha"],
        "main_sha": contract["main_sha"],
        "source_sha": contract["source_sha"],
        "contract_binding_sha256": contract["contract_binding_sha256"],
        "review_artifact_id": review_artifact_id,
        "review_artifact_digest_sha256": review_artifact_digest_sha256,
        "review_binding_sha256": review_binding_sha256,
        "public_preflight_artifact_id": public_preflight_artifact_id,
        "public_preflight_artifact_digest_sha256": public_preflight_artifact_digest_sha256,
        "private_preflight_result_sha256": private_preflight_result_sha256,
        "u1_02_authorization_id": U1_02_ID,
        "u1_02_consumed_marker_sha256": u1_02_consumed_marker_sha256,
        "board_identity_sha256": board_identity_sha256,
        "serial_identity_sha256": serial_identity_sha256,
        "baseline_state_sha256": baseline_state_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_script_sha256": execution_script_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "execution_marker_name_sha256": execution_marker_name_sha256,
        "locked_recovery_package_sha256": locked_recovery_package_sha256,
        "allowed_operations": list(ALLOWED_OPERATIONS),
        "prohibited_operations": list(PROHIBITED_OPERATIONS),
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "isolated_broker_start_max_count": 1,
        "locked_recovery_max_count": 1,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "success_or_failure_after_claim_consumes": True,
        "authorized": False,
        "authorization_record_created": False,
        "execution_launcher_included": False,
        "secret_values_included": False,
        "private_paths_included": False,
    }
    request["request_binding_sha256"] = sha256_bytes(canonical_json_bytes(request))
    return request
