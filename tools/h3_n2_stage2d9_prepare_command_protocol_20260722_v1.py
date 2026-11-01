from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re

SCHEMA = "GH2D9_PREPARE_V1"
VERIFY_SCHEMA = "GH2D9_VERIFY_V1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUFFIX = re.compile(r"^[a-z0-9]{8,24}$")


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrepareCommand:
    schema: str
    run_suffix: str
    unlock_token_hex: str
    persistence_key_hex: str
    authorization_digest: str
    candidate_digest: str


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_candidate(run_suffix: str, authorization_digest: str) -> dict[str, object]:
    if SUFFIX.fullmatch(run_suffix) is None:
        raise CommandError("run suffix invalid")
    if HEX64.fullmatch(authorization_digest) is None:
        raise CommandError("authorization digest invalid")
    test_run_id = f"gh-test-run-{run_suffix}"
    return {
        "schema": "gh.h3.n2.isolated-candidate-profile/1",
        "test_run_id": test_run_id,
        "system_id": f"gh-test-system-{run_suffix}",
        "node_id": f"gh-test-node-{run_suffix}",
        "broker_host": "stage2d9.invalid",
        "broker_port": 8883,
        "broker_tls_server_name": "stage2d9.invalid",
        "ca_pem": "stage2d9-test-ca",
        "mqtt_username": "stage2d9-test",
        "mqtt_client_id": f"gh-test-client-{test_run_id}",
        "mqtt_password": authorization_digest,
        "test_topic_root": f"gh-test/{test_run_id}/node",
        "credential_generation": 1,
    }


def candidate_material(candidate: dict[str, object]) -> bytes:
    """Canonical representation of the persisted RamCredentialBundle."""
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
    return _sha256_hex(candidate_material(candidate))


def parse_command(
    line: str,
    expected_unlock_digest: str,
    *,
    expected_schema: str = SCHEMA,
) -> PrepareCommand:
    if len(line) > 384:
        raise CommandError("command too long")
    line = line.rstrip("\r\n")
    if "\r" in line or "\n" in line:
        raise CommandError("embedded line ending")
    parts = line.split(" ")
    if len(parts) != 6 or parts[0] != expected_schema or any(not part for part in parts):
        raise CommandError("command shape invalid")
    schema, suffix, unlock, key, auth, supplied_candidate_digest = parts
    if SUFFIX.fullmatch(suffix) is None:
        raise CommandError("run suffix invalid")
    for name, value in (
        ("unlock token", unlock),
        ("persistence key", key),
        ("authorization digest", auth),
        ("candidate digest", supplied_candidate_digest),
    ):
        if HEX64.fullmatch(value) is None:
            raise CommandError(f"{name} invalid")
    if unlock == "0" * 64 or key == "0" * 64 or auth == "0" * 64:
        raise CommandError("zero secret rejected")
    if HEX64.fullmatch(expected_unlock_digest) is None:
        raise CommandError("compiled unlock digest invalid")
    unlock_digest = _sha256_hex(bytes.fromhex(unlock))
    if not hmac.compare_digest(unlock_digest, expected_unlock_digest):
        raise CommandError("unlock digest mismatch")
    built = build_candidate(suffix, auth)
    expected_candidate = candidate_digest(built)
    if not hmac.compare_digest(supplied_candidate_digest, expected_candidate):
        raise CommandError("candidate digest mismatch")
    return PrepareCommand(
        schema,
        suffix,
        unlock,
        key,
        auth,
        supplied_candidate_digest,
    )


def render_command(
    schema: str,
    run_suffix: str,
    unlock_token_hex: str,
    persistence_key_hex: str,
    authorization_digest: str,
) -> str:
    if schema not in {SCHEMA, VERIFY_SCHEMA}:
        raise CommandError("render schema invalid")
    candidate = build_candidate(run_suffix, authorization_digest)
    digest = candidate_digest(candidate)
    return " ".join(
        (
            schema,
            run_suffix,
            unlock_token_hex,
            persistence_key_hex,
            authorization_digest,
            digest,
        )
    )
