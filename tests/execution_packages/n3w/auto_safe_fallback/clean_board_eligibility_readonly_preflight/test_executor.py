from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/clean_board_eligibility_readonly_preflight/executor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("clean_board_preflight_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_partition_entry(label: str, type_value: int, subtype: int, offset: int, size: int) -> bytes:
    record = bytearray(b"\xff" * 32)
    record[0:2] = (0x50AA).to_bytes(2, "little")
    record[2] = type_value
    record[3] = subtype
    record[4:8] = offset.to_bytes(4, "little")
    record[8:12] = size.to_bytes(4, "little")
    encoded = label.encode("ascii")
    record[12 : 12 + len(encoded)] = encoded
    record[12 + len(encoded)] = 0
    record[28:32] = (0).to_bytes(4, "little")
    return bytes(record)


def mark_written(bitmap: bytearray, index: int) -> None:
    shift = (index % 4) * 2
    pos = index // 4
    bitmap[pos] &= ~(0x03 << shift)
    bitmap[pos] |= 0x02 << shift


def make_nvs_page(namespace: str, key: str) -> bytes:
    page = bytearray(b"\xff" * 4096)
    bitmap = bytearray(b"\xff" * 32)
    mark_written(bitmap, 0)
    mark_written(bitmap, 1)
    page[32:64] = bitmap

    namespace_entry = bytearray(b"\x00" * 32)
    namespace_entry[0] = 0
    namespace_entry[1] = 0x01
    namespace_entry[2] = 1
    namespace_bytes = namespace.encode("ascii")
    namespace_entry[8 : 8 + len(namespace_bytes)] = namespace_bytes
    namespace_entry[24] = 1
    page[64:96] = namespace_entry

    value_entry = bytearray(b"\x00" * 32)
    value_entry[0] = 1
    value_entry[1] = 0x42
    value_entry[2] = 1
    key_bytes = key.encode("ascii")
    value_entry[8 : 8 + len(key_bytes)] = key_bytes
    page[96:128] = value_entry
    return bytes(page)


def test_partition_table_blank_and_valid_nvs():
    module = load_module()
    state, entries = module.parse_partition_table(b"\xff" * module.PARTITION_TABLE_READ_SIZE)
    assert state == "BLANK"
    assert entries == []

    raw = bytearray(b"\xff" * module.PARTITION_TABLE_READ_SIZE)
    raw[0:32] = make_partition_entry("nvs", 0x01, 0x02, 0x9000, 0x6000)
    raw[32:64] = make_partition_entry("factory", 0x00, 0x00, 0x10000, 0x200000)
    state, entries = module.parse_partition_table(bytes(raw))
    assert state == "VALID"
    nvs = module.find_nvs_partitions(entries)
    assert len(nvs) == 1
    assert nvs[0].label == "nvs"
    assert nvs[0].offset == 0x9000
    assert nvs[0].size == 0x6000


def test_nvs_target_residue_is_detected():
    module = load_module()
    result = module.inspect_nvs_partition(make_nvs_page("gh_n3w_v2", "peer"))
    assert result["n3w_residue_present"] is True
    assert "gh_n3w_v2/peer" in result["active_target_entries"]


def test_nvs_boot_state_residue_is_detected():
    module = load_module()
    result = module.inspect_nvs_partition(make_nvs_page("gh_n3w", "boot_state"))
    assert result["n3w_residue_present"] is True
    assert "gh_n3w/boot_state" in result["active_target_entries"]


def test_unrelated_nvs_is_clean():
    module = load_module()
    result = module.inspect_nvs_partition(make_nvs_page("vendor_cfg", "setup"))
    assert result["n3w_residue_present"] is False
    assert result["active_target_entries"] == []
    assert result["conservative_raw_markers"] == []


def test_executor_has_no_esptool_mutation_subcommands():
    source = EXECUTOR.read_text(encoding="utf-8")
    forbidden = [
        '"write-flash"',
        '"erase-flash"',
        '"erase-region"',
        '"write_flash"',
        '"erase_flash"',
        '"erase_region"',
    ]
    for marker in forbidden:
        assert marker not in source


def test_rom_mac_is_only_a_silicon_binding():
    module = load_module()
    binding = module.silicon_binding_from_rom_mac("11:22:33:44:55:66")
    assert binding == "rom-c6-112233445566"
    assert module.public_binding_sha256(binding)
    assert module.SCHEMA.endswith("/2")


def test_public_contract_defers_runtime_product_identity():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert '"silicon_binding_sha256": silicon_binding_hash' in source
    assert '"product_hardware_id_sha256": None' in source
    assert "DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING" in source
    assert "HARDWARE_ID_SHA256={identity_hash}" not in source
    assert "NEXT_CHECK=PRODUCT_RUNTIME_IDENTITY_BINDING_AFTER_FIRST_BOOT" in source


def test_frozen_release_binding():
    module = load_module()
    assert module.SOURCE_HEAD == "157448b621f288c5ac5038e7a1ac906cf2575a7f"
    assert module.SOURCE_TREE == "f45ca257de0b6e41f0458346711bb4e105ba1fcc"
    assert module.ARTIFACT_ID == 11320812037
    assert module.RELEASE_ZIP_SHA256 == "44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff"
    assert module.FIRMWARE_SHA256 == "4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b"
