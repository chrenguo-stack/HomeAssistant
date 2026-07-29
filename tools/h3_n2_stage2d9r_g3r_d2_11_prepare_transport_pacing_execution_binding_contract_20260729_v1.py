#!/usr/bin/env python3
"""Fail-closed contract for the D2-11 paced-transport successor binding."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-D2-11-PREPARE-TRANSPORT-PACING-"
    "SUCCESSOR-EXECUTION-BINDING-20260729-01"
)
STAGE = "H3/N2 Stage 2D-9R G3R D2-11 paced PREPARE transport successor"
D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PREPARE-TRANSPORT-PACING-"
    "PHYSICAL-20260729-11"
)
REQUEST_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-request/1"
)
AUTH_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-authorization/1"
)
RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-result/1"
)
MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-marker/1"
)
PRE_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-preclaim-result/1"
)
PRE_MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "physical-preclaim-marker/1"
)
PACKAGE_BINDING_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "execution-package/1"
)
CLOSURE_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-11-execution-closure-manifest/1"
)

BASE_PR = 207
BASE_HEAD_SHA = "8be62eb76626a5f65f3635a02fe4ec06b0ca80c2"
MAIN_SHA_AT_BINDING = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
README_BLOB_SHA_AT_BINDING = "23ccbd3d31c0333924af6d4791f4dde24d1b1b89"

PR205_ARTIFACT_ID = 8718562956
PR205_ARTIFACT_SHA256 = (
    "218b2138640dc3d5a21d3a0a6f455b9708de11eac7ca4b6908c167776a36c479"
)
PR205_REVIEW_BINDING_SHA256 = (
    "d2a7b7fc94735c615143149bfff2e74b129569c0355decad12449e6852c0064e"
)
PR205_EXECUTION_PACKAGE_SHA256 = (
    "ec02afe63c894ef5bbea4f8537ad588a5cf15f8a9cc2f382092f35e9c0b9ccd2"
)
PR205_EXECUTION_CLOSURE_SHA256 = (
    "6a85e8ec5380db7ee3a09d6de458bd74fa2dfc09d1249c0bbc6a00b32f0ed868"
)

PR206_ARTIFACT_ID = 8722654153
PR206_ARTIFACT_SHA256 = (
    "c014fa369917bceb293f1234c96c007feffd67e0732c3bc8ea1591c0004a9614"
)
PR206_REVIEW_BINDING_SHA256 = (
    "ba8bb4392a41a67fe0f1a6dc1636f4a5ae6eadf9a31b8a14940299d88972504d"
)
TERMINALIZATION_REPAIR_SHA256 = (
    "edc10a2f7ffd6225306675db2e55d6f64a16e9d10943cb8bcf520ecf6b013a1b"
)

PR207_ARTIFACT_ID = 8724360014
PR207_ARTIFACT_SHA256 = (
    "ece2de20f8e79f396f7aca180ac55d95e4ada1262ba595080df2d90709f778c0"
)
PR207_REVIEW_BINDING_SHA256 = (
    "7e7d8a2d6f11e8f5fa88934f99c1e1dad1d6431835bccd7f9a801c0e32f00b63"
)
PACING_REPAIR_SHA256 = (
    "134239afe9705157b05299becba88f20cae096e94ceef11af00bc36440d9afc9"
)
PACED_CHUNK_BYTES = 64
INTER_CHUNK_DELAY_MS = 100

D2_10_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-"
    "PHYSICAL-20260729-10"
)
D2_10_REQUEST_BINDING_SHA256 = (
    "599b0cc7f9468a0fd9b68e1cee0998a69f9c240f6a69324abd24ca900061cc54"
)
D2_10_AUTHORIZATION_RECORD_SHA256 = (
    "d7b9a37e9272dc834af13c054d15e336f11dafcc0471b268f9557410b84bf287"
)
D2_10_AUTHORIZATION_FILE_SHA256 = (
    "e4adc24ba07f81dc6286f9cdb0fb8d4632a00e27fbaa12c34cab66c1ab82dd91"
)
D2_10_TERMINAL_RESULT_SHA256 = (
    "715079d46d8f6f02b396b519d97fb2dd77322d8f293ba3749d8337e835d7fda6"
)
D2_10_TERMINAL_MARKER_SHA256 = (
    "2bd46c499c9cbf1462c834cc8374990789aaa0f654e373ffde40304c8d818295"
)
D2_10_TERMINAL_RESULT_FILE_SHA256 = (
    "d79963208425a62fca26d459913b490d86d1abfe77a2217fca19b01369a9738e"
)
D2_10_TERMINAL_MARKER_FILE_SHA256 = (
    "4da37f572a9fef25e7842dc3fe23e931236f5c6473487b9707e62762591d286a"
)

IMMUTABLE_BUILD_BINDING = "4051f5d541898cef742f35aeec757e7fc479f383"
APPLICATION_SHA256 = "d60b2e0ccf5013629ee7b7aea017a06387e540380dbf2522415c8876a4cf3032"
IMMUTABLE_PAYLOAD_TAR_SHA256 = (
    "ed8e4c673e89107750743702c7e4f4cb9bfada9c53519edcc4ee31719045b2de"
)
RECOVERY_PAYLOAD_TAR_SHA256 = (
    "9a1b75a39edc4b47d7e54417bdb1e6a07671f37a9100e7f4364e63383e11eeb2"
)
FINAL_EXECUTION_BINDING = "307fcc23fd606afe9898a7879f2898b012c4bbe5"
FINAL_EXECUTION_BINDING_SHA256 = (
    "307fcc23fd606afe9898a7879f2898b012c4bbe5d6c86d8b950a0455ad68789b"
)

CLOSURE_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
PACKAGE_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_FILE, PACKAGE_BINDING_FILE, SUMS_FILE})
WRAPPER_FILE = (
    "h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_"
    "physical_d2_wrapper_20260729_v1.py"
)
LAUNCHER_FILE = (
    "run_stage2d9r_g3r_d2_11_prepare_transport_pacing_"
    "physical_d2_20260729_v1.sh"
)
CONTRACT_FILE = Path(__file__).name
TERMINALIZATION_FILE = (
    "h3_n2_stage2d9r_g3r_executor_terminalization_repair_20260729_v1.py"
)
PACING_FILE = (
    "h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1.py"
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_flat_name(value: object, code: str) -> str:
    require(isinstance(value, str) and bool(value), code)
    pure = PurePosixPath(value)
    require(
        not pure.is_absolute()
        and len(pure.parts) == 1
        and pure.name == value
        and ".." not in pure.parts,
        code,
    )
    return value


def _load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def _parse_sums(path: Path) -> dict[str, str]:
    require(path.is_file() and not path.is_symlink(), "PACKAGE_SUMS_INVALID")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(
            len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None,
            "PACKAGE_SUMS_INVALID",
        )
        name = _safe_flat_name(parts[1], "PACKAGE_SUMS_UNSAFE")
        require(name not in result and name != SUMS_FILE, "PACKAGE_SUMS_DUPLICATE")
        result[name] = parts[0]
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
                "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-"
                "pacing-execution-package-set/1"
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
        "execution_closure_policy_version": 3,
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
        "execution_closure_policy_version": 3,
    }
    for key, expected in exact.items():
        require(manifest.get(key) == expected, "EXECUTION_CLOSURE_" + key.upper())
    entries = manifest.get("files")
    require(isinstance(entries, list) and bool(entries), "EXECUTION_CLOSURE_FILES")
    observed: dict[str, str] = {}
    for entry in entries:
        require(isinstance(entry, dict), "EXECUTION_CLOSURE_ENTRY")
        name = _safe_flat_name(entry.get("name"), "EXECUTION_CLOSURE_NAME")
        digest = entry.get("sha256")
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            "EXECUTION_CLOSURE_DIGEST",
        )
        require(name not in observed and name not in CONTROL_FILES, "EXECUTION_CLOSURE_DUPLICATE")
        observed[name] = digest
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name not in CONTROL_FILES
    }
    require(set(observed) == actual, "EXECUTION_CLOSURE_COVERAGE_MISMATCH")
    for name, digest in observed.items():
        require(sha256_file(root / name) == digest, "EXECUTION_CLOSURE_FILE_MISMATCH")
    manifest["execution_closure_sha256"] = supplied
    return manifest


def validate_execution_package(root: Path) -> dict[str, Any]:
    sums = verify_sums_tree(root)
    closure = validate_execution_closure(root)
    binding = _load_json(root / PACKAGE_BINDING_FILE, "PACKAGE_BINDING_INVALID")
    package_sha = package_set_digest(root)
    exact = {
        "schema": PACKAGE_BINDING_SCHEMA,
        "state": "FROZEN_UNAUTHORIZED_D2_11_PACED_TRANSPORT_PACKAGE",
        "decision_id": DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 3,
        "execution_closure_sha256": closure["execution_closure_sha256"],
        "execution_package_sha256": package_sha,
        "pr205_artifact_id": PR205_ARTIFACT_ID,
        "pr205_artifact_sha256": PR205_ARTIFACT_SHA256,
        "pr205_execution_package_reuse_permitted": False,
        "pr205_execution_closure_reuse_permitted": False,
        "pr206_artifact_id": PR206_ARTIFACT_ID,
        "pr206_artifact_sha256": PR206_ARTIFACT_SHA256,
        "terminalization_repair_sha256": TERMINALIZATION_REPAIR_SHA256,
        "pr207_artifact_id": PR207_ARTIFACT_ID,
        "pr207_artifact_sha256": PR207_ARTIFACT_SHA256,
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
        TERMINALIZATION_FILE: TERMINALIZATION_REPAIR_SHA256,
        PACING_FILE: PACING_REPAIR_SHA256,
    }
    for name, expected in files.items():
        require(
            isinstance(expected, str)
            and HEX64.fullmatch(expected) is not None
            and name in sums
            and sums[name] == expected,
            "PACKAGE_ENTRYPOINT_BINDING_MISMATCH",
        )
    require(
        D2_10_REQUEST_BINDING_SHA256
        not in {
            binding.get("execution_package_sha256"),
            binding.get("execution_closure_sha256"),
        },
        "D2_10_BINDING_REUSED",
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
        "execution_closure_policy_version": 3,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
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
        "predecessor_request_id": D2_10_ID,
        "predecessor_status": "CONSUMED_FAILED",
        "predecessor_terminalization_state": "FORENSIC_TERMINAL_CLOSED",
        "predecessor_primary_failure_code": "PREPARE_RESULT_TIMEOUT",
        "predecessor_secondary_failure_code": "KeyError",
        "predecessor_prepare_count": 1,
        "predecessor_verify_count": 0,
        "predecessor_locked_recovery_attempted": True,
        "predecessor_locked_recovery_outcome": "UNKNOWN",
        "predecessor_terminal_result_sha256": D2_10_TERMINAL_RESULT_SHA256,
        "predecessor_terminal_marker_sha256": D2_10_TERMINAL_MARKER_SHA256,
        "predecessor_replay_permitted": False,
        "predecessor_automatic_retry_permitted": False,
        "predecessor_request_reuse_permitted": False,
        "predecessor_authorization_reuse_permitted": False,
        "predecessor_execution_package_reuse_permitted": False,
        "predecessor_execution_closure_reuse_permitted": False,
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
        value["request_binding_sha256"] != D2_10_REQUEST_BINDING_SHA256,
        "D2_10_REQUEST_REUSED",
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
        "terminalization_repair_sha256": TERMINALIZATION_REPAIR_SHA256,
        "pacing_repair_sha256": PACING_REPAIR_SHA256,
        "paced_chunk_bytes": PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": INTER_CHUNK_DELAY_MS,
        "predecessor_request_id": D2_10_ID,
        "predecessor_terminal_result_sha256": D2_10_TERMINAL_RESULT_SHA256,
        "predecessor_terminal_marker_sha256": D2_10_TERMINAL_MARKER_SHA256,
        "predecessor_locked_recovery_outcome": "UNKNOWN",
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
    require(supplied != D2_10_AUTHORIZATION_RECORD_SHA256, "D2_10_AUTHORIZATION_REUSED")
    return authorization


def validate_repository_audit(value: Mapping[str, Any]) -> None:
    require(
        value.get("repository_head_role") == "AUDIT_ONLY"
        and value.get("repository_head_enforced") is False,
        "REPOSITORY_HEAD_ROLE_INVALID",
    )
