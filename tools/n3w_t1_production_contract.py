#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

RELEASE_SCHEMA = "gh.n3w-t1-production-release/1"
PLAN_SCHEMA = "gh.n3w-t1-production-plan/1"
RESULT_SCHEMA = "gh.n3w-t1-production-result/1"
CHECK_POLICY_SCHEMA = "gh.n3w-t1-production-check-policy/1"
RUN_ID_RE = re.compile(r"[0-9a-f]{64}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SOURCE_HEAD_RE = re.compile(r"[0-9a-f]{40}")

PHASES = (
    "HOST_BASELINE",
    "F3_DEPLOY",
    "PROVISION",
    "F4_PREPARE",
    "F4_ACTIVATE",
    "F4_ACCEPT",
    "PERSIST_CERT",
    "REBOOT_CONTROL",
    "FINALIZE",
    "CLOSE_RUN",
)

CHECK_CATALOG = {
    "AUTH.RUN_PHASE": "HARD_STOP",
    "AUTH.TARGET_BINDING": "HARD_STOP",
    "AUTH.RELEASE_BINDING": "HARD_STOP",
    "SSH.HOST_KEY": "HARD_STOP",
    "SSH.CONNECTION_REUSE": "HARD_STOP",
    "RELEASE.EXACT_BYTES": "HARD_STOP",
    "RELEASE.ENVIRONMENT": "HARD_STOP",
    "CAPACITY.POST_PEAK_RESERVE": "HARD_STOP",
    "PROVISION.DEVICE_READY": "HARD_STOP",
    "F4.RUNTIME_ACCEPTED": "HARD_STOP",
    "F4.REBOOT_ACCEPTED": "HARD_STOP",
    "SESSION.CLEANUP": "HARD_STOP",
    "EVIDENCE.COMPLETE": "HARD_STOP",
    "USABILITY.NONCRITICAL": "OVERRIDABLE",
}

PUBLIC_RESULT_FIELDS = frozenset({
    "schema",
    "status",
    "final_outcome",
    "release_id",
    "release_sha256",
    "source_head",
    "run_id_sha256",
    "target_binding_sha256",
    "ssh_host_key_sha256",
    "device_acceptance",
    "operator_session_closed",
    "evidence_complete",
    "override_used",
    "override_check_ids",
    "terminal_phase",
    "board_access",
    "production_service_start",
})

FORBIDDEN_PUBLIC_KEY_TOKENS = (
    "password",
    "secret",
    "private_key",
    "token",
    "credential",
    "locator",
    "address",
    "hostname",
    "raw_target",
)


class ProductionContractError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exact(document: dict[str, Any], expected: set[str], code: str) -> None:
    if set(document) != expected:
        raise ProductionContractError(code)


def _sha(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ProductionContractError(code)
    return value


def _source(value: object, code: str) -> str:
    if not isinstance(value, str) or SOURCE_HEAD_RE.fullmatch(value) is None:
        raise ProductionContractError(code)
    return value


def validate_check_policy(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ProductionContractError("check_policy_invalid")
    _exact(document, {"schema", "allow_overrides"}, "check_policy_fields_invalid")
    if document.get("schema") != CHECK_POLICY_SCHEMA:
        raise ProductionContractError("check_policy_schema_invalid")
    allow = document.get("allow_overrides")
    if not isinstance(allow, list) or not all(isinstance(item, str) for item in allow):
        raise ProductionContractError("check_policy_allowlist_invalid")
    if len(allow) != len(set(allow)):
        raise ProductionContractError("check_policy_allowlist_duplicate")
    if any(CHECK_CATALOG.get(item) != "OVERRIDABLE" for item in allow):
        raise ProductionContractError("check_policy_allowlist_forbidden")
    return {"schema": CHECK_POLICY_SCHEMA, "allow_overrides": list(allow)}


def validate_release(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ProductionContractError("release_invalid")
    _exact(
        document,
        {
            "schema",
            "release_id",
            "source_head",
            "artifacts",
            "environment",
            "check_policy",
            "result_schema",
        },
        "release_fields_invalid",
    )
    if document.get("schema") != RELEASE_SCHEMA:
        raise ProductionContractError("release_schema_invalid")
    release_id = _sha(document.get("release_id"), "release_id_invalid")
    source_head = _source(document.get("source_head"), "release_source_head_invalid")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ProductionContractError("release_artifacts_invalid")
    normalized_artifacts: dict[str, dict[str, str]] = {}
    for name, record in artifacts.items():
        if not isinstance(name, str) or not name or not isinstance(record, dict):
            raise ProductionContractError("release_artifact_record_invalid")
        _exact(record, {"sha256"}, "release_artifact_fields_invalid")
        normalized_artifacts[name] = {
            "sha256": _sha(
                record.get("sha256"),
                f"release_artifact_sha256_invalid:{name}",
            )
        }
    environment = document.get("environment")
    if not isinstance(environment, dict):
        raise ProductionContractError("release_environment_invalid")
    _exact(
        environment,
        {"os", "architecture", "packages"},
        "release_environment_fields_invalid",
    )
    os_record = environment.get("os")
    if not isinstance(os_record, dict):
        raise ProductionContractError("release_os_invalid")
    _exact(os_record, {"id", "version", "codename"}, "release_os_fields_invalid")
    if not all(
        isinstance(os_record.get(key), str) and os_record.get(key)
        for key in ("id", "version", "codename")
    ):
        raise ProductionContractError("release_os_value_invalid")
    if environment.get("architecture") not in {"aarch64", "arm64"}:
        raise ProductionContractError("release_architecture_invalid")
    packages = environment.get("packages")
    if not isinstance(packages, dict) or set(packages) != {
        "docker.io",
        "docker-compose-v2",
    }:
        raise ProductionContractError("release_package_policy_invalid")
    if not all(isinstance(value, str) and value for value in packages.values()):
        raise ProductionContractError("release_package_version_invalid")
    policy = validate_check_policy(document.get("check_policy"))
    if policy["allow_overrides"]:
        raise ProductionContractError("release_override_policy_not_empty")
    if document.get("result_schema") != RESULT_SCHEMA:
        raise ProductionContractError("release_result_schema_invalid")
    normalized = {
        "schema": RELEASE_SCHEMA,
        "release_id": release_id,
        "source_head": source_head,
        "artifacts": normalized_artifacts,
        "environment": {
            "os": dict(os_record),
            "architecture": environment["architecture"],
            "packages": dict(packages),
        },
        "check_policy": policy,
        "result_schema": RESULT_SCHEMA,
    }
    binding = {key: value for key, value in normalized.items() if key != "release_id"}
    if canonical_sha256(binding) != release_id:
        raise ProductionContractError("release_id_binding_invalid")
    return normalized


def validate_plan(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ProductionContractError("plan_invalid")
    _exact(
        document,
        {
            "schema",
            "run_id",
            "release_id",
            "release_sha256",
            "source_head",
            "target_binding_sha256",
            "ssh_host_key_sha256",
            "plan_digest",
            "approved_at",
            "expires_at",
            "max_duration_seconds",
            "phases",
            "reboot_budget",
        },
        "plan_fields_invalid",
    )
    if document.get("schema") != PLAN_SCHEMA:
        raise ProductionContractError("plan_schema_invalid")
    run_id = document.get("run_id")
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ProductionContractError("plan_run_id_invalid")
    _sha(document.get("release_id"), "plan_release_id_invalid")
    _sha(document.get("release_sha256"), "plan_release_sha256_invalid")
    _source(document.get("source_head"), "plan_source_head_invalid")
    _sha(document.get("target_binding_sha256"), "plan_target_binding_invalid")
    _sha(document.get("ssh_host_key_sha256"), "plan_host_key_invalid")
    plan_digest = _sha(document.get("plan_digest"), "plan_digest_invalid")
    approved_at = document.get("approved_at")
    expires_at = document.get("expires_at")
    max_duration = document.get("max_duration_seconds")
    if (
        not isinstance(approved_at, int)
        or isinstance(approved_at, bool)
        or approved_at <= 0
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or expires_at <= approved_at
        or not isinstance(max_duration, int)
        or isinstance(max_duration, bool)
        or max_duration <= 0
        or expires_at - approved_at > max_duration
    ):
        raise ProductionContractError("plan_time_window_invalid")
    if document.get("phases") != list(PHASES):
        raise ProductionContractError("plan_phases_invalid")
    if document.get("reboot_budget") != 1:
        raise ProductionContractError("plan_reboot_budget_invalid")
    normalized = deepcopy(document)
    binding = dict(normalized)
    binding["plan_digest"] = "0" * 64
    if canonical_sha256(binding) != plan_digest:
        raise ProductionContractError("plan_digest_binding_invalid")
    return normalized


def evaluate_check(
    check_id: str,
    status: str,
    *,
    policy: dict[str, Any],
    operator_approved: bool = False,
) -> dict[str, object]:
    if check_id not in CHECK_CATALOG:
        return {
            "check_id": check_id,
            "severity": "HARD_STOP",
            "decision": "STOP",
            "override_used": False,
        }
    severity = CHECK_CATALOG[check_id]
    normalized = validate_check_policy(policy)
    if status == "PASS":
        return {
            "check_id": check_id,
            "severity": severity,
            "decision": "PASS",
            "override_used": False,
        }
    if status != "FAIL":
        return {
            "check_id": check_id,
            "severity": "HARD_STOP",
            "decision": "STOP",
            "override_used": False,
        }
    if (
        severity == "OVERRIDABLE"
        and check_id in normalized["allow_overrides"]
        and operator_approved
    ):
        return {
            "check_id": check_id,
            "severity": severity,
            "decision": "PASS_WITH_OVERRIDE",
            "override_used": True,
        }
    return {
        "check_id": check_id,
        "severity": severity if severity == "OVERRIDABLE" else "HARD_STOP",
        "decision": "STOP",
        "override_used": False,
    }


def final_outcome(
    *,
    device_acceptance: bool,
    operator_session_closed: bool,
    evidence_complete: bool,
    override_check_ids: list[str] | tuple[str, ...],
) -> str:
    if not device_acceptance or not operator_session_closed or not evidence_complete:
        return "FAIL"
    return "PASS_WITH_OVERRIDE" if override_check_ids else "PASS"


def _forbidden(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in FORBIDDEN_PUBLIC_KEY_TOKENS):
                return True
            if _forbidden(item):
                return True
    elif isinstance(value, list):
        return any(_forbidden(item) for item in value)
    return False


def public_result(private_result: object) -> dict[str, Any]:
    if not isinstance(private_result, dict):
        raise ProductionContractError("result_invalid")
    if private_result.get("schema") != RESULT_SCHEMA:
        raise ProductionContractError("result_schema_invalid")
    public = {
        key: deepcopy(value)
        for key, value in private_result.items()
        if key in PUBLIC_RESULT_FIELDS
    }
    if set(public) != PUBLIC_RESULT_FIELDS:
        raise ProductionContractError("public_result_required_field_missing")
    if _forbidden(public):
        raise ProductionContractError("public_result_forbidden_key")
    override_ids = public["override_check_ids"]
    if (
        not isinstance(override_ids, list)
        or not all(isinstance(item, str) for item in override_ids)
        or len(override_ids) != len(set(override_ids))
        or any(CHECK_CATALOG.get(item) != "OVERRIDABLE" for item in override_ids)
    ):
        raise ProductionContractError("result_override_check_ids_invalid")
    expected = final_outcome(
        device_acceptance=public["device_acceptance"] is True,
        operator_session_closed=public["operator_session_closed"] is True,
        evidence_complete=public["evidence_complete"] is True,
        override_check_ids=override_ids,
    )
    if public["final_outcome"] != expected:
        raise ProductionContractError("result_outcome_invalid")
    if public["override_used"] is not bool(public["override_check_ids"]):
        raise ProductionContractError("result_override_flag_invalid")
    return public
