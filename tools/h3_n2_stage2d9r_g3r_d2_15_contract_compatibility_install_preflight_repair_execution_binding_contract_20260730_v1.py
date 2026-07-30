#!/usr/bin/env python3
"""Fail-closed D2-15 contract with D2-11 installer compatibility."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1 as upstream

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-D2-15-CONTRACT-COMPATIBILITY-INSTALL-PREFLIGHT-REPAIR-20260730-01"
STAGE = "H3/N2 Stage 2D-9R G3R D2-15 contract-compatibility-install-preflight-repaired successor"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-CONTRACT-COMPATIBILITY-INSTALL-PREFLIGHT-REPAIRED-PHYSICAL-20260730-15"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-request/1"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-physical-preclaim-marker/1"
PACKAGE_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-execution-package/1"
CLOSURE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repaired-execution-closure-manifest/1"
BASE_PR = 213
BASE_HEAD_SHA = "1d62ba600f68e4dd5e91f0cd63331e85a1d9f95d"
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-d2-14-payload-extraction-ownership-repair-20260730-v1"
MAIN_SHA_AT_BINDING = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
PR213_ARTIFACT_ID = 8745445393
PR213_ARTIFACT_SHA256 = "ed25703b130b4fed65e51f9192d6ca45e1ebf0eeb05f46f71caf8d1687dc2a56"
PR213_REVIEW_BINDING_SHA256 = "7ea47b0250fd093d4535ddfb03280488afc66334ad0e1802965ded312d0cfb6c"
D2_14_REQUEST_BINDING_SHA256 = "3fbd96eb10cb185d5c13cca539287c2d5acf95bc1a1a033d4a9f1f65ed77bf40"
D2_14_EXECUTION_CLOSURE_SHA256 = "6b2ffeb24b2a42139b31574ad201c6ec837e9f6ab9d4932d0344712a42b94798"
D2_14_EXECUTION_PACKAGE_SHA256 = "565ca6b08f74a9ff14b8971854d4e2718d5424d5683bf0d35a4d9dcc986ca4c0"
D2_14_ID = upstream.D2_REQUEST_ID
D2_14_TERMINAL_STATE = "CONSUMED_FAILED_OR_STOPPED"
D2_14_FAILURE_CODE = "CONTRACT_COMPATIBILITY_SYMBOL_MISSING_CANONICAL_PACKAGE_DIGEST"
D2_14_TERMINAL_OUTPUT_FILE_SHA256 = "a3c86b32c71f82de347fbd949e0e77d617704ac8ac7ae2a6c66e6dd229f87e91"
D2_14_STDOUT_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
D2_14_STDERR_SHA256 = "666e3085307bc1301b192feb36fcb62898bf9144862343f139c5123ed2ef66c7"
D2_14_RETURN_CODE = 1
D2_14_RESULT_FILE_PRESENT = False
CLOSURE_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
PACKAGE_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_FILE, PACKAGE_BINDING_FILE, SUMS_FILE})
WRAPPER_FILE = "h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repaired_physical_d2_wrapper_20260730_v1.py"
LAUNCHER_FILE = "run_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repaired_physical_d2_20260730_v1.sh"
CONTRACT_FILE = Path(__file__).name
DECISION_FILE = "h3-n2-stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repair-20260730-v1.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

# Preserve every payload/baseline constant used by inherited physical layers.
IMMUTABLE_BUILD_BINDING = upstream.IMMUTABLE_BUILD_BINDING
APPLICATION_SHA256 = upstream.APPLICATION_SHA256
IMMUTABLE_PAYLOAD_TAR_SHA256 = upstream.IMMUTABLE_PAYLOAD_TAR_SHA256
RECOVERY_PAYLOAD_TAR_SHA256 = upstream.RECOVERY_PAYLOAD_TAR_SHA256
IMMUTABLE_PAYLOAD_FILE = upstream.IMMUTABLE_PAYLOAD_FILE
RECOVERY_PAYLOAD_FILE = upstream.RECOVERY_PAYLOAD_FILE
FINAL_EXECUTION_BINDING = upstream.FINAL_EXECUTION_BINDING
FINAL_EXECUTION_BINDING_SHA256 = upstream.FINAL_EXECUTION_BINDING_SHA256
D2_10_ID = upstream.D2_10_ID
D2_10_TERMINAL_RESULT_SHA256 = upstream.D2_10_TERMINAL_RESULT_SHA256
D2_10_TERMINAL_MARKER_SHA256 = upstream.D2_10_TERMINAL_MARKER_SHA256


class ContractError(RuntimeError):
    """Stable D2-15 contract failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_decision(path: Path) -> dict[str, Any]:
    value = load_json(path, "DECISION_FILE_INVALID")
    supplied = value.pop("decision_binding_sha256", None)
    require(isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None, "DECISION_BINDING_MISMATCH")
    require(canonical_sha256(value) == supplied, "DECISION_BINDING_MISMATCH")
    exact = {
        "decision_id": DECISION_ID, "base_pr": BASE_PR, "base_head_sha": BASE_HEAD_SHA,
        "d2_request_id": D2_REQUEST_ID,
        "state": "FROZEN_UNAUTHORIZED_D2_15_CONTRACT_COMPATIBILITY_INSTALL_PREFLIGHT_REPAIR",
        "predecessor_request_id": D2_14_ID, "predecessor_terminal_state": D2_14_TERMINAL_STATE,
        "predecessor_failure_code": D2_14_FAILURE_CODE, "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False, "predecessor_board_operation": False,
        "predecessor_replay_permitted": False, "contract_compatibility_symbol_required": "canonical_package_digest",
        "host_install_preflight_required": True, "preclaim_unhandled_exception_terminalization_required": True,
        "outer_payload_preextraction_prohibited": True, "inner_payload_extraction_single_owner": True,
        "payload_roots_empty_before_inner_start": True, "payload_tar_copy_inside_roots_prohibited": True,
        "real_shell_integration_required": True, "macos_path_normalization_required": True,
        "preclaim_failure_evidence_required": True, "physical_request_created": True,
        "physical_request_authorized": False, "physical_authorization_created": False,
        "board_operation": False, "usb_enumeration": False, "serial_operation": False,
        "esptool_operation": False, "flash_operation": False, "network_operation": False,
        "replay_permitted": False, "automatic_retry_permitted": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "DECISION_" + key.upper())
    value["decision_binding_sha256"] = supplied
    return value


def package_set_digest(root: Path) -> str:
    files = [
        {"name": p.name, "sha256": sha256_file(p)}
        for p in sorted(root.iterdir(), key=lambda x: x.name)
        if p.is_file() and not p.is_symlink() and p.name not in {SUMS_FILE, PACKAGE_BINDING_FILE}
    ]
    require(bool(files), "PACKAGE_EMPTY")
    return canonical_sha256({"schema": "gh.h3.n2.stage2d9r-g3r-d2-15-package-set/1", "files": files})


def build_execution_closure_manifest(root: Path) -> dict[str, Any]:
    files = [
        {"name": p.name, "sha256": sha256_file(p)}
        for p in sorted(root.iterdir(), key=lambda x: x.name)
        if p.is_file() and not p.is_symlink() and p.name not in CONTROL_FILES
    ]
    value: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA, "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
        "base_pr": BASE_PR, "base_head_sha": BASE_HEAD_SHA, "files": files,
    }
    value["execution_closure_sha256"] = canonical_sha256(value)
    return value


def _verify_sums(root: Path) -> None:
    sums = root / SUMS_FILE
    require(sums.is_file() and not sums.is_symlink(), "PACKAGE_SUMS_INVALID")
    expected: dict[str, str] = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        require(HEX64.fullmatch(digest) is not None and name not in expected and "/" not in name, "PACKAGE_SUMS_INVALID")
        expected[name] = digest
    observed = {p.name for p in root.iterdir() if p.is_file() and not p.is_symlink() and p != sums}
    require(set(expected) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in expected.items():
        require(sha256_file(root / name) == digest, "PACKAGE_DIGEST_MISMATCH")


def validate_execution_package(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    require(all(p.is_file() and not p.is_symlink() for p in root.iterdir()), "PACKAGE_MEMBER_INVALID")
    _verify_sums(root)
    closure = load_json(root / CLOSURE_FILE, "EXECUTION_CLOSURE_INVALID")
    supplied = closure.pop("execution_closure_sha256", None)
    require(canonical_sha256(closure) == supplied, "EXECUTION_CLOSURE_BINDING_MISMATCH")
    closure["execution_closure_sha256"] = supplied
    binding = load_json(root / PACKAGE_BINDING_FILE, "EXECUTION_PACKAGE_BINDING_INVALID")
    require(binding.get("schema") == PACKAGE_BINDING_SCHEMA, "EXECUTION_PACKAGE_SCHEMA_MISMATCH")
    require(binding.get("decision_id") == DECISION_ID and binding.get("d2_request_id") == D2_REQUEST_ID, "EXECUTION_PACKAGE_ID_MISMATCH")
    require(binding.get("base_pr") == BASE_PR and binding.get("base_head_sha") == BASE_HEAD_SHA, "EXECUTION_PACKAGE_BASE_MISMATCH")
    require(binding.get("pr213_artifact_id") == PR213_ARTIFACT_ID and binding.get("pr213_artifact_sha256") == PR213_ARTIFACT_SHA256, "PR213_ARTIFACT_MISMATCH")
    require(binding.get("execution_closure_sha256") == supplied, "EXECUTION_CLOSURE_DIGEST_MISMATCH")
    require(binding.get("execution_package_sha256") == package_set_digest(root), "EXECUTION_PACKAGE_DIGEST_MISMATCH")
    for key, name in (("execution_wrapper_sha256", WRAPPER_FILE), ("execution_launcher_sha256", LAUNCHER_FILE), ("execution_contract_sha256", CONTRACT_FILE)):
        require(binding.get(key) == sha256_file(root / name), key.upper() + "_MISMATCH")
    return {"binding": binding, "closure": closure, "package_sha256": binding["execution_package_sha256"]}


def canonical_package_digest(root: Path) -> str:
    """Compatibility symbol required by inherited D2-11 install()."""
    return str(validate_execution_package(root)["package_sha256"])


def request_template(root: Path, *, source_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    package = validate_execution_package(root)
    binding = package["binding"]
    value: dict[str, Any] = {
        "schema": REQUEST_SCHEMA, "state": "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "stage": STAGE, "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
        "source_sha": source_sha, "base_pr": BASE_PR, "base_head_sha": BASE_HEAD_SHA,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
        "pr213_artifact_id": PR213_ARTIFACT_ID, "pr213_artifact_sha256": PR213_ARTIFACT_SHA256,
        "pr213_review_binding_sha256": PR213_REVIEW_BINDING_SHA256,
        "predecessor_request_id": D2_14_ID, "predecessor_terminal_state": D2_14_TERMINAL_STATE,
        "predecessor_failure_code": D2_14_FAILURE_CODE, "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False, "predecessor_board_operation": False,
        "contract_compatibility_symbol_required": "canonical_package_digest", "host_install_preflight_required": True,
        "outer_payload_preextraction_prohibited": True, "inner_payload_extraction_single_owner": True,
        "payload_roots_empty_before_inner_start": True, "payload_tar_copy_inside_roots_prohibited": True,
        "authorized": False, "authorization_created": False, "authorization_claimed": False,
        "authorization_consumed": False, "physical_request_authorized": False, "one_shot": True,
        "prepare_max_count": 1, "verify_max_count": 1, "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY", "replay_permitted": False,
        "automatic_retry_permitted": False, "activate_authorized": False, "cleanup_authorized": False,
        "production_operation_authorized": False, "board_operation": False, "usb_enumeration": False,
        "serial_operation": False, "esptool_operation": False, "flash_operation": False,
        "network_operation": False, "broker_started": False, "prepare_executed": False,
        "verify_executed": False, "physical_execution_started": False,
    }
    value["request_binding_sha256"] = canonical_sha256(value)
    return value


def validate_physical_request(value: dict[str, Any], root: Path) -> dict[str, Any]:
    expected = request_template(root, source_sha=str(value.get("source_sha")))
    require(value == expected, "REQUEST_MISMATCH")
    return value


def validate_authorization_contract(authorization: dict[str, Any], request: dict[str, Any], root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    validate_physical_request(request, root)
    package = validate_execution_package(root)
    fixed = {
        "schema": AUTH_SCHEMA, "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
        "source_sha": request["source_sha"], "request_binding_sha256": request["request_binding_sha256"],
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": request["execution_wrapper_sha256"],
        "execution_launcher_sha256": request["execution_launcher_sha256"],
        "execution_contract_sha256": request["execution_contract_sha256"],
        "authorized": True, "authorization_created": True, "authorization_claimed": False,
        "authorization_consumed": False, "one_shot": True, "prepare_max_count": 1,
        "verify_max_count": 1, "locked_recovery_authorized": True, "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY", "replay_permitted": False,
        "automatic_retry_permitted": False, "activate_authorized": False, "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    for key, expected in fixed.items():
        require(authorization.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    issued = datetime.fromisoformat(str(authorization.get("issued_at")).replace("Z", "+00:00")).astimezone(timezone.utc)
    expires = datetime.fromisoformat(str(authorization.get("expires_at")).replace("Z", "+00:00")).astimezone(timezone.utc)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    require(issued <= current <= expires and 0 < (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_NOT_CURRENT")
    without = dict(authorization); supplied = without.pop("authorization_record_sha256", None)
    require(isinstance(supplied, str) and canonical_sha256(without) == supplied, "AUTHORIZATION_BINDING_MISMATCH")
    return authorization


def __getattr__(name: str) -> Any:
    """Forward unchanged inherited constants used below D2-14."""
    return getattr(upstream, name)
