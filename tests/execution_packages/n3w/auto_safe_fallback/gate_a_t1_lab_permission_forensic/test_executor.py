from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_t1_lab_permission_forensic/executor.py"

spec = importlib.util.spec_from_file_location("gate_a_t1_lab_permission_forensic", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_remote_forensic_is_readonly() -> None:
    source = module.REMOTE_FORENSIC
    required = (
        '"docker", "inspect"',
        '"docker", "image", "inspect"',
        '"docker", "exec"',
        '"cat", "/proc/1/status"',
        '"cat", "/etc/passwd"',
    )
    for token in required:
        assert token in source
    forbidden = (
        '"docker", "run"',
        '"docker", "rm"',
        '"docker", "restart"',
        '"docker", "stop"',
        '"ip", "addr", "add"',
        '"ip", "addr", "del"',
        '"systemctl"',
        '"chmod"',
        '"chown"',
    )
    for token in forbidden:
        assert token not in source


def test_forensic_reads_effective_pid1_identity_and_mosquitto_account() -> None:
    source = module.REMOTE_FORENSIC
    assert 'parse_effective_id(status_out, "Uid")' in source
    assert 'parse_effective_id(status_out, "Gid")' in source
    assert 'line.startswith("mosquitto:")' in source
    assert '"broker_process_is_mosquitto_account"' in source


def test_public_output_has_no_credentials_or_private_addresses() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    region = source[source.index("def run_forensic") :]
    for token in (
        "mqtt_username",
        "mqtt_password",
        "mqtt_client_id",
        "restore_host",
        "live_alias",
        "blackhole_ip",
        "server.key",
        "profile.json",
    ):
        assert token not in region


def test_no_board_transport() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    for token in ("esptool", "write-flash", "/dev/cu.", "/dev/tty"):
        assert token not in source
