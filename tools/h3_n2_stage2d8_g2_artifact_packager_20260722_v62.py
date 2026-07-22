#!/usr/bin/env python3
"""Assemble and verify immutable Stage2D8 dedicated-board G2 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path

SOURCE_BINDING = "510566f7047a779b319daa87fb64cf64f292c224"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PARTITION_MAGIC = 0x50AA
READONLY_FLAG = 0x1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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
        label = chunk[12:28].split(b"\0", 1)[0].decode("ascii")
        flags = struct.unpack_from("<I", chunk, 28)[0]
        entries.append(
            {
                "label": label,
                "type": ptype,
                "subtype": subtype,
                "offset": address,
                "size": size,
                "flags": flags,
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
        "gh2d8_nvs": (0x01, 0x02, 0x400000, 0x10000, READONLY_FLAG),
    }
    require(set(by_label) == set(expected), "partition labels differ from frozen plan")
    for label, (ptype, subtype, address, size, flags) in expected.items():
        entry = by_label[label]
        require(int(entry["type"]) == ptype, f"{label} type mismatch")
        require(int(entry["subtype"]) == subtype, f"{label} subtype mismatch")
        require(int(entry["offset"]) == address, f"{label} offset mismatch")
        require(int(entry["size"]) == size, f"{label} size mismatch")
        if flags:
            require(int(entry["flags"]) & flags == flags, f"{label} read-only flag missing")
        else:
            require(int(entry["flags"]) == 0, f"{label} unexpected flags")
    return entries


def run_checked(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--esptool-python", required=True)
    parser.add_argument("--seed-image", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    output = Path(args.output).resolve()
    esptool_python = Path(args.esptool_python).resolve()
    seed_image = Path(args.seed_image).resolve()

    require(HEX40.fullmatch(args.source_commit) is not None, "invalid source commit")
    require(esptool_python.is_file(), "esptool Python missing")
    require(seed_image.is_file(), "NVS seed image missing")
    require(seed_image.stat().st_size == 0x10000, "NVS seed size mismatch")
    seed_bytes = seed_image.read_bytes()
    require(b"gh2d8_seed" in seed_bytes, "seed namespace missing from binary")
    require(b"gh2d8_state" not in seed_bytes, "target namespace present in binary")
    require(not output.exists(), "output directory already exists")
    output.mkdir(parents=True)

    board = repo / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g2_probe"
    build_names = {
        "g2": "gh-2d8-g2-v60",
        "recovery": "gh-2d8-recovery-v60",
    }
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
            "gh2d8_nvs_seed.bin": seed_image,
        }
        for filename, source in sources.items():
            shutil.copy2(source, role_dir / filename)

        entries = verify_partition_table(role_dir / "partitions.bin")
        if partition_entries is None:
            partition_entries = entries
        else:
            require(entries == partition_entries, "G2/recovery partition binaries differ")

        merged = role_dir / f"stage2d8-{role}-merged-v62.bin"
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
                str(role_dir / "gh2d8_nvs_seed.bin"),
            ]
        )
        run_checked(
            [
                str(esptool_python),
                "-m",
                "esptool",
                "--chip",
                "esp32c6",
                "image-info",
                str(role_dir / "firmware.bin"),
            ]
        )
        packages[role] = {
            path.name: {"sha256": sha256(path), "size": path.stat().st_size}
            for path in sorted(role_dir.iterdir())
        }

    require(
        (output / "g2/gh2d8_nvs_seed.bin").read_bytes()
        == (output / "recovery/gh2d8_nvs_seed.bin").read_bytes(),
        "G2/recovery seed images differ",
    )

    partition_csv = board / "stage2d8_g2_partitions_20260722_v60.csv"
    seed_csv = board / "stage2d8_g2_nvs_seed_20260722_v61.csv"
    boundary_json = Path("/tmp/stage2d8-g2-source-boundary-v62.json")
    for source in (partition_csv, seed_csv, boundary_json):
        require(source.is_file(), f"missing package metadata: {source}")
        shutil.copy2(source, output / source.name)

    manifest = {
        "schema": "gh.h3.n2.stage2d8-g2-artifact-manifest/3",
        "gate": "LOCKED",
        "source_commit": args.source_commit,
        "driver_source_binding": SOURCE_BINDING,
        "build_tools": {
            "esphome": "2026.4.3",
            "esptool": "5.3.1",
            "esp_idf_nvs_partition_gen": "0.2.0",
            "esp_idf_nvs_partition_gen_wheel_sha256": (
                "7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3"
            ),
            "reproducible_build": True,
        },
        "target": {
            "chip": "ESP32-C6",
            "module": "ESP32-C6-WROOM-1-N8",
            "flash_size": 8388608,
            "transport": "USB_SERIAL_JTAG",
        },
        "partition_table": {
            "csv": partition_csv.name,
            "csv_sha256": sha256(partition_csv),
            "binary_offset": "0x8000",
            "factory_app_offset": "0x10000",
            "test_partition_label": "gh2d8_nvs",
            "test_partition_offset": "0x400000",
            "test_partition_size": "0x10000",
            "test_partition_readonly": True,
            "target_namespace": "gh2d8_state",
            "seed_namespace": "gh2d8_seed",
            "seed_csv": seed_csv.name,
            "seed_csv_sha256": sha256(seed_csv),
            "seed_image_sha256": sha256(seed_image),
            "decoded_entries": partition_entries,
        },
        "packages": packages,
        "execution": {
            "flash_authorized": False,
            "read_only_probe_authorized": False,
            "test_partition_pre_post_readback_authorized": False,
            "persistent_write_authorized": False,
            "wifi_authorized": False,
            "mqtt_authorized": False,
        },
    }
    manifest_path = output / "stage2d8-g2-artifact-manifest-v62.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    text_scan = [
        manifest_path,
        output / partition_csv.name,
        output / seed_csv.name,
        output / boundary_json.name,
    ]
    forbidden_text = (
        "usbmodem",
        "98:a3:16",
        "mqtt_password",
        "wifi_password",
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
    )
    for path in text_scan:
        lowered = path.read_text(encoding="utf-8", errors="strict").lower()
        for token in forbidden_text:
            require(token.lower() not in lowered, f"redaction failure in {path.name}: {token}")

    for path in sorted(output.rglob("*.bin")):
        data = path.read_bytes().lower()
        require(b"usbmodem" not in data, f"local port leaked into {path.name}")
        require(b"98:a3:16" not in data, f"board identifier leaked into {path.name}")

    checksum_lines = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            checksum_lines.append(f"{sha256(path)}  {path.relative_to(output)}")
    (output / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )

    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
