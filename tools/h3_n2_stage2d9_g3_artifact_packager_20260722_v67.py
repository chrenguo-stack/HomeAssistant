#!/usr/bin/env python3
"""Assemble immutable Stage2D9 G3 V67 executor and locked recovery artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PARTITION_MAGIC = 0x50AA
TEST_PARTITION_SIZE = 0x10000
GENERATOR_VERSION = "0.2.0"
GENERATOR_WHEEL_SHA256 = (
    "7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3"
)
FIXED_BUILD_EPOCH = 1784678400
FIXED_BUILD_TIME_STR = "2026-07-22 00:00:00 +0000"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate(build_root: Path, filename: str, *, exclude_bootloader: bool = False) -> Path:
    candidates = sorted(build_root.rglob(filename))
    if exclude_bootloader:
        candidates = [path for path in candidates if "bootloader" not in path.parts]
    require(bool(candidates), f"missing {filename} under {build_root}")
    return candidates[0]


def parse_partitions(path: Path) -> list[dict[str, int | str]]:
    data = path.read_bytes()
    entries: list[dict[str, int | str]] = []
    for offset in range(0, len(data), 32):
        chunk = data[offset : offset + 32]
        if len(chunk) < 32 or chunk == b"\xff" * 32:
            break
        magic, ptype, subtype, address, size = struct.unpack_from("<HBBII", chunk, 0)
        if magic != PARTITION_MAGIC:
            break
        entries.append(
            {
                "label": chunk[12:28].split(b"\0", 1)[0].decode("ascii"),
                "type": ptype,
                "subtype": subtype,
                "offset": address,
                "size": size,
                "flags": struct.unpack_from("<I", chunk, 28)[0],
            }
        )
    return entries


def verify_partition_table(path: Path) -> list[dict[str, int | str]]:
    entries = parse_partitions(path)
    require(len(entries) == 4, f"unexpected partition count: {len(entries)}")
    by_label = {str(entry["label"]): entry for entry in entries}
    expected = {
        "nvs": (0x01, 0x02, 0x9000, 0x6000, 0),
        "phy_init": (0x01, 0x01, 0xF000, 0x1000, 0),
        "factory": (0x00, 0x00, 0x10000, 0x3F0000, 0),
        "gh2d8_p2d9": (0x01, 0x02, 0x400000, TEST_PARTITION_SIZE, 0),
    }
    require(set(by_label) == set(expected), "partition labels differ from V67 plan")
    for label, values in expected.items():
        ptype, subtype, address, size, flags = values
        entry = by_label[label]
        require(int(entry["type"]) == ptype, f"{label} type mismatch")
        require(int(entry["subtype"]) == subtype, f"{label} subtype mismatch")
        require(int(entry["offset"]) == address, f"{label} offset mismatch")
        require(int(entry["size"]) == size, f"{label} size mismatch")
        require(int(entry["flags"]) == flags, f"{label} flags mismatch")
    return entries


def verify_seed(path: Path) -> None:
    require(path.is_file(), "Stage2D9 seed image missing")
    require(path.stat().st_size == TEST_PARTITION_SIZE, "seed image size mismatch")
    data = path.read_bytes()
    require(b"gh2d8_seed" in data, "seed namespace missing")
    require(b"gh2d8_s2d9" not in data, "target namespace present in seed")


def load_json(path: Path, message: str) -> dict:
    require(path.is_file(), message)
    return json.loads(path.read_text(encoding="utf-8"))


def scan_redaction(paths: list[Path]) -> None:
    forbidden_all = (b"usbmodem", b"/users/", b"begin private key")
    forbidden_text = (
        b"unlock_token_hex",
        b"persistence_key_hex",
        b"gh2d9_prepare_v1 ",
        b"gh2d9_verify_v1 ",
    )
    for path in paths:
        data = path.read_bytes().lower()
        for token in forbidden_all:
            require(token not in data, f"private marker in {path.name}")
        if path.suffix.lower() in {".json", ".csv", ".txt"} or path.name == "SHA256SUMS":
            for token in forbidden_text:
                require(token not in data, f"private command material in {path.name}")


def run_checked(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--esptool-python", required=True)
    parser.add_argument("--seed-image", required=True)
    parser.add_argument("--boundary-report", required=True)
    parser.add_argument("--reproducibility-report", required=True)
    parser.add_argument("--nvsgen-runtime-report", required=True)
    parser.add_argument("--nvsgen-requirements", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    output = Path(args.output).resolve()
    esptool_python = Path(args.esptool_python).resolve()
    seed = Path(args.seed_image).resolve()
    boundary_path = Path(args.boundary_report).resolve()
    repro_path = Path(args.reproducibility_report).resolve()
    runtime_path = Path(args.nvsgen_runtime_report).resolve()
    requirements = Path(args.nvsgen_requirements).resolve()

    require(HEX40.fullmatch(args.source_commit) is not None, "invalid source commit")
    require(esptool_python.is_file(), "esptool Python missing")
    require(not output.exists(), "output directory already exists")
    verify_seed(seed)
    boundary = load_json(boundary_path, "boundary report missing")
    repro = load_json(repro_path, "reproducibility report missing")
    runtime = load_json(runtime_path, "NVS generator runtime report missing")
    require(requirements.is_file(), "NVS generator requirements missing")
    require(boundary.get("status") == "pass", "boundary report did not pass")
    require(boundary.get("gate") == "LOCKED", "boundary gate is not LOCKED")
    require(repro.get("status") == "pass", "reproducibility did not pass")
    require(repro.get("byte_identical") is True, "builds are not byte-identical")
    require(repro.get("clean_build_count") == 2, "wrong clean build count")
    require(runtime.get("generator_version") == GENERATOR_VERSION, "generator version mismatch")
    require(runtime.get("wheel_sha256") == GENERATOR_WHEEL_SHA256, "generator wheel mismatch")

    output.mkdir(parents=True)
    board = repo / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare"
    build_names = {"g3": "gh-2d9-g3-v67", "recovery": "gh-2d9-recovery-v65"}
    packages: dict[str, dict[str, dict[str, int | str]]] = {}
    partition_entries: list[dict[str, int | str]] | None = None

    for role, build_name in build_names.items():
        build_root = board / ".esphome/build" / build_name
        role_dir = output / role
        role_dir.mkdir()
        sources = {
            "bootloader.bin": locate(build_root, "bootloader.bin"),
            "partitions.bin": locate(build_root, "partitions.bin"),
            "firmware.bin": locate(build_root, "firmware.bin", exclude_bootloader=True),
            "gh2d9_nvs_seed.bin": seed,
        }
        for filename, source in sources.items():
            shutil.copy2(source, role_dir / filename)
        entries = verify_partition_table(role_dir / "partitions.bin")
        if partition_entries is None:
            partition_entries = entries
        else:
            require(entries == partition_entries, "G3/recovery partition binaries differ")
        merged = role_dir / f"stage2d9-{role}-merged-v67.bin"
        run_checked(
            [
                str(esptool_python),
                "-m",
                "esptool",
                "--chip",
                "esp32c6",
                "merge-bin",
                "--output",
                str(merged),
                "0x0",
                str(role_dir / "bootloader.bin"),
                "0x8000",
                str(role_dir / "partitions.bin"),
                "0x10000",
                str(role_dir / "firmware.bin"),
                "0x400000",
                str(role_dir / "gh2d9_nvs_seed.bin"),
            ]
        )
        packages[role] = {
            path.name: {"sha256": sha256(path), "size": path.stat().st_size}
            for path in sorted(role_dir.iterdir())
        }

    partition_csv = board / "stage2d9_g3_partitions_20260722_v65.csv"
    seed_csv = board / "stage2d9_g3_nvs_seed_20260722_v65.csv"
    execution_config = board / "greenhouse_profile_isolated_device_g3_execution_20260722_v67.yml"
    recovery_config = board / "greenhouse_stage2d9_locked_recovery_20260722_v65.yml"
    for source in (
        partition_csv,
        seed_csv,
        execution_config,
        recovery_config,
        boundary_path,
        repro_path,
        runtime_path,
        requirements,
    ):
        require(source.is_file(), f"package metadata missing: {source}")
        shutil.copy2(source, output / source.name)

    unlock_digest = str(boundary["unlock_digest_sha256"])
    require(HEX64.fullmatch(unlock_digest) is not None, "unlock digest missing")
    manifest = {
        "schema": "gh.h3.n2.stage2d9-g3-artifact-manifest/1",
        "gate": "LOCKED",
        "source_commit": args.source_commit,
        "executor_source_binding": boundary["executor_source_binding"],
        "unlock_digest_sha256": unlock_digest,
        "unlock_preimage_in_artifact": False,
        "target": {
            "chip": "ESP32-C6",
            "module": "ESP32-C6-WROOM-1-N8",
            "flash_size": 8388608,
            "transport": "USB_SERIAL_JTAG",
        },
        "build_tools": {
            "esphome": "2026.4.3",
            "esptool": "5.3.1",
            "esp_idf_nvs_partition_gen": GENERATOR_VERSION,
            "esp_idf_nvs_partition_gen_wheel_sha256": GENERATOR_WHEEL_SHA256,
            "fixed_build_epoch": FIXED_BUILD_EPOCH,
            "fixed_build_time": FIXED_BUILD_TIME_STR,
            "clean_build_count": 2,
            "byte_identical": True,
        },
        "partition_table": {
            "label": "gh2d8_p2d9",
            "namespace": "gh2d8_s2d9",
            "offset": "0x400000",
            "size": "0x10000",
            "writable_capable": True,
            "seed_namespace": "gh2d8_seed",
            "target_namespace_absent_from_seed": True,
            "seed_image_sha256": sha256(seed),
            "decoded_entries": partition_entries,
        },
        "reproducibility": {
            "report": repro_path.name,
            "report_sha256": sha256(repro_path),
        },
        "source_boundary": {
            "report": boundary_path.name,
            "report_sha256": sha256(boundary_path),
        },
        "packages": packages,
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
    }
    manifest_path = output / "stage2d9-g3-artifact-manifest-v67.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    scan_redaction([path for path in output.rglob("*") if path.is_file()])

    checksum_lines = [
        f"{sha256(path)}  {path.relative_to(output)}"
        for path in sorted(output.rglob("*"))
        if path.is_file()
    ]
    (output / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
