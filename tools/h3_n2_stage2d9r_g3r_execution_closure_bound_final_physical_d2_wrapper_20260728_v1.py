#!/usr/bin/env python3
"""Physical-D2 wrapper bound to an execution closure, not repository HEAD.

The wrapper preserves the repaired serial handshake, immutable/recovery payload
bytes, private custody bindings, one-shot authorization and locked recovery.
Repository HEAD is validated as audit metadata only and cannot authorize a
changed execution package or changed payload.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_execution_closure_binding_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff
import h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1 as repaired

core = repaired.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.NEW_PHYSICAL_D2_REQUEST_ID
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-preclaim-marker/1"
_BASE_VALIDATE_AUTHORIZATION = core.validate_authorization


def configure_core() -> Any:
    bindings = {
        "STAGE": STAGE,
        "D2_REQUEST_ID": D2_REQUEST_ID,
        "AUTH_SCHEMA": AUTH_SCHEMA,
        "RESULT_SCHEMA": RESULT_SCHEMA,
        "MARKER_SCHEMA": MARKER_SCHEMA,
        "IMMUTABLE_ARTIFACT_ID": repaired.IMMUTABLE_ARTIFACT_ID,
        "IMMUTABLE_ARCHIVE_SHA256": repaired.IMMUTABLE_ARCHIVE_SHA256,
        "IMMUTABLE_PAYLOAD_TAR_SHA256": repaired.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE_MERGED_SHA256": repaired.IMMUTABLE_MERGED_SHA256,
        "RECOVERY_ARTIFACT_ID": repaired.IMMUTABLE_ARTIFACT_ID,
        "RECOVERY_ARCHIVE_SHA256": repaired.IMMUTABLE_ARCHIVE_SHA256,
        "RECOVERY_PAYLOAD_TAR_SHA256": repaired.RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY_DESCRIPTOR_SHA256": repaired.RECOVERY_DESCRIPTOR_SHA256,
        "PRIVATE_PACKAGE_SHA256": repaired.PRIVATE_PACKAGE_SHA256,
        "PREPARE_COMMAND_SHA256": repaired.PREPARE_COMMAND_SHA256,
        "VERIFY_COMMAND_SHA256": repaired.VERIFY_COMMAND_SHA256,
        "CANDIDATE_DIGEST_SHA256": repaired.CANDIDATE_DIGEST_SHA256,
        "CA_PEM_SHA256": repaired.CA_PEM_SHA256,
        "BUILD_BINDING": repaired.BUILD_BINDING,
        "CUSTODY_RELATIVE": repaired.CUSTODY_RELATIVE,
        "TEST_PARTITION_ADDRESS": repaired.TEST_PARTITION_ADDRESS,
        "TEST_PARTITION_SIZE": repaired.TEST_PARTITION_SIZE,
        "ERASED_SHA256": repaired.ERASED_SHA256,
        "validate_public_inputs": handoff.validate_public_inputs,
        "locked_recovery": repaired.locked_recovery,
    }
    for key, value in bindings.items():
        setattr(core, key, value)

    # The base validator verifies the exact package digest, payload digests,
    # execution script, toolchain executables, time window and one-shot limits.
    # This successor adds an explicit closure manifest and deliberately does not
    # compare repository HEAD to a frozen commit.
    core.__file__ = __file__

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = _BASE_VALIDATE_AUTHORIZATION(*args, **kwargs)
        package_root = kwargs.get("package_root")
        core.require(isinstance(package_root, Path), "AUTHORIZATION_PACKAGE_ROOT_MISSING")
        closure = contract.validate_execution_closure(package_root)
        binding = closure["binding"]
        manifest = closure["manifest"]

        required = {
            "decision_id": contract.DECISION_ID,
            "execution_closure_sha256": manifest["execution_closure_sha256"],
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 1,
            "execution_package_sha256": core.canonical_package_digest(package_root),
            "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
            "execution_launcher_sha256": binding["execution_launcher_sha256"],
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "baseline_original_main_sha": repaired.BASELINE_ORIGINAL_MAIN_SHA,
            "immutable_source_sha": repaired.BASE_HEAD_SHA,
            "base_pr": repaired.BASE_PR,
            "base_head_sha": repaired.BASE_HEAD_SHA,
            "final_execution_binding": repaired.FINAL_EXECUTION_BINDING,
            "final_execution_binding_sha256": repaired.FINAL_EXECUTION_BINDING_SHA256,
            "baseline_result_sha256": repaired.BASELINE_RESULT_SHA256,
            "locked_recovery_scope": "TEST_PARTITION_ONLY",
            "upstream_execution_rebind_source_sha": contract.BASE_HEAD_SHA,
            "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
            "upstream_execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
            "previous_request_id": contract.PREVIOUS_REQUEST_ID,
            "previous_request_state": contract.PREVIOUS_REQUEST_STATE,
            "previous_request_reuse_permitted": False,
        }
        for key, expected in required.items():
            core.require(value.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")

        contract.validate_repository_audit(value)
        core.require(
            isinstance(value.get("source_sha"), str)
            and core.HEX40.fullmatch(value["source_sha"]) is not None
            and value.get("source_sha") == binding.get("source_sha")
            and value.get("host_final_preflight_source_sha") == value.get("source_sha"),
            "AUTHORIZATION_EXECUTION_SOURCE_MISMATCH",
        )
        core.require(
            value.get("locked_recovery_authorized") is True,
            "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED",
        )
        return value

    core.validate_authorization = validate_authorization
    repaired.repair.install_repaired_handshake(core)
    return core


def install() -> None:
    handoff.STAGE = STAGE
    handoff.D2_REQUEST_ID = D2_REQUEST_ID
    handoff.AUTH_SCHEMA = AUTH_SCHEMA
    handoff.RESULT_SCHEMA = RESULT_SCHEMA
    handoff.MARKER_SCHEMA = MARKER_SCHEMA
    handoff.PRE_RESULT_SCHEMA = PRE_RESULT_SCHEMA
    handoff.PRE_MARKER_SCHEMA = PRE_MARKER_SCHEMA
    handoff.configure_core = configure_core


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_EXECUTION_CLOSURE_AUTHORIZATION",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_role": "BLOCKING",
            "authorization_created": False,
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
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 0
    install()
    return handoff.main()


if __name__ == "__main__":
    raise SystemExit(main())
