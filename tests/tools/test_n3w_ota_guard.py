from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "n3w_ota_guard.py"
spec = importlib.util.spec_from_file_location("n3w_ota_guard", MODULE_PATH)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def entry(seq: int, state: int, label: bytes = b"L" * 20) -> bytes:
    crc = m.esp_ota_crc(seq)
    return struct.pack("<I", seq) + label + struct.pack("<II", state, crc)


def otadata(copy0: bytes, copy1: bytes) -> bytes:
    a = bytearray(b"\xff" * m.OTADATA_SECTOR_SIZE)
    b = bytearray(b"\xff" * m.OTADATA_SECTOR_SIZE)
    a[:32] = copy0
    b[:32] = copy1
    return bytes(a + b)


def active_app1(target_state: int | None = None) -> bytes:
    if target_state is None:
        target_state = int(m.OtaState.UNDEFINED)
    return otadata(
        entry(1, target_state, b"A" * 20),
        entry(2, int(m.OtaState.UNDEFINED), b"B" * 20),
    )


def frozen_binding(tmp_path: Path) -> m.AppPayloadBinding:
    return m.AppPayloadBinding(
        slot=m.APP0_SLOT,
        offset=m.APP0_OFFSET,
        size=m.APP0_PAYLOAD_SIZE,
        sha256=m.APP0_EXPECTED_SHA256,
        source_path=str(tmp_path / "verified-app0.bin"),
    )


def test_crc_matches_idf_formula():
    import binascii
    seq = 3
    expected = binascii.crc32(struct.pack("<I", seq), 0xFFFFFFFF) & 0xFFFFFFFF
    assert m.esp_ota_crc(seq) == expected


def test_parse_selects_highest_valid_sequence():
    snap = m.parse_otadata(active_app1())
    assert snap.active_index == 1
    assert snap.selected_slot == 1


def test_parse_rejects_equal_valid_sequences():
    raw = otadata(entry(1, int(m.OtaState.UNDEFINED)), entry(1, int(m.OtaState.UNDEFINED)))
    with pytest.raises(m.GuardError, match="equal ota_seq"):
        m.parse_otadata(raw)


def test_parse_rejects_unknown_state():
    raw = otadata(entry(1, 0x12345678), entry(2, int(m.OtaState.UNDEFINED)))
    with pytest.raises(m.GuardError, match="unknown ota_state"):
        m.parse_otadata(raw)


def test_plan_preserves_state_and_label_and_changes_only_seq_crc(tmp_path: Path):
    pre = active_app1(target_state=int(m.OtaState.VALID))
    p = m.plan_ota_switch_to_app0(pre, frozen_binding(tmp_path))
    assert p.new_seq == 3
    assert p.preserved_ota_state == int(m.OtaState.VALID)
    assert p.entry_image[4:24] == b"A" * 20
    assert struct.unpack_from("<I", p.entry_image, 24)[0] == int(m.OtaState.VALID)
    for start, end in p.changed_entry_byte_ranges:
        assert (0 <= start and end <= 4) or (28 <= start and end <= 32)


def test_plan_requires_frozen_app0_binding(tmp_path: Path):
    bad = m.AppPayloadBinding(0, m.APP0_OFFSET, m.APP0_PAYLOAD_SIZE, "00" * 32, str(tmp_path / "x"))
    with pytest.raises(m.GuardError, match="frozen firmware authority"):
        m.plan_ota_switch_to_app0(active_app1(), bad)


def test_plan_rejects_if_app0_already_selected(tmp_path: Path):
    pre = otadata(entry(3, int(m.OtaState.UNDEFINED)), entry(2, int(m.OtaState.UNDEFINED)))
    with pytest.raises(m.GuardError, match="already selected"):
        m.plan_ota_switch_to_app0(pre, frozen_binding(tmp_path))


def test_postverify_accepts_erase_plus_32_byte_write(tmp_path: Path):
    pre = active_app1()
    p = m.plan_ota_switch_to_app0(pre, frozen_binding(tmp_path))
    post = bytearray(pre)
    rel = m.OTADATA_COPY_OFFSETS[p.target_copy_index]
    post[rel:rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
    post[rel:rel + 32] = p.entry_image
    m.verify_ota_switch(pre, bytes(post), p)


def test_postverify_rejects_non_target_change(tmp_path: Path):
    pre = active_app1()
    p = m.plan_ota_switch_to_app0(pre, frozen_binding(tmp_path))
    post = bytearray(pre)
    rel = m.OTADATA_COPY_OFFSETS[p.target_copy_index]
    post[rel:rel + m.OTADATA_SECTOR_SIZE] = b"\xff" * m.OTADATA_SECTOR_SIZE
    post[rel:rel + 32] = p.entry_image
    other = m.OTADATA_COPY_OFFSETS[1 - p.target_copy_index]
    post[other + 0x100] ^= 1
    with pytest.raises(m.GuardError, match="non-target"):
        m.verify_ota_switch(pre, bytes(post), p)


def test_app0_read_argv_has_exact_reset_and_flash_contract():
    argv = m.build_app0_read_command("/python", "/idf/esptool.py", "/dev/cu.X", "/tmp/app0.bin")
    m.validate_esptool_argv(argv)
    sub = argv.index("read-flash")
    assert argv[argv.index("--before") + 1] == "no-reset"
    assert argv[argv.index("--after") + 1] == "no-reset"
    assert argv[argv.index("--connect-attempts") + 1] == "1"
    assert "--no-stub" in argv[:sub]
    assert argv[sub + 1:sub + 3] == ["--flash-size", "8MB"]
    assert argv[sub + 3:sub + 6] == [hex(m.APP0_OFFSET), str(m.APP0_PAYLOAD_SIZE), "/tmp/app0.bin"]


def test_validator_rejects_hard_reset():
    argv = m.build_identity_read_command("/python", "/idf/esptool.py", "/dev/cu.X")
    argv[argv.index("no-reset")] = "hard-reset"
    with pytest.raises(m.GuardError):
        m.validate_esptool_argv(argv)


def test_otadata_write_is_exactly_target_copy_start(tmp_path: Path):
    p = m.plan_ota_switch_to_app0(active_app1(), frozen_binding(tmp_path))
    argv = m.build_otadata_entry_write_command("/python", "/idf/esptool.py", "/dev/cu.X", p, "/tmp/e.bin")
    idx = argv.index("write-flash")
    assert argv[idx + 3] == hex(p.target_entry_flash_offset)
    assert p.target_entry_flash_offset in (0x9000, 0xA000)
    assert len(p.entry_image) == 32


def test_identity_output_requires_expected_mac():
    ok = m.verify_identity_output("MAC: 98:a3:16:a9:f4:5c", "98:A3:16:A9:F4:5C")
    assert ok.observed_base_mac == "98:a3:16:a9:f4:5c"
    with pytest.raises(m.GuardError, match="mismatch"):
        m.verify_identity_output("MAC: 98:a3:16:a9:f3:50", "98:a3:16:a9:f4:5c")


def test_evidence_store_refuses_nonempty_directory(tmp_path: Path):
    d = tmp_path / "ev"
    d.mkdir()
    (d / "old").write_text("x")
    with pytest.raises(m.GuardError, match="not empty"):
        m.EvidenceStore(d)


def test_recovery_cli_has_no_app0_write_command():
    help_text = m._parser().format_help()
    assert "write-app0" not in help_text


def test_esptool_retry_config_is_single_attempt(tmp_path: Path):
    store = m.EvidenceStore(tmp_path / "ev")
    cfg = store.ensure_esptool_config().read_text()
    assert "connect_attempts = 1" in cfg
    assert "write_block_attempts = 1" in cfg


def test_repo_layout_import_path_is_real():
    assert MODULE_PATH.is_file()


def test_workflow_source_contains_recovery_no_write_guard():
    text = MODULE_PATH.read_text()
    assert '"app0_write_allowed": False' in text
    assert "execute_recovery_app0_to_slot0" in text


def test_tool_status_is_review():
    assert m.TOOL_VERSION == "0.2.0-review"
