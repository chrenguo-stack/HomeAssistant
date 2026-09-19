from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/kf096/pr437_board_b_write/executor.py"

spec = importlib.util.spec_from_file_location("pr437_board_b_write_executor", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic_mac() -> str:
    return ":".join(["02", "00", "00", "00", "00", "02"])


def test_pr437_artifact_binding_is_exact() -> None:
    assert module.PRODUCT_SOURCE == "cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c"
    assert module.PRODUCT_TREE == "b459fae0a054d45b0d09e60bffae9769e060a5c0"
    assert module.WORKFLOW_TRIGGER_SHA == "f5dfdad292a1a9263a7f433b759a6def4d3d1153"
    assert module.WORKFLOW_RUN_ID == 35414060819
    assert module.ARTIFACT_ID == 10575077512
    assert module.ARTIFACT_NAME == "n3w-pr437-boardb-exact-source"
    assert module.ARTIFACT_ZIP_SIZE == 727532
    assert module.ARTIFACT_ZIP_SHA256 == "b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814"
    assert module.APPLICATION_SIZE == 1139600
    assert module.APPLICATION_SHA256 == "407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb"
    assert module.OTADATA_SIZE == 8192
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.MANIFEST_SIZE == 575
    assert module.MANIFEST_SHA256 == "98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0"
    assert module.WRITE_CONFIRMATION == "PR437_BOARD_B_WRITE_AUTHORIZED"


def test_hardware_id_derivation_matches_product_contract() -> None:
    raw = synthetic_mac()
    expected_id = "ghw-c6-" + "020000000002"
    assert module.hardware_id_from_mac(raw) == expected_id
    assert module.public_identity_sha256(raw) == hashlib.sha256(expected_id.encode("utf-8")).hexdigest()


def test_probe_is_read_only_and_requires_exact_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return "Chip is ESP32-C6 (QFN40)\nMAC: " + raw + "\nSecure Boot: Disabled\nFlash Encryption: Disabled\n"
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
    forbidden = {"write-flash", "erase-flash", "erase-region", "write-mem", "write-flash-status"}
    assert forbidden.isdisjoint(flattened)
    assert all("--no-stub" in call for call in calls)


def test_probe_rejects_enabled_security(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = synthetic_mac()
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", module.public_identity_sha256(raw))

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return "Chip is ESP32-C6 (QFN40)\nMAC: " + raw + "\nSecure Boot: Enabled\nFlash Encryption: Disabled\n"
        return "Detected flash size: 8 MB\n"

    monkeypatch.setattr(module, "run_capture", fake_run)
    with pytest.raises(module.StopExecution, match="Secure Boot"):
        module.probe_board("/dev/cu.synthetic")


def test_write_command_is_minimal_app_plus_otadata_only() -> None:
    cmd = module.build_write_command("/dev/cu.synthetic", Path("/tmp/ota.bin"), Path("/tmp/app.bin"))
    assert "write-flash" in cmd
    write_index = cmd.index("write-flash")
    assert cmd[write_index + 1 :] == ["0x9000", "/tmp/ota.bin", "0x10000", "/tmp/app.bin"]
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


def test_preflight_rejects_stale_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    now = dt.datetime(2026, 9, 19, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    payload = {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": (now - dt.timedelta(seconds=module.PREFLIGHT_MAX_AGE_SECONDS + 1)).isoformat(),
        "artifact": module.artifact_binding_payload(),
        "board": {
            "hardware_id_sha256": expected_hash,
            "port_sha256": module.sha256_bytes(port.encode("utf-8")),
            "chip": "ESP32-C6",
            "flash_size": "8MB",
            "secure_boot": False,
            "flash_encryption": False,
        },
    }
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(path, port)
