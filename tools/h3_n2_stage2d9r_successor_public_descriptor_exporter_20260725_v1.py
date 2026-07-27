#!/usr/bin/env python3
"""One-shot exporter for the Stage 2D-9R successor redacted public descriptor.

Default operation is a read-only state probe. Export requires a separate exact,
unexpired U1 authorization and ``--execute``. The exporter reads only the
already-redacted public descriptor and the consumed generation marker. It never
reads MQTT passwords, persistence keys, unlock tokens, private keys, password
database contents, or PREPARE/VERIFY command files. It performs no board,
serial, Flash, NVS, network, Broker, PREPARE, VERIFY, ACTIVATE or CLEANUP work.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile
from typing import Any

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export-u1-authorization/1"
AUTH_OPERATION = "EXPORT_SUCCESSOR_PUBLIC_DESCRIPTOR"
AUTH_PREFIX = "U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-u1-consumption/1"
EXPORT_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export-u1-consumption/1"
PUBLIC_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-public/1"
EXPORT_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export/1"
PROBE_SCHEMA = "gh.h3.n2.stage2d9r-successor-public-descriptor-export-probe/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
RUN_SUFFIX = "tlsvalid02"
AUTHORIZED_SOURCE_SHA = "0cd9eeb5fd567d47a29bddee83159ac9570aa3dd"
GENERATION_AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01"
GENERATION_RECORD_SHA256 = "99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817"
GENERATION_MARKER_SHA256 = "428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
PRIVATE_PACKAGE_SHA256 = "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
UNLOCK_DIGEST_SHA256 = "727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
BROKER_CERTIFICATE_DER_SHA256 = "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
BROKER_SPKI_SHA256 = "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
PRIVATE_ROOT_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02"
)
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
PUBLIC_DESCRIPTOR_NAME = "public-descriptor.redacted.json"
EXPORT_FILE_NAME = "Stage2D9R_G3R_Successor_Public_Descriptor_Export_U1_01_20260725.zip"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ExportError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ExportError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def parse_utc(value: object, field: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{field.upper()}_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ExportError(f"{field.upper()}_INVALID") from exc
    require(parsed.tzinfo is not None, f"{field.upper()}_INVALID")
    return parsed.astimezone(timezone.utc)


def write_private(path: Path, data: bytes) -> None:
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
    require(file_mode(path) == "0600", "OUTPUT_MODE_MISMATCH")


def replace_private(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".new")
    require(not temporary.exists(), "MARKER_REPLACEMENT_TEMP_EXISTS")
    write_private(temporary, data)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def default_private_root(home: Path) -> Path:
    return (home.resolve(strict=True) / PRIVATE_ROOT_RELATIVE).resolve(strict=False)


def default_generation_marker(home: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", GENERATION_AUTHORIZATION_ID)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def default_export_marker(home: Path, authorization_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", authorization_id)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def default_output(home: Path) -> Path:
    return (home.resolve(strict=True) / "Downloads" / EXPORT_FILE_NAME).resolve(strict=False)


def validate_generation_marker(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), "GENERATION_MARKER_MISSING")
    require(sha256_file(path) == GENERATION_MARKER_SHA256, "GENERATION_MARKER_SHA256_MISMATCH")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("schema") == MARKER_SCHEMA, "GENERATION_MARKER_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == GENERATION_AUTHORIZATION_ID, "GENERATION_AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED", "GENERATION_MARKER_STATUS_MISMATCH")
    require(value.get("record_sha256") == GENERATION_RECORD_SHA256, "GENERATION_RECORD_SHA256_MISMATCH")
    require(value.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256, "GENERATION_PUBLIC_DESCRIPTOR_SHA256_MISMATCH")
    require(value.get("failure_code") is None, "GENERATION_FAILURE_CODE_PRESENT")
    require(value.get("one_shot") is True, "GENERATION_ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "GENERATION_REPLAY_BOUNDARY_MISMATCH")
    require(value.get("automatic_retry_permitted") is False, "GENERATION_RETRY_BOUNDARY_MISMATCH")


def validate_public_descriptor_bytes(
    data: bytes, expected_sha256: str = PUBLIC_DESCRIPTOR_SHA256
) -> dict[str, object]:
    require(sha256_bytes(data) == expected_sha256, "PUBLIC_DESCRIPTOR_SHA256_MISMATCH")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExportError("PUBLIC_DESCRIPTOR_JSON_INVALID") from exc
    require(isinstance(value, dict), "PUBLIC_DESCRIPTOR_JSON_INVALID")
    expected = {
        "schema": PUBLIC_SCHEMA,
        "stage": STAGE,
        "state": "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
        "source_sha": AUTHORIZED_SOURCE_SHA,
        "run_suffix": RUN_SUFFIX,
        "broker_host": "stage2d9r.local",
        "broker_port": 8883,
        "broker_tls_server_name": "stage2d9r.local",
        "mqtt_username": "stage2d9r-test",
        "unlock_digest_sha256": UNLOCK_DIGEST_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
        "broker_certificate_der_sha256": BROKER_CERTIFICATE_DER_SHA256,
        "broker_spki_sha256": BROKER_SPKI_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
    }
    for key, expected_value in expected.items():
        require(value.get(key) == expected_value, f"PUBLIC_DESCRIPTOR_{key.upper()}_MISMATCH")
    for key in (
        "mqtt_password_sha256",
        "persistence_key_file_sha256",
        "prepare_command_sha256",
        "verify_command_sha256",
    ):
        item = value.get(key)
        require(isinstance(item, str) and HEX64.fullmatch(item) is not None, f"PUBLIC_DESCRIPTOR_{key.upper()}_INVALID")
    for key in (
        "private_values_included",
        "private_paths_included",
        "secret_values_included",
        "execution_authorized",
        "board_operation_authorized",
        "serial_operation_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
        "network_operation_authorized",
        "broker_start_authorized",
        "prepare_authorized",
        "verify_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
    ):
        require(value.get(key) is False, f"PUBLIC_DESCRIPTOR_{key.upper()}_MISMATCH")
    forbidden_keys = {
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
    require(not forbidden_keys.intersection(value), "PUBLIC_DESCRIPTOR_FORBIDDEN_KEY_PRESENT")
    return value


def authorization_record_digest(record: dict[str, Any]) -> str:
    bound = dict(record)
    bound.pop("record_sha256", None)
    return canonical_json_sha256(bound)


def validate_authorization(
    record: dict[str, Any], source_sha: str, exporter_sha256: str, python_sha256: str,
    home: Path, now: datetime
) -> tuple[str, Path, str, Path]:
    require(record.get("schema") == AUTH_SCHEMA, "AUTH_SCHEMA_MISMATCH")
    require(record.get("stage") == STAGE, "AUTH_STAGE_MISMATCH")
    authorization_id = record.get("authorization_id")
    require(isinstance(authorization_id, str) and authorization_id.startswith(AUTH_PREFIX), "AUTHORIZATION_ID_INVALID")
    require(record.get("operation") == AUTH_OPERATION, "AUTH_OPERATION_MISMATCH")
    require(record.get("authorized") is True, "AUTH_NOT_GRANTED")
    require(record.get("one_shot") is True, "AUTH_ONE_SHOT_REQUIRED")
    require(record.get("replay_permitted") is False, "AUTH_REPLAY_FORBIDDEN")
    require(record.get("automatic_retry_permitted") is False, "AUTH_AUTO_RETRY_FORBIDDEN")
    require(record.get("source_sha") == source_sha, "AUTH_SOURCE_SHA_MISMATCH")
    require(record.get("authorized_generation_source_sha") == AUTHORIZED_SOURCE_SHA, "AUTH_GENERATION_SOURCE_SHA_MISMATCH")
    require(record.get("generation_marker_sha256") == GENERATION_MARKER_SHA256, "AUTH_GENERATION_MARKER_SHA256_MISMATCH")
    require(record.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256, "AUTH_PUBLIC_DESCRIPTOR_SHA256_MISMATCH")
    require(record.get("exporter_sha256") == exporter_sha256, "AUTH_EXPORTER_SHA256_MISMATCH")
    require(record.get("python_executable_sha256") == python_sha256, "AUTH_PYTHON_SHA256_MISMATCH")
    output = default_output(home)
    require(record.get("output_target_digest_sha256") == sha256_bytes(str(output).encode("utf-8")), "AUTH_OUTPUT_TARGET_DIGEST_MISMATCH")
    require(record.get("output_target_exists") is False, "AUTH_OUTPUT_TARGET_STATE_MISMATCH")
    issued = parse_utc(record.get("issued_at"), "issued_at")
    expires = parse_utc(record.get("expires_at"), "expires_at")
    require(expires - issued == timedelta(hours=2), "AUTH_INTERVAL_NOT_EXACTLY_TWO_HOURS")
    require(issued <= now <= expires, "AUTH_NOT_CURRENT")
    record_sha = authorization_record_digest(record)
    require(record.get("record_sha256") == record_sha, "AUTH_RECORD_DIGEST_MISMATCH")
    marker = default_export_marker(home, authorization_id)
    require(not marker.exists(), "AUTH_ALREADY_CLAIMED_OR_CONSUMED")
    require(not output.exists(), "OUTPUT_TARGET_ALREADY_EXISTS")
    require(output.parent.is_dir(), "OUTPUT_DIRECTORY_MISSING")
    return authorization_id, marker, record_sha, output


def claim(marker: Path, authorization_id: str, record_sha: str) -> None:
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(marker.parent, 0o700)
    payload = {
        "schema": EXPORT_MARKER_SCHEMA,
        "authorization_id": authorization_id,
        "status": "CLAIMED",
        "record_sha256": record_sha,
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
    }
    write_private(marker, json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")


def finalize(marker: Path, status: str, export_sha256: str | None = None, failure_code: str | None = None) -> None:
    value = json.loads(marker.read_text(encoding="utf-8"))
    value["status"] = status
    value["consumed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    value["export_zip_sha256"] = export_sha256
    value["failure_code"] = failure_code
    replace_private(marker, json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    with tempfile.TemporaryFile() as handle:
        with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(entries):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                info.create_system = 3
                archive.writestr(info, entries[name])
        handle.seek(0)
        return handle.read()


def build_export(descriptor_bytes: bytes, source_sha: str, authorization_id: str, record_sha: str) -> tuple[bytes, str]:
    descriptor = validate_public_descriptor_bytes(descriptor_bytes)
    binding = {
        "schema": EXPORT_SCHEMA,
        "stage": STAGE,
        "state": "PUBLIC_DESCRIPTOR_EXPORTED",
        "authorization_id": authorization_id,
        "authorization_record_sha256": record_sha,
        "exporter_source_sha": source_sha,
        "authorized_generation_source_sha": AUTHORIZED_SOURCE_SHA,
        "generation_marker_sha256": GENERATION_MARKER_SHA256,
        "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "candidate_digest_sha256": descriptor["candidate_digest_sha256"],
        "private_content_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "authorization_record_included": False,
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
    binding_bytes = json.dumps(binding, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    binding_sha = sha256_bytes(binding_bytes)
    sums = (
        f"{PUBLIC_DESCRIPTOR_SHA256}  public-descriptor.redacted.json\n"
        f"{binding_sha}  export-binding.json\n"
    ).encode("ascii")
    archive = deterministic_zip(
        {
            "SHA256SUMS": sums,
            "export-binding.json": binding_bytes,
            "public-descriptor.redacted.json": descriptor_bytes,
        }
    )
    return archive, binding_sha


def probe(home: Path, exporter_path: Path) -> dict[str, object]:
    output = default_output(home)
    generation_marker = default_generation_marker(home)
    return {
        "schema": PROBE_SCHEMA,
        "stage": STAGE,
        "source_sha": AUTHORIZED_SOURCE_SHA,
        "exporter_sha256": sha256_file(exporter_path.resolve(strict=True)),
        "python_executable_sha256": sha256_file(Path(sys.executable).resolve(strict=True)),
        "generation_marker_exists": generation_marker.is_file(),
        "generation_marker_sha256": sha256_file(generation_marker) if generation_marker.is_file() else None,
        "expected_generation_marker_sha256": GENERATION_MARKER_SHA256,
        "expected_public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "output_target_digest_sha256": sha256_bytes(str(output).encode("utf-8")),
        "output_target_exists": output.exists(),
        "private_descriptor_content_read": False,
        "secret_values_included": False,
        "private_paths_included": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }


def execute(authorization_path: Path, source_sha: str, home: Path, exporter_path: Path) -> dict[str, object]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    exporter_sha = sha256_file(exporter_path.resolve(strict=True))
    python_sha = sha256_file(Path(sys.executable).resolve(strict=True))
    record = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization_id, marker, record_sha, output = validate_authorization(
        record, source_sha, exporter_sha, python_sha, home, datetime.now(timezone.utc)
    )
    generation_marker = default_generation_marker(home)
    validate_generation_marker(generation_marker)
    descriptor_path = default_private_root(home) / PUBLIC_DESCRIPTOR_NAME
    require(descriptor_path.is_file() and not descriptor_path.is_symlink(), "PUBLIC_DESCRIPTOR_MISSING")
    claim(marker, authorization_id, record_sha)
    try:
        descriptor_bytes = descriptor_path.read_bytes()
        archive, binding_sha = build_export(descriptor_bytes, source_sha, authorization_id, record_sha)
        write_private(output, archive)
        export_sha = sha256_bytes(archive)
        finalize(marker, "CONSUMED", export_sha256=export_sha)
        return {
            "schema": "gh.h3.n2.stage2d9r-successor-public-descriptor-export-result/1",
            "status": "PASS",
            "authorization_id": authorization_id,
            "source_sha": source_sha,
            "authorized_generation_source_sha": AUTHORIZED_SOURCE_SHA,
            "generation_marker_sha256": GENERATION_MARKER_SHA256,
            "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
            "export_binding_sha256": binding_sha,
            "export_zip_sha256": export_sha,
            "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
            "authorization_consumed": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_content_included": False,
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
        }
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ExportError) and exc.args else type(exc).__name__
        if marker.exists():
            finalize(marker, "CONSUMED_FAILED", failure_code=str(code))
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-state", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=Path)
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    home = Path.home().resolve(strict=True)
    exporter_path = Path(__file__).resolve(strict=True)
    try:
        if args.probe_state and not args.execute:
            print("STAGE2D9R_SUCCESSOR_PUBLIC_DESCRIPTOR_EXPORT_PROBE=PASS")
            print(json.dumps(probe(home, exporter_path), sort_keys=True))
            return 0
        require(args.execute, "EXPORT_REQUIRES_EXPLICIT_EXECUTE")
        require(not args.probe_state, "PROBE_AND_EXECUTE_MUTUALLY_EXCLUSIVE")
        require(args.authorization_record is not None, "AUTHORIZATION_RECORD_REQUIRED")
        require(args.source_sha is not None, "SOURCE_SHA_REQUIRED")
        result = execute(
            args.authorization_record.expanduser().resolve(strict=True),
            args.source_sha,
            home,
            exporter_path,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ExportError) and exc.args else type(exc).__name__
        print("STAGE2D9R_SUCCESSOR_PUBLIC_DESCRIPTOR_EXPORT=FAIL")
        print(f"FAILURE_CODE={code}")
        print("PRIVATE_CONTENT_INCLUDED=false")
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
    print("STAGE2D9R_SUCCESSOR_PUBLIC_DESCRIPTOR_EXPORT=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
