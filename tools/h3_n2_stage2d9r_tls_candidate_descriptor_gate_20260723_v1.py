#!/usr/bin/env python3
"""Fail-closed public descriptor gate for H3/N2 Stage 2D-9R G3R."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-tls-candidate-descriptor/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
LOCKED = "LOCKED_DESIGN"
FROZEN = "TLS_CANDIDATE_FROZEN"
ALLOWED_STATES = {LOCKED, FROZEN}
HOST = "stage2d9r.local"
PORT = 8883
GENERATION = 1
CANONICALIZATION = "gh.h3.n2.isolated-candidate-profile/1+sha256-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

HASH_FIELDS = (
    "ca_pem_sha256",
    "ca_certificate_sha256",
    "broker_certificate_sha256",
    "broker_spki_sha256",
    "broker_config_sha256",
    "private_package_sha256",
    "candidate_digest_sha256",
)

FALSE_FLAGS = (
    "execution_authorized",
    "board_operation_authorized",
    "network_operation_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "private_values_included",
    "production_material_included",
    "alias_resolution_allowed",
    "tls_verification_bypass_allowed",
)

PROOF_FLAGS = (
    "ca_pem_parseable",
    "ca_role_valid",
    "broker_leaf_role_valid",
    "broker_leaf_chain_valid",
    "broker_hostname_match",
)


class DescriptorError(RuntimeError):
    """Raised when a public descriptor violates the frozen contract."""


def _require_exact(data: dict[str, Any], key: str, expected: Any) -> None:
    if data.get(key) != expected:
        raise DescriptorError(f"{key} mismatch")


def _require_false(data: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if data.get(key) is not False:
            raise DescriptorError(f"{key} must be false")


def _parse_utc(value: object, key: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DescriptorError(f"{key} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DescriptorError(f"{key} is invalid") from exc
    if parsed.tzinfo != timezone.utc:
        raise DescriptorError(f"{key} must use UTC")
    return parsed


def validate(descriptor: dict[str, Any], expected_state: str | None = None) -> str:
    _require_exact(descriptor, "schema", SCHEMA)
    _require_exact(descriptor, "stage", STAGE)

    state = descriptor.get("state")
    if state not in ALLOWED_STATES:
        raise DescriptorError("state is not allowed")
    if expected_state is not None and state != expected_state:
        raise DescriptorError("state does not match expected state")

    _require_exact(descriptor, "broker_host", HOST)
    _require_exact(descriptor, "broker_port", PORT)
    _require_exact(descriptor, "broker_tls_server_name", HOST)
    _require_exact(descriptor, "dns_san", [HOST])
    _require_exact(descriptor, "candidate_generation", GENERATION)
    _require_exact(descriptor, "credential_generation", GENERATION)
    _require_exact(descriptor, "candidate_canonicalization", CANONICALIZATION)
    _require_false(descriptor, *FALSE_FLAGS)

    public_material = descriptor.get("public_material")
    if not isinstance(public_material, dict):
        raise DescriptorError("public_material must be an object")
    _require_false(public_material, "private_key_included", "mqtt_password_included")

    proofs = descriptor.get("offline_proofs")
    if not isinstance(proofs, dict):
        raise DescriptorError("offline_proofs must be an object")

    if state == LOCKED:
        for key in HASH_FIELDS:
            if public_material.get(key) is not None:
                raise DescriptorError(f"{key} must be null while locked")
        for key in ("certificate_not_before", "certificate_not_after"):
            if public_material.get(key) is not None:
                raise DescriptorError(f"{key} must be null while locked")
        for key in PROOF_FLAGS:
            if proofs.get(key) is not False:
                raise DescriptorError(f"{key} must be false while locked")
    else:
        for key in HASH_FIELDS:
            value = public_material.get(key)
            if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
                raise DescriptorError(f"{key} must be lowercase sha256")
        not_before = _parse_utc(
            public_material.get("certificate_not_before"),
            "certificate_not_before",
        )
        not_after = _parse_utc(
            public_material.get("certificate_not_after"),
            "certificate_not_after",
        )
        if not_before >= not_after:
            raise DescriptorError("certificate validity interval is invalid")
        for key in PROOF_FLAGS:
            if proofs.get(key) is not True:
                raise DescriptorError(f"{key} must be true when frozen")

    return str(state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--expect-state", choices=sorted(ALLOWED_STATES))
    args = parser.parse_args()

    try:
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
        state = validate(descriptor, args.expect_state)
    except Exception as exc:  # fail-closed CLI boundary
        print("STAGE2D9R_TLS_DESCRIPTOR_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_TLS_DESCRIPTOR_GATE=PASS")
    print(f"STATE={state}")
    print("BROKER_HOST=stage2d9r.local")
    print("BROKER_PORT=8883")
    print("SECRET_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
