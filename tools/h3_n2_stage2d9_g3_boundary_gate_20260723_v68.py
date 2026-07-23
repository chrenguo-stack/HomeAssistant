#!/usr/bin/env python3
"""Static fail-closed boundary gate for the Stage2D9 G3 V68 source set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ZERO64 = "0" * 64
EXPECTED_UNLOCK_DIGEST = (
    "c6cfae354edbd426f9990fb65b4c865e711a0c2b6c1fba1d2e7faf132ebc2208"
)
EXPECTED_EXECUTION_CONFIG = (
    "greenhouse_profile_isolated_device_g3_execution_20260723_v68.yml"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def top_level_keys(text: str) -> set[str]:
    return {
        line.split(":", 1)[0]
        for line in text.splitlines()
        if line
        and not line[0].isspace()
        and not line.startswith("#")
        and ":" in line
    }


def scalar(text: str, key: str) -> str:
    matches = re.findall(rf"^\s+{re.escape(key)}:\s*([^#\s]+)\s*$", text, re.M)
    require(len(matches) == 1, f"expected one {key} scalar")
    value = matches[0]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--execution-config", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    execution_config = (repo / args.execution_config).resolve()
    output = Path(args.output).resolve()
    require(HEX40.fullmatch(args.source_commit) is not None, "invalid source commit")
    require(execution_config.is_file(), "execution config missing")
    require(
        execution_config.name == EXPECTED_EXECUTION_CONFIG,
        "unexpected V68 execution config",
    )

    board = repo / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare"
    executor = repo / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3_executor"
    locked = repo / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3_prepare"
    partition_csv = board / "stage2d9_g3_partitions_20260722_v65.csv"
    recovery_yml = board / "greenhouse_stage2d9_locked_recovery_20260722_v65.yml"
    public_compile_yml = board / "greenhouse_profile_isolated_device_g3_executor_20260722_v66.yml"

    for path in (
        partition_csv,
        recovery_yml,
        public_compile_yml,
        executor / "stage2d9_g3_prepare_executor.cpp",
        executor / "stage2d9_g3_prepare_executor.h",
        locked / "stage2d9_g3_locked_prepare_harness.cpp",
    ):
        require(path.is_file(), f"missing boundary source: {path}")

    execution_text = execution_config.read_text(encoding="utf-8")
    compile_text = public_compile_yml.read_text(encoding="utf-8")
    recovery_text = recovery_yml.read_text(encoding="utf-8")
    executor_cpp = (executor / "stage2d9_g3_prepare_executor.cpp").read_text(
        encoding="utf-8"
    )

    prohibited_runtime = {"wifi", "api", "ota", "captive_portal", "mqtt", "web_server"}
    require(
        not (top_level_keys(execution_text) & prohibited_runtime),
        "execution config contains a prohibited runtime component",
    )
    require(
        not (top_level_keys(recovery_text) & prohibited_runtime),
        "recovery config contains a prohibited runtime component",
    )
    require("external_components:" not in recovery_text, "recovery links Stage2D9 code")

    unlock_digest = scalar(execution_text, "unlock_digest")
    require(HEX64.fullmatch(unlock_digest) is not None, "unlock digest shape invalid")
    require(unlock_digest == EXPECTED_UNLOCK_DIGEST, "V68 unlock digest mismatch")
    require(unlock_digest != ZERO64, "execution config command surface remains disabled")
    require(
        scalar(compile_text, "unlock_digest") == ZERO64,
        "public compile config command surface is enabled",
    )
    source_binding = scalar(execution_text, "build_binding")
    require(HEX40.fullmatch(source_binding) is not None, "build binding invalid")

    row = next(
        (
            line
            for line in partition_csv.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("gh2d8_p2d9")
        ),
        "",
    )
    fields = [field.strip() for field in row.split(",")]
    require(
        fields[:5] == ["gh2d8_p2d9", "data", "nvs", "0x400000", "0x10000"],
        "partition geometry mismatch",
    )
    require(
        not any("readonly" in field.lower() for field in fields[5:]),
        "PREPARE partition is read-only",
    )

    required_executor_markers = (
        "GH2D9_PREPARE_V1",
        "GH2D9_VERIFY_V1",
        "command_replay",
        "constant_equal_",
        "authorization_binder_.grant",
        "package_.prepare_candidate",
        "verify_recovered_candidate_",
        "candidate_digest_match=true",
        "mqtt_operation_attempted",
        "esp_restart",
    )
    for marker in required_executor_markers:
        require(marker in executor_cpp, f"executor marker missing: {marker}")
    for prohibited in (
        "package_.activate(",
        "package_.cleanup_test_state(",
        "driver_.activate(",
        "driver_.cleanup_test_state(",
        "esp_efuse",
    ):
        require(prohibited not in executor_cpp, f"prohibited executor path: {prohibited}")

    report = {
        "schema": "gh.h3.n2.stage2d9-g3-source-boundary/2",
        "artifact_generation": "V68",
        "status": "pass",
        "gate": "LOCKED",
        "source_commit": args.source_commit,
        "executor_source_binding": source_binding,
        "unlock_digest_sha256": unlock_digest,
        "unlock_preimage_in_repository": False,
        "private_custody_required_before_d2": True,
        "partition": {
            "label": "gh2d8_p2d9",
            "namespace": "gh2d8_s2d9",
            "offset": "0x400000",
            "size": "0x10000",
            "writable_capable": True,
        },
        "execution": {
            "flash_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "network_authorized": False,
            "efuse_authorized": False,
            "production_authorized": False,
        },
        "sources": {
            "execution_config_sha256": sha256(execution_config),
            "partition_csv_sha256": sha256(partition_csv),
            "executor_cpp_sha256": sha256(
                executor / "stage2d9_g3_prepare_executor.cpp"
            ),
            "recovery_config_sha256": sha256(recovery_yml),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
