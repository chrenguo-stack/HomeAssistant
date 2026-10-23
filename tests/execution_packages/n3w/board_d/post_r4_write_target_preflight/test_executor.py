from __future__ import annotations

import argparse
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/board_d/post_r4_write_target_preflight/executor.py"
spec = importlib.util.spec_from_file_location("board_d_post_r4_preflight", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_authority_constants() -> None:
    assert module.MERGED_MAIN == "e24b5af4a271867c613dd52012bc83a6d40b06a5"
    assert module.PRODUCT_SOURCE == "ec5f6d68e33db7757d91c807fff708ca81b075dc"
    assert module.PRODUCT_TREE == "16740efa8ad24d423adc0b2de32b99d56e2d23d1"
    assert module.ARTIFACT_RUN_ID == 39901919230
    assert module.ARTIFACT_ID == 12478974186
    assert module.RELEASE_BUNDLE_SHA256 == "b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5"
    assert module.MANIFEST_SHA256 == "173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb"


def test_no_write_surface_exists() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'add_parser("write")' not in source
    assert "write-flash" not in source
    assert "erase-flash" not in source
    parser = module.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["write"])


def test_manifest_duplicate_key_fails() -> None:
    with pytest.raises(module.StopExecution):
        module.parse_manifest("A=1\nA=2\n")


def test_write_mode_classification() -> None:
    assert module.classify_write_mode(True, True) == "APP_PLUS_OTADATA_CANDIDATE"
    assert module.classify_write_mode(False, True) == "FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED"
    assert module.classify_write_mode(True, False) == "FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED"
    assert module.classify_write_mode(False, False) == "FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED"


def test_validate_release_bundle_accepts_exact_contract_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bindings = {
        "MANIFEST.txt": (4, module.sha256_bytes(b"A=1\n")),
        "bootloader.bin": (1, module.sha256_bytes(b"b")),
        "firmware.bin": (1, module.sha256_bytes(b"f")),
        "firmware.factory.bin": (1, module.sha256_bytes(b"x")),
        "firmware.ota.bin": (1, module.sha256_bytes(b"o")),
        "flash_args": (1, module.sha256_bytes(b"a")),
        "ota_data_initial.bin": (1, module.sha256_bytes(b"d")),
        "partitions.bin": (1, module.sha256_bytes(b"p")),
    }
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in {
            "MANIFEST.txt": b"A=1\n",
            "bootloader.bin": b"b",
            "firmware.bin": b"f",
            "firmware.factory.bin": b"x",
            "firmware.ota.bin": b"o",
            "flash_args": b"a",
            "ota_data_initial.bin": b"d",
            "partitions.bin": b"p",
        }.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, data)
    monkeypatch.setattr(module, "MEMBER_BINDINGS", bindings)
    monkeypatch.setattr(module, "EXPECTED_MANIFEST", {"A": "1"})
    monkeypatch.setattr(module, "MANIFEST_SHA256", bindings["MANIFEST.txt"][1])
    monkeypatch.setattr(module, "RELEASE_BUNDLE_SHA256", module.sha256_file(archive))
    out = module.validate_release_bundle(archive, tmp_path / "out")
    assert set(out) == module.EXPECTED_MEMBERS


def test_validate_release_bundle_rejects_nondeterministic_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bindings = {name: (1, module.sha256_bytes(b"x")) for name in module.EXPECTED_MEMBERS}
    bindings["MANIFEST.txt"] = (4, module.sha256_bytes(b"A=1\n"))
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(module.EXPECTED_MEMBERS):
            data = b"A=1\n" if name == "MANIFEST.txt" else b"x"
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, data)
    monkeypatch.setattr(module, "MEMBER_BINDINGS", bindings)
    monkeypatch.setattr(module, "RELEASE_BUNDLE_SHA256", module.sha256_file(archive))
    with pytest.raises(module.StopExecution, match="timestamp"):
        module.validate_release_bundle(archive, tmp_path / "out")


def test_probe_board_sanitizes_identity_and_classifies_existing_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = iter([
        "esptool v5.1\nESP32-C6\nMAC: 12:34:56:78:9A:BC\nSecure Boot: Disabled\nFlash Encryption: Disabled\n",
        "Detected flash size: 8MB\n",
    ])
    monkeypatch.setattr(module, "run_capture", lambda *args, **kwargs: next(outputs))
    hashes = iter([
        module.MEMBER_BINDINGS["bootloader.bin"][1],
        module.MEMBER_BINDINGS["partitions.bin"][1],
    ])
    monkeypatch.setattr(module, "read_flash_region", lambda *args, **kwargs: next(hashes))
    board = module.probe_board("/dev/cu.usbmodem-test")
    assert board["hardware_id_sha256"] == module.public_identity_sha256("12:34:56:78:9A:BC")
    assert board["write_mode_candidate"] == "APP_PLUS_OTADATA_CANDIDATE"
    assert "12:34:56:78:9A:BC" not in json.dumps(board)


def test_run_preflight_never_grants_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = tmp_path / "release.zip"
    release.write_bytes(b"placeholder")
    files = {name: tmp_path / name for name in module.EXPECTED_MEMBERS}
    for path in files.values():
        path.write_bytes(b"x")
    monkeypatch.setattr(module, "validate_release_bundle", lambda *args, **kwargs: files)
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.1.0")
    monkeypatch.setattr(module, "verify_image", lambda path: None)
    monkeypatch.setattr(
        module,
        "probe_board",
        lambda port: {
            "hardware_id_sha256": "a" * 64,
            "port_sha256": "b" * 64,
            "chip": "ESP32-C6",
            "flash_size": "8MB",
            "secure_boot": False,
            "flash_encryption": False,
            "bootloader_offset": "0x0",
            "bootloader_sha256": "c" * 64,
            "bootloader_matches_release": True,
            "partition_table_offset": "0x8000",
            "partition_table_sha256": "d" * 64,
            "partition_table_matches_release": True,
            "write_mode_candidate": "APP_PLUS_OTADATA_CANDIDATE",
        },
    )
    output = tmp_path / "preflight.json"
    rc = module.run_preflight(argparse.Namespace(port="/dev/cu.test", release_bundle=str(release), output=str(output)))
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["flash_write"] is False
    assert payload["nvs_write"] is False
    assert payload["persistent_mutation"] is False
    assert payload["write_command_present"] is False
    assert payload["write_authorization_granted"] is False
    assert payload["raw_flash_args_direct_execution_allowed"] is False
