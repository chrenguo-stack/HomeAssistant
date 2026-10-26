from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/board_d/r4_dual_slot_normalization_write/executor.py"
spec = importlib.util.spec_from_file_location("board_d_r4_dual_slot_write", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_board(port: str = "/dev/cu.usbmodem-test") -> dict[str, object]:
    return {
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "port_sha256": module.sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(module.PARTITION_TABLE_OFFSET),
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "bootloader_offset": hex(module.BOOTLOADER_OFFSET),
        "bootloader_sha256": "0" * 64,
        "bootloader_matches_release": False,
        "phy_init_offset": hex(module.PHY_INIT_OFFSET),
        "phy_init_size": module.PHY_INIT_SIZE,
        "phy_init_sha256": "1" * 64,
        "nvs_offset": hex(module.NVS_OFFSET),
        "nvs_size": module.NVS_SIZE,
        "nvs_sha256": "2" * 64,
    }


def sample_preflight(port: str = "/dev/cu.usbmodem-test") -> dict[str, object]:
    erase_ranges = {
        name: [hex(start), hex(end)]
        for name, (start, end) in module.validate_write_erase_boundaries().items()
    }
    return {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": dt.datetime(2026, 10, 23, 8, 20, tzinfo=dt.timezone.utc).isoformat(),
        "esptool_version": "5.3.1",
        "board": sample_board(port),
        "artifact": module.artifact_binding_payload(),
        "selected_write_route": module.SELECTED_WRITE_ROUTE,
        "normalized_slot": module.normalized_slot_binding_payload(),
        "erase_ranges": erase_ranges,
        "manual_reset_allowed_before_claim": True,
        "manual_reset_allowed_after_claim": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
        "persistent_mutation": False,
    }


def test_frozen_identity_route_and_offsets() -> None:
    assert module.SCHEMA_PREFLIGHT.endswith("/3")
    assert module.SCHEMA_WRITE.endswith("/3")
    assert module.ROM_FLASH_SIZE == "8MB"
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55"
    assert module.SELECTED_WRITE_ROUTE == "DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA"
    assert module.BOOTLOADER_OFFSET == 0x0
    assert module.PARTITION_TABLE_OFFSET == 0x8000
    assert module.OTADATA_OFFSET == 0x9000
    assert module.PHY_INIT_OFFSET == 0xB000
    assert module.APP0_OFFSET == 0x10000
    assert module.APP1_OFFSET == 0x3D0000
    assert module.NVS_OFFSET == 0x790000
    assert module.OTA_SLOT_SIZE == 0x3C0000
    assert module.APP0_OFFSET + module.OTA_SLOT_SIZE == module.APP1_OFFSET
    assert module.APP1_OFFSET + module.OTA_SLOT_SIZE == module.NVS_OFFSET


def test_normalized_slot_binding_is_frozen() -> None:
    binding = module.normalized_slot_binding_payload()
    assert binding["size"] == 0x3C0000
    assert binding["sha256"] == "539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195"
    assert binding["tail_size"] == 0x266E10
    assert binding["tail_sha256"] == "50b46211550f22ac7f9bcb795c7a784f2a14f96de618032f600e722f0418b12e"


def test_write_erase_ranges_are_exact_and_non_overlapping() -> None:
    erased = module.validate_write_erase_boundaries()
    assert erased == {
        "bootloader": (0x0, 0x6000),
        "otadata": (0x9000, 0xB000),
        "app0": (0x10000, 0x3D0000),
        "app1": (0x3D0000, 0x790000),
    }


def test_derive_normalized_slot_pads_with_ff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    application = tmp_path / "firmware.bin"
    application.write_bytes(b"abc")
    expected = b"abc" + b"\xff" * 5
    monkeypatch.setitem(
        module.MEMBER_BINDINGS,
        "firmware.bin",
        (3, hashlib.sha256(b"abc").hexdigest()),
    )
    monkeypatch.setattr(module, "OTA_SLOT_SIZE", 8)
    monkeypatch.setattr(module, "NORMALIZED_SLOT_SHA256", hashlib.sha256(expected).hexdigest())
    destination = tmp_path / "slot.bin"
    result = module.derive_normalized_slot(application, destination)
    assert result == destination
    assert destination.read_bytes() == expected


def test_validate_otadata_erased_accepts_only_all_ff(tmp_path: Path) -> None:
    path = tmp_path / "ota.bin"
    path.write_bytes(b"\xff" * module.MEMBER_BINDINGS["ota_data_initial.bin"][0])
    module.validate_otadata_erased(path)
    data = bytearray(path.read_bytes())
    data[-1] = 0
    path.write_bytes(data)
    with pytest.raises(module.StopExecution, match="not the expected erased state"):
        module.validate_otadata_erased(path)


def test_build_write_command_is_exactly_dual_slot_and_uses_keep() -> None:
    files = {
        "bootloader.bin": Path("/tmp/bootloader.bin"),
        "ota_data_initial.bin": Path("/tmp/ota_data_initial.bin"),
    }
    slot = Path("/tmp/normalized_slot.bin")
    command = module.build_write_command("/dev/cu.usbmodem-test", files, slot)
    joined = " ".join(command)
    assert "write-flash" in command
    before_index = command.index("--before")
    after_index = command.index("--after")
    assert command[before_index + 1] == "no-reset"
    assert command[after_index + 1] == "no-reset-stub"
    assert "--flash-mode keep" in joined
    assert "--flash-freq keep" in joined
    assert "--flash-size keep" in joined
    assert "0x0 /tmp/bootloader.bin" in joined
    assert "0x9000 /tmp/ota_data_initial.bin" in joined
    assert "0x10000 /tmp/normalized_slot.bin" in joined
    assert "0x3d0000 /tmp/normalized_slot.bin" in joined
    assert "0x8000" not in command
    assert "0xb000" not in command
    assert "0x790000" not in command
    assert "firmware.factory.bin" not in joined
    assert "flash_args" not in joined

def test_read_flash_region_rom_mode_binds_8mb_and_disables_stub(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "rom.bin"
    seen: list[str] = []

    def fake_run_capture(args, *, port=None):
        seen.extend(args)
        destination.write_bytes(b"x" * 16)
        return ""

    monkeypatch.setattr(module, "run_capture", fake_run_capture)
    module.read_flash_region(
        "/dev/cu.usbmodem-test",
        0x790000,
        16,
        destination,
    )
    assert "--no-stub" in seen
    before_index = seen.index("--before")
    after_index = seen.index("--after")
    read_index = seen.index("read-flash")
    assert seen[before_index + 1] == "no-reset"
    assert seen[after_index + 1] == "no-reset"
    assert seen[read_index + 1:read_index + 3] == ["--flash-size", "8MB"]


def test_read_flash_region_stub_mode_preserves_running_stub(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "stub.bin"
    seen: list[str] = []

    def fake_run_capture(args, *, port=None):
        seen.extend(args)
        destination.write_bytes(b"x" * 16)
        return ""

    monkeypatch.setattr(module, "run_capture", fake_run_capture)
    module.read_flash_region(
        "/dev/cu.usbmodem-test",
        0,
        16,
        destination,
        use_stub=True,
    )
    assert "--no-stub" not in seen
    assert "--flash-size" not in seen
    before_index = seen.index("--before")
    after_index = seen.index("--after")
    assert seen[before_index + 1] == "no-reset-no-sync"
    assert seen[after_index + 1] == "no-reset-stub"



def test_source_has_no_erase_flash_or_erase_region_command() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"erase-flash"' not in source
    assert '"erase-region"' not in source
    assert "NORMALIZED_OFFSETS_BOOTLOADER_OTADATA_APPLICATION" not in source


def test_load_preflight_rejects_legacy_identity_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = sample_preflight()
    payload["schema"] = "n3w.board-d.r4-dual-slot-normalization-write-preflight/2"
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="preflight closure is not PASS"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_load_preflight_accepts_fresh_exact_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(sample_preflight()), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    loaded = module.load_preflight(path, "/dev/cu.usbmodem-test")
    assert loaded["status"] == "PASS"


def test_load_preflight_rejects_wrong_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = sample_preflight()
    payload["selected_write_route"] = "OLD"
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="write route mismatch"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_normalized_slot_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = sample_preflight()
    payload["normalized_slot"]["sha256"] = "f" * 64
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="normalized-slot binding mismatch"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_erase_range_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = sample_preflight()
    payload["erase_ranges"]["app1"] = ["0x3d0000", "0x790001"]
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="erase-range binding mismatch"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_wrong_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = sample_preflight()
    payload["board"]["hardware_id_sha256"] = "f" * 64
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 25, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="identity mismatch"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_stale_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(sample_preflight()), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 9, 0, tzinfo=dt.timezone.utc),
    )
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(path, "/dev/cu.usbmodem-test")


def test_claim_preflight_is_one_shot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(sample_preflight()), encoding="utf-8")
    fresh_board = sample_board()
    monkeypatch.setattr(module, "load_preflight", lambda *args, **kwargs: sample_preflight())
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 26, tzinfo=dt.timezone.utc),
    )
    claimed, payload = module.claim_preflight(
        path,
        "/dev/cu.usbmodem-test",
        fresh_board,
    )
    assert not path.exists()
    assert claimed.exists()
    assert payload["authorization_claimed"] is True
    assert payload["authorization_consumed"] is True
    assert payload["replay_permitted"] is False
    assert payload["fresh_prewrite"]["board"] == fresh_board
    assert payload["execution_state"]["fresh_prewrite_persisted"] is True
    assert payload["execution_state"]["write_flash_returned_success"] is False
    on_disk = json.loads(claimed.read_text(encoding="utf-8"))
    assert on_disk["fresh_prewrite"]["board"]["nvs_sha256"] == fresh_board["nvs_sha256"]
    assert on_disk["fresh_prewrite"]["board"]["phy_init_sha256"] == fresh_board["phy_init_sha256"]
    with pytest.raises(module.StopExecution):
        module.claim_preflight(
            path,
            "/dev/cu.usbmodem-test",
            fresh_board,
        )


def test_verify_postwrite_integrity_requires_two_full_slots_and_protected_continuity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [
        module.MEMBER_BINDINGS["bootloader.bin"][1],
        module.MEMBER_BINDINGS["partitions.bin"][1],
        module.MEMBER_BINDINGS["ota_data_initial.bin"][1],
        module.NORMALIZED_SLOT_SHA256,
        module.NORMALIZED_SLOT_SHA256,
        "a" * 64,
        "b" * 64,
    ]
    read_modes: list[bool] = []

    def fake_read(*args, **kwargs):
        read_modes.append(kwargs.get("use_stub") is True)
        return expected.pop(0)

    monkeypatch.setattr(module, "read_flash_region", fake_read)
    result = module.verify_postwrite_integrity(
        "/dev/cu.usbmodem-test",
        tmp_path,
        prewrite_phy_init_sha256="a" * 64,
        prewrite_nvs_sha256="b" * 64,
    )
    assert result["app0_full_slot_match"] is True
    assert result["app1_full_slot_match"] is True
    assert result["app0_tail_erased"] is True
    assert result["app1_tail_erased"] is True
    assert result["old_application_code_remains"] is False
    assert result["phy_init_unchanged"] is True
    assert result["nvs_unchanged"] is True
    assert read_modes == [True] * 7


def test_verify_postwrite_integrity_rejects_app1_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [
        module.MEMBER_BINDINGS["bootloader.bin"][1],
        module.MEMBER_BINDINGS["partitions.bin"][1],
        module.MEMBER_BINDINGS["ota_data_initial.bin"][1],
        module.NORMALIZED_SLOT_SHA256,
        "c" * 64,
    ]
    monkeypatch.setattr(module, "read_flash_region", lambda *args, **kwargs: expected.pop(0))
    with pytest.raises(module.StopExecution, match="app1 full-slot SHA256 mismatch"):
        module.verify_postwrite_integrity(
            "/dev/cu.usbmodem-test",
            tmp_path,
            prewrite_phy_init_sha256="a" * 64,
            prewrite_nvs_sha256="b" * 64,
        )


def test_verify_postwrite_integrity_rejects_nvs_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [
        module.MEMBER_BINDINGS["bootloader.bin"][1],
        module.MEMBER_BINDINGS["partitions.bin"][1],
        module.MEMBER_BINDINGS["ota_data_initial.bin"][1],
        module.NORMALIZED_SLOT_SHA256,
        module.NORMALIZED_SLOT_SHA256,
        "a" * 64,
        "c" * 64,
    ]
    monkeypatch.setattr(module, "read_flash_region", lambda *args, **kwargs: expected.pop(0))
    with pytest.raises(module.StopExecution, match="NVS region changed"):
        module.verify_postwrite_integrity(
            "/dev/cu.usbmodem-test",
            tmp_path,
            prewrite_phy_init_sha256="a" * 64,
            prewrite_nvs_sha256="b" * 64,
        )


def test_postwrite_identity_observation_selects_base_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    eui64 = ":".join(("02", "00", "00", "AA", "BB", "00", "00", "01"))
    base_mac = ":".join(("02", "00", "00", "00", "00", "01"))
    expected_hash = module.public_identity_sha256(base_mac)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    seen: list[str] = []

    def fake_run_capture(args, *, port=None):
        seen.extend(args)
        return (
            "ESP32-C6\n"
            f"MAC:                 {eui64}\n"
            f"BASE MAC:            {base_mac}\n"
            "MAC_EXT:             aa:bb\n"
            "Secure Boot: Disabled\n"
            "Flash Encryption: Disabled\n"
        )

    monkeypatch.setattr(module, "run_capture", fake_run_capture)
    observed = module.observe_board_identity_security("/dev/cu.usbmodem-test", before="no-reset")
    assert observed == expected_hash
    assert observed != module.public_identity_sha256(
        ":".join(("02", "00", "00", "AA", "BB", "00"))
    )
    before_index = seen.index("--before")
    after_index = seen.index("--after")
    assert seen[before_index + 1] == "no-reset"
    assert seen[after_index + 1] == "no-reset"


def test_write_identity_parser_rejects_missing_or_ambiguous_base_mac() -> None:
    with pytest.raises(module.StopExecution, match="exactly one ESP32-C6 BASE MAC"):
        module.base_mac_from_esptool_output(
            "ESP32-C6\nMAC: "
            + ":".join(("02", "00", "00", "AA", "BB", "00", "00", "01"))
            + "\n"
        )

    with pytest.raises(module.StopExecution, match="exactly one ESP32-C6 BASE MAC"):
        module.base_mac_from_esptool_output(
            "BASE MAC: "
            + ":".join(("02", "00", "00", "00", "00", "01"))
            + "\nBASE MAC: "
            + ":".join(("02", "00", "00", "00", "00", "02"))
            + "\n"
        )


def test_run_write_claims_before_single_write_then_full_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "write.json"
    preflight = tmp_path / "preflight.json"
    preflight.write_text("{}", encoding="utf-8")
    release = tmp_path / "release.zip"
    release.write_bytes(b"x")
    files = {
        "bootloader.bin": tmp_path / "bootloader.bin",
        "firmware.bin": tmp_path / "firmware.bin",
        "ota_data_initial.bin": tmp_path / "ota_data_initial.bin",
    }
    for path in files.values():
        path.write_bytes(b"x")
    normalized = tmp_path / "normalized_slot.bin"
    normalized.write_bytes(b"x")
    board = sample_board()
    events: list[str] = []

    monkeypatch.setattr(module, "load_preflight", lambda *args, **kwargs: sample_preflight())
    monkeypatch.setattr(module, "validate_release_bundle", lambda *args, **kwargs: files)
    monkeypatch.setattr(module, "derive_normalized_slot", lambda *args, **kwargs: normalized)
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.3.1")
    monkeypatch.setattr(module, "verify_image", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "probe_board", lambda *args, **kwargs: board)

    def fake_claim(*args, **kwargs):
        events.append("claim")
        claimed = tmp_path / "claimed-preflight.json"
        claimed.write_text("claimed", encoding="utf-8")
        payload = sample_preflight()
        payload["fresh_prewrite"] = {"captured_at": "now", "board": board}
        payload["execution_state"] = {
            "fresh_prewrite_persisted": True,
            "write_flash_returned_success": False,
            "postwrite_integrity_pass": False,
            "postwrite_identity_pass": False,
        }
        return claimed, payload

    def fake_persist(claimed, payload, **updates):
        payload["execution_state"].update(updates)
        if updates.get("write_flash_returned_success") is True:
            events.append("persist-write")
        elif updates.get("postwrite_integrity_pass") is True:
            events.append("persist-readback")
        elif updates.get("postwrite_identity_pass") is True:
            events.append("persist-identity")

    def fake_run_capture(*args, **kwargs):
        events.append("write")
        return ""

    def fake_postwrite(*args, **kwargs):
        events.append("readback")
        return {
            "bootloader_sha256": module.MEMBER_BINDINGS["bootloader.bin"][1],
            "bootloader_match": True,
            "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
            "partition_table_match": True,
            "otadata_sha256": module.MEMBER_BINDINGS["ota_data_initial.bin"][1],
            "otadata_match": True,
            "app0_full_slot_sha256": module.NORMALIZED_SLOT_SHA256,
            "app0_full_slot_match": True,
            "app1_full_slot_sha256": module.NORMALIZED_SLOT_SHA256,
            "app1_full_slot_match": True,
            "app0_tail_erased": True,
            "app1_tail_erased": True,
            "old_application_code_remains": False,
            "phy_init_sha256": board["phy_init_sha256"],
            "phy_init_unchanged": True,
            "nvs_sha256": board["nvs_sha256"],
            "nvs_unchanged": True,
        }

    def fake_postwrite_identity(*args, **kwargs):
        assert kwargs["before"] == "default-reset"
        events.append("identity")
        return module.EXPECTED_HARDWARE_ID_SHA256

    monkeypatch.setattr(module, "claim_preflight", fake_claim)
    monkeypatch.setattr(module, "persist_claimed_execution_state", fake_persist)
    monkeypatch.setattr(module, "run_capture", fake_run_capture)
    monkeypatch.setattr(module, "verify_postwrite_integrity", fake_postwrite)
    monkeypatch.setattr(module, "observe_board_identity_security", fake_postwrite_identity)
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 30, tzinfo=dt.timezone.utc),
    )

    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port="/dev/cu.usbmodem-test",
        release_bundle=str(release),
        output=str(output),
    )
    assert module.run_write(args) == 0
    assert events == [
        "claim",
        "write",
        "persist-write",
        "readback",
        "persist-readback",
        "identity",
        "persist-identity",
    ]
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["authorization"]["consumed"] is True
    assert payload["fresh_prewrite"]["board"] == board
    assert payload["execution_state"]["write_flash_returned_success"] is True
    assert payload["execution_state"]["postwrite_integrity_pass"] is True
    assert payload["execution_state"]["postwrite_identity_pass"] is True
    assert payload["write_scope"]["selected_write_route"] == module.SELECTED_WRITE_ROUTE
    assert payload["write_scope"]["app0_offset"] == "0x10000"
    assert payload["write_scope"]["app1_offset"] == "0x3d0000"
    assert payload["write_scope"]["ota_slot_size"] == 0x3C0000
    assert payload["write_scope"]["partition_table_write"] is False
    assert payload["write_scope"]["phy_init_write"] is False
    assert payload["write_scope"]["nvs_write"] is False
    assert payload["write_scope"]["erase_region_command_used"] is False
    assert payload["postwrite"]["old_application_code_remains"] is False
    assert payload["postwrite"]["hardware_id_match"] is True


def test_run_write_persists_write_success_before_readback_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "write.json"
    preflight = tmp_path / "preflight.json"
    preflight.write_text("{}", encoding="utf-8")
    release = tmp_path / "release.zip"
    release.write_bytes(b"x")
    files = {
        "bootloader.bin": tmp_path / "bootloader.bin",
        "firmware.bin": tmp_path / "firmware.bin",
        "ota_data_initial.bin": tmp_path / "ota_data_initial.bin",
    }
    for path in files.values():
        path.write_bytes(b"x")
    normalized = tmp_path / "normalized_slot.bin"
    normalized.write_bytes(b"x")
    board = sample_board()
    persisted: list[dict[str, object]] = []

    monkeypatch.setattr(module, "load_preflight", lambda *args, **kwargs: sample_preflight())
    monkeypatch.setattr(module, "validate_release_bundle", lambda *args, **kwargs: files)
    monkeypatch.setattr(module, "derive_normalized_slot", lambda *args, **kwargs: normalized)
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.3.1")
    monkeypatch.setattr(module, "verify_image", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "probe_board", lambda *args, **kwargs: board)

    def fake_claim(*args, **kwargs):
        claimed = tmp_path / "claimed-preflight.json"
        claimed.write_text("claimed", encoding="utf-8")
        payload = sample_preflight()
        payload["fresh_prewrite"] = {"captured_at": "now", "board": board}
        payload["execution_state"] = {
            "fresh_prewrite_persisted": True,
            "write_flash_returned_success": False,
            "postwrite_integrity_pass": False,
            "postwrite_identity_pass": False,
        }
        return claimed, payload

    def fake_persist(claimed, payload, **updates):
        payload["execution_state"].update(updates)
        persisted.append(dict(payload["execution_state"]))

    monkeypatch.setattr(module, "claim_preflight", fake_claim)
    monkeypatch.setattr(module, "persist_claimed_execution_state", fake_persist)
    monkeypatch.setattr(module, "run_capture", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        module,
        "verify_postwrite_integrity",
        lambda *args, **kwargs: (_ for _ in ()).throw(module.StopExecution("readback failed")),
    )
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 23, 8, 30, tzinfo=dt.timezone.utc),
    )

    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port="/dev/cu.usbmodem-test",
        release_bundle=str(release),
        output=str(output),
    )
    with pytest.raises(module.StopExecution, match="readback failed"):
        module.run_write(args)
    assert persisted
    assert persisted[0]["write_flash_returned_success"] is True
    assert persisted[0]["postwrite_integrity_pass"] is False
    assert not output.exists()


def test_run_write_rejects_wrong_confirmation_before_any_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched = {"load": False}

    def fake_load(*args, **kwargs):
        touched["load"] = True
        return sample_preflight()

    monkeypatch.setattr(module, "load_preflight", fake_load)
    args = argparse.Namespace(
        confirm="WRONG",
        preflight=str(tmp_path / "preflight.json"),
        port="/dev/cu.usbmodem-test",
        release_bundle=str(tmp_path / "release.zip"),
        output=str(tmp_path / "write.json"),
    )
    with pytest.raises(module.StopExecution, match="confirmation token mismatch"):
        module.run_write(args)
    assert touched["load"] is False
