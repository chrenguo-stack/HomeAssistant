#!/usr/bin/env python3
"""Fail-closed manifest gate for H3/N2 Stage 2D-9 G3."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SCHEMA = "gh.h3.n2.stage2d9-g3-prepare-execution-manifest/1"
ALLOWED_GATES = {"LOCKED", "FLASH_ONLY", "READ_ONLY", "PREPARE_CANDIDATE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class GateError(RuntimeError):
    pass


def require_false(data: dict[str, object], *keys: str) -> None:
    for key in keys:
        if data.get(key) is not False:
            raise GateError(f"{key} must be false")


def validate(manifest: dict[str, object], expected_gate: str | None = None) -> str:
    if manifest.get("schema") != SCHEMA:
        raise GateError("schema mismatch")
    gate = manifest.get("gate")
    if gate not in ALLOWED_GATES:
        raise GateError("gate is not allowed in Stage 2D-9")
    if expected_gate is not None and gate != expected_gate:
        raise GateError("gate does not match expected gate")

    require_false(
        manifest,
        "activate_profile_authorized",
        "cleanup_test_state_authorized",
        "network_operation_authorized",
        "wifi_authorized",
        "mqtt_authorized",
        "broker_authorized",
        "efuse_operation_authorized",
        "secure_boot_change_authorized",
        "flash_encryption_change_authorized",
        "production_environment_operation_authorized",
        "release_authorized",
    )

    if manifest.get("expected_active_generation") != 0:
        raise GateError("active generation must remain zero")
    if manifest.get("expected_candidate_generation_before") != 0:
        raise GateError("candidate generation must start at zero")
    if manifest.get("expected_candidate_generation_after") != 1:
        raise GateError("candidate generation after PREPARE must be one")
    if manifest.get("expected_candidate_state_after") != "PREPARED":
        raise GateError("candidate state after PREPARE must be PREPARED")

    for key in ("source_sha", "artifact_sha256", "candidate_digest_sha256"):
        value = manifest.get(key)
        if value is not None and not SHA256_RE.fullmatch(str(value)):
            raise GateError(f"{key} must be lowercase sha256 or null")

    authorization = manifest.get("prepare_authorization")
    if not isinstance(authorization, dict):
        raise GateError("prepare_authorization must be an object")
    if authorization.get("action") != "PREPARE_CANDIDATE":
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
    writable_nvs = manifest.get("writable_test_nvs_authorized")

    if gate in {"LOCKED", "FLASH_ONLY", "READ_ONLY"}:
        if execution_authorized is not False:
            raise GateError("non-PREPARE gates cannot authorize execution")
        if writable_nvs is not False:
            raise GateError("non-PREPARE gates cannot authorize writable NVS")
        if authorization.get("authorization_id") is not None:
            raise GateError("locked manifest cannot carry authorization id")
    else:
        if execution_authorized is not True:
            raise GateError("PREPARE gate requires explicit execution authorization")
        if writable_nvs is not True:
            raise GateError("PREPARE gate requires isolated writable test NVS")
        if not authorization.get("authorization_id"):
            raise GateError("PREPARE gate requires authorization id")
        if not SHA256_RE.fullmatch(str(manifest.get("candidate_digest_sha256"))):
            raise GateError("PREPARE gate requires candidate digest")
        if manifest.get("allowed_nvs_partition") != "gh2d9_nvs":
            raise GateError("writable partition must be gh2d9_nvs")
        if manifest.get("allowed_nvs_namespace") != "gh2d9_state":
            raise GateError("writable namespace must be gh2d9_state")

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
        print("STAGE2D9_MANIFEST_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D9_MANIFEST_GATE=PASS")
    print(f"GATE={gate}")
    print(f"EXECUTION_AUTHORIZED={str(bool(manifest['execution_authorized'])).lower()}")
    print("ACTIVATE_PROFILE_AUTHORIZED=false")
    print("CLEANUP_TEST_STATE_AUTHORIZED=false")
    print("NETWORK_OPERATION_AUTHORIZED=false")
    print("EFUSE_OPERATION_AUTHORIZED=false")
    print("PRODUCTION_ENVIRONMENT_OPERATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
