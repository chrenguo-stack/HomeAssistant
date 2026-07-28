#!/usr/bin/env python3
"""One-shot host-only final preflight for repaired Stage2D9R.

Default invocation is inert. The authorized host probe validates the frozen
public review package, hashes the local toolchain, and verifies tlsvalid03
private custody entirely offline. It never enumerates USB/serial devices, opens
a serial port, invokes esptool, accesses a board, reads Flash/NVS, starts a
Broker, opens a network socket, or executes PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from typing import Any, Mapping
import zipfile

import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_20260728_v1 as packager
import h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1 as private_contract
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-host-final-preflight-consumption/1"
AUTH_OPERATION = "VALIDATE_REPAIRED_SUCCESSOR_PRIVATE_CUSTODY_AND_BUILD_PHYSICAL_D2_REQUEST"
CUSTODY_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/"
    "repaired-successor-private-execution-material-tlsvalid03"
)
AUTH_STATE_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/host-final-preflight-authorizations"
)
PRIVATE_DESCRIPTOR = "private-custody-descriptor.json"
PUBLIC_DESCRIPTOR = "public-descriptor.redacted.json"
REQUIRED_PRIVATE_FILES = tuple(private_contract.REQUIRED_PRIVATE_FILES)
HEX64 = contract.HEX64


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def regular(path: Path, mode: str, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == mode, code + "_MODE")


def load_json(path: Path, mode: str, code: str) -> dict[str, Any]:
    regular(path, mode, code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code + "_JSON")
    return value


def write_json_exclusive(path: Path, value: object) -> None:
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
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


def replace_json(path: Path, value: object) -> None:
    regular(path, "0600", "MARKER_INVALID")
    temporary = path.with_name(path.name + ".new")
    require(not temporary.exists(), "MARKER_TEMP_EXISTS")
    write_json_exclusive(temporary, value)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProbeError(code) from exc
    return parsed.astimezone(timezone.utc)


def executable(name: str, explicit: str | None = None) -> Path:
    candidate = explicit or shutil.which(name)
    require(candidate is not None, f"EXECUTABLE_UNAVAILABLE_{name.upper()}")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(
        path.is_file() and not path.is_symlink() and os.access(path, os.X_OK),
        f"EXECUTABLE_INVALID_{name.upper()}",
    )
    return path


def module_file(name: str) -> Path:
    spec = importlib.util.find_spec(name)
    require(spec is not None and spec.origin is not None, f"MODULE_UNAVAILABLE_{name.upper()}")
    path = Path(spec.origin).resolve(strict=True)
    require(path.is_file() and not path.is_symlink(), f"MODULE_INVALID_{name.upper()}")
    return path


def run_checked(command: list[str], *, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=45,
        env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C"},
    )
    require(completed.returncode == 0, "OFFLINE_TOOL_VALIDATION_FAILED")
    return completed.stdout


def probe_toolchain(args: argparse.Namespace) -> dict[str, Any]:
    python_path = Path(sys.executable).resolve(strict=True)
    openssl = executable("openssl", args.openssl)
    esptool = executable("esptool", args.esptool)
    mosquitto = executable("mosquitto", args.mosquitto)
    esptool_module = module_file("esptool")
    pyserial_module = module_file("serial")
    return {
        "python_path": python_path,
        "openssl_path": openssl,
        "esptool_path": esptool,
        "mosquitto_path": mosquitto,
        "python_executable_sha256": sha256_file(python_path),
        "openssl_executable_sha256": sha256_file(openssl),
        "esptool_executable_sha256": sha256_file(esptool),
        "esptool_module_sha256": sha256_file(esptool_module),
        "pyserial_module_sha256": sha256_file(pyserial_module),
        "mosquitto_executable_sha256": sha256_file(mosquitto),
    }


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
