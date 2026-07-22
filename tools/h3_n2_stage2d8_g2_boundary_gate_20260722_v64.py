#!/usr/bin/env python3
"""Fail-closed source boundary for Stage2D8 dedicated-board G2 V64."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE_BINDING = "510566f7047a779b319daa87fb64cf64f292c224"
NVSGEN_REQUIREMENT = (
    "esp-idf-nvs-partition-gen==0.2.0 "
    "--hash=sha256:7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3"
)
FIXED_BUILD_EPOCH = "1784678400"
FIXED_BUILD_TIME = "2026-07-22 00:00:00 +0000"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    board = repo / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g2_probe"
    probe_component = repo / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g2_probe"
    driver_component = repo / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver"

    paths = {
        "g2": board / "greenhouse_profile_isolated_device_g2_probe_20260722_v60.yml",
        "recovery": board / "greenhouse_stage2d8_locked_recovery_20260722_v60.yml",
        "partitions": board / "stage2d8_g2_partitions_20260722_v60.csv",
        "seed": board / "stage2d8_g2_nvs_seed_20260722_v61.csv",
        "probe": probe_component / "stage2d8_g2_read_only_probe.cpp",
        "port": driver_component / "isolated_device_esp32_ports.cpp",
        "wrapper": repo / "tools/h3_n2_stage2d8_esphome_reproducible_compile_20260722_v64.py",
        "packager": repo / "tools/h3_n2_stage2d8_g2_artifact_packager_20260722_v64.py",
        "repro_gate": repo / "tools/h3_n2_stage2d8_g2_reproducibility_gate_20260722_v64.py",
        "fault": repo / "tools/h3_n2_stage2d8_g2_host_fault_matrix_20260722_v64.py",
        "requirements": repo / "tools/h3_n2_stage2d8_nvsgen_requirements_20260722_v64.txt",
        "workflow": repo / ".github/workflows/h3-n2-stage2d8-dedicated-board-g2-v64-ci.yml",
    }
    for name, path in paths.items():
        require(path.is_file(), f"missing required {name}: {path.relative_to(repo)}")

    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    for name in ("g2", "recovery"):
        for block in ("wifi", "api", "ota", "mqtt", "mdns", "web_server", "captive_portal"):
            require(
                re.search(rf"(?m)^\s*{re.escape(block)}\s*:", text[name]) is None,
                f"{name} contains forbidden runtime block: {block}",
            )
        require(
            "CONFIG_APP_REPRODUCIBLE_BUILD: y" in text[name],
            f"{name} reproducible-build option missing",
        )

    for token in (
        "hardware_uart: USB_SERIAL_JTAG",
        "partition_label: gh2d8_nvs",
        "namespace_name: gh2d8_state",
        f"build_binding: {SOURCE_BINDING}",
    ):
        require(token in text["g2"], f"G2 binding missing: {token}")

    require(
        "gh2d8_nvs,  data, nvs,     0x400000, 0x10000,   readonly"
        in text["partitions"],
        "read-only test partition row mismatch",
    )
    expected_seed = (
        "key,type,encoding,value\n"
        "gh2d8_seed,namespace,,\n"
        "format_version,data,u8,1\n"
    )
    require(text["seed"] == expected_seed, "NVS seed CSV differs from frozen content")
    require("gh2d8_state" not in text["seed"], "target namespace present in seed")

    for token in (
        "nvs_flash_init_partition",
        "nvs_flash_deinit_partition",
        "partition->readonly",
        "STAGE2D8_TEST_PARTITION_ADDRESS = 0x400000",
        "STAGE2D8_TEST_PARTITION_SIZE = 0x10000",
        "package_.inspect_read_only()",
        "persistent_write_count == 0",
        'persistence_status == "empty"',
        "stage2d8_g2_probe=pass",
    ):
        require(token in text["probe"], f"G2 read-only contract missing: {token}")
    for token in (
        "nvs_set_",
        "nvs_erase_",
        "nvs_commit(",
        "esp_partition_write",
        "esp_partition_erase_range",
        "PREPARE_CANDIDATE",
        "ACTIVATE_PROFILE",
        "CLEANUP_TEST_STATE",
    ):
        require(token not in text["probe"], f"G2 probe contains mutation token: {token}")

    missing_index = text["port"].find("if (this->backend_->namespace_missing())")
    key_index = text["port"].find("if (this->test_key_provider_ == nullptr")
    require(missing_index >= 0 and key_index >= 0, "ESP32 no-key empty path missing")
    require(missing_index < key_index, "key gate must follow absent-namespace result")
    for token in (
        "snapshot->read_only_opened = true",
        "snapshot->namespace_missing = true",
        "snapshot->recovery_valid = true",
        'snapshot->recovery_status = "empty"',
        "snapshot->persistent_write_count = this->persistent_write_count_",
    ):
        require(token in text["port"][missing_index:key_index], f"no-key path missing: {token}")

    for token in (
        f"FIXED_BUILD_EPOCH = {FIXED_BUILD_EPOCH}",
        f'FIXED_BUILD_TIME_STR = "{FIXED_BUILD_TIME}"',
        "writer.get_build_info = fixed_get_build_info",
        'REQUIRED_ESPHOME_VERSION = "2026.4.3"',
    ):
        require(token in text["wrapper"], f"fixed-time wrapper contract missing: {token}")

    for token in (
        "clean_build_count",
        "byte_identical",
        "non-reproducible binary",
        FIXED_BUILD_TIME,
    ):
        require(token in text["repro_gate"], f"reproducibility gate missing: {token}")

    for token in (
        "READONLY_FLAG = 0x2",
        "verify_reproducibility_report",
        '"schema": "gh.h3.n2.stage2d8-g2-artifact-manifest/5"',
        '"gate": "LOCKED"',
        '"flash_authorized": False',
        '"persistent_write_authorized": False',
        "stage2d8-g2-artifact-manifest-v64.json",
    ):
        require(token in text["packager"], f"V64 packager contract missing: {token}")

    for token in (
        "P02_TEST_PARTITION_READONLY_FLAG_MISSING",
        "P03_TEST_PARTITION_OFFSET_DRIFT",
        "N02_SEED_SIZE_MISMATCH",
        "N04_TARGET_NAMESPACE_PRECREATED",
        "READONLY_FLAG = 0x2",
        '"case_count": len(results)',
    ):
        require(token in text["fault"], f"V64 fault matrix case missing: {token}")

    require(text["requirements"].strip() == NVSGEN_REQUIREMENT, "NVS generator pin mismatch")
    for token in (
        "h3_n2_stage2d8_esphome_reproducible_compile_20260722_v64.py",
        "clean-build-a",
        "clean-build-b",
        "h3_n2_stage2d8_g2_reproducibility_gate_20260722_v64.py",
        "--no-deps",
        "--require-hashes",
        "stage2d8-g2-immutable-locked-v64",
    ):
        require(token in text["workflow"], f"V64 workflow contract missing: {token}")

    report = {
        "schema": "gh.h3.n2.stage2d8-g2-source-boundary/5",
        "status": "pass",
        "gate": "LOCKED",
        "driver_source_binding": SOURCE_BINDING,
        "no_key_empty_namespace_path_verified": True,
        "partition_readonly_flag_word": "0x00000002",
        "fixed_build_epoch": int(FIXED_BUILD_EPOCH),
        "fixed_build_time": FIXED_BUILD_TIME,
        "files": {
            str(path.relative_to(repo)): sha256(path)
            for path in sorted(paths.values())
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
