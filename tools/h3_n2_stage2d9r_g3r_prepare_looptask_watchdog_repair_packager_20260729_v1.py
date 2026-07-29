#!/usr/bin/env python3
"""Build the public review Artifact for the D2-09 loopTask watchdog repair."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Any

import h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_contract_20260729_v1 as contract

REVIEW_SCHEMA = "gh.h3.n2.stage2d9r-g3r-prepare-looptask-watchdog-repair-review/1"
SOURCE_DATE_EPOCH = 1785196800
SOURCE_FILES = (
    ".github/workflows/h3-n2-stage2d9r-g3r-prepare-looptask-watchdog-root-cause-firmware-repair-ci-v1.yml",
    "docs/decisions/h3-n2-stage2d9r-g3r-prepare-looptask-watchdog-root-cause-firmware-repair-20260729-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-prepare-looptask-watchdog-root-cause-firmware-repair-contract-20260729-v1.md",
    "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3r_tls_prepare/greenhouse_profile_isolated_device_g3r_watchdog_repaired_20260729_v1.yml",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/__init__.py",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_executor_20260723_v1.h",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.h",
    "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.cpp",
    "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_contract_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_build_lane_20260729_v1.sh",
    "tools/h3_n2_stage2d9r_g3r_prepare_looptask_watchdog_repair_packager_20260729_v1.py",
    "tools/h3_n2_stage2d9r_g3r_task_watchdog_parser_20260729_v1.py",
)
FINAL_FILES = (
    "SHA256SUMS",
    "final-execution-binding.json",
    "immutable-freeze-manifest.json",
    "immutable-recovery-freeze-manifest.json",
    "stage2d9r-g3r-repaired-immutable-payload-v1.tar",
    "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar",
)
OLD_SYMBOLICATION_FILES = (
    "SHA256SUMS",
    "addr2line.txt",
    "firmware.elf",
    "firmware.map",
    "nearby-symbols.txt",
    "symbolication.json",
)
NEW_DEBUG_FILES = (
    "DEBUG_SHA256SUMS",
    "firmware.elf",
    "firmware.map",
    "loop-task-watchdog-repair-build-evidence.json",
)


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def copy_file(source: Path, destination: Path, mode: int = 0o600) -> None:
    require(source.is_file() and not source.is_symlink(), "SOURCE_FILE_INVALID")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, destination)
    os.chmod(destination, mode)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def write_sums(root: Path) -> None:
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        name = path.relative_to(root).as_posix()
        entries.append((name, sha256_file(path)))
    (root / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in entries),
        encoding="utf-8",
    )
    os.chmod(root / "SHA256SUMS", 0o600)


def deterministic_tar(root: Path, output: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path == output:
                continue
            name = path.relative_to(root).as_posix()
            pure = PurePosixPath(name)
            require(not pure.is_absolute() and ".." not in pure.parts, "TAR_MEMBER_UNSAFE")
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    output.write_bytes(buffer.getvalue())
    os.chmod(output, 0o600)


def build(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve(strict=True)
    old_root = args.old_symbolication_root.resolve(strict=True)
    final_root = args.final_freeze_root.resolve(strict=True)
    debug_root = args.new_debug_root.resolve(strict=True)
    output = args.output.resolve(strict=False)
    require(contract.HEX40.fullmatch(args.source_sha) is not None, "SOURCE_SHA_INVALID")
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)

    old_symbolication = contract.validate_old_symbolication(old_root)
    new_build = contract.validate_repaired_build(debug_root, source_sha=args.source_sha)

    for name in FINAL_FILES:
        copy_file(final_root / name, output / "repaired-freeze" / name)
    for name in OLD_SYMBOLICATION_FILES:
        copy_file(old_root / name, output / "old-symbolication" / name)
    for name in NEW_DEBUG_FILES:
        copy_file(debug_root / name, output / "new-debug" / name)
    for relative in SOURCE_FILES:
        copy_file(
            source_root / relative,
            output / "source" / relative,
            0o700 if relative.endswith(".sh") else 0o600,
        )

    final_manifest = json.loads(
        (final_root / "immutable-recovery-freeze-manifest.json").read_text(encoding="utf-8")
    )
    new_immutable = sha256_file(
        final_root / "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
    )
    new_recovery = sha256_file(
        final_root / "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
    )
    require(new_immutable != contract.OLD_IMMUTABLE_TAR_SHA256, "OLD_IMMUTABLE_REUSED")
    require(new_recovery != contract.OLD_RECOVERY_TAR_SHA256, "OLD_RECOVERY_REUSED")

    review: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "state": "LOOPTASK_WATCHDOG_ROOT_CAUSE_REPAIRED_SOURCE_BUILD_ONLY",
        "decision_id": contract.DECISION_ID,
        "source_sha": args.source_sha,
        "base_pr": 203,
        "base_head_sha": "9f6d39ad48de15c21550cdb17fec6abe794896e0",
        "predecessor_request_id": contract.D2_09_ID,
        "predecessor_status": contract.D2_09_STATUS,
        "predecessor_failure_code": contract.D2_09_FAILURE_CODE,
        "predecessor_terminal_state": contract.D2_09_TERMINAL_STATE,
        "predecessor_terminal_result_sha256": contract.D2_09_TERMINAL_RESULT_SHA256,
        "predecessor_realtime_serial_sha256": contract.D2_09_REALTIME_SERIAL_SHA256,
        "predecessor_reset_signatures_sha256": contract.D2_09_RESET_SIGNATURES_SHA256,
        "predecessor_realtime_timeline_sha256": contract.D2_09_REALTIME_TIMELINE_SHA256,
        "predecessor_reset_loop_count": contract.D2_09_RESET_LOOP_COUNT,
        "root_cause": "BLOCKING_STDIN_READ_IN_ESPHOME_LOOPTASK",
        "old_mepc": contract.OLD_MEPC,
        "old_ra": contract.OLD_RA,
        "old_saved_pc": contract.OLD_SAVED_PC,
        "old_mepc_symbol": contract.EXPECTED_MEPC_SYMBOL,
        "old_application_sha256": contract.OLD_APPLICATION_SHA256,
        "old_elf_sha256": contract.OLD_ELF_SHA256,
        "old_map_sha256": contract.OLD_MAP_SHA256,
        "stdin_nonblocking_repair": True,
        "watchdog_disabled": False,
        "watchdog_timeout_extended": False,
        "new_application_sha256": new_build["record"]["firmware"]["application_sha256"],
        "new_immutable_tar_sha256": new_immutable,
        "new_recovery_tar_sha256": new_recovery,
        "old_immutable_tar_sha256": contract.OLD_IMMUTABLE_TAR_SHA256,
        "old_recovery_tar_sha256": contract.OLD_RECOVERY_TAR_SHA256,
        "old_payloads_reused": False,
        "new_final_execution_binding": final_manifest["final_execution_binding"],
        "new_final_execution_binding_sha256": final_manifest["final_execution_binding_sha256"],
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "broker_operation": False,
        "prepare_operation": False,
        "verify_operation": False,
        "activate_operation": False,
        "cleanup_operation": False,
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
    }
    review["review_binding_sha256"] = canonical_sha256(review)
    write_json(output / "PREPARE_LOOPTASK_WATCHDOG_REPAIR_REVIEW.json", review)

    tar_path = output / "stage2d9r-g3r-prepare-looptask-watchdog-repair-review-v1.tar"
    deterministic_tar(output, tar_path)
    write_sums(output)

    print(json.dumps({
        "status": "PACKAGE_BUILT",
        "review_binding_sha256": review["review_binding_sha256"],
        "new_immutable_tar_sha256": new_immutable,
        "new_recovery_tar_sha256": new_recovery,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
    }, sort_keys=True))


def main() -> int:
    value = argparse.ArgumentParser()
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--source-sha", required=True)
    value.add_argument("--old-symbolication-root", type=Path, required=True)
    value.add_argument("--final-freeze-root", type=Path, required=True)
    value.add_argument("--new-debug-root", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    build(value.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
