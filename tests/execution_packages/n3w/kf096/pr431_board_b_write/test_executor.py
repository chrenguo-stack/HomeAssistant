from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/kf096/pr431_board_b_write/executor.py"
)

spec = importlib.util.spec_from_file_location("pr431_board_b_write_executor", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_hardware_id_derivation_matches_product_contract() -> None:
    raw = "02:00:00:00:00:02"
    expected_id = "ghw-c6-020000000002"
    assert module.hardware_id_from_mac(raw) == expected_id
    assert module.public_identity_sha256(raw) == hashlib.sha256(
        expected_id.encode("utf-8")
    ).hexdigest()


def test_probe_is_read_only_and_requires_exact_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "02:00:00:00:00:02"
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)

    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    result = module.probe_board("/dev/cu.synthetic")
    assert result["hardware_id_sha256"] == expected_hash
    assert result["chip"] == "ESP32-C6"
    assert result["flash_size"] == "8MB"
    assert result["secure_boot"] is False
    assert result["flash_encryption"] is False

    flattened = [token for call in calls for token in call]
    assert "get-security-info" in flattened
    assert "flash-id" in flattened
    forbidden = {
        "write-flash",
        "erase-flash",
        "erase-region",
        "write-mem",
        "write-flash-status",
    }
    assert forbidden.isdisjoint(flattened)
    assert all("--no-stub" in call for call in calls)


def test_probe_rejects_enabled_security(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "02:00:00:00:00:02"
    monkeypatch.setattr(
        module, "EXPECTED_HARDWARE_ID_SHA256", module.public_identity_sha256(raw)
    )

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw}\n"
                "Secure Boot: Enabled\n"
                "Flash Encryption: Disabled\n"
            )
        return "Detected flash size: 8 MB\n"

    monkeypatch.setattr(module, "run_capture", fake_run)
    with pytest.raises(module.StopExecution, match="Secure Boot"):
        module.probe_board("/dev/cu.synthetic")


def test_write_command_is_minimal_app_plus_otadata_only() -> None:
    cmd = module.build_write_command(
        "/dev/cu.synthetic", Path("/tmp/ota.bin"), Path("/tmp/app.bin")
    )
    assert "write-flash" in cmd
    write_index = cmd.index("write-flash")
    assert cmd[write_index + 1 :] == [
        "0x9000",
        "/tmp/ota.bin",
        "0x10000",
        "/tmp/app.bin",
    ]
    assert "erase-flash" not in cmd
    assert "erase-region" not in cmd
    assert "0x0" not in cmd
    assert "0x8000" not in cmd


def test_write_refuses_without_exact_confirmation() -> None:
    args = argparse.Namespace(
        confirm="WRONG",
        preflight="/tmp/preflight.json",
        port="/dev/cu.synthetic",
        artifact_zip="/tmp/artifact.zip",
        output="/tmp/write.json",
    )
    with pytest.raises(module.StopExecution, match="confirmation"):
        module.run_write(args)


def test_manifest_contract_is_exact() -> None:
    text = "\n".join(f"{key}={value}" for key, value in module.EXPECTED_MANIFEST.items())
    assert module.parse_manifest(text) == module.EXPECTED_MANIFEST
    with pytest.raises(module.StopExecution, match="duplicate"):
        module.parse_manifest(text + "\nSOURCE_HEAD=duplicate")
