from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_f_board_b_preflight/write_executor.py"
spec = importlib.util.spec_from_file_location("gate_f_board_b_write_executor", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def board_payload(port: str) -> dict[str, object]:
    return {
        "hardware_id_sha256": module.preflight.EXPECTED_HARDWARE_ID_SHA256,
        "port_sha256": module.preflight.sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": module.preflight.PARTITION_TABLE_SHA256,
    }


def preflight_payload(port: str, created_at: dt.datetime) -> dict[str, object]:
    return {
        "schema": module.preflight.SCHEMA,
        "status": "PASS",
        "created_at": created_at.isoformat(),
        "preflight_max_age_seconds": module.preflight.PREFLIGHT_MAX_AGE_SECONDS,
        "esptool_version": "5.4.0",
        "board": board_payload(port),
        "artifact": module.expected_artifact_payload(),
        "persistent_mutation": False,
        "flash_write": False,
    }


def test_write_scope_is_app_plus_otadata_only() -> None:
    cmd = module.build_write_command("/dev/cu.synthetic", Path("/tmp/ota.bin"), Path("/tmp/app.bin"))
    index = cmd.index("write-flash")
    assert cmd[index + 1 :] == ["0x9000", "/tmp/ota.bin", "0x10000", "/tmp/app.bin"]
    assert "erase-flash" not in cmd
    assert "erase-region" not in cmd
    assert "0x0" not in cmd
    assert "0x8000" not in cmd


def test_wrong_confirmation_stops_before_preflight_access() -> None:
    args = argparse.Namespace(
        confirm="WRONG",
        preflight="/tmp/missing.json",
        port="/dev/cu.synthetic",
        artifact_zip="/tmp/missing.zip",
        output="/tmp/write.json",
    )
    with pytest.raises(module.StopExecution, match="confirmation"):
        module.run_write(args)


def test_stale_preflight_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = dt.datetime(2026, 10, 4, 4, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(preflight_payload(port, now - dt.timedelta(seconds=module.preflight.PREFLIGHT_MAX_AGE_SECONDS + 1))),
        encoding="utf-8",
    )
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(path, port)


def test_claim_consumes_preflight_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = dt.datetime(2026, 10, 4, 4, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(preflight_payload(port, now)), encoding="utf-8")
    claimed, payload = module.claim_preflight(path, port)
    assert not path.exists()
    assert claimed.is_file()
    assert payload["write_authorization"]["claimed"] is True
    assert payload["write_authorization"]["consumed"] is True
    assert payload["write_authorization"]["replay_permitted"] is False
    with pytest.raises(module.StopExecution):
        module.claim_preflight(path, port)


def test_write_claims_before_flash_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = dt.datetime(2026, 10, 4, 4, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    port = "/dev/cu.synthetic"
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight_payload(port, now)), encoding="utf-8")
    ota = tmp_path / "ota.bin"
    app = tmp_path / "app.bin"
    ota.write_bytes(b"ota")
    app.write_bytes(b"app")
    monkeypatch.setattr(module, "extract_write_images", lambda artifact_zip, extract_root: (ota, app))
    monkeypatch.setattr(module.preflight, "verify_esptool", lambda: "5.4.0")
    monkeypatch.setattr(module, "verify_image", lambda application: None)
    monkeypatch.setattr(module.preflight, "probe_board", lambda requested_port: board_payload(port))
    mutations: list[list[str]] = []

    def fake_run(args: list[str], port: str | None = None) -> str:
        if "write-flash" in args:
            assert not preflight_path.exists()
            assert preflight_path.with_name("claimed-" + preflight_path.name).is_file()
            mutations.append(args)
            return "Hash of data verified.\n"
        raise AssertionError(args)

    monkeypatch.setattr(module.preflight, "run_capture", fake_run)
    output = tmp_path / "write.json"
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        preflight=str(preflight_path),
        port=port,
        artifact_zip=str(tmp_path / "artifact.zip"),
        output=str(output),
    )
    assert module.run_write(args) == 0
    assert len(mutations) == 1
    closure = json.loads(output.read_text(encoding="utf-8"))
    assert closure["write_scope"]["bootloader_write"] is False
    assert closure["write_scope"]["partition_table_write"] is False
    assert closure["write_scope"]["product_nvs_write"] is False
    assert closure["write_scope"]["full_flash_erase"] is False
