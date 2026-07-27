#!/usr/bin/env python3
"""Build the public-only successor D2 review and preflight package."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_contract_20260727_v1.py"
CLOSURE_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_u1_public_closure_20260727_v1.py"
DEFAULT_U1_01 = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-private-content-binding-u1-01-invalidation-l1-v1.json"
DEFAULT_U1_02 = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-private-content-binding-u1-02-success-l1-v1.json"

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED_{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CONTRACT = load_module("stage2d9r_successor_d2_contract", CONTRACT_PATH)
CLOSURE = load_module("stage2d9r_successor_u1_closure", CLOSURE_PATH)

class ReviewError(RuntimeError):
    pass

def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewError(code)

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

def write_text(path: Path, content: str, mode: int = 0o600) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    os.chmod(path, mode)

def exact_request_template(contract: dict[str, Any]) -> str:
    return f"""# Exact D2 authorization request is intentionally not yet generated

D2 request ID: `{contract['d2_request_id']}`

This review package does not authorize execution. The exact request generator
fails closed until all of these live values are available and frozen:

- review Artifact ID and digest;
- review binding SHA-256;
- public preflight Artifact ID and digest;
- private read-only preflight result SHA-256;
- live U1-02 consumed-marker SHA-256;
- one target-board identity SHA-256;
- one serial-candidate identity SHA-256;
- expected board-baseline state SHA-256;
- reviewed execution-package, script and launcher SHA-256;
- one-shot execution-marker name SHA-256;
- locked-recovery package SHA-256;
- issue and expiry timestamps no more than 7200 seconds apart.

Before exact D2 authorization there is no board connection, serial access,
Flash/NVS access, Broker start, PREPARE, VERIFY, ACTIVATE or CLEANUP.
"""

def stop_conditions() -> str:
    return """# Fail-closed stop conditions

Before authorization claim, stop and invalidate without consuming D2 if any of
the following changes:

- main, PR #180, PR #176, source/base SHA, Draft/open/mergeability state;
- any current-source CI conclusion;
- review/preflight/immutable Artifact ID, digest, source or expiry;
- U1-01/U1-02 public closure, U1-02 record/result/consumed marker;
- custody root selection, descriptor/package/candidate/command/PKI digest;
- Python or OpenSSL executable digest;
- reviewed execution package or execution-marker binding.

After claim, success or failure consumes D2. No automatic retry or replay is
allowed. Locked recovery is allowed at most once and only after the destructive
boundary when the exact authorization explicitly includes it.
"""

def readme(binding: dict[str, Any], launcher: str) -> str:
    return f"""# Stage 2D-9R G3R successor D2 review package

State: `D2_REVIEWED`

This package is public-only and review-only. It contains the U1 public closure
binding, D2 contract, state machine, failure matrix, public result and consumed-
marker schemas, execution-package contract, prohibited operations and a description
of the read-only preflight. It contains no authorization record, execution launcher,
private path, secret value or complete PREPARE/VERIFY command.

Run `{launcher}` only to verify package integrity and print public metadata.
That launcher cannot claim D2 and cannot access a board, serial port, network,
Broker, Flash, NVS, PREPARE, VERIFY, ACTIVATE or CLEANUP.

Source SHA: `{binding['source_sha']}`
Main SHA: `{binding['main_sha']}`
Review binding: `{binding['review_binding_sha256']}`
"""

def assemble(
    output: Path,
    source_sha: str,
    main_sha: str,
    u1_01_path: Path = DEFAULT_U1_01,
    u1_02_path: Path = DEFAULT_U1_02,
) -> dict[str, Any]:
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)

    contract = CONTRACT.build_contract(source_sha, main_sha)
    closure = CLOSURE.validate(u1_01_path, u1_02_path)
    state_machine = contract["state_machine"]
    failure_matrix = contract["failure_matrix"]

    binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-review-binding/1",
        "stage": CONTRACT.STAGE,
        "state": "D2_REVIEWED",
        "d2_request_id": CONTRACT.D2_REQUEST_ID,
        "repository": CONTRACT.REPOSITORY,
        "branch": CONTRACT.BRANCH,
        "pull_request": CONTRACT.PULL_REQUEST,
        "base_pull_request": CONTRACT.BASE_PULL_REQUEST,
        "base_source_sha": CONTRACT.BASE_SOURCE_SHA,
        "main_sha": main_sha,
        "source_sha": source_sha,
        "contract_binding_sha256": contract["contract_binding_sha256"],
        "u1_closure_binding_sha256": closure["closure_binding_sha256"],
        "u1_01_public_record_sha256": closure["u1_01_record_sha256"],
        "u1_02_public_record_sha256": closure["u1_02_record_sha256"],
        "u1_02_authorization_record_sha256": closure["u1_02_authorization_record_sha256"],
        "u1_02_result_sha256": closure["u1_02_result_sha256"],
        "u1_02_consumed_marker_live_preflight_required": True,
        "immutable_artifact_id": CONTRACT.PUBLIC_BINDINGS["immutable_artifact_id"],
        "immutable_artifact_archive_sha256": CONTRACT.PUBLIC_BINDINGS["immutable_artifact_archive_sha256"],
        "candidate_digest_sha256": CONTRACT.PUBLIC_BINDINGS["candidate_digest_sha256"],
        "exact_authorization_request_included": False,
        "authorization_record_included": False,
        "execution_package_contract_included": True,
        "execution_launcher_included": False,
        "private_content_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
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
        "production_operation": False,
    }
    binding["review_binding_sha256"] = sha256_bytes(canonical_json_bytes(binding))

    launcher = (
        "run_stage2d9r_successor_d2_review_integrity_probe_20260727_v1_"
        + binding["review_binding_sha256"][:8]
        + ".sh"
    )
    write_text(output / "D2_REVIEW_BINDING.json", json.dumps(binding, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_CONTRACT.json", json.dumps(contract, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_STATE_MACHINE.json", json.dumps(state_machine, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_FAILURE_MATRIX.json", json.dumps(failure_matrix, indent=2, sort_keys=True) + "\n")
    write_text(output / "U1_PUBLIC_CLOSURE_BINDING.json", json.dumps(closure, indent=2, sort_keys=True) + "\n")
    exact_request_schema = {
        "schema": "gh.h3.n2.stage2d9r-successor-exact-d2-authorization-request-schema/1",
        "stage": CONTRACT.STAGE,
        "required_fields": [
            "d2_request_id", "issued_at", "expires_at",
            "authorization_validity_seconds", "repository", "pull_request",
            "base_pull_request", "base_source_sha", "main_sha", "source_sha",
            "contract_binding_sha256", "review_artifact_id",
            "review_artifact_digest_sha256", "review_binding_sha256",
            "public_preflight_artifact_id",
            "public_preflight_artifact_digest_sha256",
            "private_preflight_result_sha256",
            "u1_02_consumed_marker_sha256", "board_identity_sha256",
            "serial_identity_sha256", "baseline_state_sha256",
            "execution_package_sha256", "execution_script_sha256",
            "execution_launcher_sha256", "execution_marker_name_sha256",
            "locked_recovery_package_sha256", "request_binding_sha256",
        ],
        "authorization_validity_seconds_max": CONTRACT.MAX_AUTHORIZATION_SECONDS,
        "request_object_authorized_value": False,
        "authorization_record_created_value": False,
        "secret_values_included": False,
        "private_paths_included": False,
    }
    public_result_schema = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-public-result-schema/1",
        "stage": CONTRACT.STAGE,
        "terminal_results": ["CONSUMED_PASS", "CONSUMED_FAILED", "INVALIDATED_BEFORE_CLAIM"],
        "required_public_bindings": [
            "d2_request_id", "request_binding_sha256", "authorization_record_sha256",
            "consumed_marker_sha256", "source_sha", "main_sha",
            "immutable_artifact_id", "immutable_artifact_archive_sha256",
            "board_identity_sha256", "flash_sha256", "candidate_digest_sha256",
            "prepare_result_sha256", "verify_result_sha256", "terminal_state",
        ],
        "forbidden_public_content": [
            "private paths", "secret values", "raw board identifier",
            "raw serial path", "private serial logs", "complete private commands",
        ],
        "activate_executed": False,
        "cleanup_executed": False,
        "production_operation": False,
    }
    consumed_marker_schema = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-consumed-marker-schema/1",
        "stage": CONTRACT.STAGE,
        "required_fields": [
            "d2_request_id", "request_binding_sha256", "authorization_record_sha256",
            "status", "one_shot", "replay_permitted",
            "automatic_retry_permitted", "terminal_result_sha256",
        ],
        "allowed_status": ["CONSUMED_PASS", "CONSUMED_FAILED"],
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
        "private_paths_included": False,
    }
    execution_package_contract = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-contract/1",
        "stage": CONTRACT.STAGE,
        "state": "REVIEWED_SOURCE_CONTRACT_ONLY",
        "required_exact_bindings": [
            "authorization request", "authorization record", "target board identity",
            "serial identity", "baseline state", "immutable Artifact",
            "successor private custody", "PREPARE/VERIFY commands",
            "isolated Broker configuration", "locked recovery package",
            "execution marker name",
        ],
        "required_package_digests": [
            "execution_package_sha256", "execution_script_sha256",
            "execution_launcher_sha256", "execution_marker_name_sha256",
            "locked_recovery_package_sha256",
        ],
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "isolated_broker_start_max_count": 1,
        "locked_recovery_max_count": 1,
        "execution_launcher_included": False,
        "authorization_record_included": False,
        "private_content_included": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }
    write_text(output / "EXACT_D2_AUTHORIZATION_REQUEST_SCHEMA.json", json.dumps(exact_request_schema, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_PUBLIC_RESULT_SCHEMA.json", json.dumps(public_result_schema, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_CONSUMED_MARKER_SCHEMA.json", json.dumps(consumed_marker_schema, indent=2, sort_keys=True) + "\n")
    write_text(output / "D2_EXECUTION_PACKAGE_CONTRACT.json", json.dumps(execution_package_contract, indent=2, sort_keys=True) + "\n")
    write_text(output / "EXACT_D2_AUTHORIZATION_REQUEST_PENDING.md", exact_request_template(contract))
    write_text(output / "STOP_CONDITIONS.md", stop_conditions())
    write_text(output / "README.md", readme(binding, launcher))
    preflight = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-contract/1",
        "stage": CONTRACT.STAGE,
        "source_sha": source_sha,
        "main_sha": main_sha,
        "review_binding_sha256": binding["review_binding_sha256"],
        "required_checks": [
            "LIVE_REPOSITORY_PR_AND_CI",
            "REVIEW_AND_PUBLIC_PREFLIGHT_ARTIFACT_METADATA",
            "IMMUTABLE_ARTIFACT_BYTES",
            "SUCCESSOR_CUSTODY_METADATA_WITHOUT_SECRET_CONTENT",
            "U1_02_AUTHORIZATION_RECORD_RESULT_AND_CONSUMED_MARKER",
            "PYTHON_AND_OPENSSL_TOOLCHAIN",
            "PREVIOUSLY_FROZEN_BOARD_SERIAL_AND_BASELINE_IDENTITIES",
            "REVIEWED_EXECUTION_AND_LOCKED_RECOVERY_PACKAGES",
            "ABSENCE_OF_OLD_D2_CLAIM_AND_EXECUTION_MARKERS",
        ],
        "deferred_until_exact_d2_claim": [
            "TARGET_BOARD_CONNECTION",
            "SERIAL_CANDIDATE_ENUMERATION",
            "BOARD_BASELINE_READ",
        ],
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "private_material_content_read": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
    }
    write_text(output / "READ_ONLY_PREFLIGHT_CONTRACT.json", json.dumps(preflight, indent=2, sort_keys=True) + "\n")

    script = f"""#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$ROOT"
sha256sum -c SHA256SUMS
PYTHONDONTWRITEBYTECODE=1 "$(command -v python3)" - <<'PY'
import json
from pathlib import Path
b = json.loads(Path("D2_REVIEW_BINDING.json").read_text(encoding="utf-8"))
print("STAGE2D9R_SUCCESSOR_D2_REVIEW_PROBE_V1_BEGIN")
for key in (
    "state", "d2_request_id", "repository", "pull_request",
    "base_pull_request", "main_sha", "source_sha", "review_binding_sha256",
    "exact_authorization_request_included", "authorization_record_included",
    "execution_package_contract_included",
    "execution_launcher_included", "private_content_included",
    "board_operation", "serial_operation", "flash_operation",
    "physical_nvs_operation", "network_operation", "broker_started",
    "prepare_executed", "verify_executed", "activate_executed",
    "cleanup_executed", "production_operation",
):
    value = b[key]
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{{key}}={{value}}")
print("STAGE2D9R_SUCCESSOR_D2_REVIEW_PROBE_V1_END")
PY
"""
    write_text(output / launcher, script, mode=0o700)

    entries = []
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if path.name != "SHA256SUMS":
            entries.append(f"{sha256_file(path)}  {path.name}")
    write_text(output / "SHA256SUMS", "\n".join(entries) + "\n")

    return {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-review-package-summary/1",
        "state": "D2_REVIEWED",
        "d2_request_id": CONTRACT.D2_REQUEST_ID,
        "source_sha": source_sha,
        "main_sha": main_sha,
        "review_binding_sha256": binding["review_binding_sha256"],
        "launcher": launcher,
        "exact_authorization_request_included": False,
        "authorization_record_included": False,
        "execution_package_contract_included": True,
        "execution_launcher_included": False,
        "private_content_included": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--u1-01", type=Path, default=DEFAULT_U1_01)
    parser.add_argument("--u1-02", type=Path, default=DEFAULT_U1_02)
    args = parser.parse_args()
    try:
        result = assemble(
            args.output.expanduser().resolve(strict=False),
            args.source_sha,
            args.main_sha,
            args.u1_01,
            args.u1_02,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ReviewError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
