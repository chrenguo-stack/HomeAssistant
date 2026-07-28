#!/usr/bin/env python3
"""Source-only correction for the frozen Stage2D9R aggregate baseline digest."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "gh.h3.n2.stage2d9r-g3r-baseline-aggregate-digest-correction-contract/1"
REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-baseline-aggregate-digest-correction-review/1"
MAC_POLICY_SCHEMA = "gh.h3.n2.stage2d9r-g3r-chip-mac-candidate-evidence-policy/2"
CLOSURE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-corrected-baseline-execution-closure/1"
H5_REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-corrected-baseline-host-closure-request/1"
H5_AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-corrected-baseline-host-closure-authorization/1"
STAGE = "H3/N2 Stage 2D-9R G3R baseline aggregate digest correction"
DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-BASELINE-AGGREGATE-DIGEST-CORRECTION-20260729-01"
BASE_PR = 197
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-usb-identity-evidence-repair-20260728-v1"
BASE_HEAD_SHA = "0468e831e61f859ca5e1654785c67dd323e92e64"
REPOSITORY_HEAD_AT_REPAIR = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
UPSTREAM_ARTIFACT_ID = 8696182269
UPSTREAM_ARTIFACT_SHA256 = "ce87a0d2f421970cd5c8f53a16f0b85e70d3cdbe294afb18263f4276768d87b5"
UPSTREAM_REVIEW_BINDING_SHA256 = "b63f3678be4badf90943601506b68c1a90f932221d0b34d6e1fafade8827576c"
UPSTREAM_INNER_TAR_SHA256 = "aed734308676d6babf01a6e62c252ae07b9731719f7633b780950191217d1501"
B2_AUTHORIZATION_ID = "B2-H3N2-STAGE2D9R-G3R-USB-IDENTITY-AND-BASELINE-DIAGNOSTIC-READONLY-20260728-01"
B2_AUTHORIZATION_RECORD_SHA256 = "3bef115a711270c7c27538981d3e4e6df774e5cd3075c395f9ed40ba8c3dbb45"
B2_AUTHORIZATION_FILE_SHA256 = "877ff05f7d176673aeb5d16f145d76e63fc30c4ed9afc15a3b48b5db6d4c82c3"
B2_RESULT_SHA256 = "f46565e0f4445781cbd84d2685bea6dcee7961ea7e7f48cd4bd7568a3e747082"
B2_RESULT_FILE_SHA256 = "7cd2d5ff39ed7e0b3060dd6c0e6de6e5559e79b23daae7ccd0eba43a8057b744"
B2_MARKER_FILE_SHA256 = "3cc8c75cf55b9ead9a4221ed3449ef4191824e17956a0b16abaacb86d1219909"
B2_TERMINAL_OUTPUT_FILE_SHA256 = "e3c1c5f5fc554017460a4b680667c40ec1845700c039e8209e19f1f54bf5b351"
INVALID_LEGACY_BASELINE_SHA256 = "0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
CORRECTED_LEGACY_BASELINE_SHA256 = "776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f"
CORRECTED_PATH_NEUTRAL_BASELINE_SHA256 = "bec8a0da70a76c4f7d29fd738b9f2e1a398843884e1a9d7a09befe25f5c01683"
PATH_NEUTRAL_USB_IDENTITY_SHA256 = "066ba231fa22464b96ffda2f0cf3115b0c5db083cd15d326946113bd5c0c8529"
BOARD_IDENTITY_SHA256 = "2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
SERIAL_IDENTITY_SHA256 = "b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
CHIP_ID_OUTPUT_SHA256 = "ebc8ed3ce6923e1a86a7ff8dbb01e830955cd7aef5e5927963a0bd3adacbb0b7"
FLASH_ID_OUTPUT_SHA256 = "738b4537462780c847d34baa744a5f17034a05a7e65d0bbd300be5eb5e4d801e"
TEST_PARTITION_SHA256 = "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
TEST_PARTITION_SIZE = 0x10000
H5_AUTHORIZATION_ID = "H5-H3N2-STAGE2D9R-G3R-CORRECTED-BASELINE-EXECUTION-CLOSURE-20260729-01"
H5_OPERATION = "HOST_ONLY_VALIDATE_CORRECTED_BASELINE_AND_BUILD_UNAUTHORIZED_PHYSICAL_REQUEST_05"
FUTURE_PHYSICAL_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-05"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAC = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
FALSE_BOUNDARY = {k: False for k in (
    "authorized authorization_created authorization_claimed authorization_consumed board_operation "
    "usb_enumeration serial_open esptool_operation flash_write flash_erase physical_nvs_operation "
    "network_operation broker_started prepare_executed verify_executed activate_executed cleanup_executed "
    "ready merge release tag deployment private_values_included private_paths_included secret_values_included "
    "physical_request_created physical_request_authorized"
).split()}

class ContractError(RuntimeError):
    pass

def require(ok: bool, code: str) -> None:
    if not ok:
        raise ContractError(code)

def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value

def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value

def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(code) from error
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)

def legacy_baseline_components() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-successor-board-baseline/1",
        "board_identity_sha256": BOARD_IDENTITY_SHA256,
        "serial_identity_sha256": SERIAL_IDENTITY_SHA256,
        "chip_id_output_sha256": CHIP_ID_OUTPUT_SHA256,
        "flash_id_output_sha256": FLASH_ID_OUTPUT_SHA256,
        "test_partition_sha256": TEST_PARTITION_SHA256,
        "test_partition_size": TEST_PARTITION_SIZE,
    }

def recompute_corrected_legacy_baseline_sha256() -> str:
    digest = canonical_json_sha256(legacy_baseline_components())
    require(digest == CORRECTED_LEGACY_BASELINE_SHA256, "CORRECTED_BASELINE_INTERNAL_DIGEST_MISMATCH")
    require(digest != INVALID_LEGACY_BASELINE_SHA256, "INVALID_AND_CORRECTED_BASELINE_COLLISION")
    return digest

def expected_b2_result() -> dict[str, Any]:
    return {
        "status": "CONSUMED_PASS",
        "authorization_id": B2_AUTHORIZATION_ID,
        "diagnostic_result_sha256": B2_RESULT_SHA256,
        "authorization_consumed": True,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "flash_write": False,
        "flash_erase": False,
        "serial_open": False,
        "network_operation": False,
        "future_physical_request_created": False,
        "baseline_evidence": {
            "legacy_board_identity_matches": True,
            "legacy_serial_identity_matches": True,
            "legacy_baseline_matches": False,
            "observed_legacy_baseline_sha256": CORRECTED_LEGACY_BASELINE_SHA256,
            "observed_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
            "chip_id_output_sha256": CHIP_ID_OUTPUT_SHA256,
            "flash_id_output_sha256": FLASH_ID_OUTPUT_SHA256,
            "test_partition_sha256": TEST_PARTITION_SHA256,
            "test_partition_size": TEST_PARTITION_SIZE,
            "chip_mac_candidate_count": 2,
            "chip_mac_sha256": None,
        },
    }

def validate_b2_result(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = expected_b2_result()
    for key, item in expected.items():
        if key == "baseline_evidence":
            evidence = value.get(key)
            require(isinstance(evidence, Mapping), "B2_RESULT_BASELINE_EVIDENCE_MISSING")
            for evidence_key, evidence_value in item.items():
                require(evidence.get(evidence_key) == evidence_value, f"B2_RESULT_{evidence_key.upper()}_MISMATCH")
        else:
            require(value.get(key) == item, f"B2_RESULT_{key.upper()}_MISMATCH")
    if len(value) > len(expected):
        body = dict(value)
        supplied = body.pop("diagnostic_result_sha256", None)
        require(supplied == canonical_json_sha256(body), "B2_RESULT_CANONICAL_DIGEST_MISMATCH")
    return dict(value)

def b2_disposition() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-b2-terminal-disposition/1",
        "authorization_id": B2_AUTHORIZATION_ID,
        "status": "CONSUMED_PASS",
        "authorization_record_sha256": B2_AUTHORIZATION_RECORD_SHA256,
        "authorization_file_sha256": B2_AUTHORIZATION_FILE_SHA256,
        "diagnostic_result_sha256": B2_RESULT_SHA256,
        "result_file_sha256": B2_RESULT_FILE_SHA256,
        "marker_file_sha256": B2_MARKER_FILE_SHA256,
        "terminal_output_file_sha256": B2_TERMINAL_OUTPUT_FILE_SHA256,
        "authorization_consumed": True,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "legacy_board_identity_matches": True,
        "legacy_serial_identity_matches": True,
        "legacy_baseline_matches": False,
        "observed_legacy_baseline_sha256": CORRECTED_LEGACY_BASELINE_SHA256,
        "observed_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "flash_write": False,
        "flash_erase": False,
        "serial_open": False,
        "network_operation": False,
        "future_physical_request_created": False,
    }

def invalid_legacy_digest_disposition() -> dict[str, Any]:
    recomputed = recompute_corrected_legacy_baseline_sha256()
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-invalid-legacy-baseline-digest/1",
        "state": "INVALID_DERIVED_AGGREGATE_DIGEST_PERMANENTLY_REJECTED",
        "invalid_legacy_baseline_sha256": INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": recomputed,
        "reason": "DOES_NOT_EQUAL_CANONICAL_JSON_SHA256_OF_FROZEN_COMPONENTS",
        "frozen_components_sha256": recomputed,
        "component_values_changed": False,
        "all_component_values_match_b2": True,
        "invalid_digest_reuse_permitted": False,
        "invalid_digest_acceptance_permitted": False,
    }

def corrected_baseline_candidate() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-corrected-baseline-candidate/1",
        "state": "CORRECTED_BASELINE_CANDIDATE_AWAITING_EXACT_HOST_CLOSURE_AUTHORIZATION",
        "legacy_baseline_components": legacy_baseline_components(),
        "corrected_legacy_baseline_sha256": recompute_corrected_legacy_baseline_sha256(),
        "corrected_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "path_neutral_usb_identity_sha256": PATH_NEUTRAL_USB_IDENTITY_SHA256,
        "b2_result_sha256": B2_RESULT_SHA256,
        "b2_status": "CONSUMED_PASS",
        "same_components_observed_by_b2": True,
        "accepted_for_physical_execution": False,
        "physical_request_created": False,
        "physical_request_authorized": False,
    }

def extract_chip_mac_candidate_evidence(stdout: str) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for line in stdout.splitlines():
        label = line.split(":", 1)[0].strip().lower() if ":" in line else ""
        for candidate in sorted({m.group(0).lower() for m in MAC.finditer(line)}):
            digest = sha256_text(candidate)
            entry = records.setdefault(digest, {"candidate_sha256": digest, "label_sha256s": [], "line_sha256s": []})
            for key, item in (("label_sha256s", sha256_text(label)), ("line_sha256s", sha256_text(line))):
                if item not in entry[key]:
                    entry[key].append(item)
    ordered = []
    for digest in sorted(records):
        records[digest]["label_sha256s"].sort()
        records[digest]["line_sha256s"].sort()
        ordered.append(records[digest])
    count = len(ordered)
    return {
        "schema": MAC_POLICY_SCHEMA,
        "policy_version": 2,
        "selection_state": "NO_CANDIDATE" if count == 0 else "UNIQUE_CANDIDATE" if count == 1 else "AMBIGUOUS_CANDIDATES",
        "candidate_count": count,
        "candidate_records": ordered,
        "selected_chip_mac_sha256": ordered[0]["candidate_sha256"] if count == 1 else None,
        "raw_mac_values_included": False,
        "raw_output_included": False,
        "candidate_set_preserved_hash_only": True,
        "used_as_blocking_hardware_identity": False,
    }

def mac_candidate_policy() -> dict[str, Any]:
    return {
        "schema": MAC_POLICY_SCHEMA,
        "policy_version": 2,
        "b2_candidate_count": 2,
        "b2_selected_chip_mac_sha256": None,
        "b2_candidate_digests_available": False,
        "b2_evidence_limitation": "V1_RETAINED_COUNT_BUT_NOT_HASHED_CANDIDATE_SET",
        "future_candidate_set_must_be_preserved_hash_only": True,
        "future_ambiguous_candidate_must_not_be_selected": True,
        "raw_mac_values_included": False,
        "used_as_blocking_hardware_identity": False,
    }

def build_corrected_execution_closure(source_sha: str, review_binding_sha256: str) -> dict[str, Any]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    validate_sha256(review_binding_sha256, "REVIEW_BINDING_SHA256_INVALID")
    return {
        "schema": CLOSURE_SCHEMA,
        "state": "CORRECTED_BASELINE_EXECUTION_CLOSURE_SOURCE_FROZEN_AWAITING_EXACT_H5_AUTHORIZATION",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "review_binding_sha256": review_binding_sha256,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "b2_authorization_id": B2_AUTHORIZATION_ID,
        "b2_result_sha256": B2_RESULT_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": recompute_corrected_legacy_baseline_sha256(),
        "corrected_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "physical_request_id_reserved": FUTURE_PHYSICAL_REQUEST_ID,
        "physical_request_generation_requires_separate_h5_authorization": True,
        "next_gate": H5_AUTHORIZATION_ID,
        **FALSE_BOUNDARY,
    }

def build_h5_request_draft(source_sha: str, review_binding_sha256: str) -> dict[str, Any]:
    closure = build_corrected_execution_closure(source_sha, review_binding_sha256)
    return {
        "schema": H5_REQUEST_SCHEMA,
        "state": "CORRECTED_BASELINE_HOST_CLOSURE_REQUEST_AWAITING_EXACT_AUTHORIZATION",
        "authorization_id": H5_AUTHORIZATION_ID,
        "operation": H5_OPERATION,
        "source_sha": source_sha,
        "review_binding_sha256": review_binding_sha256,
        "corrected_execution_closure_sha256": canonical_json_sha256(closure),
        "b2_result_sha256": B2_RESULT_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": CORRECTED_LEGACY_BASELINE_SHA256,
        "future_physical_request_id": FUTURE_PHYSICAL_REQUEST_ID,
        "issued_at": None,
        "expires_at": None,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        **FALSE_BOUNDARY,
    }

def validate_h5_authorization(value: Mapping[str, Any], *, source_sha: str, review_binding_sha256: str,
                              closure_sha256: str, now: datetime | None = None) -> dict[str, Any]:
    exact = {
        "schema": H5_AUTH_SCHEMA, "authorization_id": H5_AUTHORIZATION_ID, "operation": H5_OPERATION,
        "authorized": True, "one_shot": True, "replay_permitted": False, "automatic_retry_permitted": False,
        "source_sha": source_sha, "review_binding_sha256": review_binding_sha256,
        "corrected_execution_closure_sha256": closure_sha256, "b2_result_sha256": B2_RESULT_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": CORRECTED_LEGACY_BASELINE_SHA256,
        "host_only": True, "board_operation_authorized": False, "usb_enumeration_authorized": False,
        "esptool_operation_authorized": False, "flash_write_authorized": False, "flash_erase_authorized": False,
        "network_after_authorization_authorized": False, "broker_operation_authorized": False,
        "prepare_authorized": False, "verify_authorized": False,
        "physical_request_generation_authorized": True, "physical_request_execution_authorized": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, f"H5_AUTH_{key.upper()}_MISMATCH")
    issued = utc(value.get("issued_at"), "H5_AUTH_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "H5_AUTH_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "H5_AUTH_NOT_CURRENT")
    require((expires - issued).total_seconds() <= 3600, "H5_AUTH_WINDOW_TOO_LONG")
    body = dict(value)
    supplied = body.pop("authorization_record_sha256", None)
    require(supplied == canonical_json_sha256(body), "H5_AUTH_RECORD_DIGEST_MISMATCH")
    return dict(value)

def source_contract(source_sha: str) -> dict[str, Any]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR197")
    return {
        "schema": SCHEMA,
        "state": "BASELINE_AGGREGATE_DIGEST_CORRECTION_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_repair": REPOSITORY_HEAD_AT_REPAIR,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "b2_authorization_id": B2_AUTHORIZATION_ID,
        "b2_state": "CONSUMED_PASS",
        "b2_result_sha256": B2_RESULT_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_LEGACY_BASELINE_SHA256,
        "corrected_legacy_baseline_sha256": recompute_corrected_legacy_baseline_sha256(),
        "corrected_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "mac_candidate_policy_version": 2,
        "future_h5_authorization_id": H5_AUTHORIZATION_ID,
        "future_physical_request_id": FUTURE_PHYSICAL_REQUEST_ID,
        "next_gate": "EXACT_HOST_ONLY_CORRECTED_BASELINE_CLOSURE_AUTHORIZATION",
        **FALSE_BOUNDARY,
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
