#!/usr/bin/env python3
"""One-shot offline U1 generator for repaired Stage 2D-9R private material.

The default invocation is inert and prints a source-only status.  Toolchain
probing is read-only.  Secret generation requires an exact, current, mode-0600
U1 authorization record and ``--execute``.  This module never enumerates USB or
serial devices, opens a serial port, invokes esptool, accesses a board, writes
Flash/NVS, starts a Broker, opens a socket, or sends PREPARE/VERIFY.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-u1-authorization/1"
AUTH_OPERATION = "GENERATE_REPAIRED_SUCCESSOR_PRIVATE_MATERIAL"
AUTH_PREFIX = "U1-H3N2-STAGE2D9R-G3R-REPAIRED-PRIVATE-MATERIAL-"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-u1-consumption/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-generation-result/1"
PRIVATE_DESCRIPTOR_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-custody/1"
TOOLCHAIN_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-toolchain-probe/1"
STAGE = chain.STAGE
CUSTODY_RULE = chain.CUSTODY_SELECTION_RULE
CUSTODY_RELATIVE = Path(chain.CUSTODY_RELATIVE)
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
PRIVATE_DESCRIPTOR = "private-custody-descriptor.json"
PUBLIC_DESCRIPTOR = "public-descriptor.redacted.json"
ROOT_CA_CN = "Stage2D9R Repaired Successor Test Root CA"
ROOT_VALID_DAYS = 365
LEAF_VALID_DAYS = 30
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

PRIVATE_FILENAMES = {
    "mqtt_password_preimage": "mqtt-password.hex",
    "mosquitto_password_database": "mosquitto.password",
    "persistence_key": "persistence-key.hex",
    "unlock_token": "unlock-token.hex",
    "prepare_command": "prepare-command.txt",
    "verify_command": "verify-command.txt",
    "root_ca_private_key": "root-ca.key.pem",
    "root_ca_certificate": "root-ca.cert.pem",
    "broker_private_key": "broker.key.pem",
    "broker_certificate": "broker.cert.pem",
    "broker_full_chain": "broker.fullchain.pem",
    "isolated_broker_configuration": "mosquitto.stage2d9r.conf",
    "isolated_broker_acl": "mosquitto.stage2d9r.acl",
}
assert set(PRIVATE_FILENAMES.values()) == set(contract.REQUIRED_PRIVATE_FILES)


class GenerationError(RuntimeError):
    """Fail-closed repaired-successor generation error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GenerationError(code)


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


def parse_utc(value: object, field: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{field.upper()}_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GenerationError(f"{field.upper()}_INVALID") from exc
    require(parsed.tzinfo is not None, f"{field.upper()}_INVALID")
    return parsed.astimezone(timezone.utc)


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def regular_file(path: Path, expected_mode: str, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == expected_mode, code)


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
    require(file_mode(path) == "0600", "PRIVATE_FILE_MODE_MISMATCH")


def replace_private(path: Path, data: bytes) -> None:
    regular_file(path, "0600", "PRIVATE_REPLACEMENT_TARGET_INVALID")
    temporary = path.with_name(path.name + ".new")
    require(not temporary.exists(), "PRIVATE_REPLACEMENT_TEMP_EXISTS")
    write_private(temporary, data)
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    require(file_mode(path) == "0600", "PRIVATE_FILE_MODE_MISMATCH")


def resolve_executable(name: str, explicit: Path | None = None) -> Path:
    candidate = str(explicit) if explicit is not None else shutil.which(name)
    require(candidate is not None, f"REQUIRED_EXECUTABLE_UNAVAILABLE_{name.upper()}")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(
        path.is_file() and not path.is_symlink() and os.access(path, os.X_OK),
        f"EXECUTABLE_INVALID_{name.upper()}",
    )
    return path


def executable_version(path: Path, args: tuple[str, ...]) -> str:
    completed = subprocess.run(
        [str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=15,
        env={"PATH": str(path.parent), "LC_ALL": "C"},
    )
    require(completed.returncode in (0, 1), "TOOL_VERSION_PROBE_FAILED")
    text = (completed.stdout or completed.stderr).decode("utf-8", errors="replace")
    line = next((item.strip() for item in text.splitlines() if item.strip()), "")
    require(bool(line), "TOOL_VERSION_EMPTY")
    return line[:240]


def run_checked(command: list[str], input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        env={"PATH": str(Path(command[0]).resolve().parent), "LC_ALL": "C"},
    )
    require(completed.returncode == 0, "OFFLINE_TOOL_COMMAND_FAILED")
    return completed.stdout


@dataclass(frozen=True)
class Toolchain:
    generator_sha256: str
    contract_sha256: str
    chain_contract_sha256: str
    protocol_sha256: str
    python_executable_sha256: str
    python_version: str
    openssl_path: Path
    openssl_executable_sha256: str
    openssl_version: str
    mosquitto_passwd_path: Path
    mosquitto_passwd_executable_sha256: str
    mosquitto_passwd_version: str


def probe_toolchain(
    generator_path: Path,
    contract_path: Path,
    chain_contract_path: Path,
    protocol_path: Path,
    openssl: Path | None = None,
    mosquitto_passwd: Path | None = None,
) -> Toolchain:
    openssl_path = resolve_executable("openssl", openssl)
    passwd_path = resolve_executable("mosquitto_passwd", mosquitto_passwd)
    python_path = Path(sys.executable).resolve(strict=True)
    return Toolchain(
        generator_sha256=sha256_file(generator_path.resolve(strict=True)),
        contract_sha256=sha256_file(contract_path.resolve(strict=True)),
        chain_contract_sha256=sha256_file(chain_contract_path.resolve(strict=True)),
        protocol_sha256=sha256_file(protocol_path.resolve(strict=True)),
        python_executable_sha256=sha256_file(python_path),
        python_version=sys.version.replace("\n", " ")[:240],
        openssl_path=openssl_path,
        openssl_executable_sha256=sha256_file(openssl_path),
        openssl_version=executable_version(openssl_path, ("version",)),
        mosquitto_passwd_path=passwd_path,
        mosquitto_passwd_executable_sha256=sha256_file(passwd_path),
        mosquitto_passwd_version=executable_version(passwd_path, ("-h",)),
    )


def default_custody_root(home: Path) -> Path:
    return (home.resolve(strict=True) / CUSTODY_RELATIVE).resolve(strict=False)


def default_consumed_marker(home: Path, authorization_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", authorization_id)
    return (
        home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json"
    ).resolve(strict=False)


def validate_private_root(
    root: Path, home: Path, repository_root: Path | None
) -> None:
    home_resolved = home.resolve(strict=True)
    require(
        root.resolve(strict=False) == default_custody_root(home_resolved),
        "CUSTODY_RULE_MISMATCH",
    )
    require(not root.exists(), "CUSTODY_ROOT_ALREADY_EXISTS")
    require(root.is_relative_to(home_resolved), "CUSTODY_ROOT_OUTSIDE_HOME")
    for forbidden in (Path("/tmp"), Path("/private/tmp"), Path("/Users/Shared")):
        try:
            root.relative_to(forbidden)
        except ValueError:
            continue
        raise GenerationError("CUSTODY_ROOT_SHARED_TEMPORARY")
    if repository_root is not None:
        repo = repository_root.resolve(strict=True)
        require(not root.is_relative_to(repo), "CUSTODY_ROOT_INSIDE_REPOSITORY")


def authorization_record_digest(record: dict[str, Any]) -> str:
    bound = dict(record)
    bound.pop("record_sha256", None)
    return canonical_json_sha256(bound)


def validate_authorization(
    record: dict[str, Any],
    source_sha: str,
    toolchain: Toolchain,
    home: Path,
    now: datetime,
) -> tuple[str, Path, str]:
    require(record.get("schema") == AUTH_SCHEMA, "AUTH_SCHEMA_MISMATCH")
    require(record.get("stage") == STAGE, "AUTH_STAGE_MISMATCH")
    require(record.get("decision_id") == chain.DECISION_ID, "AUTH_DECISION_MISMATCH")
    authorization_id = record.get("authorization_id")
    require(
        isinstance(authorization_id, str) and authorization_id.startswith(AUTH_PREFIX),
        "AUTHORIZATION_ID_INVALID",
    )
    require(record.get("operation") == AUTH_OPERATION, "AUTH_OPERATION_MISMATCH")
    require(record.get("authorized") is True, "AUTH_NOT_GRANTED")
    require(record.get("one_shot") is True, "AUTH_ONE_SHOT_REQUIRED")
    require(record.get("replay_permitted") is False, "AUTH_REPLAY_FORBIDDEN")
    require(
        record.get("automatic_retry_permitted") is False,
        "AUTH_AUTO_RETRY_FORBIDDEN",
    )
    require(record.get("run_suffix") == chain.RUN_SUFFIX, "AUTH_RUN_SUFFIX_MISMATCH")
    require(
        record.get("custody_root_selection_rule") == CUSTODY_RULE,
        "AUTH_CUSTODY_RULE_MISMATCH",
    )
    require(record.get("current_main_sha") == chain.CURRENT_MAIN_SHA, "AUTH_MAIN_SHA_MISMATCH")
    require(record.get("base_head_sha") == chain.BASE_HEAD_SHA, "AUTH_BASE_HEAD_MISMATCH")
    require(
        record.get("repair_source_binding") == chain.REPAIR_SOURCE_BINDING,
        "AUTH_REPAIR_BINDING_MISMATCH",
    )
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    require(source_sha != chain.BASE_HEAD_SHA, "SOURCE_SHA_MUST_EXTEND_REPAIR_BASE")
    require(record.get("source_sha") == source_sha, "AUTH_SOURCE_SHA_MISMATCH")
    expected = {
        "generator_sha256": toolchain.generator_sha256,
        "contract_sha256": toolchain.contract_sha256,
        "chain_contract_sha256": toolchain.chain_contract_sha256,
        "protocol_sha256": toolchain.protocol_sha256,
        "python_executable_sha256": toolchain.python_executable_sha256,
        "openssl_executable_sha256": toolchain.openssl_executable_sha256,
        "mosquitto_passwd_executable_sha256": toolchain.mosquitto_passwd_executable_sha256,
    }
    for key, value in expected.items():
        require(record.get(key) == value, f"AUTH_{key.upper()}_MISMATCH")
    root = default_custody_root(home)
    require(
        record.get("custody_root_digest_sha256")
        == sha256_bytes(str(root).encode("utf-8")),
        "AUTH_CUSTODY_DIGEST_MISMATCH",
    )
    issued = parse_utc(record.get("issued_at"), "issued_at")
    expires = parse_utc(record.get("expires_at"), "expires_at")
    require(expires > issued, "AUTH_INTERVAL_INVALID")
    require(expires - issued <= timedelta(hours=2), "AUTH_INTERVAL_TOO_LONG")
    require(issued <= now <= expires, "AUTH_NOT_CURRENT")
    record_sha = authorization_record_digest(record)
    require(record.get("record_sha256") == record_sha, "AUTH_RECORD_DIGEST_MISMATCH")
    marker = default_consumed_marker(home, authorization_id)
    require(not marker.exists(), "AUTH_ALREADY_CLAIMED_OR_CONSUMED")
    return authorization_id, marker, record_sha


def claim_authorization(marker: Path, authorization_id: str, record_sha: str) -> None:
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(marker.parent, 0o700)
    require(file_mode(marker.parent) == "0700", "AUTH_DIRECTORY_MODE_MISMATCH")
    payload = {
        "schema": MARKER_SCHEMA,
        "authorization_id": authorization_id,
        "status": "CLAIMED",
        "record_sha256": record_sha,
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
    }
    write_private(marker, json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n")


def finalize_authorization(
    marker: Path,
    status: str,
    *,
    public_descriptor_sha256: str | None = None,
    failure_code: str | None = None,
) -> None:
    current = json.loads(marker.read_text(encoding="utf-8"))
    current["status"] = status
    current["consumed_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    current["public_descriptor_sha256"] = public_descriptor_sha256
    current["failure_code"] = failure_code
    replace_private(
        marker, json.dumps(current, sort_keys=True, indent=2).encode() + b"\n"
    )


def build_acl() -> str:
    return (
        f"user {contract.MQTT_USERNAME}\n"
        f"topic readwrite gh-test/gh-test-run-{chain.RUN_SUFFIX}/node/#\n"
    )


def build_broker_configuration(root: Path) -> str:
    path = {key: root / value for key, value in PRIVATE_FILENAMES.items()}
    return "\n".join(
        (
            "per_listener_settings true",
            f"listener {contract.PORT} 127.0.0.1",
            "protocol mqtt",
            "allow_anonymous false",
            f"password_file {path['mosquitto_password_database']}",
            f"acl_file {path['isolated_broker_acl']}",
            f"cafile {path['root_ca_certificate']}",
            f"certfile {path['broker_certificate']}",
            f"keyfile {path['broker_private_key']}",
            "require_certificate false",
            "tls_version tlsv1.2",
            "persistence false",
            "connection_messages true",
            "log_type all",
            "",
        )
    )


def generate_certificates(root: Path, openssl: Path) -> None:
    root_key = root / PRIVATE_FILENAMES["root_ca_private_key"]
    root_cert = root / PRIVATE_FILENAMES["root_ca_certificate"]
    broker_key = root / PRIVATE_FILENAMES["broker_private_key"]
    broker_cert = root / PRIVATE_FILENAMES["broker_certificate"]
    fullchain = root / PRIVATE_FILENAMES["broker_full_chain"]
    run_checked(
        [
            str(openssl), "genpkey", "-algorithm", "RSA", "-pkeyopt",
            "rsa_keygen_bits:2048", "-out", str(root_key),
        ]
    )
    os.chmod(root_key, 0o600)
    run_checked(
        [
            str(openssl), "req", "-x509", "-new", "-key", str(root_key),
            "-sha256", "-days", str(ROOT_VALID_DAYS), "-subj", f"/CN={ROOT_CA_CN}",
            "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-out", str(root_cert),
        ]
    )
    os.chmod(root_cert, 0o600)
    run_checked(
        [
            str(openssl), "genpkey", "-algorithm", "RSA", "-pkeyopt",
            "rsa_keygen_bits:2048", "-out", str(broker_key),
        ]
    )
    os.chmod(broker_key, 0o600)
    csr = root / ".broker.csr.pem"
    ext = root / ".broker.ext.cnf"
    try:
        run_checked(
            [
                str(openssl), "req", "-new", "-key", str(broker_key),
                "-subj", f"/CN={contract.HOST}", "-out", str(csr),
            ]
        )
        os.chmod(csr, 0o600)
        write_private(
            ext,
            (
                "basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth\n"
                f"subjectAltName=DNS:{contract.HOST}\n"
            ).encode("ascii"),
        )
        serial = secrets.token_hex(16).lstrip("0") or "1"
        run_checked(
            [
                str(openssl), "x509", "-req", "-in", str(csr), "-CA",
                str(root_cert), "-CAkey", str(root_key), "-set_serial", "0x" + serial,
                "-days", str(LEAF_VALID_DAYS), "-sha256", "-extfile", str(ext),
                "-out", str(broker_cert),
            ]
        )
        os.chmod(broker_cert, 0o600)
    finally:
        for temporary in (csr, ext):
            if temporary.exists():
                temporary.unlink()
    write_private(fullchain, broker_cert.read_bytes() + root_cert.read_bytes())


def generate_password_database(
    root: Path, password_hex: str, executable: Path
) -> None:
    target = root / PRIVATE_FILENAMES["mosquitto_password_database"]
    temporary = root / ".mosquitto.password.plain"
    write_private(
        temporary, f"{contract.MQTT_USERNAME}:{password_hex}\n".encode("ascii")
    )
    try:
        run_checked(
            [str(executable), "-H", "sha512-pbkdf2", "-U", str(temporary)]
        )
        hashed = temporary.read_text(encoding="ascii").strip()
        require(
            password_hex not in hashed
            and contract.verify_mosquitto_sha512_pbkdf2(password_hex, hashed),
            "PASSWORD_DATABASE_CROSS_BINDING_FAILED",
        )
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def certificate_public_digests(root: Path, openssl: Path) -> tuple[str, str]:
    broker_cert = root / PRIVATE_FILENAMES["broker_certificate"]
    der = run_checked(
        [str(openssl), "x509", "-in", str(broker_cert), "-outform", "DER"]
    )
    public_pem = run_checked(
        [str(openssl), "x509", "-in", str(broker_cert), "-pubkey", "-noout"]
    )
    spki_der = run_checked(
        [str(openssl), "pkey", "-pubin", "-outform", "DER"],
        input_bytes=public_pem,
    )
    return sha256_bytes(der), sha256_bytes(spki_der)


def validate_offline_pki(root: Path, openssl: Path) -> None:
    root_key = root / PRIVATE_FILENAMES["root_ca_private_key"]
    root_cert = root / PRIVATE_FILENAMES["root_ca_certificate"]
    broker_key = root / PRIVATE_FILENAMES["broker_private_key"]
    broker_cert = root / PRIVATE_FILENAMES["broker_certificate"]
    run_checked(
        [
            str(openssl), "verify", "-CAfile", str(root_cert),
            "-verify_hostname", contract.HOST, str(broker_cert),
        ]
    )
    root_key_pub = run_checked(
        [str(openssl), "pkey", "-in", str(root_key), "-pubout", "-outform", "DER"]
    )
    root_cert_public_pem = run_checked(
        [str(openssl), "x509", "-in", str(root_cert), "-pubkey", "-noout"]
    )
    root_cert_pub = run_checked(
        [str(openssl), "pkey", "-pubin", "-outform", "DER"],
        input_bytes=root_cert_public_pem,
    )
    require(root_key_pub == root_cert_pub, "ROOT_CA_KEY_CERT_MISMATCH")
    broker_key_pub = run_checked(
        [str(openssl), "pkey", "-in", str(broker_key), "-pubout", "-outform", "DER"]
    )
    broker_cert_public_pem = run_checked(
        [str(openssl), "x509", "-in", str(broker_cert), "-pubkey", "-noout"]
    )
    broker_cert_pub = run_checked(
        [str(openssl), "pkey", "-pubin", "-outform", "DER"],
        input_bytes=broker_cert_public_pem,
    )
    require(broker_key_pub == broker_cert_pub, "BROKER_KEY_CERT_MISMATCH")


def material_metadata(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for filename in contract.REQUIRED_PRIVATE_FILES:
        path = root / filename
        regular_file(path, "0600", "PRIVATE_MATERIAL_INVALID")
        result[filename] = {
            "relative_path": filename,
            "mode": "0600",
            "sha256": sha256_file(path),
        }
    return result


def toolchain_public_summary(toolchain: Toolchain, home: Path) -> dict[str, object]:
    root = default_custody_root(home)
    return {
        "schema": TOOLCHAIN_SCHEMA,
        "stage": STAGE,
        "decision_id": chain.DECISION_ID,
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
        "custody_root_selection_rule": CUSTODY_RULE,
        "custody_root_digest_sha256": sha256_bytes(str(root).encode("utf-8")),
        "custody_root_exists": root.exists(),
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_generation": False,
        "private_material_created": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }


def execute_generation(
    authorization_path: Path,
    source_sha: str,
    repository_root: Path | None,
    toolchain: Toolchain,
    home: Path,
) -> dict[str, object]:
    regular_file(authorization_path, "0600", "AUTHORIZATION_RECORD_INVALID")
    record = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization_id, marker, record_sha = validate_authorization(
        record, source_sha, toolchain, home, datetime.now(timezone.utc)
    )
    root = default_custody_root(home)
    validate_private_root(root, home, repository_root)
    claim_authorization(marker, authorization_id, record_sha)
    try:
        root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root.parent, 0o700)
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        require(file_mode(root) == "0700", "CUSTODY_ROOT_MODE_MISMATCH")

        mqtt_password = secrets.token_hex(32)
        persistence_key = secrets.token_hex(32)
        unlock_token = secrets.token_hex(32)
        for value, code in (
            (mqtt_password, "MQTT_PASSWORD_INVALID"),
            (persistence_key, "PERSISTENCE_KEY_INVALID"),
            (unlock_token, "UNLOCK_TOKEN_INVALID"),
        ):
            contract.validate_secret_hex(value, code)

        write_private(
            root / PRIVATE_FILENAMES["mqtt_password_preimage"],
            (mqtt_password + "\n").encode("ascii"),
        )
        write_private(
            root / PRIVATE_FILENAMES["persistence_key"],
            (persistence_key + "\n").encode("ascii"),
        )
        write_private(
            root / PRIVATE_FILENAMES["unlock_token"],
            (unlock_token + "\n").encode("ascii"),
        )
        generate_certificates(root, toolchain.openssl_path)
        generate_password_database(
            root, mqtt_password, toolchain.mosquitto_passwd_path
        )

        ca_path = root / PRIVATE_FILENAMES["root_ca_certificate"]
        ca_pem = ca_path.read_text(encoding="ascii")
        prepare, verify, candidate_sha, unlock_digest = contract.render_commands(
            unlock_token, persistence_key, mqtt_password, ca_pem
        )
        write_private(
            root / PRIVATE_FILENAMES["prepare_command"], prepare.encode("utf-8")
        )
        write_private(
            root / PRIVATE_FILENAMES["verify_command"], verify.encode("utf-8")
        )
        write_private(
            root / PRIVATE_FILENAMES["isolated_broker_acl"],
            build_acl().encode("utf-8"),
        )
        write_private(
            root / PRIVATE_FILENAMES["isolated_broker_configuration"],
            build_broker_configuration(root).encode("utf-8"),
        )

        validate_offline_pki(root, toolchain.openssl_path)
        password_line = (
            root / PRIVATE_FILENAMES["mosquitto_password_database"]
        ).read_text(encoding="ascii").strip()
        require(
            contract.verify_mosquitto_sha512_pbkdf2(mqtt_password, password_line),
            "PASSWORD_DATABASE_CROSS_BINDING_FAILED",
        )
        require(
            contract.candidate_digest(mqtt_password, ca_pem) == candidate_sha,
            "CANDIDATE_DIGEST_CROSS_BINDING_FAILED",
        )
        parsed_prepare = protocol.parse_prepare(prepare, unlock_digest)
        parsed_verify = protocol.parse_verify(verify, unlock_digest)
        require(
            parsed_prepare.candidate_digest == candidate_sha,
            "PREPARE_PARSE_CROSS_BINDING_FAILED",
        )
        require(
            parsed_verify.candidate_digest == candidate_sha,
            "VERIFY_PARSE_CROSS_BINDING_FAILED",
        )

        materials = material_metadata(root)
        private_package_sha = contract.private_material_digest(materials)
        cert_der_sha, broker_spki_sha = certificate_public_digests(
            root, toolchain.openssl_path
        )
        public_descriptor = contract.build_public_descriptor(
            source_sha=source_sha,
            generator_sha256=toolchain.generator_sha256,
            contract_sha256=toolchain.contract_sha256,
            chain_contract_sha256=toolchain.chain_contract_sha256,
            protocol_sha256=toolchain.protocol_sha256,
            mqtt_password_sha256=sha256_bytes(mqtt_password.encode("ascii")),
            unlock_digest_sha256=unlock_digest,
            persistence_key_file_sha256=sha256_file(
                root / PRIVATE_FILENAMES["persistence_key"]
            ),
            ca_pem_sha256=sha256_file(ca_path),
            broker_certificate_der_sha256=cert_der_sha,
            broker_spki_sha256=broker_spki_sha,
            candidate_digest_sha256=candidate_sha,
            prepare_command_sha256=sha256_file(
                root / PRIVATE_FILENAMES["prepare_command"]
            ),
            verify_command_sha256=sha256_file(
                root / PRIVATE_FILENAMES["verify_command"]
            ),
            private_package_sha256=private_package_sha,
        )
        public_bytes = (
            json.dumps(public_descriptor, indent=2, sort_keys=True).encode("utf-8")
            + b"\n"
        )
        write_private(root / PUBLIC_DESCRIPTOR, public_bytes)
        public_sha = sha256_bytes(public_bytes)
        private_descriptor = {
            "schema": PRIVATE_DESCRIPTOR_SCHEMA,
            "stage": STAGE,
            "state": "REPAIRED_SUCCESSOR_PRIVATE_MATERIAL_FROZEN",
            "decision_id": chain.DECISION_ID,
            "source_sha": source_sha,
            "current_main_sha": chain.CURRENT_MAIN_SHA,
            "base_head_sha": chain.BASE_HEAD_SHA,
            "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
            "repair_source_binding_is_final_execution_binding": False,
            "final_execution_binding_ready": False,
            "run_suffix": chain.RUN_SUFFIX,
            "custody_root": str(root),
            "custody_root_mode": "0700",
            "generator_sha256": toolchain.generator_sha256,
            "contract_sha256": toolchain.contract_sha256,
            "chain_contract_sha256": toolchain.chain_contract_sha256,
            "protocol_sha256": toolchain.protocol_sha256,
            "python_executable_sha256": toolchain.python_executable_sha256,
            "openssl_executable_sha256": toolchain.openssl_executable_sha256,
            "mosquitto_passwd_executable_sha256": toolchain.mosquitto_passwd_executable_sha256,
            "private_package_sha256": private_package_sha,
            "public_descriptor_sha256": public_sha,
            "authorization": {
                "authorization_id": authorization_id,
                "record_sha256": record_sha,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "consumed": True,
            },
            "materials": materials,
            "offline_proofs": {
                "password_database_matches_preimage": True,
                "candidate_digest_reconstructable": True,
                "prepare_command_reconstructable": True,
                "verify_command_reconstructable": True,
                "prepare_protocol_parse_valid": True,
                "verify_protocol_parse_valid": True,
                "certificate_chain_valid": True,
                "hostname_valid": True,
                "root_ca_private_key_matches_certificate": True,
                "broker_private_key_matches_certificate": True,
                "private_modes_valid": True,
            },
            "private_values_included": False,
            "raw_private_values_in_descriptor": False,
            "board_operation_authorized": False,
            "serial_operation_authorized": False,
            "flash_operation_authorized": False,
            "physical_nvs_operation_authorized": False,
            "network_operation_authorized": False,
            "broker_start_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "ready_authorized": False,
            "merge_authorized": False,
            "release_authorized": False,
            "tag_authorized": False,
            "deployment_authorized": False,
        }
        private_bytes = (
            json.dumps(private_descriptor, indent=2, sort_keys=True).encode("utf-8")
            + b"\n"
        )
        write_private(root / PRIVATE_DESCRIPTOR, private_bytes)
        finalize_authorization(
            marker, "CONSUMED_PASS", public_descriptor_sha256=public_sha
        )

        mqtt_password = "0" * len(mqtt_password)
        persistence_key = "0" * len(persistence_key)
        unlock_token = "0" * len(unlock_token)
        return {
            "schema": RESULT_SCHEMA,
            "status": "PASS",
            "authorization_id": authorization_id,
            "source_sha": source_sha,
            "run_suffix": chain.RUN_SUFFIX,
            "private_package_sha256": private_package_sha,
            "public_descriptor_sha256": public_sha,
            "candidate_digest_sha256": candidate_sha,
            "unlock_digest_sha256": unlock_digest,
            "ca_pem_sha256": public_descriptor["ca_pem_sha256"],
            "broker_certificate_der_sha256": cert_der_sha,
            "broker_spki_sha256": broker_spki_sha,
            "authorization_consumed": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
        }
    except Exception as exc:
        code = (
            exc.args[0]
            if isinstance(
                exc,
                (
                    GenerationError,
                    contract.ContractError,
                    chain.ContractError,
                    protocol.CommandError,
                ),
            )
            and exc.args
            else type(exc).__name__
        )
        if marker.exists():
            finalize_authorization(
                marker, "CONSUMED_FAILED", failure_code=str(code)
            )
        raise


def inert_source_status() -> dict[str, object]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-repaired-private-material-source/1",
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_U1",
        "decision_id": chain.DECISION_ID,
        "run_suffix": chain.RUN_SUFFIX,
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
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-toolchain", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--openssl", type=Path)
    parser.add_argument("--mosquitto-passwd", type=Path)
    args = parser.parse_args()
    if not args.probe_toolchain and not args.execute:
        print(json.dumps(inert_source_status(), sort_keys=True))
        return 0

    generator_path = Path(__file__).resolve(strict=True)
    contract_path = Path(contract.__file__).resolve(strict=True)
    chain_contract_path = Path(chain.__file__).resolve(strict=True)
    protocol_path = Path(protocol.__file__).resolve(strict=True)
    home = Path.home().resolve(strict=True)
    try:
        toolchain = probe_toolchain(
            generator_path,
            contract_path,
            chain_contract_path,
            protocol_path,
            args.openssl,
            args.mosquitto_passwd,
        )
        if args.probe_toolchain and not args.execute:
            print("STAGE2D9R_REPAIRED_PRIVATE_MATERIAL_TOOLCHAIN_PROBE=PASS")
            print(json.dumps(toolchain_public_summary(toolchain, home), sort_keys=True))
            return 0
        require(args.execute, "GENERATION_REQUIRES_EXPLICIT_EXECUTE")
        require(not args.probe_toolchain, "PROBE_AND_EXECUTE_MUTUALLY_EXCLUSIVE")
        require(args.authorization_record is not None, "AUTHORIZATION_RECORD_REQUIRED")
        require(args.source_sha is not None, "SOURCE_SHA_REQUIRED")
        result = execute_generation(
            args.authorization_record.expanduser().resolve(strict=True),
            args.source_sha,
            args.repository_root,
            toolchain,
            home,
        )
    except Exception as exc:
        code = (
            exc.args[0]
            if isinstance(
                exc,
                (
                    GenerationError,
                    contract.ContractError,
                    chain.ContractError,
                    protocol.CommandError,
                ),
            )
            and exc.args
            else type(exc).__name__
        )
        print("STAGE2D9R_REPAIRED_PRIVATE_MATERIAL_GENERATION=FAIL")
        print(f"FAILURE_CODE={code}")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("USB_ENUMERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PHYSICAL_NVS_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("PREPARE_EXECUTED=false")
        print("VERIFY_EXECUTED=false")
        return 2
    print("STAGE2D9R_REPAIRED_PRIVATE_MATERIAL_GENERATION=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
