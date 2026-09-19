#!/usr/bin/env python3
"""One-shot offline deep binding verifier for Stage 2D-9R private materials.

Default mode is a metadata/toolchain preauthorization probe. Deep content
verification requires an exact, unexpired, one-shot U1 authorization record and
the explicit ``--execute`` flag. The verifier never opens a network socket,
starts a Broker, accesses a board, or invokes a firmware command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-private-content-binding-u1-authorization/1"
AUTH_OPERATION = "VERIFY_PRIVATE_CONTENT_BINDINGS_READ_ONLY"
AUTH_PREFIX = "U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-"
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
COMMAND_ROOT_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/private-command-material-tlsvalid01"
)
PKI_ROOT_RELATIVE = Path(".local/state/greenhouse-stage2d9r/private-pki-tlsvalid01")

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

EXPECTED = {
    "python_executable_sha256": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
    "python_version_prefix": "3.11.9 ",
    "command_root_digest": "ef5f79be168fff686cabcc91fdc4109918d75d3311da1209dd8d0e381804006e",
    "command_private_descriptor_sha256": "cda5b1604200045fec0db45e46f9c441e1bde10f2e5a57f8c98ee2d14b5f9a75",
    "command_public_descriptor_sha256": "91c10168174438fc30b3dce087a6b75e24375b87b4262bafddb5b2822ee16d23",
    "command_package_sha256": "cc9086c20781007655c498b78ff1ce7af3316db0c02edbae2440d177d7fdfbb5",
    "unlock_digest_sha256": "3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3",
    "command_execution_binding_sha256": "283b6bf20bbeda03181a719ffd638f3a4b3a40e86c047aff9f4280df29763327",
    "command_source_sha": "9dd8ca9e0b3139bfd187eb7a1dfa38485a9eb2fd",
    "command_implementation_binding": "3d3b67cac008adf30e90a51e891d0dd53b36df69",
    "u1_01_marker_sha256": "7461c0396a7be9fc99d1e880fdfc386054f003b4a64f9e758e6b826f93769314",
    "u1_01_record_sha256": "a574d572aeecd63439e4e4c8ff1f2a70cf984bfcab7ece67db1d61fe7daae737",
    "u1_02_marker_sha256": "1fc51b7338adc56b00b38795173b805b7408e7aafa4e0315e7553dc5898779a9",
    "u1_02_record_sha256": "fb11a086dcfb58ea483aae4d5c09f13c5740a5d619c4e967013a5da8e70fd44e",
    "pki_root_digest": "4cd43ee4b2df177bd99c32d3904dbe1e1df890aa14c6b6714a6b4f7ae4024868",
    "pki_private_descriptor_sha256": "59814b825cd2df4ac7f0e3eb137798af4efdbbed4da9d627fe8ad98144be8687",
    "pki_public_descriptor_sha256": "93bb071a5bf6f58472ac9e3891c2330dd9de6f05410824ad2fb51829267b4540",
    "pki_public_config_sha256": "01c10996c8dc8c7de9a8284284cecbd6ca25f03089297896984bd09e1fad7cf0",
    "pki_package_sha256": "0632b37a70aa2eae416c48ffa9420a8f1e13788c22a7d12e211f77cf6e78a267",
    "pki_marker_sha256": "fbe03088de17b8db4d8b048e1985d571ca9f54d3add9b9fc3fce1735c9bec261",
    "ca_pem_sha256": "cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963",
    "broker_certificate_sha256": "988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7",
    "broker_spki_sha256": "f034dc2a036f709287f0558773418ee1799e75bee50dcf55e09143a3a9052a03",
    "candidate_digest_sha256": "f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5",
    "mqtt_password_sha256": "2cad4f6eddc6cce6eb1b1ced62a07f9a8f5ac73232de44664b403f5090145c2f",
    "broker_host": "stage2d9r.local",
    "broker_port": 8883,
    "mqtt_username": "stage2d9r-test",
}

class BindingError(RuntimeError):
    """Fail-closed verifier error containing only a public error code."""

def require(condition: bool, code: str) -> None:
    if not condition:
        raise BindingError(code)

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
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise BindingError(f"{field.upper()}_INVALID") from exc
    return result.astimezone(timezone.utc)

def resolve_executable(name: str) -> Path:
    value = shutil.which(name)
    require(value is not None, f"{name.upper()}_UNAVAILABLE")
    path = Path(value).resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), f"{name.upper()}_INVALID")
    return path

def openssl_version(openssl: Path) -> str:
    completed = subprocess.run(
        [str(openssl), "version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=15,
        env={"PATH": str(openssl.parent), "LC_ALL": "C"},
    )
    require(completed.returncode == 0, "OPENSSL_VERSION_PROBE_FAILED")
    return completed.stdout.decode("utf-8", errors="replace").strip()[:240]

def run_openssl(openssl: Path, args: list[str], input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        [str(openssl), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
        env={"PATH": str(openssl.parent), "LC_ALL": "C"},
    )
    require(completed.returncode == 0, "OFFLINE_CRYPTOGRAPHIC_CHECK_FAILED")
    return completed.stdout

def private_root(home: Path, relative: Path, digest: str) -> Path:
    root = (home.resolve(strict=True) / relative).resolve(strict=False)
    require(sha256_bytes(str(root).encode("utf-8")) == digest, "CUSTODY_ROOT_DIGEST_MISMATCH")
    require(root.exists() and root.is_dir() and not root.is_symlink(), "CUSTODY_ROOT_INVALID")
    require(file_mode(root) == "0700", "CUSTODY_ROOT_MODE_MISMATCH")
    return root

def exact_json(path: Path, digest: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "DESCRIPTOR_INVALID")
    require(file_mode(path) == "0600", "DESCRIPTOR_MODE_MISMATCH")
    raw = path.read_bytes()
    require(sha256_bytes(raw) == digest, "DESCRIPTOR_DIGEST_MISMATCH")
    value = json.loads(raw)
    require(isinstance(value, dict), "DESCRIPTOR_TYPE_INVALID")
    return value

def exact_marker(
    path: Path,
    digest: str,
    authorization_id: str,
    status: str,
) -> dict[str, Any]:
    value = exact_json(path, digest)
    require(value.get("authorization_id") == authorization_id, "MARKER_AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == status, "MARKER_STATUS_MISMATCH")
    require(value.get("one_shot") is True, "MARKER_ONE_SHOT_MISMATCH")
    require(value.get("replay_permitted") is False, "MARKER_REPLAY_MISMATCH")
    require(value.get("secret_values_included") is False, "MARKER_SECRET_FLAG_MISMATCH")
    record = value.get("record_sha256")
    require(isinstance(record, str) and HEX64.fullmatch(record) is not None, "MARKER_RECORD_SHAPE_INVALID")
    return value

def authorization_marker(home: Path, authorization_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", authorization_id)
    return (home.resolve(strict=True) / AUTH_RELATIVE / f"{safe}.consumed.json").resolve(strict=False)

def private_write(path: Path, payload: dict[str, Any], replace: bool = False) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    require(file_mode(path.parent) == "0700", "AUTHORIZATION_DIRECTORY_MODE_MISMATCH")
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if replace:
        temp = path.with_name(path.name + ".new")
        require(not temp.exists(), "AUTHORIZATION_TEMPORARY_EXISTS")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
    os.chmod(path, 0o600)
    require(file_mode(path) == "0600", "AUTHORIZATION_MARKER_MODE_MISMATCH")

def authorization_digest(record: dict[str, Any]) -> str:
    copy = dict(record)
    copy.pop("record_sha256", None)
    return canonical_json_sha256(copy)

def validate_authorization(
    record: dict[str, Any],
    binding: dict[str, Any],
    python_sha: str,
    openssl_sha: str,
    home: Path,
) -> tuple[str, Path, str]:
    require(record.get("schema") == AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(record.get("stage") == STAGE, "AUTHORIZATION_STAGE_MISMATCH")
    authorization_id = record.get("authorization_id")
    require(
        isinstance(authorization_id, str) and authorization_id.startswith(AUTH_PREFIX),
        "AUTHORIZATION_ID_INVALID",
    )
    require(record.get("operation") == AUTH_OPERATION, "AUTHORIZATION_OPERATION_MISMATCH")
    require(record.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(record.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(record.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_ENABLED")
    require(record.get("automatic_retry_permitted") is False, "AUTOMATIC_RETRY_ENABLED")
    require(record.get("source_sha") == binding.get("source_sha"), "SOURCE_SHA_MISMATCH")
    require(record.get("probe_sha256") == binding.get("probe_sha256"), "PROBE_SHA_MISMATCH")
    require(record.get("review_binding_sha256") == binding.get("review_binding_sha256"), "REVIEW_BINDING_MISMATCH")
    require(record.get("command_group_sha256") == binding.get("command_group_sha256"), "COMMAND_GROUP_MISMATCH")
    require(record.get("stop_conditions_sha256") == binding.get("stop_conditions_sha256"), "STOP_CONDITIONS_MISMATCH")
    require(record.get("python_executable_sha256") == python_sha, "PYTHON_DIGEST_MISMATCH")
    require(record.get("openssl_executable_sha256") == openssl_sha, "OPENSSL_DIGEST_MISMATCH")
    require(record.get("command_root_digest_sha256") == EXPECTED["command_root_digest"], "COMMAND_ROOT_BINDING_MISMATCH")
    require(record.get("pki_root_digest_sha256") == EXPECTED["pki_root_digest"], "PKI_ROOT_BINDING_MISMATCH")
    issued = parse_utc(record.get("issued_at"), "issued_at")
    expires = parse_utc(record.get("expires_at"), "expires_at")
    now = datetime.now(timezone.utc)
    require(expires > issued, "AUTHORIZATION_INTERVAL_INVALID")
    require(expires - issued <= timedelta(hours=2), "AUTHORIZATION_INTERVAL_TOO_LONG")
    require(issued <= now <= expires, "AUTHORIZATION_EXPIRED_OR_NOT_YET_VALID")
    observed = authorization_digest(record)
    require(record.get("record_sha256") == observed, "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    marker = authorization_marker(home, authorization_id)
    require(not marker.exists(), "AUTHORIZATION_ALREADY_CONSUMED")
    return authorization_id, marker, observed

def claim(marker: Path, authorization_id: str, record_sha: str) -> None:
    private_write(
        marker,
        {
            "schema": "gh.h3.n2.stage2d9r-private-content-binding-u1-consumption/1",
            "authorization_id": authorization_id,
            "status": "CLAIMED",
            "record_sha256": record_sha,
            "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
        },
    )

def finalize(marker: Path, status: str, result_sha: str | None, failure_code: str | None) -> None:
    current = json.loads(marker.read_text(encoding="utf-8"))
    current["status"] = status
    current["consumed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    current["result_sha256"] = result_sha
    current["failure_code"] = failure_code
    current["secret_values_included"] = False
    private_write(marker, current, replace=True)

def preauthorization_state(home: Path) -> dict[str, Any]:
    command_root = private_root(home, COMMAND_ROOT_RELATIVE, EXPECTED["command_root_digest"])
    pki_root = private_root(home, PKI_ROOT_RELATIVE, EXPECTED["pki_root_digest"])
    exact_json(
        command_root / "private-command-material-descriptor.json",
        EXPECTED["command_private_descriptor_sha256"],
    )
    exact_json(
        command_root / "public-command-material-descriptor.redacted.json",
        EXPECTED["command_public_descriptor_sha256"],
    )
    exact_json(
        pki_root / "private-custody-descriptor.json",
        EXPECTED["pki_private_descriptor_sha256"],
    )
    exact_json(
        pki_root / "public-descriptor.redacted.json",
        EXPECTED["pki_public_descriptor_sha256"],
    )
    auth = (home.resolve(strict=True) / AUTH_RELATIVE).resolve(strict=False)
    require(auth.is_dir() and not auth.is_symlink() and file_mode(auth) == "0700", "AUTHORIZATION_DIRECTORY_INVALID")
    exact_marker(
        auth / "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01.consumed.json",
        EXPECTED["u1_01_marker_sha256"],
        "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01",
        "CONSUMED_FAILED",
    )
    exact_marker(
        auth / "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02.consumed.json",
        EXPECTED["u1_02_marker_sha256"],
        "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02",
        "CONSUMED",
    )
    exact_marker(
        auth / "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01.consumed.json",
        EXPECTED["pki_marker_sha256"],
        "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01",
        "CONSUMED",
    )
    return {
        "command_root_digest_sha256": EXPECTED["command_root_digest"],
        "pki_root_digest_sha256": EXPECTED["pki_root_digest"],
        "command_descriptors_bound": True,
        "pki_descriptors_bound": True,
        "consumed_markers_bound": True,
    }

def command_deep_binding(home: Path) -> dict[str, Any]:
    root = private_root(home, COMMAND_ROOT_RELATIVE, EXPECTED["command_root_digest"])
    token_path = root / "unlock-token.hex"
    require(token_path.is_file() and not token_path.is_symlink(), "UNLOCK_TOKEN_FILE_INVALID")
    require(file_mode(token_path) == "0600", "UNLOCK_TOKEN_MODE_MISMATCH")
    token_raw = token_path.read_bytes()
    token_text = token_raw.decode("ascii").strip()
    require(HEX64.fullmatch(token_text) is not None and token_text != "0" * 64, "UNLOCK_TOKEN_FORMAT_INVALID")
    token_file_sha = sha256_bytes(token_raw)
    unlock_digest = sha256_bytes(bytes.fromhex(token_text))
    require(unlock_digest == EXPECTED["unlock_digest_sha256"], "UNLOCK_DIGEST_MISMATCH")
    private_descriptor = exact_json(
        root / "private-command-material-descriptor.json",
        EXPECTED["command_private_descriptor_sha256"],
    )
    public_descriptor = exact_json(
        root / "public-command-material-descriptor.redacted.json",
        EXPECTED["command_public_descriptor_sha256"],
    )
    require(private_descriptor["unlock_token"]["file_sha256"] == token_file_sha, "TOKEN_FILE_DIGEST_BINDING_MISMATCH")
    require(private_descriptor["unlock_token"]["unlock_digest_sha256"] == unlock_digest, "PRIVATE_UNLOCK_DIGEST_BINDING_MISMATCH")
    require(private_descriptor["authorization"]["record_sha256"] == EXPECTED["u1_02_record_sha256"], "PRIVATE_AUTHORIZATION_RECORD_MISMATCH")
    require(public_descriptor["authorization_record_sha256"] == EXPECTED["u1_02_record_sha256"], "PUBLIC_AUTHORIZATION_RECORD_MISMATCH")
    require(public_descriptor["unlock_digest_sha256"] == unlock_digest, "PUBLIC_UNLOCK_DIGEST_MISMATCH")
    require(public_descriptor["execution_binding_sha256"] == EXPECTED["command_execution_binding_sha256"], "EXECUTION_BINDING_MISMATCH")
    auth = (home.resolve(strict=True) / AUTH_RELATIVE).resolve(strict=False)
    u1_01 = exact_marker(
        auth / "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01.consumed.json",
        EXPECTED["u1_01_marker_sha256"],
        "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01",
        "CONSUMED_FAILED",
    )
    u1_02 = exact_marker(
        auth / "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02.consumed.json",
        EXPECTED["u1_02_marker_sha256"],
        "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02",
        "CONSUMED",
    )
    require(u1_01["record_sha256"] == EXPECTED["u1_01_record_sha256"], "U1_01_RECORD_CROSS_BINDING_MISMATCH")
    require(u1_02["record_sha256"] == EXPECTED["u1_02_record_sha256"], "U1_02_RECORD_CROSS_BINDING_MISMATCH")
    package_sha = canonical_json_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-private-command-material-set/2",
            "unlock_token_file_sha256": token_file_sha,
            "private_descriptor_sha256": EXPECTED["command_private_descriptor_sha256"],
            "public_descriptor_sha256": EXPECTED["command_public_descriptor_sha256"],
            "authorization_consumed_marker_sha256": EXPECTED["u1_02_marker_sha256"],
            "execution_binding_sha256": EXPECTED["command_execution_binding_sha256"],
        }
    )
    require(package_sha == EXPECTED["command_package_sha256"], "COMMAND_PACKAGE_DIGEST_MISMATCH")
    token_text = "0" * len(token_text)
    token_raw = b""
    return {
        "unlock_digest_sha256": unlock_digest,
        "private_package_sha256": package_sha,
        "token_file_digest_bound": True,
        "u1_01_record_cross_binding_valid": True,
        "u1_02_record_cross_binding_valid": True,
        "raw_unlock_token_included": False,
    }

def material_set_digest(materials: dict[str, dict[str, str]]) -> str:
    ordered = {
        name: {
            "relative_path": materials[name]["relative_path"],
            "mode": materials[name]["mode"],
            "sha256": materials[name]["sha256"],
        }
        for name in sorted(materials)
    }
    return canonical_json_sha256(
        {"schema": "gh.h3.n2.stage2d9r-private-material-set/1", "materials": ordered}
    )

def cert_public_der(openssl: Path, certificate: Path) -> bytes:
    public_pem = run_openssl(openssl, ["x509", "-in", str(certificate), "-pubkey", "-noout"])
    return run_openssl(openssl, ["pkey", "-pubin", "-outform", "DER"], input_bytes=public_pem)

def key_public_der(openssl: Path, private_key: Path) -> bytes:
    return run_openssl(openssl, ["pkey", "-in", str(private_key), "-pubout", "-outform", "DER"])

def pki_deep_binding(home: Path, openssl: Path) -> dict[str, Any]:
    root = private_root(home, PKI_ROOT_RELATIVE, EXPECTED["pki_root_digest"])
    private_descriptor = exact_json(
        root / "private-custody-descriptor.json",
        EXPECTED["pki_private_descriptor_sha256"],
    )
    public_descriptor = exact_json(
        root / "public-descriptor.redacted.json",
        EXPECTED["pki_public_descriptor_sha256"],
    )
    public_config = exact_json(
        root / "isolated-broker-public-config.redacted.json",
        EXPECTED["pki_public_config_sha256"],
    )
    materials = private_descriptor.get("materials")
    require(isinstance(materials, dict), "PKI_MATERIALS_INVALID")
    observed: dict[str, dict[str, str]] = {}
    material_bytes: dict[str, bytes] = {}
    for name, metadata in materials.items():
        require(isinstance(name, str) and isinstance(metadata, dict), "PKI_MATERIAL_METADATA_INVALID")
        relative = metadata.get("relative_path")
        require(isinstance(relative, str) and "/" not in relative and relative not in ("", ".", ".."), "PKI_MATERIAL_PATH_INVALID")
        path = root / relative
        require(path.is_file() and not path.is_symlink(), "PKI_MATERIAL_FILE_INVALID")
        require(file_mode(path) == "0600" and metadata.get("mode") == "0600", "PKI_MATERIAL_MODE_MISMATCH")
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        require(metadata.get("sha256") == digest, "PKI_MATERIAL_DIGEST_MISMATCH")
        observed[name] = {"relative_path": relative, "mode": "0600", "sha256": digest}
        material_bytes[name] = raw
    package_sha = material_set_digest(observed)
    require(package_sha == EXPECTED["pki_package_sha256"], "PKI_PACKAGE_DIGEST_MISMATCH")
    require(private_descriptor["package_sha256"] == package_sha, "PKI_PRIVATE_PACKAGE_BINDING_MISMATCH")
    require(public_descriptor["public_material"]["private_package_sha256"] == package_sha, "PKI_PUBLIC_PACKAGE_BINDING_MISMATCH")

    root_key = root / materials["root_ca_private_key"]["relative_path"]
    root_cert = root / materials["root_ca_certificate"]["relative_path"]
    broker_key = root / materials["broker_private_key"]["relative_path"]
    broker_cert = root / materials["broker_certificate"]["relative_path"]
    fullchain = root / materials["broker_full_chain"]["relative_path"]
    passwd = root / materials["mosquitto_password_file"]["relative_path"]
    config = root / materials["isolated_broker_configuration"]["relative_path"]
    acl = root / materials["isolated_broker_acl"]["relative_path"]

    require(sha256_file(root_cert) == EXPECTED["ca_pem_sha256"], "CA_PEM_DIGEST_MISMATCH")
    require(sha256_file(broker_cert) == EXPECTED["broker_certificate_sha256"], "BROKER_CERTIFICATE_DIGEST_MISMATCH")
    root_key_spki = sha256_bytes(key_public_der(openssl, root_key))
    root_cert_spki = sha256_bytes(cert_public_der(openssl, root_cert))
    broker_key_spki = sha256_bytes(key_public_der(openssl, broker_key))
    broker_cert_spki = sha256_bytes(cert_public_der(openssl, broker_cert))
    require(root_key_spki == root_cert_spki, "ROOT_CA_PRIVATE_KEY_MISMATCH")
    require(broker_key_spki == broker_cert_spki, "BROKER_PRIVATE_KEY_MISMATCH")
    require(broker_cert_spki == EXPECTED["broker_spki_sha256"], "BROKER_SPKI_PUBLIC_BINDING_MISMATCH")
    run_openssl(openssl, ["verify", "-CAfile", str(root_cert), str(broker_cert)])
    run_openssl(openssl, ["x509", "-in", str(broker_cert), "-checkhost", EXPECTED["broker_host"], "-noout"])
    require(fullchain.read_bytes() == broker_cert.read_bytes() + root_cert.read_bytes(), "FULLCHAIN_CONTENT_MISMATCH")

    password_bytes = passwd.read_bytes()
    require(len(password_bytes.splitlines()) == 1, "PASSWORD_DATABASE_LINE_COUNT_INVALID")
    line = password_bytes.decode("ascii").strip()
    require(line.startswith(EXPECTED["mqtt_username"] + ":$7$"), "PASSWORD_DATABASE_FORMAT_INVALID")
    require(EXPECTED["mqtt_password_sha256"] == public_config["mqtt_password_sha256"], "PUBLIC_PASSWORD_DIGEST_BINDING_MISMATCH")

    config_text = config.read_text(encoding="utf-8")
    required_lines = {
        "per_listener_settings true",
        "listener 8883 127.0.0.1",
        "protocol mqtt",
        "allow_anonymous false",
        f"password_file {passwd}",
        f"acl_file {acl}",
        f"cafile {root_cert}",
        f"certfile {broker_cert}",
        f"keyfile {broker_key}",
        "require_certificate false",
        "tls_version tlsv1.2",
        "persistence false",
    }
    require(required_lines.issubset(set(config_text.splitlines())), "BROKER_CONFIG_BINDING_MISMATCH")
    acl_text = acl.read_text(encoding="utf-8")
    require(
        acl_text
        == "user stage2d9r-test\n"
        "topic readwrite gh-test/gh-test-run-tlsvalid01/node/#\n",
        "BROKER_ACL_BINDING_MISMATCH",
    )

    require(public_config["broker_host"] == EXPECTED["broker_host"], "PUBLIC_BROKER_HOST_MISMATCH")
    require(public_config["broker_port"] == EXPECTED["broker_port"], "PUBLIC_BROKER_PORT_MISMATCH")
    require(public_descriptor["public_material"]["candidate_digest_sha256"] == EXPECTED["candidate_digest_sha256"], "CANDIDATE_DIGEST_MISMATCH")
    auth = (home.resolve(strict=True) / AUTH_RELATIVE).resolve(strict=False)
    consumed = exact_marker(
        auth / "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01.consumed.json",
        EXPECTED["pki_marker_sha256"],
        "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01",
        "CONSUMED",
    )
    private_record = private_descriptor["authorization"]["record_sha256"]
    require(isinstance(private_record, str) and HEX64.fullmatch(private_record) is not None, "PKI_PRIVATE_RECORD_SHAPE_INVALID")
    require(consumed["record_sha256"] == private_record, "PKI_RECORD_CROSS_BINDING_MISMATCH")
    material_bytes.clear()
    password_bytes = b""
    return {
        "private_package_sha256": package_sha,
        "ca_pem_sha256": EXPECTED["ca_pem_sha256"],
        "broker_certificate_sha256": EXPECTED["broker_certificate_sha256"],
        "broker_spki_sha256": EXPECTED["broker_spki_sha256"],
        "candidate_digest_sha256": EXPECTED["candidate_digest_sha256"],
        "root_ca_private_key_matches_certificate": True,
        "broker_private_key_matches_certificate": True,
        "certificate_chain_valid": True,
        "hostname_valid": True,
        "password_database_hash_format_valid": True,
        "authorization_record_cross_binding_valid": True,
        "raw_private_keys_included": False,
        "password_database_content_included": False,
        "raw_mqtt_password_included": False,
    }

def probe(binding: dict[str, Any], home: Path, openssl: Path) -> dict[str, Any]:
    python = Path(sys.executable).resolve(strict=True)
    python_sha = sha256_file(python)
    require(python_sha == EXPECTED["python_executable_sha256"], "PYTHON_DIGEST_CHANGED")
    require(sys.version.startswith(EXPECTED["python_version_prefix"]), "PYTHON_VERSION_CHANGED")
    state = preauthorization_state(home)
    authorization_id = binding.get("authorization_request_id")
    require(isinstance(authorization_id, str), "AUTHORIZATION_REQUEST_ID_MISSING")
    marker = authorization_marker(home, authorization_id)
    require(not marker.exists(), "NEW_AUTHORIZATION_MARKER_ALREADY_EXISTS")
    return {
        "schema": "gh.h3.n2.stage2d9r-private-content-binding-toolchain-probe/1",
        "stage": STAGE,
        "authorization_request_id": authorization_id,
        "source_sha": binding.get("source_sha"),
        "probe_sha256": binding.get("probe_sha256"),
        "python_executable_sha256": python_sha,
        "python_version": sys.version.replace("\n", " ")[:240],
        "openssl_executable_sha256": sha256_file(openssl),
        "openssl_version": openssl_version(openssl),
        **state,
        "authorization_marker_exists": False,
        "private_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "network_operation": False,
        "broker_started": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "prepare_executed": False,
        "verify_executed": False,
    }

def execute(
    binding: dict[str, Any],
    authorization_path: Path,
    home: Path,
    openssl: Path,
) -> dict[str, Any]:
    python = Path(sys.executable).resolve(strict=True)
    python_sha = sha256_file(python)
    openssl_sha = sha256_file(openssl)
    require(python_sha == EXPECTED["python_executable_sha256"], "PYTHON_DIGEST_CHANGED")
    require(sys.version.startswith(EXPECTED["python_version_prefix"]), "PYTHON_VERSION_CHANGED")
    preauthorization_state(home)
    record = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization_id, marker, record_sha = validate_authorization(
        record, binding, python_sha, openssl_sha, home
    )
    claim(marker, authorization_id, record_sha)
    try:
        command = command_deep_binding(home)
        pki = pki_deep_binding(home, openssl)
        result_payload = {
            "schema": "gh.h3.n2.stage2d9r-private-content-binding-result/1",
            "stage": STAGE,
            "authorization_id": authorization_id,
            "source_sha": binding["source_sha"],
            "command_binding": command,
            "pki_binding": pki,
            "authorization_consumed": True,
            "authorization_replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_content_read": True,
            "private_paths_included": False,
            "secret_values_included": False,
            "raw_unlock_token_included": False,
            "raw_private_keys_included": False,
            "password_database_content_included": False,
            "raw_mqtt_password_included": False,
            "network_operation": False,
            "broker_started": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
        }
        result_sha = canonical_json_sha256(result_payload)
        result_payload["private_content_binding_sha256"] = result_sha
        finalize(marker, "CONSUMED", result_sha, None)
        return result_payload
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, BindingError) and exc.args else type(exc).__name__
        finalize(marker, "CONSUMED_FAILED", None, str(code))
        raise

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--probe-toolchain", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=Path)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()

    failure_stage = "ARGUMENT_RESOLUTION"
    try:
        package_root = args.package_root.expanduser().resolve(strict=True)
        binding_path = package_root / "PROBE_PACKAGE_BINDING.json"
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        require(binding.get("schema") == "gh.h3.n2.stage2d9r-private-content-binding-review-package/1", "PACKAGE_BINDING_SCHEMA_MISMATCH")
        probe_path = Path(__file__).resolve(strict=True)
        require(sha256_file(probe_path) == binding.get("probe_sha256"), "PROBE_SOURCE_DIGEST_MISMATCH")
        home = args.home.expanduser().resolve(strict=True)
        openssl = resolve_executable("openssl")
        if args.probe_toolchain and not args.execute:
            failure_stage = "READ_ONLY_TOOLCHAIN_PREAUTH_PROBE"
            print(json.dumps(probe(binding, home, openssl), sort_keys=True))
            return 0
        require(args.execute and not args.probe_toolchain, "EXECUTION_MODE_INVALID")
        require(args.authorization_record is not None, "AUTHORIZATION_RECORD_REQUIRED")
        failure_stage = "PRIVATE_CONTENT_BINDING"
        result = execute(
            binding,
            args.authorization_record.expanduser().resolve(strict=True),
            home,
            openssl,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, BindingError) and exc.args else type(exc).__name__
        print("PRIVATE_CONTENT_BINDING=FAIL")
        print(f"FAILURE_STAGE={failure_stage}")
        print(f"FAILURE_CODE={code}")
        print("AUTHORIZATION_REPLAY_PERMITTED=false")
        print("AUTOMATIC_RETRY_PERMITTED=false")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("RAW_UNLOCK_TOKEN_INCLUDED=false")
        print("RAW_PRIVATE_KEYS_INCLUDED=false")
        print("PASSWORD_DATABASE_CONTENT_INCLUDED=false")
        print("RAW_MQTT_PASSWORD_INCLUDED=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("BOARD_OPERATION=false")
        print("SERIAL_OPERATION=false")
        print("FLASH_OPERATION=false")
        return 2
    print("PRIVATE_CONTENT_BINDING=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
