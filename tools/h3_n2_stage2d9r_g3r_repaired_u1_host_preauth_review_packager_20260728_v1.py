#!/usr/bin/env python3
"""Deterministic public host-preflight review packager for repaired U1.

The packager copies only public source, emits an unauthorized host-preflight
request draft, and creates a deterministic tar.  It does not probe the operator
host, create an authorization, generate secrets, touch private custody, access a
board or serial port, invoke esptool, start a Broker, or execute commands.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
from typing import Iterable

import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain
import h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_probe_20260728_v1 as probe

SCHEMA = probe.PACKAGE_SCHEMA
REQUEST_SCHEMA = probe.REQUEST_SCHEMA
ARCHIVE_NAME = probe.PACKAGE_ARCHIVE_NAME
HEX40 = re.compile(r"^[0-9a-f]{40}$")

NEW_SOURCE_FILES = (
    "docs/decisions/h3-n2-stage2d9r-g3r-repaired-u1-host-preauth-scope-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-repaired-u1-host-preauth-contract-20260728-v1.md",
    "tools/h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_probe_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_review_packager_20260728_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_20260728_v1.py",
    ".github/workflows/h3-n2-stage2d9r-g3r-repaired-u1-host-preauth-review-ci-v1.yml",
)
SOURCE_FILES = tuple(probe.UPSTREAM_SOURCE_DIGESTS) + NEW_SOURCE_FILES


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def safe_repository_file(root: Path, relative: str) -> Path:
    require(relative and not relative.startswith("/"), "SOURCE_PATH_INVALID")
    path = (root / relative).resolve(strict=True)
    require(path.is_relative_to(root), "SOURCE_PATH_OUTSIDE_REPOSITORY")
    require(path.is_file() and not path.is_symlink(), "SOURCE_FILE_INVALID")
    return path


def write_public(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS")
    path.write_bytes(data)
    os.chmod(path, 0o644)


def source_inventory(repository_root: Path) -> dict[str, str]:
    result = {
        relative: sha256_bytes(safe_repository_file(repository_root, relative).read_bytes())
        for relative in SOURCE_FILES
    }
    for relative, expected in probe.UPSTREAM_SOURCE_DIGESTS.items():
        require(result[relative] == expected, "UPSTREAM_SOURCE_DIGEST_MISMATCH")
    return result


def build_binding(source_sha: str, inventory: dict[str, str]) -> dict[str, object]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    require(source_sha != probe.UPSTREAM_SOURCE_SHA, "HOST_PREFLIGHT_SOURCE_MUST_EXTEND_UPSTREAM")
    require(set(inventory) == set(SOURCE_FILES), "SOURCE_INVENTORY_MISMATCH")
    for digest in inventory.values():
        chain.validate_sha256(digest, "SOURCE_DIGEST_INVALID", reject_retired=False)
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "state": "HOST_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "stage": chain.STAGE,
        "decision_id": chain.DECISION_ID,
        "checkpoint_id": "C1-H3N2-STAGE2D9R-G3R-REPAIRED-U1-HOST-PREFLIGHT-20260728-01",
        "host_preflight_source_sha": source_sha,
        "upstream_source_sha": probe.UPSTREAM_SOURCE_SHA,
        "upstream_artifact_id": probe.UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": probe.UPSTREAM_ARTIFACT_SHA256,
        "upstream_inner_tar_sha256": probe.UPSTREAM_INNER_TAR_SHA256,
        "upstream_review_binding_sha256": probe.UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_request_file_sha256": probe.UPSTREAM_REQUEST_FILE_SHA256,
        "current_main_sha": chain.CURRENT_MAIN_SHA,
        "base_pull_request": 186,
        "base_head_sha": chain.BASE_HEAD_SHA,
        "layer_base_head_sha": probe.UPSTREAM_SOURCE_SHA,
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "run_suffix": chain.RUN_SUFFIX,
        "custody_selection_rule": chain.CUSTODY_SELECTION_RULE,
        "source_inventory": dict(sorted(inventory.items())),
        "source_inventory_sha256": canonical_json_sha256(
            {"source_inventory": dict(sorted(inventory.items()))}
        ),
        "host_probe_is_read_only": True,
        "host_probe_reads_secret_files": False,
        "host_probe_lists_custody_contents": False,
        "host_probe_requires_custody_root_absent": True,
        "exact_u1_authorization_required_after_probe": True,
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
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "tag_authorized": False,
        "deployment_authorized": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    payload["host_preflight_binding_sha256"] = canonical_json_sha256(payload)
    return payload


def build_request_draft(binding: dict[str, object]) -> dict[str, object]:
    return {
        "schema": REQUEST_SCHEMA,
        "state": "AWAITING_HOST_TOOLCHAIN_PROBE",
        "stage": chain.STAGE,
        "decision_id": chain.DECISION_ID,
        "checkpoint_id": binding["checkpoint_id"],
        "operation": generator_operation(),
        "source_sha": probe.UPSTREAM_SOURCE_SHA,
        "host_preflight_source_sha": binding["host_preflight_source_sha"],
        "host_preflight_binding_sha256": binding["host_preflight_binding_sha256"],
        "current_main_sha": chain.CURRENT_MAIN_SHA,
        "base_head_sha": chain.BASE_HEAD_SHA,
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "run_suffix": chain.RUN_SUFFIX,
        "custody_root_selection_rule": chain.CUSTODY_SELECTION_RULE,
        "required_host_fields": [
            "generator_sha256",
            "contract_sha256",
            "chain_contract_sha256",
            "protocol_sha256",
            "python_executable_sha256",
            "openssl_executable_sha256",
            "mosquitto_passwd_executable_sha256",
            "custody_root_digest_sha256",
        ],
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


def generator_operation() -> str:
    return "GENERATE_REPAIRED_SUCCESSOR_PRIVATE_MATERIAL"


def deterministic_tar(root: Path, names: Iterable[str], target: Path) -> None:
    require(not target.exists(), "ARCHIVE_ALREADY_EXISTS")
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(names):
            path = root / name
            require(path.is_file() and not path.is_symlink(), "ARCHIVE_MEMBER_INVALID")
            data = path.read_bytes()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    os.chmod(target, 0o644)


def build_package(repository_root: Path, output_root: Path, source_sha: str) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    require(not output_root.exists(), "OUTPUT_ROOT_ALREADY_EXISTS")
    require(not output_root.is_relative_to(repository_root), "OUTPUT_ROOT_INSIDE_REPOSITORY")
    output_root.mkdir(mode=0o755, parents=True)
    inventory = source_inventory(repository_root)
    binding = build_binding(source_sha, inventory)
    request = build_request_draft(binding)

    members: list[str] = []
    for relative in SOURCE_FILES:
        write_public(output_root / relative, safe_repository_file(repository_root, relative).read_bytes())
        members.append(relative)
    write_public(
        output_root / probe.BINDING_FILE,
        json.dumps(binding, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    members.append(probe.BINDING_FILE)
    write_public(
        output_root / probe.REQUEST_FILE,
        json.dumps(request, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    members.append(probe.REQUEST_FILE)
    sums = "".join(
        f"{sha256_bytes((output_root / name).read_bytes())}  {name}\n"
        for name in sorted(members)
    ).encode("utf-8")
    write_public(output_root / probe.SUMS_FILE, sums)
    members.append(probe.SUMS_FILE)
    archive = output_root / ARCHIVE_NAME
    deterministic_tar(output_root, members, archive)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-repaired-u1-host-preauth-review-package-result/1",
        "status": "PASS",
        "source_sha": source_sha,
        "host_preflight_binding_sha256": binding["host_preflight_binding_sha256"],
        "archive_name": ARCHIVE_NAME,
        "archive_sha256": sha256_bytes(archive.read_bytes()),
        "member_count": len(members),
        "authorized": False,
        "authorization_created": False,
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
        "schema": "gh.h3.n2.stage2d9r-g3r-repaired-u1-host-preauth-review-packager/1",
        "status": "SOURCE_ONLY_BUILD_REQUIRES_EXPLICIT_OUTPUT",
        "authorized": False,
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
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    if not args.build:
        print(json.dumps(inert_status(), sort_keys=True))
        return 0
    try:
        require(args.repository_root is not None, "REPOSITORY_ROOT_REQUIRED")
        require(args.output_root is not None, "OUTPUT_ROOT_REQUIRED")
        require(args.source_sha is not None, "SOURCE_SHA_REQUIRED")
        result = build_package(args.repository_root, args.output_root, args.source_sha)
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (PackageError, chain.ContractError)) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code), **inert_status()}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
