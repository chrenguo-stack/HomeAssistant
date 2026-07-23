#!/usr/bin/env python3
"""Fail-closed validator for Stage 2D-9R private PKI custody descriptors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-private-pki-custody-descriptor/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
LOCKED = "LOCKED_TEMPLATE"
FROZEN = "PKI_FROZEN"
ALLOWED_STATES = {LOCKED, FROZEN}
HOST = "stage2d9r.local"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUFFIX = re.compile(r"^[a-z0-9]{8,24}$")
PLACEHOLDER = re.compile(r"<[^>]+>")

MATERIALS = {
    "root_ca_private_key": "root-ca.key.pem",
    "root_ca_certificate": "root-ca.cert.pem",
    "broker_private_key": "broker.key.pem",
    "broker_certificate": "broker.cert.pem",
    "broker_full_chain": "broker.fullchain.pem",
    "mosquitto_password_file": "mosquitto.password",
    "isolated_broker_configuration": "mosquitto.stage2d9r.conf",
    "isolated_broker_acl": "mosquitto.stage2d9r.acl",
}

FALSE_FLAGS = (
    "raw_private_keys_in_descriptor",
    "raw_mqtt_password_in_descriptor",
    "board_operation_authorized",
    "network_operation_authorized",
    "broker_start_authorized",
    "flash_operation_authorized",
    "physical_nvs_operation_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "production_operation_authorized",
)

PROOFS = (
    "root_ca_role_valid",
    "broker_leaf_role_valid",
    "certificate_chain_valid",
    "hostname_valid",
    "private_modes_valid",
    "public_private_leakage_scan_passed",
)


class CustodyError(RuntimeError):
    """Raised when a private custody descriptor violates the frozen contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CustodyError(message)


def object_at(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    require(isinstance(value, dict), f"{key} must be an object")
    return value


def has_placeholder(value: object) -> bool:
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return PLACEHOLDER.search(str(value)) is not None


def absolute_private_path(value: object) -> bool:
    text = str(value)
    path = PurePosixPath(text)
    return path.is_absolute() and PLACEHOLDER.search(text) is None and ".." not in path.parts


def validate(data: dict[str, Any], expected_state: str | None = None) -> str:
    require(data.get("schema") == SCHEMA, "schema mismatch")
    require(data.get("stage") == STAGE, "stage mismatch")
    state = data.get("state")
    require(state in ALLOWED_STATES, "state is not allowed")
    if expected_state is not None:
        require(state == expected_state, "state does not match expected state")

    require(data.get("broker_host") == HOST, "broker_host mismatch")
    require(data.get("broker_port") == 8883, "broker_port mismatch")
    require(data.get("broker_tls_server_name") == HOST, "TLS server name mismatch")
    require(data.get("dns_san") == [HOST], "DNS SAN mismatch")
    suffix = data.get("test_run_suffix")
    require(isinstance(suffix, str) and SUFFIX.fullmatch(suffix) is not None,
            "test_run_suffix invalid")
    require(data.get("custody_root_mode") == "0700", "custody root mode mismatch")
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"{key} must be false")
    require(data.get("private_values_included") is False,
            "descriptor must not include private values")

    authorization = object_at(data, "authorization")
    require(authorization.get("operation") == "GENERATE_PRIVATE_TEST_PKI",
            "authorization operation mismatch")
    require(authorization.get("one_shot") is True, "authorization must be one-shot")
    require(authorization.get("replay_permitted") is False,
            "authorization replay must be false")

    materials = object_at(data, "materials")
    require(set(materials) == set(MATERIALS), "material set mismatch")
    for name, relative_path in MATERIALS.items():
        item = object_at(materials, name)
        require(item.get("relative_path") == relative_path,
                f"{name} relative path mismatch")
        require(item.get("mode") == "0600", f"{name} mode mismatch")

    proofs = object_at(data, "offline_proofs")
    require(set(proofs) == set(PROOFS), "offline proof set mismatch")

    if state == LOCKED:
        require(has_placeholder(data), "locked template must retain placeholders")
        require(authorization.get("authorization_id") is None,
                "locked template authorization id must be null")
        require(authorization.get("authorized") is False,
                "locked template must not be authorized")
        require(authorization.get("consumed") is False,
                "locked template must not be consumed")
        require(authorization.get("record_sha256") is None,
                "locked template authorization digest must be null")
        for key in PROOFS:
            require(proofs.get(key) is False, f"{key} must be false while locked")
        return LOCKED

    require(not has_placeholder(data), "frozen descriptor has placeholders")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None,
            "source_sha invalid")
    for key in (
        "generator_sha256",
        "openssl_executable_sha256",
        "package_sha256",
        "public_descriptor_sha256",
        "candidate_digest_sha256",
    ):
        require(HEX64.fullmatch(str(data.get(key))) is not None, f"{key} invalid")
    require(isinstance(data.get("openssl_version"), str) and
            bool(str(data.get("openssl_version")).strip()),
            "openssl_version invalid")
    require(absolute_private_path(data.get("custody_root")),
            "custody_root must be an absolute private path")

    require(isinstance(authorization.get("authorization_id"), str) and
            str(authorization.get("authorization_id")).startswith("U1-"),
            "authorization id invalid")
    require(authorization.get("authorized") is True,
            "frozen PKI must record generation authorization")
    require(authorization.get("consumed") is True,
            "frozen PKI must record consumed authorization")
    require(HEX64.fullmatch(str(authorization.get("record_sha256"))) is not None,
            "authorization record digest invalid")

    for name in MATERIALS:
        item = object_at(materials, name)
        require(HEX64.fullmatch(str(item.get("sha256"))) is not None,
                f"{name} sha256 invalid")
    for key in PROOFS:
        require(proofs.get(key) is True, f"{key} must be true when frozen")
    return FROZEN


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--expect-state", choices=sorted(ALLOWED_STATES))
    args = parser.parse_args()
    try:
        data = json.loads(args.descriptor.read_text(encoding="utf-8"))
        state = validate(data, args.expect_state)
    except Exception as exc:  # fail-closed CLI boundary
        print("STAGE2D9R_PRIVATE_PKI_CUSTODY_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_PRIVATE_PKI_CUSTODY_GATE=PASS")
    print(f"STATE={state}")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    print("BROKER_START_AUTHORIZED=false")
    print("PREPARE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
