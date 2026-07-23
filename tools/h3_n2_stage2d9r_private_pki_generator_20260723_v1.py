#!/usr/bin/env python3
"""One-shot offline generator for the Stage 2D-9R test-only PKI package.

The default command is read-only toolchain probing. Secret generation requires an
exact, unexpired U1 authorization record and the explicit ``--execute`` flag.
This tool never starts Mosquitto, opens a socket, accesses a board, or invokes a
firmware command.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
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
from typing import Any, Iterator

import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as command_protocol
import h3_n2_stage2d9r_tls_public_binding_builder_20260723_v1 as public_binding

AUTH_SCHEMA = "gh.h3.n2.stage2d9r-private-pki-u1-authorization/1"
AUTH_OPERATION = "GENERATE_PRIVATE_TEST_PKI"
AUTH_PREFIX = "U1-H3N2-STAGE2D9R-PRIVATE-PKI-"
STAGE = "H3/N2 Stage 2D-9R G3R"
RUN_SUFFIX = "tlsvalid01"
HOST = "stage2d9r.local"
PORT = 8883
MQTT_USERNAME = "stage2d9r-test"
ROOT_CA_CN = "Stage2D9R Test Root CA"
ROOT_VALID_DAYS = 365
LEAF_VALID_DAYS = 30
CUSTODY_RULE = "HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_PKI_V1"
CUSTODY_RELATIVE = Path(".local/state/greenhouse-stage2d9r/private-pki-tlsvalid01")
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

MATERIAL_FILES = {
    "root_ca_private_key": "root-ca.key.pem",
    "root_ca_certificate": "root-ca.cert.pem",
    "broker_private_key": "broker.key.pem",
    "broker_certificate": "broker.cert.pem",
    "broker_full_chain": "broker.fullchain.pem",
    "mosquitto_password_file": "mosquitto.password",
    "isolated_broker_configuration": "mosquitto.stage2d9r.conf",
    "isolated_broker_acl": "mosquitto.stage2d9r.acl",
}
PRIVATE_DESCRIPTOR_NAME = "private-custody-descriptor.json"
PUBLIC_DESCRIPTOR_NAME = "public-descriptor.redacted.json"
PUBLIC_CONFIG_NAME = "isolated-broker-public-config.redacted.json"

FORBIDDEN_OUTPUT_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "authorization_digest",
    "unlock_token",
    "persistence_key",
)


class GenerationError(RuntimeError):
    """Fail-closed generation or authorization error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GenerationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def parse_utc(value: object, field: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{field} invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GenerationError(f"{field} invalid") from exc
    require(parsed.tzinfo is not None, f"{field} invalid")
    return parsed.astimezone(timezone.utc)


def executable_version(path: Path, args: tuple[str, ...]) -> str:
    completed = subprocess.run(
        [str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=15,
        env={"PATH": str(path.parent), "LC_ALL": "C"},
    )
    require(completed.returncode in (0, 1), "tool version probe failed")
    text = (completed.stdout or completed.stderr).decode("utf-8", errors="replace")
    line = next((item.strip() for item in text.splitlines() if item.strip()), "")
    require(bool(line), "tool version probe returned no version")
    return line[:240]


def resolve_executable(name: str, explicit: Path | None = None) -> Path:
    candidate = str(explicit) if explicit is not None else shutil.which(name)
    require(candidate is not None, f"required executable unavailable: {name}")
    path = Path(candidate).expanduser().resolve(strict=True)
    require(path.is_file(), f"required executable invalid: {name}")
    require(os.access(path, os.X_OK), f"required executable not executable: {name}")
    return path


def default_custody_root(home: Path) -> Path:
    return (home.resolve(strict=True) / CUSTODY_RELATIVE).resolve(strict=False)


def default_consumed_marker(home: Path, authorization_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", authorization_id)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(
        strict=False
    )


def validate_private_root(root: Path, home: Path, repository_root: Path | None) -> None:
    home_resolved = home.resolve(strict=True)
    expected = default_custody_root(home_resolved)
    require(root.resolve(strict=False) == expected, "custody root selection rule mismatch")
    require(not root.exists(), "custody root already exists")
    for forbidden in (Path("/tmp"), Path("/private/tmp"), Path("/Users/Shared")):
        try:
            root.relative_to(forbidden)
        except ValueError:
            continue
        raise GenerationError("custody root is in a shared temporary location")
    if repository_root is not None:
        repo = repository_root.resolve(strict=True)
        try:
            root.relative_to(repo)
        except ValueError:
            pass
        else:
            raise GenerationError("custody root is inside the repository")
    require(root.is_relative_to(home_resolved), "custody root is outside the user home")


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


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
    require(file_mode(path) == "0600", "private file mode mismatch")


def replace_private(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        raise GenerationError("private replacement temporary already exists")
    write_private(temporary, data)
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    require(file_mode(path) == "0600", "private file mode mismatch")


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
    require(completed.returncode == 0, "offline cryptographic command failed")
    return completed.stdout


@contextmanager
def exact_binding_openssl(openssl: Path) -> Iterator[None]:
    original = public_binding.run_openssl

    def exact(*args: str, input_bytes: bytes | None = None) -> bytes:
        return run_checked([str(openssl), *args], input_bytes=input_bytes)

    public_binding.run_openssl = exact
    try:
        yield
    finally:
        public_binding.run_openssl = original


@dataclass(frozen=True)
class Toolchain:
    generator_sha256: str
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
    openssl: Path | None = None,
    mosquitto_passwd: Path | None = None,
) -> Toolchain:
    openssl_path = resolve_executable("openssl", openssl)
    passwd_path = resolve_executable("mosquitto_passwd", mosquitto_passwd)
    python_path = Path(sys.executable).resolve(strict=True)
    return Toolchain(
        generator_sha256=sha256_file(generator_path.resolve(strict=True)),
        python_executable_sha256=sha256_file(python_path),
        python_version=sys.version.replace("\n", " ")[:240],
        openssl_path=openssl_path,
        openssl_executable_sha256=sha256_file(openssl_path),
        openssl_version=executable_version(openssl_path, ("version",)),
        mosquitto_passwd_path=passwd_path,
        mosquitto_passwd_executable_sha256=sha256_file(passwd_path),
        mosquitto_passwd_version=executable_version(passwd_path, ("-h",)),
    )


def toolchain_public_summary(toolchain: Toolchain, home: Path) -> dict[str, object]:
    root = default_custody_root(home)
    return {
        "schema": "gh.h3.n2.stage2d9r-private-pki-toolchain-probe/1",
        "stage": STAGE,
        "generator_sha256": toolchain.generator_sha256,
        "python_executable_sha256": toolchain.python_executable_sha256,
        "python_version": toolchain.python_version,
        "openssl_executable_sha256": toolchain.openssl_executable_sha256,
        "openssl_version": toolchain.openssl_version,
        "mosquitto_passwd_executable_sha256": (
            toolchain.mosquitto_passwd_executable_sha256
        ),
        "mosquitto_passwd_version": toolchain.mosquitto_passwd_version,
        "custody_root_selection_rule": CUSTODY_RULE,
        "custody_root_digest_sha256": sha256_bytes(str(root).encode("utf-8")),
        "custody_root_exists": root.exists(),
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "network_operation": False,
        "broker_started": False,
    }


def authorization_record_digest(record: dict[str, Any]) -> str:
    bound = dict(record)
    bound.pop("record_sha256", None)
    return canonical_json_sha256(bound)


def validate_authorization(
    record: dict[str, Any],
    record_path: Path,
    toolchain: Toolchain,
    source_sha: str,
    home: Path,
    now: datetime,
) -> tuple[str, Path, str]:
    require(record.get("schema") == AUTH_SCHEMA, "authorization schema mismatch")
    require(record.get("stage") == STAGE, "authorization stage mismatch")
    authorization_id = record.get("authorization_id")
    require(
        isinstance(authorization_id, str) and authorization_id.startswith(AUTH_PREFIX),
        "authorization id invalid",
    )
    require(record.get("operation") == AUTH_OPERATION, "authorization operation mismatch")
    require(record.get("authorized") is True, "authorization is not granted")
    require(record.get("one_shot") is True, "authorization must be one-shot")
    require(record.get("replay_permitted") is False, "authorization replay forbidden")
    require(record.get("test_run_suffix") == RUN_SUFFIX, "run suffix mismatch")
    require(record.get("custody_root_selection_rule") == CUSTODY_RULE, "custody rule mismatch")
    require(HEX40.fullmatch(source_sha) is not None, "source sha invalid")
    require(record.get("source_sha") == source_sha, "source sha mismatch")

    expected = {
        "generator_sha256": toolchain.generator_sha256,
        "python_executable_sha256": toolchain.python_executable_sha256,
        "openssl_executable_sha256": toolchain.openssl_executable_sha256,
        "mosquitto_passwd_executable_sha256": (
            toolchain.mosquitto_passwd_executable_sha256
        ),
    }
    for key, observed in expected.items():
        require(record.get(key) == observed, f"{key} mismatch")

    root = default_custody_root(home)
    root_digest = sha256_bytes(str(root).encode("utf-8"))
    require(record.get("custody_root_digest_sha256") == root_digest, "custody digest mismatch")

    issued = parse_utc(record.get("issued_at"), "issued_at")
    expires = parse_utc(record.get("expires_at"), "expires_at")
    require(expires > issued, "authorization interval invalid")
    require(expires - issued <= timedelta(hours=2), "authorization interval too long")
    require(issued <= now <= expires, "authorization is not currently valid")

    record_sha = authorization_record_digest(record)
    require(record.get("record_sha256") == record_sha, "authorization record digest mismatch")
    marker = default_consumed_marker(home, authorization_id)
    require(not marker.exists(), "authorization already claimed or consumed")
    return authorization_id, marker, record_sha


def claim_authorization(marker: Path, authorization_id: str, record_sha: str) -> None:
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(marker.parent, 0o700)
    require(file_mode(marker.parent) == "0700", "authorization directory mode mismatch")
    claimed = {
        "schema": "gh.h3.n2.stage2d9r-private-pki-u1-consumption/1",
        "authorization_id": authorization_id,
        "status": "CLAIMED",
        "record_sha256": record_sha,
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "one_shot": True,
        "replay_permitted": False,
        "secret_values_included": False,
    }
    write_private(marker, json.dumps(claimed, sort_keys=True, indent=2).encode() + b"\n")


def finalize_authorization(marker: Path, public_descriptor_sha256: str) -> None:
    current = json.loads(marker.read_text(encoding="utf-8"))
    current["status"] = "CONSUMED"
    current["consumed_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    current["public_descriptor_sha256"] = public_descriptor_sha256
    replace_private(marker, json.dumps(current, sort_keys=True, indent=2).encode() + b"\n")


def build_candidate_digest(password_hex: str, ca_pem: str) -> str:
    candidate = command_protocol.build_candidate(RUN_SUFFIX, password_hex, ca_pem)
    return command_protocol.candidate_digest(candidate)


def build_public_config(password_hex: str) -> dict[str, object]:
    require(HEX64.fullmatch(password_hex) is not None, "generated password shape invalid")
    run_id = f"gh-test-run-{RUN_SUFFIX}"
    return {
        "schema": "gh.h3.n2.stage2d9r-isolated-broker-public-config/1",
        "test_run_suffix": RUN_SUFFIX,
        "system_id": f"gh-test-system-{RUN_SUFFIX}",
        "node_id": f"gh-test-node-{RUN_SUFFIX}",
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "dns_san": [HOST],
        "credential_generation": 1,
        "mqtt_username": MQTT_USERNAME,
        "mqtt_client_id": f"gh-test-client-{run_id}",
        "test_topic_root": f"gh-test/{run_id}/node",
        "mqtt_password_sha256": sha256_bytes(password_hex.encode("ascii")),
        "private_values_included": False,
        "execution_authorized": False,
        "network_operation_authorized": False,
    }


def build_acl() -> str:
    return (
        f"user {MQTT_USERNAME}\n"
        f"topic readwrite gh-test/gh-test-run-{RUN_SUFFIX}/node/#\n"
    )


def build_broker_configuration(root: Path) -> str:
    values = {name: root / filename for name, filename in MATERIAL_FILES.items()}
    return "\n".join(
        (
            "per_listener_settings true",
            "listener 8883 127.0.0.1",
            "protocol mqtt",
            "allow_anonymous false",
            f"password_file {values['mosquitto_password_file']}",
            f"acl_file {values['isolated_broker_acl']}",
            f"cafile {values['root_ca_certificate']}",
            f"certfile {values['broker_certificate']}",
            f"keyfile {values['broker_private_key']}",
            "require_certificate false",
            "tls_version tlsv1.2",
            "persistence false",
            "connection_messages true",
            "log_type all",
            "",
        )
    )


def package_digest(materials: dict[str, dict[str, str]]) -> str:
    ordered = {
        name: {
            "relative_path": materials[name]["relative_path"],
            "mode": materials[name]["mode"],
            "sha256": materials[name]["sha256"],
        }
        for name in sorted(materials)
    }
    return canonical_json_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-private-material-set/1",
            "materials": ordered,
        }
    )


def generate_certificates(root: Path, openssl: Path) -> None:
    root_key = root / MATERIAL_FILES["root_ca_private_key"]
    root_cert = root / MATERIAL_FILES["root_ca_certificate"]
    broker_key = root / MATERIAL_FILES["broker_private_key"]
    broker_cert = root / MATERIAL_FILES["broker_certificate"]
    fullchain = root / MATERIAL_FILES["broker_full_chain"]

    run_checked(
        [
            str(openssl),
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(root_key),
        ]
    )
    os.chmod(root_key, 0o600)
    run_checked(
        [
            str(openssl),
            "req",
            "-x509",
            "-new",
            "-key",
            str(root_key),
            "-sha256",
            "-days",
            str(ROOT_VALID_DAYS),
            "-subj",
            f"/CN={ROOT_CA_CN}",
            "-addext",
            "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-out",
            str(root_cert),
        ]
    )
    os.chmod(root_cert, 0o600)
    run_checked(
        [
            str(openssl),
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(broker_key),
        ]
    )
    os.chmod(broker_key, 0o600)

    csr = root / ".broker.csr.pem"
    ext = root / ".broker.ext.cnf"
    try:
        run_checked(
            [
                str(openssl),
                "req",
                "-new",
                "-key",
                str(broker_key),
                "-subj",
                f"/CN={HOST}",
                "-out",
                str(csr),
            ]
        )
        os.chmod(csr, 0o600)
        write_private(
            ext,
            (
                "basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth\n"
                f"subjectAltName=DNS:{HOST}\n"
            ).encode("ascii"),
        )
        serial = secrets.token_hex(16).lstrip("0") or "1"
        run_checked(
            [
                str(openssl),
                "x509",
                "-req",
                "-in",
                str(csr),
                "-CA",
                str(root_cert),
                "-CAkey",
                str(root_key),
                "-set_serial",
                "0x" + serial,
                "-days",
                str(LEAF_VALID_DAYS),
                "-sha256",
                "-extfile",
                str(ext),
                "-out",
                str(broker_cert),
            ]
        )
        os.chmod(broker_cert, 0o600)
    finally:
        for temporary in (csr, ext):
            if temporary.exists():
                temporary.unlink()

    write_private(fullchain, broker_cert.read_bytes() + root_cert.read_bytes())


def generate_password_file(root: Path, password_hex: str, executable: Path) -> None:
    target = root / MATERIAL_FILES["mosquitto_password_file"]
    temporary = root / ".mosquitto.password.plain"
    write_private(temporary, f"{MQTT_USERNAME}:{password_hex}\n".encode("ascii"))
    try:
        run_checked(
            [
                str(executable),
                "-H",
                "sha512-pbkdf2",
                "-U",
                str(temporary),
            ]
        )
        hashed = temporary.read_bytes()
        require(password_hex.encode("ascii") not in hashed, "password conversion failed")
        require(hashed.startswith((MQTT_USERNAME + ":$").encode("ascii")), "password format invalid")
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def material_metadata(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name, filename in MATERIAL_FILES.items():
        path = root / filename
        require(path.is_file() and not path.is_symlink(), f"material missing: {name}")
        require(file_mode(path) == "0600", f"material mode invalid: {name}")
        result[name] = {
            "relative_path": filename,
            "mode": "0600",
            "sha256": sha256_file(path),
        }
    return result


def validate_no_private_leakage(
    public_config: dict[str, object], public_descriptor: dict[str, object], password_hex: str
) -> None:
    payload = canonical_json_bytes(
        {"public_config": public_config, "public_descriptor": public_descriptor}
    )
    require(password_hex.encode("ascii") not in payload, "raw MQTT password leaked")
    for marker in FORBIDDEN_OUTPUT_MARKERS:
        require(marker.encode("ascii") not in payload, "private marker leaked")


def execute_generation(
    authorization_path: Path,
    source_sha: str,
    repository_root: Path | None,
    toolchain: Toolchain,
    home: Path,
    generator_path: Path,
) -> dict[str, object]:
    record = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization_id, marker, record_sha = validate_authorization(
        record,
        authorization_path,
        toolchain,
        source_sha,
        home,
        datetime.now(timezone.utc),
    )
    root = default_custody_root(home)
    validate_private_root(root, home, repository_root)
    claim_authorization(marker, authorization_id, record_sha)

    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root.parent, 0o700)
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    require(file_mode(root) == "0700", "custody root mode mismatch")

    password_hex = secrets.token_hex(32)
    require(HEX64.fullmatch(password_hex) is not None, "generated password invalid")
    generate_certificates(root, toolchain.openssl_path)
    generate_password_file(root, password_hex, toolchain.mosquitto_passwd_path)

    acl = build_acl()
    broker_config_text = build_broker_configuration(root)
    write_private(root / MATERIAL_FILES["isolated_broker_acl"], acl.encode("utf-8"))
    write_private(
        root / MATERIAL_FILES["isolated_broker_configuration"],
        broker_config_text.encode("utf-8"),
    )

    ca_path = root / MATERIAL_FILES["root_ca_certificate"]
    broker_path = root / MATERIAL_FILES["broker_certificate"]
    ca_pem = ca_path.read_text(encoding="ascii")
    candidate_sha = build_candidate_digest(password_hex, ca_pem)
    public_config = build_public_config(password_hex)
    materials = material_metadata(root)
    private_package_sha = package_digest(materials)

    with exact_binding_openssl(toolchain.openssl_path):
        public_descriptor = public_binding.build_descriptor(
            ca_path,
            broker_path,
            public_config,
            private_package_sha,
            candidate_sha,
        )
    validate_no_private_leakage(public_config, public_descriptor, password_hex)

    public_config_bytes = json.dumps(public_config, indent=2, sort_keys=True).encode() + b"\n"
    public_descriptor_bytes = (
        json.dumps(public_descriptor, indent=2, sort_keys=True).encode() + b"\n"
    )
    write_private(root / PUBLIC_CONFIG_NAME, public_config_bytes)
    write_private(root / PUBLIC_DESCRIPTOR_NAME, public_descriptor_bytes)
    public_descriptor_sha = sha256_bytes(public_descriptor_bytes)

    private_descriptor = {
        "schema": "gh.h3.n2.stage2d9r-private-pki-custody-descriptor/1",
        "stage": STAGE,
        "state": "PKI_FROZEN",
        "source_sha": source_sha,
        "generator_sha256": toolchain.generator_sha256,
        "python_executable_sha256": toolchain.python_executable_sha256,
        "python_version": toolchain.python_version,
        "openssl_executable_sha256": toolchain.openssl_executable_sha256,
        "openssl_version": toolchain.openssl_version,
        "mosquitto_passwd_executable_sha256": (
            toolchain.mosquitto_passwd_executable_sha256
        ),
        "mosquitto_passwd_version": toolchain.mosquitto_passwd_version,
        "test_run_suffix": RUN_SUFFIX,
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "dns_san": [HOST],
        "custody_root": str(root),
        "custody_root_mode": "0700",
        "package_sha256": private_package_sha,
        "public_descriptor_sha256": public_descriptor_sha,
        "candidate_digest_sha256": candidate_sha,
        "authorization": {
            "authorization_id": authorization_id,
            "operation": AUTH_OPERATION,
            "one_shot": True,
            "replay_permitted": False,
            "authorized": True,
            "consumed": True,
            "record_sha256": record_sha,
        },
        "materials": materials,
        "offline_proofs": {
            "root_ca_role_valid": True,
            "broker_leaf_role_valid": True,
            "certificate_chain_valid": True,
            "hostname_valid": True,
            "private_modes_valid": True,
            "public_private_leakage_scan_passed": True,
        },
        "private_values_included": False,
        "raw_private_keys_in_descriptor": False,
        "raw_mqtt_password_in_descriptor": False,
        "board_operation_authorized": False,
        "network_operation_authorized": False,
        "broker_start_authorized": False,
        "flash_operation_authorized": False,
        "physical_nvs_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    private_descriptor_bytes = (
        json.dumps(private_descriptor, indent=2, sort_keys=True).encode() + b"\n"
    )
    write_private(root / PRIVATE_DESCRIPTOR_NAME, private_descriptor_bytes)
    finalize_authorization(marker, public_descriptor_sha)

    password_hex = "0" * len(password_hex)
    return {
        "schema": "gh.h3.n2.stage2d9r-private-pki-generation-result/1",
        "status": "PASS",
        "authorization_id": authorization_id,
        "source_sha": source_sha,
        "generator_sha256": toolchain.generator_sha256,
        "private_package_sha256": private_package_sha,
        "ca_pem_sha256": sha256_file(ca_path),
        "broker_certificate_sha256": public_descriptor["public_material"][
            "broker_certificate_sha256"
        ],
        "broker_spki_sha256": public_descriptor["public_material"][
            "broker_spki_sha256"
        ],
        "public_descriptor_sha256": public_descriptor_sha,
        "candidate_digest_sha256": candidate_sha,
        "u1_authorization_consumed": True,
        "private_paths_included": False,
        "secret_values_included": False,
        "board_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
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

    generator_path = Path(__file__).resolve(strict=True)
    home = Path.home().resolve(strict=True)
    try:
        toolchain = probe_toolchain(generator_path, args.openssl, args.mosquitto_passwd)
        if args.probe_toolchain and not args.execute:
            print(json.dumps(toolchain_public_summary(toolchain, home), sort_keys=True))
            return 0
        require(args.execute, "generation requires explicit --execute")
        require(not args.probe_toolchain, "probe and execute modes are mutually exclusive")
        require(args.authorization_record is not None, "authorization record required")
        require(args.source_sha is not None, "source sha required")
        result = execute_generation(
            args.authorization_record.resolve(strict=True),
            args.source_sha,
            args.repository_root,
            toolchain,
            home,
            generator_path,
        )
    except Exception as exc:
        print("STAGE2D9R_PRIVATE_PKI_GENERATION=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        return 2

    print("STAGE2D9R_PRIVATE_PKI_GENERATION=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
