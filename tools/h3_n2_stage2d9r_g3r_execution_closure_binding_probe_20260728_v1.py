#!/usr/bin/env python3
"""One-shot host-only probe for execution-closure binding.

The probe validates the public review package and issues only an unauthorized
physical-D2 request. It never enumerates hardware, opens serial, invokes
esptool, reads private custody, starts a broker, or performs PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_execution_closure_binding_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_execution_closure_binding_packager_20260728_v1 as packager
from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1 import (
    canonical_sha256, parse_sums, sha256_file,
)


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


def validate_review_package(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    sums_path = root / packager.SUMS_FILE
    sums = parse_sums(sums_path.read_bytes())
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() not in {
            packager.SUMS_FILE, packager.REVIEW_ARCHIVE_NAME
        }
    }
    require(set(sums) == observed, "PACKAGE_SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_file(root / name) == digest, "PACKAGE_MEMBER_DIGEST_MISMATCH")

    binding = load_json(
        root / packager.REVIEW_BINDING_FILE,
        expected_mode=None,
        code="REVIEW_BINDING_INVALID",
    )
    supplied = binding.get("review_binding_sha256")
    without = dict(binding)
    without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "REVIEW_BINDING_DIGEST_MISMATCH")
    require(binding.get("schema") == contract.REVIEW_SCHEMA, "REVIEW_BINDING_SCHEMA_MISMATCH")
    require(binding.get("base_pr") == contract.BASE_PR, "REVIEW_BINDING_BASE_PR_MISMATCH")
    require(binding.get("base_head_sha") == contract.BASE_HEAD_SHA, "REVIEW_BINDING_BASE_HEAD_MISMATCH")
    require(binding.get("repository_head_role") == "AUDIT_ONLY", "REVIEW_BINDING_REPOSITORY_ROLE_MISMATCH")
    require(binding.get("repository_head_enforced") is False, "REVIEW_BINDING_REPOSITORY_ENFORCEMENT_MISMATCH")
    require(binding.get("execution_closure_role") == "BLOCKING", "REVIEW_BINDING_CLOSURE_ROLE_MISMATCH")

    execution_root = root / packager.EXECUTION_DIR
    closure = contract.validate_execution_closure(execution_root)
    execution_package_sha256 = packager.canonical_execution_package_digest(execution_root)
    require(binding.get("execution_package_sha256") == execution_package_sha256,
            "REVIEW_BINDING_EXECUTION_PACKAGE_MISMATCH")
    require(binding.get("execution_closure_sha256") == closure["manifest"]["execution_closure_sha256"],
            "REVIEW_BINDING_EXECUTION_CLOSURE_MISMATCH")
    review_archive_sha256 = sha256_file(root / packager.REVIEW_ARCHIVE_NAME)
    draft = load_json(root / packager.REQUEST_FILE, expected_mode=None, code="REQUEST_DRAFT_INVALID")
    require(draft.get("d2_request_id") == contract.NEW_PHYSICAL_D2_REQUEST_ID, "REQUEST_DRAFT_ID_MISMATCH")
    require(draft.get("authorized") is False, "REQUEST_DRAFT_AUTHORIZED")
    require(draft.get("request_binding_sha256") is None, "REQUEST_DRAFT_ALREADY_FINALIZED")
    previous = load_json(
        root / packager.PREVIOUS_DISPOSITION_FILE,
        expected_mode=None,
        code="PREVIOUS_DISPOSITION_INVALID",
    )
    require(previous.get("state") == contract.PREVIOUS_REQUEST_STATE,
            "PREVIOUS_DISPOSITION_STATE_MISMATCH")
    require(previous.get("request_reuse_permitted") is False,
            "PREVIOUS_DISPOSITION_REUSE_EXPANDED")
    return {
        "binding": binding,
        "draft": draft,
        "review_archive_sha256": review_archive_sha256,
        "execution_package_sha256": execution_package_sha256,
        "execution_closure_sha256": closure["manifest"]["execution_closure_sha256"],
    }


def marker_path(state_root: Path) -> Path:
    name = hashlib.sha256(contract.FUTURE_HOST_AUTHORIZATION_ID.encode("utf-8")).hexdigest() + ".json"
    return state_root / name


def claim(marker: Path, authorization: Mapping[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(marker, {
        "schema": contract.HOST_MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
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
        "schema": contract.HOST_MARKER_SCHEMA,
        "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
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
    validated = validate_review_package(package_root)
    authorization_path = args.authorization.expanduser().resolve(strict=True)
    authorization_value = load_json(
        authorization_path, expected_mode="0600", code="AUTHORIZATION_RECORD_INVALID"
    )
    authorization = contract.validate_host_authorization(
        authorization_value,
        review_binding=validated["binding"],
        review_archive_sha256=validated["review_archive_sha256"],
        execution_package_sha256=validated["execution_package_sha256"],
        execution_closure_sha256=validated["execution_closure_sha256"],
    )
    state_root = args.state_root.expanduser().resolve(strict=True)
    require(state_root.is_dir() and not state_root.is_symlink() and mode(state_root) == "0700",
            "STATE_ROOT_INVALID")
    marker = marker_path(state_root)
    claim(marker, authorization)
    try:
        result: dict[str, Any] = {
            "schema": contract.HOST_RESULT_SCHEMA,
            "state": "EXECUTION_CLOSURE_HOST_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION",
            "status": "CONSUMED_PASS",
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "source_sha": validated["binding"]["source_sha"],
            "repository_head_sha": authorization["repository_head_sha"],
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "non_execution_drift_files": authorization["non_execution_drift_files"],
            "execution_closure_sha256": validated["execution_closure_sha256"],
            "execution_closure_role": "BLOCKING",
            "execution_package_sha256": validated["execution_package_sha256"],
            "review_binding_sha256": validated["binding"]["review_binding_sha256"],
            "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
            "physical_request_authorized": False,
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
            "activate_executed": False,
            "cleanup_executed": False,
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        result["host_preflight_result_sha256"] = contract.canonical_json_sha256(result)
        request = contract.finalize_request(validated["draft"], result["host_preflight_result_sha256"])
        write_json_exclusive(args.result_output.expanduser(), result)
        write_json_exclusive(args.request_output.expanduser(), request)
        finish_marker(marker, "CONSUMED_PASS", result["host_preflight_result_sha256"], None)
        return result, request
    except Exception as exc:
        failure = str(exc.args[0]) if exc.args else type(exc).__name__
        failure_result = {
            "schema": contract.HOST_RESULT_SCHEMA,
            "status": "CONSUMED_FAILED",
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "failure_code": failure,
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        failure_result["host_preflight_result_sha256"] = contract.canonical_json_sha256(failure_result)
        finish_marker(marker, "CONSUMED_FAILED", failure_result["host_preflight_result_sha256"], failure)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--request-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result, request = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (ProbeError, contract.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({
            "status": "FAIL",
            "failure_code": str(code),
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result["status"],
        "host_preflight_result_sha256": result["host_preflight_result_sha256"],
        "request_binding_sha256": request["request_binding_sha256"],
        "physical_request_authorized": False,
        "board_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
