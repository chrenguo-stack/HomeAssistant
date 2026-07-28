#!/usr/bin/env python3
"""Build deterministic repaired host-final-preflight and physical-D2 review package.

The packager consumes only public repository source, the canonical immutable /
recovery Artifact ZIP, and the redacted baseline acceptance files. It does not
read private custody, enumerate USB/serial, invoke esptool, use a board, start a
Broker, or execute PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, Mapping
import zipfile

import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1 as contract

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-review-binding/1"
EXECUTION_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-physical-d2-execution-package/1"
REVIEW_ARCHIVE_NAME = "stage2d9r-g3r-repaired-host-final-preflight-review-v1.tar"
BASELINE_ARCHIVE_NAME = "stage2d9r-g3r-repaired-baseline-readonly-public-acceptance-v1.tar"
IMMUTABLE_ZIP_NAME = "stage2d9r-g3r-repaired-immutable-recovery-freeze-v3.zip"
EXECUTION_DIR = "physical-d2-execution-package"
BINDING_FILE = "HOST_FINAL_PREFLIGHT_REVIEW_BINDING.json"
REQUEST_FILE = "PHYSICAL_D2_REQUEST_DRAFT.json"
SUMS_FILE = "SHA256SUMS"
BASELINE_DIR = "tests/h3_n2_stage2d9r_tls_candidate/public_repaired_baseline_readonly"
SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-repaired-host-final-preflight-review-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-repaired-main-zero-net-correction-acceptance-20260728-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-repaired-host-final-preflight-contract-20260728-v1.md",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_common_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_execution_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_common_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_validation_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py",
    "tools/h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
    "tools/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py",
    "tools/h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_repaired_host_final_preflight_20260728_v1.py",
)
IMMUTABLE_MEMBERS = {
    "SHA256SUMS",
    "final-execution-binding.json",
    "immutable-freeze-manifest.json",
    "immutable-recovery-freeze-manifest.json",
    "stage2d9r-g3r-repaired-immutable-payload-v1.tar",
    "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar",
}
EXECUTION_SOURCE_NAMES = (
    "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py",
    "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
    "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py",
)
HEX64 = contract.HEX64


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def pretty_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def safe_name(name: str) -> None:
    pure = PurePosixPath(name)
    require(name and not pure.is_absolute() and ".." not in pure.parts, "PATH_INVALID")


def write_file(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, mode)


def copy_public(source: Path, destination: Path) -> None:
    require(source.is_file() and not source.is_symlink(), "SOURCE_FILE_INVALID")
    write_file(destination, source.read_bytes(), 0o600)


def parse_sums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        safe_name(name)
        require(HEX64.fullmatch(digest) is not None, "SHA256SUMS_INVALID")
        require(name not in result, "SHA256SUMS_DUPLICATE")
        result[name] = digest
    require(bool(result), "SHA256SUMS_EMPTY")
    return result


def deterministic_tar_bytes(files: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            safe_name(name)
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def reconstruct_baseline(root: Path) -> tuple[bytes, dict[str, Any]]:
    source = root / BASELINE_DIR
    names = (
        "SHA256SUMS",
        "baseline-public-acceptance.json",
        "baseline-result.redacted.json",
        "consumed-marker.redacted.json",
    )
    require(
        sorted(path.name for path in source.iterdir()) == sorted(names),
        "BASELINE_DIRECTORY_INVENTORY_MISMATCH",
    )
    files = {name: (source / name).read_bytes() for name in names}
    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == set(names) - {"SHA256SUMS"}, "BASELINE_SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest, "BASELINE_FILE_DIGEST_MISMATCH")
    archive = deterministic_tar_bytes(files)
    require(
        sha256_bytes(archive) == contract.BASELINE_PUBLIC_ARCHIVE_SHA256,
        "BASELINE_ARCHIVE_DIGEST_MISMATCH",
    )
    acceptance = json.loads(files["baseline-public-acceptance.json"])
    result = json.loads(files["baseline-result.redacted.json"])
    marker = json.loads(files["consumed-marker.redacted.json"])
    require(
        sha256_bytes(files["baseline-public-acceptance.json"])
        == contract.BASELINE_PUBLIC_ACCEPTANCE_SHA256,
        "BASELINE_ACCEPTANCE_DIGEST_MISMATCH",
    )
    require(result.get("result_sha256") == contract.BASELINE_RESULT_SHA256, "BASELINE_RESULT_MISMATCH")
    without = dict(result)
    observed = without.pop("result_sha256")
    require(canonical_sha256(without) == observed, "BASELINE_RESULT_CANONICAL_MISMATCH")
    require(result.get("status") == "CONSUMED_PASS", "BASELINE_STATUS_MISMATCH")
    require(marker.get("status") == "CONSUMED_PASS", "BASELINE_MARKER_STATUS_MISMATCH")
    require(
        marker.get("terminal_result_sha256") == contract.BASELINE_RESULT_SHA256,
        "BASELINE_MARKER_RESULT_MISMATCH",
    )
    require(acceptance.get("main_sha") == contract.BASELINE_ORIGINAL_MAIN_SHA, "BASELINE_MAIN_MISMATCH")
    require(acceptance.get("authorization_consumed") is True, "BASELINE_NOT_CONSUMED")
    require(acceptance.get("replay_permitted") is False, "BASELINE_REPLAY_EXPANDED")
    return archive, acceptance


def read_tar_members(data: bytes) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as archive:
        for member in archive.getmembers():
            safe_name(member.name)
            require(member.isfile(), "TAR_MEMBER_NOT_FILE")
            require(member.name not in result, "TAR_MEMBER_DUPLICATE")
            handle = archive.extractfile(member)
            require(handle is not None, "TAR_MEMBER_UNREADABLE")
            result[member.name] = handle.read()
    return result
