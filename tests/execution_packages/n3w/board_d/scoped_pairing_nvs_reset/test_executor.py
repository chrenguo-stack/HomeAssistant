from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/board_d/scoped_pairing_nvs_reset/executor.py"
spec = importlib.util.spec_from_file_location("board_d_scoped_pairing_nvs_reset", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_board_d_scope() -> None:
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"
    assert module.EXPECTED_BOOTLOADER_SHA256 == "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46"
    assert module.EXPECTED_PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    assert module.NVS_OFFSET == 0x790000
    assert module.NVS_SIZE == 0x70000
    assert module.ERASED_SHA256


def test_executor_forbids_broad_flash_mutation() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"erase-flash"' not in source
    assert '"write-flash"' not in source
    assert "FULL_FLASH_ERASE=false" in source
    assert "APPLICATION_FLASH_REWRITE=false" in source


def test_claim_precedes_exact_scoped_erase() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    claim = source.index("write_private_json(claim_path, claim)")
    erase = source.index("erase_nvs_noreset(args.port)")
    erased_readback = source.index(
        "noreset_read(args.port, NVS_OFFSET, NVS_SIZE, erased, before_no_reset=True)"
    )
    oracle = source.index('raise StopExecution("preboot erased NVS oracle failed")')
    closed = source.index('"status": "CLOSED_PASS_PREBOOT"')
    assert claim < erase < erased_readback < oracle < closed


def test_erase_command_uses_exact_range_and_no_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_capture(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        return "PASS"

    monkeypatch.setattr(module.base, "run_capture", fake_run_capture)
    monkeypatch.setattr(module.base, "esptool_base", lambda: ["python3", "-m", "esptool"])

    module.erase_nvs_noreset("/dev/cu.usbmodem14101")

    assert len(calls) == 1
    command = calls[0]
    assert "--after" in command
    assert command[command.index("--after") + 1] == "no-reset"
    assert "erase-region" in command
    position = command.index("erase-region")
    assert command[position + 1 : position + 3] == ["0x790000", "0x70000"]
    assert "erase-flash" not in command
    assert "write-flash" not in command


def test_preboot_readback_does_not_start_application(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run_capture(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        destination = Path(args[-1])
        size = int(args[-2], 0)
        destination.write_bytes(b"\xff" * size)
        return "PASS"

    monkeypatch.setattr(module.base, "run_capture", fake_run_capture)
    monkeypatch.setattr(module.base, "esptool_base", lambda: ["python3", "-m", "esptool"])

    output = tmp_path / "readback.bin"
    observed = module.noreset_read(
        "/dev/cu.usbmodem14101",
        module.NVS_OFFSET,
        module.NVS_SIZE,
        output,
        before_no_reset=True,
    )

    assert observed == module.ERASED_SHA256
    assert module.non_ff_count(output) == 0
    command = calls[0]
    assert command[command.index("--before") + 1] == "no-reset"
    assert command[command.index("--after") + 1] == "no-reset"
    assert "read-flash" in command


def test_preflight_rejects_reused_or_mismatched_board_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        """{
  "schema": "n3w.board-d.post-r4-write-target-preflight/1",
  "status": "PASS",
  "created_at": "2026-10-25T15:06:08+00:00",
  "persistent_mutation": false,
  "flash_write": false,
  "nvs_write": false,
  "write_command_present": false,
  "write_authorization_granted": false,
  "board": {
    "hardware_id_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "bootloader_sha256": "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46",
    "partition_table_sha256": "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca",
    "bootloader_matches_release": true,
    "partition_table_matches_release": true,
    "port_sha256": "3dbd58fb2a751780ce45dab2216fc0ffbcb9e70e8ff0a6fe00c85bd0055420b5"
  }
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: module.dt.datetime(
            2026,
            10,
            25,
            15,
            7,
            tzinfo=module.dt.timezone.utc,
        ),
    )

    with pytest.raises(module.StopExecution, match="Board D identity"):
        module.require_preflight(preflight, "/dev/cu.usbmodem14101")
