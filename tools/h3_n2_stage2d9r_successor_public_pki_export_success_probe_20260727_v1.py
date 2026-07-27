#!/usr/bin/env python3
"""Read-only closure probe for the consumed successor public PKI export U1."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any
import zipfile

SCHEMA = "gh.h3.n2.stage2d9r-successor-public-pki-export-success-probe/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-pki-export-u1-consumption/1"
EXPORT_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-pki-export/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-20260725-01"
AUTHORIZED_SOURCE_SHA = "d6a2304ef1b9b229ed515f2fdc00e0146888b7d7"
AUTHORIZATION_RECORD_SHA256 = "8b2fb72bc61a14d8618a03fd5c3c029253d3b05232de2fae06517fdf38c7c839"
EXPORT_ZIP_SHA256 = "c54f134bc9f135881a74462aecfc561ce89739724cdfeca41ae54dbc735dec6b"
EXPORT_BINDING_SHA256 = "0a38ef9648008cbd7a3966e5e558bb8a9b672f255fa6e390800508cd93555734"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
BROKER_DER_SHA256 = "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
BROKER_SPKI_SHA256 = "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
OUTPUT_NAME = "Stage2D9R_G3R_Successor_Public_PKI_Export_U1_01_20260725.zip"
EXPECTED_ENTRIES = {
    "SHA256SUMS",
    "broker.cert.pem",
    "broker.fullchain.pem",
    "public-descriptor.redacted.json",
    "public-pki-export-binding.json",
    "root-ca.cert.pem",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def default_output(home: Path) -> Path:
    return (home.resolve(strict=True) / "Downloads" / OUTPUT_NAME).resolve(strict=False)


def validate_marker(marker: Path) -> dict[str, object]:
    require(marker.is_file() and not marker.is_symlink(), "MARKER_MISSING_OR_INVALID")
    require(file_mode(marker) == "0600", "MARKER_MODE_MISMATCH")
    before_sha = sha256_file(marker)
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("MARKER_JSON_INVALID") from exc
    require(isinstance(value, dict), "MARKER_JSON_INVALID")
    require(value.get("schema") == MARKER_SCHEMA, "MARKER_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED", "MARKER_STATUS_MISMATCH")
    require(
        value.get("record_sha256") == AUTHORIZATION_RECORD_SHA256,
        "AUTHORIZATION_RECORD_SHA256_MISMATCH",
    )
    require(value.get("export_zip_sha256") == EXPORT_ZIP_SHA256, "EXPORT_ZIP_SHA256_MISMATCH")
    require(value.get("failure_code") is None, "MARKER_FAILURE_CODE_PRESENT")
    require(value.get("one_shot") is True, "ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "REPLAY_BOUNDARY_MISMATCH")
    require(
        value.get("automatic_retry_permitted") is False,
        "AUTOMATIC_RETRY_BOUNDARY_MISMATCH",
    )
    require(value.get("secret_values_included") is False, "SECRET_VALUE_FLAG_MISMATCH")
    claimed = parse_utc(value.get("claimed_at"), "CLAIMED_AT_INVALID")
    consumed = parse_utc(value.get("consumed_at"), "CONSUMED_AT_INVALID")
    require(consumed >= claimed, "MARKER_TIMESTAMP_ORDER_INVALID")
    after_sha = sha256_file(marker)
    require(after_sha == before_sha, "MARKER_CHANGED_DURING_PROBE")
    require(HEX64.fullmatch(before_sha) is not None, "MARKER_SHA256_INVALID")
    return {
        "marker_sha256": before_sha,
        "marker_modified": False,
        "authorization_consumed": True,
    }


def parse_sums(value: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = value.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ProbeError("SHA256SUMS_INVALID") from exc
    for line in lines:
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        require(HEX64.fullmatch(digest) is not None, "SHA256SUMS_INVALID")
        require(name and name not in result, "SHA256SUMS_INVALID")
        result[name] = digest
    return result


def validate_output(output: Path) -> dict[str, object]:
    require(output.is_file() and not output.is_symlink(), "OUTPUT_MISSING_OR_INVALID")
    require(file_mode(output) == "0600", "OUTPUT_MODE_MISMATCH")
    output_sha = sha256_file(output)
    require(output_sha == EXPORT_ZIP_SHA256, "OUTPUT_SHA256_MISMATCH")
    try:
        with zipfile.ZipFile(output) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            require(set(names) == EXPECTED_ENTRIES and len(names) == 6, "OUTPUT_INVENTORY_MISMATCH")
            for info in infos:
                require(((info.external_attr >> 16) & 0o777) == 0o600, "ARCHIVE_MODE_MISMATCH")
                require(info.date_time == (1980, 1, 1, 0, 0, 0), "ARCHIVE_TIMESTAMP_MISMATCH")
            entries = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ProbeError("OUTPUT_ZIP_INVALID") from exc

    sums = parse_sums(entries["SHA256SUMS"])
    expected_sum_names = EXPECTED_ENTRIES - {"SHA256SUMS"}
    require(set(sums) == expected_sum_names, "SHA256SUMS_INVENTORY_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(entries[name]) == digest, "SHA256SUMS_MISMATCH")

    binding_bytes = entries["public-pki-export-binding.json"]
    require(sha256_bytes(binding_bytes) == EXPORT_BINDING_SHA256, "EXPORT_BINDING_SHA256_MISMATCH")
    try:
        binding = json.loads(binding_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError("EXPORT_BINDING_JSON_INVALID") from exc
    require(binding.get("schema") == EXPORT_SCHEMA, "EXPORT_BINDING_SCHEMA_MISMATCH")
    require(binding.get("stage") == STAGE, "EXPORT_BINDING_STAGE_MISMATCH")
    require(binding.get("state") == "PUBLIC_PKI_EXPORTED", "EXPORT_BINDING_STATE_MISMATCH")
    require(binding.get("authorization_id") == AUTHORIZATION_ID, "EXPORT_BINDING_AUTH_ID_MISMATCH")
    require(
        binding.get("authorization_record_sha256") == AUTHORIZATION_RECORD_SHA256,
        "EXPORT_BINDING_RECORD_SHA256_MISMATCH",
    )
    require(binding.get("exporter_source_sha") == AUTHORIZED_SOURCE_SHA, "EXPORT_BINDING_SOURCE_MISMATCH")
    require(
        binding.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256,
        "PUBLIC_DESCRIPTOR_SHA256_MISMATCH",
    )
    require(
        binding.get("candidate_digest_sha256") == CANDIDATE_DIGEST_SHA256,
        "CANDIDATE_DIGEST_SHA256_MISMATCH",
    )
    require(binding.get("ca_pem_sha256") == CA_PEM_SHA256, "CA_PEM_SHA256_MISMATCH")
    require(binding.get("broker_der_sha256") == BROKER_DER_SHA256, "BROKER_DER_SHA256_MISMATCH")
    require(binding.get("broker_spki_sha256") == BROKER_SPKI_SHA256, "BROKER_SPKI_SHA256_MISMATCH")
    require(binding.get("certificate_chain_valid") is True, "CERTIFICATE_CHAIN_INVALID")
    require(binding.get("broker_hostname_match") is True, "BROKER_HOSTNAME_MISMATCH")
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
        require(binding.get(key) is False, f"BOUNDARY_{key.upper()}_MISMATCH")
    return {
        "output_zip_sha256": output_sha,
        "export_binding_sha256": sha256_bytes(binding_bytes),
        "output_mode": "0600",
        "output_entry_count": 6,
        "internal_sha256sums_valid": True,
        "archive_modes_valid": True,
        "archive_timestamps_deterministic": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        home = Path.home().resolve(strict=True)
        expected_marker = default_marker(home)
        expected_output = default_output(home)
        marker = expected_marker if args.marker is None else args.marker.expanduser().resolve(strict=False)
        output = expected_output if args.output is None else args.output.expanduser().resolve(strict=False)
        require(marker == expected_marker, "MARKER_SELECTION_RULE_MISMATCH")
        require(output == expected_output, "OUTPUT_SELECTION_RULE_MISMATCH")
        marker_result = validate_marker(marker)
        output_result = validate_output(output)
        result = {
            "schema": SCHEMA,
            "stage": STAGE,
            "authorization_id": AUTHORIZATION_ID,
            "status": "PASS",
            "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
            **marker_result,
            **output_result,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
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
        print("STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT_SUCCESS_PROBE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("MARKER_MODIFIED=false")
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
    print("STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT_SUCCESS_PROBE=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
