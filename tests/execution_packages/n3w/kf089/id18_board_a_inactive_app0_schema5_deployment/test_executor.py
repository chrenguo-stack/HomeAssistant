from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[5]
ENTRY = ROOT / "tools/execution_packages/n3w/kf089/id18_board_a_inactive_app0_schema5_deployment/executor.py"
IMPL = ROOT / "tools/execution_packages/n3w/kf089/id18_board_a_inactive_app0_schema5_deployment/executor_impl.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id18_board_a_inactive_app0_schema5_deployment/manifest.json"

spec = importlib.util.spec_from_file_location("id18_executor_impl_test", IMPL)
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


def test_manifest_freezes_direct_rom_app0_only_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id18_board_a_inactive_app0_schema5_deployment"
    assert manifest["target_contract"]["target_slot"] == 0
    assert manifest["target_contract"]["rollback_slot"] == 1
    assert manifest["mutation_contract"]["slot_switch_in_same_gate"] is False
    assert manifest["tool_bindings"]["stock_high_level_write_flash_used"] is False
    assert manifest["tool_bindings"]["flash_finish_used"] is False
    assert manifest["forbidden"]["ota_slot_switch"] is True
    assert manifest["forbidden"]["otadata_write"] is True
    assert manifest["forbidden"]["app1_write"] is True
    assert manifest["forbidden"]["whole_image_mutation_retry"] is True


def test_exact_schema5_authority_is_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    refs = manifest["authority_references"]
    assert refs["schema5_source_commit"] == executor.SCHEMA5_SOURCE_COMMIT
    assert refs["schema5_firmware_size"] == executor.SCHEMA5_FIRMWARE_SIZE
    assert refs["schema5_firmware_sha256"] == executor.SCHEMA5_FIRMWARE_SHA256
    assert refs["esptool_5_3_1_commit"] == "0d2dfefe029eb48c23ddde61f9118b32d39dc7b9"


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


def test_entrypoint_ast_rejects_no_prohibited_impl_calls() -> None:
    source = IMPL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    prohibited = {"write_" + "flash", "flash_" + "finish"}
    observed = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert observed.isdisjoint(prohibited)
    assert {"flash_begin", "flash_block", "flash_md5sum"}.issubset(observed)


def test_entrypoint_self_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENTRY), "--self-check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["self_check"] == "PASS"


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


def test_esptool_cfg_binds_block_retry_to_one(tmp_path: Path) -> None:
    executor.ensure_private_dir(tmp_path)
    cfg = executor.make_esptool_cfg(tmp_path)
    text = cfg.read_text(encoding="utf-8")
    assert "connect_attempts = 1" in text
    assert "write_block_attempts = 1" in text
    assert "open_port_attempts = 1" in text

    code = (
        "import os; "
        f"os.environ['ESPTOOL_CFGFILE']={str(cfg)!r}; "
        "import esptool, esptool.loader as loader; "
        "print(esptool.__version__, loader.WRITE_BLOCK_ATTEMPTS, loader.ESPLoader.WRITE_FLASH_ATTEMPTS)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "5.3.1 1 2"


def test_direct_rom_mutation_sends_each_block_once_and_never_finishes(
    tmp_path: Path, monkeypatch,
) -> None:
    fake_data = (b"schema5-test-payload-" * 130)[:2500]
    fake_size = len(fake_data)
    fake_sha = hashlib.sha256(fake_data).hexdigest()
    monkeypatch.setattr(executor, "SCHEMA5_FIRMWARE_SIZE", fake_size)
    monkeypatch.setattr(executor, "SCHEMA5_FIRMWARE_SHA256", fake_sha)

    firmware = tmp_path / "firmware.bin"
    pre_app0 = tmp_path / "pre_app0.bin"
    pre_app1 = tmp_path / "pre_app1.bin"
    firmware.write_bytes(fake_data)
    pre_app0.write_bytes(b"A" * fake_size)
    pre_app1.write_bytes(b"B" * fake_size)
    pre_otadata = b"C" * executor.OTADATA_SIZE

    expected_pre_app0_md5 = executor.md5_file(pre_app0)
    expected_pre_app1_md5 = executor.md5_file(pre_app1)
    expected_pre_ota_md5 = executor.md5_bytes(pre_otadata)
    expected_post_md5 = executor.md5_bytes(fake_data)
    base_mac = ":".join(["98", "a3", "16", "a9", "f3", "50"])

    class FakeEsp:
        IS_STUB = False
        sync_stub_detected = False
        secure_download_mode = False

        def __init__(self):
            self.blocks: list[tuple[int, bytes]] = []
            self.connect_calls: list[tuple[str, int]] = []
            self.begin_calls: list[tuple[int, int]] = []
            self.flash_params: list[int] = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def connect(self, *, mode: str, attempts: int):
            self.connect_calls.append((mode, attempts))

        def read_mac(self, kind: str):
            assert kind == "BASE_MAC"
            return tuple(int(part, 16) for part in base_mac.split(":"))

        def flash_set_parameters(self, size: int):
            self.flash_params.append(size)

        def flash_md5sum(self, offset: int, size: int):
            if offset == executor.APP0_OFFSET:
                return expected_post_md5 if self.blocks else expected_pre_app0_md5
            if offset == executor.OTADATA_OFFSET:
                return expected_pre_ota_md5
            if offset == executor.APP1_OFFSET:
                return expected_pre_app1_md5
            raise AssertionError("unexpected md5 geometry")

        def flash_begin(self, size: int, offset: int):
            self.begin_calls.append((size, offset))
            return (size + executor.EXPECTED_FLASH_WRITE_SIZE - 1) // executor.EXPECTED_FLASH_WRITE_SIZE

        def flash_block(self, block: bytes, seq: int):
            self.blocks.append((seq, block))

    fake = FakeEsp()
    runtime = {
        "ESP32C6ROM": lambda port, baud: fake,
        "attach_flash": lambda esp: None,
        "flash_write_size": executor.EXPECTED_FLASH_WRITE_SIZE,
    }
    evidence = tmp_path / "evidence"
    executor.ensure_private_dir(evidence)
    executor.direct_write_app0_once(
        runtime=runtime,
        root=evidence,
        port="/dev/example",
        expected_base_mac=base_mac,
        firmware=firmware,
        pre_app0=pre_app0,
        pre_otadata=pre_otadata,
        pre_app1=pre_app1,
    )

    expected_blocks = (
        fake_size + executor.EXPECTED_FLASH_WRITE_SIZE - 1
    ) // executor.EXPECTED_FLASH_WRITE_SIZE
    assert fake.connect_calls == [("no-reset", 1)]
    assert fake.begin_calls == [(fake_size, executor.APP0_OFFSET)]
    assert [seq for seq, _ in fake.blocks] == list(range(expected_blocks))
    assert all(len(block) == executor.EXPECTED_FLASH_WRITE_SIZE for _, block in fake.blocks)
    completion = json.loads((evidence / "direct_rom_mutation_completion.json").read_text())
    assert completion["flash_finish_used"] is False


def test_canonical_base_mac_parser_ignores_generic_mac_line() -> None:
    base = ":".join(["98", "a3", "16", "a9", "f3", "50"])
    generic = ":".join(["00"] * 6)
    output = "MAC: " + generic + "\nBASE MAC: " + base + "\n"
    parsed = executor.parse_base_mac(output)
    assert executor.mac_suffix(parsed) == executor.EXPECTED_BOARD_A_SUFFIX
