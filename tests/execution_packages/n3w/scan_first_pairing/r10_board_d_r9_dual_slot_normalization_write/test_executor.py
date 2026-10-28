from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/scan_first_pairing/r10_board_d_r9_dual_slot_normalization_write/executor.py"
spec = importlib.util.spec_from_file_location("r10_board_d_r9_dual_slot", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_board(port: str = "/dev/cu.usbmodem-test") -> dict[str, object]:
    return {
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "port_sha256": module.sha256_bytes(port.encode()),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "partition_sector_sha256": "1" * 64,
        "phy_init_sha256": module.PHY_ALL_FF_SHA256,
        "phy_all_ff": True,
    }


def sample_preflight(port: str = "/dev/cu.usbmodem-test") -> dict[str, object]:
    return {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": dt.datetime(2026, 10, 28, 14, 0, tzinfo=dt.timezone.utc).isoformat(),
        "esptool_version": "5.3.1",
        "board": sample_board(port),
        "artifact": module.artifact_binding_payload(),
        "selected_write_route": module.SELECTED_WRITE_ROUTE,
        "normalized_slot": module.normalized_slot_binding_payload(),
        "erase_ranges": {
            name: [hex(a), hex(b)]
            for name, (a, b) in module.validate_write_erase_boundaries().items()
        },
        "fresh_prewrite_backup_required": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "flash_write": False,
        "nvs_write": False,
    }


def sample_fresh(port: str, root: Path) -> dict[str, object]:
    backups = {}
    protected = {}
    for section_name, layout in (("backups", module.BACKUP_LAYOUT), ("protected", module.PROTECTED_LAYOUT)):
        target = backups if section_name == "backups" else protected
        for name, (offset, size, filename) in layout.items():
            path = root / filename
            path.write_bytes((name.encode() * ((size // max(1, len(name))) + 1))[:size])
            path.chmod(0o600)
            target[name] = {
                "offset": hex(offset),
                "size": size,
                "sha256": module.sha256_file(path),
                "file": filename,
            }
    return {
        "captured_at": "2026-10-28T14:01:00+00:00",
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "port_sha256": module.sha256_bytes(port.encode()),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "backups": backups,
        "protected": protected,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "phy_all_ff": True,
    }


def test_exact_r9_artifact_and_identity_are_frozen() -> None:
    assert module.PRODUCT_SOURCE == "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
    assert module.ARTIFACT_ID == 12783234959
    assert module.OUTER_SHA256 == "6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995"
    assert module.INNER_SHA256 == "b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1"
    assert module.MANIFEST_SHA256 == "8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05"
    assert module.MEMBER_BINDINGS["firmware.bin"] == (
        1460144,
        "fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be",
    )
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"


def test_r9_normalized_slot_binding_is_exact() -> None:
    b = module.normalized_slot_binding_payload()
    assert b["size"] == 0x3C0000
    assert b["source_application_size"] == 0x1647B0
    assert b["tail_size"] == 0x25B850
    assert b["tail_sha256"] == "a77ed5023b0caeaad43d58317f864574f4d82e9ba5af0274fb8df9df7584d209"
    assert b["sha256"] == "6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079"


def test_derive_normalized_slot_pads_only_ff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = tmp_path / "firmware.bin"
    app.write_bytes(b"abc")
    expected = b"abc" + b"\xff" * 5
    monkeypatch.setitem(module.MEMBER_BINDINGS, "firmware.bin", (3, hashlib.sha256(b"abc").hexdigest()))
    monkeypatch.setattr(module, "OTA_SLOT_SIZE", 8)
    monkeypatch.setattr(module, "NORMALIZED_SLOT_SHA256", hashlib.sha256(expected).hexdigest())
    out = tmp_path / "slot.bin"
    module.derive_normalized_slot(app, out)
    assert out.read_bytes() == expected


def test_otadata_accepts_only_all_ff(tmp_path: Path) -> None:
    p = tmp_path / "ota.bin"
    p.write_bytes(b"\xff" * 8192)
    module.validate_otadata_erased(p)
    data = bytearray(p.read_bytes())
    data[1] = 0
    p.write_bytes(data)
    with pytest.raises(module.StopExecution, match="all-FF"):
        module.validate_otadata_erased(p)


def test_exact_erase_ranges_do_not_touch_protected_regions() -> None:
    assert module.validate_write_erase_boundaries() == {
        "bootloader": (0x0, 0x6000),
        "otadata": (0x9000, 0xB000),
        "app0": (0x10000, 0x3D0000),
        "app1": (0x3D0000, 0x790000),
    }


def test_write_command_is_four_segment_only() -> None:
    files = {
        "bootloader.bin": Path("/tmp/r9-bootloader.bin"),
        "ota_data_initial.bin": Path("/tmp/r9-ota.bin"),
    }
    slot = Path("/tmp/r9-slot.bin")
    cmd = module.build_write_command("/dev/cu.usbmodem-test", files, slot)
    joined = " ".join(cmd)
    assert "write-flash" in cmd
    assert "--flash-mode keep" in joined
    assert "--flash-freq keep" in joined
    assert "--flash-size keep" in joined
    assert "0x0 /tmp/r9-bootloader.bin" in joined
    assert "0x9000 /tmp/r9-ota.bin" in joined
    assert "0x10000 /tmp/r9-slot.bin" in joined
    assert "0x3d0000 /tmp/r9-slot.bin" in joined
    assert "0x8000" not in cmd
    assert "0xb000" not in cmd
    assert "0x790000" not in cmd
    assert "firmware.factory.bin" not in joined
    assert "flash_args" not in joined


def test_source_has_no_destructive_erase_command() -> None:
    source = MODULE_PATH.read_text()
    assert '"erase-flash"' not in source
    assert '"erase-region"' not in source


def test_restore_command_uses_all_four_fresh_backup_ranges(tmp_path: Path) -> None:
    cmd = module.build_restore_command("/dev/cu.usbmodem-test", tmp_path)
    joined = " ".join(cmd)
    for _, (offset, _, filename) in module.BACKUP_LAYOUT.items():
        assert f"{hex(offset)} {tmp_path / filename}" in joined
    assert "0x8000" not in cmd
    assert "0xb000" not in cmd
    assert "0x790000" not in cmd


def test_single_serial_target_requires_exactly_one(monkeypatch: pytest.MonkeyPatch) -> None:
    port = "/dev/cu.usbmodem-one"
    monkeypatch.setattr(module.glob, "glob", lambda _: [port])
    module.verify_single_serial_target(port)
    monkeypatch.setattr(module.glob, "glob", lambda _: [port, "/dev/cu.usbmodem-two"])
    with pytest.raises(module.StopExecution, match="exactly one"):
        module.verify_single_serial_target(port)


def test_wrong_board_identity_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    synthetic_mac = ":".join(("02", "00", "00", "00", "00", "01"))
    monkeypatch.setattr(
        module,
        "run_capture",
        lambda *a, **k: (
            "ESP32-C6\n"
            f"MAC: {synthetic_mac}\n"
            "Secure Boot: Disabled\n"
            "Flash Encryption: Disabled\n"
        ),
    )
    with pytest.raises(module.StopExecution, match="frozen Board D"):
        module.observe_board_identity_security("/dev/cu.usbmodem-test", before="default-reset")


def test_probe_rejects_wrong_partition(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "verify_single_serial_target", lambda p: None)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "verify_flash_size", lambda p: None)

    def fake_read(port, offset, size, destination):
        if offset == module.PARTITION_TABLE_OFFSET:
            destination.write_bytes(b"\x00" * size)
        else:
            destination.write_bytes(b"\xff" * size)
        return module.sha256_file(destination)

    monkeypatch.setattr(module, "read_rom_region", fake_read)
    with pytest.raises(module.StopExecution, match="partition table"):
        module.probe_board_readonly("/dev/cu.usbmodem-test")


def test_probe_rejects_non_ff_phy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "verify_single_serial_target", lambda p: None)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "verify_flash_size", lambda p: None)

    def fake_read(port, offset, size, destination):
        if offset == module.PARTITION_TABLE_OFFSET:
            destination.write_bytes(b"P" * size)
        else:
            destination.write_bytes(b"\x00" * size)
        return module.sha256_file(destination)

    real_sha = module.sha256_bytes
    monkeypatch.setattr(module, "read_rom_region", fake_read)
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: module.MEMBER_BINDINGS["partitions.bin"][1]
        if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0]
        else real_sha(data),
    )
    with pytest.raises(module.StopExecution, match="PHY"):
        module.probe_board_readonly("/dev/cu.usbmodem-test")


def test_capture_prewrite_covers_every_touched_and_protected_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    monkeypatch.setattr(module, "verify_single_serial_target", lambda p: None)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "verify_flash_size", lambda p: None)
    order = []

    def fake_read(port, offset, size, destination):
        order.append((offset, size))
        if offset == module.PARTITION_TABLE_OFFSET:
            destination.write_bytes(b"P" * size)
        elif offset == module.PHY_INIT_OFFSET:
            destination.write_bytes(b"\xff" * size)
        else:
            destination.write_bytes(b"X" * size)
        destination.chmod(0o600)
        return module.sha256_file(destination)

    real_sha = module.sha256_bytes
    monkeypatch.setattr(module, "read_stub_start", fake_read)
    monkeypatch.setattr(module, "read_stub_continue", fake_read)
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: module.MEMBER_BINDINGS["partitions.bin"][1]
        if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0] and data.startswith(b"P")
        else real_sha(data),
    )
    fresh = module.capture_prewrite_evidence(port, tmp_path)
    expected = [(v[0], v[1]) for v in module.BACKUP_LAYOUT.values()] + [
        (v[0], v[1]) for v in module.PROTECTED_LAYOUT.values()
    ]
    assert order == expected
    assert set(fresh["backups"]) == set(module.BACKUP_LAYOUT)
    assert set(fresh["protected"]) == set(module.PROTECTED_LAYOUT)
    module.verify_backup_files(tmp_path, fresh)


def test_verify_backup_files_rejects_drift(tmp_path: Path) -> None:
    fresh = sample_fresh("/dev/cu.usbmodem-test", tmp_path)
    module.verify_backup_files(tmp_path, fresh)
    (tmp_path / module.BACKUP_LAYOUT["app0"][2]).write_bytes(b"drift")
    with pytest.raises(module.StopExecution, match="drifted"):
        module.verify_backup_files(tmp_path, fresh)


def test_load_preflight_accepts_fresh_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 28, 14, 5, tzinfo=dt.timezone.utc))
    assert module.load_preflight(p, "/dev/cu.usbmodem-test")["status"] == "PASS"


def test_load_preflight_rejects_wrong_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = sample_preflight()
    doc["selected_write_route"] = "DIRECT_FACTORY"
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(doc))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 28, 14, 5, tzinfo=dt.timezone.utc))
    with pytest.raises(module.StopExecution, match="route"):
        module.load_preflight(p, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 28, 15, 0, tzinfo=dt.timezone.utc))
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(p, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_wrong_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = sample_preflight()
    doc["board"]["hardware_id_sha256"] = "f" * 64
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(doc))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 28, 14, 5, tzinfo=dt.timezone.utc))
    with pytest.raises(module.StopExecution, match="identity"):
        module.load_preflight(p, "/dev/cu.usbmodem-test")


def test_claim_preflight_is_one_shot_and_consumes_before_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    fresh = {"x": 1}
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 28, 14, 6, tzinfo=dt.timezone.utc))
    claimed, doc = module.claim_preflight(p, sample_preflight(), fresh)
    assert not p.exists()
    assert claimed.exists()
    assert doc["authorization_claimed"] is True
    assert doc["authorization_consumed"] is True
    assert doc["replay_permitted"] is False
    with pytest.raises(module.StopExecution):
        module.claim_preflight(p, sample_preflight(), fresh)


def test_wrong_write_confirmation_stops_before_preflight_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    touched = {"load": False}
    def fake(*a, **k):
        touched["load"] = True
        return {}
    monkeypatch.setattr(module, "load_preflight", fake)
    args = argparse.Namespace(
        confirm="WRONG",
        preflight=str(tmp_path / "preflight.json"),
        port="/dev/cu.usbmodem-test",
        artifact_zip=str(tmp_path / "artifact.zip"),
        output=str(tmp_path / "result.json"),
    )
    with pytest.raises(module.StopExecution, match="confirmation token"):
        module.run_write(args)
    assert touched["load"] is False


def _fake_postwrite_reader_factory(module, wrong_name: str | None = None):
    def reader(port, offset, size, destination, *, first):
        key = destination.name[:-4]
        if key in ("app0_full_slot", "app1_full_slot"):
            app_size = module.MEMBER_BINDINGS["firmware.bin"][0]
            data = b"A" * app_size + b"\xff" * (module.OTA_SLOT_SIZE - app_size)
            destination.write_bytes(data)
            digest = module.NORMALIZED_SLOT_SHA256
        elif key == "partition_sector":
            destination.write_bytes(b"P" * size)
            digest = "c" * 64
        elif key == "phy_init":
            destination.write_bytes(b"\xff" * size)
            digest = "d" * 64
        elif key == "nvs":
            destination.write_bytes(b"N" * size)
            digest = "e" * 64
        elif key == "bootloader_erase_span":
            destination.write_bytes(b"B" * size)
            digest = module.BOOTLOADER_ERASE_SPAN_SHA256
        elif key == "otadata":
            destination.write_bytes(b"\xff" * size)
            digest = module.MEMBER_BINDINGS["ota_data_initial.bin"][1]
        else:
            raise AssertionError(key)
        if key == wrong_name:
            return "f" * 64
        return digest
    return reader


def test_postwrite_requires_full_slots_and_protected_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh = {
        "protected": {
            "partition_sector": {"sha256": "c" * 64},
            "phy_init": {"sha256": "d" * 64},
            "nvs": {"sha256": "e" * 64},
        }
    }
    monkeypatch.setattr(module, "_postwrite_read", _fake_postwrite_reader_factory(module))
    real_sha = module.sha256_bytes
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: module.MEMBER_BINDINGS["partitions.bin"][1]
        if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0] and data.startswith(b"P")
        else real_sha(data),
    )
    out = module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)
    assert out["app0_full_slot_match"] is True
    assert out["app1_full_slot_match"] is True
    assert out["app0_tail_erased"] is True
    assert out["app1_tail_erased"] is True
    assert out["partition_unchanged"] is True
    assert out["phy_init_unchanged"] is True
    assert out["nvs_unchanged"] is True
    assert out["old_application_code_remains"] is False


def test_postwrite_rejects_app1_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = {
        "protected": {
            "partition_sector": {"sha256": "c" * 64},
            "phy_init": {"sha256": "d" * 64},
            "nvs": {"sha256": "e" * 64},
        }
    }
    monkeypatch.setattr(module, "_postwrite_read", _fake_postwrite_reader_factory(module, "app1_full_slot"))
    with pytest.raises(module.StopExecution, match="app1_full_slot"):
        module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)


def test_postwrite_rejects_non_ff_slot_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = {
        "protected": {
            "partition_sector": {"sha256": "c" * 64},
            "phy_init": {"sha256": "d" * 64},
            "nvs": {"sha256": "e" * 64},
        }
    }
    reader = _fake_postwrite_reader_factory(module)
    def bad_reader(port, offset, size, destination, *, first):
        digest = reader(port, offset, size, destination, first=first)
        if destination.name == "app0_full_slot.bin":
            data = bytearray(destination.read_bytes())
            data[-1] = 0
            destination.write_bytes(data)
        return digest
    monkeypatch.setattr(module, "_postwrite_read", bad_reader)
    real_sha = module.sha256_bytes
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: module.MEMBER_BINDINGS["partitions.bin"][1]
        if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0] and data.startswith(b"P")
        else real_sha(data),
    )
    with pytest.raises(module.StopExecution, match="tail"):
        module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)


def test_verify_restore_checks_all_touched_and_protected_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    fresh = sample_fresh(port, tmp_path)
    sequence = []
    expected = {}
    for section, layout in (("backups", module.BACKUP_LAYOUT), ("protected", module.PROTECTED_LAYOUT)):
        for name, (_, _, _) in layout.items():
            expected[name] = fresh[section][name]["sha256"]

    def fake(port, offset, size, destination, *, first):
        key = destination.name[:-4]
        sequence.append(key)
        destination.write_bytes(b"x" * size)
        return expected[key]

    monkeypatch.setattr(module, "_postwrite_read", fake)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    module.verify_restore(port, tmp_path, fresh, tmp_path / "verify")
    assert sequence == list(module.BACKUP_LAYOUT) + list(module.PROTECTED_LAYOUT)


def test_attempt_rollback_marks_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = "/dev/cu.usbmodem-test"
    fresh = sample_fresh(port, tmp_path)
    claimed = tmp_path / "claimed-preflight.json"
    claimed.write_text("{}")
    claimed.chmod(0o600)
    payload = {"execution_state": {}}
    events = []
    monkeypatch.setattr(module, "verify_backup_files", lambda *a, **k: events.append("verify-backups"))
    monkeypatch.setattr(module, "run_capture", lambda *a, **k: events.append("restore-write") or "")
    monkeypatch.setattr(module, "verify_restore", lambda *a, **k: events.append("verify-restore"))
    monkeypatch.setattr(module, "persist_claimed_state", lambda *a, **k: events.append(("persist", k)))
    assert module.attempt_rollback(port, tmp_path, fresh, claimed, payload) is True
    assert "verify-backups" in events
    assert "restore-write" in events
    assert "verify-restore" in events


def test_run_write_orders_backup_before_claim_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    evidence = tmp_path / "e"
    evidence.mkdir(mode=0o700)
    preflight = evidence / "preflight.json"
    preflight.write_text("{}")
    output = evidence / "write-result.json"
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"x")
    files = {
        "firmware.bin": tmp_path / "firmware.bin",
        "bootloader.bin": tmp_path / "bootloader.bin",
        "ota_data_initial.bin": tmp_path / "ota.bin",
    }
    for p in files.values():
        p.write_bytes(b"x")
    normalized = tmp_path / "slot.bin"
    normalized.write_bytes(b"x")
    fresh = {"hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
             "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
             "phy_all_ff": True,
             "backups": {}, "protected": {}}
    events = []
    monkeypatch.setattr(module, "load_preflight", lambda *a, **k: sample_preflight(port))
    monkeypatch.setattr(module, "private_evidence_root", lambda *a, **k: evidence)
    monkeypatch.setattr(module, "validate_artifact", lambda *a, **k: files)
    monkeypatch.setattr(module, "derive_normalized_slot", lambda *a, **k: normalized)
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.3.1")
    monkeypatch.setattr(module, "verify_image", lambda *a, **k: None)
    monkeypatch.setattr(module, "capture_prewrite_evidence", lambda *a, **k: events.append("backup") or fresh)
    monkeypatch.setattr(module, "verify_backup_files", lambda *a, **k: events.append("verify-backup"))
    claimed = evidence / "claimed-preflight.json"
    def claim(*a, **k):
        events.append("claim")
        claimed.write_text("{}")
        claimed.chmod(0o600)
        doc = sample_preflight(port)
        doc["fresh_prewrite"] = fresh
        doc["execution_state"] = {}
        return claimed, doc
    monkeypatch.setattr(module, "claim_preflight", claim)
    monkeypatch.setattr(module, "persist_claimed_state", lambda *a, **k: None)
    monkeypatch.setattr(module, "run_capture", lambda *a, **k: events.append("write") or "")
    monkeypatch.setattr(module, "verify_postwrite_integrity", lambda *a, **k: {
        "bootloader_erase_span_sha256": module.BOOTLOADER_ERASE_SPAN_SHA256,
        "otadata_sha256": module.MEMBER_BINDINGS["ota_data_initial.bin"][1],
        "app0_full_slot_sha256": module.NORMALIZED_SLOT_SHA256,
        "app1_full_slot_sha256": module.NORMALIZED_SLOT_SHA256,
        "old_application_code_remains": False,
    })
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "write_private_json", lambda *a, **k: None)
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port=port,
        artifact_zip=str(artifact),
        output=str(output),
    )
    assert module.run_write(args) == 0
    assert events[:4] == ["backup", "verify-backup", "claim", "write"]


def test_run_write_failure_after_claim_attempts_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    evidence = tmp_path / "e"
    evidence.mkdir(mode=0o700)
    preflight = evidence / "preflight.json"
    preflight.write_text("{}")
    output = evidence / "write-result.json"
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"x")
    files = {
        "firmware.bin": tmp_path / "firmware.bin",
        "bootloader.bin": tmp_path / "bootloader.bin",
        "ota_data_initial.bin": tmp_path / "ota.bin",
    }
    for p in files.values():
        p.write_bytes(b"x")
    normalized = tmp_path / "slot.bin"
    normalized.write_bytes(b"x")
    fresh = {"hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
             "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
             "phy_all_ff": True,
             "backups": {}, "protected": {}}
    monkeypatch.setattr(module, "load_preflight", lambda *a, **k: sample_preflight(port))
    monkeypatch.setattr(module, "private_evidence_root", lambda *a, **k: evidence)
    monkeypatch.setattr(module, "validate_artifact", lambda *a, **k: files)
    monkeypatch.setattr(module, "derive_normalized_slot", lambda *a, **k: normalized)
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.3.1")
    monkeypatch.setattr(module, "verify_image", lambda *a, **k: None)
    monkeypatch.setattr(module, "capture_prewrite_evidence", lambda *a, **k: fresh)
    monkeypatch.setattr(module, "verify_backup_files", lambda *a, **k: None)
    claimed = evidence / "claimed-preflight.json"
    def claim(*a, **k):
        claimed.write_text("{}")
        claimed.chmod(0o600)
        doc = sample_preflight(port)
        doc["fresh_prewrite"] = fresh
        doc["execution_state"] = {}
        return claimed, doc
    monkeypatch.setattr(module, "claim_preflight", claim)
    monkeypatch.setattr(module, "persist_claimed_state", lambda *a, **k: None)
    monkeypatch.setattr(module, "run_capture", lambda *a, **k: (_ for _ in ()).throw(module.StopExecution("write failed")))
    rolled = {"called": False}
    monkeypatch.setattr(module, "attempt_rollback", lambda *a, **k: rolled.__setitem__("called", True) or True)
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port=port,
        artifact_zip=str(artifact),
        output=str(output),
    )
    with pytest.raises(module.StopExecution, match="rollback PASS"):
        module.run_write(args)
    assert rolled["called"] is True


def test_failure_before_claim_keeps_preflight_unconsumed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = "/dev/cu.usbmodem-test"
    evidence = tmp_path / "e"
    evidence.mkdir(mode=0o700)
    preflight = evidence / "preflight.json"
    preflight.write_text("{}")
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"x")
    output = evidence / "result.json"
    monkeypatch.setattr(module, "load_preflight", lambda *a, **k: sample_preflight(port))
    monkeypatch.setattr(module, "private_evidence_root", lambda *a, **k: evidence)
    monkeypatch.setattr(module, "validate_artifact", lambda *a, **k: (_ for _ in ()).throw(module.StopExecution("artifact drift")))
    touched = {"claim": False}
    monkeypatch.setattr(module, "claim_preflight", lambda *a, **k: touched.__setitem__("claim", True))
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port=port,
        artifact_zip=str(artifact),
        output=str(output),
    )
    with pytest.raises(module.StopExecution, match="artifact drift"):
        module.run_write(args)
    assert touched["claim"] is False
    assert preflight.exists()


def test_artifact_binding_payload_is_r9_not_r4() -> None:
    payload = module.artifact_binding_payload()
    assert payload["artifact_id"] == 12783234959
    assert payload["product_source"].startswith("e299c937")
    source = MODULE_PATH.read_text()
    assert "12478974186" not in source
    assert "ec5f6d68e33db7757d91c807fff708ca81b075dc" not in source


def test_factory_image_is_validation_member_not_write_authority() -> None:
    assert "firmware.factory.bin" in module.MEMBER_BINDINGS
    joined = " ".join(module.build_write_command(
        "/dev/cu.usbmodem-test",
        {"bootloader.bin": Path("/b"), "ota_data_initial.bin": Path("/o")},
        Path("/s"),
    ))
    assert "factory" not in joined


def test_bootloader_erase_span_hash_is_frozen() -> None:
    assert module.BOOTLOADER_ERASE_SPAN_SIZE == 0x6000
    assert module.BOOTLOADER_ERASE_SPAN_SHA256 == "e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae"


def test_previous_direct_factory_confirmation_is_not_reused() -> None:
    assert "DIRECT" not in module.WRITE_CONFIRMATION
    assert module.WRITE_CONFIRMATION == "N3W_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_WRITE_AUTHORIZED"


def test_private_json_handles_short_os_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "state.json"
    real_write = module.os.write

    def short_write(fd, data):
        return real_write(fd, bytes(data[:3]))

    monkeypatch.setattr(module.os, "write", short_write)
    module.write_private_json(target, {"status": "PASS", "value": "x" * 200})
    assert json.loads(target.read_text())["status"] == "PASS"
    assert target.stat().st_size > 200


def test_claim_fsyncs_directory_transitions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(sample_preflight()))
    calls = []
    monkeypatch.setattr(module, "_fsync_dir", lambda path: calls.append(path))
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: dt.datetime(2026, 10, 28, 14, 6, tzinfo=dt.timezone.utc),
    )
    claimed, payload = module.claim_preflight(preflight, sample_preflight(), {"fresh": True})
    assert claimed.exists()
    assert payload["authorization_consumed"] is True
    assert len(calls) >= 3
    assert all(path == tmp_path for path in calls)


def test_private_state_zero_progress_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "state.json"
    monkeypatch.setattr(module.os, "write", lambda fd, data: 0)
    with pytest.raises(module.StopExecution, match="made no progress"):
        module.write_private_json(target, {"status": "PASS"})
