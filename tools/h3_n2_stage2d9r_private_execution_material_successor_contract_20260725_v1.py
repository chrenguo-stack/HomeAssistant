#!/usr/bin/env python3
"""Pure offline contract for Stage 2D-9R successor execution material.

This module contains no board, serial, Flash, NVS, Broker, socket, PREPARE, or
VERIFY execution code. It defines the exact private material that a later
one-shot U1 generator must retain and the public bindings that may be exported.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from typing import Mapping

SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-contract/1"
PUBLIC_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-successor-public/1"
MATERIAL_SCHEMA = "gh.h3.n2.stage2d9r-private-execution-material-set/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
RUN_SUFFIX = "tlsvalid02"
HOST = "stage2d9r.local"
PORT = 8883
MQTT_USERNAME = "stage2d9r-test"
CREDENTIAL_SCHEMA = "gh.pair.credentials/1"

REQUIRED_PRIVATE_FILES = (
    "mqtt-password.hex",
    "mosquitto.password",
    "persistence-key.hex",
    "unlock-token.hex",
    "prepare-command.txt",
    "verify-command.txt",
    "root-ca.key.pem",
    "root-ca.cert.pem",
    "broker.key.pem",
    "broker.cert.pem",
    "broker.fullchain.pem",
    "mosquitto.stage2d9r.conf",
    "mosquitto.stage2d9r.acl",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUFFIX = re.compile(r"^[a-z0-9]{8,24}$")


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(encoded)


def validate_secret_hex(value: str, code: str) -> None:
    require(HEX64.fullmatch(value) is not None and value != "0" * 64, code)


def verify_mosquitto_sha512_pbkdf2(
    password: str, database_line: str, username: str = MQTT_USERNAME
) -> bool:
    prefix = username + ":"
    if not database_line.startswith(prefix):
        return False
    parts = database_line[len(prefix) :].split("$")
    if len(parts) != 5 or parts[0] != "" or parts[1] != "7":
        return False
    try:
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3], validate=True)
        expected = base64.b64decode(parts[4], validate=True)
    except (ValueError, TypeError):
        return False
    if iterations <= 0 or iterations > 10_000_000 or not salt or not expected:
        return False
    observed = hashlib.pbkdf2_hmac(
        "sha512", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(observed, expected)


def candidate_material(password: str, ca_pem: str) -> bytes:
    validate_secret_hex(password, "MQTT_PASSWORD_INVALID")
    test_run_id = f"gh-test-run-{RUN_SUFFIX}"
    fields = (
        CREDENTIAL_SCHEMA,
        f"gh-test-system-{RUN_SUFFIX}",
        f"gh-test-node-{RUN_SUFFIX}",
        HOST,
        PORT,
        HOST,
        ca_pem,
        MQTT_USERNAME,
        f"gh-test-client-{test_run_id}",
        1,
        password,
    )
    return "\n".join(str(value) for value in fields).encode("utf-8")


def candidate_digest(password: str, ca_pem: str) -> str:
    return sha256_bytes(candidate_material(password, ca_pem))


def render_commands(
    unlock_token: str, persistence_key: str, password: str, ca_pem: str
) -> tuple[str, str, str]:
    validate_secret_hex(unlock_token, "UNLOCK_TOKEN_INVALID")
    validate_secret_hex(persistence_key, "PERSISTENCE_KEY_INVALID")
    validate_secret_hex(password, "MQTT_PASSWORD_INVALID")
    require(SUFFIX.fullmatch(RUN_SUFFIX) is not None, "RUN_SUFFIX_INVALID")
    ca_bytes = ca_pem.encode("ascii")
    ca_digest = sha256_bytes(ca_bytes)
    digest = candidate_digest(password, ca_pem)
    encoded_ca = base64.urlsafe_b64encode(ca_bytes).decode("ascii").rstrip("=")
    prepare = " ".join(
        (
            "GH2D9R_PREPARE_V1",
            RUN_SUFFIX,
            unlock_token,
            persistence_key,
            password,
            encoded_ca,
            ca_digest,
            digest,
        )
    )
    verify = " ".join(
        (
            "GH2D9R_VERIFY_V1",
            RUN_SUFFIX,
            unlock_token,
            persistence_key,
            digest,
            "READ_ONLY",
        )
    )
    require(len(prepare) <= 8192 and len(verify) <= 512, "COMMAND_LENGTH_INVALID")
    return prepare + "\n", verify + "\n", digest


def private_material_digest(materials: Mapping[str, Mapping[str, str]]) -> str:
    require(set(materials) == set(REQUIRED_PRIVATE_FILES), "PRIVATE_INVENTORY_MISMATCH")
    ordered: dict[str, dict[str, str]] = {}
    for name in sorted(materials):
        metadata = materials[name]
        require(metadata.get("relative_path") == name, "PRIVATE_RELATIVE_PATH_MISMATCH")
        require(metadata.get("mode") == "0600", "PRIVATE_MODE_MISMATCH")
        digest = metadata.get("sha256")
        require(isinstance(digest, str) and HEX64.fullmatch(digest), "PRIVATE_DIGEST_INVALID")
        ordered[name] = {
            "relative_path": name,
            "mode": "0600",
            "sha256": digest,
        }
    return canonical_json_sha256({"schema": MATERIAL_SCHEMA, "materials": ordered})


def build_public_descriptor(
    source_sha: str,
    mqtt_password_sha256: str,
    unlock_digest_sha256: str,
    persistence_key_file_sha256: str,
    ca_pem_sha256: str,
    broker_certificate_der_sha256: str,
    broker_spki_sha256: str,
    candidate_digest_sha256: str,
    prepare_command_sha256: str,
    verify_command_sha256: str,
    private_package_sha256: str,
) -> dict[str, object]:
    for value in (
        mqtt_password_sha256,
        unlock_digest_sha256,
        persistence_key_file_sha256,
        ca_pem_sha256,
        broker_certificate_der_sha256,
        broker_spki_sha256,
        candidate_digest_sha256,
        prepare_command_sha256,
        verify_command_sha256,
        private_package_sha256,
    ):
        require(HEX64.fullmatch(value) is not None, "PUBLIC_DIGEST_INVALID")
    require(re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None, "SOURCE_SHA_INVALID")
    return {
        "schema": PUBLIC_SCHEMA,
        "stage": STAGE,
        "state": "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
        "source_sha": source_sha,
        "run_suffix": RUN_SUFFIX,
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password_sha256": mqtt_password_sha256,
        "unlock_digest_sha256": unlock_digest_sha256,
        "persistence_key_file_sha256": persistence_key_file_sha256,
        "ca_pem_sha256": ca_pem_sha256,
        "broker_certificate_der_sha256": broker_certificate_der_sha256,
        "broker_spki_sha256": broker_spki_sha256,
        "candidate_digest_sha256": candidate_digest_sha256,
        "prepare_command_sha256": prepare_command_sha256,
        "verify_command_sha256": verify_command_sha256,
        "private_package_sha256": private_package_sha256,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "execution_authorized": False,
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
        "production_operation_authorized": False,
    }
