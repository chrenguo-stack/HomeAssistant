from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_private_build/executor.py"
)

spec = importlib.util.spec_from_file_location("gate_a_private_build", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_preflight(path: Path) -> None:
    payload = {
        "schema": module.EXPECTED_PREFLIGHT_SCHEMA,
        "status": "PASS",
        "t1": {
            "interface": "eth0",
            "current_ip": "192.0.2.10",
            "prefixlen": 24,
            "wildcard_8883": True,
            "broker_running": True,
            "manager_running": True,
            "manager_restart_count": 0,
            "live_alias": "192.0.2.250",
            "blackhole_ip": "192.0.2.249",
        },
        "board": {
            "hardware_id_sha256": module.EXPECTED_BOARD_B_HARDWARE_ID_SHA256,
            "partition_table_sha256": module.EXPECTED_PARTITION_TABLE_SHA256,
            "flash_write": False,
            "persistent_mutation": False,
        },
        "t1_mutation": False,
        "board_flash": False,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)


def test_frozen_source_authority_is_exact() -> None:
    assert module.SOURCE_HEAD == "8210cf7b53e9ec934d145f1c15e9619579c923be"
    assert module.SOURCE_TREE == "5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c"
    assert module.TARGET_BLOB == "7279271d469958940c2b51aa4a80602078470891"
    assert module.PATCH_BLOB == "49570a83ead08158d4d99c385740fa6d646b5e3d"
    assert module.ESPHOME_VERSION == "2026.4.3"
    assert module.ESP_IDF_VERSION == "5.5.4"


def test_private_preflight_accepts_same_subnet_distinct_candidates(tmp_path: Path) -> None:
    path = tmp_path / "preflight.json"
    write_preflight(path)
    result = module.load_preflight(path)
    assert result["status"] == "PASS"
    assert result["t1"]["live_alias"] != result["t1"]["blackhole_ip"]


def test_private_preflight_fails_closed_on_board_binding_drift(tmp_path: Path) -> None:
    path = tmp_path / "preflight.json"
    write_preflight(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["board"]["hardware_id_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)
    with pytest.raises(module.StopExecution):
        module.load_preflight(path)


def test_private_preflight_fails_closed_on_subnet_drift(tmp_path: Path) -> None:
    path = tmp_path / "preflight.json"
    write_preflight(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["t1"]["blackhole_ip"] = "198.51.100.12"
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)
    with pytest.raises(module.StopExecution):
        module.load_preflight(path)


def test_private_workspace_is_0700(tmp_path: Path) -> None:
    root = module.create_private_workspace(tmp_path / "private")
    assert root.stat().st_mode & 0o777 == 0o700


def test_lab_profile_is_private_and_uses_no_production_identity(tmp_path: Path) -> None:
    root = module.create_private_workspace(tmp_path / "private")
    (root / "lab").mkdir(mode=0o700)
    path = tmp_path / "preflight.json"
    write_preflight(path)
    preflight = module.load_preflight(path)
    profile = module.create_lab_profile(root, preflight)
    profile_path = root / "lab/profile.json"
    assert profile_path.stat().st_mode & 0o777 == 0o600
    assert profile["broker_port"] == str(module.BROKER_PORT)
    assert profile["tls_server_name"] == module.TLS_SERVER_NAME
    assert profile["mqtt_username"].startswith("gate_a_")
    assert profile["mqtt_client_id"].startswith("gate-a-")
    assert len(profile["mqtt_password"]) >= 24




def test_resolve_esphome_reuses_existing_exact_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/local/bin/esphome" if name == "esphome" else None)
    monkeypatch.setattr(module, "_probe_exact_esphome", lambda command: command == ["/usr/local/bin/esphome"])
    command, source = module.resolve_esphome_command(tmp_path)
    assert command == ["/usr/local/bin/esphome"]
    assert source == "existing_exact_cli"
    assert not (tmp_path / "venv").exists()


def test_resolve_esphome_fails_closed_on_intel_macos_without_rust(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "_probe_exact_esphome", lambda command: False)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")
    with pytest.raises(module.StopExecution, match="no Rust toolchain"):
        module.resolve_esphome_command(tmp_path)
    assert not (tmp_path / "venv").exists()

def test_executor_has_no_board_or_t1_mutation_transport() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "esptool",
        "write-flash",
        "erase-flash",
        "ssh_argv",
        "scp_argv",
        "ip addr add",
        "docker run",
        "docker restart",
        "systemctl",
    )
    for token in forbidden:
        assert token not in source


def test_console_output_does_not_emit_private_profile_fields() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    print_region = source[source.index('print("GATE_A_PRIVATE_BUILD=PASS")') :]
    assert 'profile["mqtt_username"]' not in print_region
    assert 'profile["mqtt_password"]' not in print_region
    assert 'profile["mqtt_client_id"]' not in print_region
    assert 'preflight["t1"]["current_ip"]' not in print_region
    assert 'preflight["t1"]["live_alias"]' not in print_region
    assert 'preflight["t1"]["blackhole_ip"]' not in print_region
