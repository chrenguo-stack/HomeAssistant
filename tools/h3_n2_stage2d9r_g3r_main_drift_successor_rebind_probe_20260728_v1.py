#!/usr/bin/env python3
"""One-shot host-only probe for the accepted main-drift successor rebind.

The probe validates only public package material and the two exact public JSON
evidence files produced by the consumed H2. It never enumerates USB/serial,
invokes esptool, touches Flash/NVS, starts a Broker, or executes PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_packager_20260728_v1 as packager
from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import (
    canonical_sha256, parse_sums, sha256_bytes, sha256_file,
)

AUTH_OPERATION = "VALIDATE_CONSUMED_H2_AND_REBIND_ACCEPTED_MAIN_DRIFT"
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def mode(path: Path) -> str:
    return f"{path.stat().st_mode & 0o777:04o}"


def load_json(path: Path, *, expected_mode: str | None, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    if expected_mode is not None:
        require(mode(path) == expected_mode, code + "_MODE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(code) from exc
    require(isinstance(value, dict), code)
    return value


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def replace_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    write_json_exclusive(temporary, value)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def validate_package(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    sums_path = root / packager.SUMS_FILE
    sums = parse_sums(sums_path.read_bytes())
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() not in {packager.SUMS_FILE, packager.REVIEW_ARCHIVE_NAME}
    }
    require(set(sums) == observed, "PACKAGE_SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_file(root / name) == digest, "PACKAGE_MEMBER_DIGEST_MISMATCH")

    binding = load_json(root / packager.BINDING_FILE, expected_mode=None, code="PACKAGE_BINDING_INVALID")
    supplied = binding.get("review_binding_sha256")
    without = dict(binding)
    without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "PACKAGE_BINDING_DIGEST_MISMATCH")
    exact = {
        "state": "MAIN_DRIFT_SUCCESSOR_REBIND_SOURCE_FROZEN_UNAUTHORIZED",
        "decision_id": contract.DECISION_ID,
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
        "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
        "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
        "h2_status": "CONSUMED_PASS",
        "h2_replay_permitted": False,
        "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
        "old_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
        "old_request_state": contract.OLD_PHYSICAL_D2_REQUEST_STATE,
        "old_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
        "old_request_reuse_permitted": False,
        "future_host_rebind_authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
        "future_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        "host_rebind_executed": False,
        "authorized": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "PACKAGE_BINDING_" + key.upper() + "_MISMATCH")

    draft = load_json(root / packager.REQUEST_FILE, expected_mode=None, code="REQUEST_DRAFT_INVALID")
    require(draft.get("d2_request_id") == contract.NEW_PHYSICAL_D2_REQUEST_ID, "REQUEST_DRAFT_ID_MISMATCH")
    require(draft.get("main_sha") == contract.ACCEPTED_CURRENT_MAIN_SHA, "REQUEST_DRAFT_MAIN_MISMATCH")
    require(draft.get("request_binding_sha256") is None, "REQUEST_DRAFT_PREMATURELY_FINALIZED")
    require(draft.get("authorized") is False, "REQUEST_DRAFT_AUTHORIZED")
    stale = load_json(root / packager.STALE_FILE, expected_mode=None, code="STALE_DISPOSITION_INVALID")
    require(stale == contract.stale_request_disposition(), "STALE_DISPOSITION_MISMATCH")

    upstream_path = root / packager.UPSTREAM_ARTIFACT_NAME
    packager.validate_upstream_artifact(upstream_path)
    execution_root = root / packager.EXECUTION_DIR
    exec_sums = parse_sums((execution_root / packager.SUMS_FILE).read_bytes())
    observed_exec = {path.name for path in execution_root.iterdir() if path.is_file() and path.name != packager.SUMS_FILE}
    require(set(exec_sums) == observed_exec, "EXECUTION_SUMS_INVENTORY_MISMATCH")
    for name, digest in exec_sums.items():
        require(sha256_file(execution_root / name) == digest, "EXECUTION_MEMBER_DIGEST_MISMATCH")
    execution_digest = packager.canonical_execution_package_digest(execution_root)
    require(execution_digest == binding.get("execution_package_sha256"), "EXECUTION_PACKAGE_DIGEST_MISMATCH")
    require(sha256_file(execution_root / packager.NEW_WRAPPER) == binding.get("execution_wrapper_sha256"), "EXECUTION_WRAPPER_DIGEST_MISMATCH")
    require(sha256_file(execution_root / packager.NEW_LAUNCHER) == binding.get("execution_launcher_sha256"), "EXECUTION_LAUNCHER_DIGEST_MISMATCH")
    archive_sha = sha256_file(root / packager.REVIEW_ARCHIVE_NAME)
    return binding, draft, {
        "review_archive_sha256": archive_sha,
        "execution_package_sha256": execution_digest,
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
    }


def validate_authorization(path: Path, *, binding: Mapping[str, Any], package_digests: Mapping[str, str], now: datetime | None = None) -> dict[str, Any]:
    value = load_json(path, expected_mode="0600", code="AUTHORIZATION_RECORD_INVALID")
    require(value.get("schema") == contract.AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(value.get("operation") == AUTH_OPERATION, "AUTHORIZATION_OPERATION_MISMATCH")
    require(value.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(value.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_EXPANDED")
    require(value.get("automatic_retry_permitted") is False, "AUTHORIZATION_RETRY_EXPANDED")
    issued = utc(value.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires and 0 < (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_WINDOW_INVALID")
    exact = {
        "source_sha": binding["source_sha"],
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
        "review_binding_sha256": binding["review_binding_sha256"],
        "review_archive_sha256": package_digests["review_archive_sha256"],
        "execution_package_sha256": package_digests["execution_package_sha256"],
        "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
        "h2_result_raw_sha256": contract.H2_RESULT_RAW_SHA256,
        "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
        "old_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
        "old_request_raw_sha256": contract.OLD_REQUEST_RAW_SHA256,
        "old_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
        "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    for key in (
        "board_operation_authorized", "usb_enumeration_authorized", "serial_operation_authorized",
        "esptool_operation_authorized", "flash_operation_authorized", "physical_nvs_operation_authorized",
        "network_operation_authorized", "broker_operation_authorized", "prepare_authorized", "verify_authorized",
        "activate_authorized", "cleanup_authorized", "ready_authorized", "merge_authorized", "release_authorized",
        "tag_authorized", "deployment_authorized",
    ):
        require(value.get(key) is False, "AUTHORIZATION_BOUNDARY_" + key.upper())
    without = dict(value)
    observed = without.pop("authorization_record_sha256", None)
    require(observed == contract.canonical_json_sha256(without), "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    return value


def marker_path(state_root: Path) -> Path:
    return state_root / (hashlib.sha256(contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID.encode("utf-8")).hexdigest() + ".json")


def claim(marker: Path, authorization: Mapping[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(marker, {
        "schema": MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
        "status": "CLAIMED",
        "authorization_record_sha256": authorization["authorization_record_sha256"],
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "private_values_included": False,
        "private_paths_included": False,
    })


def finish_marker(marker: Path, status: str, result_sha256: str, failure_code: str | None) -> None:
    replace_json(marker, {
        "schema": MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
        "status": status,
        "terminal_result_sha256": result_sha256,
        "failure_code": failure_code,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "private_values_included": False,
        "private_paths_included": False,
    })


def execute(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = args.package_root.expanduser().resolve(strict=True)
    binding, _draft, package_digests = validate_package(package_root)
    h2_path = args.h2_result.expanduser().resolve(strict=True)
    old_path = args.old_request.expanduser().resolve(strict=True)
    require(sha256_file(h2_path) == contract.H2_RESULT_RAW_SHA256, "H2_RESULT_RAW_DIGEST_MISMATCH")
    require(sha256_file(old_path) == contract.OLD_REQUEST_RAW_SHA256, "OLD_REQUEST_RAW_DIGEST_MISMATCH")
    h2 = contract.validate_h2_result(load_json(h2_path, expected_mode="0600", code="H2_RESULT_INVALID"))
    old = contract.validate_old_request(load_json(old_path, expected_mode="0600", code="OLD_REQUEST_INVALID"))
    authorization = validate_authorization(
        args.authorization.expanduser().resolve(strict=True),
        binding=binding,
        package_digests=package_digests,
    )
    state_root = args.state_root.expanduser().resolve(strict=True)
    require(state_root.is_dir() and not state_root.is_symlink() and mode(state_root) == "0700", "STATE_ROOT_INVALID")
    marker = marker_path(state_root)
    claim(marker, authorization)
    try:
        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "state": "MAIN_DRIFT_SUCCESSOR_REBIND_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION",
            "status": "CONSUMED_PASS",
            "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
            "source_sha": binding["source_sha"],
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
            "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
            "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
            "review_binding_sha256": binding["review_binding_sha256"],
            **package_digests,
            "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
            "h2_status": h2["status"],
            "h2_authorization_consumed": h2["authorization_consumed"],
            "h2_replay_permitted": False,
            "h2_result_raw_sha256": contract.H2_RESULT_RAW_SHA256,
            "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
            "old_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
            "old_request_state": contract.OLD_PHYSICAL_D2_REQUEST_STATE,
            "old_request_raw_sha256": contract.OLD_REQUEST_RAW_SHA256,
            "old_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
            "old_request_authorization_created": old["authorization_created"],
            "old_request_authorization_claimed": old["authorization_claimed"],
            "old_request_authorization_consumed": old["authorization_consumed"],
            "old_request_reuse_permitted": False,
            "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            **{key: value for key, value in contract.FALSE_BOUNDARY.items() if not key.startswith("authorization_") and key != "authorized"},
        }
        result["host_rebind_result_sha256"] = contract.canonical_json_sha256(result)
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        expires = issued + timedelta(hours=2)
        request = contract.build_rebound_request_from_old(
            old,
            source_sha=binding["source_sha"],
            review_binding_sha256=binding["review_binding_sha256"],
            execution_package_sha256=package_digests["execution_package_sha256"],
            execution_wrapper_sha256=package_digests["execution_wrapper_sha256"],
            execution_launcher_sha256=package_digests["execution_launcher_sha256"],
            host_rebind_result_sha256=result["host_rebind_result_sha256"],
            issued_at=issued.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
        )
        write_json_exclusive(args.result_output.expanduser().resolve(strict=False), result)
        write_json_exclusive(args.request_output.expanduser().resolve(strict=False), request)
        finish_marker(marker, "CONSUMED_PASS", result["host_rebind_result_sha256"], None)
        return result, request
    except Exception as exc:
        failure_code = exc.args[0] if isinstance(exc, (ProbeError, contract.ContractError)) and exc.args else type(exc).__name__
        failure: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "state": "MAIN_DRIFT_SUCCESSOR_REBIND_CONSUMED_FAILED",
            "status": "CONSUMED_FAILED",
            "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
            "failure_code": str(failure_code),
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
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
        }
        failure["host_rebind_result_sha256"] = contract.canonical_json_sha256(failure)
        try:
            write_json_exclusive(args.result_output.expanduser().resolve(strict=False), failure)
        finally:
            finish_marker(marker, "CONSUMED_FAILED", failure["host_rebind_result_sha256"], str(failure_code))
        raise


def main() -> int:
    if len(os.sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_EXACT_HOST_REBIND_AUTHORIZATION",
            "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
            "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
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
        }, sort_keys=True))
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--h2-result", type=Path, required=True)
    parser.add_argument("--old-request", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--request-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result, request = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (ProbeError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "host_rebind_result_sha256": result["host_rebind_result_sha256"],
        "request_binding_sha256": request["request_binding_sha256"],
        "authorized": False,
        "physical_d2_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
