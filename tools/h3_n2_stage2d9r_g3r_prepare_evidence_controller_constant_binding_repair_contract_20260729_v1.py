#!/usr/bin/env python3
"""Contract for the PREPARE evidence controller constant-binding repair successor -08."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PREPARE-EVIDENCE-CONTROLLER-CONSTANT-BINDING-REPAIR-20260729-01"
STAGE = "H3/N2 Stage 2D-9R G3R PREPARE evidence controller constant-binding repair successor"
REQUEST_08_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-08"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-physical-d2-request/1"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-physical-d2-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-preclaim-marker/1"
PACKAGE_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-execution-package-binding/1"
EVIDENCE_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-execution-binding/1"

PR201_HEAD = "b5d02e0492401b022605f10ee99f998021104dcf"
PR201_ARTIFACT_ID = 8710636881
PR201_ARTIFACT_SHA256 = "e7b407165dfc792eac8e758e854edb70b332fb554e5aae80366379fb13c109a8"
PR201_REVIEW_BINDING_SHA256 = "66035bcce5d7efd35e3ad98cb4e7aaa078a5cc86759d28ca7f3cb2f818703f5c"
PR200_ARTIFACT_SHA256 = "be9c0e940407391c287f955044d8688255f397d1ca96f28128c91da216eb73a0"
D2_07_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-07"
D2_07_STATUS = "CONSUMED_FAILED"
D2_07_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
D2_07_FAILURE_CODE = "AttributeError"
D2_07_AUTHORIZATION_SHA256 = "0886c73ddbaa2528683d720f5fc7c0db3127e56dcd0d1fd82d54ca4de3cea360"
D2_07_TERMINAL_RESULT_SHA256 = "0c1e8adbcfb23d323330e9f86f7d102eaaad2a37fc61bc2404fe2a32bd7d77dd"
D2_07_PREPARE_CAPTURE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
D2_07_BROKER_LOG_SHA256 = "2d1311a3844db4018d3d5828cd701decb8697a58596b3d55ea6e42811ea88960"
CORRECTED_BASELINE_SHA256 = "776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f"
INVALID_BASELINE_SHA256 = "0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
IMMUTABLE_PAYLOAD_TAR_SHA256 = "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
RECOVERY_PAYLOAD_TAR_SHA256 = "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
EVIDENCE_POLICY_VERSION = 1
LATE_RESULT_OBSERVATION_WINDOW_SECONDS = 5
CLASSIFICATIONS = ("NO_RESULT", "SERIAL_RESET", "BROKER_DISCONNECT", "LATE_RESULT", "UNRECOGNIZED_RESULT")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError("PACKAGE_SUMS_INVALID") from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None, "PACKAGE_SUMS_INVALID")
        name = parts[1]
        pure = PurePosixPath(name)
        require(not pure.is_absolute() and ".." not in pure.parts and pure.name == name, "PACKAGE_SUMS_UNSAFE")
        require(name not in result, "PACKAGE_SUMS_DUPLICATE")
        result[name] = parts[0]
    require(result, "PACKAGE_SUMS_EMPTY")
    return result


def canonical_package_digest(root: Path) -> str:
    sums = parse_sums(root / "SHA256SUMS")
    observed = sorted(path.name for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    require(sorted(sums) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    entries: list[dict[str, str]] = []
    for name in sorted(sums):
        path = root / name
        require(path.is_file() and not path.is_symlink(), "PACKAGE_FILE_INVALID")
        require(sha256_file(path) == sums[name], "PACKAGE_DIGEST_MISMATCH")
        if name != "PREPARE_EVIDENCE_CONTROLLER_REPAIR_EXECUTION_PACKAGE_BINDING.json":
            entries.append({"name": name, "sha256": sums[name]})
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-package-set/1",
        "files": entries,
    })


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_execution_package(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "EXECUTION_PACKAGE_ROOT_INVALID")
    package_digest = canonical_package_digest(root)
    binding = _load_json(root / "PREPARE_EVIDENCE_CONTROLLER_REPAIR_EXECUTION_PACKAGE_BINDING.json", "PACKAGE_BINDING_INVALID")
    evidence = _load_json(root / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_BINDING.json", "EVIDENCE_BINDING_INVALID")
    require(binding.get("schema") == PACKAGE_BINDING_SCHEMA, "PACKAGE_BINDING_SCHEMA_MISMATCH")
    require(evidence.get("schema") == EVIDENCE_BINDING_SCHEMA, "EVIDENCE_BINDING_SCHEMA_MISMATCH")
    require(binding.get("execution_package_sha256") == package_digest, "PACKAGE_BINDING_DIGEST_MISMATCH")
    required_files = {
        "execution_wrapper_sha256": "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py",
        "execution_launcher_sha256": "run_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_20260729_v1.sh",
        "evidence_recorder_sha256": "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py",
        "evidence_overlay_sha256": "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1.py",
        "evidence_contract_sha256": "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1.py",
    }
    for key, name in required_files.items():
        require(binding.get(key) == sha256_file(root / name), "PACKAGE_" + key.upper() + "_MISMATCH")
    require(evidence.get("policy_version") == EVIDENCE_POLICY_VERSION, "EVIDENCE_POLICY_VERSION_MISMATCH")
    require(evidence.get("persist_before_recovery") is True, "EVIDENCE_BEFORE_RECOVERY_MISSING")
    require(evidence.get("persist_before_temporary_cleanup") is True, "EVIDENCE_BEFORE_CLEANUP_MISSING")
    require(evidence.get("classifications") == list(CLASSIFICATIONS), "EVIDENCE_CLASSIFICATIONS_MISMATCH")
    require(evidence.get("late_result_observation_window_seconds") == LATE_RESULT_OBSERVATION_WINDOW_SECONDS,
            "EVIDENCE_LATE_WINDOW_MISMATCH")
    return {"package_sha256": package_digest, "binding": binding, "evidence": evidence}


def validate_physical_request(value: dict[str, Any], package_root: Path) -> dict[str, Any]:
    package = validate_execution_package(package_root)
    require(value.get("schema") == REQUEST_SCHEMA, "PHYSICAL_REQUEST_SCHEMA_MISMATCH")
    require(value.get("stage") == STAGE, "PHYSICAL_REQUEST_STAGE_MISMATCH")
    require(value.get("d2_request_id") == REQUEST_08_ID, "PHYSICAL_REQUEST_ID_MISMATCH")
    require(value.get("state") == "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
            "PHYSICAL_REQUEST_STATE_MISMATCH")
    for key in ("authorized", "authorization_created", "authorization_claimed", "authorization_consumed",
                "physical_request_authorized"):
        require(value.get(key) is False, "PHYSICAL_REQUEST_AUTHORIZATION_STATE_EXPANDED")
    require(value.get("replay_permitted") is False and value.get("automatic_retry_permitted") is False,
            "PHYSICAL_REQUEST_RETRY_EXPANDED")
    require(value.get("predecessor_request_id") == D2_07_ID, "PHYSICAL_REQUEST_PREDECESSOR_ID_MISMATCH")
    require(value.get("predecessor_status") == D2_07_STATUS, "PHYSICAL_REQUEST_PREDECESSOR_STATUS_MISMATCH")
    require(value.get("predecessor_terminal_state") == D2_07_TERMINAL_STATE,
            "PHYSICAL_REQUEST_PREDECESSOR_TERMINAL_STATE_MISMATCH")
    require(value.get("predecessor_failure_code") == D2_07_FAILURE_CODE,
            "PHYSICAL_REQUEST_PREDECESSOR_FAILURE_MISMATCH")
    require(value.get("predecessor_terminal_result_sha256") == D2_07_TERMINAL_RESULT_SHA256,
            "PHYSICAL_REQUEST_PREDECESSOR_RESULT_MISMATCH")
    require(value.get("predecessor_replay_permitted") is False, "PHYSICAL_REQUEST_PREDECESSOR_REPLAY_EXPANDED")
    require(value.get("baseline_state_sha256") == CORRECTED_BASELINE_SHA256, "PHYSICAL_REQUEST_BASELINE_MISMATCH")
    require(value.get("invalid_legacy_baseline_sha256") == INVALID_BASELINE_SHA256,
            "PHYSICAL_REQUEST_INVALID_BASELINE_MISMATCH")
    require(value.get("execution_package_sha256") == package["package_sha256"], "PHYSICAL_REQUEST_PACKAGE_MISMATCH")
    binding = package["binding"]
    for key in ("execution_wrapper_sha256", "execution_launcher_sha256", "evidence_recorder_sha256",
                "evidence_overlay_sha256", "evidence_contract_sha256"):
        require(value.get(key) == binding.get(key), "PHYSICAL_REQUEST_" + key.upper() + "_MISMATCH")
    require(value.get("evidence_policy_version") == EVIDENCE_POLICY_VERSION, "PHYSICAL_REQUEST_EVIDENCE_POLICY_MISMATCH")
    require(value.get("immutable_payload_tar_sha256") == IMMUTABLE_PAYLOAD_TAR_SHA256,
            "PHYSICAL_REQUEST_IMMUTABLE_PAYLOAD_MISMATCH")
    require(value.get("recovery_payload_tar_sha256") == RECOVERY_PAYLOAD_TAR_SHA256,
            "PHYSICAL_REQUEST_RECOVERY_PAYLOAD_MISMATCH")
    without_binding = dict(value)
    observed = without_binding.pop("request_binding_sha256", None)
    require(observed == canonical_sha256(without_binding), "PHYSICAL_REQUEST_BINDING_MISMATCH")
    return value


def _utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def authorization_contract_required(request: dict[str, Any], package_root: Path) -> dict[str, Any]:
    package = validate_execution_package(package_root)
    return {
        "schema": AUTH_SCHEMA,
        "stage": STAGE,
        "d2_request_id": REQUEST_08_ID,
        "request_binding_sha256": request["request_binding_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": package["binding"]["execution_wrapper_sha256"],
        "execution_launcher_sha256": package["binding"]["execution_launcher_sha256"],
        "evidence_recorder_sha256": package["binding"]["evidence_recorder_sha256"],
        "evidence_overlay_sha256": package["binding"]["evidence_overlay_sha256"],
        "evidence_contract_sha256": package["binding"]["evidence_contract_sha256"],
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "predecessor_terminal_result_sha256": D2_07_TERMINAL_RESULT_SHA256,
        "predecessor_failure_code": D2_07_FAILURE_CODE,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "prepare_evidence_required": True,
        "prepare_evidence_persist_before_recovery": True,
        "prepare_evidence_persist_before_cleanup": True,
    }


def validate_authorization_contract(
    authorization: dict[str, Any], request: dict[str, Any], package_root: Path, *, now: datetime | None = None
) -> dict[str, Any]:
    validate_physical_request(request, package_root)
    required = authorization_contract_required(request, package_root)
    for key, expected in required.items():
        require(authorization.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    require(authorization.get("authorized") is True and authorization.get("one_shot") is True,
            "AUTHORIZATION_NOT_GRANTED")
    require(authorization.get("replay_permitted") is False and authorization.get("automatic_retry_permitted") is False,
            "AUTHORIZATION_RETRY_EXPANDED")
    require(authorization.get("activate_authorized") is False and authorization.get("cleanup_authorized") is False,
            "AUTHORIZATION_OPERATION_EXPANDED")
    issued = _utc(authorization.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = _utc(authorization.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires and (expires - issued).total_seconds() <= 7200,
            "AUTHORIZATION_NOT_CURRENT")
    without = dict(authorization)
    digest = without.pop("authorization_record_sha256", None)
    require(digest == canonical_sha256(without), "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    return authorization


def request_template(package_root: Path, *, source_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    package = validate_execution_package(package_root)
    binding = package["binding"]
    value: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_08_ID,
        "state": "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "source_sha": source_sha,
        "base_pr": 201,
        "base_head_sha": PR201_HEAD,
        "upstream_artifact_id": PR201_ARTIFACT_ID,
        "upstream_artifact_sha256": PR201_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": PR201_REVIEW_BINDING_SHA256,
        "predecessor_request_id": D2_07_ID,
        "predecessor_status": D2_07_STATUS,
        "predecessor_terminal_state": D2_07_TERMINAL_STATE,
        "predecessor_failure_code": D2_07_FAILURE_CODE,
        "predecessor_authorization_record_sha256": D2_07_AUTHORIZATION_SHA256,
        "predecessor_terminal_result_sha256": D2_07_TERMINAL_RESULT_SHA256,
        "predecessor_prepare_capture_sha256": D2_07_PREPARE_CAPTURE_SHA256,
        "predecessor_broker_log_sha256": D2_07_BROKER_LOG_SHA256,
        "predecessor_replay_permitted": False,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "invalid_legacy_baseline_reuse_permitted": False,
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "evidence_recorder_sha256": binding["evidence_recorder_sha256"],
        "evidence_overlay_sha256": binding["evidence_overlay_sha256"],
        "evidence_contract_sha256": binding["evidence_contract_sha256"],
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "evidence_classifications": list(CLASSIFICATIONS),
        "late_result_observation_window_seconds": LATE_RESULT_OBSERVATION_WINDOW_SECONDS,
        "persist_evidence_before_recovery": True,
        "persist_evidence_before_temporary_cleanup": True,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_max_count": 1,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_request_authorized": False,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "physical_execution_started": False,
    }
    value["request_binding_sha256"] = canonical_sha256(value)
    return value


if __name__ == "__main__":
    print(json.dumps({
        "status": "SOURCE_ONLY_CONTROLLER_CONSTANT_BINDING_REPAIR_CONTRACT",
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_08_ID,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
