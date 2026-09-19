from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import re

PREPARE_SCHEMA = "GH2D9R_PREPARE_V1"
VERIFY_SCHEMA = "GH2D9R_VERIFY_V1"
HOST = "stage2d9r.local"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUFFIX = re.compile(r"^[a-z0-9]{8,24}$")
MAX_COMMAND_LENGTH = 8192
MIN_CA_PEM_LENGTH = 256
MAX_CA_PEM_LENGTH = 4096
PEM_BEGIN = "-----BEGIN CERTIFICATE-----\n"
PEM_END = "\n-----END CERTIFICATE-----\n"


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrepareCommand:
    run_suffix: str
    unlock_token_hex: str
    persistence_key_hex: str
    authorization_digest: str
    ca_pem: str
    ca_pem_sha256: str
    candidate_digest: str


@dataclass(frozen=True)
class VerifyCommand:
    run_suffix: str
    unlock_token_hex: str
    persistence_key_hex: str
    candidate_digest: str


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode_base64url(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise CommandError("CA base64url invalid")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except ValueError as exc:
        raise CommandError("CA base64url invalid") from exc
    return decoded


def validate_ca_pem_bytes(value: bytes) -> str:
    if len(value) < MIN_CA_PEM_LENGTH or len(value) > MAX_CA_PEM_LENGTH:
        raise CommandError("CA PEM length invalid")
    if b"\x00" in value or b"\r" in value:
        raise CommandError("CA PEM contains forbidden bytes")
    try:
        text = value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CommandError("CA PEM must be ASCII") from exc
    if not text.startswith(PEM_BEGIN) or not text.endswith(PEM_END):
        raise CommandError("CA PEM framing invalid")
    body = text[len(PEM_BEGIN) : -len(PEM_END)]
    lines = body.split("\n")
    if not lines or any(
        not line or len(line) > 76 or re.fullmatch(r"[A-Za-z0-9+/=]+", line) is None
        for line in lines
    ):
        raise CommandError("CA PEM body invalid")
    return text


def build_candidate(
    run_suffix: str,
    authorization_digest: str,
    ca_pem: str,
) -> dict[str, object]:
    if SUFFIX.fullmatch(run_suffix) is None:
        raise CommandError("run suffix invalid")
    if HEX64.fullmatch(authorization_digest) is None:
        raise CommandError("authorization digest invalid")
    validate_ca_pem_bytes(ca_pem.encode("ascii"))
    test_run_id = f"gh-test-run-{run_suffix}"
    return {
        "schema": "gh.h3.n2.isolated-candidate-profile/1",
        "test_run_id": test_run_id,
        "system_id": f"gh-test-system-{run_suffix}",
        "node_id": f"gh-test-node-{run_suffix}",
        "broker_host": HOST,
        "broker_port": 8883,
        "broker_tls_server_name": HOST,
        "ca_pem": ca_pem,
        "mqtt_username": "stage2d9r-test",
        "mqtt_client_id": f"gh-test-client-{test_run_id}",
        "mqtt_password": authorization_digest,
        "test_topic_root": f"gh-test/{test_run_id}/node",
        "credential_generation": 1,
    }


def candidate_material(candidate: dict[str, object]) -> bytes:
    persisted = (
        "gh.pair.credentials/1",
        candidate["system_id"],
        candidate["node_id"],
        candidate["broker_host"],
        candidate["broker_port"],
        candidate["broker_tls_server_name"],
        candidate["ca_pem"],
        candidate["mqtt_username"],
        candidate["mqtt_client_id"],
        candidate["credential_generation"],
        candidate["mqtt_password"],
    )
    return "\n".join(str(value) for value in persisted).encode("utf-8")


def candidate_digest(candidate: dict[str, object]) -> str:
    return sha256_hex(candidate_material(candidate))


def _validate_common(
    suffix: str,
    unlock: str,
    key: str,
    expected_unlock_digest: str,
) -> None:
    if SUFFIX.fullmatch(suffix) is None:
        raise CommandError("run suffix invalid")
    for name, value in (("unlock token", unlock), ("persistence key", key)):
        if HEX64.fullmatch(value) is None:
            raise CommandError(f"{name} invalid")
        if value == "0" * 64:
            raise CommandError(f"zero {name} rejected")
    if HEX64.fullmatch(expected_unlock_digest) is None:
        raise CommandError("compiled unlock digest invalid")
    observed = sha256_hex(bytes.fromhex(unlock))
    if not hmac.compare_digest(observed, expected_unlock_digest):
        raise CommandError("unlock digest mismatch")


def parse_prepare(line: str, expected_unlock_digest: str) -> PrepareCommand:
    if len(line) > MAX_COMMAND_LENGTH:
        raise CommandError("command too long")
    if line.endswith("\r") or line.endswith("\n"):
        line = line.rstrip("\r\n")
    if "\r" in line or "\n" in line:
        raise CommandError("embedded line ending")
    parts = line.split(" ")
    if len(parts) != 8 or parts[0] != PREPARE_SCHEMA or any(not part for part in parts):
        raise CommandError("PREPARE command shape invalid")
    _, suffix, unlock, key, authorization, encoded_ca, supplied_ca_hash, supplied_candidate = parts
    _validate_common(suffix, unlock, key, expected_unlock_digest)
    for name, value in (
        ("authorization digest", authorization),
        ("CA PEM digest", supplied_ca_hash),
        ("candidate digest", supplied_candidate),
    ):
        if HEX64.fullmatch(value) is None:
            raise CommandError(f"{name} invalid")
    if authorization == "0" * 64:
        raise CommandError("zero authorization digest rejected")
    ca_bytes = decode_base64url(encoded_ca)
    ca_pem = validate_ca_pem_bytes(ca_bytes)
    observed_ca_hash = sha256_hex(ca_bytes)
    if not hmac.compare_digest(observed_ca_hash, supplied_ca_hash):
        raise CommandError("CA PEM digest mismatch")
    expected_candidate = candidate_digest(build_candidate(suffix, authorization, ca_pem))
    if not hmac.compare_digest(expected_candidate, supplied_candidate):
        raise CommandError("candidate digest mismatch")
    return PrepareCommand(
        suffix,
        unlock,
        key,
        authorization,
        ca_pem,
        supplied_ca_hash,
        supplied_candidate,
    )


def parse_verify(line: str, expected_unlock_digest: str) -> VerifyCommand:
    if len(line) > 512:
        raise CommandError("command too long")
    if line.endswith("\r") or line.endswith("\n"):
        line = line.rstrip("\r\n")
    if "\r" in line or "\n" in line:
        raise CommandError("embedded line ending")
    parts = line.split(" ")
    if len(parts) != 6 or parts[0] != VERIFY_SCHEMA or parts[5] != "READ_ONLY":
        raise CommandError("VERIFY command shape invalid")
    _, suffix, unlock, key, supplied_candidate, _ = parts
    if HEX64.fullmatch(supplied_candidate) is None:
        raise CommandError("candidate digest invalid")
    _validate_common(suffix, unlock, key, expected_unlock_digest)
    return VerifyCommand(suffix, unlock, key, supplied_candidate)


def render_prepare(
    run_suffix: str,
    unlock_token_hex: str,
    persistence_key_hex: str,
    authorization_digest: str,
    ca_pem: str,
) -> str:
    candidate = build_candidate(run_suffix, authorization_digest, ca_pem)
    ca_bytes = ca_pem.encode("ascii")
    return " ".join(
        (
            PREPARE_SCHEMA,
            run_suffix,
            unlock_token_hex,
            persistence_key_hex,
            authorization_digest,
            encode_base64url(ca_bytes),
            sha256_hex(ca_bytes),
            candidate_digest(candidate),
        )
    )


def render_verify(
    run_suffix: str,
    unlock_token_hex: str,
    persistence_key_hex: str,
    expected_candidate_digest: str,
) -> str:
    if HEX64.fullmatch(expected_candidate_digest) is None:
        raise CommandError("candidate digest invalid")
    return " ".join(
        (
            VERIFY_SCHEMA,
            run_suffix,
            unlock_token_hex,
            persistence_key_hex,
            expected_candidate_digest,
            "READ_ONLY",
        )
    )
