#!/usr/bin/env python3
"""Build a redacted public Stage 2D-9R TLS descriptor from public certificates.

This tool performs offline certificate and configuration checks only. It does not
start a Broker, open a socket, access a board, write NVS, or authorize execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

HOST = "stage2d9r.local"
PORT = 8883
CONFIG_SCHEMA = "gh.h3.n2.stage2d9r-isolated-broker-public-config/1"
DESCRIPTOR_SCHEMA = "gh.h3.n2.stage2d9r-tls-candidate-descriptor/1"
STAGE = "H3/N2 Stage 2D-9R G3R"
CANONICALIZATION = "gh.h3.n2.isolated-candidate-profile/1+sha256-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_CONFIG_KEYS = {
    "password",
    "mqtt_password",
    "private_key",
    "private_key_pem",
    "unlock_token",
    "persistence_key",
    "raw_command",
}


class BindingError(RuntimeError):
    """Raised when public TLS material cannot satisfy the Stage 2D-9R contract."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(payload)


def run_openssl(*args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        completed = subprocess.run(
            ["openssl", *args],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BindingError("openssl is unavailable") from exc
    if completed.returncode != 0:
        raise BindingError("openssl validation failed")
    return completed.stdout


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    except ValueError as exc:
        raise BindingError("certificate timestamp is invalid") from exc
    return parsed.replace(tzinfo=timezone.utc)


def certificate_dates(path: Path) -> tuple[datetime, datetime]:
    output = run_openssl("x509", "-in", str(path), "-noout", "-dates").decode(
        "utf-8", errors="strict"
    )
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    if set(values) != {"notBefore", "notAfter"}:
        raise BindingError("certificate dates are incomplete")
    return parse_timestamp(values["notBefore"]), parse_timestamp(values["notAfter"])


def certificate_text(path: Path) -> str:
    return run_openssl("x509", "-in", str(path), "-noout", "-text").decode(
        "utf-8", errors="strict"
    )


def dns_san(path: Path) -> list[str]:
    output = run_openssl(
        "x509", "-in", str(path), "-noout", "-ext", "subjectAltName"
    ).decode("utf-8", errors="strict")
    return re.findall(r"DNS:([^,\s]+)", output)


def certificate_der(path: Path) -> bytes:
    return run_openssl("x509", "-in", str(path), "-outform", "DER")


def certificate_spki_der(path: Path) -> bytes:
    public_pem = run_openssl("x509", "-in", str(path), "-pubkey", "-noout")
    return run_openssl("pkey", "-pubin", "-outform", "DER", input_bytes=public_pem)


def require_public_config(config: dict[str, Any]) -> None:
    expected = {
        "schema": CONFIG_SCHEMA,
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "dns_san": [HOST],
        "credential_generation": 1,
        "private_values_included": False,
        "execution_authorized": False,
        "network_operation_authorized": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise BindingError(f"broker config {key} mismatch")

    for key in FORBIDDEN_CONFIG_KEYS:
        if key in config:
            raise BindingError(f"broker config contains forbidden key {key}")

    for key in (
        "mqtt_username",
        "mqtt_client_id",
        "test_topic_root",
        "mqtt_password_sha256",
    ):
        value = config.get(key)
        if not isinstance(value, str) or not value:
            raise BindingError(f"broker config {key} is missing")
    if SHA256_RE.fullmatch(str(config["mqtt_password_sha256"])) is None:
        raise BindingError("broker config mqtt_password_sha256 is invalid")
    if not str(config["test_topic_root"]).startswith("gh-test/"):
        raise BindingError("broker config test_topic_root is outside gh-test")


def build_descriptor(
    ca_path: Path,
    broker_cert_path: Path,
    broker_config: dict[str, Any],
    private_package_sha256: str,
    candidate_digest_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if SHA256_RE.fullmatch(private_package_sha256) is None:
        raise BindingError("private package sha256 is invalid")
    if SHA256_RE.fullmatch(candidate_digest_sha256) is None:
        raise BindingError("candidate digest sha256 is invalid")
    require_public_config(broker_config)

    ca_bytes = ca_path.read_bytes()
    leaf_bytes = broker_cert_path.read_bytes()
    ca_text = certificate_text(ca_path)
    leaf_text = certificate_text(broker_cert_path)

    if "CA:TRUE" not in ca_text:
        raise BindingError("CA basic constraints are invalid")
    if "CA:FALSE" not in leaf_text:
        raise BindingError("broker leaf basic constraints are invalid")
    if (
        "TLS Web Server Authentication" not in leaf_text
        and "1.3.6.1.5.5.7.3.1" not in leaf_text
    ):
        raise BindingError("broker leaf serverAuth EKU is missing")
    observed_san = dns_san(broker_cert_path)
    if observed_san != [HOST]:
        raise BindingError("broker DNS SAN is not the exact frozen hostname")

    run_openssl(
        "verify",
        "-CAfile",
        str(ca_path),
        "-purpose",
        "sslserver",
        "-verify_hostname",
        HOST,
        str(broker_cert_path),
    )

    not_before, not_after = certificate_dates(broker_cert_path)
    instant = now or datetime.now(timezone.utc)
    if not_before >= not_after:
        raise BindingError("broker certificate validity interval is invalid")
    if instant < not_before or instant > not_after:
        raise BindingError("broker certificate is not currently valid")

    descriptor = {
        "schema": DESCRIPTOR_SCHEMA,
        "stage": STAGE,
        "state": "TLS_CANDIDATE_FROZEN",
        "broker_host": HOST,
        "broker_port": PORT,
        "broker_tls_server_name": HOST,
        "dns_san": [HOST],
        "candidate_generation": 1,
        "credential_generation": 1,
        "candidate_canonicalization": CANONICALIZATION,
        "execution_authorized": False,
        "board_operation_authorized": False,
        "network_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "private_values_included": False,
        "production_material_included": False,
        "alias_resolution_allowed": False,
        "tls_verification_bypass_allowed": False,
        "public_material": {
            "ca_pem_sha256": sha256_bytes(ca_bytes),
            "ca_certificate_sha256": sha256_bytes(certificate_der(ca_path)),
            "broker_certificate_sha256": sha256_bytes(
                certificate_der(broker_cert_path)
            ),
            "broker_spki_sha256": sha256_bytes(
                certificate_spki_der(broker_cert_path)
            ),
            "broker_config_sha256": canonical_json_sha256(broker_config),
            "private_package_sha256": private_package_sha256,
            "candidate_digest_sha256": candidate_digest_sha256,
            "certificate_not_before": not_before.isoformat().replace("+00:00", "Z"),
            "certificate_not_after": not_after.isoformat().replace("+00:00", "Z"),
            "private_key_included": False,
            "mqtt_password_included": False,
        },
        "offline_proofs": {
            "ca_pem_parseable": True,
            "ca_role_valid": True,
            "broker_leaf_role_valid": True,
            "broker_leaf_chain_valid": True,
            "broker_hostname_match": True,
        },
    }
    return descriptor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ca-pem", type=Path, required=True)
    parser.add_argument("--broker-cert-pem", type=Path, required=True)
    parser.add_argument("--broker-config", type=Path, required=True)
    parser.add_argument("--private-package-sha256", required=True)
    parser.add_argument("--candidate-digest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.broker_config.read_text(encoding="utf-8"))
        descriptor = build_descriptor(
            args.ca_pem,
            args.broker_cert_pem,
            config,
            args.private_package_sha256,
            args.candidate_digest_sha256,
        )
        output = json.dumps(descriptor, indent=2, sort_keys=True) + "\n"
        args.output.write_text(output, encoding="utf-8")
    except Exception as exc:  # fail-closed CLI boundary
        print("STAGE2D9R_TLS_PUBLIC_BINDING=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9R_TLS_PUBLIC_BINDING=PASS")
    print("BROKER_HOST=stage2d9r.local")
    print("DNS_SAN_EXACT=true")
    print("CERTIFICATE_CHAIN_VALID=true")
    print("SECRET_VALUES_INCLUDED=false")
    print("EXECUTION_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
