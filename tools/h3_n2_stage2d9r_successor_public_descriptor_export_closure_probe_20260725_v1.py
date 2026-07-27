#!/usr/bin/env python3
"""Read-only closure probe for successor public-descriptor export U1-01.

The probe reads only the export consumed-marker and the already-public export
ZIP. It does not read private custody material or private paths, modify files,
claim an authorization, or perform board, serial, Flash, NVS, network, Broker,
PREPARE, VERIFY, ACTIVATE, CLEANUP, or production work.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export-closure-probe/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export-u1-consumption/1"
EXPORT_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export/1"
PUBLIC_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-public/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-20260725-01"
AUTHORIZATION_RECORD_SHA256 = "3c55e5f01071cfebf4f2cb98ab643da09582f1cc94496e4b061d29a6f88e8e73"
AUTHORIZED_SOURCE_SHA = "950fdc26a0b876ffcdf9c2e7c21716cb49b1843d"
AUTHORIZED_GENERATION_SOURCE_SHA = "0cd9eeb5fd567d47a29bddee83159ac9570aa3dd"
GENERATION_MARKER_SHA256 = "428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
PRIVATE_PACKAGE_SHA256 = "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
EXPORT_BINDING_SHA256 = "acb161544e2fb3a381f0d93691f2fecddad31780dc19e2eca39bc4ab0424556c"
EXPORT_ZIP_SHA256 = "77fcded756d3914964138909ca2b51c2a20c60be76eed758049ef6c84ce4d8d1"
EXPORT_FILE_NAME = "Stage2D9R_G3R_Successor_Public_Descriptor_Export_U1_01_20260725.zip"
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
EXPECTED_FILES = (
    "SHA256SUMS",
    "export-binding.json",
    "public-descriptor.redacted.json",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def parse_utc(value: Any, code: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProbeError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed


def default_marker(home: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", AUTHORIZATION_ID)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def default_export(home: Path) -> Path:
    return (home.resolve(strict=True) / "Downloads" / EXPORT_FILE_NAME).resolve(strict=False)


def validate_marker(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "MARKER_MISSING_OR_INVALID")
    before = sha256_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("MARKER_JSON_INVALID") from exc
    require(isinstance(value, dict), "MARKER_JSON_INVALID")
    require(value.get("schema") == MARKER_SCHEMA, "MARKER_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED", "MARKER_STATUS_MISMATCH")
    require(value.get("record_sha256") == AUTHORIZATION_RECORD_SHA256, "RECORD_SHA256_MISMATCH")
    require(value.get("export_zip_sha256") == EXPORT_ZIP_SHA256, "EXPORT_ZIP_SHA256_MISMATCH")
    require(value.get("failure_code") is None, "MARKER_FAILURE_CODE_PRESENT")
    require(value.get("one_shot") is True, "ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "REPLAY_BOUNDARY_MISMATCH")
    require(value.get("automatic_retry_permitted") is False, "RETRY_BOUNDARY_MISMATCH")
    require(value.get("secret_values_included") is False, "SECRET_FLAG_MISMATCH")
    claimed = parse_utc(value.get("claimed_at"), "CLAIMED_AT_INVALID")
    consumed = parse_utc(value.get("consumed_at"), "CONSUMED_AT_INVALID")
    require(consumed >= claimed, "TIMESTAMP_ORDER_INVALID")
    require(sha256_file(path) == before, "MARKER_CHANGED_DURING_PROBE")
    return before


def parse_sums(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("ascii")
    except UnicodeError as exc:
        raise ProbeError("SHA256SUMS_INVALID") from exc
    observed: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("  ", 1)
        require(len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None, "SHA256SUMS_INVALID")
        require(parts[1] not in observed, "SHA256SUMS_DUPLICATE")
        observed[parts[1]] = parts[0]
    require(set(observed) == {"export-binding.json", "public-descriptor.redacted.json"}, "SHA256SUMS_INVENTORY_MISMATCH")
    return observed


def validate_export(path: Path) -> tuple[str, str, str]:
    require(path.is_file() and not path.is_symlink(), "EXPORT_ZIP_MISSING_OR_INVALID")
    require(file_mode(path) == "0600", "EXPORT_ZIP_MODE_MISMATCH")
    before = sha256_file(path)
    require(before == EXPORT_ZIP_SHA256, "EXPORT_ZIP_SHA256_MISMATCH")
    try:
        with zipfile.ZipFile(path) as archive:
            require(tuple(sorted(archive.namelist())) == EXPECTED_FILES, "EXPORT_INVENTORY_MISMATCH")
            for info in archive.infolist():
                require(not info.is_dir(), "EXPORT_DIRECTORY_ENTRY_FORBIDDEN")
                require(((info.external_attr >> 16) & 0o777) == 0o600, "EXPORT_ENTRY_MODE_MISMATCH")
            sums = parse_sums(archive.read("SHA256SUMS"))
            binding_bytes = archive.read("export-binding.json")
            descriptor_bytes = archive.read("public-descriptor.redacted.json")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ProbeError("EXPORT_ZIP_INVALID") from exc
    binding_sha = sha256_bytes(binding_bytes)
    descriptor_sha = sha256_bytes(descriptor_bytes)
    require(binding_sha == EXPORT_BINDING_SHA256, "EXPORT_BINDING_SHA256_MISMATCH")
    require(descriptor_sha == PUBLIC_DESCRIPTOR_SHA256, "PUBLIC_DESCRIPTOR_SHA256_MISMATCH")
    require(sums["export-binding.json"] == binding_sha, "EXPORT_BINDING_SUM_MISMATCH")
    require(sums["public-descriptor.redacted.json"] == descriptor_sha, "PUBLIC_DESCRIPTOR_SUM_MISMATCH")
    try:
        binding = json.loads(binding_bytes.decode("utf-8"))
        descriptor = json.loads(descriptor_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("PUBLIC_JSON_INVALID") from exc
    require(isinstance(binding, dict) and isinstance(descriptor, dict), "PUBLIC_JSON_INVALID")
    expected_binding = {
        "schema": EXPORT_BINDING_SCHEMA,
        "stage": STAGE,
        "state": "PUBLIC_DESCRIPTOR_EXPORTED",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
        "exporter_source_sha": AUTHORIZED_SOURCE_SHA,
        "authorized_generation_source_sha": AUTHORIZED_GENERATION_SOURCE_SHA,
        "generation_marker_sha256": GENERATION_MARKER_SHA256,
        "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
    }
    for key, expected in expected_binding.items():
        require(binding.get(key) == expected, f"EXPORT_BINDING_{key.upper()}_MISMATCH")
    for key in (
        "private_content_included",
        "private_paths_included",
        "secret_values_included",
        "authorization_record_included",
        "board_operation",
        "serial_operation",
        "flash_operation",
        "physical_nvs_operation",
        "network_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "activate_executed",
        "cleanup_executed",
        "production_operation",
    ):
        require(binding.get(key) is False, f"EXPORT_BINDING_{key.upper()}_MISMATCH")
    require(descriptor.get("schema") == PUBLIC_SCHEMA, "PUBLIC_DESCRIPTOR_SCHEMA_MISMATCH")
    require(descriptor.get("source_sha") == AUTHORIZED_GENERATION_SOURCE_SHA, "PUBLIC_DESCRIPTOR_SOURCE_SHA_MISMATCH")
    require(descriptor.get("candidate_digest_sha256") == CANDIDATE_DIGEST_SHA256, "PUBLIC_DESCRIPTOR_CANDIDATE_MISMATCH")
    require(descriptor.get("private_package_sha256") == PRIVATE_PACKAGE_SHA256, "PUBLIC_DESCRIPTOR_PRIVATE_PACKAGE_MISMATCH")
    forbidden = {
        "mqtt_password",
        "persistence_key",
        "unlock_token",
        "private_key",
        "password_database",
        "prepare_command",
        "verify_command",
        "custody_root",
        "private_path",
    }
    require(not forbidden.intersection(descriptor), "PUBLIC_DESCRIPTOR_FORBIDDEN_KEY_PRESENT")
    require(sha256_file(path) == before, "EXPORT_CHANGED_DURING_PROBE")
    return before, binding_sha, descriptor_sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path)
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    try:
        home = Path.home()
        expected_marker = default_marker(home)
        expected_export = default_export(home)
        marker = expected_marker if args.marker is None else args.marker.expanduser().resolve(strict=False)
        export = expected_export if args.export is None else args.export.expanduser().resolve(strict=False)
        require(marker == expected_marker, "MARKER_SELECTION_RULE_MISMATCH")
        require(export == expected_export, "EXPORT_SELECTION_RULE_MISMATCH")
        marker_sha = validate_marker(marker)
        export_sha, binding_sha, descriptor_sha = validate_export(export)
        result = {
            "schema": SCHEMA,
            "stage": STAGE,
            "authorization_id": AUTHORIZATION_ID,
            "status": "CONSUMED",
            "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
            "marker_sha256": marker_sha,
            "export_zip_sha256": export_sha,
            "export_binding_sha256": binding_sha,
            "public_descriptor_sha256": descriptor_sha,
            "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "marker_modified": False,
            "export_modified": False,
            "private_content_read": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
        }
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        print("STAGE2D9R_SUCCESSOR_PUBLIC_DESCRIPTOR_EXPORT_CLOSURE_PROBE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("MARKER_MODIFIED=false")
        print("EXPORT_MODIFIED=false")
        print("PRIVATE_CONTENT_READ=false")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PHYSICAL_NVS_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("PREPARE_EXECUTED=false")
        print("VERIFY_EXECUTED=false")
        return 2
    print("STAGE2D9R_SUCCESSOR_PUBLIC_DESCRIPTOR_EXPORT_CLOSURE_PROBE=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
