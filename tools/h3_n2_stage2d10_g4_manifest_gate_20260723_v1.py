#!/usr/bin/env python3
"""Fail-closed execution manifest gate for H3/N2 Stage 2D-10 G4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SCHEMA = "gh.h3.n2.stage2d10-g4-activate-execution-manifest/1"
ALLOWED_GATES = {"LOCKED", "READ_ONLY", "ACTIVATE_PROFILE"}
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PARTITION = "gh2d8_p2d9"
NAMESPACE = "gh2d8_s2d9"


class GateError(RuntimeError):
    pass


def require_false(data: dict[str, object], *keys: str) -> None:
    for key in keys:
        if data.get(key) is not False:
            raise GateError(f"{key} must be false")


def require_true(data: dict[str, object], *keys: str) -> None:
    for key in keys:
        if data.get(key) is not True:
            raise GateError(f"{key} must be true")


def require_optional_commit_sha(data: dict[str, object], key: str) -> None:
    value = data.get(key)
    if value is not None and COMMIT_SHA_RE.fullmatch(str(value)) is None:
        raise GateError(f"{key} must be lowercase 40-hex commit SHA or null")


def require_optional_sha256(data: dict[str, object], *keys: str) -> None:
    for key in keys:
        value = data.get(key)
        if value is not None and SHA256_RE.fullmatch(str(value)) is None:
            raise GateError(f"{key} must be lowercase sha256 or null")


def validate(manifest: dict[str, object], expected_gate: str | None = None) -> str:
    if manifest.get("schema") != SCHEMA:
        raise GateError("schema mismatch")
    if manifest.get("stage") != "H3/N2 Stage 2D-10 G4":
        raise GateError("stage mismatch")

    gate = manifest.get("gate")
    if gate not in ALLOWED_GATES:
        raise GateError("gate is not allowed in Stage 2D-10")
    if expected_gate is not None and gate != expected_gate:
        raise GateError("gate does not match expected gate")

    require_false(
        manifest,
        "prepare_candidate_authorized",
        "cleanup_test_state_authorized",
        "efuse_operation_authorized",
        "secure_boot_change_authorized",
        "flash_encryption_change_authorized",
        "production_environment_operation_authorized",
        "release_authorized",
    )

    expected_values = {
        "expected_active_generation_before": 0,
        "expected_candidate_generation_before": 1,
        "expected_candidate_state_before": "PREPARED",
        "expected_active_generation_after": 1,
        "expected_candidate_generation_after": 0,
        "expected_active_state_after": "ACTIVE",
        "allowed_nvs_partition": PARTITION,
        "allowed_nvs_namespace": NAMESPACE,
    }
    for key, expected in expected_values.items():
        if manifest.get(key) != expected:
            raise GateError(f"{key} mismatch")

    require_optional_commit_sha(manifest, "source_sha")
    require_optional_sha256(
        manifest,
        "artifact_sha256",
        "candidate_digest_sha256",
    )

    authorization = manifest.get("activation_authorization")
    if not isinstance(authorization, dict):
        raise GateError("activation_authorization must be an object")
    if authorization.get("action") != "ACTIVATE_PROFILE":
        raise GateError("authorization action mismatch")
    if authorization.get("active_generation") != 0:
        raise GateError("authorization active generation mismatch")
    if authorization.get("candidate_generation") != 1:
        raise GateError("authorization candidate generation mismatch")
    if authorization.get("one_shot") is not True:
        raise GateError("authorization must be one-shot")
    if authorization.get("replay_permitted") is not False:
        raise GateError("authorization replay must be false")

    execution_authorized = manifest.get("execution_authorized")
    authorization_id = authorization.get("authorization_id")

    if gate in {"LOCKED", "READ_ONLY"}:
        if execution_authorized is not False:
            raise GateError("non-ACTIVATE gates cannot authorize execution")
        require_false(
            manifest,
            "writable_test_nvs_authorized",
            "temporary_network_authorized",
            "temporary_wifi_authorized",
            "temporary_mqtt_authorized",
            "temporary_broker_authorized",
            "post_restart_verify_authorized",
        )
        if authorization_id is not None:
            raise GateError("non-ACTIVATE manifest cannot carry authorization id")
    else:
        if execution_authorized is not True:
            raise GateError("ACTIVATE gate requires explicit execution authorization")
        require_true(
            manifest,
            "writable_test_nvs_authorized",
            "temporary_network_authorized",
            "temporary_wifi_authorized",
            "temporary_mqtt_authorized",
            "temporary_broker_authorized",
            "post_restart_verify_authorized",
        )
        if not isinstance(authorization_id, str) or not authorization_id:
            raise GateError("ACTIVATE gate requires authorization id")
        if COMMIT_SHA_RE.fullmatch(str(manifest.get("source_sha"))) is None:
            raise GateError("ACTIVATE gate requires source_sha")
        for key in ("artifact_sha256", "candidate_digest_sha256"):
            if SHA256_RE.fullmatch(str(manifest.get(key))) is None:
                raise GateError(f"ACTIVATE gate requires {key}")

    return str(gate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-gate", choices=sorted(ALLOWED_GATES))
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        gate = validate(manifest, args.expect_gate)
    except Exception as exc:
        print("STAGE2D10_G4_MANIFEST_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D10_G4_MANIFEST_GATE=PASS")
    print(f"GATE={gate}")
    print(
        "EXECUTION_AUTHORIZED="
        + str(bool(manifest["execution_authorized"])).lower()
    )
    print("PREPARE_CANDIDATE_AUTHORIZED=false")
    print("CLEANUP_TEST_STATE_AUTHORIZED=false")
    print("EFUSE_OPERATION_AUTHORIZED=false")
    print("PRODUCTION_ENVIRONMENT_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
