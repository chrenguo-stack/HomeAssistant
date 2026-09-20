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


def synthetic_partition() -> bytes:
    return bytes((index % 251 for index in range(module.PARTITION_TABLE_SIZE)))


def board_payload(port: str, hardware_hash: str) -> dict[str, object]:
    return {
        "hardware_id_sha256": hardware_hash,
        "port_sha256": module.sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(module.PARTITION_TABLE_OFFSET),
        "partition_table_size": module.PARTITION_TABLE_SIZE,
        "partition_table_sha256": module.PARTITION_TABLE_SHA256,
    }


def preflight_payload(
    port: str,
    hardware_hash: str,
    created_at: dt.datetime,
) -> dict[str, object]:
    return {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": created_at.isoformat(),
        "esptool_version": "5.1.0",
        "board": board_payload(port, hardware_hash),
        "artifact": module.artifact_binding_payload(),
        "persistent_mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
    }


def test_pr437_artifact_binding_is_exact() -> None:
    assert module.PRODUCT_SOURCE == "b289041d1b9a1cb493feb674a57c50660301a69a"
    assert module.PRODUCT_TREE == "20753f5ccadba60383b88f4bee68b40cc4ff565e"
    assert module.WORKFLOW_TRIGGER_SHA == "b1bccda2f6b0528da165c1599099dbabe3211b1a"
    assert module.WORKFLOW_RUN_ID == 35494924449
    assert module.ARTIFACT_ID == 10599444353
    assert module.ARTIFACT_NAME == "n3w-pr437-b289041-boardb-exact-source"
    assert module.ARTIFACT_ZIP_SIZE == 728511
    assert module.ARTIFACT_ZIP_SHA256 == "6ee0533a27f7d5881f940f55a865d2a66467054f6b0a30d08806c79bdad63c29"
    assert module.APPLICATION_SIZE == 1141856
    assert module.APPLICATION_SHA256 == "d035de81b810bd38eda702b9bca94c32e05df967f5932d2c191847646906c907"
    assert module.OTADATA_SIZE == 8192
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.MANIFEST_SIZE == 575
    assert module.MANIFEST_SHA256 == "d1a1c892d2929e928d4cfdcee1d87df6cf8324089d22abd9c382a64deb1848cf"
    assert module.PARTITION_TABLE_OFFSET == 0x8000
    assert module.PARTITION_TABLE_SIZE == 0xC00
    assert module.PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
    assert module.WRITE_CONFIRMATION == "PR437_B289041_BOARD_B_WRITE_AUTHORIZED"


def test_hardware_id_derivation_matches_product_contract() -> None:
    raw = synthetic_mac()
    expected_id = "ghw-c6-" + "020000000002"
    assert module.hardware_id_from_mac(raw) == expected_id
    assert module.public_identity_sha256(raw) == hashlib.sha256(expected_id.encode("utf-8")).hexdigest()


def test_probe_is_read_only_and_requires_exact_identity_and_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    partition = synthetic_partition()
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    monkeypatch.setattr(module, "PARTITION_TABLE_SHA256", hashlib.sha256(partition).hexdigest())
    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return "Chip is ESP32-C6 (QFN40)\nMAC: " + raw + "\nSecure Boot: Disabled\nFlash Encryption: Disabled\n"
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            Path(args[-1]).write_bytes(partition)
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)
    result = module.probe_board("/dev/cu.synthetic")
    assert result["hardware_id_sha256"] == expected_hash
    assert result["chip"] == "ESP32-C6"
    assert result["flash_size"] == "8MB"
    assert result["secure_boot"] is False
    assert result["flash_encryption"] is False
    assert result["partition_table_offset"] == "0x8000"
    assert result["partition_table_size"] == 0xC00
    assert result["partition_table_sha256"] == hashlib.sha256(partition).hexdigest()
    flattened = [token for call in calls for token in call]
    assert "get-security-info" in flattened
    assert "flash-id" in flattened
    assert "read-flash" in flattened
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


def test_probe_rejects_partition_table_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = synthetic_mac()
    partition = synthetic_partition()
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", module.public_identity_sha256(raw))
    monkeypatch.setattr(module, "PARTITION_TABLE_SHA256", hashlib.sha256(b"different").hexdigest())

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return "Chip is ESP32-C6 (QFN40)\nMAC: " + raw + "\nSecure Boot: Disabled\nFlash Encryption: Disabled\n"
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            Path(args[-1]).write_bytes(partition)
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)
    with pytest.raises(module.StopExecution, match="partition table binding"):
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
    payload = preflight_payload(
        port,
        expected_hash,
        now - dt.timedelta(seconds=module.PREFLIGHT_MAX_AGE_SECONDS + 1),
    )
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(path, port)


def test_claim_preflight_consumes_single_use_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    now = dt.datetime(2026, 9, 19, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(preflight_payload(port, expected_hash, now)), encoding="utf-8")
    claimed, payload = module.claim_preflight(path, port)
    assert not path.exists()
    assert claimed.is_file()
    assert claimed.name == "claimed-preflight.json"
    assert payload["authorization_claimed"] is True
    assert payload["authorization_consumed"] is True
    assert payload["replay_permitted"] is False
    saved = json.loads(claimed.read_text(encoding="utf-8"))
    assert saved["authorization_claimed"] is True
    assert saved["authorization_consumed"] is True
    with pytest.raises(module.StopExecution):
        module.claim_preflight(path, port)


def test_write_claims_before_mutation_and_replay_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    now = dt.datetime(2026, 9, 19, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(preflight_payload(port, expected_hash, now)), encoding="utf-8")
    app = tmp_path / "app.bin"
    ota = tmp_path / "ota.bin"
    manifest = tmp_path / "manifest.txt"
    app.write_bytes(b"app")
    ota.write_bytes(b"ota")
    manifest.write_text("manifest", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "validate_artifact",
        lambda archive, extract_root: {
            "application": app,
            "otadata": ota,
            "manifest": manifest,
        },
    )
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.1.0")
    monkeypatch.setattr(module, "verify_image", lambda application: None)
    monkeypatch.setattr(module, "probe_board", lambda requested_port: board_payload(port, expected_hash))

    mutations: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if "write-flash" in args:
            assert not preflight.exists()
            claimed = preflight.with_name("claimed-" + preflight.name)
            saved = json.loads(claimed.read_text(encoding="utf-8"))
            assert saved["authorization_claimed"] is True
            assert saved["authorization_consumed"] is True
            assert saved["replay_permitted"] is False
            mutations.append(args)
            return "Hash of data verified.\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)
    output = tmp_path / "write.json"
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port=port,
        artifact_zip=str(tmp_path / "artifact.zip"),
        output=str(output),
    )
    assert module.run_write(args) == 0
    assert len(mutations) == 1
    closure = json.loads(output.read_text(encoding="utf-8"))
    assert closure["authorization"]["claimed"] is True
    assert closure["authorization"]["consumed"] is True
    assert closure["authorization"]["replay_permitted"] is False
    with pytest.raises(module.StopExecution):
        module.run_write(args)
    assert len(mutations) == 1


def test_write_partition_mismatch_fails_before_authorization_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)
    monkeypatch.setattr(module, "EXPECTED_HARDWARE_ID_SHA256", expected_hash)
    now = dt.datetime(2026, 9, 19, 2, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(preflight_payload(port, expected_hash, now)), encoding="utf-8")
    app = tmp_path / "app.bin"
    ota = tmp_path / "ota.bin"
    manifest = tmp_path / "manifest.txt"
    app.write_bytes(b"app")
    ota.write_bytes(b"ota")
    manifest.write_text("manifest", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "validate_artifact",
        lambda archive, extract_root: {
            "application": app,
            "otadata": ota,
            "manifest": manifest,
        },
    )
    monkeypatch.setattr(module, "verify_esptool_version", lambda: "5.1.0")
    monkeypatch.setattr(module, "verify_image", lambda application: None)
    bad_board = board_payload(port, expected_hash)
    bad_board["partition_table_sha256"] = "0" * 64
    monkeypatch.setattr(module, "probe_board", lambda requested_port: bad_board)

    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight),
        port=port,
        artifact_zip=str(tmp_path / "artifact.zip"),
        output=str(tmp_path / "write.json"),
    )
    with pytest.raises(module.StopExecution, match="fresh partition table"):
        module.run_write(args)
    assert preflight.is_file()
    assert not preflight.with_name("claimed-" + preflight.name).exists()
