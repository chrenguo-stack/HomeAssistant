#!/usr/bin/env python3
"""One-shot host-only final preflight after payload-handoff repair.

Default invocation is inert. An exact future host authorization may validate the
public package, local toolchain hashes and existing tlsvalid03 custody offline.
No USB/serial enumeration, board access, esptool invocation, Broker start,
network socket, Flash/NVS operation, PREPARE or VERIFY is implemented here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, Mapping

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_common_20260728_v1 import (
    ProbeError,
    AUTH_STATE_RELATIVE,
    CUSTODY_RELATIVE,
    canonical_sha256,
    file_mode,
    load_json,
    probe_toolchain,
    regular,
    replace_json,
    require,
    sha256_bytes,
    sha256_file,
    utc,
    write_json_exclusive,
)
import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_validation_20260728_v1 as frozen_validation
import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_packager_20260728_v1 as packager

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-host-final-preflight-consumption/1"
AUTH_OPERATION = "VALIDATE_PAYLOAD_HANDOFF_REPAIRED_PACKAGE_AND_EXISTING_TLSVALID03_CUSTODY"


def verify_recursive_sums(root: Path) -> dict[str, str]:
    sums_path = root / packager.SUMS_FILE
    regular(sums_path, "0600", "PACKAGE_SUMS_INVALID")
    sums = packager.parse_sums(sums_path.read_bytes())
    observed: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name in (packager.SUMS_FILE, packager.REVIEW_ARCHIVE_NAME):
            continue
        observed.add(name)
    require(set(sums) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        path = (root / name).resolve(strict=True)
        require(path.is_relative_to(root), "PACKAGE_SUM_PATH_OUTSIDE_ROOT")
        regular(path, "0600", "PACKAGE_MEMBER_INVALID")
        require(sha256_file(path) == digest, "PACKAGE_MEMBER_DIGEST_MISMATCH")
    return sums


def validate_review_archive(root: Path, sums: Mapping[str, str]) -> str:
    archive_path = root / packager.REVIEW_ARCHIVE_NAME
    regular(archive_path, "0600", "REVIEW_ARCHIVE_INVALID")
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "REVIEW_ARCHIVE_DUPLICATE_MEMBER")
        require(set(names) == set(sums) | {packager.SUMS_FILE}, "REVIEW_ARCHIVE_INVENTORY_MISMATCH")
        for member in members:
            pure = PurePosixPath(member.name)
            require(member.isfile() and not pure.is_absolute() and ".." not in pure.parts, "REVIEW_ARCHIVE_MEMBER_INVALID")
            require(member.mode == 0o644 and member.uid == 0 and member.gid == 0, "REVIEW_ARCHIVE_METADATA_MISMATCH")
            require(member.uname == "" and member.gname == "" and member.mtime == 0, "REVIEW_ARCHIVE_METADATA_MISMATCH")
            handle = archive.extractfile(member)
            require(handle is not None, "REVIEW_ARCHIVE_MEMBER_UNREADABLE")
            data = handle.read()
            if member.name == packager.SUMS_FILE:
                require(data == (root / packager.SUMS_FILE).read_bytes(), "REVIEW_ARCHIVE_SUMS_MISMATCH")
            else:
                require(sha256_bytes(data) == sums[member.name], "REVIEW_ARCHIVE_DIGEST_MISMATCH")
    return sha256_file(archive_path)


def validate_execution_package(root: Path, binding: Mapping[str, Any]) -> dict[str, str]:
    package = root / packager.EXECUTION_DIR
    require(package.is_dir() and not package.is_symlink(), "EXECUTION_PACKAGE_INVALID")
    sums = packager.parse_sums((package / packager.SUMS_FILE).read_bytes())
    observed = {path.name for path in package.iterdir() if path.is_file() and path.name != packager.SUMS_FILE}
    require(set(sums) == observed, "EXECUTION_PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        regular(package / name, "0600", "EXECUTION_PACKAGE_MEMBER_INVALID")
        require(sha256_file(package / name) == digest, "EXECUTION_PACKAGE_MEMBER_DIGEST_MISMATCH")
    package_sha = packager.canonical_execution_package_digest(package)
    require(package_sha == binding.get("execution_package_sha256"), "EXECUTION_PACKAGE_BINDING_MISMATCH")
    result = {
        "execution_package_sha256": package_sha,
        "execution_wrapper_sha256": sha256_file(package / packager.FINAL_WRAPPER),
        "execution_launcher_sha256": sha256_file(package / packager.FINAL_LAUNCHER),
        "payload_handoff_wrapper_sha256": sha256_file(package / packager.HANDOFF_WRAPPER),
        "repaired_host_controller_sha256": sha256_file(package / packager.SERIAL_REPAIR),
    }
    for key, digest in result.items():
        require(binding.get(key) == digest, "EXECUTION_" + key.upper() + "_MISMATCH")
    execution_binding = load_json(package / "EXECUTION_PACKAGE_BINDING.json", "0600", "EXECUTION_BINDING_INVALID")
    require(execution_binding.get("payload_handoff_contract") == contract.PAYLOAD_HANDOFF_CONTRACT, "EXECUTION_HANDOFF_CONTRACT_MISMATCH")
    require(execution_binding.get("preclaim_failure_contract") == contract.PRECLAIM_FAILURE_CONTRACT, "EXECUTION_PRECLAIM_CONTRACT_MISMATCH")
    require(execution_binding.get("recovery_write_flash_permitted") is False, "EXECUTION_RECOVERY_WRITE_EXPANDED")
    require(execution_binding.get("whole_chip_recovery_erase_permitted") is False, "EXECUTION_RECOVERY_ERASE_EXPANDED")
    return result


def validate_package(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    root = root.expanduser().resolve(strict=True)
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    require(file_mode(root) == "0700", "PACKAGE_ROOT_MODE_INVALID")
    sums = verify_recursive_sums(root)
    archive_sha = validate_review_archive(root, sums)
    binding = load_json(root / packager.BINDING_FILE, "0600", "REVIEW_BINDING_INVALID")
    request = load_json(root / packager.REQUEST_FILE, "0600", "REQUEST_DRAFT_INVALID")
    require(binding.get("schema") == packager.REVIEW_SCHEMA, "REVIEW_BINDING_SCHEMA_MISMATCH")
    require(binding.get("state") == "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED", "REVIEW_BINDING_STATE_MISMATCH")
    without = dict(binding)
    supplied = without.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(without), "REVIEW_BINDING_DIGEST_MISMATCH")
    exact = {
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "payload_repair_review_binding_sha256": contract.PAYLOAD_REPAIR_REVIEW_BINDING_SHA256,
        "payload_repair_execution_package_sha256": contract.PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256,
        "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
        "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
        "old_physical_d2_replay_permitted": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "REVIEW_BINDING_" + key.upper() + "_MISMATCH")
    require(request.get("schema") == contract.REQUEST_SCHEMA, "REQUEST_SCHEMA_MISMATCH")
    require(request.get("authorized") is False, "REQUEST_AUTHORIZED_PREMATURELY")
    require(request.get("host_preflight_result_sha256") is None, "REQUEST_PREFLIGHT_PREPOPULATED")
    require(request.get("review_binding_sha256") == supplied, "REQUEST_REVIEW_BINDING_MISMATCH")
    repair_path = root / packager.REPAIR_ARTIFACT_NAME
    require(sha256_file(repair_path) == contract.PAYLOAD_REPAIR_ARTIFACT_SHA256, "PACKAGE_REPAIR_ARTIFACT_DIGEST_MISMATCH")
    packager.validate_repair_artifact(repair_path)
    execution = validate_execution_package(root, binding)
    return binding, request, {"review_archive_sha256": archive_sha, **execution}


def validate_authorization(
    path: Path,
    *,
    binding: Mapping[str, Any],
    package_digests: Mapping[str, str],
    toolchain: Mapping[str, Any],
    custody_root: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    value = load_json(path, "0600", "AUTHORIZATION_RECORD_INVALID")
    require(value.get("schema") == AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == contract.FUTURE_HOST_AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
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
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "review_binding_sha256": binding["review_binding_sha256"],
        "review_archive_sha256": package_digests["review_archive_sha256"],
        "execution_package_sha256": package_digests["execution_package_sha256"],
        "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
        "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
        "python_executable_sha256": toolchain["python_executable_sha256"],
        "openssl_executable_sha256": toolchain["openssl_executable_sha256"],
        "esptool_executable_sha256": toolchain["esptool_executable_sha256"],
        "esptool_module_sha256": toolchain["esptool_module_sha256"],
        "pyserial_module_sha256": toolchain["pyserial_module_sha256"],
        "mosquitto_executable_sha256": toolchain["mosquitto_executable_sha256"],
        "custody_root_digest_sha256": sha256_bytes(str(custody_root).encode("utf-8")),
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
    require(observed == canonical_sha256(without), "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    return value


def claim(marker: Path, authorization: Mapping[str, Any]) -> None:
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json_exclusive(marker, {
        "schema": MARKER_SCHEMA,
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
        "secret_values_included": False,
        "private_paths_included": False,
    })


def finish_marker(marker: Path, status: str, result_sha256: str, failure_code: str | None) -> None:
    replace_json(marker, {
        "schema": MARKER_SCHEMA,
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
        "secret_values_included": False,
        "private_paths_included": False,
    })


def execute(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = args.package_root.expanduser().resolve(strict=True)
    binding, request_template, package_digests = validate_package(package_root)
    toolchain = probe_toolchain(args)
    home = args.home.expanduser().resolve(strict=True)
    custody = (home / CUSTODY_RELATIVE).resolve(strict=True)
    authorization = validate_authorization(
        args.authorization.expanduser().resolve(strict=True),
        binding=binding,
        package_digests=package_digests,
        toolchain=toolchain,
        custody_root=custody,
    )
    marker = (home / AUTH_STATE_RELATIVE / (sha256_bytes(contract.FUTURE_HOST_AUTHORIZATION_ID.encode("utf-8")) + ".json")).resolve(strict=False)
    claim(marker, authorization)
    try:
        custody_result = frozen_validation.validate_private_custody(custody, toolchain["openssl_path"])
        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "state": "PAYLOAD_HANDOFF_HOST_FINAL_PREFLIGHT_PASS_AWAITING_EXACT_PHYSICAL_D2_DECISION",
            "status": "CONSUMED_PASS",
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "source_sha": binding["source_sha"],
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
            "review_binding_sha256": binding["review_binding_sha256"],
            **package_digests,
            **custody_result,
            "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
            "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
            "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
            "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
            "old_physical_d2_replay_permitted": False,
            "python_executable_sha256": toolchain["python_executable_sha256"],
            "openssl_executable_sha256": toolchain["openssl_executable_sha256"],
            "esptool_executable_sha256": toolchain["esptool_executable_sha256"],
            "esptool_module_sha256": toolchain["esptool_module_sha256"],
            "pyserial_module_sha256": toolchain["pyserial_module_sha256"],
            "mosquitto_executable_sha256": toolchain["mosquitto_executable_sha256"],
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
            "ready": False,
            "merge": False,
            "release": False,
            "tag": False,
            "deployment": False,
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        result["preflight_result_sha256"] = canonical_sha256(result)
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        expires = issued + timedelta(hours=2)
        request = contract.finalize_request(
            request_template,
            host_preflight_result_sha256=result["preflight_result_sha256"],
            toolchain={key: toolchain[key] for key in (
                "python_executable_sha256", "openssl_executable_sha256", "esptool_executable_sha256",
                "esptool_module_sha256", "pyserial_module_sha256", "mosquitto_executable_sha256",
            )},
            issued_at=issued.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
        )
        write_json_exclusive(args.preflight_output, result)
        write_json_exclusive(args.request_output, request)
        finish_marker(marker, "CONSUMED_PASS", result["preflight_result_sha256"], None)
        return result, request
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        failure = {
            "schema": RESULT_SCHEMA,
            "status": "CONSUMED_FAILED",
            "failure_code": str(code),
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
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
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        failure["preflight_result_sha256"] = canonical_sha256(failure)
        if not args.preflight_output.exists():
            write_json_exclusive(args.preflight_output, failure)
        finish_marker(marker, "CONSUMED_FAILED", failure["preflight_result_sha256"], str(code))
        raise ProbeError(str(code)) from exc


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--probe-host", action="store_true")
    value.add_argument("--package-root", type=Path)
    value.add_argument("--authorization", type=Path)
    value.add_argument("--preflight-output", type=Path)
    value.add_argument("--request-output", type=Path)
    value.add_argument("--home", type=Path, default=Path.home())
    value.add_argument("--openssl")
    value.add_argument("--esptool")
    value.add_argument("--mosquitto")
    return value


def main() -> int:
    args = parser().parse_args()
    if not args.probe_host:
        print(json.dumps({
            "status": "SOURCE_ONLY_AWAITING_EXACT_HOST_PREFLIGHT_AUTHORIZATION",
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
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
            "private_values_included": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }, sort_keys=True))
        return 0
    for name in ("package_root", "authorization", "preflight_output", "request_output"):
        require(getattr(args, name) is not None, "ARGUMENT_REQUIRED_" + name.upper())
    try:
        result, request = execute(args)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        print(json.dumps({
            "status": "FAIL", "failure_code": str(code),
            "authorization_created": False,
            "board_operation": False, "usb_enumeration": False, "serial_operation": False,
            "esptool_operation": False, "flash_operation": False, "network_operation": False,
            "prepare_executed": False, "verify_executed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "preflight_result_sha256": result["preflight_result_sha256"],
        "request_binding_sha256": request["request_binding_sha256"],
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "host_authorization_consumed": True,
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


if __name__ == "__main__":
    raise SystemExit(main())
