#!/usr/bin/env python3
"""Validate the public U1-01/U1-02 closure without reading private material."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STAGE = "H3/N2 Stage 2D-9R G3R successor"
U1_01_ID = "U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-01"
U1_02_ID = "U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-02"
U1_02_RECORD_SHA256 = "88314a56bc5d7dd3e175278e2b01409cde611562f1bea11690adb9ff3f71f348"
U1_02_RESULT_SHA256 = "9ad24d630640ab485e055e7cb8f08c1320f19b6ca37d43e36303ce44d62d0b08"
IMMUTABLE_ARTIFACT_ID = 8638796771
IMMUTABLE_ARCHIVE_SHA256 = "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
FORBIDDEN_TEXT = (
    "BEGIN " + "PRIVATE KEY",
    "BEGIN " + "RSA " + "PRIVATE KEY",
    "BEGIN " + "EC " + "PRIVATE KEY",
    "/" + "Users" + "/",
    "/" + "private" + "/tmp/",
    "mqtt" + "-password" + ".hex",
    "persistence" + "-key" + ".hex",
    "unlock" + "-token" + ".hex",
    "root-ca" + ".key" + ".pem",
    "broker" + ".key" + ".pem",
)


class ClosureError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ClosureError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "PUBLIC_RECORD_INVALID")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    for token in FORBIDDEN_TEXT:
        require(token not in text, "PUBLIC_RECORD_SECRET_OR_PATH_PATTERN")
    value = json.loads(text)
    require(isinstance(value, dict), "PUBLIC_RECORD_NOT_OBJECT")
    return value


def false_boundaries(value: dict[str, Any], *, allow_private_read_key: bool = False) -> None:
    protected = value.get("protected_boundaries")
    require(isinstance(protected, dict), "PROTECTED_BOUNDARIES_MISSING")
    for key, observed in protected.items():
        if allow_private_read_key and key == "private_material_content_read":
            require(observed is False, "PRIVATE_CONTENT_READ_EXPANDED")
        else:
            require(observed is False, f"BOUNDARY_EXPANDED_{key.upper()}")


def validate(u1_01_path: Path, u1_02_path: Path) -> dict[str, Any]:
    first = load_json(u1_01_path)
    second = load_json(u1_02_path)

    require(first.get("stage") == STAGE, "U1_01_STAGE_MISMATCH")
    require(first.get("authorization_id") == U1_01_ID, "U1_01_ID_MISMATCH")
    require(first.get("disposition") == "INVALIDATED_BEFORE_CLAIM", "U1_01_DISPOSITION_MISMATCH")
    state1 = first.get("authorization_state")
    require(isinstance(state1, dict), "U1_01_STATE_MISSING")
    require(state1.get("authorization_record_publicly_frozen") is False,
            "U1_01_RECORD_UNSUPPORTED_PUBLIC_FREEZE")
    require(state1.get("authorization_record_sha256") is None,
            "U1_01_RECORD_SHA_MUST_REMAIN_UNASSERTED")
    for key in (
        "authorization_claimed",
        "authorization_marker_created",
        "authorization_consumed",
    ):
        require(state1.get(key) is False, f"U1_01_{key.upper()}_MISMATCH")
    require(state1.get("replay_permitted") is False, "U1_01_REPLAY_EXPANDED")
    require(state1.get("automatic_retry_permitted") is False, "U1_01_RETRY_EXPANDED")
    false_boundaries(first, allow_private_read_key=True)

    require(second.get("stage") == STAGE, "U1_02_STAGE_MISMATCH")
    require(second.get("authorization_id") == U1_02_ID, "U1_02_ID_MISMATCH")
    require(second.get("status") == "CONSUMED_PASS", "U1_02_STATUS_MISMATCH")
    require(second.get("execution_result") == "PASS", "U1_02_RESULT_MISMATCH")
    require(second.get("deep_binding_status") == "PASS", "U1_02_DEEP_BINDING_MISMATCH")
    require(second.get("authorization_record_sha256") == U1_02_RECORD_SHA256, "U1_02_RECORD_SHA_MISMATCH")
    require(second.get("result_sha256") == U1_02_RESULT_SHA256, "U1_02_RESULT_SHA_MISMATCH")
    immutable = second.get("immutable_artifact")
    require(isinstance(immutable, dict), "IMMUTABLE_BINDING_MISSING")
    require(immutable.get("id") == IMMUTABLE_ARTIFACT_ID, "IMMUTABLE_ID_MISMATCH")
    require(immutable.get("archive_sha256") == IMMUTABLE_ARCHIVE_SHA256, "IMMUTABLE_ARCHIVE_SHA_MISMATCH")
    public = second.get("public_bindings")
    require(isinstance(public, dict), "PUBLIC_BINDINGS_MISSING")
    require(public.get("candidate_digest_sha256") == CANDIDATE_DIGEST_SHA256, "CANDIDATE_DIGEST_MISMATCH")
    for key, observed in public.items():
        if key.endswith("_sha256"):
            require(isinstance(observed, str) and HEX64.fullmatch(observed) is not None,
                    f"PUBLIC_DIGEST_INVALID_{key.upper()}")
    state2 = second.get("authorization_state")
    require(isinstance(state2, dict), "U1_02_STATE_MISSING")
    require(state2.get("authorization_consumed") is True, "U1_02_NOT_CONSUMED")
    require(state2.get("one_shot") is True, "U1_02_NOT_ONE_SHOT")
    require(state2.get("replay_permitted") is False, "U1_02_REPLAY_EXPANDED")
    require(state2.get("automatic_retry_permitted") is False, "U1_02_RETRY_EXPANDED")
    require(state2.get("consumed_marker_status") == "CONSUMED", "U1_02_MARKER_STATE_MISMATCH")
    require(state2.get("consumed_marker_sha256_publicly_frozen") is False,
            "U1_02_MARKER_UNSUPPORTED_PUBLIC_FREEZE")
    require(state2.get("consumed_marker_sha256") is None,
            "U1_02_MARKER_SHA_MUST_REQUIRE_LIVE_PREFLIGHT")
    require(state2.get("live_read_only_preflight_required") is True,
            "U1_02_LIVE_PREFLIGHT_NOT_REQUIRED")
    false_boundaries(second)

    closure = {
        "schema": "gh.h3.n2.stage2d9r-successor-u1-public-closure-binding/1",
        "stage": STAGE,
        "u1_01_record_sha256": sha256_file(u1_01_path),
        "u1_01_disposition": "INVALIDATED_BEFORE_CLAIM",
        "u1_02_record_sha256": sha256_file(u1_02_path),
        "u1_02_authorization_id": U1_02_ID,
        "u1_02_authorization_record_sha256": U1_02_RECORD_SHA256,
        "u1_02_result_sha256": U1_02_RESULT_SHA256,
        "u1_02_status": "CONSUMED_PASS",
        "u1_02_consumed_marker_live_preflight_required": True,
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "replay_permitted": False,
        "d2_authorized": False,
        "physical_execution_authorized": False,
        "private_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    closure["closure_binding_sha256"] = sha256_bytes(canonical_json_bytes(closure))
    return closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--u1-01", type=Path, required=True)
    parser.add_argument("--u1-02", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.u1_01, args.u1_02)
        if args.output is not None:
            require(not args.output.exists(), "OUTPUT_ALREADY_EXISTS")
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ClosureError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
