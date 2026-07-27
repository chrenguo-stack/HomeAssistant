#!/usr/bin/env python3
"""V2 read-only D2 preflight with exact recovery and execution Artifacts.

This wrapper closes the V1 gap where arbitrary shape-valid recovery/execution
SHA-256 values could be supplied. It adds exact acceptance and live Artifact-state
validation, then rebuilds the unauthorized exact request over the augmented private
preflight result. It performs no board, serial, Flash, NVS, network or Broker work.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v1.py"


def load_v1():
    spec = importlib.util.spec_from_file_location("stage2d9r_successor_d2_preflight_v1", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("V1_PREFLIGHT_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V1 = load_v1()
RECOVERY_ACCEPTANCE_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-locked-recovery-artifact-acceptance-l1/1"
)
EXECUTION_ACCEPTANCE_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-d2-execution-package-acceptance-l1/1"
)
RECOVERY_STATE_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-locked-recovery-artifact-state/1"
)
EXECUTION_STATE_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-d2-execution-artifact-state/1"
)
RECOVERY_SOURCE_SHA = "f26ceafcfddec9abc1f8b023451ebe0747f2442b"
RECOVERY_ARTIFACT_ID = 8644594652
RECOVERY_ARTIFACT_DIGEST = "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e"
RECOVERY_PAYLOAD_SHA256 = "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e"
RECOVERY_DESCRIPTOR_SHA256 = "912e7e2ec4f10cb81836e5a50df1dd5745eae2ba057bd51b1929671fb5872beb"
EXECUTION_SOURCE_SHA = "623f2cddf7ed121952eb8644abe681aa11b5677b"
EXECUTION_ARTIFACT_ID = 8644968239
EXECUTION_ARTIFACT_DIGEST = "d15928b1930b39871f16a67b768718466ffcd4ed2f4ad0eaefbc424c9a1ca33f"
EXECUTION_PAYLOAD_SHA256 = "30662f81612cb164332ab3c34e1cb197ddba73a2e144aa9119d3bfe1e2520bfd"
EXECUTION_PACKAGE_SHA256 = "d01aeb81b3c23b38061f17e3e32f807b0ceffd79c87cd79d9d47e24f42446112"
EXECUTION_SCRIPT_SHA256 = "1fa9428e940f65e98716f20a5ae78904c96db53e94bdfb0ee5da845894c6d3aa"
EXECUTION_LAUNCHER_SHA256 = "e084a1173d061bb414801bf9cf189c5a11db0590df9a562cd35551fef287cdd3"
EXECUTION_MARKER_NAME_SHA256 = "034e7357d0e7cea177c20cc4ea257a72a9a1a9eb02318cef47f5d43ee32f5987"


class PreflightV2Error(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightV2Error(code)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "V2_JSON_INPUT_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "V2_JSON_INPUT_NOT_OBJECT")
    return value


def all_false(value: dict[str, Any], keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        require(value.get(key) is False, f"{prefix}_BOUNDARY_EXPANDED_{key.upper()}")


def validate_recovery_acceptance(value: dict[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == RECOVERY_ACCEPTANCE_SCHEMA,
            "RECOVERY_ACCEPTANCE_SCHEMA_MISMATCH")
    require(value.get("stage") == V1.CONTRACT.STAGE, "RECOVERY_ACCEPTANCE_STAGE_MISMATCH")
    require(value.get("state") == "SUCCESSOR_RECOVERY_ARTIFACT_REPRODUCIBLE_AND_FROZEN",
            "RECOVERY_ACCEPTANCE_STATE_MISMATCH")
    require(value.get("source_sha") == RECOVERY_SOURCE_SHA,
            "RECOVERY_ACCEPTANCE_SOURCE_MISMATCH")
    artifact = value.get("canonical_artifact")
    require(isinstance(artifact, dict), "RECOVERY_ACCEPTANCE_ARTIFACT_MISSING")
    require(artifact.get("id") == RECOVERY_ARTIFACT_ID,
            "RECOVERY_ACCEPTANCE_ARTIFACT_ID_MISMATCH")
    require(artifact.get("github_digest_sha256") == RECOVERY_ARTIFACT_DIGEST,
            "RECOVERY_ACCEPTANCE_ARTIFACT_DIGEST_MISMATCH")
    require(artifact.get("payload_tar_sha256") == RECOVERY_PAYLOAD_SHA256,
            "RECOVERY_ACCEPTANCE_PAYLOAD_MISMATCH")
    require(artifact.get("descriptor_sha256") == RECOVERY_DESCRIPTOR_SHA256,
            "RECOVERY_ACCEPTANCE_DESCRIPTOR_MISMATCH")
    builds = value.get("independent_builds")
    require(isinstance(builds, dict), "RECOVERY_ACCEPTANCE_BUILDS_MISSING")
    require(builds.get("clean_build_count") == 2,
            "RECOVERY_ACCEPTANCE_BUILD_COUNT_MISMATCH")
    require(builds.get("payloads_byte_identical") is True,
            "RECOVERY_ACCEPTANCE_NOT_REPRODUCIBLE")
    protected = value.get("protected_boundaries")
    require(isinstance(protected, dict), "RECOVERY_ACCEPTANCE_BOUNDARIES_MISSING")
    require(all(observed is False for observed in protected.values()),
            "RECOVERY_ACCEPTANCE_BOUNDARY_EXPANDED")
    disposition = value.get("disposition")
    require(isinstance(disposition, dict), "RECOVERY_ACCEPTANCE_DISPOSITION_MISSING")
    require(disposition.get("recovery_artifact_accepted") is True,
            "RECOVERY_ACCEPTANCE_NOT_ACCEPTED")
    require(disposition.get("d2_authorized") is False,
            "RECOVERY_ACCEPTANCE_D2_EXPANDED")
    require(disposition.get("physical_execution_authorized") is False,
            "RECOVERY_ACCEPTANCE_PHYSICAL_EXPANDED")
    return {
        "id": RECOVERY_ARTIFACT_ID,
        "digest_sha256": RECOVERY_ARTIFACT_DIGEST,
        "source_sha": RECOVERY_SOURCE_SHA,
        "payload_tar_sha256": RECOVERY_PAYLOAD_SHA256,
        "descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
        "clean_build_count": 2,
        "payloads_byte_identical": True,
    }


def validate_execution_acceptance(value: dict[str, Any]) -> dict[str, Any]:
    require(value.get("schema") == EXECUTION_ACCEPTANCE_SCHEMA,
            "EXECUTION_ACCEPTANCE_SCHEMA_MISMATCH")
    require(value.get("stage") == V1.CONTRACT.STAGE,
            "EXECUTION_ACCEPTANCE_STAGE_MISMATCH")
    require(value.get("state") == "D2_EXECUTION_PACKAGE_REPRODUCIBLE_AND_FROZEN",
            "EXECUTION_ACCEPTANCE_STATE_MISMATCH")
    require(value.get("source_sha") == EXECUTION_SOURCE_SHA,
            "EXECUTION_ACCEPTANCE_SOURCE_MISMATCH")
    artifact = value.get("canonical_artifact")
    bindings = value.get("execution_bindings")
    require(isinstance(artifact, dict) and isinstance(bindings, dict),
            "EXECUTION_ACCEPTANCE_BINDINGS_MISSING")
    require(artifact.get("id") == EXECUTION_ARTIFACT_ID,
            "EXECUTION_ACCEPTANCE_ARTIFACT_ID_MISMATCH")
    require(artifact.get("github_digest_sha256") == EXECUTION_ARTIFACT_DIGEST,
            "EXECUTION_ACCEPTANCE_ARTIFACT_DIGEST_MISMATCH")
    require(artifact.get("payload_tar_sha256") == EXECUTION_PAYLOAD_SHA256,
            "EXECUTION_ACCEPTANCE_PAYLOAD_MISMATCH")
    expected = {
        "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
        "execution_script_sha256": EXECUTION_SCRIPT_SHA256,
        "execution_launcher_sha256": EXECUTION_LAUNCHER_SHA256,
        "execution_marker_name_sha256": EXECUTION_MARKER_NAME_SHA256,
    }
    for key, digest in expected.items():
        require(bindings.get(key) == digest,
                f"EXECUTION_ACCEPTANCE_MISMATCH_{key.upper()}")
    builds = value.get("independent_builds")
    require(isinstance(builds, dict), "EXECUTION_ACCEPTANCE_BUILDS_MISSING")
    require(builds.get("clean_build_count") == 2,
            "EXECUTION_ACCEPTANCE_BUILD_COUNT_MISMATCH")
    require(builds.get("payloads_byte_identical") is True,
            "EXECUTION_ACCEPTANCE_NOT_REPRODUCIBLE")
    protected = value.get("protected_boundaries")
    require(isinstance(protected, dict), "EXECUTION_ACCEPTANCE_BOUNDARIES_MISSING")
    require(all(observed is False for observed in protected.values()),
            "EXECUTION_ACCEPTANCE_BOUNDARY_EXPANDED")
    disposition = value.get("disposition")
    require(isinstance(disposition, dict), "EXECUTION_ACCEPTANCE_DISPOSITION_MISSING")
    require(disposition.get("execution_package_accepted") is True,
            "EXECUTION_ACCEPTANCE_NOT_ACCEPTED")
    require(disposition.get("d2_authorized") is False,
            "EXECUTION_ACCEPTANCE_D2_EXPANDED")
    require(disposition.get("physical_execution_authorized") is False,
            "EXECUTION_ACCEPTANCE_PHYSICAL_EXPANDED")
    return {
        "id": EXECUTION_ARTIFACT_ID,
        "digest_sha256": EXECUTION_ARTIFACT_DIGEST,
        "source_sha": EXECUTION_SOURCE_SHA,
        "payload_tar_sha256": EXECUTION_PAYLOAD_SHA256,
        **expected,
        "clean_build_count": 2,
        "payloads_byte_identical": True,
    }


def validate_frozen_artifact_state(
    value: dict[str, Any], *, schema: str, artifact_id: int,
    digest: str, source_sha: str, prefix: str,
) -> dict[str, Any]:
    require(value.get("schema") == schema, f"{prefix}_STATE_SCHEMA_MISMATCH")
    require(value.get("id") == artifact_id, f"{prefix}_STATE_ID_MISMATCH")
    require(value.get("digest_sha256") == digest, f"{prefix}_STATE_DIGEST_MISMATCH")
    require(value.get("source_sha") == source_sha, f"{prefix}_STATE_SOURCE_MISMATCH")
    require(value.get("expired") is False, f"{prefix}_STATE_EXPIRED")
    require(value.get("accessible") is True, f"{prefix}_STATE_NOT_ACCESSIBLE")
    return {
        "id": artifact_id,
        "digest_sha256": digest,
        "source_sha": source_sha,
        "expired": False,
        "accessible": True,
    }


def validate_exact_arguments(args: argparse.Namespace) -> None:
    expected = {
        "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
        "execution_script_sha256": EXECUTION_SCRIPT_SHA256,
        "execution_launcher_sha256": EXECUTION_LAUNCHER_SHA256,
        "execution_marker_name_sha256": EXECUTION_MARKER_NAME_SHA256,
        "locked_recovery_package_sha256": RECOVERY_PAYLOAD_SHA256,
    }
    for key, digest in expected.items():
        require(getattr(args, key) == digest, f"EXACT_{key.upper()}_MISMATCH")


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_exact_arguments(args)
    recovery_acceptance = validate_recovery_acceptance(
        load_json(args.recovery_acceptance)
    )
    execution_acceptance = validate_execution_acceptance(
        load_json(args.execution_acceptance)
    )
    recovery_state = validate_frozen_artifact_state(
        load_json(args.recovery_artifact_state),
        schema=RECOVERY_STATE_SCHEMA,
        artifact_id=RECOVERY_ARTIFACT_ID,
        digest=RECOVERY_ARTIFACT_DIGEST,
        source_sha=RECOVERY_SOURCE_SHA,
        prefix="RECOVERY_ARTIFACT",
    )
    execution_state = validate_frozen_artifact_state(
        load_json(args.execution_artifact_state),
        schema=EXECUTION_STATE_SCHEMA,
        artifact_id=EXECUTION_ARTIFACT_ID,
        digest=EXECUTION_ARTIFACT_DIGEST,
        source_sha=EXECUTION_SOURCE_SHA,
        prefix="EXECUTION_ARTIFACT",
    )
    base = V1.run(args)
    preflight = dict(base["preflight"])
    preflight.pop("preflight_result_sha256", None)
    preflight["schema"] = "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/2"
    preflight["locked_recovery_artifact"] = {
        **recovery_acceptance,
        "live_state": recovery_state,
    }
    preflight["execution_package_artifact"] = {
        **execution_acceptance,
        "live_state": execution_state,
    }
    preflight["arbitrary_recovery_or_execution_digest_accepted"] = False
    preflight["preflight_result_sha256"] = V1.sha256_bytes(
        json.dumps(preflight, sort_keys=True, separators=(",", ":")).encode()
    )
    contract = V1.CONTRACT.build_contract(
        base["preflight"]["repository_state"]["source_sha"],
        base["preflight"]["repository_state"]["main_sha"],
    )
    u1 = preflight["u1_02"]
    exact_request = V1.CONTRACT.build_exact_authorization_request(
        contract,
        review_artifact_id=args.review_artifact_id,
        review_artifact_digest_sha256=args.review_artifact_digest_sha256,
        review_binding_sha256=preflight["review_binding_sha256"],
        public_preflight_artifact_id=args.public_preflight_artifact_id,
        public_preflight_artifact_digest_sha256=args.public_preflight_artifact_digest_sha256,
        private_preflight_result_sha256=preflight["preflight_result_sha256"],
        u1_02_consumed_marker_sha256=u1["consumed_marker_sha256"],
        board_identity_sha256=args.board_identity_sha256,
        serial_identity_sha256=args.serial_identity_sha256,
        baseline_state_sha256=args.baseline_state_sha256,
        execution_package_sha256=EXECUTION_PACKAGE_SHA256,
        execution_script_sha256=EXECUTION_SCRIPT_SHA256,
        execution_launcher_sha256=EXECUTION_LAUNCHER_SHA256,
        execution_marker_name_sha256=EXECUTION_MARKER_NAME_SHA256,
        locked_recovery_package_sha256=RECOVERY_PAYLOAD_SHA256,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
    )
    return {"preflight": preflight, "exact_request": exact_request}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--review-binding", type=Path, required=True)
    value.add_argument("--repository-state", type=Path, required=True)
    value.add_argument("--review-artifact-state", type=Path, required=True)
    value.add_argument("--review-artifact-id", type=int, required=True)
    value.add_argument("--review-artifact-digest-sha256", required=True)
    value.add_argument("--public-preflight-artifact-state", type=Path, required=True)
    value.add_argument("--public-preflight-artifact-id", type=int, required=True)
    value.add_argument("--public-preflight-artifact-digest-sha256", required=True)
    value.add_argument("--host-probe-result", type=Path, required=True)
    value.add_argument("--home", type=Path, default=Path.home())
    value.add_argument("--u1-02-authorization-record", type=Path, required=True)
    value.add_argument("--u1-02-result", type=Path, required=True)
    value.add_argument("--u1-02-consumed-marker", type=Path, required=True)
    value.add_argument("--openssl-executable-sha256", required=True)
    value.add_argument("--board-identity-sha256", required=True)
    value.add_argument("--serial-identity-sha256", required=True)
    value.add_argument("--baseline-state-sha256", required=True)
    value.add_argument("--execution-package-sha256", required=True)
    value.add_argument("--execution-script-sha256", required=True)
    value.add_argument("--execution-launcher-sha256", required=True)
    value.add_argument("--execution-marker-name-sha256", required=True)
    value.add_argument("--locked-recovery-package-sha256", required=True)
    value.add_argument("--recovery-acceptance", type=Path, required=True)
    value.add_argument("--execution-acceptance", type=Path, required=True)
    value.add_argument("--recovery-artifact-state", type=Path, required=True)
    value.add_argument("--execution-artifact-state", type=Path, required=True)
    value.add_argument("--issued-at", required=True)
    value.add_argument("--expires-at", required=True)
    value.add_argument("--preflight-output", type=Path, required=True)
    value.add_argument("--request-output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = run(args)
        V1.write_json_exclusive(args.preflight_output, result["preflight"])
        V1.write_json_exclusive(args.request_output, result["exact_request"])
    except Exception as exc:
        if isinstance(exc, (PreflightV2Error, V1.PreflightError)) and exc.args:
            code = exc.args[0]
        else:
            code = type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "preflight_result_sha256": result["preflight"]["preflight_result_sha256"],
        "request_binding_sha256": result["exact_request"]["request_binding_sha256"],
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "arbitrary_recovery_or_execution_digest_accepted": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
