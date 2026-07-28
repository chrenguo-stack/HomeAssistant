#!/usr/bin/env python3
"""Host-only read-only preauthorization probe for repaired Stage 2D-9R U1.

The default invocation is inert.  ``--probe-host`` validates a frozen public
review package, hashes the exact Python/OpenSSL/mosquitto_passwd toolchain, and
checks only metadata for the not-yet-created tlsvalid03 custody root.  It never
creates an authorization, generates a secret, opens USB or serial, invokes
esptool, starts a Broker, opens a network socket, or executes PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_repaired_private_material_generator_20260728_v1 as generator
import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain

SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-u1-host-preauth-probe/1"
PACKAGE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-u1-host-preauth-review-binding/1"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-u1-authorization-request-draft/1"
RESULT_STATE = "HOST_PREFLIGHT_PASS_AWAITING_EXACT_U1_DECISION"
UPSTREAM_SOURCE_SHA = "2ed70e3292e5b6522ac3a5bc279c94535cd7b784"
UPSTREAM_ARTIFACT_ID = 8672973249
UPSTREAM_ARTIFACT_SHA256 = "c493c4464935ecbf2f71952ebadfcbab28c9f9d1cf5203afb4350fc95bb31b50"
UPSTREAM_INNER_TAR_SHA256 = "4fd6ed8d359e49583229ab4068312bdca9e15a0d422097d3c5a5ac16bd46b8fb"
UPSTREAM_REVIEW_BINDING_SHA256 = "ccc25531d868bd09f66f4d98cb907c0272408edee97f2700e818274a1a0efd3c"
UPSTREAM_REQUEST_FILE_SHA256 = "b45a19dfea9ceb8918d2bc127dc9783a589cd0b2ec32b63245d6008ee52271e1"
PACKAGE_ARCHIVE_NAME = "stage2d9r-g3r-repaired-u1-host-preauth-review-v1.tar"
BINDING_FILE = "HOST_PREFLIGHT_BINDING.json"
REQUEST_FILE = "U1_AUTHORIZATION_REQUEST_DRAFT.json"
SUMS_FILE = "SHA256SUMS"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

UPSTREAM_SOURCE_DIGESTS = {
    ".github/workflows/h3-n2-stage2d9r-g3r-repaired-private-material-u1-review-ci-v1.yml": "92e3badefda5f86605f3d2a87a2a8b37dad4ad92b5b2fbff699628df3f9e7263",
    ".github/workflows/h3-n2-stage2d9r-g3r-repaired-successor-chain-contract-ci-v1.yml": "f0316ce2e20b80350e10458ea06b2c03e70cab6c4dd2420656c858a624bdce49",
    "docs/decisions/h3-n2-stage2d9r-g3r-repaired-successor-chain-d1-20260728-v1.json": "263f39fdddb03a1f947f0dc44dabcd5a7abddd12085c8ed8580df97c9d93f348",
    "docs/decisions/h3-n2-stage2d9r-g3r-serial-handshake-repair-d1-20260727-v1.json": "2e1add7b3910b4a9669c7abe8afd61516854fa222c9c6aee511b1f4b7a8763e9",
    "docs/development/h3-n2-stage2d9r-g3r-repaired-successor-chain-contract-20260728-v1.md": "d88fe388a4fcfae169cbd7fee5f93a5eadc177cda3f343047c8b90d5e3b258e3",
    "docs/development/h3-n2-stage2d9r-g3r-serial-handshake-repair-contract-20260727-v1.md": "d0078c5bfab94567409b508e20e866cd8a3367aecdf6b24246fa12b538bea389",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_repaired_private_material_20260728_v1.py": "a3c4edadf0ac7c8271bceef816760fae2284049a98d5b6d4ee8c26a19006ecd4",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py": "b45041f8897f0480b2579aa0d931281ea0c1e74d664410302b09ca2784a92ef6",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py": "19ed23e8ed81d8803d105467a3398251e2db45bf95905126ff2df971086019d4",
    "tools/h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1.py": "1d096a2c2f65e74f5e8c09bd2932749fd59dcc65fc23a3b69de0bfc7335800a7",
    "tools/h3_n2_stage2d9r_g3r_repaired_private_material_generator_20260728_v1.py": "b768093a86e18acf826dc8d81650bac09fff5ea77ce9c362a0dc92212657b3bb",
    "tools/h3_n2_stage2d9r_g3r_repaired_private_material_u1_review_packager_20260728_v1.py": "9a5ed55920ce688575d44d2c074bae4a739690879cd254b149eb4d647944ebb2",
    "tools/h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py": "2d73f6f6641b1951e83c5f317bb84f2ceffb38aadbe6bfa66e04fa7b8ca49e1b",
    "tools/h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py": "2520c292151b240827083272673df82441fd68b4e022ab0320311866d2bd4f18",
    "tools/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py": "5e7ac5377e94c40fa0e2c536e4c95bffe15f99d5ac3dc91f3df4d9ddf80378ee",
}

TOOLCHAIN_SOURCE_PATHS = {
    "generator": "tools/h3_n2_stage2d9r_g3r_repaired_private_material_generator_20260728_v1.py",
    "contract": "tools/h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1.py",
    "chain": "tools/h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py",
    "protocol": "tools/h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py",
}


class ProbeError(RuntimeError):
    """Fail-closed host preauthorization probe error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def regular_file(path: Path, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)


def safe_member_name(name: str) -> None:
    path = Path(name)
    require(name and not path.is_absolute(), "PACKAGE_MEMBER_PATH_INVALID")
    require(".." not in path.parts, "PACKAGE_MEMBER_PATH_INVALID")


def parse_sums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        safe_member_name(name)
        require(HEX64.fullmatch(digest) is not None, "SHA256SUMS_INVALID")
        require(name not in result, "SHA256SUMS_DUPLICATE")
        result[name] = digest
    require(bool(result), "SHA256SUMS_EMPTY")
    return result


def validate_upstream_inventory(root: Path) -> None:
    for relative, expected in UPSTREAM_SOURCE_DIGESTS.items():
        path = (root / relative).resolve(strict=True)
        require(path.is_relative_to(root), "SOURCE_PATH_OUTSIDE_PACKAGE")
        regular_file(path, "SOURCE_FILE_INVALID")
        require(sha256_file(path) == expected, "UPSTREAM_SOURCE_DIGEST_MISMATCH")


def validate_package(root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    root = root.resolve(strict=True)
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    binding_path = root / BINDING_FILE
    request_path = root / REQUEST_FILE
    sums_path = root / SUMS_FILE
    archive_path = root / PACKAGE_ARCHIVE_NAME
    for path in (binding_path, request_path, sums_path, archive_path):
        regular_file(path, "PACKAGE_REQUIRED_FILE_INVALID")

    sums = parse_sums(sums_path.read_bytes())
    for name, expected in sums.items():
        path = (root / name).resolve(strict=True)
        require(path.is_relative_to(root), "PACKAGE_SUM_PATH_OUTSIDE_ROOT")
        regular_file(path, "PACKAGE_SUM_MEMBER_INVALID")
        require(sha256_file(path) == expected, "PACKAGE_MEMBER_DIGEST_MISMATCH")

    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "PACKAGE_ARCHIVE_DUPLICATE_MEMBER")
        require(set(names) == set(sums) | {SUMS_FILE}, "PACKAGE_ARCHIVE_INVENTORY_MISMATCH")
        for member in members:
            safe_member_name(member.name)
            require(member.isfile(), "PACKAGE_ARCHIVE_MEMBER_NOT_FILE")
            require(member.uid == 0 and member.gid == 0, "PACKAGE_ARCHIVE_OWNER_MISMATCH")
            require(member.uname == "" and member.gname == "", "PACKAGE_ARCHIVE_OWNER_MISMATCH")
            require(member.mtime == 0, "PACKAGE_ARCHIVE_MTIME_MISMATCH")
            require(member.mode == 0o644, "PACKAGE_ARCHIVE_MODE_MISMATCH")
            handle = archive.extractfile(member)
            require(handle is not None, "PACKAGE_ARCHIVE_MEMBER_UNREADABLE")
            data = handle.read()
            if member.name == SUMS_FILE:
                require(data == sums_path.read_bytes(), "PACKAGE_ARCHIVE_SUMS_MISMATCH")
            else:
                require(sha256_bytes(data) == sums[member.name], "PACKAGE_ARCHIVE_DIGEST_MISMATCH")

    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    require(binding.get("schema") == PACKAGE_SCHEMA, "PACKAGE_BINDING_SCHEMA_MISMATCH")
    require(binding.get("state") == "HOST_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED", "PACKAGE_BINDING_STATE_MISMATCH")
    require(binding.get("upstream_source_sha") == UPSTREAM_SOURCE_SHA, "PACKAGE_UPSTREAM_SOURCE_MISMATCH")
    require(binding.get("upstream_artifact_id") == UPSTREAM_ARTIFACT_ID, "PACKAGE_UPSTREAM_ARTIFACT_MISMATCH")
    require(binding.get("upstream_artifact_sha256") == UPSTREAM_ARTIFACT_SHA256, "PACKAGE_UPSTREAM_ARTIFACT_MISMATCH")
    require(binding.get("upstream_inner_tar_sha256") == UPSTREAM_INNER_TAR_SHA256, "PACKAGE_UPSTREAM_TAR_MISMATCH")
    require(binding.get("upstream_review_binding_sha256") == UPSTREAM_REVIEW_BINDING_SHA256, "PACKAGE_UPSTREAM_BINDING_MISMATCH")
    require(binding.get("run_suffix") == chain.RUN_SUFFIX, "PACKAGE_RUN_SUFFIX_MISMATCH")
    require(binding.get("current_main_sha") == chain.CURRENT_MAIN_SHA, "PACKAGE_MAIN_SHA_MISMATCH")
    require(binding.get("base_head_sha") == chain.BASE_HEAD_SHA, "PACKAGE_BASE_SHA_MISMATCH")
    require(binding.get("host_preflight_source_sha") != UPSTREAM_SOURCE_SHA, "PACKAGE_SOURCE_NOT_LAYERED")
    require(HEX40.fullmatch(str(binding.get("host_preflight_source_sha"))) is not None, "PACKAGE_SOURCE_SHA_INVALID")
    observed_binding = dict(binding)
    supplied_binding_sha = observed_binding.pop("host_preflight_binding_sha256", None)
    require(supplied_binding_sha == canonical_json_sha256(observed_binding), "PACKAGE_BINDING_DIGEST_MISMATCH")

    require(request.get("schema") == REQUEST_SCHEMA, "PACKAGE_REQUEST_SCHEMA_MISMATCH")
    require(request.get("state") == "AWAITING_HOST_TOOLCHAIN_PROBE", "PACKAGE_REQUEST_STATE_MISMATCH")
    require(request.get("source_sha") == UPSTREAM_SOURCE_SHA, "PACKAGE_REQUEST_SOURCE_MISMATCH")
    require(request.get("host_preflight_binding_sha256") == supplied_binding_sha, "PACKAGE_REQUEST_BINDING_MISMATCH")
    for key in (
        "authorized", "authorization_created", "authorization_claimed",
        "authorization_consumed", "secret_generation", "private_material_created",
        "board_operation", "usb_enumeration", "serial_operation", "flash_operation",
        "physical_nvs_operation", "network_operation", "broker_started",
        "prepare_executed", "verify_executed", "private_paths_included",
        "secret_values_included",
    ):
        require(request.get(key) is False, f"PACKAGE_REQUEST_{key.upper()}_MUST_BE_FALSE")
    require(request.get("issued_at") is None and request.get("expires_at") is None, "PACKAGE_REQUEST_TIME_MUST_BE_NULL")
    validate_upstream_inventory(root)
    return binding, request, sha256_file(archive_path)


def custody_metadata(home: Path, repository_root: Path) -> dict[str, object]:
    home = home.expanduser().resolve(strict=True)
    root = generator.default_custody_root(home)
    generator.validate_private_root(root, home, repository_root)
    parent = root.parent
    parent_exists = parent.exists()
    if parent_exists:
        require(parent.is_dir() and not parent.is_symlink(), "CUSTODY_PARENT_INVALID")
        require(file_mode(parent) == "0700", "CUSTODY_PARENT_MODE_INVALID")
    return {
        "custody_root_selection_rule": chain.CUSTODY_SELECTION_RULE,
        "custody_root_digest_sha256": sha256_bytes(str(root).encode("utf-8")),
        "custody_root_exists": False,
        "custody_parent_exists": parent_exists,
        "custody_parent_mode": file_mode(parent) if parent_exists else None,
        "custody_path_included": False,
        "home_path_included": False,
    }


def build_request(
    binding: Mapping[str, Any],
    toolchain: generator.Toolchain,
    custody: Mapping[str, object],
    package_archive_sha256: str,
) -> dict[str, object]:
    request: dict[str, object] = {
        "schema": REQUEST_SCHEMA,
        "state": RESULT_STATE,
        "stage": chain.STAGE,
        "decision_id": chain.DECISION_ID,
        "operation": generator.AUTH_OPERATION,
        "source_sha": UPSTREAM_SOURCE_SHA,
        "host_preflight_source_sha": binding["host_preflight_source_sha"],
        "host_preflight_binding_sha256": binding["host_preflight_binding_sha256"],
        "host_preflight_package_archive_sha256": package_archive_sha256,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "current_main_sha": chain.CURRENT_MAIN_SHA,
        "base_head_sha": chain.BASE_HEAD_SHA,
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "run_suffix": chain.RUN_SUFFIX,
        "generator_sha256": toolchain.generator_sha256,
        "contract_sha256": toolchain.contract_sha256,
        "chain_contract_sha256": toolchain.chain_contract_sha256,
        "protocol_sha256": toolchain.protocol_sha256,
        "python_executable_sha256": toolchain.python_executable_sha256,
        "python_version": toolchain.python_version,
        "openssl_executable_sha256": toolchain.openssl_executable_sha256,
        "openssl_version": toolchain.openssl_version,
        "mosquitto_passwd_executable_sha256": toolchain.mosquitto_passwd_executable_sha256,
        "mosquitto_passwd_version": toolchain.mosquitto_passwd_version,
        **custody,
        "authorization_id": None,
        "issued_at": None,
        "expires_at": None,
        "authorized": False,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_generation": False,
        "private_material_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
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
    request["request_binding_sha256"] = canonical_json_sha256(request)
    return request


def run_host_probe(
    package_root: Path,
    home: Path,
    openssl: Path | None,
    mosquitto_passwd: Path | None,
) -> dict[str, object]:
    package_root = package_root.expanduser().resolve(strict=True)
    binding, _draft, archive_sha = validate_package(package_root)
    toolchain = generator.probe_toolchain(
        package_root / TOOLCHAIN_SOURCE_PATHS["generator"],
        package_root / TOOLCHAIN_SOURCE_PATHS["contract"],
        package_root / TOOLCHAIN_SOURCE_PATHS["chain"],
        package_root / TOOLCHAIN_SOURCE_PATHS["protocol"],
        openssl,
        mosquitto_passwd,
    )
    custody = custody_metadata(home, package_root)
    request = build_request(binding, toolchain, custody, archive_sha)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": RESULT_STATE,
        "request": request,
        "ready_for_exact_u1_decision": True,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_generation": False,
        "private_material_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
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


def inert_status() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "SOURCE_ONLY_REQUIRES_EXPLICIT_HOST_PROBE",
        "upstream_source_sha": UPSTREAM_SOURCE_SHA,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "run_suffix": chain.RUN_SUFFIX,
        "host_probe_executed": False,
        "ready_for_exact_u1_decision": False,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_generation": False,
        "private_material_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-host", action="store_true")
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--openssl", type=Path)
    parser.add_argument("--mosquitto-passwd", type=Path)
    args = parser.parse_args()
    if not args.probe_host:
        print(json.dumps(inert_status(), sort_keys=True))
        return 0
    try:
        require(args.package_root is not None, "PACKAGE_ROOT_REQUIRED")
        home = args.home.expanduser().resolve(strict=True) if args.home else Path.home().resolve(strict=True)
        result = run_host_probe(
            args.package_root,
            home,
            args.openssl,
            args.mosquitto_passwd,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (ProbeError, generator.GenerationError, chain.ContractError)) and exc.args else type(exc).__name__
        print("STAGE2D9R_REPAIRED_U1_HOST_PREAUTH_PROBE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("AUTHORIZED=false")
        print("SECRET_GENERATION=false")
        print("PRIVATE_MATERIAL_CREATED=false")
        print("BOARD_OPERATION=false")
        print("USB_ENUMERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PHYSICAL_NVS_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("PREPARE_EXECUTED=false")
        print("VERIFY_EXECUTED=false")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        return 2
    print("STAGE2D9R_REPAIRED_U1_HOST_PREAUTH_PROBE=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
