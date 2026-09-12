from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/kf089/id18_board_a_inactive_app0_schema5_deployment/executor.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id18_board_a_inactive_app0_schema5_deployment/manifest.json"

spec = importlib.util.spec_from_file_location("id18_executor", EXECUTOR)
assert spec and spec.loader
executor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = executor
spec.loader.exec_module(executor)


def _partition_entry(ptype: int, subtype: int, offset: int, size: int, label: str) -> bytes:
    raw = bytearray(32)
    raw[0:2] = executor.PARTITION_MAGIC.to_bytes(2, "little")
    raw[2] = ptype
    raw[3] = subtype
    raw[4:8] = offset.to_bytes(4, "little")
    raw[8:12] = size.to_bytes(4, "little")
    encoded = label.encode("ascii")
    raw[12:12 + len(encoded)] = encoded
    return bytes(raw)


def _partition_table() -> bytes:
    raw = bytearray(b"\xff" * executor.PARTITION_TABLE_SIZE)
    entries = [
        _partition_entry(
            executor.PARTITION_TYPE_DATA,
            executor.PARTITION_SUBTYPE_OTA_DATA,
            executor.OTADATA_OFFSET,
            executor.OTADATA_SIZE,
            "otadata",
        ),
        _partition_entry(
            executor.PARTITION_TYPE_APP,
            executor.PARTITION_SUBTYPE_OTA0,
            executor.APP0_OFFSET,
            executor.APP0_PARTITION_SIZE,
            "app0",
        ),
        _partition_entry(
            executor.PARTITION_TYPE_APP,
            executor.PARTITION_SUBTYPE_OTA1,
            executor.APP1_OFFSET,
            executor.APP1_PARTITION_SIZE,
            "app1",
        ),
    ]
    for index, entry in enumerate(entries):
        raw[index * 32:(index + 1) * 32] = entry
    return bytes(raw)


def _ota_entry(seq: int, state: int) -> bytes:
    raw = bytearray(b"\xff" * executor.OTA_ENTRY_SIZE)
    struct.pack_into("<I", raw, 0, seq)
    struct.pack_into("<I", raw, 24, state)
    struct.pack_into("<I", raw, 28, executor.ota_crc(seq))
    return bytes(raw)


def _otadata(active_seq: int = 4, active_state: int = 2, older_seq: int = 3) -> bytes:
    raw = bytearray(b"\xff" * executor.OTADATA_SIZE)
    raw[0:executor.OTA_ENTRY_SIZE] = _ota_entry(older_seq, executor.OTA_STATE_INVALID)
    start = 0x1000
    raw[start:start + executor.OTA_ENTRY_SIZE] = _ota_entry(active_seq, active_state)
    return bytes(raw)


def test_manifest_freezes_app0_only_mutation_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id18_board_a_inactive_app0_schema5_deployment"
    assert manifest["target_contract"]["target_slot"] == 0
    assert manifest["target_contract"]["rollback_slot"] == 1
    assert manifest["mutation_contract"]["slot_switch_in_same_gate"] is False
    assert manifest["forbidden"]["ota_slot_switch"] is True
    assert manifest["forbidden"]["otadata_write"] is True
    assert manifest["forbidden"]["app1_write"] is True
    assert manifest["forbidden"]["auto_retry"] is True


def test_exact_schema5_authority_is_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    refs = manifest["authority_references"]
    assert refs["schema5_source_commit"] == executor.SCHEMA5_SOURCE_COMMIT
    assert refs["schema5_firmware_size"] == executor.SCHEMA5_FIRMWARE_SIZE
    assert refs["schema5_firmware_sha256"] == executor.SCHEMA5_FIRMWARE_SHA256


def test_read_commands_remain_rom_read_only() -> None:
    commands = [
        executor.build_read_mac_command("/dev/example"),
        executor.build_read_flash_command(
            "/dev/example", executor.PARTITION_TABLE_OFFSET,
            executor.PARTITION_TABLE_SIZE, Path("/tmp/pt.bin")
        ),
        executor.build_read_flash_command(
            "/dev/example", executor.OTADATA_OFFSET,
            executor.OTADATA_SIZE, Path("/tmp/ota.bin")
        ),
        executor.build_read_flash_command(
            "/dev/example", executor.APP0_OFFSET,
            executor.SCHEMA5_FIRMWARE_SIZE, Path("/tmp/app0.bin")
        ),
        executor.build_read_flash_command(
            "/dev/example", executor.APP1_OFFSET,
            executor.SCHEMA5_FIRMWARE_SIZE, Path("/tmp/app1.bin")
        ),
    ]
    for argv in commands:
        assert "--before" in argv and "no-reset" in argv
        assert "--after" in argv
        assert "--no-stub" in argv
        executor.assert_read_only_argv(argv)


def test_mutation_command_is_exactly_one_app0_write() -> None:
    firmware = Path("/tmp/exact-schema5.bin")
    argv = executor.build_app0_write_command("/dev/example", firmware)
    assert argv.count("write-flash") == 1
    assert hex(executor.APP0_OFFSET) in argv
    assert str(firmware) in argv
    assert hex(executor.OTADATA_OFFSET) not in argv
    assert hex(executor.APP1_OFFSET) not in argv
    assert "erase-flash" not in argv
    assert "erase-region" not in argv
    assert "switch_ota_partition" not in argv


def test_partition_geometry_accepts_exact_contract() -> None:
    parsed = executor.parse_partition_table(_partition_table())
    assert parsed["otadata"].offset == executor.OTADATA_OFFSET
    assert parsed["app0"].offset == executor.APP0_OFFSET
    assert parsed["app0"].size == executor.APP0_PARTITION_SIZE
    assert parsed["app1"].offset == executor.APP1_OFFSET
    assert parsed["app1"].size == executor.APP1_PARTITION_SIZE


def test_id17_prestate_is_required() -> None:
    ota = executor.parse_otadata(_otadata())
    assert ota.selected_slot == 1
    assert ota.active_seq == 4
    assert ota.active_state == 2
    executor.verify_expected_prestate(ota)


def test_prestate_rejects_slot_drift() -> None:
    # seq 5 selects slot 0 in the two-slot mapping.
    raw = bytearray(b"\xff" * executor.OTADATA_SIZE)
    raw[0:executor.OTA_ENTRY_SIZE] = _ota_entry(5, 2)
    ota = executor.parse_otadata(bytes(raw))
    try:
        executor.verify_expected_prestate(ota)
    except executor.StopExecution as exc:
        assert "selected OTA slot drifted" in str(exc)
    else:
        raise AssertionError("slot drift must stop")


def test_firmware_binding_requires_exact_size_and_hash(tmp_path: Path) -> None:
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"not-the-real-image")
    try:
        executor.verify_firmware(firmware)
    except executor.StopExecution as exc:
        assert "size mismatch" in str(exc)
    else:
        raise AssertionError("wrong firmware must stop")


def test_esptool_cfg_bounds_connection_and_block_attempts(tmp_path: Path) -> None:
    executor.ensure_private_dir(tmp_path)
    cfg = executor.make_esptool_cfg(tmp_path)
    text = cfg.read_text(encoding="utf-8")
    assert "connect_attempts = 1" in text
    assert "write_block_attempts = 1" in text
    assert "open_port_attempts = 1" in text


def test_canonical_base_mac_parser_ignores_generic_mac_line() -> None:
    base = ":".join(["98", "a3", "16", "a9", "f3", "50"])
    generic = ":".join(["00"] * 6)
    output = "MAC: " + generic + "\nBASE MAC: " + base + "\n"
    parsed = executor.parse_base_mac(output)
    assert executor.mac_suffix(parsed) == executor.EXPECTED_BOARD_A_SUFFIX
