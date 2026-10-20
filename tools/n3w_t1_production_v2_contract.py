#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

RELEASE_SCHEMA = "gh.n3w-t1-production-v2-release/1"
PLAN_SCHEMA = "gh.n3w-t1-production-v2-plan/1"
RESULT_SCHEMA = "gh.n3w-t1-production-v2-result/1"
RUN_MARKER_SCHEMA = "gh.n3w-t1-production-v2-run/1"
RUN_CONTEXT_SCHEMA = "gh.n3w-t1-production-v2-run-context/1"
FORENSIC_SCHEMA = "gh.n3w-t1-production-v2-forensics/1"

SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
RUN_ID_RE = SHA256_RE

REQUIRED_RELEASE_ARTIFACTS = frozenset(
    {
        "f3_payload",
        "f3_image",
        "f4_control",
        "reboot_control",
        "v2_mac_tools",
        "transport_contract",
    }
)

FORBIDDEN_PUBLIC_KEY_TOKENS = (
    "password",
    "secret",
    "private_key",
    "token",
    "credential",
    "address",
    "hostname",
    "raw_target",
)

V2_ACTIONS = (
    "HOST_BASELINE",
    "F3_DEPLOY",
    "PROVISION",
    "F4_PREPARE",
    "F4_ACTIVATE",
    "F4_ACCEPT",
    "PERSIST_CERT",
    "REBOOT_CONTROL",
    "POST_REBOOT_ACCEPTANCE",
)

RESULT_MARKER_STATES = frozenset({"ABSENT", "STARTED", "ACCEPTED"})
RESULT_ERROR_CLASSES = frozenset(
    {
        "NONE",
        "PRE_MUTATION_FAIL",
        "MUTATION_FAIL_REFLASH_REQUIRED",
        "POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED",
        "PROCESS_CLEANUP_FAIL",
    }
)


class ProductionV2ContractError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    except (TypeError, ValueError) as error:
        raise ProductionV2ContractError("document_not_canonical_json") from error


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProductionV2ContractError(f"{name}_not_object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ProductionV2ContractError(f"{name}_keys_invalid")


def _sha(value: Any, name: str, *, git: bool = False) -> str:
    pattern = GIT_SHA_RE if git else SHA256_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ProductionV2ContractError(f"{name}_invalid")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ProductionV2ContractError(f"{name}_invalid")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ProductionV2ContractError(f"{name}_invalid")
    return value


def _positive_int(value: Any, name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProductionV2ContractError(f"{name}_invalid")
    return value


def validate_release(document: Any) -> dict[str, Any]:
    value = deepcopy(_mapping(document, "release"))
    _exact_keys(
        value,
        {
            "schema",
            "release_id",
            "source_head",
            "source_tree",
            "os_contract",
            "packages",
            "apt_source_policy",
            "artifacts",
            "capacity",
            "public_evidence_fields",
        },
        "release",
    )
    if value["schema"] != RELEASE_SCHEMA:
        raise ProductionV2ContractError("release_schema_invalid")
    _sha(value["release_id"], "release_id")
    _sha(value["source_head"], "source_head", git=True)
    _sha(value["source_tree"], "source_tree", git=True)

    os_contract = _mapping(value["os_contract"], "os_contract")
    _exact_keys(
        os_contract,
        {
            "ID",
            "VERSION_ID",
            "VERSION_CODENAME",
            "PRETTY_NAME",
            "BOARD",
            "BOARD_NAME",
            "VERSION",
            "BRANCH",
            "ARCH",
            "IMAGE_TYPE",
            "kernel_arch",
        },
        "os_contract",
    )
    for key, item in os_contract.items():
        _text(item, f"os_contract_{key}")

    packages = _mapping(value["packages"], "packages")
    _exact_keys(packages, {"docker.io", "docker-compose-v2"}, "packages")
    for name, version in packages.items():
        _text(version, f"package_{name}")

    apt_policy = _mapping(value["apt_source_policy"], "apt_source_policy")
    _exact_keys(
        apt_policy,
        {"host", "suite", "component", "architecture"},
        "apt_source_policy",
    )
    for key, item in apt_policy.items():
        _text(item, f"apt_source_policy_{key}")

    artifacts = _mapping(value["artifacts"], "artifacts")
    if not REQUIRED_RELEASE_ARTIFACTS.issubset(artifacts):
        raise ProductionV2ContractError("release_artifacts_missing")
    for name, record_raw in artifacts.items():
        _text(name, "artifact_name")
        record = _mapping(record_raw, f"artifact_{name}")
        _exact_keys(record, {"sha256", "size_bytes"}, f"artifact_{name}")
        _sha(record["sha256"], f"artifact_{name}_sha256")
        _positive_int(record["size_bytes"], f"artifact_{name}_size_bytes", allow_zero=True)

    capacity = _mapping(value["capacity"], "capacity")
    _exact_keys(capacity, {"minimum_post_peak_free_bytes"}, "capacity")
    _positive_int(
        capacity["minimum_post_peak_free_bytes"],
        "minimum_post_peak_free_bytes",
    )

    fields = value["public_evidence_fields"]
    if not isinstance(fields, list) or not fields or len(set(fields)) != len(fields):
        raise ProductionV2ContractError("public_evidence_fields_invalid")
    for field in fields:
        text = _text(field, "public_evidence_field")
        lowered = text.casefold()
        if any(token in lowered for token in FORBIDDEN_PUBLIC_KEY_TOKENS):
            raise ProductionV2ContractError("public_evidence_field_sensitive")
    return value


def validate_plan(document: Any) -> dict[str, Any]:
    value = deepcopy(_mapping(document, "plan"))
    _exact_keys(
        value,
        {
            "schema",
            "run_id",
            "release_id",
            "release_sha256",
            "source_head",
            "target_binding_sha256",
            "ssh_host_key_sha256",
            "actions",
        },
        "plan",
    )
    if value["schema"] != PLAN_SCHEMA:
        raise ProductionV2ContractError("plan_schema_invalid")
    _sha(value["run_id"], "run_id")
    _sha(value["release_id"], "release_id")
    _sha(value["release_sha256"], "release_sha256")
    _sha(value["source_head"], "source_head", git=True)
    _sha(value["target_binding_sha256"], "target_binding_sha256")
    _sha(value["ssh_host_key_sha256"], "ssh_host_key_sha256")
    if value["actions"] != list(V2_ACTIONS):
        raise ProductionV2ContractError("plan_actions_invalid")
    return value


def validate_run_context(document: Any) -> dict[str, Any]:
    value = deepcopy(_mapping(document, "run_context"))
    _exact_keys(
        value,
        {
            "schema",
            "run_id",
            "release_id",
            "release_sha256",
            "source_head",
            "target_binding_sha256",
            "production_marker_sha256",
            "action",
        },
        "run_context",
    )
    if value["schema"] != RUN_CONTEXT_SCHEMA:
        raise ProductionV2ContractError("run_context_schema_invalid")
    _sha(value["run_id"], "run_id")
    _sha(value["release_id"], "release_id")
    _sha(value["release_sha256"], "release_sha256")
    _sha(value["source_head"], "source_head", git=True)
    _sha(value["target_binding_sha256"], "target_binding_sha256")
    _sha(value["production_marker_sha256"], "production_marker_sha256")
    if value["action"] != "F3_DEPLOY":
        raise ProductionV2ContractError("run_context_action_invalid")
    return value


def validate_marker(document: Any) -> dict[str, Any]:
    value = deepcopy(_mapping(document, "marker"))
    base = {
        "schema",
        "run_id",
        "release_id",
        "release_sha256",
        "source_head",
        "target_binding_sha256",
        "ssh_host_key_sha256",
        "plan_sha256",
        "state",
        "replay_allowed",
        "created_at",
    }
    state = value.get("state")
    expected = base if state == "STARTED" else base | {
        "acceptance_sha256",
        "accepted_at",
        "T1_PRODUCTION_READY",
    }
    _exact_keys(value, expected, "marker")
    if value["schema"] != RUN_MARKER_SCHEMA:
        raise ProductionV2ContractError("marker_schema_invalid")
    for name in (
        "run_id",
        "release_id",
        "release_sha256",
        "target_binding_sha256",
        "ssh_host_key_sha256",
        "plan_sha256",
    ):
        _sha(value[name], name)
    _sha(value["source_head"], "source_head", git=True)
    if state not in {"STARTED", "ACCEPTED"}:
        raise ProductionV2ContractError("marker_state_invalid")
    if _bool(value["replay_allowed"], "replay_allowed") is not False:
        raise ProductionV2ContractError("marker_replay_allowed_invalid")
    _text(value["created_at"], "created_at")
    if state == "ACCEPTED":
        _sha(value["acceptance_sha256"], "acceptance_sha256")
        _text(value["accepted_at"], "accepted_at")
        if _bool(value["T1_PRODUCTION_READY"], "T1_PRODUCTION_READY") is not True:
            raise ProductionV2ContractError("marker_ready_invalid")
    return value


def validate_result(document: Any) -> dict[str, Any]:
    value = deepcopy(_mapping(document, "result"))
    _exact_keys(
        value,
        {
            "schema",
            "status",
            "release_id",
            "release_sha256",
            "source_head",
            "run_id_sha256",
            "target_binding_sha256",
            "marker_state",
            "error_class",
            "device_acceptance",
            "T1_PRODUCTION_READY",
            "operator_session_closed",
            "evidence_complete",
            "reflash_required",
            "terminal_stage",
            "private_result_sha256",
        },
        "result",
    )
    if value["schema"] != RESULT_SCHEMA:
        raise ProductionV2ContractError("result_schema_invalid")
    if value["status"] not in {"PASS", "FAIL"}:
        raise ProductionV2ContractError("result_status_invalid")
    for name in (
        "release_id",
        "release_sha256",
        "run_id_sha256",
        "target_binding_sha256",
        "private_result_sha256",
    ):
        _sha(value[name], name)
    _sha(value["source_head"], "source_head", git=True)
    if value["marker_state"] not in RESULT_MARKER_STATES:
        raise ProductionV2ContractError("result_marker_state_invalid")
    if value["error_class"] not in RESULT_ERROR_CLASSES:
        raise ProductionV2ContractError("result_error_class_invalid")
    if value["device_acceptance"] not in {"PASS", "FAIL", "NOT_REACHED"}:
        raise ProductionV2ContractError("device_acceptance_invalid")
    for name in (
        "T1_PRODUCTION_READY",
        "operator_session_closed",
        "evidence_complete",
        "reflash_required",
    ):
        _bool(value[name], name)
    _text(value["terminal_stage"], "terminal_stage")

    marker_state = value["marker_state"]
    error_class = value["error_class"]
    acceptance_pass = value["device_acceptance"] == "PASS"

    if value["T1_PRODUCTION_READY"] is not acceptance_pass:
        raise ProductionV2ContractError("result_acceptance_ready_mismatch")
    if acceptance_pass and value["reflash_required"]:
        raise ProductionV2ContractError("result_accepted_device_reflash_forbidden")

    if marker_state == "ACCEPTED":
        if not acceptance_pass:
            raise ProductionV2ContractError("result_accepted_marker_without_device_acceptance")
        if value["reflash_required"] is not False:
            raise ProductionV2ContractError("result_accepted_marker_with_reflash")
    else:
        if acceptance_pass:
            raise ProductionV2ContractError("result_device_acceptance_without_accepted_marker")
        if value["T1_PRODUCTION_READY"] is not False:
            raise ProductionV2ContractError("result_ready_without_accepted_marker")

    if marker_state == "STARTED":
        if value["status"] != "FAIL":
            raise ProductionV2ContractError("result_started_marker_requires_failure")
        if value["evidence_complete"] is not True:
            raise ProductionV2ContractError("result_started_failure_without_evidence")
        if value["operator_session_closed"] is not True:
            raise ProductionV2ContractError("result_started_failure_without_session_close")
        if value["reflash_required"] is not True:
            raise ProductionV2ContractError("result_started_failure_requires_reflash")
        if error_class not in {
            "MUTATION_FAIL_REFLASH_REQUIRED",
            "POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED",
        }:
            raise ProductionV2ContractError("result_started_error_class_invalid")

    if marker_state == "ABSENT":
        if value["status"] != "FAIL":
            raise ProductionV2ContractError("result_absent_marker_requires_failure")
        if value["device_acceptance"] != "NOT_REACHED":
            raise ProductionV2ContractError("result_absent_marker_device_acceptance_invalid")
        if error_class != "PRE_MUTATION_FAIL":
            raise ProductionV2ContractError("result_absent_marker_error_class_invalid")

    if marker_state == "ACCEPTED" and value["status"] == "FAIL":
        if error_class != "PROCESS_CLEANUP_FAIL":
            raise ProductionV2ContractError("result_accepted_failure_error_class_invalid")

    if value["status"] == "PASS":
        if marker_state != "ACCEPTED":
            raise ProductionV2ContractError("result_pass_without_accepted_marker")
        if error_class != "NONE":
            raise ProductionV2ContractError("result_pass_error_class_invalid")
        if not acceptance_pass:
            raise ProductionV2ContractError("result_pass_without_device_acceptance")
        if value["operator_session_closed"] is not True:
            raise ProductionV2ContractError("result_pass_without_session_close")
        if value["evidence_complete"] is not True:
            raise ProductionV2ContractError("result_pass_without_evidence")
        if value["reflash_required"] is not False:
            raise ProductionV2ContractError("result_pass_with_reflash")
    elif error_class == "NONE":
        raise ProductionV2ContractError("result_failure_without_error_class")
    return value
