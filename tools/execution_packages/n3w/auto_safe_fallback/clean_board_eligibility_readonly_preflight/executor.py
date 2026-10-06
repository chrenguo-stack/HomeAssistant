from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

SOURCE_HEAD = "157448b621f288c5ac5038e7a1ac906cf2575a7f"
SOURCE_TREE = "f45ca257de0b6e41f0458346711bb4e105ba1fcc"
WORKFLOW_RUN_ID = 37249933019
ARTIFACT_ID = 11320812037
ARTIFACT_NAME = "n3w-kf050-first-pair-f1rc2-157448b-exact-source"
RELEASE_ZIP_NAME = "n3w-kf050-first-pair-f1rc2-157448b-exact-source.zip"
RELEASE_ZIP_SIZE = 4332479
RELEASE_ZIP_SHA256 = "44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff"
FIRMWARE_SIZE = 1410080
FIRMWARE_SHA256 = "4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b"
FACTORY_SIZE = 1475616
FACTORY_SHA256 = "a952987c6e6aabd3205f15f60a2ee3a7b9a946635b03b1ce90578880c83f5186"
BOOTLOADER_SIZE = 22576
BOOTLOADER_SHA256 = "e36ee1eaa32780c74612ea512164fa56770744fbefa1e34df2fab36de76b4b97"
PARTITIONS_SIZE = 3072
PARTITIONS_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
FLASH_ARGS_SIZE = 167
FLASH_ARGS_SHA256 = "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_READ_SIZE = 0x1000
FLASH_SIZE_BYTES = 8 * 1024 * 1024
KNOWN_BOARD_HARDWARE_IDS = {
    "ghw-c6-98a316a9f350",
    "ghw-c6-98a316a9f45c",
}
TARGET_NAMESPACES = {
    "gh_n3w_v2": {"peer", "broker", "pair_ack", "pair_intent", "setup", "pair_epoch"},
    "gh_n3w": {"boot_state"},
}
DISTINCTIVE_KEYS = {"pair_ack", "pair_intent", "pair_epoch", "boot_state"}
SCHEMA = "n3w.kf050.clean-board-eligibility-readonly-preflight/1"

MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
ESPTOOL_VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)


class StopExecution(RuntimeError):
    pass


@dataclass(frozen=True)
class PartitionEntry:
    label: str
    type_value: int
    subtype: int
    offset: int
    size: int
    flags: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardware_id_from_mac(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC format")
    return "ghw-c6-" + compact


def public_identity_sha256(hardware_id: str) -> str:
    if not re.fullmatch(r"ghw-c6-[0-9a-f]{12}", hardware_id):
        raise StopExecution("invalid hardware id format")
    return sha256_bytes(hardware_id.encode("ascii"))


def run_capture(args: list[str], port: str | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        redacted = ["<PORT>" if port is not None and item == port else item for item in args]
        raise StopExecution(f"command failed rc={proc.returncode}: {' '.join(redacted)}")
    return output


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_esptool() -> str:
    output = run_capture(esptool_base() + ["version"])
    match = ESPTOOL_VERSION_RE.search(output)
    if match is None:
        raise StopExecution("unable to parse esptool version")
    major, minor, patch = map(int, match.groups())
    if major != 5:
        raise StopExecution("esptool major version must be 5")
    return f"{major}.{minor}.{patch}"


def verify_release_zip(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise StopExecution("release ZIP missing")
    if path.stat().st_size != RELEASE_ZIP_SIZE:
        raise StopExecution("release ZIP size mismatch")
    if sha256_file(path) != RELEASE_ZIP_SHA256:
        raise StopExecution("release ZIP SHA256 mismatch")
    expected = {
        "MANIFEST.txt": None,
        "bootloader.bin": (BOOTLOADER_SIZE, BOOTLOADER_SHA256),
        "firmware.bin": (FIRMWARE_SIZE, FIRMWARE_SHA256),
        "firmware.factory.bin": (FACTORY_SIZE, FACTORY_SHA256),
        "firmware.ota.bin": (FIRMWARE_SIZE, FIRMWARE_SHA256),
        "flash_args": (FLASH_ARGS_SIZE, FLASH_ARGS_SHA256),
        "ota_data_initial.bin": (OTADATA_SIZE, OTADATA_SHA256),
        "partitions.bin": (PARTITIONS_SIZE, PARTITIONS_SHA256),
    }
    observed: dict[str, str] = {}
    with zipfile.ZipFile(path, "r") as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        if names != set(expected):
            raise StopExecution("release ZIP member set mismatch")
        for name, binding in expected.items():
            data = archive.read(name)
            observed[name] = sha256_bytes(data)
            if binding is None:
                continue
            size, digest = binding
            if len(data) != size or observed[name] != digest:
                raise StopExecution(f"{name} binding mismatch")
        manifest = archive.read("MANIFEST.txt").decode("utf-8", errors="strict")
        required = [
            f"SOURCE_HEAD={SOURCE_HEAD}",
            f"SOURCE_TREE={SOURCE_TREE}",
            "KF050_FIRST_PAIR_BOOT_REPAIR=true",
            "BINARY_DEHARNESS_PROOF=PASS",
            "DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS",
            "KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS",
        ]
        if any(item not in manifest for item in required):
            raise StopExecution("release manifest authority mismatch")
    return observed


def parse_partition_table(raw: bytes) -> tuple[str, list[PartitionEntry]]:
    if len(raw) < PARTITIONS_SIZE:
        raise StopExecution("partition table read too short")
    table = raw[:PARTITIONS_SIZE]
    if all(value == 0xFF for value in table):
        return "BLANK", []
    entries: list[PartitionEntry] = []
    for offset in range(0, len(table), 32):
        record = table[offset : offset + 32]
        if len(record) < 32:
            break
        if all(value == 0xFF for value in record):
            break
        magic = int.from_bytes(record[0:2], "little")
        if magic == 0xEBEB:
            break
        if magic != 0x50AA:
            raise StopExecution(f"partition table invalid at entry offset 0x{offset:x}")
        type_value = record[2]
        subtype = record[3]
        part_offset = int.from_bytes(record[4:8], "little")
        part_size = int.from_bytes(record[8:12], "little")
        label_bytes = record[12:28].split(b"\x00", 1)[0]
        try:
            label = label_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise StopExecution("partition label is not ASCII") from exc
        flags = int.from_bytes(record[28:32], "little")
        if part_size <= 0 or part_offset < 0 or part_offset + part_size > FLASH_SIZE_BYTES:
            raise StopExecution(f"partition {label!r} outside 8MB flash")
        entries.append(PartitionEntry(label, type_value, subtype, part_offset, part_size, flags))
    if not entries:
        raise StopExecution("nonblank partition table has no valid entries")
    sorted_entries = sorted(entries, key=lambda item: item.offset)
    previous_end = 0
    for entry in sorted_entries:
        if entry.offset < previous_end:
            raise StopExecution("partition table contains overlapping entries")
        previous_end = entry.offset + entry.size
    return "VALID", entries


def find_nvs_partitions(entries: list[PartitionEntry]) -> list[PartitionEntry]:
    return [entry for entry in entries if entry.type_value == 0x01 and entry.subtype == 0x02]


def _active_nvs_entries(raw: bytes) -> list[tuple[int, int, str, bytes]]:
    found: list[tuple[int, int, str, bytes]] = []
    for page_start in range(0, len(raw), 4096):
        page = raw[page_start : page_start + 4096]
        if len(page) < 4096 or all(value == 0xFF for value in page):
            continue
        bitmap = page[32:64]
        for index in range(126):
            state = (bitmap[index // 4] >> ((index % 4) * 2)) & 0x03
            if state != 0x02:
                continue
            start = 64 + index * 32
            entry = page[start : start + 32]
            if len(entry) != 32:
                continue
            ns_index = entry[0]
            entry_type = entry[1]
            key_bytes = entry[8:24].split(b"\x00", 1)[0]
            if not key_bytes:
                continue
            try:
                key = key_bytes.decode("ascii")
            except UnicodeDecodeError:
                continue
            found.append((ns_index, entry_type, key, entry[24:32]))
    return found


def inspect_nvs_partition(raw: bytes) -> dict[str, object]:
    active = _active_nvs_entries(raw)
    namespace_indexes: dict[int, str] = {}
    for ns_index, entry_type, key, data in active:
        if ns_index == 0 and entry_type == 0x01 and key in TARGET_NAMESPACES and data:
            namespace_indexes[data[0]] = key
    active_matches: set[str] = set()
    for ns_index, _entry_type, key, _data in active:
        namespace = namespace_indexes.get(ns_index)
        if namespace is not None and key in TARGET_NAMESPACES[namespace]:
            active_matches.add(f"{namespace}/{key}")
    raw_matches: set[str] = set()
    for namespace, keys in TARGET_NAMESPACES.items():
        namespace_present = namespace.encode("ascii") in raw
        for key in keys:
            key_present = key.encode("ascii") in raw
            if key in DISTINCTIVE_KEYS and key_present:
                raw_matches.add(f"raw:{key}")
            elif namespace_present and key_present:
                raw_matches.add(f"raw:{namespace}/{key}")
    matches = sorted(active_matches | raw_matches)
    return {
        "sha256": sha256_bytes(raw),
        "size": len(raw),
        "active_target_entries": sorted(active_matches),
        "conservative_raw_markers": sorted(raw_matches),
        "n3w_residue_present": bool(matches),
        "matched_markers": matches,
    }


def read_flash_region(port: str, offset: int, size: int, destination: Path) -> None:
    if offset < 0 or size <= 0 or offset + size > FLASH_SIZE_BYTES:
        raise StopExecution("requested read outside 8MB flash")
    run_capture(
        esptool_base()
        + [
            "--chip",
            "esp32c6",
            "--port",
            port,
            "--no-stub",
            "read-flash",
            hex(offset),
            hex(size),
            str(destination),
        ],
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash read size mismatch")


def probe_security_and_identity(port: str) -> tuple[str, str]:
    security = run_capture(
        esptool_base()
        + ["--chip", "esp32c6", "--port", port, "--no-stub", "get-security-info"],
        port=port,
    )
    if "ESP32-C6" not in security.upper():
        raise StopExecution("target is not ESP32-C6")
    mac_match = MAC_RE.search(security)
    if mac_match is None:
        raise StopExecution("ROM MAC missing")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot disabled state not proven")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption disabled state not proven")
    flash = run_capture(
        esptool_base() + ["--chip", "esp32c6", "--port", port, "--no-stub", "flash-id"],
        port=port,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash not proven")
    hardware_id = hardware_id_from_mac(mac_match.group(1))
    if hardware_id in KNOWN_BOARD_HARDWARE_IDS:
        raise StopExecution("candidate matches historical Board A or Board B")
    return hardware_id, mac_match.group(1).lower()


def write_json_private(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--release-zip", required=True)
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args()

    try:
        port = args.port
        if not port or any(ch.isspace() for ch in port):
            raise StopExecution("serial port locator invalid")

        release_path = Path(args.release_zip).expanduser().resolve()
        artifact_members = verify_release_zip(release_path)
        esptool_version = verify_esptool()

        private_dir = Path(args.private_dir).expanduser().resolve()
        private_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(private_dir, 0o700)

        hardware_id, raw_mac = probe_security_and_identity(port)
        identity_hash = public_identity_sha256(hardware_id)

        partition_path = private_dir / "partition-table-read.bin"
        read_flash_region(port, PARTITION_TABLE_OFFSET, PARTITION_TABLE_READ_SIZE, partition_path)
        partition_raw = partition_path.read_bytes()
        partition_state, entries = parse_partition_table(partition_raw)

        nvs_results: list[dict[str, object]] = []
        residue_present = False
        for index, entry in enumerate(find_nvs_partitions(entries)):
            safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", entry.label or f"nvs-{index}")
            destination = private_dir / f"nvs-{index:02d}-{safe_label}.bin"
            read_flash_region(port, entry.offset, entry.size, destination)
            raw = destination.read_bytes()
            result = inspect_nvs_partition(raw)
            result.update(
                {
                    "label": entry.label,
                    "offset": entry.offset,
                    "partition_size": entry.size,
                }
            )
            residue_present = residue_present or bool(result["n3w_residue_present"])
            nvs_results.append(result)

        private_payload = {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "port": port,
            "raw_mac": raw_mac,
            "hardware_id": hardware_id,
            "release_zip": str(release_path),
            "partition_table_file": str(partition_path),
            "nvs_files": [str(path) for path in sorted(private_dir.glob("nvs-*.bin"))],
        }
        write_json_private(private_dir / "private-evidence.json", private_payload)

        public_payload = {
            "schema": SCHEMA,
            "status": "FAIL" if residue_present else "PASS",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "board": {
                "chip": "ESP32-C6",
                "flash_size": "8MB",
                "secure_boot": False,
                "flash_encryption": False,
                "hardware_id_sha256": identity_hash,
                "hardware_id_unique_vs_board_a_b": True,
                "partition_table_state": partition_state,
                "partition_table_read_sha256": sha256_bytes(partition_raw),
                "nvs_partition_count": len(nvs_results),
                "nvs_partitions": nvs_results,
                "old_n3w_state_absent": not residue_present,
            },
            "artifact": {
                "source_head": SOURCE_HEAD,
                "source_tree": SOURCE_TREE,
                "workflow_run_id": WORKFLOW_RUN_ID,
                "artifact_id": ARTIFACT_ID,
                "artifact_name": ARTIFACT_NAME,
                "release_zip_name": RELEASE_ZIP_NAME,
                "release_zip_sha256": RELEASE_ZIP_SHA256,
                "firmware_sha256": artifact_members["firmware.bin"],
                "partitions_sha256": artifact_members["partitions.bin"],
                "otadata_sha256": artifact_members["ota_data_initial.bin"],
                "bootloader_sha256": artifact_members["bootloader.bin"],
            },
            "esptool_version": esptool_version,
            "board_access": True,
            "read_only": True,
            "flash_write": False,
            "flash_erase": False,
            "nvs_write": False,
            "t1_mutation": False,
            "manager_replay_mutation": False,
        }
        public_output = Path(args.public_output).expanduser().resolve()
        public_output.parent.mkdir(parents=True, exist_ok=True)
        public_output.write_text(
            json.dumps(public_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        public_output.chmod(0o600)

        if residue_present:
            print("CLEAN_BOARD_ELIGIBILITY_LOCAL=FAIL")
            print("OLD_N3W_STATE_ABSENT=false")
            print("ERASE_TO_MANUFACTURE_CLEAN_STATE=false")
            print("STOP=true")
            return 3

        print("CLEAN_BOARD_ELIGIBILITY_LOCAL=PASS")
        print(f"HARDWARE_ID_SHA256={identity_hash}")
        print("CHIP=ESP32-C6")
        print("FLASH_SIZE=8MB")
        print("SECURE_BOOT=false")
        print("FLASH_ENCRYPTION=false")
        print(f"PARTITION_TABLE_STATE={partition_state}")
        print(f"NVS_PARTITION_COUNT={len(nvs_results)}")
        print("OLD_N3W_STATE_ABSENT=true")
        print("FLASH_WRITE=false")
        print("FLASH_ERASE=false")
        print("T1_MUTATION=false")
        print(f"PUBLIC_OUTPUT={public_output}")
        print(f"PRIVATE_EVIDENCE_DIR={private_dir}")
        print("NEXT_CHECK=MANAGER_HISTORY_READONLY")
        return 0
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
