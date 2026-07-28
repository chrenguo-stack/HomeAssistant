#!/usr/bin/env python3
"""Source-only, fail-closed repair for the physical-D2 payload handoff."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
from typing import Any, Iterable

import h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1 as frozen

core = frozen.core
STAGE = "H3/N2 Stage 2D-9R G3R physical payload handoff repaired successor"
DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PHYSICAL-PAYLOAD-HANDOFF-REPAIR-20260728-01"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-PHYSICAL-PAYLOAD-HANDOFF-REPAIR-DRAFT-20260728-01"
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-consumed-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-physical-payload-handoff-repair-preclaim-marker/1"

IMMUTABLE_MEMBERS = frozenset({
    "SHA256SUMS", "application.bin", "bootloader.bin", "firmware-payload.json",
    "merged-image.bin", "partition-table.bin",
})
RECOVERY_MEMBERS = frozenset({
    "SHA256SUMS", "erased-test-partition.bin", "locked-recovery-descriptor.json",
    "locked-recovery-plan.json",
})
PARTITION_TABLE_SHA256 = "b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268"
_BOUND_TARS: tuple[Path, Path] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_path(path: Path, *, strict: bool) -> Path:
    return Path(os.path.realpath(os.path.expanduser(os.fspath(path)))).resolve(strict=strict)


def _member_name(name: str, code: str) -> str:
    pure = PurePosixPath(name)
    core.require(
        bool(name) and not pure.is_absolute() and len(pure.parts) == 1
        and pure.name == name and ".." not in pure.parts,
        code,
    )
    return name


def _sums(data: bytes, code: str) -> dict[str, str]:
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise core.ExecutionError(code) from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        parts = line.split("  ", 1)
        core.require(len(parts) == 2, code)
        digest, name = parts
        _member_name(name, code)
        core.require(core.HEX64.fullmatch(digest) is not None, code)
        core.require(name != "SHA256SUMS" and name not in result, code)
        result[name] = digest
    core.require(bool(result), code)
    return result


def _write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def verify_root(root: Path, expected: Iterable[str], code: str) -> None:
    expected_set = frozenset(expected)
    core.require(root.is_dir() and not root.is_symlink() and core.mode(root) == "0700", code)
    children = list(root.iterdir())
    core.require(all(p.is_file() and not p.is_symlink() for p in children), code)
    core.require({p.name for p in children} == expected_set, code)
    sums = _sums((root / "SHA256SUMS").read_bytes(), code)
    core.require(set(sums) == expected_set - {"SHA256SUMS"}, code)
    for name, digest in sums.items():
        target = root / name
        core.regular(target, "0600", code)
        core.require(sha256_file(target) == digest, code)


def safe_extract_payload(
    tar_path: Path,
    extract_root: Path,
    *,
    expected_tar_sha256: str,
    expected_members: Iterable[str],
    code: str,
) -> None:
    tar_path = normalized_path(tar_path, strict=True)
    extract_root = normalized_path(extract_root, strict=True)
    core.regular(tar_path, "0600", code)
    core.require(sha256_file(tar_path) == expected_tar_sha256, f"{code}_TAR_DIGEST")
    core.require(
        extract_root.is_dir() and not extract_root.is_symlink()
        and core.mode(extract_root) == "0700" and not any(extract_root.iterdir()),
        f"{code}_ROOT",
    )
    core.require(tar_path.parent != extract_root and extract_root not in tar_path.parents, code)
    expected = frozenset(expected_members)
    files: dict[str, bytes] = {}
    try:
        with tarfile.open(tar_path, "r:") as archive:
            members = archive.getmembers()
            names = [_member_name(member.name, code) for member in members]
            core.require(len(names) == len(set(names)), f"{code}_DUPLICATE_MEMBER")
            core.require(set(names) == expected, f"{code}_INVENTORY")
            for member in members:
                core.require(member.isfile(), f"{code}_NONREGULAR_MEMBER")
                handle = archive.extractfile(member)
                core.require(handle is not None, f"{code}_UNREADABLE_MEMBER")
                files[member.name] = handle.read()
    except (tarfile.TarError, OSError) as exc:
        raise core.ExecutionError(code) from exc
    for name in sorted(files):
        _write(extract_root / name, files[name])
    verify_root(extract_root, expected, f"{code}_CONTENT")


def prepare_payload_handoff(args: argparse.Namespace) -> None:
    global _BOUND_TARS
    package = normalized_path(args.package_root, strict=True)
    immutable_tar = normalized_path(args.immutable_payload_tar, strict=True)
    recovery_tar = normalized_path(args.recovery_payload_tar, strict=True)
    immutable_root = normalized_path(args.immutable_root, strict=True)
    recovery_root = normalized_path(args.recovery_root, strict=True)
    core.require(package.is_dir() and not package.is_symlink(), "PACKAGE_ROOT_INVALID")
    core.require(immutable_tar.parent == package, "IMMUTABLE_TAR_OUTSIDE_PACKAGE")
    core.require(recovery_tar.parent == package, "RECOVERY_TAR_OUTSIDE_PACKAGE")
    core.require(immutable_tar != recovery_tar and immutable_root != recovery_root, "PAYLOAD_ROLE_COLLISION")
    safe_extract_payload(
        immutable_tar, immutable_root,
        expected_tar_sha256=frozen.IMMUTABLE_PAYLOAD_TAR_SHA256,
        expected_members=IMMUTABLE_MEMBERS, code="IMMUTABLE_PAYLOAD_INVALID",
    )
    safe_extract_payload(
        recovery_tar, recovery_root,
        expected_tar_sha256=frozen.RECOVERY_PAYLOAD_TAR_SHA256,
        expected_members=RECOVERY_MEMBERS, code="RECOVERY_PAYLOAD_INVALID",
    )
    _BOUND_TARS = (immutable_tar, recovery_tar)
    args.package_root, args.immutable_root, args.recovery_root = package, immutable_root, recovery_root
    for name in ("authorization_record", "home", "state_root", "result_output"):
        setattr(args, name, normalized_path(getattr(args, name), strict=False))


def validate_public_inputs(immutable_root: Path, recovery_root: Path) -> tuple[Path, Path]:
    core.require(_BOUND_TARS is not None, "PAYLOAD_TARS_NOT_BOUND")
    immutable_tar, recovery_tar = _BOUND_TARS
    core.require(sha256_file(immutable_tar) == frozen.IMMUTABLE_PAYLOAD_TAR_SHA256, "IMMUTABLE_PAYLOAD_DIGEST_MISMATCH")
    core.require(sha256_file(recovery_tar) == frozen.RECOVERY_PAYLOAD_TAR_SHA256, "RECOVERY_PAYLOAD_DIGEST_MISMATCH")
    verify_root(immutable_root, IMMUTABLE_MEMBERS, "IMMUTABLE_PAYLOAD_CONTENT_INVALID")
    verify_root(recovery_root, RECOVERY_MEMBERS, "RECOVERY_PAYLOAD_CONTENT_INVALID")
    firmware_descriptor_path = immutable_root / "firmware-payload.json"
    try:
        firmware_descriptor = json.loads(firmware_descriptor_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise core.ExecutionError("FIRMWARE_PAYLOAD_DESCRIPTOR_INVALID") from exc
    core.require(isinstance(firmware_descriptor, dict), "FIRMWARE_PAYLOAD_DESCRIPTOR_INVALID")
    merged = immutable_root / "merged-image.bin"
    partition = immutable_root / "partition-table.bin"
    erased = recovery_root / "erased-test-partition.bin"
    descriptor = recovery_root / "locked-recovery-descriptor.json"
    core.require(sha256_file(merged) == frozen.IMMUTABLE_MERGED_SHA256, "IMMUTABLE_MERGED_IMAGE_DIGEST_MISMATCH")
    core.require(sha256_file(partition) == PARTITION_TABLE_SHA256, "IMMUTABLE_PARTITION_TABLE_DIGEST_MISMATCH")
    core.require(erased.stat().st_size == frozen.TEST_PARTITION_SIZE, "RECOVERY_ERASED_IMAGE_SIZE_MISMATCH")
    core.require(sha256_file(erased) == frozen.ERASED_SHA256, "RECOVERY_ERASED_IMAGE_DIGEST_MISMATCH")
    core.require(sha256_file(descriptor) == frozen.RECOVERY_DESCRIPTOR_SHA256, "RECOVERY_DESCRIPTOR_DIGEST_MISMATCH")
    return merged, erased


def configure_core() -> Any:
    configured = frozen.configure_core()
    configured.STAGE, configured.D2_REQUEST_ID = STAGE, D2_REQUEST_ID
    configured.AUTH_SCHEMA, configured.RESULT_SCHEMA, configured.MARKER_SCHEMA = AUTH_SCHEMA, RESULT_SCHEMA, MARKER_SCHEMA
    configured.validate_public_inputs, configured.__file__ = validate_public_inputs, __file__
    return configured


def parser() -> argparse.ArgumentParser:
    result = core.parser()
    result.add_argument("--immutable-payload-tar", type=Path, required=True)
    result.add_argument("--recovery-payload-tar", type=Path, required=True)
    return result


def marker_path(args: argparse.Namespace) -> Path:
    return normalized_path(args.state_root, strict=False) / (
        hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest() + ".json"
    )


def authorization_created(path: Path) -> bool:
    path = normalized_path(path, strict=False)
    return path.is_file() and not path.is_symlink()


def marker_was_claimed(marker: Path) -> bool:
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("schema") == MARKER_SCHEMA and value.get("status") in {
        "CLAIMED", "CONSUMED_PASS", "CONSUMED_FAILED",
    }


def _failure_code(exc: Exception) -> str:
    return str(exc.args[0]) if isinstance(exc, core.ExecutionError) and exc.args else type(exc).__name__


def write_preclaim_evidence(
    args: argparse.Namespace, code: str, *, replay_attempted: bool = False,
) -> dict[str, Any]:
    auth = normalized_path(args.authorization_record, strict=False)
    created = authorization_created(auth)
    marker = marker_path(args)
    value: dict[str, Any] = {
        "schema": PRE_RESULT_SCHEMA, "stage": STAGE, "d2_request_id": D2_REQUEST_ID,
        "status": "CONSUMED_FAILED" if created else "FAIL",
        "terminal_state": "CONSUMED_FAILED_PRECLAIM" if created else "PRECLAIM_REJECTED",
        "failure_code": code, "failure_stage": "PRECLAIM",
        "authorization_created": created, "authorization_claimed": marker_was_claimed(marker),
        "authorization_consumed": created,
        "authorization_record_sha256": sha256_file(auth) if created else None,
        "replay_attempted": replay_attempted, "one_shot": True,
        "replay_permitted": False, "automatic_retry_permitted": False,
        "board_operation": False, "usb_enumeration": False, "serial_operation": False,
        "esptool_operation": False, "flash_operation": False, "physical_nvs_operation": False,
        "network_operation": False, "broker_started": False, "prepare_executed": False,
        "verify_executed": False, "activate_executed": False, "cleanup_executed": False,
        "production_operation": False, "private_paths_included": False, "secret_values_included": False,
    }
    value["terminal_result_sha256"] = core.canonical_sha256(value)
    result = normalized_path(args.result_output, strict=False)
    if not result.exists():
        core.write_json_exclusive(result, value)
    if created and not marker.exists():
        core.write_json_exclusive(marker, {
            "schema": PRE_MARKER_SCHEMA, "stage": STAGE, "d2_request_id": D2_REQUEST_ID,
            "status": "CONSUMED_FAILED", "failure_code": code, "failure_stage": "PRECLAIM",
            "authorization_created": True, "authorization_claimed": False,
            "authorization_consumed": True,
            "authorization_record_sha256": value["authorization_record_sha256"],
            "terminal_result_sha256": value["terminal_result_sha256"], "one_shot": True,
            "replay_permitted": False, "automatic_retry_permitted": False,
            "private_paths_included": False, "secret_values_included": False,
        })
    return value


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION",
            "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
            "payload_handoff": "ORIGINAL_TAR_AND_EMPTY_EXTRACTION_ROOTS_SEPARATE",
            "authorization_created": False, "board_operation": False, "serial_operation": False,
            "esptool_operation": False, "flash_operation": False, "network_operation": False,
            "broker_started": False, "prepare_executed": False, "verify_executed": False,
            "replay_permitted": False, "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 0
    args = parser().parse_args()
    if authorization_created(args.authorization_record) and marker_path(args).exists():
        code = "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED"
        write_preclaim_evidence(args, code, replay_attempted=True)
        print(json.dumps({"status": "FAIL", "failure_code": code, "d2_request_id": D2_REQUEST_ID,
                          "replay_permitted": False, "automatic_retry_permitted": False}, sort_keys=True))
        return 2
    try:
        prepare_payload_handoff(args)
        result = configure_core().execute(args)
    except Exception as exc:
        code = _failure_code(exc)
        if not marker_path(args).exists():
            write_preclaim_evidence(args, code)
        print(json.dumps({"status": "FAIL", "failure_code": code, "d2_request_id": D2_REQUEST_ID,
                          "replay_permitted": False, "automatic_retry_permitted": False}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "d2_request_id": D2_REQUEST_ID,
                      "terminal_result_sha256": result["terminal_result_sha256"],
                      "replay_permitted": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
