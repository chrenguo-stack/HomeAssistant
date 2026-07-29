#!/usr/bin/env python3
"""Contract for the watchdog-repaired payload execution closure.

Repository HEAD is audit evidence only.  The exact runtime closure, repaired
payload bytes, final execution binding, request identity, and one-shot
authorization remain blocking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-WATCHDOG-REPAIRED-PAYLOAD-"
    "EXECUTION-BINDING-20260729-01"
)
STAGE = "H3/N2 Stage 2D-9R G3R watchdog-repaired payload execution binding"
REQUEST_10_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-"
    "PHYSICAL-20260729-10"
)
REQUEST_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-request/1"
)
AUTH_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-authorization/1"
)
RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-result/1"
)
MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-marker/1"
)
PRE_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-preclaim-result/1"
)
PRE_MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-preclaim-marker/1"
)
PACKAGE_BINDING_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-execution-package/1"
)
CLOSURE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-execution-closure-manifest/1"

BASE_PR = 204
BASE_BRANCH = (
    "fix/h3-n2-stage2d9r-g3r-prepare-looptask-watchdog-"
    "firmware-repair-20260729-v1"
)
BASE_HEAD_SHA = "8d76634adb171c6492e51a5ebd855bcd52bcf073"
MAIN_SHA_AT_BINDING = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
README_BLOB_SHA_AT_BINDING = "23ccbd3d31c0333924af6d4791f4dde24d1b1b89"

PR203_HEAD = "9f6d39ad48de15c21550cdb17fec6abe794896e0"
PR203_ARTIFACT_ID = 8713021622
PR203_ARTIFACT_SHA256 = (
    "ac4794f11c5195ce4a3bfbcefdb026453c0b94291c79692d43ca2bd2e06e34e4"
)
PR203_REVIEW_BINDING_SHA256 = (
    "b30d5fd37c8efdc910120592dd5eaee78178c5b6ebe3d1714ce2ad396d730eaa"
)
PR203_EXECUTION_PACKAGE_SHA256 = (
    "65f6e765f5ae130da8f8452c19ee59fec84a7d0a7f6330d84f082d471708f356"
)
PR203_EXECUTION_CLOSURE_SHA256 = (
    "d74b1b1995d35d76075b52c68f2e61f7ec67306a1615c01bfdcbaa6679d44275"
)

PR204_ARTIFACT_ID = 8716016864
PR204_ARTIFACT_SHA256 = (
    "71ee1c2bfe951e1e4db833ad4efb96e436ba6c6a0729d52caf641b2294f2d456"
)
PR204_REVIEW_BINDING_SHA256 = (
    "4da1f873ef0ba0680c56b6782e40dfa48f583e33105b9a5d8f76fce9ae75e74e"
)
IMMUTABLE_BUILD_BINDING = "4051f5d541898cef742f35aeec757e7fc479f383"
APPLICATION_SHA256 = "d60b2e0ccf5013629ee7b7aea017a06387e540380dbf2522415c8876a4cf3032"
IMMUTABLE_PAYLOAD_TAR_SHA256 = (
    "ed8e4c673e89107750743702c7e4f4cb9bfada9c53519edcc4ee31719045b2de"
)
RECOVERY_PAYLOAD_TAR_SHA256 = (
    "9a1b75a39edc4b47d7e54417bdb1e6a07671f37a9100e7f4364e63383e11eeb2"
)
IMMUTABLE_MERGED_IMAGE_SHA256 = (
    "d984c0d7cef9a54a543912d32fd0ceb1e32ecbc0bab7a98a94732531160934e3"
)
RECOVERY_DESCRIPTOR_SHA256 = (
    "ef38564bac785172efbc6d60488bdafb095a2c8699e23e38e0f91291c50610b9"
)
FINAL_EXECUTION_BINDING = "307fcc23fd606afe9898a7879f2898b012c4bbe5"
FINAL_EXECUTION_BINDING_SHA256 = (
    "307fcc23fd606afe9898a7879f2898b012c4bbe5d6c86d8b950a0455ad68789b"
)
FINAL_EXECUTION_BINDING_FILE_SHA256 = (
    "d2f21d687dbe348b4abeba35c4f106b9b19aebe0c3eee7c149b565dd75a432ad"
)
IMMUTABLE_FREEZE_MANIFEST_SHA256 = (
    "51b0c94ccdcdc1d451808b50d8f303e1edd5cfa01f1c2fccbf19273c6ca2bed2"
)
RECOVERY_FREEZE_MANIFEST_SHA256 = (
    "6c79206d796dfc3c5dae9e5bc82a6e998bde821183399b9cabe101c445574924"
)

OLD_IMMUTABLE_PAYLOAD_TAR_SHA256 = (
    "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
)
OLD_RECOVERY_PAYLOAD_TAR_SHA256 = (
    "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
)
OLD_FINAL_EXECUTION_BINDING = "387602804793c7ab110817d56aa4c26114632bde"
OLD_FINAL_EXECUTION_BINDING_SHA256 = (
    "387602804793c7ab110817d56aa4c26114632bde31050e95847833f98d83b6c1"
)

D2_09_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-"
    "PHYSICAL-20260729-09"
)
D2_09_STATUS = "CONSUMED_FAILED"
D2_09_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
D2_09_FAILURE_CODE = "PREPARE_RESULT_TIMEOUT"
D2_09_AUTHORIZATION_SHA256 = (
    "e1755341cdc879762d22374f7f98f23b43fdba352e0c99df46ade4e49a5cb2e7"
)
D2_09_TERMINAL_RESULT_SHA256 = (
    "0642e620b463b2f86f3a7e4ab42ad7f11cecf418fd09bf042c6f6002ed9b4a25"
)
D2_09_REALTIME_SERIAL_SHA256 = (
    "5a7756b858d05364bbc00dfa29ee28e5c34a03e9b27e19cab34808e4af7e40c1"
)
D2_09_RESET_SIGNATURES_SHA256 = (
    "9cc01d7fc021eca11bf675bd5e6e38eae8679492235fd929e5f772479a8a9311"
)
D2_09_REALTIME_TIMELINE_SHA256 = (
    "af9f017de1e29d83f953fa97e8cfb834d834c5c320494ac601c6a2ecce3d9f07"
)

FINAL_BINDING_FILE = "final-execution-binding.json"
IMMUTABLE_MANIFEST_FILE = "immutable-freeze-manifest.json"
RECOVERY_MANIFEST_FILE = "immutable-recovery-freeze-manifest.json"
IMMUTABLE_TAR_FILE = "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
RECOVERY_TAR_FILE = "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
CLOSURE_MANIFEST_FILE = "EXECUTION_CLOSURE_MANIFEST.json"
PACKAGE_BINDING_FILE = "EXECUTION_PACKAGE_BINDING.json"
SUMS_FILE = "SHA256SUMS"
CONTROL_FILES = frozenset({CLOSURE_MANIFEST_FILE, PACKAGE_BINDING_FILE, SUMS_FILE})

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_flat_name(value: object, code: str) -> str:
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


def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def parse_sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError("PACKAGE_SUMS_INVALID") from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        parts = line.split("  ", 1)
        require(
            len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None,
            "PACKAGE_SUMS_INVALID",
        )
        name = safe_flat_name(parts[1], "PACKAGE_SUMS_UNSAFE")
        require(name not in result and name != SUMS_FILE, "PACKAGE_SUMS_DUPLICATE")
        result[name] = parts[0]
    require(result, "PACKAGE_SUMS_EMPTY")
    return result


def verify_sums_tree(root: Path) -> dict[str, str]:
    require(root.is_dir() and not root.is_symlink(), "EXECUTION_PACKAGE_ROOT_INVALID")
    sums = parse_sums(root / SUMS_FILE)
    observed = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != SUMS_FILE
    }
    require(set(sums) == observed, "PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        target = root / name
        require(
            target.is_file() and not target.is_symlink(),
            "PACKAGE_FILE_INVALID",
        )
        require(sha256_file(target) == digest, "PACKAGE_DIGEST_MISMATCH")
    return sums


def package_set_digest(root: Path) -> str:
    entries = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name not in {SUMS_FILE, PACKAGE_BINDING_FILE}
    ]
    require(entries, "EXECUTION_PACKAGE_EMPTY")
    return canonical_sha256(
        {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-"
                "payload-execution-package-set/1"
            ),
            "files": entries,
        }
    )


def canonical_package_digest(root: Path) -> str:
    verify_sums_tree(root)
    return package_set_digest(root)


def build_execution_closure_manifest(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "EXECUTION_ROOT_INVALID")
    files = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name not in CONTROL_FILES
    ]
    require(files, "EXECUTION_CLOSURE_EMPTY")
    value: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA,
        "policy_version": 2,
        "execution_closure_role": "BLOCKING",
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "files": files,
    }
    value["execution_closure_sha256"] = canonical_sha256(value)
    return value


def validate_execution_closure(root: Path) -> dict[str, Any]:
    manifest = load_json(
        root / CLOSURE_MANIFEST_FILE, "EXECUTION_CLOSURE_MANIFEST_INVALID"
    )
    require(manifest.get("schema") == CLOSURE_SCHEMA, "EXECUTION_CLOSURE_SCHEMA_MISMATCH")
    supplied = manifest.get("execution_closure_sha256")
    without = dict(manifest)
    without.pop("execution_closure_sha256", None)
    require(supplied == canonical_sha256(without), "EXECUTION_CLOSURE_DIGEST_MISMATCH")
    require(
        isinstance(supplied, str) and HEX64.fullmatch(supplied) is not None,
        "EXECUTION_CLOSURE_DIGEST_INVALID",
    )
    require(manifest.get("policy_version") == 2, "EXECUTION_CLOSURE_POLICY_MISMATCH")
    require(
        manifest.get("execution_closure_role") == "BLOCKING",
        "EXECUTION_CLOSURE_ROLE_MISMATCH",
    )
    require(
        manifest.get("repository_head_role") == "AUDIT_ONLY",
        "REPOSITORY_HEAD_ROLE_MISMATCH",
    )
    require(
        manifest.get("repository_head_enforced") is False,
        "REPOSITORY_HEAD_MUST_NOT_BLOCK",
    )
    raw_files = manifest.get("files")
    require(isinstance(raw_files, list) and raw_files, "EXECUTION_CLOSURE_FILES_INVALID")
    expected: dict[str, str] = {}
    for item in raw_files:
        require(isinstance(item, dict), "EXECUTION_CLOSURE_FILE_ENTRY_INVALID")
        name = safe_flat_name(
            item.get("name"), "EXECUTION_CLOSURE_MEMBER_NAME_INVALID"
        )
        digest = item.get("sha256")
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            "EXECUTION_CLOSURE_MEMBER_DIGEST_INVALID",
        )
        require(
            name not in expected and name not in CONTROL_FILES,
            "EXECUTION_CLOSURE_MEMBER_DUPLICATE",
        )
        expected[name] = digest
    require(list(expected) == sorted(expected), "EXECUTION_CLOSURE_INVENTORY_NOT_SORTED")
    observed = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name not in CONTROL_FILES
    }
    require(set(expected) == observed, "EXECUTION_CLOSURE_INVENTORY_MISMATCH")
    for name, digest in expected.items():
        target = root / name
        require(
            target.is_file() and not target.is_symlink(),
            "EXECUTION_CLOSURE_MEMBER_INVALID",
        )
        require(
            sha256_file(target) == digest,
            "EXECUTION_CLOSURE_MEMBER_DIGEST_MISMATCH",
        )
    return manifest


def require_new_payload_digest(
    observed: str, expected: str, predecessor: str, role: str
) -> None:
    require(observed != predecessor, f"OLD_{role}_PAYLOAD_PERMANENTLY_REJECTED")
    require(observed == expected, f"{role}_PAYLOAD_DIGEST_MISMATCH")


def validate_final_execution_binding_value(
    value: dict[str, Any]
) -> dict[str, Any]:
    require(
        value.get("final_execution_binding") != OLD_FINAL_EXECUTION_BINDING,
        "OLD_FINAL_EXECUTION_BINDING_PERMANENTLY_REJECTED",
    )
    require(
        value.get("final_execution_binding_sha256")
        != OLD_FINAL_EXECUTION_BINDING_SHA256,
        "OLD_FINAL_EXECUTION_BINDING_PERMANENTLY_REJECTED",
    )
    require(
        value.get("final_execution_binding") == FINAL_EXECUTION_BINDING,
        "FINAL_EXECUTION_BINDING_MISMATCH",
    )
    require(
        value.get("final_execution_binding_sha256")
        == FINAL_EXECUTION_BINDING_SHA256,
        "FINAL_EXECUTION_BINDING_DIGEST_MISMATCH",
    )
    payload = value.get("payload")
    require(isinstance(payload, dict), "FINAL_EXECUTION_BINDING_PAYLOAD_INVALID")
    bindings = payload.get("bindings")
    require(isinstance(bindings, dict), "FINAL_EXECUTION_BINDINGS_INVALID")
    require(payload.get("source_sha") == BASE_HEAD_SHA, "FINAL_EXECUTION_SOURCE_MISMATCH")
    require(
        bindings.get("immutable_archive_sha256") == IMMUTABLE_PAYLOAD_TAR_SHA256,
        "FINAL_EXECUTION_IMMUTABLE_MISMATCH",
    )
    require(
        bindings.get("recovery_archive_sha256") == RECOVERY_PAYLOAD_TAR_SHA256,
        "FINAL_EXECUTION_RECOVERY_MISMATCH",
    )
    return value


def validate_final_execution_binding(path: Path) -> dict[str, Any]:
    require(
        sha256_file(path) == FINAL_EXECUTION_BINDING_FILE_SHA256,
        "FINAL_EXECUTION_BINDING_FILE_DIGEST_MISMATCH",
    )
    value = load_json(path, "FINAL_EXECUTION_BINDING_INVALID")
    return validate_final_execution_binding_value(value)


def validate_execution_package(root: Path) -> dict[str, Any]:
    package_digest = canonical_package_digest(root)
    closure = validate_execution_closure(root)
    binding = load_json(root / PACKAGE_BINDING_FILE, "EXECUTION_PACKAGE_BINDING_INVALID")
    require(
        binding.get("schema") == PACKAGE_BINDING_SCHEMA,
        "EXECUTION_PACKAGE_BINDING_SCHEMA_MISMATCH",
    )
    exact = {
        "decision_id": DECISION_ID,
        "source_sha": binding.get("source_sha"),
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_package_build": README_BLOB_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 2,
        "execution_closure_sha256": closure["execution_closure_sha256"],
        "execution_package_sha256": package_digest,
        "upstream_pr203_artifact_id": PR203_ARTIFACT_ID,
        "upstream_pr203_artifact_sha256": PR203_ARTIFACT_SHA256,
        "watchdog_repair_artifact_id": PR204_ARTIFACT_ID,
        "watchdog_repair_artifact_sha256": PR204_ARTIFACT_SHA256,
        "watchdog_repair_review_binding_sha256": PR204_REVIEW_BINDING_SHA256,
        "immutable_build_binding": IMMUTABLE_BUILD_BINDING,
        "application_sha256": APPLICATION_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "upstream_execution_closure_sha256": PR203_EXECUTION_CLOSURE_SHA256,
        "upstream_execution_closure_reuse_permitted": False,
        "old_payload_reuse_permitted": False,
        "physical_request_authorized": False,
        "physical_authorization_created": False,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "EXECUTION_PACKAGE_" + key.upper() + "_MISMATCH")
    source_sha = binding.get("source_sha")
    require(
        isinstance(source_sha, str)
        and HEX40.fullmatch(source_sha) is not None
        and source_sha != BASE_HEAD_SHA,
        "EXECUTION_PACKAGE_SOURCE_SHA_INVALID",
    )
    required_files = {
        "execution_wrapper_sha256": (
            "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
            "physical_d2_wrapper_20260729_v1.py"
        ),
        "execution_launcher_sha256": (
            "run_stage2d9r_g3r_watchdog_repaired_payload_"
            "physical_d2_20260729_v1.sh"
        ),
        "execution_contract_sha256": (
            "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
            "execution_binding_contract_20260729_v1.py"
        ),
    }
    for key, name in required_files.items():
        require(
            binding.get(key) == sha256_file(root / name),
            "EXECUTION_PACKAGE_" + key.upper() + "_MISMATCH",
        )
    immutable_digest = sha256_file(root / IMMUTABLE_TAR_FILE)
    recovery_digest = sha256_file(root / RECOVERY_TAR_FILE)
    require_new_payload_digest(
        immutable_digest,
        IMMUTABLE_PAYLOAD_TAR_SHA256,
        OLD_IMMUTABLE_PAYLOAD_TAR_SHA256,
        "IMMUTABLE",
    )
    require_new_payload_digest(
        recovery_digest,
        RECOVERY_PAYLOAD_TAR_SHA256,
        OLD_RECOVERY_PAYLOAD_TAR_SHA256,
        "RECOVERY",
    )
    require(
        sha256_file(root / IMMUTABLE_MANIFEST_FILE)
        == IMMUTABLE_FREEZE_MANIFEST_SHA256,
        "IMMUTABLE_FREEZE_MANIFEST_DIGEST_MISMATCH",
    )
    require(
        sha256_file(root / RECOVERY_MANIFEST_FILE)
        == RECOVERY_FREEZE_MANIFEST_SHA256,
        "RECOVERY_FREEZE_MANIFEST_DIGEST_MISMATCH",
    )
    validate_final_execution_binding(root / FINAL_BINDING_FILE)
    return {
        "binding": binding,
        "closure": closure,
        "package_sha256": package_digest,
    }


def validate_repository_audit(value: Mapping[str, Any]) -> None:
    repository_head = value.get("repository_head_sha")
    require(
        isinstance(repository_head, str) and HEX40.fullmatch(repository_head) is not None,
        "REPOSITORY_HEAD_SHA_INVALID",
    )
    require(
        value.get("repository_head_role") == "AUDIT_ONLY",
        "REPOSITORY_HEAD_ROLE_INVALID",
    )
    require(
        value.get("repository_head_enforced") is False,
        "REPOSITORY_HEAD_ENFORCEMENT_INVALID",
    )
    drift = value.get("non_execution_drift_files")
    require(isinstance(drift, list) and len(drift) <= 256, "NON_EXECUTION_DRIFT_INVALID")
    for item in drift:
        require(isinstance(item, str) and bool(item), "NON_EXECUTION_DRIFT_PATH_INVALID")
        pure = PurePosixPath(item)
        require(
            not pure.is_absolute() and ".." not in pure.parts,
            "NON_EXECUTION_DRIFT_PATH_INVALID",
        )


def request_template(package_root: Path, *, source_sha: str) -> dict[str, Any]:
    require(
        HEX40.fullmatch(source_sha) is not None and source_sha != BASE_HEAD_SHA,
        "SOURCE_SHA_INVALID",
    )
    package = validate_execution_package(package_root)
    binding = package["binding"]
    value: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "state": "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_10_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_package_build": README_BLOB_SHA_AT_BINDING,
        "repository_head_sha": MAIN_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "non_execution_drift_files": ["README.md"],
        "upstream_pr203_artifact_id": PR203_ARTIFACT_ID,
        "upstream_pr203_artifact_sha256": PR203_ARTIFACT_SHA256,
        "watchdog_repair_artifact_id": PR204_ARTIFACT_ID,
        "watchdog_repair_artifact_sha256": PR204_ARTIFACT_SHA256,
        "watchdog_repair_review_binding_sha256": PR204_REVIEW_BINDING_SHA256,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 2,
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
        "execution_script_sha256": binding["execution_wrapper_sha256"],
        "immutable_build_binding": IMMUTABLE_BUILD_BINDING,
        "application_sha256": APPLICATION_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "old_immutable_payload_tar_sha256": OLD_IMMUTABLE_PAYLOAD_TAR_SHA256,
        "old_recovery_payload_tar_sha256": OLD_RECOVERY_PAYLOAD_TAR_SHA256,
        "old_final_execution_binding_sha256": OLD_FINAL_EXECUTION_BINDING_SHA256,
        "old_payload_reuse_permitted": False,
        "old_execution_closure_reuse_permitted": False,
        "predecessor_request_id": D2_09_ID,
        "predecessor_status": D2_09_STATUS,
        "predecessor_terminal_state": D2_09_TERMINAL_STATE,
        "predecessor_failure_code": D2_09_FAILURE_CODE,
        "predecessor_authorization_record_sha256": D2_09_AUTHORIZATION_SHA256,
        "predecessor_terminal_result_sha256": D2_09_TERMINAL_RESULT_SHA256,
        "predecessor_realtime_serial_sha256": D2_09_REALTIME_SERIAL_SHA256,
        "predecessor_reset_signatures_sha256": D2_09_RESET_SIGNATURES_SHA256,
        "predecessor_realtime_timeline_sha256": D2_09_REALTIME_TIMELINE_SHA256,
        "predecessor_prepare_count": 1,
        "predecessor_verify_count": 0,
        "predecessor_locked_recovery_succeeded": True,
        "predecessor_replay_permitted": False,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_max_count": 1,
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
        "authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_request_authorized": False,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "physical_execution_started": False,
    }
    value["request_binding_sha256"] = canonical_sha256(value)
    return value


def validate_physical_request(
    value: dict[str, Any], package_root: Path
) -> dict[str, Any]:
    package = validate_execution_package(package_root)
    binding = package["binding"]
    exact = {
        "schema": REQUEST_SCHEMA,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_10_ID,
        "source_sha": binding["source_sha"],
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_package_build": README_BLOB_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 2,
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_contract_sha256": binding["execution_contract_sha256"],
        "immutable_build_binding": IMMUTABLE_BUILD_BINDING,
        "application_sha256": APPLICATION_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "old_payload_reuse_permitted": False,
        "old_execution_closure_reuse_permitted": False,
        "predecessor_request_id": D2_09_ID,
        "predecessor_status": D2_09_STATUS,
        "predecessor_terminal_state": D2_09_TERMINAL_STATE,
        "predecessor_failure_code": D2_09_FAILURE_CODE,
        "predecessor_terminal_result_sha256": D2_09_TERMINAL_RESULT_SHA256,
        "predecessor_prepare_count": 1,
        "predecessor_verify_count": 0,
        "predecessor_locked_recovery_succeeded": True,
        "predecessor_replay_permitted": False,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_max_count": 1,
        "prepare_max_count": 1,
        "verify_max_count": 1,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "PHYSICAL_REQUEST_" + key.upper() + "_MISMATCH")
    require(
        value.get("state")
        == "FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION",
        "PHYSICAL_REQUEST_STATE_MISMATCH",
    )
    validate_repository_audit(value)
    for key in (
        "authorized",
        "authorization_created",
        "authorization_claimed",
        "authorization_consumed",
        "physical_request_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
        "board_operation",
        "usb_enumeration",
        "serial_operation",
        "esptool_operation",
        "flash_operation",
        "physical_nvs_operation",
        "network_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "physical_execution_started",
    ):
        require(value.get(key) is False, "PHYSICAL_REQUEST_BOUNDARY_" + key.upper())
    require(
        value.get("one_shot") is True
        and value.get("replay_permitted") is False
        and value.get("automatic_retry_permitted") is False,
        "PHYSICAL_REQUEST_RETRY_EXPANDED",
    )
    without = dict(value)
    observed = without.pop("request_binding_sha256", None)
    require(observed == canonical_sha256(without), "PHYSICAL_REQUEST_BINDING_MISMATCH")
    return value


def authorization_contract_required(
    request: dict[str, Any], package_root: Path
) -> dict[str, Any]:
    package = validate_execution_package(package_root)
    binding = package["binding"]
    return {
        "schema": AUTH_SCHEMA,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "d2_request_id": REQUEST_10_ID,
        "request_binding_sha256": request["request_binding_sha256"],
        "source_sha": binding["source_sha"],
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_package_build": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_package_build": README_BLOB_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_sha256": package["closure"]["execution_closure_sha256"],
        "execution_closure_role": "BLOCKING",
        "execution_closure_policy_version": 2,
        "execution_package_sha256": package["package_sha256"],
        "execution_wrapper_sha256": binding["execution_wrapper_sha256"],
        "execution_launcher_sha256": binding["execution_launcher_sha256"],
        "execution_script_sha256": binding["execution_wrapper_sha256"],
        "immutable_artifact_id": PR204_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": PR204_ARTIFACT_SHA256,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "immutable_merged_image_sha256": IMMUTABLE_MERGED_IMAGE_SHA256,
        "recovery_artifact_id": PR204_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": PR204_ARTIFACT_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "recovery_descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
        "final_execution_binding": FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": FINAL_EXECUTION_BINDING_SHA256,
        "build_binding": IMMUTABLE_BUILD_BINDING,
        "predecessor_request_id": D2_09_ID,
        "predecessor_status": D2_09_STATUS,
        "predecessor_terminal_state": D2_09_TERMINAL_STATE,
        "predecessor_failure_code": D2_09_FAILURE_CODE,
        "predecessor_terminal_result_sha256": D2_09_TERMINAL_RESULT_SHA256,
        "predecessor_replay_permitted": False,
        "old_payload_reuse_permitted": False,
        "old_execution_closure_reuse_permitted": False,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "prepare_max_count": 1,
        "verify_max_count": 1,
    }


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
    package_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_physical_request(request, package_root)
    for key, expected in authorization_contract_required(request, package_root).items():
        require(
            authorization.get(key) == expected,
            "AUTHORIZATION_" + key.upper() + "_MISMATCH",
        )
    validate_repository_audit(authorization)
    require(
        authorization.get("authorized") is True
        and authorization.get("one_shot") is True,
        "AUTHORIZATION_NOT_GRANTED",
    )
    require(
        authorization.get("replay_permitted") is False
        and authorization.get("automatic_retry_permitted") is False,
        "AUTHORIZATION_RETRY_EXPANDED",
    )
    require(
        authorization.get("locked_recovery_authorized") is True,
        "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED",
    )
    for key in (
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
    ):
        require(authorization.get(key) is False, "AUTHORIZATION_" + key.upper())
    for key in (
        "python_executable_sha256",
        "openssl_executable_sha256",
        "esptool_executable_sha256",
        "mosquitto_executable_sha256",
        "execution_marker_name_sha256",
        "board_identity_sha256",
        "serial_identity_sha256",
        "baseline_state_sha256",
        "private_package_sha256",
        "prepare_command_sha256",
        "verify_command_sha256",
        "candidate_digest_sha256",
        "ca_pem_sha256",
    ):
        digest = authorization.get(key)
        require(
            isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
            "AUTHORIZATION_" + key.upper() + "_INVALID",
        )
    issued = _utc(authorization.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = _utc(authorization.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(
        issued <= current <= expires and 0 < (expires - issued).total_seconds() <= 7200,
        "AUTHORIZATION_NOT_CURRENT",
    )
    without = dict(authorization)
    observed = without.pop("authorization_record_sha256", None)
    require(
        observed == canonical_sha256(without),
        "AUTHORIZATION_RECORD_DIGEST_MISMATCH",
    )
    return authorization


def source_contract(source_sha: str) -> dict[str, Any]:
    require(
        HEX40.fullmatch(source_sha) is not None and source_sha != BASE_HEAD_SHA,
        "SOURCE_SHA_INVALID",
    )
    return {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-"
            "execution-binding-source/1"
        ),
        "state": "SOURCE_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_branch": BASE_BRANCH,
        "base_head_sha": BASE_HEAD_SHA,
        "repository_head_sha_at_binding": MAIN_SHA_AT_BINDING,
        "readme_blob_sha_at_binding": README_BLOB_SHA_AT_BINDING,
        "repository_head_role": "AUDIT_ONLY",
        "repository_head_enforced": False,
        "execution_closure_role": "BLOCKING",
        "new_physical_d2_request_id": REQUEST_10_ID,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    if args.source_sha:
        value = source_contract(args.source_sha)
    else:
        value = {
            "status": "SOURCE_ONLY_WATCHDOG_REPAIRED_PAYLOAD_EXECUTION_BINDING",
            "decision_id": DECISION_ID,
            "d2_request_id": REQUEST_10_ID,
            "physical_request_created": False,
            "physical_authorization_created": False,
            "board_operation": False,
            "network_operation": False,
        }
    print(json.dumps(value, sort_keys=True))
