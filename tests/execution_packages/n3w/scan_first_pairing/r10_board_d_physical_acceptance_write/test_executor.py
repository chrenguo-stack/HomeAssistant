from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/scan_first_pairing/r10_board_d_physical_acceptance_write/executor.py"
spec = importlib.util.spec_from_file_location("r10_board_d_physical_acceptance_write", MODULE_PATH)
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
        "bootloader_erase_span_sha256": module.CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "partition_sector_sha256": "1" * 64,
        "phy_init_sha256": module.PHY_ALL_FF_SHA256,
        "phy_all_ff": True,
    }


def sample_preflight(port: str = "/dev/cu.usbmodem-test") -> dict[str, object]:
    return {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": dt.datetime(2026, 10, 29, 1, 0, tzinfo=dt.timezone.utc).isoformat(),
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
        "current_r9_slot_binding_required": True,
        "bootloader_write": False,
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
        "captured_at": "2026-10-29T01:01:00+00:00",
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "port_sha256": module.sha256_bytes(port.encode()),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "backups": backups,
        "protected": protected,
        "current_r9_app0_match": True,
        "current_r9_app1_match": True,
        "current_r9_bootloader_match": True,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "phy_all_ff": True,
    }


def test_exact_acceptance_artifact_and_identity_are_frozen() -> None:
    assert module.PRODUCT_SOURCE == "44d3320877a0a47c3dd728182fae2f209bffbc0f"
    assert module.ACCEPTANCE_SOURCE == "faf07839fcef221f9defb296eadcc7c090e12d4e"
    assert module.ACCEPTANCE_TREE == "dc26f11617b721da316e7815b5330b8d8c1f3474"
    assert module.ARTIFACT_RUN_ID == 40798244418
    assert module.ARTIFACT_ID == 12864962159
    assert module.OUTER_SHA256 == "b57a5af10c23344e8e03250857455898eb60640e3e18c62022af9c2b9ab7f6da"
    assert module.INNER_SHA256 == "91b3e47b16025ec9fdf73500e463ecc0db4121ea0dc9dcc12325e88e7e7c347b"
    assert module.MANIFEST_SHA256 == "1aa0da0be83d461d92274fef0f37420032a05d7b3e25803ad236e3bb6883ef44"
    assert module.MEMBER_BINDINGS["firmware.bin"] == (
        1465712,
        "e68dcd2883500b99960b483fd06e5d16ef95557b8faedc928eb81d1b14a98eb2",
    )
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5"


def test_artifact_payload_is_explicitly_nonproduction() -> None:
    payload = module.artifact_binding_payload()
    assert payload["physical_acceptance_only"] is True
    assert payload["production_eligible"] is False
    assert payload["low_battery_protection_bypassed"] is True


def test_normalized_slot_binding_is_exact() -> None:
    b = module.normalized_slot_binding_payload()
    assert b["size"] == 0x3C0000
    assert b["source_application_size"] == 0x165D70
    assert b["tail_size"] == 0x25A290
    assert b["tail_sha256"] == "07f265cc0685350b34f568eb55654c3bd55ebea6a85588721df2f5c9ac180ac7"
    assert b["sha256"] == "9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd"


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


def test_erase_ranges_are_app_only_and_protect_bootloader() -> None:
    assert module.validate_write_erase_boundaries() == {
        "otadata": (0x9000, 0xB000),
        "app0": (0x10000, 0x3D0000),
        "app1": (0x3D0000, 0x790000),
    }


def test_write_command_has_only_three_segments() -> None:
    files = {"ota_data_initial.bin": Path("/tmp/r10-ota.bin")}
    slot = Path("/tmp/r10-slot.bin")
    cmd = module.build_write_command("/dev/cu.usbmodem-test", files, slot)
    joined = " ".join(cmd)
    assert "write-flash" in cmd
    assert "--flash-mode keep" in joined
    assert "--flash-freq keep" in joined
    assert "--flash-size keep" in joined
    assert "0x9000 /tmp/r10-ota.bin" in joined
    assert "0x10000 /tmp/r10-slot.bin" in joined
    assert "0x3d0000 /tmp/r10-slot.bin" in joined
    assert "0x0" not in cmd
    assert "0x8000" not in cmd
    assert "0xb000" not in cmd
    assert "0x790000" not in cmd
    assert "bootloader.bin" not in joined
    assert "firmware.factory.bin" not in joined
    assert "flash_args" not in joined


def test_source_has_no_destructive_erase_command() -> None:
    source = MODULE_PATH.read_text()
    assert '"erase-flash"' not in source
    assert '"erase-region"' not in source


def test_restore_command_uses_only_touched_backup_ranges(tmp_path: Path) -> None:
    cmd = module.build_restore_command("/dev/cu.usbmodem-test", tmp_path)
    joined = " ".join(cmd)
    for _, (offset, _, filename) in module.BACKUP_LAYOUT.items():
        assert f"{hex(offset)} {tmp_path / filename}" in joined
    assert "0x0" not in cmd
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


def _probe_reader(kind: str):
    def fake_read(port, offset, size, destination):
        if offset == module.BOOTLOADER_OFFSET:
            destination.write_bytes(b"B" * size)
            return (
                module.CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256
                if kind != "bootloader"
                else "0" * 64
            )
        if offset == module.PARTITION_TABLE_OFFSET:
            destination.write_bytes(b"P" * size)
            return module.sha256_file(destination)
        if offset == module.PHY_INIT_OFFSET:
            destination.write_bytes((b"\xff" if kind != "phy" else b"\x00") * size)
            return module.sha256_file(destination)
        raise AssertionError(offset)
    return fake_read


def _patch_probe_common(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    monkeypatch.setattr(module, "verify_single_serial_target", lambda p: None)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "verify_flash_size", lambda p: None)
    monkeypatch.setattr(module, "read_rom_region", _probe_reader(kind))
    real_sha = module.sha256_bytes
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: (
            ("f" * 64 if kind == "partition" else module.MEMBER_BINDINGS["partitions.bin"][1])
            if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0]
            else real_sha(data)
        ),
    )


def test_probe_rejects_wrong_bootloader(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probe_common(monkeypatch, "bootloader")
    with pytest.raises(module.StopExecution, match="bootloader baseline"):
        module.probe_board_readonly("/dev/cu.usbmodem-test")


def test_probe_rejects_wrong_partition(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probe_common(monkeypatch, "partition")
    with pytest.raises(module.StopExecution, match="partition table"):
        module.probe_board_readonly("/dev/cu.usbmodem-test")


def test_probe_rejects_non_ff_phy(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probe_common(monkeypatch, "phy")
    with pytest.raises(module.StopExecution, match="PHY"):
        module.probe_board_readonly("/dev/cu.usbmodem-test")


def test_capture_prewrite_requires_r9_slots_and_bootloader(
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
            digest = module.sha256_file(destination)
        elif offset == module.PHY_INIT_OFFSET:
            destination.write_bytes(b"\xff" * size)
            digest = module.PHY_ALL_FF_SHA256
        elif offset == module.BOOTLOADER_OFFSET:
            destination.write_bytes(b"B" * size)
            digest = module.CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256
        elif offset in (module.APP0_OFFSET, module.APP1_OFFSET):
            destination.write_bytes(b"A" * size)
            digest = module.CURRENT_R9_SLOT_SHA256
        else:
            destination.write_bytes(b"O" * size)
            digest = module.sha256_file(destination)
        destination.chmod(0o600)
        return digest

    real_sha = module.sha256_bytes
    monkeypatch.setattr(module, "read_stub_start", fake_read)
    monkeypatch.setattr(module, "read_stub_continue", fake_read)
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: (
            module.MEMBER_BINDINGS["partitions.bin"][1]
            if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0]
            else real_sha(data)
        ),
    )
    result = module.capture_prewrite_evidence(port, tmp_path)
    assert result["current_r9_app0_match"] is True
    assert result["current_r9_app1_match"] is True
    assert result["current_r9_bootloader_match"] is True
    expected = [(v[0], v[1]) for v in module.BACKUP_LAYOUT.values()] + [
        (v[0], v[1]) for v in module.PROTECTED_LAYOUT.values()
    ]
    assert order == expected


def test_capture_prewrite_rejects_app_slot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    monkeypatch.setattr(module, "verify_single_serial_target", lambda p: None)
    monkeypatch.setattr(module, "observe_board_identity_security", lambda *a, **k: module.EXPECTED_HARDWARE_ID_SHA256)
    monkeypatch.setattr(module, "verify_flash_size", lambda p: None)

    def fake_read(port, offset, size, destination):
        destination.write_bytes(b"\xff" * size)
        destination.chmod(0o600)
        if offset == module.APP0_OFFSET:
            return "0" * 64
        if offset == module.APP1_OFFSET:
            return module.CURRENT_R9_SLOT_SHA256
        if offset == module.BOOTLOADER_OFFSET:
            return module.CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256
        return module.sha256_file(destination)

    real_sha = module.sha256_bytes
    monkeypatch.setattr(module, "read_stub_start", fake_read)
    monkeypatch.setattr(module, "read_stub_continue", fake_read)
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: (
            module.MEMBER_BINDINGS["partitions.bin"][1]
            if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0]
            else real_sha(data)
        ),
    )
    with pytest.raises(module.StopExecution, match="app0"):
        module.capture_prewrite_evidence(port, tmp_path)


def test_verify_backup_files_rejects_drift(tmp_path: Path) -> None:
    fresh = sample_fresh("/dev/cu.usbmodem-test", tmp_path)
    module.verify_backup_files(tmp_path, fresh)
    first = next(iter(module.BACKUP_LAYOUT.values()))[2]
    (tmp_path / first).write_bytes(b"drift")
    with pytest.raises(module.StopExecution, match="drifted"):
        module.verify_backup_files(tmp_path, fresh)


def test_load_preflight_accepts_fresh_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 29, 1, 5, tzinfo=dt.timezone.utc))
    out = module.load_preflight(p, "/dev/cu.usbmodem-test")
    assert out["selected_write_route"] == module.SELECTED_WRITE_ROUTE


def test_load_preflight_rejects_wrong_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = sample_preflight()
    doc["selected_write_route"] = "WRONG"
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(doc))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 29, 1, 5, tzinfo=dt.timezone.utc))
    with pytest.raises(module.StopExecution, match="route"):
        module.load_preflight(p, "/dev/cu.usbmodem-test")


def test_load_preflight_rejects_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 29, 2, 0, tzinfo=dt.timezone.utc))
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(p, "/dev/cu.usbmodem-test")


def test_claim_preflight_is_one_shot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "preflight.json"
    p.write_text(json.dumps(sample_preflight()))
    fresh = {"x": 1}
    monkeypatch.setattr(module, "utc_now", lambda: dt.datetime(2026, 10, 29, 1, 6, tzinfo=dt.timezone.utc))
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


def _postwrite_reader(module, wrong: str | None = None, bad_tail: bool = False):
    def reader(port, offset, size, destination, *, first):
        name = destination.name[:-4]
        if name in ("app0_full_slot", "app1_full_slot"):
            app_size = module.MEMBER_BINDINGS["firmware.bin"][0]
            data = bytearray(b"A" * app_size + b"\xff" * (module.OTA_SLOT_SIZE - app_size))
            if bad_tail and name == "app0_full_slot":
                data[-1] = 0
            destination.write_bytes(data)
            digest = module.NORMALIZED_SLOT_SHA256
        elif name == "otadata":
            destination.write_bytes(b"\xff" * size)
            digest = module.MEMBER_BINDINGS["ota_data_initial.bin"][1]
        elif name == "partition_sector":
            destination.write_bytes(b"P" * size)
            digest = "c" * 64
        elif name == "phy_init":
            destination.write_bytes(b"\xff" * size)
            digest = "d" * 64
        elif name == "nvs":
            destination.write_bytes(b"N" * size)
            digest = "e" * 64
        elif name == "bootloader_erase_span":
            destination.write_bytes(b"B" * size)
            digest = "b" * 64
        else:
            raise AssertionError(name)
        if name == wrong:
            return "f" * 64
        return digest
    return reader


def test_postwrite_requires_full_slots_and_all_protected_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh = {
        "protected": {
            "bootloader_erase_span": {"sha256": "b" * 64},
            "partition_sector": {"sha256": "c" * 64},
            "phy_init": {"sha256": "d" * 64},
            "nvs": {"sha256": "e" * 64},
        }
    }
    monkeypatch.setattr(module, "_postwrite_read", _postwrite_reader(module))
    real_sha = module.sha256_bytes
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: (
            module.MEMBER_BINDINGS["partitions.bin"][1]
            if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0] and data.startswith(b"P")
            else real_sha(data)
        ),
    )
    out = module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)
    assert out["bootloader_unchanged"] is True
    assert out["partition_unchanged"] is True
    assert out["phy_init_unchanged"] is True
    assert out["nvs_unchanged"] is True
    assert out["app0_full_slot_match"] is True
    assert out["app1_full_slot_match"] is True
    assert out["old_application_code_remains"] is False


def test_postwrite_rejects_bootloader_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = {"protected": {
        "bootloader_erase_span": {"sha256": "b" * 64},
        "partition_sector": {"sha256": "c" * 64},
        "phy_init": {"sha256": "d" * 64},
        "nvs": {"sha256": "e" * 64},
    }}
    monkeypatch.setattr(module, "_postwrite_read", _postwrite_reader(module, "bootloader_erase_span"))
    with pytest.raises(module.StopExecution, match="bootloader_erase_span"):
        module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)


def test_postwrite_rejects_non_ff_slot_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = {"protected": {
        "bootloader_erase_span": {"sha256": "b" * 64},
        "partition_sector": {"sha256": "c" * 64},
        "phy_init": {"sha256": "d" * 64},
        "nvs": {"sha256": "e" * 64},
    }}
    monkeypatch.setattr(module, "_postwrite_read", _postwrite_reader(module, bad_tail=True))
    real_sha = module.sha256_bytes
    monkeypatch.setattr(
        module,
        "sha256_bytes",
        lambda data: (
            module.MEMBER_BINDINGS["partitions.bin"][1]
            if len(data) == module.MEMBER_BINDINGS["partitions.bin"][0] and data.startswith(b"P")
            else real_sha(data)
        ),
    )
    with pytest.raises(module.StopExecution, match="tail"):
        module.verify_postwrite_integrity("/dev/cu.usbmodem-test", tmp_path, prewrite=fresh)


def test_verify_restore_checks_touched_and_protected_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = "/dev/cu.usbmodem-test"
    fresh = sample_fresh(port, tmp_path)
    expected = {}
    sequence = []
    for section, layout in (("backups", module.BACKUP_LAYOUT), ("protected", module.PROTECTED_LAYOUT)):
        for name in layout:
            expected[name] = fresh[section][name]["sha256"]

    def fake(port, offset, size, destination, *, first):
        name = destination.name[:-4]
        sequence.append(name)
        destination.write_bytes(b"x" * size)
        return expected[name]

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
        "ota_data_initial.bin": tmp_path / "ota.bin",
    }
    for p in files.values():
        p.write_bytes(b"x")
    normalized = tmp_path / "slot.bin"
    normalized.write_bytes(b"x")
    fresh = {
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "current_r9_app0_match": True,
        "current_r9_app1_match": True,
        "current_r9_bootloader_match": True,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "phy_all_ff": True,
        "backups": {},
        "protected": {},
    }
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
        "bootloader_erase_span_sha256": module.CURRENT_R9_BOOTLOADER_ERASE_SPAN_SHA256,
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
    files = {"firmware.bin": tmp_path / "firmware.bin", "ota_data_initial.bin": tmp_path / "ota.bin"}
    for p in files.values():
        p.write_bytes(b"x")
    normalized = tmp_path / "slot.bin"
    normalized.write_bytes(b"x")
    fresh = {
        "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
        "current_r9_app0_match": True,
        "current_r9_app1_match": True,
        "current_r9_bootloader_match": True,
        "partition_table_sha256": module.MEMBER_BINDINGS["partitions.bin"][1],
        "phy_all_ff": True,
        "backups": {},
        "protected": {},
    }
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


def test_factory_and_bootloader_are_validation_members_not_write_authority() -> None:
    assert "firmware.factory.bin" in module.MEMBER_BINDINGS
    assert "bootloader.bin" in module.MEMBER_BINDINGS
    joined = " ".join(module.build_write_command(
        "/dev/cu.usbmodem-test",
        {"ota_data_initial.bin": Path("/o")},
        Path("/s"),
    ))
    assert "factory" not in joined
    assert "bootloader" not in joined
    assert "0x0" not in joined


def test_old_write_confirmation_is_not_reused() -> None:
    assert module.WRITE_CONFIRMATION == "N3W_R10_BOARD_D_PHYSICAL_ACCEPTANCE_WRITE_AUTHORIZED"
    assert "R9_DUAL_SLOT" not in module.WRITE_CONFIRMATION
    assert "DIRECT" not in module.WRITE_CONFIRMATION


def test_private_json_handles_short_os_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "state.json"
    real_write = module.os.write
    def short_write(fd, data):
        return real_write(fd, bytes(data[:3]))
    monkeypatch.setattr(module.os, "write", short_write)
    module.write_private_json(target, {"status": "PASS", "value": "x" * 200})
    assert json.loads(target.read_text())["status"] == "PASS"
    assert target.stat().st_size > 200


def test_private_state_zero_progress_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "state.json"
    monkeypatch.setattr(module.os, "write", lambda fd, data: 0)
    with pytest.raises(module.StopExecution, match="made no progress"):
        module.write_private_json(target, {"status": "PASS"})
