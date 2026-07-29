#!/usr/bin/env python3
"""Fail-closed contract for the D2-12 bytecode-repaired successor binding."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as upstream

DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-D2-12-PYTHON-BYTECODE-REPAIRED-"
    "SUCCESSOR-EXECUTION-BINDING-20260729-01"
)
STAGE = "H3/N2 Stage 2D-9R G3R D2-12 Python-bytecode-repaired successor"
D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PYTHON-BYTECODE-REPAIRED-"
    "PHYSICAL-20260729-12"
)
REQUEST_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-request/1"
)
AUTH_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-authorization/1"
)
RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-result/1"
)
MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-marker/1"
)
PRE_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-preclaim-result/1"
)
PRE_MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "physical-preclaim-marker/1"
)
PACKAGE_BINDING_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "execution-package/1"
)
CLOSURE_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "execution-closure-manifest/1"
)

BASE_PR = 209
BASE_HEAD_SHA = "bd339afb29aa1c12e2db0c8766f80e776d1435d7"
BASE_BRANCH = (
    "fix/h3-n2-stage2d9r-g3r-d2-11-python-bytecode-"
    "self-contamination-repair-20260729-v1"
)
MAIN_SHA_AT_BINDING = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
README_BLOB_SHA_AT_BINDING = upstream.README_BLOB_SHA_AT_BINDING

PR208_ARTIFACT_ID = 8726419477
PR208_ARTIFACT_SHA256 = (
    "60dc9f3c3ef96c896bd810e1912488395fed9857dee6a8933e6c55cd6c3b8583"
)
PR208_REVIEW_BINDING_SHA256 = (
    "18880cf228f161cee2174d43c90b9cb9df7d08dc543d9a7322ab0170f9190a14"
)
D2_11_REQUEST_BINDING_SHA256 = (
    "ee63e76951cbf232f32f5f45619a0341e8969860e2f3a2f25c100c35225b82fa"
)
D2_11_EXECUTION_CLOSURE_SHA256 = (
    "475da6a040027b64a7908efaccefd156ea9200e2c6ed3f8674fbf0f4468a9f4e"
)
D2_11_EXECUTION_PACKAGE_SHA256 = (
    "0f5a450d8e4560d0969b07e31d8081bbe9961411a5e7a9b1d52a2c229f0fd66a"
)
D2_11_ID = upstream.D2_REQUEST_ID

PR209_ARTIFACT_ID = 8728679363
PR209_ARTIFACT_SHA256 = (
    "917672434bf1a5066af626437dd375dade76bab1119233ad6bb9be79a6eb64b4"
)
PR209_REVIEW_BINDING_SHA256 = (
    "a3abafde375490ccf02743d58c0d4320fea2bbb4d92c4fdcada702be6ff97e1d"
)
BYTECODE_REPAIR_CONTRACT_FILE = (
    "h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_"
    "repair_contract_20260729_v1.py"
)
BYTECODE_REPAIR_WRAPPER_FILE = (
    "h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_"
    "repair_wrapper_20260729_v1.py"
)
BYTECODE_REPAIR_LAUNCHER_FILE = (
    "run_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_"
    "repair_20260729_v1.sh"
)
BYTECODE_REPAIR_CONTRACT_SHA256 = (
    "64be3c73fb5b635b8dba8f006f58e5c37d7fa3725944e4cd48e498e60fddf331"
)
BYTECODE_REPAIR_WRAPPER_SHA256 = (
    "9273f22b97747bdbed83ae2aa730a32ac0f2c0fe1fb492dd3ffd50abcb3b2dd7"
)
BYTECODE_REPAIR_LAUNCHER_SHA256 = (
    "aee23f78ce31e9d41eeb4373a3fd8ca01a4bcdfed7875b571af694824deb9cfd"
)

D2_10_ID = upstream.D2_10_ID
D2_10_TERMINAL_RESULT_SHA256 = upstream.D2_10_TERMINAL_RESULT_SHA256
D2_10_TERMINAL_MARKER_SHA256 = upstream.D2_10_TERMINAL_MARKER_SHA256
D2_10_TERMINAL_RESULT_FILE_SHA256 = upstream.D2_10_TERMINAL_RESULT_FILE_SHA256
D2_10_TERMINAL_MARKER_FILE_SHA256 = upstream.D2_10_TERMINAL_MARKER_FILE_SHA256

IMMUTABLE_BUILD_BINDING = upstream.IMMUTABLE_BUILD_BINDING
APPLICATION_SHA256 = upstream.APPLICATION_SHA256
IMMUTABLE_PAYLOAD_TAR_SHA256 = upstream.IMMUTABLE_PAYLOAD_TAR_SHA256
RECOVERY_PAYLOAD_TAR_SHA256 = upstream.RECOVERY_PAYLOAD_TAR_SHA256
FINAL_EXECUTION_BINDING = upstream.FINAL_EXECUTION_BINDING
FINAL_EXECUTION_BINDING_SHA256 = upstream.FINAL_EXECUTION_BINDING_SHA256
TERMINALIZATION_REPAIR_SHA256 = upstream.TERMINALIZATION_REPAIR_SHA256
PACING_REPAIR_SHA256 = upstream.PACING_REPAIR_SHA256
PACED_CHUNK_BYTES = upstream.PACED_CHUNK_BYTES
INTER_CHUNK_DELAY_MS = upstream.INTER_CHUNK_DELAY_MS

CLOSURE_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
PACKAGE_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_FILE, PACKAGE_BINDING_FILE, SUMS_FILE})
WRAPPER_FILE = (
    "h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_"
    "physical_d2_wrapper_20260729_v1.py"
)
LAUNCHER_FILE = (
    "run_stage2d9r_g3r_d2_12_python_bytecode_repaired_"
    "physical_d2_20260729_v1.sh"
)
CONTRACT_FILE = Path(__file__).name
DECISION_FILE = (
    "h3-n2-stage2d9r-g3r-d2-12-python-bytecode-repaired-"
    "successor-execution-binding-20260729-v1.json"
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Stable D2-12 contract failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


canonical_bytes = upstream.canonical_bytes
canonical_sha256 = upstream.canonical_sha256
sha256_file = upstream.sha256_file


def _load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_decision(path: Path) -> dict[str, Any]:
    value = _load_json(path, "DECISION_FILE_INVALID")
    supplied = value.pop("decision_binding_sha256", None)
    require(
        isinstance(supplied, str)
        and HEX64.fullmatch(supplied) is not None
        and canonical_sha256(value) == supplied,
        "DECISION_BINDING_MISMATCH",
    )
    exact = {
        "decision_id": DECISION_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "d2_request_id": D2_REQUEST_ID,
        "state": "FROZEN_UNAUTHORIZED_D2_12_SUCCESSOR_EXECUTION_BINDING",
        "predecessor_request_id": D2_11_ID,
        "predecessor_status": "PRECLAIM_CONTRACT_FAILED",
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "physical_baseline_source_request_id": D2_10_ID,
        "physical_baseline_locked_recovery_outcome": "UNKNOWN",
        "bytecode_write_disabled_before_python": True,
        "private_outer_runner_bytecode_guard_required": True,
        "stable_leaf_contract_failure_code_required": True,
        "physical_request_created": True,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "DECISION_" + key.upper())
    value["decision_binding_sha256"] = supplied
    return value


def _parse_sums(path: Path) -> dict[str, str]:
    require(path.is_file() and not path.is_symlink(), "PACKAGE_SUMS_INVALID")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(
            len(parts) == 2
            and HEX64.fullmatch(parts[0]) is not None
            and parts[1]
            and "/" not in parts[1]
            and "\\" not in parts[1],
            "PACKAGE_SUMS_INVALID",
        )
        require(
            parts[1] not in result and parts[1] != SUMS_FILE,
            "PACKAGE_SUMS_DUPLICATE",
        )
        result[parts[1]] = parts[0]
    require(bool(result), "PACKAGE_SUMS_EMPTY")
    return result


def verify_sums_tree(root: Path) -> dict[str, str]:
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    for path in root.iterdir():
        require(path.is_file() and not path.is_symlink(), "PACKAGE_MEMBER_INVALID")
    sums = _parse_sums(root / SUMS_FILE)
    observed = {path.name for path in root.iterdir() if path.name != SUMS_FILE}
    require(set(sums) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, expected in sums.items():
        require(sha256_file(root / name) == expected, "PACKAGE_DIGEST_MISMATCH")
    return sums


def package_set_digest(root: Path) -> str:
    entries = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name not in {SUMS_FILE, PACKAGE_BINDING_FILE}
    ]
    require(bool(entries), "PACKAGE_EMPTY")
    return canonical_sha256(
        {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-12-python-bytecode-repaired-"
                "execution-package-set/1"
            ),
            "files": entries,
        }
    )


def build_execution_closure_manifest(root: Path) -> dict[str, Any]:
    files = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name not in CONTROL_FILES
    ]
    require(bool(files), "EXECUTION_CLOSURE_EMPTY")
    value: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 4,
        "files": files,
    }
    value["execution_closure_sha256"] = canonical_sha256(value)
    return value


def validate_execution_closure(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / CLOSURE_FILE, "EXECUTION_CLOSURE_INVALID")
    supplied = manifest.pop("execution_closure_sha256", None)
    require(
        isinstance(supplied, str)
        and HEX64.fullmatch(supplied) is not None
        and canonical_sha256(manifest) == supplied,
        "EXECUTION_CLOSURE_BINDING_MISMATCH",
    )
    exact = {
        "schema": CLOSURE_SCHEMA,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 4,
    }
    for key, expected in exact.items():
        require(manifest.get(key) == expected, "EXECUTION_CLOSURE_" + key.upper())
    entries = manifest.get("files")
    require(isinstance(entries, list) and bool(entries), "EXECUTION_CLOSURE_FILES")
    observed: dict[str, str] = {}
    for entry in entries:
        require(isinstance(entry, dict), "EXECUTION_CLOSURE_ENTRY")
        name = entry.get("name")
        digest = entry.get("sha256")
        require(
            isinstance(name, str)
            and bool(name)
            and "/" not in name
            and "\\" not in name,
            "EXECUTION_CLOSURE_NAME",
        )
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            "EXECUTION_CLOSURE_DIGEST",
        )
        require(
            name not in observed and name not in CONTROL_FILES,
            "EXECUTION_CLOSURE_DUPLICATE",
        )
        observed[name] = digest
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name not in CONTROL_FILES
    }
    require(set(observed) == actual, "EXECUTION_CLOSURE_COVERAGE_MISMATCH")
    for name, digest in observed.items():
        require(sha256_file(root / name) == digest, "EXECUTION_CLOSURE_FILE_MISMATCH")
    require(
        supplied != D2_11_EXECUTION_CLOSURE_SHA256,
        "D2_11_EXECUTION_CLOSURE_REUSED",
    )
    manifest["execution_closure_sha256"] = supplied
    return manifest


def validate_launcher(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), "LAUNCHER_FILE_INVALID")
    text = path.read_text(encoding="utf-8")
    assignment = text.find("PYTHONDONTWRITEBYTECODE=1")
    exported = text.find("export PYTHONDONTWRITEBYTECODE")
    python_bin = text.find("PYTHON_BIN=")
    first_exec = text.find('exec "$PYTHON_BIN"')
    require(
        min(assignment, exported, python_bin, first_exec) >= 0,
        "LAUNCHER_BYTECODE_GUARD_MISSING",
    )
    require(
        assignment < exported < python_bin < first_exec,
        "LAUNCHER_BYTECODE_GUARD_ORDER_INVALID",
    )
    require(
        "PYTHONDONTWRITEBYTECODE=0" not in text
        and WRAPPER_FILE in text
        and BYTECODE_REPAIR_WRAPPER_FILE not in text,
        "LAUNCHER_ENTRYPOINT_INVALID",
    )


def validate_execution_package(root: Path) -> dict[str, Any]:
    sums = verify_sums_tree(root)
    closure = validate_execution_closure(root)
    binding = _load_json(root / PACKAGE_BINDING_FILE, "PACKAGE_BINDING_INVALID")
    package_sha = package_set_digest(root)
    exact = {
        "schema": PACKAGE_BINDING_SCHEMA,
        "state": "FROZEN_UNAUTHORIZED_D2_12_BYTECODE_REPAIRED_PACKAGE",
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 4,
        "execution_closure_sha256": closure["execution_closure_sha256"],
        "execution_package_sha256": package_sha,
        "pr208_artifact_id": PR208_ARTIFACT_ID,
        "pr208_artifact_sha256": PR208_ARTIFACT_SHA256,
        "d2_11_request_binding_sha256": D2_11_REQUEST_BINDING_SHA256,
        "d2_11_execution_closure_sha256": D2_11_EXECUTION_CLOSURE_SHA256,
        "d2_11_execution_package_sha256": D2_11_EXECUTION_PACKAGE_SHA256,
        "d2_11_request_reuse_permitted": False,
        "d2_11_authorization_reuse_permitted": False,
        "d2_11_execution_closure_reuse_permitted": False,
        "d2_11_execution_package_reuse_permitted": False,
        "pr209_artifact_id": PR209_ARTIFACT_ID,
        "pr209_artifact_sha256": PR209_ARTIFACT_SHA256,
        "pr209_review_binding_sha256": PR209_REVIEW_BINDING_SHA256,
        "bytecode_repair_contract_sha256": BYTECODE_REPAIR_CONTRACT_SHA256,
        "bytecode_repair_wrapper_sha256": BYTECODE_REPAIR_WRAPPER_SHA256,
        "bytecode_repair_launcher_sha256": BYTECODE_REPAIR_LAUNCHER_SHA256,
        "bytecode_write_disabled_before_python": True,
        "private_outer_runner_bytecode_guard_required": True,
        "stable_leaf_contract_failure_code_required": True,
        "terminalization_repair_sha256": TERMINALIZATION_REPAIR_SHA256,
        "pacing_repair_sha256": PACING_REPAIR_SHA256,
        "paced_chunk_bytes": PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": INTER_CHUNK_DELAY_MS,
        "firmware_payload_bytes_unchanged": True,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "PACKAGE_BINDING_" + key.upper())
    files = {
        WRAPPER_FILE: binding.get("execution_wrapper_sha256"),
        LAUNCHER_FILE: binding.get("execution_launcher_sha256"),
        CONTRACT_FILE: binding.get("execution_contract_sha256"),
        BYTECODE_REPAIR_CONTRACT_FILE: BYTECODE_REPAIR_CONTRACT_SHA256,
        BYTECODE_REPAIR_WRAPPER_FILE: BYTECODE_REPAIR_WRAPPER_SHA256,
    }
    for name, expected in files.items():
        require(
            isinstance(expected, str)
            and HEX64.fullmatch(expected) is not None
            and sums.get(name) == expected,
            "PACKAGE_ENTRYPOINT_BINDING_MISMATCH",
        )
    validate_launcher(root / LAUNCHER_FILE)
    require(
        package_sha != D2_11_EXECUTION_PACKAGE_SHA256,
        "D2_11_EXECUTION_PACKAGE_REUSED",
    )
    return {
        "binding": binding,
        "closure": closure,
        "package_sha256": package_sha,
        "sums": sums,
    }


def canonical_package_digest(root: Path) -> str:
    return str(validate_execution_package(root)["package_sha256"])


def request_template(root: Path, *, source_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "SOURCE_SHA_INVALID")
    package = validate_execution_package(root)
    binding = package["binding"]
    value: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "state": "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha": MAIN_SHA_AT_BINDING,
        "repository_head_sha_at_package_build": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_package_build": README_BLOB_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 4,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
        "pr208_artifact_id": PR208_ARTIFACT_ID,
        "pr208_artifact_sha256": PR208_ARTIFACT_SHA256,
        "pr209_artifact_id": PR209_ARTIFACT_ID,
        "pr209_artifact_sha256": PR209_ARTIFACT_SHA256,
        "pr209_review_binding_sha256": PR209_REVIEW_BINDING_SHA256,
        "bytecode_repair_contract_sha256": BYTECODE_REPAIR_CONTRACT_SHA256,
        "bytecode_repair_wrapper_sha256": BYTECODE_REPAIR_WRAPPER_SHA256,
        "bytecode_repair_launcher_sha256": BYTECODE_REPAIR_LAUNCHER_SHA256,
        "bytecode_write_disabled_before_python": True,
        "private_outer_runner_bytecode_guard_required": True,
        "stable_leaf_contract_failure_code_required": True,
        "terminalization_repair_sha256": TERMINALIZATION_REPAIR_SHA256,
        "pacing_repair_sha256": PACING_REPAIR_SHA256,
        "paced_chunk_bytes": PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": INTER_CHUNK_DELAY_MS,
        "result_timeout_extension_used": False,
        "command_retry_added": False,
        "immutable_build_binding": IMMUTABLE_BUILD_BINDING,
        "application_sha256": APPLICATION_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "predecessor_request_id": D2_11_ID,
        "predecessor_status": "PRECLAIM_CONTRACT_FAILED",
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "predecessor_board_operation": False,
        "predecessor_usb_enumeration": False,
        "predecessor_serial_operation": False,
        "predecessor_esptool_operation": False,
        "predecessor_flash_operation": False,
        "predecessor_network_operation": False,
        "predecessor_request_binding_sha256": D2_11_REQUEST_BINDING_SHA256,
        "predecessor_execution_closure_sha256": D2_11_EXECUTION_CLOSURE_SHA256,
        "predecessor_execution_package_sha256": D2_11_EXECUTION_PACKAGE_SHA256,
        "predecessor_request_reuse_permitted": False,
        "predecessor_authorization_reuse_permitted": False,
        "predecessor_execution_package_reuse_permitted": False,
        "predecessor_execution_closure_reuse_permitted": False,
        "physical_baseline_source_request_id": D2_10_ID,
        "physical_baseline_source_status": "CONSUMED_FAILED",
        "physical_baseline_terminalization_state": "FORENSIC_TERMINAL_CLOSED",
        "physical_baseline_locked_recovery_outcome": "UNKNOWN",
        "physical_baseline_terminal_result_sha256": D2_10_TERMINAL_RESULT_SHA256,
        "physical_baseline_terminal_marker_sha256": D2_10_TERMINAL_MARKER_SHA256,
        "physical_baseline_replay_permitted": False,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_request_authorized": False,
        "one_shot": True,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "physical_execution_started": False,
    }
    value["request_binding_sha256"] = canonical_sha256(value)
    return value


def validate_physical_request(value: dict[str, Any], root: Path) -> dict[str, Any]:
    expected = request_template(root, source_sha=str(value.get("source_sha")))
    require(set(value) == set(expected), "REQUEST_FIELD_SET_MISMATCH")
    for key, wanted in expected.items():
        require(value.get(key) == wanted, "REQUEST_" + key.upper() + "_MISMATCH")
    require(
        value["request_binding_sha256"] != D2_11_REQUEST_BINDING_SHA256,
        "D2_11_REQUEST_REUSED",
    )
    return value


def _utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def validate_authorization_contract(
    authorization: dict[str, Any],
    request: dict[str, Any],
    root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_physical_request(request, root)
    package = validate_execution_package(root)
    required = {
        "schema": AUTH_SCHEMA,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "source_sha": request["source_sha"],
        "request_binding_sha256": request["request_binding_sha256"],
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": request["execution_wrapper_sha256"],
        "execution_launcher_sha256": request["execution_launcher_sha256"],
        "execution_contract_sha256": request["execution_contract_sha256"],
        "bytecode_repair_contract_sha256": BYTECODE_REPAIR_CONTRACT_SHA256,
        "bytecode_repair_wrapper_sha256": BYTECODE_REPAIR_WRAPPER_SHA256,
        "bytecode_write_disabled_before_python": True,
        "private_outer_runner_bytecode_guard": True,
        "stable_leaf_contract_failure_code_required": True,
        "terminalization_repair_sha256": TERMINALIZATION_REPAIR_SHA256,
        "pacing_repair_sha256": PACING_REPAIR_SHA256,
        "paced_chunk_bytes": PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": INTER_CHUNK_DELAY_MS,
        "predecessor_request_id": D2_11_ID,
        "predecessor_status": "PRECLAIM_CONTRACT_FAILED",
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "predecessor_replay_permitted": False,
        "physical_baseline_source_request_id": D2_10_ID,
        "physical_baseline_terminal_result_sha256": D2_10_TERMINAL_RESULT_SHA256,
        "physical_baseline_terminal_marker_sha256": D2_10_TERMINAL_MARKER_SHA256,
        "physical_baseline_locked_recovery_outcome": "UNKNOWN",
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "authorized": True,
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "one_shot": True,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "locked_recovery_authorized": True,
        "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    require(
        set(authorization) == set(required)
        | {
            "board_identity_sha256",
            "serial_identity_sha256",
            "baseline_state_sha256",
            "private_package_sha256",
            "private_outer_runner_sha256",
            "prepare_command_sha256",
            "verify_command_sha256",
            "python_executable_sha256",
            "esptool_executable_sha256",
            "openssl_executable_sha256",
            "mosquitto_executable_sha256",
            "issued_at",
            "expires_at",
            "authorization_record_sha256",
        },
        "AUTHORIZATION_FIELD_SET_MISMATCH",
    )
    for key, expected in required.items():
        require(
            authorization.get(key) == expected,
            "AUTHORIZATION_" + key.upper() + "_MISMATCH",
        )
    for key in (
        "board_identity_sha256",
        "serial_identity_sha256",
        "baseline_state_sha256",
        "private_package_sha256",
        "private_outer_runner_sha256",
        "prepare_command_sha256",
        "verify_command_sha256",
        "python_executable_sha256",
        "esptool_executable_sha256",
        "openssl_executable_sha256",
        "mosquitto_executable_sha256",
    ):
        require(
            isinstance(authorization.get(key), str)
            and HEX64.fullmatch(authorization[key]) is not None,
            "AUTHORIZATION_" + key.upper() + "_INVALID",
        )
    issued = _utc(authorization.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = _utc(authorization.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require(
        0 < (expires - issued).total_seconds() <= 7200,
        "AUTHORIZATION_WINDOW_INVALID",
    )
    without = dict(authorization)
    supplied = without.pop("authorization_record_sha256", None)
    require(
        isinstance(supplied, str)
        and HEX64.fullmatch(supplied) is not None
        and canonical_sha256(without) == supplied,
        "AUTHORIZATION_BINDING_MISMATCH",
    )
    return authorization
