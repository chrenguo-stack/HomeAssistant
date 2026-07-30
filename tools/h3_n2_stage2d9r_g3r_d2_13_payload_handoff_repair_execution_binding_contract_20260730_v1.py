#!/usr/bin/env python3
"""Fail-closed contract for the D2-13 payload-handoff-repaired successor."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_execution_binding_contract_20260729_v1 as upstream

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-D2-13-PAYLOAD-HANDOFF-REPAIR-20260730-01"
STAGE = "H3/N2 Stage 2D-9R G3R D2-13 payload-handoff-repaired successor"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260730-13"
REQUEST_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-request/1"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-physical-preclaim-marker/1"
PACKAGE_BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-execution-package/1"
CLOSURE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-execution-closure-manifest/1"

BASE_PR = 210
BASE_HEAD_SHA = "ad64fcca8ddeeb06bec2d3c379fc3c2c6b669af2"
BASE_BRANCH = "fix/h3-n2-stage2d9r-g3r-d2-12-python-bytecode-repaired-successor-execution-binding-20260729-v1"
MAIN_SHA_AT_BINDING = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
README_BLOB_SHA_AT_BINDING = upstream.README_BLOB_SHA_AT_BINDING

PR210_ARTIFACT_ID = 8730061354
PR210_ARTIFACT_SHA256 = "b2b70234e6c66e99e8811b38b7e50992d741d3e34b868aaca5ce8ddbfd08bca8"
PR210_REVIEW_BINDING_SHA256 = "fee6ad6f6f8406fdc0807dce0f5331e17b55d732bfe3c4339a61d977590a2022"
D2_12_REQUEST_BINDING_SHA256 = "c31a58299331448bfd471138cebc1cddf31608a4148538427db73292ffc23e87"
D2_12_EXECUTION_CLOSURE_SHA256 = "863f20a49830ac389df30e22b4df62c6a0391f53c45d12bef7d35ac74cb106fa"
D2_12_EXECUTION_PACKAGE_SHA256 = "52b0b425944e8aa00d5fb07c89f6db1f6fd7ae706523009004958073a60b7271"
D2_12_ID = upstream.D2_REQUEST_ID
D2_12_STATUS = "CONSUMED_FAILED_OR_STOPPED"
D2_12_FAILURE_CODE = "OUTER_TO_INNER_PAYLOAD_HANDOFF_ARGUMENTS_MISSING"

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
D2_10_ID = upstream.D2_10_ID
D2_10_TERMINAL_RESULT_SHA256 = upstream.D2_10_TERMINAL_RESULT_SHA256
D2_10_TERMINAL_MARKER_SHA256 = upstream.D2_10_TERMINAL_MARKER_SHA256

CLOSURE_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
PACKAGE_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_FILE, PACKAGE_BINDING_FILE, SUMS_FILE})
WRAPPER_FILE = "h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_wrapper_20260730_v1.py"
LAUNCHER_FILE = "run_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_20260730_v1.sh"
CONTRACT_FILE = Path(__file__).name
PREDECESSOR_CONTRACT_FILE = upstream.CONTRACT_FILE
PREDECESSOR_WRAPPER_FILE = upstream.WRAPPER_FILE
IMMUTABLE_PAYLOAD_FILE = "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
RECOVERY_PAYLOAD_FILE = "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
DECISION_FILE = "h3-n2-stage2d9r-g3r-d2-13-payload-handoff-repair-20260730-v1.json"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Stable D2-13 contract failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    require(isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None and canonical_sha256(value) == supplied, "DECISION_BINDING_MISMATCH")
    exact = {
        "decision_id": DECISION_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "d2_request_id": D2_REQUEST_ID,
        "state": "FROZEN_UNAUTHORIZED_D2_13_PAYLOAD_HANDOFF_REPAIR",
        "predecessor_request_id": D2_12_ID,
        "predecessor_status": D2_12_STATUS,
        "predecessor_failure_code": D2_12_FAILURE_CODE,
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "predecessor_board_operation": False,
        "predecessor_replay_permitted": False,
        "shell_to_python_package_root_handoff_required": True,
        "payload_arguments_injected_before_upstream_parser": True,
        "macos_path_normalization_required": True,
        "preclaim_failure_evidence_required": True,
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
        require(len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None and parts[1] and "/" not in parts[1] and "\\" not in parts[1], "PACKAGE_SUMS_INVALID")
        require(parts[1] not in result and parts[1] != SUMS_FILE, "PACKAGE_SUMS_DUPLICATE")
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
    return canonical_sha256({"schema": "gh.h3.n2.stage2d9r-g3r-d2-13-payload-handoff-repaired-execution-package-set/1", "files": entries})


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
        "execution_closure_policy_version": 5,
        "files": files,
    }
    value["execution_closure_sha256"] = canonical_sha256(value)
    return value


def validate_execution_closure(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / CLOSURE_FILE, "EXECUTION_CLOSURE_INVALID")
    supplied = manifest.pop("execution_closure_sha256", None)
    require(isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None and canonical_sha256(manifest) == supplied, "EXECUTION_CLOSURE_BINDING_MISMATCH")
    exact = {
        "schema": CLOSURE_SCHEMA,
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 5,
    }
    for key, expected in exact.items():
        require(manifest.get(key) == expected, "EXECUTION_CLOSURE_" + key.upper())
    entries = manifest.get("files")
    require(isinstance(entries, list) and bool(entries), "EXECUTION_CLOSURE_FILES")
    observed: dict[str, str] = {}
    for entry in entries:
        require(isinstance(entry, dict), "EXECUTION_CLOSURE_ENTRY")
        name, digest = entry.get("name"), entry.get("sha256")
        require(isinstance(name, str) and name and "/" not in name and "\\" not in name, "EXECUTION_CLOSURE_NAME")
        require(isinstance(digest, str) and HEX64.fullmatch(digest) is not None, "EXECUTION_CLOSURE_DIGEST")
        require(name not in observed and name not in CONTROL_FILES, "EXECUTION_CLOSURE_DUPLICATE")
        observed[name] = digest
    actual = {path.name for path in root.iterdir() if path.is_file() and path.name not in CONTROL_FILES}
    require(set(observed) == actual, "EXECUTION_CLOSURE_COVERAGE_MISMATCH")
    for name, digest in observed.items():
        require(sha256_file(root / name) == digest, "EXECUTION_CLOSURE_FILE_MISMATCH")
    require(supplied != D2_12_EXECUTION_CLOSURE_SHA256, "D2_12_EXECUTION_CLOSURE_REUSED")
    manifest["execution_closure_sha256"] = supplied
    return manifest


def validate_launcher(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), "LAUNCHER_FILE_INVALID")
    text = path.read_text(encoding="utf-8")
    required = (
        "PYTHONDONTWRITEBYTECODE=1",
        "export PYTHONDONTWRITEBYTECODE",
        "SCRIPT_DIR=",
        "GH_D2_13_LAUNCHER_PACKAGE_ROOT=",
        "export GH_D2_13_LAUNCHER_PACKAGE_ROOT",
        WRAPPER_FILE,
        'exec "$PYTHON_BIN"',
    )
    for token in required:
        require(token in text, "LAUNCHER_HANDOFF_GUARD_MISSING")
    require(text.index("PYTHONDONTWRITEBYTECODE=1") < text.index("GH_D2_13_LAUNCHER_PACKAGE_ROOT=") < text.index('exec "$PYTHON_BIN"'), "LAUNCHER_HANDOFF_GUARD_ORDER_INVALID")


def validate_execution_package(root: Path) -> dict[str, Any]:
    sums = verify_sums_tree(root)
    closure = validate_execution_closure(root)
    binding = _load_json(root / PACKAGE_BINDING_FILE, "PACKAGE_BINDING_INVALID")
    package_sha = package_set_digest(root)
    exact = {
        "schema": PACKAGE_BINDING_SCHEMA,
        "state": "FROZEN_UNAUTHORIZED_D2_13_PAYLOAD_HANDOFF_REPAIRED_PACKAGE",
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 5,
        "execution_closure_sha256": closure["execution_closure_sha256"],
        "execution_package_sha256": package_sha,
        "pr210_artifact_id": PR210_ARTIFACT_ID,
        "pr210_artifact_sha256": PR210_ARTIFACT_SHA256,
        "pr210_review_binding_sha256": PR210_REVIEW_BINDING_SHA256,
        "d2_12_request_binding_sha256": D2_12_REQUEST_BINDING_SHA256,
        "d2_12_execution_closure_sha256": D2_12_EXECUTION_CLOSURE_SHA256,
        "d2_12_execution_package_sha256": D2_12_EXECUTION_PACKAGE_SHA256,
        "d2_12_request_reuse_permitted": False,
        "d2_12_authorization_reuse_permitted": False,
        "d2_12_execution_closure_reuse_permitted": False,
        "d2_12_execution_package_reuse_permitted": False,
        "shell_to_python_package_root_handoff_required": True,
        "payload_arguments_injected_before_upstream_parser": True,
        "macos_path_normalization_required": True,
        "preclaim_failure_evidence_required": True,
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
        PREDECESSOR_CONTRACT_FILE: upstream.sha256_file(root / PREDECESSOR_CONTRACT_FILE),
        PREDECESSOR_WRAPPER_FILE: upstream.sha256_file(root / PREDECESSOR_WRAPPER_FILE),
        IMMUTABLE_PAYLOAD_FILE: IMMUTABLE_PAYLOAD_TAR_SHA256,
        RECOVERY_PAYLOAD_FILE: RECOVERY_PAYLOAD_TAR_SHA256,
    }
    for name, expected in files.items():
        require(isinstance(expected, str) and HEX64.fullmatch(expected) is not None and sums.get(name) == expected, "PACKAGE_ENTRYPOINT_BINDING_MISMATCH")
    validate_launcher(root / LAUNCHER_FILE)
    require(package_sha != D2_12_EXECUTION_PACKAGE_SHA256, "D2_12_EXECUTION_PACKAGE_REUSED")
    return {"binding": binding, "closure": closure, "package_sha256": package_sha, "sums": sums}


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
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 5,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
        "pr210_artifact_id": PR210_ARTIFACT_ID,
        "pr210_artifact_sha256": PR210_ARTIFACT_SHA256,
        "pr210_review_binding_sha256": PR210_REVIEW_BINDING_SHA256,
        "immutable_build_binding": IMMUTABLE_BUILD_BINDING,
        "application_sha256": APPLICATION_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "shell_to_python_package_root_handoff_required": True,
        "payload_arguments_injected_before_upstream_parser": True,
        "macos_path_normalization_required": True,
        "preclaim_failure_evidence_required": True,
        "predecessor_request_id": D2_12_ID,
        "predecessor_status": D2_12_STATUS,
        "predecessor_failure_code": D2_12_FAILURE_CODE,
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "predecessor_board_operation": False,
        "predecessor_usb_enumeration": False,
        "predecessor_serial_operation": False,
        "predecessor_esptool_operation": False,
        "predecessor_flash_operation": False,
        "predecessor_network_operation": False,
        "predecessor_request_binding_sha256": D2_12_REQUEST_BINDING_SHA256,
        "predecessor_execution_closure_sha256": D2_12_EXECUTION_CLOSURE_SHA256,
        "predecessor_execution_package_sha256": D2_12_EXECUTION_PACKAGE_SHA256,
        "predecessor_request_reuse_permitted": False,
        "predecessor_authorization_reuse_permitted": False,
        "predecessor_execution_package_reuse_permitted": False,
        "predecessor_execution_closure_reuse_permitted": False,
        "physical_baseline_source_request_id": D2_10_ID,
        "physical_baseline_locked_recovery_outcome": "UNKNOWN",
        "physical_baseline_terminal_result_sha256": D2_10_TERMINAL_RESULT_SHA256,
        "physical_baseline_terminal_marker_sha256": D2_10_TERMINAL_MARKER_SHA256,
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
    require(value["request_binding_sha256"] != D2_12_REQUEST_BINDING_SHA256, "D2_12_REQUEST_REUSED")
    return value


def _utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def validate_authorization_contract(authorization: dict[str, Any], request: dict[str, Any], root: Path, *, now: datetime | None = None) -> dict[str, Any]:
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
        "shell_to_python_package_root_handoff": True,
        "payload_arguments_injected_before_upstream_parser": True,
        "macos_path_normalization": True,
        "preclaim_failure_evidence_required": True,
        "predecessor_request_id": D2_12_ID,
        "predecessor_status": D2_12_STATUS,
        "predecessor_authorization_claimed": False,
        "predecessor_authorization_consumed": False,
        "predecessor_replay_permitted": False,
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
    extra = {
        "board_identity_sha256", "serial_identity_sha256", "baseline_state_sha256",
        "private_package_sha256", "private_outer_runner_sha256", "prepare_command_sha256",
        "verify_command_sha256", "python_executable_sha256", "esptool_executable_sha256",
        "openssl_executable_sha256", "mosquitto_executable_sha256", "issued_at", "expires_at",
        "authorization_record_sha256",
    }
    require(set(authorization) == set(required) | extra, "AUTHORIZATION_FIELD_SET_MISMATCH")
    for key, expected in required.items():
        require(authorization.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    for key in extra - {"issued_at", "expires_at", "authorization_record_sha256"}:
        require(isinstance(authorization.get(key), str) and HEX64.fullmatch(authorization[key]) is not None, "AUTHORIZATION_" + key.upper() + "_INVALID")
    issued = _utc(authorization.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = _utc(authorization.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require(0 < (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_WINDOW_INVALID")
    without = dict(authorization)
    supplied = without.pop("authorization_record_sha256", None)
    require(isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None and canonical_sha256(without) == supplied, "AUTHORIZATION_BINDING_MISMATCH")
    return authorization
