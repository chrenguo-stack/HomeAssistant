from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/kf089/id17_board_a_slot_state_readonly/executor.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id17_board_a_slot_state_readonly/manifest.json"

spec = importlib.util.spec_from_file_location("id17_executor", EXECUTOR)
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


def _otadata(active_seq: int, active_state: int, older_seq: int) -> bytes:
    raw = bytearray(b"\xff" * executor.OTADATA_SIZE)
    raw[0:executor.OTA_ENTRY_SIZE] = _ota_entry(older_seq, executor.OTA_STATE_VALID)
    start = 0x1000
    raw[start:start + executor.OTA_ENTRY_SIZE] = _ota_entry(active_seq, active_state)
    return bytes(raw)


def test_manifest_freezes_read_only_board_a_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id17_board_a_slot_state_readonly"
    assert manifest["target_contract"]["physical_target"] == "BOARD_A_ONLY"
    assert manifest["forbidden"]["board_b_physical_access"] is True
    assert manifest["forbidden"]["flash_write"] is True
    assert manifest["forbidden"]["otadata_write"] is True
    assert manifest["forbidden"]["ota_slot_switch"] is True
    assert manifest["ota_guard_disposition"]["guard_fully_ready"] is False
    assert manifest["ota_guard_disposition"]["id17_uses_ota_guard_mutation"] is False


def test_exact_schema5_binary_authority_is_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    refs = manifest["authority_references"]
    assert refs["schema5_source_commit"] == executor.SCHEMA5_SOURCE_COMMIT
    assert refs["schema5_firmware_size"] == executor.SCHEMA5_FIRMWARE_SIZE
    assert refs["schema5_firmware_sha256"] == executor.SCHEMA5_FIRMWARE_SHA256


def test_esptool_commands_are_rom_read_only() -> None:
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
    assert commands[0][-1] == "read-mac"
    for argv in commands[1:]:
        assert "read-flash" in argv


def test_partition_geometry_parser_accepts_exact_contract() -> None:
    parsed = executor.parse_partition_table(_partition_table())
    assert parsed["otadata"].offset == executor.OTADATA_OFFSET
    assert parsed["app0"].offset == executor.APP0_OFFSET
    assert parsed["app0"].size == executor.APP0_PARTITION_SIZE
    assert parsed["app1"].offset == executor.APP1_OFFSET
    assert parsed["app1"].size == executor.APP1_PARTITION_SIZE


def test_partition_geometry_parser_rejects_drift() -> None:
    raw = bytearray(_partition_table())
    raw[8:12] = (0x3000).to_bytes(4, "little")
    try:
        executor.parse_partition_table(bytes(raw))
    except executor.StopExecution as exc:
        assert "partition geometry mismatch" in str(exc)
    else:
        raise AssertionError("geometry drift must stop")


def test_otadata_parser_selects_highest_valid_sequence() -> None:
    snapshot = executor.parse_otadata(_otadata(active_seq=6, active_state=executor.OTA_STATE_VALID, older_seq=5))
    assert snapshot.active_seq == 6
    assert snapshot.selected_slot == 1
    assert snapshot.active_state == executor.OTA_STATE_VALID


def test_classification_prefers_slot_switch_when_inactive_is_exact() -> None:
    ota = executor.parse_otadata(_otadata(active_seq=6, active_state=executor.OTA_STATE_VALID, older_seq=5))
    result = executor.classify(
        ota=ota,
        app0_sha=executor.SCHEMA5_FIRMWARE_SHA256,
        app1_sha="0" * 64,
    )
    assert result["selected_slot"] == 1
    assert result["inactive_slot"] == 0
    assert result["inactive_slot_exact_schema5"] is True
    assert result["next_route"] == "PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE"


def test_classification_requests_deployment_when_neither_slot_is_exact() -> None:
    ota = executor.parse_otadata(_otadata(active_seq=6, active_state=executor.OTA_STATE_VALID, older_seq=5))
    result = executor.classify(ota=ota, app0_sha="1" * 64, app1_sha="2" * 64)
    assert result["active_slot_exact_schema5"] is False
    assert result["inactive_slot_exact_schema5"] is False
    assert result["next_route"] == "PREPARE_BOARD_A_INACTIVE_SLOT_SCHEMA5_DEPLOYMENT_PACKAGE"


def test_canonical_base_mac_parser_ignores_generic_mac_line() -> None:
    base = ":".join(["98", "a3", "16", "a9", "f3", "50"])
    generic = ":".join(["00"] * 6)
    output = "MAC: " + generic + "\nBASE MAC: " + base + "\n"
    parsed = executor.parse_base_mac(output)
    assert executor.mac_suffix(parsed) == executor.EXPECTED_BOARD_A_SUFFIX
