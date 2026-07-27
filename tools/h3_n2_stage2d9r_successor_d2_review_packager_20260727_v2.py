#!/usr/bin/env python3
"""V2 public D2 review package with exact recovery/execution Artifact bindings."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_review_packager_20260727_v1.py"
DEFAULT_RECOVERY_ACCEPTANCE = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-locked-recovery-artifact-l1-v1.json"
DEFAULT_EXECUTION_ACCEPTANCE = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-d2-execution-package-l1-v1.json"


def load_v1():
    spec = importlib.util.spec_from_file_location("stage2d9r_successor_d2_review_v1", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("V1_REVIEW_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V1 = load_v1()
RECOVERY_SCHEMA = "gh.h3.n2.stage2d9r-successor-locked-recovery-artifact-acceptance-l1/1"
EXECUTION_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-package-acceptance-l1/1"
RECOVERY_ARTIFACT_ID = 8644594652
RECOVERY_ARTIFACT_DIGEST = "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e"
RECOVERY_PAYLOAD_SHA256 = "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e"
RECOVERY_DESCRIPTOR_SHA256 = "912e7e2ec4f10cb81836e5a50df1dd5745eae2ba057bd51b1929671fb5872beb"
RECOVERY_SOURCE_SHA = "f26ceafcfddec9abc1f8b023451ebe0747f2442b"
EXECUTION_ARTIFACT_ID = 8644968239
EXECUTION_ARTIFACT_DIGEST = "d15928b1930b39871f16a67b768718466ffcd4ed2f4ad0eaefbc424c9a1ca33f"
EXECUTION_PAYLOAD_SHA256 = "30662f81612cb164332ab3c34e1cb197ddba73a2e144aa9119d3bfe1e2520bfd"
EXECUTION_PACKAGE_SHA256 = "d01aeb81b3c23b38061f17e3e32f807b0ceffd79c87cd79d9d47e24f42446112"
EXECUTION_SCRIPT_SHA256 = "1fa9428e940f65e98716f20a5ae78904c96db53e94bdfb0ee5da845894c6d3aa"
EXECUTION_LAUNCHER_SHA256 = "e084a1173d061bb414801bf9cf189c5a11db0590df9a562cd35551fef287cdd3"
EXECUTION_MARKER_SHA256 = "034e7357d0e7cea177c20cc4ea257a72a9a1a9eb02318cef47f5d43ee32f5987"
EXECUTION_SOURCE_SHA = "623f2cddf7ed121952eb8644abe681aa11b5677b"


class ReviewV2Error(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewV2Error(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: object) -> str:
    return sha256_bytes(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8"))


def load_acceptance(path: Path, schema: str, state: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "ACCEPTANCE_FILE_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "ACCEPTANCE_NOT_OBJECT")
    require(value.get("schema") == schema, "ACCEPTANCE_SCHEMA_MISMATCH")
    require(value.get("stage") == V1.CONTRACT.STAGE, "ACCEPTANCE_STAGE_MISMATCH")
    require(value.get("state") == state, "ACCEPTANCE_STATE_MISMATCH")
    protected = value.get("protected_boundaries")
    require(isinstance(protected, dict) and protected,
            "ACCEPTANCE_BOUNDARIES_MISSING")
    require(all(observed is False for observed in protected.values()),
            "ACCEPTANCE_BOUNDARY_EXPANDED")
    return value


def validate_exact_acceptance(
    recovery: dict[str, Any], execution: dict[str, Any]
) -> None:
    recovery_artifact = recovery.get("canonical_artifact")
    execution_artifact = execution.get("canonical_artifact")
    execution_bindings = execution.get("execution_bindings")
    require(isinstance(recovery_artifact, dict), "RECOVERY_ARTIFACT_MISSING")
    require(isinstance(execution_artifact, dict), "EXECUTION_ARTIFACT_MISSING")
    require(isinstance(execution_bindings, dict), "EXECUTION_BINDINGS_MISSING")
    expected_recovery = {
        "id": RECOVERY_ARTIFACT_ID,
        "github_digest_sha256": RECOVERY_ARTIFACT_DIGEST,
        "payload_tar_sha256": RECOVERY_PAYLOAD_SHA256,
        "descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
    }
    for key, expected in expected_recovery.items():
        require(recovery_artifact.get(key) == expected,
                f"RECOVERY_ACCEPTANCE_MISMATCH_{key.upper()}")
    require(recovery.get("source_sha") == RECOVERY_SOURCE_SHA,
            "RECOVERY_ACCEPTANCE_SOURCE_MISMATCH")
    expected_execution_artifact = {
        "id": EXECUTION_ARTIFACT_ID,
        "github_digest_sha256": EXECUTION_ARTIFACT_DIGEST,
        "payload_tar_sha256": EXECUTION_PAYLOAD_SHA256,
    }
    for key, expected in expected_execution_artifact.items():
        require(execution_artifact.get(key) == expected,
                f"EXECUTION_ACCEPTANCE_MISMATCH_{key.upper()}")
    expected_execution_bindings = {
        "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
        "execution_script_sha256": EXECUTION_SCRIPT_SHA256,
        "execution_launcher_sha256": EXECUTION_LAUNCHER_SHA256,
        "execution_marker_name_sha256": EXECUTION_MARKER_SHA256,
    }
    for key, expected in expected_execution_bindings.items():
        require(execution_bindings.get(key) == expected,
                f"EXECUTION_ACCEPTANCE_MISMATCH_{key.upper()}")
    require(execution.get("source_sha") == EXECUTION_SOURCE_SHA,
            "EXECUTION_ACCEPTANCE_SOURCE_MISMATCH")
    for acceptance, key in (
        (recovery, "recovery_artifact_accepted"),
        (execution, "execution_package_accepted"),
    ):
        disposition = acceptance.get("disposition")
        require(isinstance(disposition, dict), "ACCEPTANCE_DISPOSITION_MISSING")
        require(disposition.get(key) is True, "ACCEPTANCE_NOT_ACCEPTED")
        require(disposition.get("d2_authorized") is False,
                "ACCEPTANCE_D2_AUTHORIZATION_EXPANDED")
        require(disposition.get("physical_execution_authorized") is False,
                "ACCEPTANCE_PHYSICAL_AUTHORIZATION_EXPANDED")


def assemble(
    output: Path,
    source_sha: str,
    main_sha: str,
    recovery_acceptance_path: Path = DEFAULT_RECOVERY_ACCEPTANCE,
    execution_acceptance_path: Path = DEFAULT_EXECUTION_ACCEPTANCE,
) -> dict[str, Any]:
    summary = V1.assemble(output, source_sha, main_sha)
    recovery = load_acceptance(
        recovery_acceptance_path,
        RECOVERY_SCHEMA,
        "SUCCESSOR_RECOVERY_ARTIFACT_REPRODUCIBLE_AND_FROZEN",
    )
    execution = load_acceptance(
        execution_acceptance_path,
        EXECUTION_SCHEMA,
        "D2_EXECUTION_PACKAGE_REPRODUCIBLE_AND_FROZEN",
    )
    validate_exact_acceptance(recovery, execution)
    recovery_copy = output / "LOCKED_RECOVERY_ARTIFACT_ACCEPTANCE.json"
    execution_copy = output / "D2_EXECUTION_PACKAGE_ACCEPTANCE.json"
    shutil.copyfile(recovery_acceptance_path, recovery_copy)
    shutil.copyfile(execution_acceptance_path, execution_copy)
    os.chmod(recovery_copy, 0o600)
    os.chmod(execution_copy, 0o600)
    artifact_binding: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-successor-d2-frozen-artifact-binding/1",
        "stage": V1.CONTRACT.STAGE,
        "d2_request_id": V1.CONTRACT.D2_REQUEST_ID,
        "review_source_sha": source_sha,
        "locked_recovery": {
            "artifact_id": RECOVERY_ARTIFACT_ID,
            "artifact_digest_sha256": RECOVERY_ARTIFACT_DIGEST,
            "artifact_source_sha": RECOVERY_SOURCE_SHA,
            "payload_tar_sha256": RECOVERY_PAYLOAD_SHA256,
            "descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
            "acceptance_file_sha256": sha256_file(recovery_acceptance_path),
        },
        "execution_package": {
            "artifact_id": EXECUTION_ARTIFACT_ID,
            "artifact_digest_sha256": EXECUTION_ARTIFACT_DIGEST,
            "artifact_source_sha": EXECUTION_SOURCE_SHA,
            "payload_tar_sha256": EXECUTION_PAYLOAD_SHA256,
            "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
            "execution_script_sha256": EXECUTION_SCRIPT_SHA256,
            "execution_launcher_sha256": EXECUTION_LAUNCHER_SHA256,
            "execution_marker_name_sha256": EXECUTION_MARKER_SHA256,
            "acceptance_file_sha256": sha256_file(execution_acceptance_path),
        },
        "arbitrary_recovery_or_execution_digest_accepted": False,
        "exact_authorization_request_included": False,
        "authorization_record_included": False,
        "private_content_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "authorization_created": False,
        "authorization_claimed": False,
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
    artifact_binding["artifact_binding_sha256"] = canonical_sha256(artifact_binding)
    V1.write_text(
        output / "FROZEN_RECOVERY_AND_EXECUTION_BINDING.json",
        json.dumps(artifact_binding, indent=2, sort_keys=True) + "\n",
    )

    binding_path = output / "D2_REVIEW_BINDING.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding.update({
        "frozen_locked_recovery_bound": True,
        "frozen_execution_package_bound": True,
        "arbitrary_recovery_or_execution_digest_accepted": False,
        "artifact_binding_sha256": artifact_binding["artifact_binding_sha256"],
        "locked_recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "locked_recovery_artifact_digest_sha256": RECOVERY_ARTIFACT_DIGEST,
        "locked_recovery_package_sha256": RECOVERY_PAYLOAD_SHA256,
        "execution_artifact_id": EXECUTION_ARTIFACT_ID,
        "execution_artifact_digest_sha256": EXECUTION_ARTIFACT_DIGEST,
        "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
        "execution_script_sha256": EXECUTION_SCRIPT_SHA256,
        "execution_launcher_sha256": EXECUTION_LAUNCHER_SHA256,
        "execution_marker_name_sha256": EXECUTION_MARKER_SHA256,
    })
    binding.pop("review_binding_sha256", None)
    binding["review_binding_sha256"] = canonical_sha256(binding)
    V1.write_text(binding_path, json.dumps(binding, indent=2, sort_keys=True) + "\n")

    preflight_path = output / "READ_ONLY_PREFLIGHT_CONTRACT.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    checks = list(preflight["required_checks"])
    for check in (
        "EXACT_LOCKED_RECOVERY_ARTIFACT_METADATA_AND_ACCEPTANCE",
        "EXACT_D2_EXECUTION_ARTIFACT_METADATA_AND_ACCEPTANCE",
        "NO_ARBITRARY_RECOVERY_OR_EXECUTION_DIGESTS",
    ):
        if check not in checks:
            checks.append(check)
    preflight["required_checks"] = checks
    preflight["artifact_binding_sha256"] = artifact_binding["artifact_binding_sha256"]
    preflight["arbitrary_recovery_or_execution_digest_accepted"] = False
    V1.write_text(
        preflight_path, json.dumps(preflight, indent=2, sort_keys=True) + "\n"
    )

    launcher = next(
        path.name for path in output.iterdir()
        if path.name.startswith("run_stage2d9r_successor_d2_review_integrity_probe_")
    )
    V1.write_text(output / "README.md", V1.readme(binding, launcher))
    entries = []
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if path.name != "SHA256SUMS":
            entries.append(f"{sha256_file(path)}  {path.name}")
    V1.write_text(output / "SHA256SUMS", "\n".join(entries) + "\n")
    return {
        **summary,
        "review_binding_sha256": binding["review_binding_sha256"],
        "artifact_binding_sha256": artifact_binding["artifact_binding_sha256"],
        "frozen_locked_recovery_bound": True,
        "frozen_execution_package_bound": True,
        "arbitrary_recovery_or_execution_digest_accepted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--recovery-acceptance", type=Path,
                        default=DEFAULT_RECOVERY_ACCEPTANCE)
    parser.add_argument("--execution-acceptance", type=Path,
                        default=DEFAULT_EXECUTION_ACCEPTANCE)
    args = parser.parse_args()
    try:
        result = assemble(
            args.output,
            args.source_sha,
            args.main_sha,
            args.recovery_acceptance.resolve(strict=True),
            args.execution_acceptance.resolve(strict=True),
        )
    except Exception as exc:
        if isinstance(exc, (ReviewV2Error, V1.ReviewError)) and exc.args:
            code = exc.args[0]
        else:
            code = type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
