#!/usr/bin/env python3
"""Public-only immutable and locked-recovery freeze pipeline for repaired Stage2D9R.

The module packages compiler outputs and deterministic review records only. It
does not enumerate USB/serial devices, invoke esptool, access a board, alter
Flash/NVS, open a network socket, start a Broker, or execute any device command.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain

STAGE = "H3/N2 Stage 2D-9R G3R repaired successor"
SOURCE_DATE_EPOCH = 1785196800
ESPHOME_VERSION = "2026.4.3"
PUBLIC_DIR_FILES = (
    "SHA256SUMS",
    "private-material-u1-result.jsonl",
    "public-descriptor.redacted.json",
    "u1-public-acceptance.json",
)
BINDING_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-immutable-build-binding/1"
BUILD_RECORD_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-immutable-clean-build/1"
FIRMWARE_PAYLOAD_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-immutable-firmware-payload/1"
IMMUTABLE_FREEZE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-immutable-freeze/1"
RECOVERY_BUILD_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-locked-recovery-clean-build/1"
RECOVERY_DESCRIPTOR_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-locked-recovery-descriptor/1"
RECOVERY_PLAN_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-locked-recovery-plan/1"
FINAL_FREEZE_SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-immutable-recovery-freeze/1"
IMMUTABLE_TAR_NAME = "stage2d9r-g3r-repaired-immutable-payload-v1.tar"
RECOVERY_TAR_NAME = "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OFFSETS = {"bootloader": 0x0, "partition_table": 0x8000, "application": 0x10000}
MAX_APPLICATION_END = chain.TEST_PARTITION_ADDRESS
ERASED_PARTITION = b"\xff" * chain.TEST_PARTITION_SIZE

FALSE_FLAGS = {
    "private_values_included": False,
    "private_paths_included": False,
    "secret_values_included": False,
    "authorization_created": False,
    "authorization_claimed": False,
    "authorization_consumed": False,
    "execution_authorized": False,
    "recovery_authorized": False,
    "board_operation_authorized": False,
    "usb_enumeration_authorized": False,
    "serial_operation_authorized": False,
    "esptool_operation_authorized": False,
    "flash_operation_authorized": False,
    "physical_nvs_operation_authorized": False,
    "network_operation_authorized": False,
    "broker_operation_authorized": False,
    "prepare_authorized": False,
    "verify_authorized": False,
    "activate_authorized": False,
    "cleanup_authorized": False,
    "ready_authorized": False,
    "merge_authorized": False,
    "release_authorized": False,
    "tag_authorized": False,
    "deployment_authorized": False,
}


class FreezeError(RuntimeError):
    """Fail-closed public freeze error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FreezeError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def pretty_json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def write_exclusive(path: Path, data: bytes, mode: int = 0o600) -> None:
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, mode)
    require(file_mode(path) == mode, "OUTPUT_MODE_MISMATCH")


def deterministic_tar(path: Path, files: Mapping[str, bytes]) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            pure = PurePosixPath(name)
            require(not pure.is_absolute() and ".." not in pure.parts, "TAR_MEMBER_INVALID")
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    write_exclusive(path, buffer.getvalue(), 0o600)


def tar_members(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with tarfile.open(path, "r") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            require(member.isfile(), "TAR_NON_FILE_MEMBER")
            require(not pure.is_absolute() and ".." not in pure.parts, "TAR_MEMBER_INVALID")
            require(member.name not in result, "TAR_DUPLICATE_MEMBER")
            handle = archive.extractfile(member)
            require(handle is not None, "TAR_MEMBER_UNREADABLE")
            result[member.name] = handle.read()
    return result


def reconstructed_public_archive_sha256(public_dir: Path) -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(PUBLIC_DIR_FILES):
            data = (public_dir / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return sha256_bytes(buffer.getvalue())


def validate_public_dir(public_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    public_dir = public_dir.resolve(strict=True)
    require(tuple(sorted(path.name for path in public_dir.iterdir())) == tuple(sorted(PUBLIC_DIR_FILES)),
            "PUBLIC_DIRECTORY_INVENTORY_MISMATCH")
    require(
        reconstructed_public_archive_sha256(public_dir)
        == "fe08ecca58f3742e3a126af9e62897d2d8cdff1e1e7187290e5c89ca1815cc59",
        "PUBLIC_ACCEPTANCE_ARCHIVE_DIGEST_MISMATCH",
    )
    sums_lines = (public_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    sums: dict[str, str] = {}
    for line in sums_lines:
        parts = line.split("  ", 1)
        require(len(parts) == 2, "PUBLIC_SUM_LINE_INVALID")
        digest, name = parts
        validate_sha256(digest, "PUBLIC_SUM_DIGEST_INVALID")
        require(name in PUBLIC_DIR_FILES and name != "SHA256SUMS", "PUBLIC_SUM_NAME_INVALID")
        sums[name] = digest
    require(set(sums) == set(PUBLIC_DIR_FILES) - {"SHA256SUMS"}, "PUBLIC_SUM_INVENTORY_MISMATCH")
    for name, expected in sums.items():
        require(sha256_file(public_dir / name) == expected, "PUBLIC_FILE_DIGEST_MISMATCH")

    result_lines = (public_dir / "private-material-u1-result.jsonl").read_text(encoding="utf-8").splitlines()
    require(len(result_lines) == 2, "U1_RESULT_LINE_COUNT_INVALID")
    require(
        result_lines[0] == "STAGE2D9R_REPAIRED_PRIVATE_MATERIAL_GENERATION=PASS",
        "U1_RESULT_MARKER_INVALID",
    )
    result = json.loads(result_lines[1])
    descriptor = json.loads((public_dir / "public-descriptor.redacted.json").read_text(encoding="utf-8"))
    acceptance = json.loads((public_dir / "u1-public-acceptance.json").read_text(encoding="utf-8"))
    require(isinstance(result, dict) and isinstance(descriptor, dict) and isinstance(acceptance, dict),
            "PUBLIC_JSON_NOT_OBJECT")
    require(result.get("status") == "PASS", "U1_RESULT_STATUS_INVALID")
    require(acceptance.get("state") == "U1_CONSUMED_PASS_PUBLIC_EVIDENCE_READY_FOR_IMMUTABLE_FREEZE",
            "U1_ACCEPTANCE_STATE_INVALID")
    require(acceptance.get("private_material_u1_consumed_pass") is True, "U1_ACCEPTANCE_NOT_PASS")
    require(acceptance.get("replay_permitted") is False, "U1_REPLAY_NOT_FALSE")
    require(acceptance.get("automatic_retry_permitted") is False, "U1_AUTO_RETRY_NOT_FALSE")
    require(descriptor.get("state") == "REPAIRED_SUCCESSOR_PRIVATE_MATERIAL_FROZEN",
            "PUBLIC_DESCRIPTOR_STATE_INVALID")
    require(descriptor.get("final_execution_binding_ready") is False,
            "PUBLIC_DESCRIPTOR_FINAL_BINDING_PREMATURE")
    expected_common = {
        "source_sha": "2ed70e3292e5b6522ac3a5bc279c94535cd7b784",
        "run_suffix": chain.RUN_SUFFIX,
        "candidate_digest_sha256": "73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15",
        "unlock_digest_sha256": "f1fe3ccbda78f069e6cf1e47ee4c3340878372f42fc24a21126884eb0c22df98",
        "ca_pem_sha256": "e9abe88df80f21311ea9ea4977b78f531380a37564490c1108fabeae8cc5bc5a",
        "private_package_sha256": "d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f",
        "broker_certificate_der_sha256": "19b599fdce443bf1ab59fac1c58b4da08d024c655502b4fda087151485ecce3c",
        "broker_spki_sha256": "a3ff45e66c18953bccb2d558e4a002208eadcf5fff9a8c05f6b77512c07a953b",
    }
    for key, expected in expected_common.items():
        for value in (result, descriptor, acceptance):
            require(value.get(key) == expected, f"PUBLIC_CROSS_BINDING_{key.upper()}_MISMATCH")
    require(
        acceptance.get("public_descriptor_sha256") == sha256_file(public_dir / "public-descriptor.redacted.json"),
        "PUBLIC_DESCRIPTOR_FILE_BINDING_MISMATCH",
    )
    require(
        acceptance.get("u1_result_sha256") == sha256_file(public_dir / "private-material-u1-result.jsonl"),
        "U1_RESULT_FILE_BINDING_MISMATCH",
    )
    for value in (result, descriptor, acceptance):
        for key in value:
            if key.endswith("_authorized") or key.endswith("_executed") or key in (
                "board_operation", "usb_enumeration", "serial_operation", "esptool_operation",
                "flash_operation", "physical_nvs_operation", "network_operation", "broker_started",
                "ready", "merge", "release", "tag", "deployment",
            ):
                require(value[key] is False, f"PUBLIC_BOUNDARY_EXPANDED_{key.upper()}")
        for privacy_key, code in (
            ("private_values_included", "PRIVATE_VALUES_INCLUDED"),
            ("private_paths_included", "PRIVATE_PATHS_INCLUDED"),
            ("secret_values_included", "SECRET_VALUES_INCLUDED"),
        ):
            if privacy_key in value:
                require(value[privacy_key] is False, code)
    return result, descriptor, acceptance


def validate_binding(binding_path: Path, descriptor: Mapping[str, Any], acceptance: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(binding_path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "BINDING_NOT_OBJECT")
    require(value.get("schema") == BINDING_SCHEMA, "BINDING_SCHEMA_MISMATCH")
    require(value.get("state") == "REPAIRED_IMMUTABLE_BUILD_INPUT_FROZEN", "BINDING_STATE_MISMATCH")
    payload = value.get("binding_payload")
    require(isinstance(payload, dict), "BINDING_PAYLOAD_MISSING")
    full = sha256_bytes(canonical_json_bytes(payload))
    require(value.get("immutable_build_binding_sha256") == full, "BINDING_FULL_DIGEST_MISMATCH")
    require(value.get("immutable_build_binding") == full[:40], "BINDING_SHORT_DIGEST_MISMATCH")
    validate_sha40(value["immutable_build_binding"], "BINDING_SHORT_INVALID")
    expected = {
        "base_source_sha": "922374a46b5ad6198623ab177efc5c313d4edff4",
        "material_source_sha": descriptor["source_sha"],
        "current_main_sha": chain.CURRENT_MAIN_SHA,
        "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
        "run_suffix": chain.RUN_SUFFIX,
        "u1_public_acceptance_sha256": sha256_bytes(pretty_json_bytes(acceptance)),
        "public_acceptance_archive_sha256": "fe08ecca58f3742e3a126af9e62897d2d8cdff1e1e7187290e5c89ca1815cc59",
        "public_descriptor_sha256": sha256_bytes(pretty_json_bytes(descriptor)),
        "private_package_sha256": descriptor["private_package_sha256"],
        "candidate_digest_sha256": descriptor["candidate_digest_sha256"],
        "unlock_digest_sha256": descriptor["unlock_digest_sha256"],
        "ca_pem_sha256": descriptor["ca_pem_sha256"],
        "broker_certificate_der_sha256": descriptor["broker_certificate_der_sha256"],
        "broker_spki_sha256": descriptor["broker_spki_sha256"],
        "prepare_command_sha256": descriptor["prepare_command_sha256"],
        "verify_command_sha256": descriptor["verify_command_sha256"],
        "protocol_sha256": descriptor["protocol_sha256"],
        "esphome_version": ESPHOME_VERSION,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "test_partition": {
            "label": chain.TEST_PARTITION_LABEL,
            "namespace": chain.TEST_PARTITION_NAMESPACE,
            "address": chain.TEST_PARTITION_ADDRESS,
            "size": chain.TEST_PARTITION_SIZE,
        },
    }
    for key, expected_value in expected.items():
        require(payload.get(key) == expected_value, f"BINDING_PAYLOAD_{key.upper()}_MISMATCH")
    for key, observed in FALSE_FLAGS.items():
        if key in value:
            require(value[key] is observed, f"BINDING_BOUNDARY_{key.upper()}_MISMATCH")
    return value


def locate(build_root: Path, names: tuple[str, ...]) -> Path:
    matches: list[Path] = []
    for name in names:
        matches.extend(path for path in build_root.rglob(name) if path.is_file())
    unique = sorted({path.resolve() for path in matches})
    require(len(unique) == 1, "BUILD_OUTPUT_COUNT_MISMATCH_" + "_".join(names))
    return unique[0]


def build_merged(parts: Mapping[str, bytes]) -> bytes:
    application_end = OFFSETS["application"] + len(parts["application"])
    require(application_end <= MAX_APPLICATION_END, "APPLICATION_OVERLAPS_TEST_PARTITION")
    end = max(OFFSETS[name] + len(data) for name, data in parts.items())
    merged = bytearray(b"\xff" * end)
    for name, data in parts.items():
        offset = OFFSETS[name]
        merged[offset:offset + len(data)] = data
    return bytes(merged)


def public_inputs(public_dir: Path, binding_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    result, descriptor, acceptance = validate_public_dir(public_dir)
    binding = validate_binding(binding_path, descriptor, acceptance)
    return result, descriptor, acceptance, binding


def build_immutable(args: argparse.Namespace) -> None:
    source_sha = validate_sha40(args.source_sha, "SOURCE_SHA_INVALID")
    for value, code in (
        (args.python_environment_sha256, "PYTHON_ENV_INVALID"),
        (args.openssl_environment_sha256, "OPENSSL_ENV_INVALID"),
        (args.esphome_environment_sha256, "ESPHOME_ENV_INVALID"),
        (args.workflow_sha256, "WORKFLOW_SHA_INVALID"),
    ):
        validate_sha256(value, code)
    result, descriptor, acceptance, binding = public_inputs(args.public_dir, args.binding)
    require(sha256_file(args.partition_csv) == "5afa0f77d5d815f00b14afbcc3b974037c5ba10c9bdcdcffa196b55e403b5cd8",
            "PARTITION_CSV_DIGEST_MISMATCH")
    host_controller_sha = sha256_file(args.host_controller)
    build_root = args.build_root.resolve(strict=True)
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "OUTPUT_DIR_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    parts = {
        "bootloader": locate(build_root, ("bootloader.bin",)).read_bytes(),
        "partition_table": locate(build_root, ("partitions.bin", "partition-table.bin")).read_bytes(),
        "application": locate(build_root, ("firmware.bin",)).read_bytes(),
    }
    for name, data in parts.items():
        require(bool(data), f"EMPTY_BUILD_OUTPUT_{name.upper()}")
    merged = build_merged(parts)
    firmware = {
        "bootloader_sha256": sha256_bytes(parts["bootloader"]),
        "bootloader_size": len(parts["bootloader"]),
        "partition_table_sha256": sha256_bytes(parts["partition_table"]),
        "partition_table_size": len(parts["partition_table"]),
        "application_sha256": sha256_bytes(parts["application"]),
        "application_size": len(parts["application"]),
        "merged_image_sha256": sha256_bytes(merged),
        "merged_image_size": len(merged),
        "flash_offsets": OFFSETS,
    }
    payload = {
        "schema": FIRMWARE_PAYLOAD_SCHEMA,
        "state": "REPAIRED_IMMUTABLE_CLEAN_BUILD_LOCKED",
        "stage": STAGE,
        "source_sha": source_sha,
        "immutable_build_binding": binding["immutable_build_binding"],
        "immutable_build_binding_sha256": binding["immutable_build_binding_sha256"],
        "esphome_version": ESPHOME_VERSION,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "python_environment_sha256": args.python_environment_sha256,
        "openssl_environment_sha256": args.openssl_environment_sha256,
        "esphome_environment_sha256": args.esphome_environment_sha256,
        "compile_workflow_sha256": args.workflow_sha256,
        "repaired_host_controller_sha256": host_controller_sha,
        "public_inputs": {
            "u1_result_sha256": acceptance["u1_result_sha256"],
            "u1_public_acceptance_sha256": sha256_file(args.public_dir / "u1-public-acceptance.json"),
            "public_descriptor_sha256": sha256_file(args.public_dir / "public-descriptor.redacted.json"),
            "private_package_sha256": descriptor["private_package_sha256"],
            "candidate_digest_sha256": descriptor["candidate_digest_sha256"],
            "unlock_digest_sha256": descriptor["unlock_digest_sha256"],
            "ca_pem_sha256": descriptor["ca_pem_sha256"],
            "broker_certificate_der_sha256": descriptor["broker_certificate_der_sha256"],
            "broker_spki_sha256": descriptor["broker_spki_sha256"],
            "prepare_command_sha256": descriptor["prepare_command_sha256"],
            "verify_command_sha256": descriptor["verify_command_sha256"],
        },
        "partition": {
            "label": chain.TEST_PARTITION_LABEL,
            "namespace": chain.TEST_PARTITION_NAMESPACE,
            "address": chain.TEST_PARTITION_ADDRESS,
            "size": chain.TEST_PARTITION_SIZE,
            "partition_csv_sha256": sha256_file(args.partition_csv),
        },
        "firmware": firmware,
        **FALSE_FLAGS,
    }
    payload_bytes = pretty_json_bytes(payload)
    files = {
        "application.bin": parts["application"],
        "bootloader.bin": parts["bootloader"],
        "firmware-payload.json": payload_bytes,
        "merged-image.bin": merged,
        "partition-table.bin": parts["partition_table"],
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    ).encode("utf-8")
    tar_path = output / IMMUTABLE_TAR_NAME
    deterministic_tar(tar_path, files)
    record = {
        "schema": BUILD_RECORD_SCHEMA,
        "state": "REPAIRED_IMMUTABLE_CLEAN_BUILD_COMPLETE",
        "stage": STAGE,
        "lane": args.lane,
        "source_sha": source_sha,
        "archive_sha256": sha256_file(tar_path),
        "payload_sha256": sha256_bytes(payload_bytes),
        "firmware": firmware,
        "immutable_build_binding": binding["immutable_build_binding"],
        "python_environment_sha256": args.python_environment_sha256,
        "openssl_environment_sha256": args.openssl_environment_sha256,
        "esphome_environment_sha256": args.esphome_environment_sha256,
        "compile_workflow_sha256": args.workflow_sha256,
        "repaired_host_controller_sha256": host_controller_sha,
        "public_inputs": payload["public_inputs"],
        **FALSE_FLAGS,
    }
    write_exclusive(output / "build-record.json", pretty_json_bytes(record))
    print("STAGE2D9R_REPAIRED_IMMUTABLE_BUILD=PASS")
    print(f"LANE={args.lane}")
    print(f"IMMUTABLE_ARCHIVE_SHA256={record['archive_sha256']}")
    print(f"APPLICATION_SHA256={firmware['application_sha256']}")
    print(f"MERGED_IMAGE_SHA256={firmware['merged_image_sha256']}")
    print("PRIVATE_VALUES_INCLUDED=false")
    print("BOARD_OPERATION=false")


def compare_build_records(a: dict[str, Any], b: dict[str, Any], schema: str) -> None:
    require(a.get("schema") == schema and b.get("schema") == schema, "BUILD_RECORD_SCHEMA_MISMATCH")
    require(a.get("lane") == "a" and b.get("lane") == "b", "BUILD_LANE_MISMATCH")
    left = dict(a)
    right = dict(b)
    left.pop("lane", None)
    right.pop("lane", None)
    require(left == right, "BUILD_RECORD_INVARIANT_MISMATCH")


def freeze_immutable(args: argparse.Namespace) -> None:
    source_sha = validate_sha40(args.source_sha, "SOURCE_SHA_INVALID")
    a_root = args.build_a.resolve(strict=True)
    b_root = args.build_b.resolve(strict=True)
    a_tar = a_root / IMMUTABLE_TAR_NAME
    b_tar = b_root / IMMUTABLE_TAR_NAME
    require(a_tar.read_bytes() == b_tar.read_bytes(), "IMMUTABLE_ARCHIVES_NOT_IDENTICAL")
    a_record = json.loads((a_root / "build-record.json").read_text(encoding="utf-8"))
    b_record = json.loads((b_root / "build-record.json").read_text(encoding="utf-8"))
    compare_build_records(a_record, b_record, BUILD_RECORD_SCHEMA)
    require(a_record["source_sha"] == source_sha, "IMMUTABLE_SOURCE_MISMATCH")
    members = tar_members(a_tar)
    require(set(members) == {
        "SHA256SUMS", "application.bin", "bootloader.bin", "firmware-payload.json",
        "merged-image.bin", "partition-table.bin",
    }, "IMMUTABLE_ARCHIVE_INVENTORY_MISMATCH")
    payload = json.loads(members["firmware-payload.json"])
    require(payload["source_sha"] == source_sha, "IMMUTABLE_PAYLOAD_SOURCE_MISMATCH")
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "OUTPUT_DIR_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    shutil.copyfile(a_tar, output / IMMUTABLE_TAR_NAME)
    os.chmod(output / IMMUTABLE_TAR_NAME, 0o600)
    manifest = {
        "schema": IMMUTABLE_FREEZE_SCHEMA,
        "state": "REPAIRED_IMMUTABLE_REPRODUCIBLE_AND_FROZEN",
        "stage": STAGE,
        "source_sha": source_sha,
        "clean_build_count": 2,
        "builds_independent": True,
        "payloads_byte_identical": True,
        "canonical_archive_sha256": sha256_file(a_tar),
        "payload_sha256": sha256_bytes(members["firmware-payload.json"]),
        "immutable_build_binding": payload["immutable_build_binding"],
        "firmware": payload["firmware"],
        "partition": payload["partition"],
        "python_environment_sha256": payload["python_environment_sha256"],
        "openssl_environment_sha256": payload["openssl_environment_sha256"],
        "esphome_environment_sha256": payload["esphome_environment_sha256"],
        "compile_workflow_sha256": payload["compile_workflow_sha256"],
        "repaired_host_controller_sha256": payload["repaired_host_controller_sha256"],
        "public_inputs": payload["public_inputs"],
        **FALSE_FLAGS,
    }
    manifest_bytes = pretty_json_bytes(manifest)
    write_exclusive(output / "immutable-freeze-manifest.json", manifest_bytes)
    sums = {
        IMMUTABLE_TAR_NAME: sha256_file(output / IMMUTABLE_TAR_NAME),
        "immutable-freeze-manifest.json": sha256_bytes(manifest_bytes),
    }
    write_exclusive(
        output / "SHA256SUMS",
        "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())).encode("utf-8"),
    )
    print("STAGE2D9R_REPAIRED_IMMUTABLE_FREEZE=PASS")
    print(f"IMMUTABLE_ARCHIVE_SHA256={manifest['canonical_archive_sha256']}")
    print(f"IMMUTABLE_PAYLOAD_SHA256={manifest['payload_sha256']}")
    print("REPRODUCIBLE=true")
    print("EXECUTION_AUTHORIZED=false")


def build_recovery(args: argparse.Namespace) -> None:
    source_sha = validate_sha40(args.source_sha, "SOURCE_SHA_INVALID")
    _, descriptor, acceptance, binding = public_inputs(args.public_dir, args.binding)
    immutable_root = args.immutable_freeze.resolve(strict=True)
    immutable_manifest = json.loads(
        (immutable_root / "immutable-freeze-manifest.json").read_text(encoding="utf-8")
    )
    require(immutable_manifest.get("state") == "REPAIRED_IMMUTABLE_REPRODUCIBLE_AND_FROZEN",
            "IMMUTABLE_FREEZE_STATE_INVALID")
    require(immutable_manifest.get("source_sha") == source_sha, "IMMUTABLE_FREEZE_SOURCE_MISMATCH")
    require(immutable_manifest.get("payloads_byte_identical") is True,
            "IMMUTABLE_FREEZE_NOT_REPRODUCIBLE")
    require(sha256_bytes(ERASED_PARTITION) == chain.ERASED_PARTITION_SHA256,
            "ERASED_PARTITION_DIGEST_MISMATCH")
    recovery_descriptor = {
        "schema": RECOVERY_DESCRIPTOR_SCHEMA,
        "state": "REPAIRED_LOCKED_RECOVERY_REVIEW_INPUT",
        "stage": STAGE,
        "source_sha": source_sha,
        "immutable_archive_sha256": immutable_manifest["canonical_archive_sha256"],
        "immutable_payload_sha256": immutable_manifest["payload_sha256"],
        "immutable_merged_image_sha256": immutable_manifest["firmware"]["merged_image_sha256"],
        "immutable_partition_table_sha256": immutable_manifest["firmware"]["partition_table_sha256"],
        "immutable_build_binding": binding["immutable_build_binding"],
        "candidate_digest_sha256": descriptor["candidate_digest_sha256"],
        "private_package_sha256": descriptor["private_package_sha256"],
        "partition": {
            "label": chain.TEST_PARTITION_LABEL,
            "namespace": chain.TEST_PARTITION_NAMESPACE,
            "address": chain.TEST_PARTITION_ADDRESS,
            "size": chain.TEST_PARTITION_SIZE,
            "expected_erased_byte": 255,
            "expected_erased_sha256": chain.ERASED_PARTITION_SHA256,
        },
        "maximum_counts": {
            "pre_read": 1,
            "region_erase": 1,
            "post_read": 1,
            "locked_recovery": 1,
        },
        "scope": "TEST_PARTITION_ONLY",
        **FALSE_FLAGS,
    }
    recovery_plan = {
        "schema": RECOVERY_PLAN_SCHEMA,
        "state": "LOCKED_REVIEW_ONLY_UNAUTHORIZED",
        "source_sha": source_sha,
        "entry_conditions": {
            "future_physical_d2_claimed": True,
            "destructive_boundary_crossed": True,
            "contract_named_failure_only": True,
            "normal_execution_return_permitted": False,
        },
        "ordered_operations": [
            {
                "index": 1,
                "operation": "READ_FLASH_REGION",
                "address": chain.TEST_PARTITION_ADDRESS,
                "size": chain.TEST_PARTITION_SIZE,
                "maximum_count": 1,
            },
            {
                "index": 2,
                "operation": "ERASE_FLASH_REGION",
                "address": chain.TEST_PARTITION_ADDRESS,
                "size": chain.TEST_PARTITION_SIZE,
                "maximum_count": 1,
            },
            {
                "index": 3,
                "operation": "READ_FLASH_REGION",
                "address": chain.TEST_PARTITION_ADDRESS,
                "size": chain.TEST_PARTITION_SIZE,
                "maximum_count": 1,
                "required_sha256": chain.ERASED_PARTITION_SHA256,
            },
        ],
        "forbidden_operations": [
            "ERASE_ALL_FLASH", "WRITE_FIRMWARE", "WRITE_NVS", "PREPARE",
            "VERIFY", "ACTIVATE", "CLEANUP", "MANUAL_BOOT", "EXTRA_RESET",
        ],
        "terminal_state_on_success": "CONSUMED_FAILED_LOCKED_RECOVERY_COMPLETED",
        **FALSE_FLAGS,
    }
    descriptor_bytes = pretty_json_bytes(recovery_descriptor)
    plan_bytes = pretty_json_bytes(recovery_plan)
    files = {
        "erased-test-partition.bin": ERASED_PARTITION,
        "locked-recovery-descriptor.json": descriptor_bytes,
        "locked-recovery-plan.json": plan_bytes,
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    ).encode("utf-8")
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "OUTPUT_DIR_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    tar_path = output / RECOVERY_TAR_NAME
    deterministic_tar(tar_path, files)
    record = {
        "schema": RECOVERY_BUILD_SCHEMA,
        "state": "REPAIRED_LOCKED_RECOVERY_CLEAN_BUILD_COMPLETE",
        "stage": STAGE,
        "lane": args.lane,
        "source_sha": source_sha,
        "archive_sha256": sha256_file(tar_path),
        "recovery_payload_sha256": sha256_bytes(plan_bytes),
        "recovery_descriptor_sha256": sha256_bytes(descriptor_bytes),
        "immutable_archive_sha256": immutable_manifest["canonical_archive_sha256"],
        "erased_partition_sha256": chain.ERASED_PARTITION_SHA256,
        **FALSE_FLAGS,
    }
    write_exclusive(output / "build-record.json", pretty_json_bytes(record))
    print("STAGE2D9R_REPAIRED_LOCKED_RECOVERY_BUILD=PASS")
    print(f"LANE={args.lane}")
    print(f"RECOVERY_ARCHIVE_SHA256={record['archive_sha256']}")
    print("RECOVERY_AUTHORIZED=false")
    print("BOARD_OPERATION=false")


def freeze_recovery(args: argparse.Namespace) -> None:
    source_sha = validate_sha40(args.source_sha, "SOURCE_SHA_INVALID")
    _, descriptor, acceptance, binding = public_inputs(args.public_dir, args.binding)
    immutable_root = args.immutable_freeze.resolve(strict=True)
    immutable_manifest_path = immutable_root / "immutable-freeze-manifest.json"
    immutable_manifest = json.loads(immutable_manifest_path.read_text(encoding="utf-8"))
    a_root = args.build_a.resolve(strict=True)
    b_root = args.build_b.resolve(strict=True)
    a_tar = a_root / RECOVERY_TAR_NAME
    b_tar = b_root / RECOVERY_TAR_NAME
    require(a_tar.read_bytes() == b_tar.read_bytes(), "RECOVERY_ARCHIVES_NOT_IDENTICAL")
    a_record = json.loads((a_root / "build-record.json").read_text(encoding="utf-8"))
    b_record = json.loads((b_root / "build-record.json").read_text(encoding="utf-8"))
    compare_build_records(a_record, b_record, RECOVERY_BUILD_SCHEMA)
    require(a_record["source_sha"] == source_sha, "RECOVERY_SOURCE_MISMATCH")
    recovery_members = tar_members(a_tar)
    require(set(recovery_members) == {
        "SHA256SUMS", "erased-test-partition.bin", "locked-recovery-descriptor.json",
        "locked-recovery-plan.json",
    }, "RECOVERY_ARCHIVE_INVENTORY_MISMATCH")
    require(sha256_bytes(recovery_members["erased-test-partition.bin"]) == chain.ERASED_PARTITION_SHA256,
            "RECOVERY_ERASED_IMAGE_MISMATCH")
    host_controller_sha = sha256_file(args.host_controller)
    require(host_controller_sha == immutable_manifest["repaired_host_controller_sha256"],
            "HOST_CONTROLLER_DIGEST_MISMATCH")
    digest_bindings = {
        "private_package_sha256": descriptor["private_package_sha256"],
        "public_descriptor_sha256": sha256_file(args.public_dir / "public-descriptor.redacted.json"),
        "candidate_digest_sha256": descriptor["candidate_digest_sha256"],
        "ca_pem_sha256": descriptor["ca_pem_sha256"],
        "prepare_command_sha256": descriptor["prepare_command_sha256"],
        "verify_command_sha256": descriptor["verify_command_sha256"],
        "repaired_host_controller_sha256": host_controller_sha,
        "immutable_archive_sha256": immutable_manifest["canonical_archive_sha256"],
        "immutable_payload_sha256": immutable_manifest["payload_sha256"],
        "immutable_merged_image_sha256": immutable_manifest["firmware"]["merged_image_sha256"],
        "immutable_partition_table_sha256": immutable_manifest["firmware"]["partition_table_sha256"],
        "recovery_archive_sha256": sha256_file(a_tar),
        "recovery_payload_sha256": sha256_bytes(recovery_members["locked-recovery-plan.json"]),
        "recovery_descriptor_sha256": sha256_bytes(recovery_members["locked-recovery-descriptor.json"]),
        "python_environment_sha256": immutable_manifest["python_environment_sha256"],
        "openssl_environment_sha256": immutable_manifest["openssl_environment_sha256"],
        "esphome_environment_sha256": immutable_manifest["esphome_environment_sha256"],
    }
    final_payload = chain.build_final_execution_payload(
        source_sha=source_sha,
        digest_bindings=digest_bindings,
        immutable_build_count=2,
        immutable_builds_byte_identical=True,
    )
    final_short, final_full = chain.derive_final_execution_binding(final_payload)
    final_binding = {
        "schema": chain.FINAL_BINDING_SCHEMA,
        "state": "REPAIRED_FINAL_EXECUTION_BINDING_FROZEN_UNAUTHORIZED",
        "final_execution_binding": final_short,
        "final_execution_binding_sha256": final_full,
        "payload": final_payload,
        **FALSE_FLAGS,
    }
    final_manifest = {
        "schema": FINAL_FREEZE_SCHEMA,
        "state": "REPAIRED_IMMUTABLE_RECOVERY_FROZEN_FINAL_BINDING_READY",
        "stage": STAGE,
        "source_sha": source_sha,
        "immutable_clean_build_count": 2,
        "immutable_builds_byte_identical": True,
        "recovery_clean_build_count": 2,
        "recovery_payloads_byte_identical": True,
        "immutable_archive_sha256": immutable_manifest["canonical_archive_sha256"],
        "immutable_payload_sha256": immutable_manifest["payload_sha256"],
        "recovery_archive_sha256": sha256_file(a_tar),
        "recovery_payload_sha256": digest_bindings["recovery_payload_sha256"],
        "recovery_descriptor_sha256": digest_bindings["recovery_descriptor_sha256"],
        "final_execution_binding": final_short,
        "final_execution_binding_sha256": final_full,
        "next_gate": "BASELINE_READONLY_GATE",
        **FALSE_FLAGS,
    }
    output = args.output_dir.resolve(strict=False)
    require(not output.exists(), "OUTPUT_DIR_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    for source, destination in (
        (immutable_root / IMMUTABLE_TAR_NAME, output / IMMUTABLE_TAR_NAME),
        (immutable_manifest_path, output / "immutable-freeze-manifest.json"),
        (a_tar, output / RECOVERY_TAR_NAME),
    ):
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o600)
    write_exclusive(output / "final-execution-binding.json", pretty_json_bytes(final_binding))
    write_exclusive(output / "immutable-recovery-freeze-manifest.json", pretty_json_bytes(final_manifest))
    sums = {
        path.name: sha256_file(path)
        for path in output.iterdir()
        if path.is_file()
    }
    write_exclusive(
        output / "SHA256SUMS",
        "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())).encode("utf-8"),
    )
    print("STAGE2D9R_REPAIRED_IMMUTABLE_RECOVERY_FREEZE=PASS")
    print(f"FINAL_EXECUTION_BINDING={final_short}")
    print(f"FINAL_EXECUTION_BINDING_SHA256={final_full}")
    print(f"IMMUTABLE_ARCHIVE_SHA256={final_manifest['immutable_archive_sha256']}")
    print(f"RECOVERY_ARCHIVE_SHA256={final_manifest['recovery_archive_sha256']}")
    print("NEXT_GATE=BASELINE_READONLY_GATE")
    print("EXECUTION_AUTHORIZED=false")
    print("BOARD_OPERATION=false")


def validate_public_command(args: argparse.Namespace) -> None:
    _, descriptor, acceptance, binding = public_inputs(args.public_dir, args.binding)
    print("STAGE2D9R_REPAIRED_PUBLIC_INPUT_VALIDATION=PASS")
    print(f"IMMUTABLE_BUILD_BINDING={binding['immutable_build_binding']}")
    print(f"PUBLIC_DESCRIPTOR_SHA256={sha256_file(args.public_dir / 'public-descriptor.redacted.json')}")
    print(f"U1_PUBLIC_ACCEPTANCE_SHA256={sha256_file(args.public_dir / 'u1-public-acceptance.json')}")
    print("PRIVATE_VALUES_INCLUDED=false")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="command", required=True)

    public = sub.add_parser("validate-public")
    public.add_argument("--public-dir", type=Path, required=True)
    public.add_argument("--binding", type=Path, required=True)
    public.set_defaults(function=validate_public_command)

    immutable = sub.add_parser("build-immutable")
    immutable.add_argument("--build-root", type=Path, required=True)
    immutable.add_argument("--output-dir", type=Path, required=True)
    immutable.add_argument("--lane", choices=("a", "b"), required=True)
    immutable.add_argument("--source-sha", required=True)
    immutable.add_argument("--python-environment-sha256", required=True)
    immutable.add_argument("--openssl-environment-sha256", required=True)
    immutable.add_argument("--esphome-environment-sha256", required=True)
    immutable.add_argument("--workflow-sha256", required=True)
    immutable.add_argument("--public-dir", type=Path, required=True)
    immutable.add_argument("--binding", type=Path, required=True)
    immutable.add_argument("--partition-csv", type=Path, required=True)
    immutable.add_argument("--host-controller", type=Path, required=True)
    immutable.set_defaults(function=build_immutable)

    freeze_i = sub.add_parser("freeze-immutable")
    freeze_i.add_argument("--build-a", type=Path, required=True)
    freeze_i.add_argument("--build-b", type=Path, required=True)
    freeze_i.add_argument("--output-dir", type=Path, required=True)
    freeze_i.add_argument("--source-sha", required=True)
    freeze_i.set_defaults(function=freeze_immutable)

    recovery = sub.add_parser("build-recovery")
    recovery.add_argument("--immutable-freeze", type=Path, required=True)
    recovery.add_argument("--output-dir", type=Path, required=True)
    recovery.add_argument("--lane", choices=("a", "b"), required=True)
    recovery.add_argument("--source-sha", required=True)
    recovery.add_argument("--public-dir", type=Path, required=True)
    recovery.add_argument("--binding", type=Path, required=True)
    recovery.set_defaults(function=build_recovery)

    freeze_r = sub.add_parser("freeze-recovery")
    freeze_r.add_argument("--build-a", type=Path, required=True)
    freeze_r.add_argument("--build-b", type=Path, required=True)
    freeze_r.add_argument("--immutable-freeze", type=Path, required=True)
    freeze_r.add_argument("--output-dir", type=Path, required=True)
    freeze_r.add_argument("--source-sha", required=True)
    freeze_r.add_argument("--public-dir", type=Path, required=True)
    freeze_r.add_argument("--binding", type=Path, required=True)
    freeze_r.add_argument("--host-controller", type=Path, required=True)
    freeze_r.set_defaults(function=freeze_recovery)
    return value


def main() -> int:
    args = parser().parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, FreezeError) and exc.args else type(exc).__name__
        print("STAGE2D9R_REPAIRED_IMMUTABLE_RECOVERY_PIPELINE=FAIL")
        print(f"FAILURE_CODE={code}")
        print("PRIVATE_VALUES_INCLUDED=false")
        print("PRIVATE_PATHS_INCLUDED=false")
        print("SECRET_VALUES_INCLUDED=false")
        print("BOARD_OPERATION=false")
        print("USB_ENUMERATION=false")
        print("SERIAL_OPERATION=false")
        print("ESPTOOL_OPERATION=false")
        print("FLASH_OPERATION=false")
        print("PHYSICAL_NVS_OPERATION=false")
        print("NETWORK_OPERATION=false")
        print("BROKER_STARTED=false")
        print("PREPARE_EXECUTED=false")
        print("VERIFY_EXECUTED=false")
        raise SystemExit(2)
