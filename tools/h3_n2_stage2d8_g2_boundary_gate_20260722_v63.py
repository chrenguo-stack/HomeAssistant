#!/usr/bin/env python3
"""Fail-closed source boundary for Stage2D8 dedicated-board G2 V63."""

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
    probe_component = (
        repo
        / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g2_probe"
    )
    driver_component = (
        repo
        / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver"
    )
    g2_path = board / "greenhouse_profile_isolated_device_g2_probe_20260722_v60.yml"
    recovery_path = board / "greenhouse_stage2d8_locked_recovery_20260722_v60.yml"
    partitions_path = board / "stage2d8_g2_partitions_20260722_v60.csv"
    seed_path = board / "stage2d8_g2_nvs_seed_20260722_v61.csv"
    probe_path = probe_component / "stage2d8_g2_read_only_probe.cpp"
    port_path = driver_component / "isolated_device_esp32_ports.cpp"
    packager_path = repo / "tools/h3_n2_stage2d8_g2_artifact_packager_20260722_v63.py"
    fault_path = repo / "tools/h3_n2_stage2d8_g2_host_fault_matrix_20260722_v63.py"
    requirement_path = repo / "tools/h3_n2_stage2d8_nvsgen_requirements_20260722_v63.txt"
    workflow_path = repo / ".github/workflows/h3-n2-stage2d8-dedicated-board-g2-v63-ci.yml"

    paths = [
        g2_path,
        recovery_path,
        partitions_path,
        seed_path,
        probe_path,
        port_path,
        packager_path,
        fault_path,
        requirement_path,
        workflow_path,
    ]
    for path in paths:
        require(path.is_file(), f"missing required file: {path.relative_to(repo)}")

    g2 = g2_path.read_text(encoding="utf-8")
    recovery = recovery_path.read_text(encoding="utf-8")
    partitions = partitions_path.read_text(encoding="utf-8")
    seed = seed_path.read_text(encoding="utf-8")
    probe = probe_path.read_text(encoding="utf-8")
    port = port_path.read_text(encoding="utf-8")
    packager = packager_path.read_text(encoding="utf-8")
    fault = fault_path.read_text(encoding="utf-8")
    requirement = requirement_path.read_text(encoding="utf-8").strip()
    workflow = workflow_path.read_text(encoding="utf-8")

    forbidden_blocks = (
        "wifi",
        "api",
        "ota",
        "mqtt",
        "mdns",
        "web_server",
        "captive_portal",
    )
    for name, text in (("g2", g2), ("recovery", recovery)):
        for block in forbidden_blocks:
            require(
                re.search(rf"(?m)^\s*{re.escape(block)}\s*:", text) is None,
                f"{name} contains forbidden runtime block: {block}",
            )
        require(
            "CONFIG_APP_REPRODUCIBLE_BUILD: y" in text,
            f"{name} reproducible-build option missing",
        )

    for token in (
        "hardware_uart: USB_SERIAL_JTAG",
        "partition_label: gh2d8_nvs",
        "namespace_name: gh2d8_state",
        f"build_binding: {SOURCE_BINDING}",
    ):
        require(token in g2, f"G2 binding missing: {token}")

    require(
        "gh2d8_nvs,  data, nvs,     0x400000, 0x10000,   readonly" in partitions,
        "read-only test partition row mismatch",
    )
    require(
        "factory,     app,  factory, 0x10000,  0x3F0000," in partitions,
        "factory partition row mismatch",
    )

    expected_seed = (
        "key,type,encoding,value\n"
        "gh2d8_seed,namespace,,\n"
        "format_version,data,u8,1\n"
    )
    require(seed == expected_seed, "NVS seed CSV differs from frozen content")
    require("gh2d8_state" not in seed, "target namespace present in seed")

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
        require(token in probe, f"G2 read-only contract missing: {token}")

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
        require(token not in probe, f"G2 probe contains forbidden mutation token: {token}")

    missing_index = port.find("if (this->backend_->namespace_missing())")
    key_index = port.find("if (this->test_key_provider_ == nullptr")
    require(missing_index >= 0, "ESP32 port missing absent-namespace branch")
    require(key_index >= 0, "ESP32 port missing key gate")
    require(
        missing_index < key_index,
        "key gate must follow absent-namespace read-only result",
    )
    for token in (
        "snapshot->read_only_opened = true",
        "snapshot->namespace_missing = true",
        "snapshot->recovery_valid = true",
        'snapshot->recovery_status = "empty"',
        "snapshot->persistent_write_count = this->persistent_write_count_",
    ):
        require(token in port[missing_index:key_index], f"no-key empty path missing: {token}")

    for token in (
        "verify_seed_image",
        "verify_partition_table",
        "READONLY_FLAG = 0x2",
        '"gate": "LOCKED"',
        '"flash_authorized": False',
        '"persistent_write_authorized": False',
        "stage2d8-g2-artifact-manifest-v63.json",
    ):
        require(token in packager, f"V63 packager contract missing: {token}")

    for token in (
        "P02_TEST_PARTITION_READONLY_FLAG_MISSING",
        "P03_TEST_PARTITION_OFFSET_DRIFT",
        "N02_SEED_SIZE_MISMATCH",
        "N04_TARGET_NAMESPACE_PRECREATED",
        "0x2 if readonly else 0",
        '"case_count": len(results)',
    ):
        require(token in fault, f"V63 fault matrix case missing: {token}")

    require(requirement == NVSGEN_REQUIREMENT, "NVS generator requirement/hash mismatch")
    for token in (
        "--no-deps",
        "--require-hashes",
        "esp_idf_nvs_partition_gen generate",
        "stage2d8-g2-host-fault-matrix-v63.json",
        "stage2d8-g2-immutable-locked-v63",
    ):
        require(token in workflow, f"V63 workflow contract missing: {token}")

    report = {
        "schema": "gh.h3.n2.stage2d8-g2-source-boundary/4",
        "status": "pass",
        "gate": "LOCKED",
        "driver_source_binding": SOURCE_BINDING,
        "no_key_empty_namespace_path_verified": True,
        "partition_readonly_flag_word": "0x00000002",
        "nvs_generator": {
            "package": "esp-idf-nvs-partition-gen",
            "version": "0.2.0",
            "wheel_sha256": "7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3",
        },
        "files": {
            str(path.relative_to(repo)): sha256(path)
            for path in sorted(paths)
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
