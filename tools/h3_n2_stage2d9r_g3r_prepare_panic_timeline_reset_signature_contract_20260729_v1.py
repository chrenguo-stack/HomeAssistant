#!/usr/bin/env python3
"""Contract for realtime PREPARE panic timeline/reset-signature successor -09."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PREPARE-PANIC-TIMELINE-AND-RESET-SIGNATURE-REPAIR-20260729-01"
STAGE = "H3/N2 Stage 2D-9R G3R PREPARE panic timeline and reset-signature repair successor"
REQUEST_09_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-09"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-physical-d2-request/1"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-physical-d2-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-preclaim-marker/1"
PACKAGE_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-execution-package-binding/1"

PR202_HEAD = "62555ff9b196277bf30993b92e5b7868f62dfb64"
PR202_ARTIFACT_ID = 8711435727
PR202_ARTIFACT_SHA256 = "4e83c011d3aba7499f85422c61079dbcd31d343c6c4863854ce6e2e07b2593a8"
PR202_REVIEW_BINDING_SHA256 = "c1308e6e76dd8f4cec85fc70ddfcd52a802b0b9d75df3c0fe1ec7df8df2c60ea"
PR201_ARTIFACT_SHA256 = "e7b407165dfc792eac8e758e854edb70b332fb554e5aae80366379fb13c109a8"
D2_08_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-08"
D2_08_STATUS = "CONSUMED_FAILED"
D2_08_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
D2_08_FAILURE_CODE = "PREPARE_RESULT_TIMEOUT"
D2_08_CLASSIFICATION = "SERIAL_RESET"
D2_08_AUTHORIZATION_SHA256 = "d79b750bc13c7d50ac75954a5b610166d58448956dfe89aae7280c1c00a520b5"
D2_08_TERMINAL_RESULT_SHA256 = "d8b5879113ecc2a5bef8882bd5c3aed0f9b9f601163bae676137e7fcacbdb364"
D2_08_PREPARE_SERIAL_SHA256 = "f853884d12ad5cc7345a7d961c2f5928e6833eaa7dfd0b59965c15fb62ba7a65"
D2_08_PREPARE_BROKER_SHA256 = "dec7d9bc05092d3b59866e807f9c1a87598631c4db4878e9c4d65531c758ef1e"
D2_08_PREPARE_TIMELINE_SHA256 = "0b68d5dabdc436f80c63cc7d3aad5b1023c471319aac831904feea1b05445145"
CORRECTED_BASELINE_SHA256 = "776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f"
INVALID_BASELINE_SHA256 = "0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
IMMUTABLE_PAYLOAD_TAR_SHA256 = "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
RECOVERY_PAYLOAD_TAR_SHA256 = "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
EVIDENCE_POLICY_VERSION = 2
LATE_RESULT_OBSERVATION_WINDOW_SECONDS = 5
CLASSIFICATIONS = ("NO_RESULT", "SERIAL_RESET", "BROKER_DISCONNECT", "LATE_RESULT", "UNRECOGNIZED_RESULT")
NORMALIZED_PANIC_FIELDS = (
    "reset_reason", "panic_class", "core", "mepc", "ra", "saved_pc",
    "backtrace_or_stack_sha256", "first_at", "last_at", "reset_loop_count",
)
BINDING_FILE = "PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_EXECUTION_PACKAGE_BINDING.json"
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
        if name != BINDING_FILE:
            entries.append({"name": name, "sha256": sums[name]})
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-panic-timeline-package-set/1",
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
    binding = _load_json(root / BINDING_FILE, "PACKAGE_BINDING_INVALID")
    require(binding.get("schema") == PACKAGE_BINDING_SCHEMA, "PACKAGE_BINDING_SCHEMA_MISMATCH")
    require(binding.get("execution_package_sha256") == package_digest, "PACKAGE_BINDING_DIGEST_MISMATCH")
    required_files = {
        "execution_wrapper_sha256": "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py",
        "execution_launcher_sha256": "run_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_20260729_v1.sh",
        "panic_timeline_recorder_sha256": "h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1.py",
        "evidence_contract_sha256": "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1.py",
    }
    for key, name in required_files.items():
        require(binding.get(key) == sha256_file(root / name), "PACKAGE_" + key.upper() + "_MISMATCH")
    require(binding.get("evidence_policy_version") == EVIDENCE_POLICY_VERSION, "PACKAGE_EVIDENCE_POLICY_MISMATCH")
    require(binding.get("realtime_byte_receipt_timestamps") is True, "PACKAGE_REALTIME_TIMESTAMPS_MISSING")
    require(binding.get("monotonic_timestamps") is True, "PACKAGE_MONOTONIC_TIMESTAMPS_MISSING")
    require(binding.get("one_reset_event_per_boot") is True, "PACKAGE_RESET_DEDUP_MISSING")
    require(binding.get("immutable_payload_tar_sha256") == IMMUTABLE_PAYLOAD_TAR_SHA256,
            "PACKAGE_IMMUTABLE_PAYLOAD_MISMATCH")
    require(binding.get("recovery_payload_tar_sha256") == RECOVERY_PAYLOAD_TAR_SHA256,
            "PACKAGE_RECOVERY_PAYLOAD_MISMATCH")
    return {"package_sha256": package_digest, "binding": binding}


def validate_physical_request(value: dict[str, Any], package_root: Path) -> dict[str, Any]:
    package = validate_execution_package(package_root)
    require(value.get("schema") == REQUEST_SCHEMA, "PHYSICAL_REQUEST_SCHEMA_MISMATCH")
    require(value.get("stage") == STAGE, "PHYSICAL_REQUEST_STAGE_MISMATCH")
    require(value.get("d2_request_id") == REQUEST_09_ID, "PHYSICAL_REQUEST_ID_MISMATCH")
    require(value.get("state") == "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
            "PHYSICAL_REQUEST_STATE_MISMATCH")
    for key in ("authorized", "authorization_created", "authorization_claimed", "authorization_consumed",
                "physical_request_authorized"):
        require(value.get(key) is False, "PHYSICAL_REQUEST_AUTHORIZATION_STATE_EXPANDED")
    require(value.get("replay_permitted") is False and value.get("automatic_retry_permitted") is False,
            "PHYSICAL_REQUEST_RETRY_EXPANDED")
    require(value.get("predecessor_request_id") == D2_08_ID, "PHYSICAL_REQUEST_PREDECESSOR_ID_MISMATCH")
    require(value.get("predecessor_status") == D2_08_STATUS, "PHYSICAL_REQUEST_PREDECESSOR_STATUS_MISMATCH")
    require(value.get("predecessor_terminal_state") == D2_08_TERMINAL_STATE,
            "PHYSICAL_REQUEST_PREDECESSOR_TERMINAL_STATE_MISMATCH")
    require(value.get("predecessor_failure_code") == D2_08_FAILURE_CODE,
            "PHYSICAL_REQUEST_PREDECESSOR_FAILURE_MISMATCH")
    require(value.get("predecessor_terminal_result_sha256") == D2_08_TERMINAL_RESULT_SHA256,
            "PHYSICAL_REQUEST_PREDECESSOR_RESULT_MISMATCH")
    require(value.get("predecessor_evidence_classification") == D2_08_CLASSIFICATION,
            "PHYSICAL_REQUEST_PREDECESSOR_CLASSIFICATION_MISMATCH")
    require(value.get("baseline_state_sha256") == CORRECTED_BASELINE_SHA256, "PHYSICAL_REQUEST_BASELINE_MISMATCH")
    require(value.get("execution_package_sha256") == package["package_sha256"], "PHYSICAL_REQUEST_PACKAGE_MISMATCH")
    for key in ("execution_wrapper_sha256", "execution_launcher_sha256", "panic_timeline_recorder_sha256",
                "evidence_contract_sha256"):
        require(value.get(key) == package["binding"].get(key), "PHYSICAL_REQUEST_" + key.upper() + "_MISMATCH")
    require(value.get("evidence_policy_version") == EVIDENCE_POLICY_VERSION,
            "PHYSICAL_REQUEST_EVIDENCE_POLICY_MISMATCH")
    require(value.get("normalized_panic_fields") == list(NORMALIZED_PANIC_FIELDS),
            "PHYSICAL_REQUEST_PANIC_FIELDS_MISMATCH")
    require(value.get("immutable_payload_tar_sha256") == IMMUTABLE_PAYLOAD_TAR_SHA256,
            "PHYSICAL_REQUEST_IMMUTABLE_PAYLOAD_MISMATCH")
    require(value.get("recovery_payload_tar_sha256") == RECOVERY_PAYLOAD_TAR_SHA256,
            "PHYSICAL_REQUEST_RECOVERY_PAYLOAD_MISMATCH")
    without = dict(value)
    observed = without.pop("request_binding_sha256", None)
    require(observed == canonical_sha256(without), "PHYSICAL_REQUEST_BINDING_MISMATCH")
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
    binding = package["binding"]
    return {
        "schema": AUTH_SCHEMA,
        "stage": STAGE,
        "d2_request_id": REQUEST_09_ID,
        "request_binding_sha256": request["request_binding_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "panic_timeline_recorder_sha256": binding["panic_timeline_recorder_sha256"],
        "evidence_contract_sha256": binding["evidence_contract_sha256"],
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "predecessor_terminal_result_sha256": D2_08_TERMINAL_RESULT_SHA256,
        "predecessor_failure_code": D2_08_FAILURE_CODE,
        "predecessor_evidence_classification": D2_08_CLASSIFICATION,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "prepare_evidence_required": True,
        "prepare_evidence_persist_before_recovery": True,
        "prepare_evidence_persist_before_cleanup": True,
        "realtime_byte_receipt_timestamps": True,
        "monotonic_timestamps": True,
        "one_reset_event_per_boot": True,
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
        "d2_request_id": REQUEST_09_ID,
        "state": "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "source_sha": source_sha,
        "base_pr": 202,
        "base_head_sha": PR202_HEAD,
        "upstream_artifact_id": PR202_ARTIFACT_ID,
        "upstream_artifact_sha256": PR202_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": PR202_REVIEW_BINDING_SHA256,
        "predecessor_request_id": D2_08_ID,
        "predecessor_status": D2_08_STATUS,
        "predecessor_terminal_state": D2_08_TERMINAL_STATE,
        "predecessor_failure_code": D2_08_FAILURE_CODE,
        "predecessor_evidence_classification": D2_08_CLASSIFICATION,
        "predecessor_authorization_record_sha256": D2_08_AUTHORIZATION_SHA256,
        "predecessor_terminal_result_sha256": D2_08_TERMINAL_RESULT_SHA256,
        "predecessor_prepare_serial_sha256": D2_08_PREPARE_SERIAL_SHA256,
        "predecessor_prepare_broker_sha256": D2_08_PREPARE_BROKER_SHA256,
        "predecessor_prepare_timeline_sha256": D2_08_PREPARE_TIMELINE_SHA256,
        "predecessor_replay_permitted": False,
        "baseline_state_sha256": CORRECTED_BASELINE_SHA256,
        "invalid_legacy_baseline_sha256": INVALID_BASELINE_SHA256,
        "invalid_legacy_baseline_reuse_permitted": False,
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "panic_timeline_recorder_sha256": binding["panic_timeline_recorder_sha256"],
        "evidence_contract_sha256": binding["evidence_contract_sha256"],
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "evidence_classifications": list(CLASSIFICATIONS),
        "normalized_panic_fields": list(NORMALIZED_PANIC_FIELDS),
        "late_result_observation_window_seconds": LATE_RESULT_OBSERVATION_WINDOW_SECONDS,
        "realtime_byte_receipt_timestamps": True,
        "monotonic_timestamps": True,
        "capture_phase_partitioning": ["startup", "ready_wait", "ready_observed", "post_command", "late_window", "result"],
        "one_reset_event_per_boot": True,
        "persist_evidence_before_recovery": True,
        "persist_evidence_before_temporary_cleanup": True,
        "local_private_normalized_panic_evidence": True,
        "real_board_evidence_in_public_artifact": False,
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
        "status": "SOURCE_ONLY_PREPARE_PANIC_TIMELINE_RESET_SIGNATURE_CONTRACT",
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_09_ID,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
