#!/usr/bin/env python3
"""Fail-closed contract for the D2-09 loopTask watchdog firmware repair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Any

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-PREPARE-LOOPTASK-WATCHDOG-ROOT-CAUSE-AND-FIRMWARE-REPAIR-20260729-01"
D2_09_ID = "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-09"
D2_09_STATUS = "CONSUMED_FAILED"
D2_09_FAILURE_CODE = "PREPARE_RESULT_TIMEOUT"
D2_09_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
D2_09_AUTHORIZATION_RECORD_SHA256 = "e1755341cdc879762d22374f7f98f23b43fdba352e0c99df46ade4e49a5cb2e7"
D2_09_TERMINAL_RESULT_SHA256 = "0642e620b463b2f86f3a7e4ab42ad7f11cecf418fd09bf042c6f6002ed9b4a25"
D2_09_REALTIME_SERIAL_SHA256 = "5a7756b858d05364bbc00dfa29ee28e5c34a03e9b27e19cab34808e4af7e40c1"
D2_09_RESET_SIGNATURES_SHA256 = "9cc01d7fc021eca11bf675bd5e6e38eae8679492235fd929e5f772479a8a9311"
D2_09_REALTIME_TIMELINE_SHA256 = "af9f017de1e29d83f953fa97e8cfb834d834c5c320494ac601c6a2ecce3d9f07"
D2_09_RESET_LOOP_COUNT = 9
D2_09_POST_COMMAND_RESET_COUNT = 9
OLD_SOURCE_SHA = "8a6fdd7c74341448d275a4412e36b303d7c95e85"
OLD_APPLICATION_SHA256 = "383463b5a3f4481cf41f8f185c7649a80fd62baf1a6836a69ac3c5047b75950d"
OLD_IMMUTABLE_TAR_SHA256 = "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea"
OLD_RECOVERY_TAR_SHA256 = "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f"
OLD_ELF_SHA256 = "5673f77afb012a9a784e583cea44625f29c61be76063f24080d54f5de1d4a163"
OLD_MAP_SHA256 = "07a7c2c968d0c7e42646a42163509ff36faa5286cd26dced7a1eb4deca5bcf45"
OLD_MEPC = "0x4080211c"
OLD_RA = "0x4080210a"
OLD_SAVED_PC = "0x4001975a"
EXPECTED_MEPC_SYMBOL = "esp_cpu_wait_for_intr"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    require(isinstance(value, dict), code)
    return value


def validate_old_symbolication(root: Path) -> dict[str, Any]:
    value = load_json(root / "symbolication.json", "OLD_SYMBOLICATION_INVALID")
    require(value.get("old_source_sha") == OLD_SOURCE_SHA, "OLD_SYMBOLICATION_SOURCE_MISMATCH")
    require(value.get("old_application_sha256") == OLD_APPLICATION_SHA256,
            "OLD_SYMBOLICATION_APPLICATION_MISMATCH")
    require(value.get("old_elf_sha256") == OLD_ELF_SHA256, "OLD_SYMBOLICATION_ELF_MISMATCH")
    require(value.get("old_map_sha256") == OLD_MAP_SHA256, "OLD_SYMBOLICATION_MAP_MISMATCH")
    require(value.get("addresses") == [OLD_MEPC, OLD_RA, OLD_SAVED_PC],
            "OLD_SYMBOLICATION_ADDRESS_MISMATCH")
    lines = value.get("addr2line")
    require(isinstance(lines, list), "OLD_SYMBOLICATION_LINES_MISSING")
    require(lines.count(EXPECTED_MEPC_SYMBOL) >= 2, "OLD_SYMBOLICATION_WAIT_SYMBOL_MISSING")
    require(any("esp_hw_support/cpu.c:64" in str(line) for line in lines),
            "OLD_SYMBOLICATION_MEPC_LINE_MISSING")
    require(any("esp_hw_support/cpu.c:57" in str(line) for line in lines),
            "OLD_SYMBOLICATION_RA_LINE_MISSING")
    require(value.get("board_operation") is False, "OLD_SYMBOLICATION_BOARD_BOUNDARY_EXPANDED")
    require(value.get("physical_authorization_created") is False,
            "OLD_SYMBOLICATION_AUTHORIZATION_BOUNDARY_EXPANDED")
    require(sha256_file(root / "firmware.elf") == OLD_ELF_SHA256,
            "OLD_SYMBOLICATION_ELF_FILE_MISMATCH")
    require(sha256_file(root / "firmware.map") == OLD_MAP_SHA256,
            "OLD_SYMBOLICATION_MAP_FILE_MISMATCH")
    return value


def tar_members(path: Path) -> set[str]:
    members: set[str] = set()
    with tarfile.open(path, "r") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            require(member.isfile(), "TAR_MEMBER_NOT_FILE")
            require(not pure.is_absolute() and ".." not in pure.parts, "TAR_MEMBER_UNSAFE")
            require(member.name not in members, "TAR_MEMBER_DUPLICATE")
            members.add(member.name)
    return members


def validate_repaired_build(root: Path, *, source_sha: str) -> dict[str, Any]:
    require(HEX40.fullmatch(source_sha) is not None, "REPAIRED_SOURCE_SHA_INVALID")
    record = load_json(root / "build-record.json", "REPAIRED_BUILD_RECORD_INVALID")
    evidence = load_json(
        root / "loop-task-watchdog-repair-build-evidence.json",
        "REPAIRED_BUILD_EVIDENCE_INVALID",
    )
    immutable = root / "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
    require(record.get("source_sha") == source_sha, "REPAIRED_BUILD_SOURCE_MISMATCH")
    application_sha = record.get("firmware", {}).get("application_sha256")
    require(isinstance(application_sha, str) and HEX64.fullmatch(application_sha) is not None,
            "REPAIRED_APPLICATION_SHA_INVALID")
    require(application_sha != OLD_APPLICATION_SHA256, "OLD_APPLICATION_REUSED")
    require(evidence.get("application_sha256") == application_sha,
            "REPAIRED_APPLICATION_EVIDENCE_MISMATCH")
    require(evidence.get("old_application_reused") is False, "OLD_APPLICATION_REUSE_FLAG_INVALID")
    require(evidence.get("old_immutable_tar_reused") is False, "OLD_IMMUTABLE_REUSE_FLAG_INVALID")
    require(evidence.get("stdin_nonblocking") is True, "NONBLOCKING_EVIDENCE_MISSING")
    require(evidence.get("watchdog_disabled") is False, "WATCHDOG_DISABLE_NOT_ALLOWED")
    require(evidence.get("watchdog_timeout_extended") is False, "WATCHDOG_EXTENSION_NOT_ALLOWED")
    require(evidence.get("elf_retained") is True and evidence.get("map_retained") is True,
            "DEBUG_ARTIFACT_RETENTION_MISSING")
    require(sha256_file(immutable) != OLD_IMMUTABLE_TAR_SHA256, "OLD_IMMUTABLE_TAR_REUSED")
    require(tar_members(immutable) == {
        "SHA256SUMS", "application.bin", "bootloader.bin", "firmware-payload.json",
        "merged-image.bin", "partition-table.bin",
    }, "REPAIRED_IMMUTABLE_INVENTORY_MISMATCH")
    require((root / "firmware.elf").is_file() and (root / "firmware.map").is_file(),
            "REPAIRED_DEBUG_ARTIFACT_MISSING")
    return {"record": record, "evidence": evidence}


def source_boundary() -> dict[str, Any]:
    return {
        "status": "SOURCE_BUILD_ONLY_LOOPTASK_WATCHDOG_REPAIR_CONTRACT",
        "decision_id": DECISION_ID,
        "d2_request_id": D2_09_ID,
        "predecessor_status": D2_09_STATUS,
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
    }


if __name__ == "__main__":
    print(json.dumps(source_boundary(), sort_keys=True))
