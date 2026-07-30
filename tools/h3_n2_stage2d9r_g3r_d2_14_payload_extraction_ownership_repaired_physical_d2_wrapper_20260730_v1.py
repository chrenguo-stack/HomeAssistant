#!/usr/bin/env python3
"""D2-14 adapter enforcing single ownership of payload extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

import h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_wrapper_20260730_v1 as predecessor
import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1 as contract
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as payload_handoff

LAUNCHER_ROOT_ENV = "GH_D2_14_LAUNCHER_PACKAGE_ROOT"
PREDECESSOR_LAUNCHER_ROOT_ENV = predecessor.LAUNCHER_ROOT_ENV


class ExtractionOwnershipError(RuntimeError):
    """Stable preclaim extraction-ownership failure."""


def _fail(code: str) -> None:
    raise ExtractionOwnershipError(code)


def _normalize(value: str | Path, *, strict: bool, code: str) -> Path:
    try:
        return Path(value).expanduser().resolve(strict=strict)
    except (OSError, RuntimeError) as exc:
        raise ExtractionOwnershipError(code) from exc


def _option_values(argv: list[str], name: str) -> list[str]:
    values: list[str] = []
    index = 0
    prefix = name + "="
    while index < len(argv):
        item = argv[index]
        if item == name:
            if index + 1 >= len(argv):
                _fail("EXTRACTION_ROOT_OPTION_VALUE_MISSING")
            values.append(argv[index + 1])
            index += 2
            continue
        if item.startswith(prefix):
            values.append(item[len(prefix):])
        index += 1
    return values


def _one(argv: list[str], name: str, code: str) -> str:
    values = _option_values(argv, name)
    if len(values) != 1 or not values[0]:
        _fail(code)
    return values[0]


def _mode(path: Path) -> str:
    return format(stat.S_IMODE(path.stat().st_mode), "04o")


def _empty_root(argv: list[str], option: str, role: str) -> Path:
    root = _normalize(_one(argv, option, role + "_PAYLOAD_ROOT_MISSING"), strict=True, code=role + "_PAYLOAD_ROOT_INVALID")
    if not root.is_dir() or root.is_symlink() or _mode(root) != "0700":
        _fail(role + "_PAYLOAD_ROOT_INVALID")
    if any(root.iterdir()):
        _fail(role + "_PAYLOAD_ROOT_NOT_EMPTY")
    return root


def verify_empty_payload_roots(argv: list[str]) -> tuple[Path, Path]:
    """Require the private outer layer to provide empty roots only."""
    immutable_root = _empty_root(argv, "--immutable-root", "IMMUTABLE")
    recovery_root = _empty_root(argv, "--recovery-root", "RECOVERY")
    if immutable_root == recovery_root:
        _fail("PAYLOAD_ROOT_ROLE_COLLISION")
    return immutable_root, recovery_root


def bind_predecessor() -> None:
    if not sys.dont_write_bytecode:
        raise contract.ContractError("PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START")
    predecessor.contract = contract
    predecessor.bind_upstream()


def _stable_error(exc: BaseException) -> str:
    if isinstance(exc, ExtractionOwnershipError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    if isinstance(exc, contract.ContractError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return type(exc).__name__


def _safe_path(argv: list[str], option: str) -> Path | None:
    values = _option_values(argv, option)
    if len(values) != 1 or not values[0]:
        return None
    try:
        return Path(values[0]).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def write_preclaim_ownership_failure(argv: list[str], code: str) -> dict[str, Any]:
    auth = _safe_path(argv, "--authorization-record")
    result_path = _safe_path(argv, "--result-output")
    state_root = _safe_path(argv, "--state-root")
    created = auth is not None and auth.is_file() and not auth.is_symlink()
    marker = None if state_root is None else state_root / (hashlib.sha256(contract.D2_REQUEST_ID.encode()).hexdigest() + ".json")
    claimed = marker is not None and marker.exists()
    value: dict[str, Any] = {
        "schema": contract.PRE_RESULT_SCHEMA,
        "stage": contract.STAGE,
        "d2_request_id": contract.D2_REQUEST_ID,
        "status": "CONSUMED_FAILED" if created else "FAIL",
        "terminal_state": "CONSUMED_FAILED_PRECLAIM" if created else "PRECLAIM_REJECTED",
        "failure_code": code,
        "failure_stage": "PAYLOAD_EXTRACTION_OWNERSHIP",
        "authorization_created": created,
        "authorization_claimed": claimed,
        "authorization_consumed": created,
        "authorization_record_sha256": contract.sha256_file(auth) if created and auth is not None else None,
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
        "production_operation": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    value["terminal_result_sha256"] = contract.canonical_sha256(value)
    if result_path is not None and not result_path.exists():
        _write_exclusive_json(result_path, value)
    if created and marker is not None and not marker.exists():
        marker_value = {
            "schema": contract.PRE_MARKER_SCHEMA,
            "stage": contract.STAGE,
            "d2_request_id": contract.D2_REQUEST_ID,
            "status": "CONSUMED_FAILED",
            "failure_code": code,
            "failure_stage": "PAYLOAD_EXTRACTION_OWNERSHIP",
            "authorization_created": True,
            "authorization_claimed": False,
            "authorization_consumed": True,
            "authorization_record_sha256": value["authorization_record_sha256"],
            "terminal_result_sha256": value["terminal_result_sha256"],
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        _write_exclusive_json(marker, marker_value)
    return value


def root_ownership_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        bind_predecessor()
        package = args.package_root.expanduser().resolve(strict=True)
        if not package.is_dir() or package.is_symlink():
            _fail("PACKAGE_ROOT_INVALID")
        launcher_root = os.environ.get(LAUNCHER_ROOT_ENV)
        if launcher_root is None or Path(launcher_root).resolve(strict=True) != package:
            _fail("LAUNCHER_PACKAGE_ROOT_MISMATCH")
        with tempfile.TemporaryDirectory(prefix="d2-14 root ownership ") as temporary:
            runtime = Path(temporary)
            immutable_root = runtime / "immutable"
            recovery_root = runtime / "recovery"
            immutable_root.mkdir(mode=0o700)
            recovery_root.mkdir(mode=0o700)
            raw = [
                "--package-root", str(package),
                "--immutable-root", str(immutable_root),
                "--recovery-root", str(recovery_root),
            ]
            verify_empty_payload_roots(raw)
            os.environ[PREDECESSOR_LAUNCHER_ROOT_ENV] = str(package)
            repaired = predecessor.repair_execute_argv(raw)
            immutable_tar = Path(repaired[repaired.index("--immutable-payload-tar") + 1])
            recovery_tar = Path(repaired[repaired.index("--recovery-payload-tar") + 1])
            payload_handoff.safe_extract_payload(
                immutable_tar,
                immutable_root,
                expected_tar_sha256=contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
                expected_members=payload_handoff.IMMUTABLE_MEMBERS,
                code="IMMUTABLE_PAYLOAD_INVALID",
            )
            payload_handoff.safe_extract_payload(
                recovery_tar,
                recovery_root,
                expected_tar_sha256=contract.RECOVERY_PAYLOAD_TAR_SHA256,
                expected_members=payload_handoff.RECOVERY_MEMBERS,
                code="RECOVERY_PAYLOAD_INVALID",
            )
            if (immutable_root / immutable_tar.name).exists() or (recovery_root / recovery_tar.name).exists():
                _fail("PAYLOAD_TAR_COPIED_INSIDE_ROOT")
            result: dict[str, Any] = {
                "schema": "gh.h3.n2.stage2d9r-g3r-d2-14-payload-extraction-ownership-check/1",
                "status": "PASS",
                "d2_request_id": contract.D2_REQUEST_ID,
                "outer_payload_preextraction": False,
                "inner_payload_extraction_count": 1,
                "payload_roots_empty_before_inner_start": True,
                "payload_tar_copy_inside_roots": False,
                "immutable_payload_inventory_valid": True,
                "recovery_payload_inventory_valid": True,
                "authorization_claimed": False,
                "authorization_consumed": False,
                "board_operation": False,
                "usb_enumeration": False,
                "serial_operation": False,
                "esptool_operation": False,
                "flash_operation": False,
                "network_operation": False,
                "prepare_executed": False,
                "verify_executed": False,
            }
        rc = 0
    except Exception as exc:
        result = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-14-payload-extraction-ownership-check/1",
            "status": "FAIL",
            "failure_code": _stable_error(exc),
            "d2_request_id": contract.D2_REQUEST_ID,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
        }
        rc = 2
    args.result_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return rc


def source_status() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-14-payload-extraction-ownership-repaired-execution-binding-source/1",
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_14_AUTHORIZATION",
        "decision_id": contract.DECISION_ID,
        "d2_request_id": contract.D2_REQUEST_ID,
        "predecessor_request_id": contract.D2_13_ID,
        "predecessor_terminal_state": contract.D2_13_TERMINAL_STATE,
        "predecessor_failure_code": contract.D2_13_FAILURE_CODE,
        "outer_payload_preextraction_prohibited": True,
        "inner_payload_extraction_single_owner": True,
        "payload_roots_empty_before_inner_start": True,
        "payload_tar_copy_inside_roots_prohibited": True,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }


def main() -> int:
    if not sys.dont_write_bytecode:
        value = source_status()
        value.update({"status": "FAIL", "failure_code": "PYTHON_BYTECODE_WRITE_NOT_DISABLED_AT_PROCESS_START"})
        print(json.dumps(value, sort_keys=True))
        return 2
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
        return 0
    if sys.argv[1] == "root-ownership-check":
        return root_ownership_check(sys.argv[2:])
    if sys.argv[1] == "contract-check":
        predecessor.contract = contract
        return predecessor.contract_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print("first argument must be contract-check, root-ownership-check or execute", file=sys.stderr)
        return 2
    original = sys.argv[2:]
    try:
        bind_predecessor()
        verify_empty_payload_roots(original)
        package_raw = _one(original, "--package-root", "PACKAGE_ROOT_MISSING")
        package = _normalize(package_raw, strict=True, code="PACKAGE_ROOT_INVALID")
        launcher_raw = os.environ.get(LAUNCHER_ROOT_ENV)
        if launcher_raw is None or _normalize(launcher_raw, strict=True, code="LAUNCHER_PACKAGE_ROOT_INVALID") != package:
            _fail("LAUNCHER_PACKAGE_ROOT_MISMATCH")
        os.environ[PREDECESSOR_LAUNCHER_ROOT_ENV] = str(package)
    except Exception as exc:
        code = _stable_error(exc)
        value = write_preclaim_ownership_failure(original, code)
        print(json.dumps({
            "status": value["status"],
            "failure_code": code,
            "d2_request_id": contract.D2_REQUEST_ID,
            "authorization_claimed": value["authorization_claimed"],
            "authorization_consumed": value["authorization_consumed"],
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 2
    predecessor.contract = contract
    sys.argv = [sys.argv[0], "execute", *original]
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
