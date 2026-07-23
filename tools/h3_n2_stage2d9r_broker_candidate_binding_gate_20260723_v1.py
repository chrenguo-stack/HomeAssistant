#!/usr/bin/env python3
"""Validate the public isolated-Broker view against the candidate identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "gh.h3.n2.stage2d9r-isolated-broker-public-config/1"
HOST = "stage2d9r.local"
SUFFIX_RE = re.compile(r"^[a-z0-9]{8,24}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "password",
    "mqtt_password",
    "private_key",
    "private_key_pem",
    "unlock_token",
    "persistence_key",
    "raw_command",
}


class BrokerBindingError(RuntimeError):
    pass


def expected_values(suffix: str) -> dict[str, object]:
    if SUFFIX_RE.fullmatch(suffix) is None:
        raise BrokerBindingError("test_run_suffix is invalid")
    test_run_id = f"gh-test-run-{suffix}"
    return {
        "schema": SCHEMA,
        "test_run_suffix": suffix,
        "system_id": f"gh-test-system-{suffix}",
        "node_id": f"gh-test-node-{suffix}",
        "broker_host": HOST,
        "broker_port": 8883,
        "broker_tls_server_name": HOST,
        "dns_san": [HOST],
        "credential_generation": 1,
        "mqtt_username": "stage2d9r-test",
        "mqtt_client_id": f"gh-test-client-{test_run_id}",
        "test_topic_root": f"gh-test/{test_run_id}/node",
        "private_values_included": False,
        "execution_authorized": False,
        "network_operation_authorized": False,
    }


def validate(config: dict[str, Any]) -> str:
    suffix = config.get("test_run_suffix")
    if not isinstance(suffix, str):
        raise BrokerBindingError("test_run_suffix is missing")
    for key, expected in expected_values(suffix).items():
        if config.get(key) != expected:
            raise BrokerBindingError(f"{key} mismatch")
    password_digest = config.get("mqtt_password_sha256")
    if not isinstance(password_digest, str) or SHA256_RE.fullmatch(password_digest) is None:
        raise BrokerBindingError("mqtt_password_sha256 is invalid")
    for key in FORBIDDEN_KEYS:
        if key in config:
            raise BrokerBindingError(f"forbidden key {key}")
    allowed = set(expected_values(suffix)) | {"mqtt_password_sha256"}
    unexpected = sorted(set(config) - allowed)
    if unexpected:
        raise BrokerBindingError(f"unexpected keys: {','.join(unexpected)}")
    return suffix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        suffix = validate(config)
    except Exception as exc:
        print("STAGE2D9R_BROKER_CANDIDATE_BINDING=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2
    print("STAGE2D9R_BROKER_CANDIDATE_BINDING=PASS")
    print(f"TEST_RUN_SUFFIX={suffix}")
    print("BROKER_HOST=stage2d9r.local")
    print("BROKER_TLS_SERVER_NAME=stage2d9r.local")
    print("SECRET_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
