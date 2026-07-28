#!/usr/bin/env python3
"""Execution-closure binding contract for the Stage2D9R G3R successor.

Repository HEAD is retained as audit evidence only. Authorization remains
fail-closed on the exact execution closure, package bytes, payload bytes,
toolchain digests, one-shot identity, and board/runtime bindings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-binding-contract/1"
CLOSURE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-manifest/1"
EXECUTION_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-package/1"
REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-binding-review/1"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-request/1"
HOST_AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-host-preflight-authorization/1"
HOST_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-host-preflight-result/1"
HOST_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-host-preflight-marker/1"

STAGE = "H3/N2 Stage 2D-9R G3R execution-closure binding successor"
DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01"
BASE_PR = 194
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-main-drift-successor-rebind-20260728-v1"
BASE_HEAD_SHA = "b69371b13b6af139b4607a2150f25f440bb251c7"
REPOSITORY_HEAD_AT_POLICY_FREEZE = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"

UPSTREAM_ARTIFACT_ID = 8688476229
UPSTREAM_ARTIFACT_SHA256 = "89e25e287c33de0d88c714c748329c5d4cdbe12f83343fdd18eff8debf351a04"
UPSTREAM_REVIEW_ARCHIVE_SHA256 = "8ea47c873e048c8c9833a01701de68520d9f0a92849cfaf2b36d342d3118816f"
UPSTREAM_REVIEW_BINDING_SHA256 = "5278980189c426097b835034233eb1701540ca4262fdf599c62452b98e6d5a45"
UPSTREAM_EXECUTION_PACKAGE_SHA256 = "e78b8d72f6d4f98425fc0f164b4e9a162b6a5faf3d8303f6f4582d87281da710"
UPSTREAM_EXECUTION_WRAPPER_SHA256 = "11b9c096cfe80600c3ceb43d79c9b3b3b20773a83b4404ea9c057ade3e60a379"
UPSTREAM_EXECUTION_LAUNCHER_SHA256 = "89cd609cb6835fbbc03abca6eabefe8895f1813ef6fcdce51065247ebcab74ec"

PREVIOUS_HOST_AUTHORIZATION_ID = "H3-H3N2-STAGE2D9R-G3R-MAIN-DRIFT-SUCCESSOR-REBIND-20260728-01"
PREVIOUS_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03"
PREVIOUS_REQUEST_STATE = "SUPERSEDED_BY_EXECUTION_CLOSURE_POLICY_BEFORE_AUTHORIZATION"
FUTURE_HOST_AUTHORIZATION_ID = "H4-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01"
NEW_PHYSICAL_D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04"
HOST_AUTH_OPERATION = "VALIDATE_EXECUTION_CLOSURE_AND_ISSUE_UNAUTHORIZED_PHYSICAL_D2_REQUEST"

CLOSURE_MANIFEST_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
EXECUTION_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_MANIFEST_FILE, EXECUTION_BINDING_FILE, SUMS_FILE})
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def safe_flat_name(value: object, code: str) -> str:
    require(isinstance(value, str) and bool(value), code)
    pure = PurePosixPath(value)
    require(not pure.is_absolute() and len(pure.parts) == 1 and pure.name == value and ".." not in pure.parts, code)
    return value


def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def source_contract(source_sha: str) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "SOURCE_MUST_LAYER_ABOVE_PR194")
    return {
        "schema": SCHEMA,
        "state": "EXECUTION_CLOSURE_BINDING_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_policy_freeze": REPOSITORY_HEAD_AT_POLICY_FREEZE,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 1,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "previous_host_authorization_id": PREVIOUS_HOST_AUTHORIZATION_ID,
        "previous_host_authorization_created": False,
        "previous_request_id": PREVIOUS_REQUEST_ID,
        "previous_request_state": PREVIOUS_REQUEST_STATE,
        "previous_request_reuse_permitted": False,
        "future_host_authorization_id": FUTURE_HOST_AUTHORIZATION_ID,
        "future_physical_d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
        "next_gate": "EXACT_HOST_ONLY_EXECUTION_CLOSURE_PREFLIGHT_AUTHORIZATION",
        **FALSE_BOUNDARY,
    }


def previous_request_disposition(raw_sha256: str | None) -> dict[str, object]:
    if raw_sha256 is not None:
        validate_sha256(raw_sha256, "PREVIOUS_REQUEST_RAW_SHA256_INVALID")
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-execution-closure-superseded-request/1",
        "state": PREVIOUS_REQUEST_STATE,
        "reason": "BINDING_POLICY_REPLACED_BEFORE_AUTHORIZATION",
        "d2_request_id": PREVIOUS_REQUEST_ID,
        "request_raw_sha256": raw_sha256,
        "authorization_id": PREVIOUS_HOST_AUTHORIZATION_ID,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "request_reuse_permitted": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "physical_execution_occurred": False,
        **{key: value for key, value in FALSE_BOUNDARY.items() if key not in {
            "authorization_created", "authorization_claimed", "authorization_consumed"
        }},
    }


def build_execution_closure_manifest(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "EXECUTION_ROOT_INVALID")
    entries: list[dict[str, str]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in CONTROL_FILES:
            continue
        safe_flat_name(path.name, "EXECUTION_CLOSURE_MEMBER_NAME_INVALID")
        entries.append({"name": path.name, "sha256": sha256_file(path)})
    require(bool(entries), "EXECUTION_CLOSURE_EMPTY")
    manifest: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA,
        "policy_version": 1,
        "execution_closure_role": "BLOCKING",
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "files": entries,
    }
    manifest["execution_closure_sha256"] = canonical_json_sha256(manifest)
    return manifest


def validate_execution_closure(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "EXECUTION_ROOT_INVALID")
    manifest = load_json(root / CLOSURE_MANIFEST_FILE, "EXECUTION_CLOSURE_MANIFEST_INVALID")
    require(manifest.get("schema") == CLOSURE_SCHEMA, "EXECUTION_CLOSURE_SCHEMA_MISMATCH")
    supplied = manifest.get("execution_closure_sha256")
    without = dict(manifest)
    without.pop("execution_closure_sha256", None)
    require(supplied == canonical_json_sha256(without), "EXECUTION_CLOSURE_DIGEST_MISMATCH")
    validate_sha256(supplied, "EXECUTION_CLOSURE_DIGEST_INVALID")
    require(manifest.get("policy_version") == 1, "EXECUTION_CLOSURE_POLICY_VERSION_MISMATCH")
    require(manifest.get("execution_closure_role") == "BLOCKING", "EXECUTION_CLOSURE_ROLE_MISMATCH")
    require(manifest.get("repository_head_role") == "AUDIT_ONLY", "REPOSITORY_HEAD_ROLE_MISMATCH")
    require(manifest.get("repository_head_enforced") is False, "REPOSITORY_HEAD_MUST_NOT_BLOCK")

    raw_entries = manifest.get("files")
    require(isinstance(raw_entries, list) and raw_entries, "EXECUTION_CLOSURE_FILES_INVALID")
    expected: dict[str, str] = {}
    for entry in raw_entries:
        require(isinstance(entry, dict), "EXECUTION_CLOSURE_FILE_ENTRY_INVALID")
        name = safe_flat_name(entry.get("name"), "EXECUTION_CLOSURE_MEMBER_NAME_INVALID")
        digest = validate_sha256(entry.get("sha256"), "EXECUTION_CLOSURE_MEMBER_DIGEST_INVALID")
        require(name not in expected and name not in CONTROL_FILES, "EXECUTION_CLOSURE_MEMBER_DUPLICATE")
        expected[name] = digest
    require(list(expected) == sorted(expected), "EXECUTION_CLOSURE_INVENTORY_NOT_SORTED")
    observed = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name not in CONTROL_FILES
    }
    require(set(expected) == observed, "EXECUTION_CLOSURE_INVENTORY_MISMATCH")
    for name, digest in expected.items():
        target = root / name
        require(target.is_file() and not target.is_symlink(), "EXECUTION_CLOSURE_MEMBER_INVALID")
        require(sha256_file(target) == digest, "EXECUTION_CLOSURE_MEMBER_DIGEST_MISMATCH")

    binding = load_json(root / EXECUTION_BINDING_FILE, "EXECUTION_BINDING_INVALID")
    require(binding.get("schema") == EXECUTION_BINDING_SCHEMA, "EXECUTION_BINDING_SCHEMA_MISMATCH")
    require(binding.get("execution_closure_sha256") == supplied, "EXECUTION_BINDING_CLOSURE_MISMATCH")
    require(binding.get("execution_closure_role") == "BLOCKING", "EXECUTION_BINDING_CLOSURE_ROLE_MISMATCH")
    require(binding.get("repository_head_role") == "AUDIT_ONLY", "EXECUTION_BINDING_REPOSITORY_ROLE_MISMATCH")
    require(binding.get("repository_head_enforced") is False, "EXECUTION_BINDING_REPOSITORY_ENFORCEMENT_MISMATCH")
    validate_sha40(binding.get("repository_head_sha_at_package_build"), "EXECUTION_BINDING_REPOSITORY_HEAD_INVALID")
    return {"manifest": manifest, "binding": binding}


def validate_repository_audit(value: Mapping[str, Any]) -> None:
    validate_sha40(value.get("repository_head_sha"), "REPOSITORY_HEAD_SHA_INVALID")
    require(value.get("repository_head_role") == "AUDIT_ONLY", "REPOSITORY_HEAD_ROLE_INVALID")
    require(value.get("repository_head_enforced") is False, "REPOSITORY_HEAD_ENFORCEMENT_INVALID")
    drift = value.get("non_execution_drift_files")
    require(isinstance(drift, list) and len(drift) <= 256, "NON_EXECUTION_DRIFT_INVALID")
    for item in drift:
        require(isinstance(item, str) and item and not item.startswith("/") and ".." not in PurePosixPath(item).parts,
                "NON_EXECUTION_DRIFT_PATH_INVALID")


def build_request_draft(
    *, source_sha: str, review_binding_sha256: str, execution_package_sha256: str,
    execution_closure_sha256: str, execution_wrapper_sha256: str,
    execution_launcher_sha256: str, previous_request_raw_sha256: str,
) -> dict[str, Any]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    for name, value in {
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_closure_sha256": execution_closure_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "previous_request_raw_sha256": previous_request_raw_sha256,
    }.items():
        validate_sha256(value, name.upper() + "_INVALID")
    return {
        "schema": REQUEST_SCHEMA,
        "state": "EXECUTION_CLOSURE_BOUND_PHYSICAL_D2_REQUEST_DRAFT_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
        "source_sha": source_sha,
        "host_final_preflight_source_sha": source_sha,
        "repository_head_sha": REPOSITORY_HEAD_AT_POLICY_FREEZE,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "non_execution_drift_files": [],
        "execution_closure_sha256": execution_closure_sha256,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 1,
        "review_binding_sha256": review_binding_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_wrapper_sha256": execution_wrapper_sha256,
        "execution_launcher_sha256": execution_launcher_sha256,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "previous_request_id": PREVIOUS_REQUEST_ID,
        "previous_request_state": PREVIOUS_REQUEST_STATE,
        "previous_request_raw_sha256": previous_request_raw_sha256,
        "previous_request_reuse_permitted": False,
        "future_host_authorization_id": FUTURE_HOST_AUTHORIZATION_ID,
        "host_preflight_result_sha256": None,
        "request_binding_sha256": None,
        "issued_at": None,
        "expires_at": None,
        **FALSE_BOUNDARY,
    }


def finalize_request(draft: Mapping[str, Any], host_result_sha256: str) -> dict[str, Any]:
    validate_sha256(host_result_sha256, "HOST_RESULT_SHA256_INVALID")
    require(draft.get("schema") == REQUEST_SCHEMA, "REQUEST_DRAFT_SCHEMA_MISMATCH")
    require(draft.get("d2_request_id") == NEW_PHYSICAL_D2_REQUEST_ID, "REQUEST_DRAFT_ID_MISMATCH")
    require(draft.get("authorized") is False and draft.get("request_binding_sha256") is None,
            "REQUEST_DRAFT_ALREADY_FINALIZED_OR_AUTHORIZED")
    value = dict(draft)
    value["state"] = "EXECUTION_CLOSURE_BOUND_PHYSICAL_D2_REQUEST_AWAITING_EXACT_AUTHORIZATION"
    value["host_preflight_result_sha256"] = host_result_sha256
    without_binding = dict(value)
    without_binding.pop("request_binding_sha256", None)
    value["request_binding_sha256"] = canonical_json_sha256(without_binding)
    return value


def validate_host_authorization(
    value: Mapping[str, Any], *, review_binding: Mapping[str, Any],
    review_archive_sha256: str, execution_package_sha256: str,
    execution_closure_sha256: str, now: datetime | None = None,
) -> dict[str, Any]:
    require(value.get("schema") == HOST_AUTH_SCHEMA, "HOST_AUTH_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == FUTURE_HOST_AUTHORIZATION_ID, "HOST_AUTH_ID_MISMATCH")
    require(value.get("operation") == HOST_AUTH_OPERATION, "HOST_AUTH_OPERATION_MISMATCH")
    require(value.get("authorized") is True, "HOST_AUTH_NOT_GRANTED")
    require(value.get("one_shot") is True, "HOST_AUTH_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False, "HOST_AUTH_REPLAY_EXPANDED")
    require(value.get("automatic_retry_permitted") is False, "HOST_AUTH_RETRY_EXPANDED")
    issued = utc(value.get("issued_at"), "HOST_AUTH_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "HOST_AUTH_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires and 0 < (expires - issued).total_seconds() <= 7200,
            "HOST_AUTH_WINDOW_INVALID")
    validate_repository_audit(value)
    exact = {
        "source_sha": review_binding.get("source_sha"),
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "review_binding_sha256": review_binding.get("review_binding_sha256"),
        "review_archive_sha256": review_archive_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_closure_sha256": execution_closure_sha256,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 1,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "previous_request_id": PREVIOUS_REQUEST_ID,
        "previous_request_state": PREVIOUS_REQUEST_STATE,
        "new_physical_d2_request_id": NEW_PHYSICAL_D2_REQUEST_ID,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "HOST_AUTH_" + key.upper() + "_MISMATCH")
    for key in (
        "board_operation_authorized", "usb_enumeration_authorized", "serial_operation_authorized",
        "esptool_operation_authorized", "flash_operation_authorized", "physical_nvs_operation_authorized",
        "network_operation_authorized", "broker_operation_authorized", "prepare_authorized",
        "verify_authorized", "activate_authorized", "cleanup_authorized", "ready_authorized",
        "merge_authorized", "release_authorized", "tag_authorized", "deployment_authorized",
    ):
        require(value.get(key) is False, "HOST_AUTH_BOUNDARY_" + key.upper())
    without = dict(value)
    observed = without.pop("authorization_record_sha256", None)
    require(observed == canonical_json_sha256(without), "HOST_AUTH_RECORD_DIGEST_MISMATCH")
    return dict(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        value = source_contract(args.source_sha)
    except ContractError as exc:
        print(json.dumps({"status": "FAIL", "failure_code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
