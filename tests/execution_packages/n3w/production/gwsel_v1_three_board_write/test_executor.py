from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/production/gwsel_v1_three_board_write/executor.py"
)

spec = importlib.util.spec_from_file_location(
    "n3w_gwsel_v1_three_board_write_executor", MODULE_PATH
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _mac_text(parts: tuple[int, ...]) -> str:
    return ":".join(f"{value:02x}" for value in parts)


def _partition_bytes() -> bytes:
    result = bytearray(b"\xff" * module.PARTITION_TABLE_SIZE)
    for index, (label, part_type, subtype, offset, size, flags) in enumerate(
        module.EXPECTED_PARTITIONS
    ):
        entry = bytearray(32)
        struct.pack_into("<H", entry, 0, 0x50AA)
        entry[2] = part_type
        entry[3] = subtype
        struct.pack_into("<II", entry, 4, offset, size)
        encoded = label.encode("ascii")
        entry[12 : 12 + len(encoded)] = encoded
        struct.pack_into("<I", entry, 28, flags)
        result[index * 32 : (index + 1) * 32] = entry

    md5_index = len(module.EXPECTED_PARTITIONS) * 32
    result[md5_index : md5_index + 2] = b"\xeb\xeb"
    return bytes(result)


def test_exact_artifact_and_board_bindings() -> None:
    assert module.PRODUCT_SOURCE == "8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c"
    assert module.PRODUCT_TREE == "e9c0216c4a25e99038ff81e54036455cb32b4181"
    assert module.ARTIFACT_ID == 10693728323
    assert module.ARTIFACT_ZIP_SIZE == 4281423
    assert (
        module.ARTIFACT_ZIP_SHA256
        == "e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814"
    )
    assert (
        module.RELEASE_BUNDLE_SHA256
        == "f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598"
    )
    assert module.OTADATA_OFFSET == 0x9000
    assert module.APPLICATION_OFFSET == 0x10000
    assert module.OTADATA_SIZE == 0x2000
    assert module.APPLICATION_SIZE == 1392960
    assert set(module.BOARD_PROFILES) == {"A", "B", "C"}

    for profile in module.BOARD_PROFILES.values():
        digest = profile["hardware_id_sha256"]
        assert len(digest) == 64
        int(digest, 16)


def test_corrected_esp32c6_identity_parser_does_not_truncate_eui64() -> None:
    base_a = (2, 0, 0, 16, 32, 48)
    base_b = (2, 0, 0, 16, 32, 49)
    eui_a = base_a[:3] + (255, 254) + base_a[3:]
    eui_b = base_b[:3] + (255, 254) + base_b[3:]

    canonical_a = module.canonical_base_mac(f"MAC: {_mac_text(eui_a)}\n")
    canonical_b = module.canonical_base_mac(f"MAC: {_mac_text(eui_b)}\n")

    assert canonical_a == _mac_text(base_a)
    assert canonical_b == _mac_text(base_b)
    assert module.public_identity_sha256(canonical_a) != module.public_identity_sha256(
        canonical_b
    )


def test_explicit_base_mac_preferred_and_malformed_eui64_fails_closed() -> None:
    base = (2, 0, 0, 85, 102, 119)
    other = (2, 0, 0, 85, 102, 120)
    eui = other[:3] + (255, 254) + other[3:]

    security = (
        f"MAC: {_mac_text(eui)}\n"
        f"BASE MAC: {_mac_text(base)}\n"
        "MAC_EXT: ff:fe\n"
    )
    assert module.canonical_base_mac(security) == _mac_text(base)

    malformed = (2, 0, 0, 1, 2, 3, 4, 5)
    with pytest.raises(module.StopExecution, match="unsupported ESP32-C6 EUI-64"):
        module.canonical_base_mac(f"MAC: {_mac_text(malformed)}\n")


def test_frozen_partition_layout() -> None:
    raw = _partition_bytes()
    assert module.parse_partition_table(raw) == module.EXPECTED_PARTITIONS

    by_label = {item[0]: item for item in module.EXPECTED_PARTITIONS}
    assert by_label["otadata"][3:5] == (0x9000, 0x2000)
    assert by_label["app0"][3:5] == (0x10000, 0x3C0000)
    assert by_label["app1"][3:5] == (0x3D0000, 0x3C0000)
    assert by_label["nvs"][3:5] == (0x790000, 0x70000)


def test_factory_composition_and_flash_args_freeze_minimal_route(tmp_path: Path) -> None:
    partition = _partition_bytes()
    bootloader = b"boot"
    otadata = b"ota"
    application = b"app-image"

    factory = bytearray(b"\xff" * (module.APPLICATION_OFFSET + len(application)))
    factory[0 : len(bootloader)] = bootloader
    factory[
        module.PARTITION_TABLE_OFFSET :
        module.PARTITION_TABLE_OFFSET + len(partition)
    ] = partition
    factory[module.OTADATA_OFFSET : module.OTADATA_OFFSET + len(otadata)] = otadata
    factory[
        module.APPLICATION_OFFSET :
        module.APPLICATION_OFFSET + len(application)
    ] = application

    files: dict[str, Path] = {}
    values = {
        "partition_table": partition,
        "bootloader": bootloader,
        "otadata": otadata,
        "application": application,
        "ota_application": application,
        "factory": bytes(factory),
        "flash_args": module.EXPECTED_FLASH_ARGS.encode(),
    }
    for name, data in values.items():
        path = tmp_path / name
        path.write_bytes(data)
        files[name] = path

    module.validate_write_route(files)


def test_write_command_contains_only_otadata_and_application() -> None:
    command = module.build_write_command(
        "/dev/cu.synthetic",
        Path("/tmp/ota.bin"),
        Path("/tmp/app.bin"),
    )

    index = command.index("write-flash")
    tail = command[index + 1 :]

    assert tail == [
        hex(module.OTADATA_OFFSET),
        "/tmp/ota.bin",
        hex(module.APPLICATION_OFFSET),
        "/tmp/app.bin",
    ]

    forbidden = {
        "erase-flash",
        "erase-region",
        "0x0",
        "0x8000",
        "0x790000",
    }
    assert forbidden.isdisjoint(tail)


def test_identity_mismatch_stops_before_flash_id_or_flash_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = _mac_text((2, 0, 0, 0, 0, 70))
    calls: list[list[str]] = []

    monkeypatch.setitem(
        module.BOARD_PROFILES["A"],
        "hardware_id_sha256",
        "0" * 64,
    )

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    with pytest.raises(module.StopExecution, match="frozen Board A identity"):
        module.probe_board("/dev/cu.synthetic", "A")

    flat = [token for call in calls for token in call]
    assert "flash-id" not in flat
    assert "read-flash" not in flat


def test_probe_is_read_only_and_raw_mac_is_not_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = _mac_text((2, 0, 0, 0, 0, 71))
    expected_identity = module.public_identity_sha256(raw_mac)

    monkeypatch.setitem(
        module.BOARD_PROFILES["B"],
        "hardware_id_sha256",
        expected_identity,
    )

    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        raise AssertionError(args)

    def fake_read(
        port: str,
        offset: int,
        size: int,
        destination: Path,
    ) -> str:
        calls.append(["read-flash", hex(offset), hex(size)])
        if offset == module.PARTITION_TABLE_OFFSET:
            return module.PARTITION_TABLE_SHA256
        if offset == module.OTADATA_OFFSET:
            return "1" * 64
        raise AssertionError((offset, size))

    monkeypatch.setattr(module, "run_capture", fake_run)
    monkeypatch.setattr(module, "read_flash_region", fake_read)

    result = module.probe_board("/dev/cu.synthetic", "B")

    assert result["operator_board_label"] == "B"
    assert result["hardware_id_sha256"] == expected_identity
    assert result["partition_table_sha256"] == module.PARTITION_TABLE_SHA256
    assert result["current_otadata_sha256"] == "1" * 64
    assert raw_mac not in json.dumps(result, sort_keys=True)

    flat = [token for call in calls for token in call]
    assert "write-flash" not in flat
    assert "erase-flash" not in flat
    assert "erase-region" not in flat


def test_postwrite_readback_verifies_all_three_regions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[int, int]] = []

    def fake_read(
        port: str,
        offset: int,
        size: int,
        destination: Path,
    ) -> str:
        seen.append((offset, size))
        if offset == module.OTADATA_OFFSET:
            return module.OTADATA_SHA256
        if offset == module.APPLICATION_OFFSET:
            return module.APPLICATION_SHA256
        if offset == module.PARTITION_TABLE_OFFSET:
            return module.PARTITION_TABLE_SHA256
        raise AssertionError(offset)

    monkeypatch.setattr(module, "read_flash_region", fake_read)

    result = module.verify_postwrite_readback("/dev/cu.synthetic")

    assert result == {
        "otadata_sha256": module.OTADATA_SHA256,
        "application_sha256": module.APPLICATION_SHA256,
        "partition_table_sha256": module.PARTITION_TABLE_SHA256,
    }
    assert seen == [
        (module.OTADATA_OFFSET, module.OTADATA_SIZE),
        (module.APPLICATION_OFFSET, module.APPLICATION_SIZE),
        (module.PARTITION_TABLE_OFFSET, module.PARTITION_TABLE_SIZE),
    ]


def test_wrong_write_confirmation_stops_before_preflight_or_board_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched = False

    def should_not_run(*args: object, **kwargs: object) -> object:
        nonlocal touched
        touched = True
        raise AssertionError("must not run before exact write confirmation")

    monkeypatch.setattr(module, "load_preflight", should_not_run)

    args = argparse.Namespace(
        board="C",
        port="/dev/not-used",
        artifact_zip="/tmp/not-used.zip",
        preflight="/tmp/not-used.json",
        output="/tmp/not-used-output.json",
        confirm_write="WRONG",
    )

    with pytest.raises(module.StopExecution, match="write confirmation token mismatch"):
        module.run_write(args)

    assert touched is False


def test_source_has_no_automatic_destructive_recovery() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert '"erase-flash"' not in source
    assert '"erase-region"' not in source
    assert '"write-mem"' not in source
    assert '"write-flash-status"' not in source
    assert "10691518958" not in source

    assert '"write-flash"' in source
    assert '"bootloader_write": False' in source
    assert '"partition_table_write": False' in source
    assert '"product_nvs_write": False' in source
    assert '"factory_image_write": False' in source
    assert '"full_flash_erase": False' in source
