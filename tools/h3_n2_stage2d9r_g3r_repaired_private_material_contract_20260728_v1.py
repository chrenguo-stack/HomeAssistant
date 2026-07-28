#!/usr/bin/env python3
"""Offline private-material contract for the repaired Stage 2D-9R successor.

The module performs deterministic validation and rendering only.  It does not
create secrets, touch private custody, access a board or serial port, start a
Broker, or execute a device command.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from typing import Mapping

import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol

SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-contract/1"
PUBLIC_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-public/1"
MATERIAL_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-private-material-set/1"
STAGE = chain.STAGE
RUN_SUFFIX = chain.RUN_SUFFIX
HOST = protocol.HOST
PORT = 8883
MQTT_USERNAME = "stage2d9r-test"
REQUIRED_PRIVATE_FILES = chain.REQUIRED_PRIVATE_FILES
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


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


def candidate_digest(password: str, ca_pem: str) -> str:
    validate_secret_hex(password, "MQTT_PASSWORD_INVALID")
    candidate = protocol.build_candidate(RUN_SUFFIX, password, ca_pem)
    return protocol.candidate_digest(candidate)


def render_commands(
    unlock_token: str,
    persistence_key: str,
    password: str,
    ca_pem: str,
) -> tuple[str, str, str, str]:
    validate_secret_hex(unlock_token, "UNLOCK_TOKEN_INVALID")
    validate_secret_hex(persistence_key, "PERSISTENCE_KEY_INVALID")
    validate_secret_hex(password, "MQTT_PASSWORD_INVALID")
    unlock_digest = sha256_bytes(bytes.fromhex(unlock_token))
    prepare = protocol.render_prepare(
        RUN_SUFFIX, unlock_token, persistence_key, password, ca_pem
    )
    candidate = candidate_digest(password, ca_pem)
    verify = protocol.render_verify(
        RUN_SUFFIX, unlock_token, persistence_key, candidate
    )
    parsed_prepare = protocol.parse_prepare(prepare, unlock_digest)
    parsed_verify = protocol.parse_verify(verify, unlock_digest)
    require(parsed_prepare.run_suffix == RUN_SUFFIX, "PREPARE_SUFFIX_MISMATCH")
    require(parsed_prepare.authorization_digest == password, "PREPARE_PASSWORD_MISMATCH")
    require(parsed_prepare.candidate_digest == candidate, "PREPARE_CANDIDATE_MISMATCH")
    require(parsed_verify.run_suffix == RUN_SUFFIX, "VERIFY_SUFFIX_MISMATCH")
    require(parsed_verify.candidate_digest == candidate, "VERIFY_CANDIDATE_MISMATCH")
    return prepare + "\n", verify + "\n", candidate, unlock_digest


def private_material_digest(materials: Mapping[str, Mapping[str, str]]) -> str:
    require(set(materials) == set(REQUIRED_PRIVATE_FILES), "PRIVATE_INVENTORY_MISMATCH")
    normalized: dict[str, dict[str, str]] = {}
    for name in sorted(materials):
        metadata = materials[name]
        require(metadata.get("relative_path") == name, "PRIVATE_RELATIVE_PATH_MISMATCH")
        require(metadata.get("mode") == "0600", "PRIVATE_MODE_MISMATCH")
        digest = chain.validate_sha256(
            metadata.get("sha256"), "PRIVATE_DIGEST_INVALID"
        )
        normalized[name] = {
            "relative_path": name,
            "mode": "0600",
            "sha256": digest,
        }
    return canonical_json_sha256(
        {
            "schema": MATERIAL_SCHEMA,
            "run_suffix": RUN_SUFFIX,
            "materials": normalized,
        }
    )


def build_public_descriptor(
    *,
    source_sha: str,
    generator_sha256: str,
    contract_sha256: str,
    chain_contract_sha256: str,
    protocol_sha256: str,
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
    chain.validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    digest_values = {
        "generator_sha256": generator_sha256,
        "contract_sha256": contract_sha256,
        "chain_contract_sha256": chain_contract_sha256,
        "protocol_sha256": protocol_sha256,
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
    }
    normalized = {
        key: chain.validate_sha256(value, f"PUBLIC_{key.upper()}_INVALID")
        for key, value in digest_values.items()
    }
    return {
        "schema": PUBLIC_SCHEMA,
        "stage": STAGE,
        "state": "REPAIRED_SUCCESSOR_PRIVATE_MATERIAL_FROZEN",
        "decision_id": chain.DECISION_ID,
        "source_sha": source_sha,
        "current_main_sha": chain.CURRENT_MAIN_SHA,
        "base_head_sha": chain.BASE_HEAD_SHA,
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "repair_source_binding_is_final_execution_binding": False,
        "final_execution_binding_ready": False,
        "run_suffix": RUN_SUFFIX,
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "mqtt_username": MQTT_USERNAME,
        **normalized,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
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


def source_contract() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "state": "SOURCE_ONLY_REQUIRES_NEW_EXACT_U1",
        "stage": STAGE,
        "decision_id": chain.DECISION_ID,
        "run_suffix": RUN_SUFFIX,
        "required_private_files": list(REQUIRED_PRIVATE_FILES),
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "new_final_execution_binding_required": True,
        "old_private_material_reuse_permitted": False,
        "secret_generation": False,
        "private_material_created": False,
        "authorization_created": False,
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
        "activate_executed": False,
        "cleanup_executed": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    print(json.dumps(source_contract(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
